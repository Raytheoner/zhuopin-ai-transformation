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
