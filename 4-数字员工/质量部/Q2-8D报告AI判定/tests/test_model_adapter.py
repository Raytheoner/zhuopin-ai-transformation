import json
import pytest
from q2_8d_verdict.model_adapter import build_argv,parse_events,ModelError,FAIL_CLOSED_NOTICE

def test_cli_argv_pins_model_and_limits_capabilities(tmp_path):
    argv=build_argv(tmp_path,tmp_path/'schema.json',[])
    assert argv[argv.index('--model')+1]=='gpt-6-luna'
    assert argv[argv.index('--sandbox')+1]=='read-only'
    assert '--strict-config' in argv and '--ephemeral' in argv
    for capability in ('shell_tool','plugins','apps','web_search','multi_agent','view_image'):
        assert any(capability in s for s in argv)
    assert not any('dangerously' in s or s.startswith('--ignore-') for s in argv)

def test_events_usage_unknown_not_zero():
    result=parse_events(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'{"ok":true}'}}))
    assert result['payload']=={'ok':True} and result['usage'] is None

def test_known_closed_capability_notice_not_business_error():
    text='\n'.join(json.dumps(e) for e in [{'type':'item.completed','item':{'type':'error','message':FAIL_CLOSED_NOTICE}}, {'type':'item.completed','item':{'type':'agent_message','text':'{"ok":true}'}}])
    assert parse_events(text)['payload']=={'ok':True}

@pytest.mark.parametrize('event',[{'type':'item.started','item':{'type':'command_execution','command':'whoami'}},{'type':'error','message':'quota'},{'type':'response.created','model':'other-model'}])
def test_tool_error_or_foreign_model_rejected(event):
    with pytest.raises(ModelError):parse_events(json.dumps(event))

def test_output_limit_and_invalid_json():
    for text in ('x'*(2*1024*1024+1),'invalid'):
        with pytest.raises(ModelError):parse_events(text)
