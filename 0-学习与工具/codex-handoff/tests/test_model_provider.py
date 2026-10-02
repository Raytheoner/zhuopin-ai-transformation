"""隔离模型进程夹具，不调用外网或业务。"""
import importlib.util
import json
from pathlib import Path
import sys
import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'model_provider.py'

def provider():
    assert SOURCE.is_file(), '统一 Codex provider 尚未实现'
    spec = importlib.util.spec_from_file_location('migration_model_provider', SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

class TestProvider:
    def test_safe_command_new_and_resume(self, tmp_path):
        p = provider()
        for thread in (None, '01234567-89ab-cdef-0123-456789abcdef'):
            args = p.command('codex.exe', tmp_path, tmp_path / 'final.txt', 'read-only', thread=thread)
            assert args[:5] == ['codex.exe', '-a', 'never', '-s', 'read-only']
            assert '--json' in args and args[-1] == '-'
            assert ('resume' in args) == bool(thread)
            assert not any('danger' in arg for arg in args)

    @pytest.mark.parametrize('model', ['sonnet', 'opus', 'haiku'])
    def test_reject_legacy_models(self, tmp_path, model):
        p = provider()
        with pytest.raises(ValueError):
            p.command('codex', tmp_path, tmp_path / 'final.txt', 'workspace-write', model=model)

    def test_reject_unbounded_permissions(self, tmp_path):
        p = provider()
        with pytest.raises(ValueError):
            p.command('codex', tmp_path, tmp_path / 'final.txt', 'danger-full-access')

    def test_zero_exit_is_not_turn_success(self):
        p = provider()
        result = p.summarize([{'type':'thread.started','thread_id':'test'}], 0)
        assert result['status'] == 'incomplete'
        assert result['accepted'] is False

    def test_tool_failure_is_visible(self):
        p = provider()
        result = p.summarize([
            {'type':'thread.started','thread_id':'test'},
            {'type':'item.completed','item':{'type':'command_execution','exit_code':7,'status':'failed'}},
            {'type':'turn.completed','usage':{'input_tokens':200000}},
        ], 0)
        assert result['tool_failures'] == 1
        assert result['status'] == 'tool_failed'
        assert result['current_context_tokens'] is None
        assert result['accepted'] is False

    def test_turn_failure_even_with_zero_exit(self):
        p = provider()
        result = p.summarize([{'type':'turn.failed','error':{'message':'denied'}}], 0)
        assert result['status'] == 'failed'

    def test_success_still_needs_product_acceptance(self):
        p = provider()
        result = p.summarize([
            {'type':'thread.started','thread_id':'test'},
            {'type':'item.completed','item':{'type':'command_execution','exit_code':0,'status':'completed'}},
            {'type':'turn.completed'},
        ], 0)
        assert result['status'] == 'output_needs_review'
        assert result['tool_events'] == 1
        assert result['accepted'] is False

    def test_pause_does_not_start_process(self, tmp_path):
        p = provider()
        def forbidden(*args, **kwargs):
            pytest.fail('暂停状态不能起进程')
        result = p.run(workspace=tmp_path, evidence=tmp_path/'evidence', prompt='hello', enabled=False, popen=forbidden)
        assert result['status'] == 'paused'
        assert (tmp_path/'evidence/result.json').is_file()

    @pytest.mark.parametrize('mode,expected', [('ok','output_needs_review'),('nonzero','failed'),('incomplete','incomplete'),('malformed','protocol_error'),('timeout','timeout')])
    def test_real_child_process_outcomes(self, tmp_path, mode, expected):
        p = provider()
        fake = tmp_path/'fake.py'
        fake.write_text('''import sys,json,time
sys.stdin.read()
mode=sys.argv[1]
print(json.dumps({'type':'thread.started','thread_id':'01234567-89ab-cdef-0123-456789abcdef'}),flush=True)
if mode=='timeout': time.sleep(30)
elif mode=='malformed': print('not JSON')
elif mode!='incomplete':
 print(json.dumps({'type':'item.completed','item':{'type':'command_execution','exit_code':0,'status':'completed'}}))
 print(json.dumps({'type':'turn.completed'}))
sys.exit(7 if mode=='nonzero' else 0)
''', encoding='utf-8')
        result = p.run(workspace=tmp_path, evidence=tmp_path/'evidence', prompt='fixture', enabled=True,
                       timeout=0.3 if mode=='timeout' else 10, executable=sys.executable,
                       argv_override=[sys.executable,str(fake),mode])
        assert result['status'] == expected
        assert result['accepted'] is False
        assert result['thread_id'] == '01234567-89ab-cdef-0123-456789abcdef'
        assert (tmp_path/'evidence/events.jsonl').is_file()
        assert json.loads((tmp_path/'evidence/result.json').read_text(encoding='utf-8'))['status'] == expected

class TestNativeTelemetry:
    def write(self,path,thread,cwd,info):
        rows=[{'type':'session_meta','payload':{'id':thread,'cwd':str(cwd)}},
              {'type':'turn_context','payload':{'model':'verified-model'}},
              {'type':'event_msg','payload':{'type':'token_count','info':info}}]
        path.write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf-8')

    def test_last_request_not_accumulated_usage(self,tmp_path):
        p=provider(); f=tmp_path/'rollout.jsonl'
        self.write(f,'t',tmp_path,{'last_token_usage':{'total_tokens':160000},'total_token_usage':{'total_tokens':900000}})
        result=p.native_telemetry(f,'t',tmp_path)
        assert result['current_context_tokens']==160000
        assert result['actual_model']=='verified-model'
        assert result['context_source']=='native.last_token_usage.total_tokens'

    def test_aggregate_only_is_unknown(self,tmp_path):
        p=provider(); f=tmp_path/'rollout.jsonl'
        self.write(f,'t',tmp_path,{'total_token_usage':{'total_tokens':900000}})
        assert p.native_telemetry(f,'t',tmp_path)['current_context_tokens'] is None

    def test_wrong_session_rejected(self,tmp_path):
        p=provider(); f=tmp_path/'rollout.jsonl'
        self.write(f,'different',tmp_path,{'last_token_usage':{'total_tokens':4}})
        with pytest.raises(ValueError): p.native_telemetry(f,'t',tmp_path)

    def test_wrong_workspace_rejected(self,tmp_path):
        p=provider(); f=tmp_path/'rollout.jsonl'
        self.write(f,'t',tmp_path/'other',{'last_token_usage':{'total_tokens':4}})
        with pytest.raises(ValueError): p.native_telemetry(f,'t',tmp_path)

    def test_compaction_uses_latest_context(self,tmp_path):
        p=provider(); f=tmp_path/'rollout.jsonl'
        self.write(f,'t',tmp_path,{'last_token_usage':{'total_tokens':170000}})
        with f.open('a',encoding='utf-8') as out:
            out.write(json.dumps({'type':'event_msg','payload':{'type':'token_count','info':{'last_token_usage':{'total_tokens':30000}}}})+'\n')
        assert p.native_telemetry(f,'t',tmp_path)['current_context_tokens']==30000

class TestContextGuard:
    def test_hard_limit(self):
        p=provider()
        assert p.context_guard(250000,now=10,started=0,soft_since=None)[0]=='hard_limit'
    def test_soft_grace(self):
        p=provider()
        reason,soft=p.context_guard(150000,now=10,started=0,soft_since=None)
        assert reason is None and soft==10
        assert p.context_guard(151000,now=909,started=0,soft_since=soft)[0] is None
        assert p.context_guard(151000,now=910,started=0,soft_since=soft)[0]=='soft_grace_expired'
    def test_unknown_fails_closed(self):
        p=provider()
        assert p.context_guard(None,now=121,started=0,soft_since=None)[0]=='context_unavailable'
    def test_below_threshold(self):
        p=provider()
        assert p.context_guard(40000,now=9000,started=0,soft_since=None)==(None,None)

class TestModelRoutes:
    def test_inherit_does_not_invent_model(self,tmp_path):
        assert provider().resolve_model('inherit',tmp_path) is None
    def test_route_requires_explicit_policy(self,tmp_path):
        with pytest.raises(ValueError): provider().resolve_model('routine',tmp_path)
    def test_policy_can_deliberately_inherit(self,tmp_path):
        d=tmp_path/'.codex'; d.mkdir()
        (d/'model-policy.json').write_text(json.dumps({'routes':{'routine':None,'design':None}}))
        assert provider().resolve_model('routine',tmp_path) is None
        assert provider().resolve_model('design',tmp_path) is None

class TestTelemetryFreshness:
    def test_latest_unknown_does_not_reuse_old_value(self,tmp_path):
        p=provider(); f=tmp_path/'rollout.jsonl'
        TestNativeTelemetry().write(f,'t',tmp_path,{'last_token_usage':{'total_tokens':12000}})
        with f.open('a',encoding='utf-8') as out:
            out.write(json.dumps({'type':'event_msg','payload':{'type':'token_count','info':None}})+'\n')
        assert p.native_telemetry(f,'t',tmp_path)['current_context_tokens'] is None

    def test_new_turn_does_not_reuse_old_value(self,tmp_path):
        p=provider(); f=tmp_path/'rollout.jsonl'
        TestNativeTelemetry().write(f,'t',tmp_path,{'last_token_usage':{'total_tokens':12000}})
        with f.open('a',encoding='utf-8') as out:
            out.write(json.dumps({'type':'turn_context','payload':{'model':'verified-model'}})+'\n')
        assert p.native_telemetry(f,'t',tmp_path)['current_context_tokens'] is None

class TestReviewRegressions:
    def test_zero_grace_disables_soft_timer_but_not_hard_limit(self):
        p=provider()
        assert p.context_guard(160000,now=10,started=0,soft_since=None,grace_seconds=0)[0] is None
        assert p.context_guard(250000,now=10,started=0,soft_since=None,grace_seconds=0)[0]=='hard_limit'

    def test_audit_write_failure_stops_owned_child(self,tmp_path,monkeypatch):
        import subprocess
        p=provider(); stopped=[]
        class Child:
            pid=12345
            returncode=None
            def poll(self): return self.returncode
            def communicate(self,*a,**k): raise subprocess.TimeoutExpired('fixture',2)
        child=Child()
        def popen(argv,**kw):
            kw['stdout'].write(json.dumps({'type':'thread.started','thread_id':'01234567-89ab-cdef-0123-456789abcdef'})+'\n')
            kw['stdout'].flush()
            return child
        write=p.write_json
        def broken(path,value):
            if Path(path).name=='session.json': raise OSError('fixture audit disk failure')
            return write(path,value)
        monkeypatch.setattr(p,'write_json',broken)
        monkeypatch.setattr(p,'find_telemetry',lambda *a,**k:{'current_context_tokens':10})
        monkeypatch.setattr(p,'stop_child',lambda proc:stopped.append(proc))
        result=p.run(workspace=tmp_path,evidence=tmp_path/'e',prompt='test',enabled=True,executable='fixture',popen=popen)
        assert result['status']=='start_failed'
        assert stopped==[child]

class TestRuntimeInheritance:
    def test_linked_worktree_uses_common_root_runtime(self,tmp_path,monkeypatch):
        from types import SimpleNamespace
        p=provider(); main=tmp_path/'main'; wt=tmp_path/'linked worktree'
        wt.mkdir(); (main/'.codex').mkdir(parents=True); (main/'.git').mkdir()
        (main/'.codex/runtime.local.json').write_text(json.dumps({'codex_executable':'verified-native.exe'}))
        monkeypatch.delenv('ZHUOPIN_CODEX_RUNTIME',raising=False)
        monkeypatch.delenv('ZHUOPIN_CODEX_EXECUTABLE',raising=False)
        monkeypatch.setattr(p.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=str(main/'.git')))
        monkeypatch.setattr(p.shutil,'which',lambda name:None)
        assert p.resolve_executable(wt)=='verified-native.exe'


