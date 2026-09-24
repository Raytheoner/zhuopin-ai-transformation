"""Codex接缝验证：所有Popen均注入，不启动任何CLI。"""
import json
import sys
from pathlib import Path
from aibot_service import patrol_dispatch as pd
from aibot_service.repo_paths import resolve_patrol_charter_path

class Proc:
    pid=7654
    class Input:
        def write(self,text): pass
        def close(self): pass
    stdin=Input()
    def wait(self): return 0

class TestCodexPatrol:
    def charter(self,root):
        path=resolve_patrol_charter_path(root)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('隔离章程',encoding='utf-8')

    def configure(self,root,enabled=True):
        config=root/'.codex'; config.mkdir()
        (config/'runtime.local.json').write_text(json.dumps({'python':sys.executable}),encoding='utf-8')
        (config/'consumers.local.json').write_text(json.dumps({'patrol':{'enabled':enabled,'timeout_seconds':60}}),encoding='utf-8')
        provider=root/'0-学习与工具/codex-handoff/model_provider.py'
        provider.parent.mkdir(parents=True,exist_ok=True); provider.write_text('# placeholder, never executed',encoding='utf-8')

    def test_missing_policy_does_not_start_legacy(self,tmp_path):
        self.charter(tmp_path)
        calls=[]
        result=pd.dispatch_headless_patrol(tmp_path,popen=lambda *a,**kw:calls.append(a) or Proc(),pid_alive=lambda p:False,run_in_thread=lambda f:None)
        assert calls==[]
        assert result.action=='paused'

    def test_disabled_keeps_signal_file(self,tmp_path):
        self.charter(tmp_path); self.configure(tmp_path,False)
        signal=tmp_path/'signal-marker'; signal.write_text('pending')
        calls=[]
        result=pd.dispatch_headless_patrol(tmp_path,popen=lambda *a,**kw:calls.append(a) or Proc(),pid_alive=lambda p:False,run_in_thread=lambda f:None)
        assert not calls
        assert result.action=='paused'
        assert signal.read_text()=='pending'

    def test_enabled_only_starts_bounded_codex_provider(self,tmp_path):
        self.charter(tmp_path); self.configure(tmp_path)
        calls=[]
        result=pd.dispatch_headless_patrol(tmp_path,popen=lambda *a,**kw:calls.append(a) or Proc(),pid_alive=lambda p:False,run_in_thread=lambda f:None)
        assert result.action=='started'
        argv=calls[0][0]
        assert argv[0]==sys.executable
        assert 'model_provider.py' in argv[2]
        assert argv[argv.index('--sandbox')+1]=='workspace-write'
        assert '--enabled' in argv
        assert not any('claude' in a.lower() or 'dangerous' in a for a in argv)
        assert '--model' not in argv

class TestNoProgress:
    def test_long_zero_exit_with_unchanged_signal_halts(self,tmp_path,monkeypatch):
        import itertools
        monkeypatch.delenv('ZHUOPIN_CODEX_RUNTIME',raising=False)
        f=TestCodexPatrol(); f.charter(tmp_path); f.configure(tmp_path)
        pd.patrol_signal.raise_signal(tmp_path,letter_number='FIXTURE',archived_filename='fixture.md')
        calls=[]; alerts=[]
        def popen(*a,**kw):
            calls.append(1)
            assert len(calls)<=4, 'bounded fake prevents an infinite test loop'
            return Proc()
        pd.dispatch_headless_patrol(tmp_path,popen=popen,pid_alive=lambda p:False,
            run_in_thread=lambda f:f(),monotonic=itertools.count(0,100).__next__,sleep=lambda s:None,alert_send=alerts.append)
        assert len(calls)==3
        assert len(alerts)==1
        assert pd.patrol_signal.read_signal(tmp_path).present
