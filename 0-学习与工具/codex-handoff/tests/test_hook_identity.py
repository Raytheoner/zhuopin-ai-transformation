import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]

class TestHookAudit:
    def test_session_identity_without_prompt(self,tmp_path,monkeypatch):
        spec=importlib.util.spec_from_file_location('hook_bridge_under_test',ROOT/'0-学习与工具/codex-handoff/hook_bridge.py')
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        monkeypatch.setenv('ZHUOPIN_CODEX_STATE',str(tmp_path))
        module.audit({'hook_event_name':'PreToolUse','session_id':'test-session','turn_id':'turn','cwd':str(ROOT),'model':'verified','prompt':'SECRET_TEST'},[])
        row=json.loads(next((tmp_path/'hooks').glob('*.json')).read_text(encoding='utf-8'))
        assert row['session_id']=='test-session'
        assert row['cwd']==str(ROOT)
        assert 'SECRET_TEST' not in json.dumps(row)