def d3_run(p, tmp_path, monkeypatch, *, kill_code=0, kill_error=None,
           wait_error=None, already_exited=False):
    """仅替换 OS 观察；request/process/result 全由生产 run 写出。"""
    from types import SimpleNamespace
    import subprocess
    class Child:
        pid = 12345
        returncode = 9 if already_exited else None
        def poll(self): return self.returncode
        def communicate(self, *a, **kw): raise subprocess.TimeoutExpired('fixture', 2)
        def kill(self): self.returncode = 9
        def wait(self, timeout):
            failure = wait_error.pop(0) if isinstance(wait_error, list) and wait_error else wait_error
            if failure: raise failure
            self.returncode = 9
            return 9
    child = Child()
    evidence = tmp_path/'evidence'
    def taskkill(argv, **kw):
        pending = json.loads((evidence/'result.json').read_text(encoding='utf8'))
        assert pending['termination']['outcome'] == 'termination_unknown'
        if kill_error: raise kill_error
        return SimpleNamespace(returncode=kill_code, stdout=b'\xff\x00ok', stderr=b'')
    monkeypatch.setattr(p.sys, 'platform', 'win32')
    monkeypatch.setattr(p.subprocess, 'run', taskkill)
    monkeypatch.setattr(p, 'context_guard', lambda *a, **kw: ('hard_limit', None))
    monkeypatch.setattr(p, 'find_telemetry', lambda *a: {'current_context_tokens':250000})
    def popen(*a, **kw):
        kw['stdout'].write(json.dumps({'type':'thread.started',
            'thread_id':'01234567-89ab-cdef-0123-456789abcdef'})+'\n')
        kw['stdout'].flush()
        return child
    result = p.run(workspace=tmp_path, evidence=evidence, prompt='fixture', enabled=True,
                   executable='fixture', popen=popen,
                   source_id='sample:proposal', attempt_id='d3', require_context=True)
    return evidence, result


