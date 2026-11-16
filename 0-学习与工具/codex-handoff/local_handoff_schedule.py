"""单仓库本地接力维护周期；不调用模型、不修改Git或业务状态。"""
from datetime import datetime, timedelta, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from quality_handoff import Store, HandoffError, encode, digest, DOMAINS, domain_store, check_all

BJT = timezone(timedelta(hours=8))


def identity(root):
    return hashlib.sha256(os.path.normcase(str(Path(root).resolve())).encode()).hexdigest()[:12]


def period(now):
    if now.tzinfo is None: raise ValueError('timezone-aware clock required')
    local = now.astimezone(BJT)
    due = local.replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(days=(local.weekday()-3) % 7)
    return due if local >= due else due-timedelta(days=7)


def next_due(now):
    return period(now)+timedelta(days=7)


def related_paths():
    return [profile[key] for profile in DOMAINS.values() for key in ('entry', 'base')]


def maintain_all(root, who, dirty):
    results = {}
    for domain in DOMAINS:
        store = domain_store(root, domain)
        tool = root/'0-学习与工具/工具-共享文档编辑锁.py'
        args = [sys.executable, str(tool), '--file', store.entry_rel]
        r = subprocess.run(args+['acquire', '--who', who, '--note', '唯一纯本地维护任务；本周期仅资料生成/完整性，无业务状态判断'], cwd=root, capture_output=True, encoding='utf-8', timeout=30)
        if r.returncode:
            raise HandoffError('official card lock busy/unavailable: '+r.stdout[-300:])
        try:
            if dirty():
                raise HandoffError('author edits appeared after check; no further maintenance applied')
            results[domain] = store.apply()
        finally:
            r = subprocess.run(args+['release', '--who', who], cwd=root, capture_output=True, encoding='utf-8', timeout=30)
            if r.returncode:
                raise HandoffError('official card lock release failed: '+r.stdout[-300:])
    return {'domains': results, 'changed': any(r['changed'] for r in results.values()),
            'paths': [p for r in results.values() for p in r['paths']]}


class Runner:
    def __init__(self, state_root, config, check, maintain, dirty, notify, clock=None):
        self.root=Path(state_root);self.config=config;self.check=check;self.maintain=maintain;self.dirty=dirty;self.notify=notify
        self.clock=clock or (lambda:datetime.now(BJT));self.guard=Store(self.root,'.scheduler','unused')

    def read_state(self):
        p=self.root/'state.json'
        return json.loads(p.read_bytes()) if p.exists() else {}

    def save(self,state):
        Store.atomic(self.root/'state.json',encode(state))

    def reset_retry(self):
        with self.guard.lock():
            state=self.read_state()
            if state.get('attempt_period')!=period(self.clock()).isoformat() or state.get('attempts',0)<4:
                raise HandoffError('no exhausted current period to explicitly retry')
            raw=encode(state);Store.immutable(self.root/'operator-resets'/(digest(raw)+'.json'),raw)
            state.update(attempts=0,next_retry=None,last_outcome='explicit_operator_retry')
            self.save(state)
            return {'outcome':'explicit_operator_retry','period':state['attempt_period'],'success_recorded':False}

    def run(self):
        with self.guard.lock():
            now=self.clock();due=period(now);key=due.isoformat();installed=datetime.fromisoformat(self.config['installed_at'])
            if due<installed:return {'outcome':'before_installation','next_beijing':next_due(now).isoformat()}
            state=self.read_state()
            if state.get('success_period')==key:return {'outcome':'already_completed','period':key}
            if state.get('attempt_period')!=key:
                state.update(attempt_period=key,attempts=0,next_retry=None)
            if state.get('next_retry') and now<datetime.fromisoformat(state['next_retry']):return {'outcome':'retry_not_due','period':key}
            if state['attempts']>=4:return {'outcome':'exhausted','period':key,'recovery':'explicit local retry after correcting cause; no automatic fallback'}
            try:
                checked=self.check()
                if self.dirty():
                    state.update(last_checked_period=key,last_outcome='checked_only',unresolved=None)
                    self.save(state);return {'outcome':'checked_only','period':key,'integrity':checked}
                result=self.maintain();self.check()
                state.update(success_period=key,last_outcome='maintained',unresolved=None,next_retry=None)
                self.save(state);return {'outcome':'maintained','period':key,'maintenance':result}
            except Exception as exc:
                message=type(exc).__name__+': '+str(exc);fingerprint=digest(message.encode());old=state.get('unresolved') or {}
                notified=old.get('notified',False) if old.get('fingerprint')==fingerprint else False
                notice_error=None
                if not notified:
                    try:notified=bool(self.notify(message))
                    except Exception as e:notice_error=str(e)
                state.update(attempts=state['attempts']+1,next_retry=(now+timedelta(hours=1)).isoformat(),last_outcome='failed',unresolved={'fingerprint':fingerprint,'message':message,'notified':notified,'notification_error':notice_error})
                self.root.mkdir(parents=True,exist_ok=True)
                raw=encode({'time':now.isoformat(),'period':key,'attempt':state['attempts'],'error':message,'notification_accepted':notified})
                Store.immutable(self.root/'failures'/(digest(raw)+'.json'),raw)
                self.save(state);return {'outcome':'failed','period':key,'error':message,'attempt':state['attempts'],'notification_accepted':notified}