def test_d3_production_identity_and_raw_observations(tmp_path, monkeypatch):
    import base64, hashlib
    p = provider()
    evidence, result = d3_run(p, tmp_path, monkeypatch)
    process = json.loads((evidence/'process.json').read_text(encoding='utf8'))
    assert process['attempt_id'] == 'd3'
    assert process['request_sha256'] == hashlib.sha256((evidence/'request.json').read_bytes()).hexdigest()
    term = result['termination']
    assert term['process_sha256'] == hashlib.sha256((evidence/'process.json').read_bytes()).hexdigest()
    assert term['outcome'] == 'tree_termination_confirmed'
    observation = term['attempts'][0]
    assert base64.b64decode(observation['taskkill']['stdout_base64']) == b'\xff\x00ok'
    assert observation['wait']['returncode'] == result['exit_code'] == 9
    assert observation['fallback']['invoked'] is False


@pytest.mark.parametrize('failure', ['nonzero', 'kill_timeout', 'kill_error', 'wait_timeout', 'wait_error', 'exited'])
def test_d3_failed_cleanup_cannot_claim_tree(tmp_path, monkeypatch, failure):
    import subprocess
    options = {
        'nonzero': {'kill_code': 5},
        'kill_timeout': {'kill_error': subprocess.TimeoutExpired('taskkill', 15, output=b'partial')},
        'kill_error': {'kill_error': OSError('denied')},
        'wait_timeout': {'wait_error': subprocess.TimeoutExpired('wait', 15)},
        'wait_error': {'wait_error': OSError('wait failed')},
        'exited': {'already_exited': True},
    }
    _, result = d3_run(provider(), tmp_path, monkeypatch, **options[failure])
    term = result['termination']
    assert result['status'] == 'context_stopped'
    assert term['outcome'] == ('parent_exited_only' if failure == 'exited' else 'termination_failed')
    first = term['attempts'][0]
    if failure == 'kill_timeout':
        assert first['taskkill']['timed_out'] is True
        assert first['taskkill']['returncode'] is None
    if failure == 'exited': assert first['taskkill']['invoked'] is False


def test_d3_process_hash_read_failure_still_cleans_owned_process(tmp_path, monkeypatch):
    p = provider()
    original = Path.read_bytes
    def broken(path):
        if path.name == 'process.json': raise OSError('process read denied')
        return original(path)
    monkeypatch.setattr(Path, 'read_bytes', broken)
    stopped = []
    stop = p.stop_child
    def counted(proc):
        stopped.append(proc)
        return stop(proc)
    monkeypatch.setattr(p, 'stop_child', counted)
    _, result = d3_run(p, tmp_path, monkeypatch)
    assert stopped and stopped[0].poll() == 9
    assert result['error']


def test_d3_initial_exception_and_hash_failure_still_cleans(tmp_path, monkeypatch):
    p = provider()
    write, read = p.write_json, Path.read_bytes
    def broken_write(path, value):
        if Path(path).name == 'session.json': raise OSError('session write failed')
        return write(path, value)
    def broken_read(path):
        if path.name == 'process.json': raise OSError('process read failed')
        return read(path)
    monkeypatch.setattr(p, 'write_json', broken_write)
    monkeypatch.setattr(Path, 'read_bytes', broken_read)
    stopped = []
    stop = p.stop_child
    def counted(proc):
        stopped.append(proc)
        return stop(proc)
    monkeypatch.setattr(p, 'stop_child', counted)
    _, result = d3_run(p, tmp_path, monkeypatch)
    assert stopped and stopped[0].poll() == 9
    assert 'process read failed' in result['error']