def notify_windows(message):
    """只给当前用户的实际活动控制台会话发本机消息；没有桌面就返回失败。"""
    if os.name!='nt':return False
    import ctypes
    from ctypes import wintypes as w
    kernel=ctypes.windll.kernel32;wts=ctypes.windll.wtsapi32
    kernel.WTSGetActiveConsoleSessionId.restype=w.DWORD
    sid=kernel.WTSGetActiveConsoleSessionId()
    if sid==0xFFFFFFFF:return False
    query=wts.WTSQuerySessionInformationW;query.argtypes=[w.HANDLE,w.DWORD,ctypes.c_int,ctypes.POINTER(w.LPWSTR),ctypes.POINTER(w.DWORD)]
    user=w.LPWSTR();size=w.DWORD()
    if not query(None,sid,5,ctypes.byref(user),ctypes.byref(size)):return False
    try:
        if not user.value or user.value.casefold()!=os.environ.get('USERNAME','').casefold():return False
    finally:
        wts.WTSFreeMemory.argtypes=[w.LPVOID];wts.WTSFreeMemory(user)
    send=wts.WTSSendMessageW;send.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,w.DWORD,w.LPWSTR,w.DWORD,w.DWORD,w.DWORD,ctypes.POINTER(w.DWORD),w.BOOL]
    title='接力维护异常';response=w.DWORD();text=message[:1200]
    return bool(send(None,sid,title,len(title)*2,text,len(text)*2,0x30,0,ctypes.byref(response),False))


def describe(root,now=None):
    root=Path(root).resolve();now=now or datetime.now(BJT);rid=identity(root)
    return {'repository':str(root),'identity':rid,'task_name':'ZhuopinHandoff-'+rid,'next_beijing':next_due(now).isoformat(),'next_local':next_due(now).astimezone().isoformat(),'config':str(root/'reports/local-handoff'/rid/'schedule.json'),'script':str(Path(__file__).resolve()),'python':sys.executable}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',default=str(Path(__file__).resolve().parents[2]));g=p.add_mutually_exclusive_group(required=True)
    for f in ('describe','configure','run-due','retry-exhausted'):g.add_argument('--'+f,action='store_true')
    a=p.parse_args(argv);root=Path(a.root).resolve();proposal=describe(root);config_path=Path(proposal['config'])
    if a.describe:print(json.dumps(proposal,ensure_ascii=False));return 0
    if a.configure:
        files=[Path(__file__).resolve(),Path(__file__).with_name('quality_handoff.py')]
        config={**proposal,'installed_at':datetime.now(BJT).isoformat(),'code_hashes':{str(f):digest(f.read_bytes()) for f in files}}
        Store.atomic(config_path,encode(config));print(json.dumps(config,ensure_ascii=False));return 0
    try:
        config=json.loads(config_path.read_bytes())
        if config['identity']!=proposal['identity']:raise HandoffError('repository identity mismatch')
        def check():
            if any(digest(Path(f).read_bytes())!=h for f,h in config['code_hashes'].items()):raise HandoffError('installed code drift; explicit reinstall required')
            return check_all(root)
        def dirty():
            r=subprocess.run(['git','status','--porcelain=v1','--untracked-files=all','--',*related_paths()],cwd=root,capture_output=True,encoding='utf-8',timeout=30)
            if r.returncode:raise HandoffError('Git read failed; no maintenance applied')
            return bool(r.stdout.strip())
        def maintain():
            return maintain_all(root, 'LocalHandoff-'+proposal['identity'], dirty)
        runner=Runner(config_path.parent,config,check,maintain,dirty,notify_windows)
        if a.retry_exhausted:
            print(json.dumps(runner.reset_retry(),ensure_ascii=False));return 0
        result=runner.run()
        if result['outcome']=='failed':print(json.dumps(result,ensure_ascii=False),file=sys.stderr);return 2
        prior=config_path.parent/'configuration-error.json'
        if prior.exists() and result['outcome'] not in ('retry_not_due','exhausted'):
            previous=json.loads(prior.read_bytes());previous['resolved']=True;Store.atomic(prior,encode(previous))
        return 0
    except Exception as exc:
        # 配置未安装/坏配置也失败，不启动模型；日志至少落在当前仓库固定本机目录。
        error={'error':str(exc),'fingerprint':digest(str(exc).encode()),'notification_accepted':False,'resolved':False}
        try:
            with Store(config_path.parent,'.scheduler','unused').lock():
                path=config_path.parent/'configuration-error.json';old=json.loads(path.read_bytes()) if path.exists() else {}
                accepted=old.get('notification_accepted',False) if old.get('fingerprint')==error['fingerprint'] and not old.get('resolved') else False
                error['notification_accepted']=accepted or notify_windows(str(exc))
                Store.atomic(path,encode(error))
        except Exception as notice_exc:
            error['notification_error']=str(notice_exc)
            try:Store.immutable(config_path.parent/'pending-notifications'/(digest(encode(error))+'.json'),encode(error))
            except OSError:pass
        print(json.dumps(error,ensure_ascii=False),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