def test_d3_pending_write_failure_never_loses_first_cleanup(tmp_path, monkeypatch):
    p = provider()
    write = p.write_json
    failed = False
    def broken(path, value):
        nonlocal failed
        if value.get('status') == 'termination_pending' and not failed:
            failed = True
            # 先留下 pending，模拟 replace 后的异常；清理动作仍应执行。
            write(path, value)
            raise OSError('pending write failed')
        return write(path, value)
    monkeypatch.setattr(p, 'write_json', broken)
    _, result = d3_run(p, tmp_path, monkeypatch)
    assert 'pending write failed' in result['error']
    assert len(result['termination']['attempts']) == 1
    assert result['exit_code'] == 9


def test_d3_cleanup_reentry_preserves_initial_wait_failure(tmp_path, monkeypatch):
    import subprocess
    p = provider()
    write = p.write_json
    writes = []
    def fail_first_pending(path, value):
        write(path, value)
        if value.get('status') == 'termination_pending':
            writes.append(True)
            if len(writes) == 1: raise OSError('pending disk failure')
    monkeypatch.setattr(p, 'write_json', fail_first_pending)
    _, result = d3_run(p, tmp_path, monkeypatch,
                       wait_error=[subprocess.TimeoutExpired('wait', 15), None])
    attempts = result['termination']['attempts']
    assert len(attempts) == 2
    assert attempts[0]['wait']['timed_out'] is True
    assert attempts[1]['wait']['returned'] is True
    assert [item['sequence'] for item in attempts] == [1, 2]
    assert result['termination']['outcome'] == 'termination_failed'


@pytest.mark.skipif(sys.platform != 'win32', reason='原生 Windows taskkill 夹具')
def test_d3_native_windows_tree_and_child_handle(tmp_path, monkeypatch):
    """真实 OS 命令与独立子句柄观察；不启动模型，不读取旧运行现场。"""
    import ctypes
    from ctypes import wintypes
    import subprocess
    p = provider()
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    evidence = tmp_path/'native'
    owned = []
    handles = []
    code = (
        "import subprocess,sys,json,time; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(90)']); "
        "print(json.dumps({'type':'thread.started','thread_id':'01234567-89ab-cdef-0123-456789abcdef'}),flush=True); "
        "print(json.dumps({'type':'fixture.child','pid':child.pid}),flush=True); time.sleep(90)"
    )
    def popen(*a, **kw):
        proc = subprocess.Popen(*a, **kw)
        owned.append(proc)
        return proc
    def guard(*a, **kw):
        child = next(event['pid'] for event in p.event_objects(evidence/'events.jsonl')
                     if event['type'] == 'fixture.child')
        handle = kernel.OpenProcess(0x00100001, False, child)  # SYNCHRONIZE | TERMINATE
        assert handle, ctypes.get_last_error()
        handles.append(handle)
        assert kernel.WaitForSingleObject(handle, 0) == 258
        return 'hard_limit', None
    monkeypatch.setattr(p, 'find_telemetry', lambda *a: {'current_context_tokens':250000})
    monkeypatch.setattr(p, 'context_guard', guard)
    try:
        result = p.run(workspace=tmp_path, evidence=evidence, prompt='fixture', enabled=True,
                       executable=sys.executable, argv_override=[sys.executable, '-c', code],
                       popen=popen, require_context=True, source_id='sample:proposal', attempt_id='native')
        assert result['termination']['outcome'] == 'tree_termination_confirmed'
        assert result['termination']['attempts'][0]['taskkill']['returncode'] == 0
        assert kernel.WaitForSingleObject(handles[0], 5000) == 0
        spec = importlib.util.spec_from_file_location('native_d3_driver', SOURCE.parent/'workflow_driver.py')
        driver = importlib.util.module_from_spec(spec); spec.loader.exec_module(driver)
        binding = dict(task_id='sample', phase='proposal', attempt_id='native', source_id='sample:proposal',
                       workspace=str(tmp_path.resolve()), evidence_dir=str(evidence.resolve()),
                       thread_id=result['thread_id'], prompt_sha256=result['prompt_sha256'])
        sealed = driver.seal_termination_evidence(evidence, binding)
        assert driver.verify_termination_evidence(evidence, binding, sealed)['status'] == 'satisfied'
    finally:
        for proc in owned:
            if proc.poll() is None: p.stop_child(proc)
        for handle in handles:
            if kernel.WaitForSingleObject(handle, 0) == 258:
                kernel.TerminateProcess(handle, 1)
            kernel.CloseHandle(handle)


class TestProcessCompletionExit:
    THREAD = '01234567-89ab-cdef-0123-456789abcdef'

    @staticmethod
    def result(p, *, failed_tool=True, exit_code=0):
        events = [{'type': 'thread.started', 'thread_id': TestProcessCompletionExit.THREAD}]
        if failed_tool:
            events.append({'type': 'item.completed', 'item': {
                'type': 'command_execution', 'status': 'failed', 'exit_code': 7}})
        events.append({'type': 'turn.completed'})
        return {**p.summarize(events, exit_code), 'timed_out': False,
                'malformed_events': 0, 'error': None, 'context_reason': None}

    @staticmethod
    def cli(p, result, tmp_path, monkeypatch, *, explicit):
        import io
        evidence = tmp_path / 'evidence'
        evidence.mkdir(exist_ok=True)
        original = json.dumps(result, sort_keys=True).encode('utf-8')
        def run(**kwargs):
            assert 'process_completion_exit' not in kwargs
            (evidence / 'result.json').write_bytes(original)
            return result
        monkeypatch.setattr(p, 'run', run)
        monkeypatch.setattr(sys, 'argv', ['model_provider.py', '--workspace', str(tmp_path),
            '--evidence', str(evidence), *(['--process-completion-exit'] if explicit else [])])
        monkeypatch.setattr(sys, 'stdin', io.StringIO('isolated lifecycle fixture'))
        code = p.main()
        assert (evidence / 'result.json').read_bytes() == original
        return code

    def test_default_keeps_tool_failure_nonzero(self, tmp_path, monkeypatch):
        p = provider(); result = self.result(p)
        assert self.cli(p, result, tmp_path, monkeypatch, explicit=False) == 1
        assert result['status'] == 'tool_failed' and result['accepted'] is False

    @pytest.mark.parametrize('failed_tool', [True, False])
    def test_explicit_mode_reports_completed_process_without_accepting_output(
            self, tmp_path, monkeypatch, failed_tool):
        p = provider(); result = self.result(p, failed_tool=failed_tool)
        assert self.cli(p, result, tmp_path, monkeypatch, explicit=True) == 0
        assert result['status'] == ('tool_failed' if failed_tool else 'output_needs_review')
        assert result['tool_failures'] == (1 if failed_tool else 0)
        assert result['accepted'] is False

    @pytest.mark.parametrize('updates, expected', [
        ({'exit_code': 7, 'status': 'failed'}, 1),
        ({'status': 'failed'}, 1),
        ({'status': 'incomplete'}, 1),
        ({'status': 'paused'}, 1),
        ({'status': 'start_failed', 'error': 'unavailable'}, 1),
        ({'status': 'timeout', 'timed_out': True}, 124),
        ({'timed_out': True}, 1),
        ({'status': 'context_stopped', 'context_reason': 'context_unavailable'}, 1),
        ({'context_reason': 'context_unavailable'}, 1),
        ({'context_reason': 'hard_limit'}, 1),
        ({'status': 'protocol_error', 'malformed_events': 1}, 1),
        ({'malformed_events': 1}, 1),
        ({'malformed_events': False}, 1),
        ({'error': 'CLI error'}, 1),
        ({'thread_id': None}, 1),
        ({'thread_id': ''}, 1),
        ({'thread_id': 'not-a-native-uuid'}, 1),
        ({'thread_id': True}, 1),
        ({'turn_completed': False}, 1),
        ({'turn_completed': 1}, 1),
        ({'exit_code': False}, 1),
        ({'exit_code': True}, 1),
        ({'exit_code': 0.0}, 1),
        ({'exit_code': '0'}, 1),
        ({'accepted': True}, 1),
    ])
    def test_explicit_mode_rejects_fatal_or_incomplete_terminal(
            self, tmp_path, monkeypatch, updates, expected):
        p = provider(); result = {**self.result(p), **updates}
        assert self.cli(p, result, tmp_path, monkeypatch, explicit=True) == expected

    @pytest.mark.parametrize('field', ['exit_code', 'thread_id', 'turn_completed',
        'timed_out', 'malformed_events', 'error', 'context_reason', 'accepted'])
    def test_explicit_mode_rejects_missing_terminal_field(self, tmp_path, monkeypatch, field):
        p = provider(); result = self.result(p); result.pop(field)
        assert self.cli(p, result, tmp_path, monkeypatch, explicit=True) == 1
