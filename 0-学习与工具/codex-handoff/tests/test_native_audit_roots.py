"""Native guards keep shared locks canonical and all adapter traces local."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
GUARD_NAMES = ('hooks-common.ps1','hooks-pretooluse-dedup-guard.ps1',
    'hooks-pretooluse-editlock-guard.ps1','hooks-pretooluse-queue-read-guard.ps1',
    'mail-native.ps1','protected-native.ps1','protected-paths.json',
    'sentinel-mojibake.ps1','sentinel-pronoun.ps1','sentinels-mode.json')
QUEUE_REL = '1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md'

def load_bridge():
    spec = importlib.util.spec_from_file_location('audit_root_bridge', BASE/'hook_bridge.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

@pytest.mark.parametrize('event_name', ['PreToolUse','PostToolUse'])
def test_adapter_cannot_inherit_an_external_audit_destination(tmp_path, monkeypatch, event_name):
    bridge = load_bridge()
    monkeypatch.setattr(bridge, 'ROOT', tmp_path/'source')
    monkeypatch.setenv('ZHUOPIN_SENTINEL_AUDIT_ROOT', str(tmp_path/'other'))
    env = bridge.native_guard_environment(event_name)
    assert env['ZHUOPIN_SENTINEL_AUDIT_ROOT'] == str(bridge.ROOT)
    assert os.environ['ZHUOPIN_SENTINEL_AUDIT_ROOT'] == str(tmp_path/'other')

def test_native_adapter_preserves_shared_data_root_for_both_phases(tmp_path, monkeypatch):
    bridge = load_bridge()
    monkeypatch.setattr(bridge, 'ROOT', tmp_path/'source')
    shared = str(tmp_path/'canonical-shared')
    monkeypatch.setenv('ZHUOPIN_SENTINEL_REPO_ROOT', shared)
    assert bridge.native_guard_environment('PreToolUse')['ZHUOPIN_SENTINEL_REPO_ROOT'] == shared
    assert bridge.native_guard_environment('PostToolUse')['ZHUOPIN_SENTINEL_REPO_ROOT'] == shared
    assert os.environ['ZHUOPIN_SENTINEL_REPO_ROOT'] == shared

@pytest.fixture
def lane(tmp_path_factory, request):
    token = hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:6]
    folder = tmp_path_factory.getbasetemp()/token
    main, source, state = folder/'m', folder/'w', folder/'s'
    main.mkdir(parents=True)
    empty_config = folder/'empty-gitconfig';empty_config.write_bytes(b'')
    empty_hooks = folder/'empty-hooks';empty_hooks.mkdir()
    env = dict(os.environ)
    for name in list(env):
        if name.upper().startswith(('ERP_','SRM_','CRM_','OPENAI_','ANTHROPIC_','CLAUDE_','WECOM','AIBOT','ZHUOPIN_','GIT_')):
            env.pop(name, None)
    env.update(GIT_ALLOW_PROTOCOL='file',GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=str(empty_config),
        GIT_CONFIG_SYSTEM=str(empty_config),GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='core.hooksPath',
        GIT_CONFIG_VALUE_0=str(empty_hooks),GIT_OPTIONAL_LOCKS='0',GIT_TERMINAL_PROMPT='0',
        PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',ZHUOPIN_CODEX_STATE=str(state))
    def git(*args):
        return subprocess.run(['git',*args],cwd=main,env=env,capture_output=True,text=True,encoding='utf8',check=True).stdout.strip()
    names = ['0-学习与工具/codex-handoff/'+name for name in ('hook_bridge.py','hook_configuration.py','hook_audit_store.py')]
    names += ['0-学习与工具/codex-handoff/guards/'+name for name in GUARD_NAMES]
    for relative in names:
        path = main/relative;path.parent.mkdir(parents=True,exist_ok=True)
        raw = (REPO/relative).read_bytes()
        path.write_bytes(raw)
        assert path.read_bytes() == raw
    target = main/QUEUE_REL;target.parent.mkdir(parents=True)
    target.write_text('# Synthetic shared queue\n',encoding='utf8')
    git('init','-q','-b','master')
    for key,value in (('user.name','Native audit fixture'),('user.email','fixture@example.invalid'),('commit.gpgsign','false')):
        git('config',key,value)
    git('add','--',*names,QUEUE_REL)
    git('commit','-qm','synthetic native audit fixture')
    git('worktree','add','-q','-b','codex/audit-fixture',str(source),'HEAD')
    # Model the original shared main before native guard installation. The
    # candidate itself retains all ten approved dependencies and its policy.
    (main/'0-学习与工具/codex-handoff/guards/sentinels-mode.json').unlink()
    assert not (source/'.codex/hooks.json').exists()
    def event(name, patch=None):
        value={'hook_event_name':name,'session_id':'synthetic-native-audit','cwd':str(source)}
        if patch is None:value.update(tool_name='exec_command',tool_input={'cmd':'Get-Date'})
        else:value.update(tool_name='apply_patch',tool_input={'command':patch})
        return value
    def run(value):
        result=subprocess.run([sys.executable,'-B',str(source/'0-学习与工具/codex-handoff/hook_bridge.py')],
            cwd=source,env=env,input=json.dumps(value,ensure_ascii=False),text=True,capture_output=True,encoding='utf8')
        assert not (source/'.codex/hooks.json').exists(), 'fixture must never become a configured Codex project'
        return result
    return {'main':main,'source':source,'state':state,'env':env,'event':event,'run':run,'target':target}

def test_pretool_audit_does_not_write_the_canonical_shared_checkout(lane):
    result=lane['run'](lane['event']('PreToolUse'))
    assert result.returncode==0,(result.stdout,result.stderr)
    assert result.stdout.strip()==''
    audit=lane['source']/'reports/hooks-audit.jsonl'
    assert audit.is_file()
    assert json.loads(audit.read_text(encoding='utf-8-sig').splitlines()[-1])['verdict']=='pass'
    assert not (lane['main']/'reports').exists()

def test_posttool_heartbeat_and_mode_are_bound_to_candidate_checkout(lane):
    target=lane['source']/'docs/synthetic.md';target.parent.mkdir();target.write_text('synthetic only\n',encoding='utf8')
    result=lane['run'](lane['event']('PostToolUse','*** Add File: docs/synthetic.md\n+synthetic only'))
    assert result.returncode==0,(result.stdout,result.stderr)
    heartbeat=lane['source']/'reports/hooks-heartbeat.json'
    assert heartbeat.is_file()
    record=json.loads(heartbeat.read_text(encoding='utf8'))
    assert record['runs']['total']>=1
    assert not any(term in record.get('note','') for term in ('不存在','缺失','回落'))
    assert not (lane['main']/'reports').exists()

def test_posttool_violation_audit_stays_in_candidate_checkout(lane):
    target=lane['source']/'docs/synthetic.md';target.parent.mkdir();target.write_text('bad \ufffd marker\n',encoding='utf8')
    result=lane['run'](lane['event']('PostToolUse','*** Add File: docs/synthetic.md\n+bad \ufffd marker'))
    assert result.returncode==0,(result.stdout,result.stderr)  # Frozen warn mode is unchanged.
    logs=list((lane['source']/'reports/codex-hooks').glob('audit-blocks-*.log'))
    assert len(logs)==1
    assert 'warn' in logs[0].read_text(encoding='utf-8-sig')
    assert not (lane['main']/'reports').exists()

def test_shared_lock_is_still_required_and_read_from_canonical_main(lane):
    patch='*** Update File: '+str(lane['target'])+'\n@@\n+x'
    value=lane['event']('PreToolUse',patch)
    denied=lane['run'](value)
    assert denied.returncode==0,(denied.stdout,denied.stderr)
    assert json.loads(denied.stdout)['hookSpecificOutput']['permissionDecision']=='deny'
    lock=Path(str(lane['target'])+'.editlock')
    lock.write_text(json.dumps({'held_since':datetime.now(timezone.utc).isoformat(),'who':'synthetic owner'}),encoding='utf8')
    before=lock.read_bytes()
    allowed=lane['run'](value)
    assert allowed.returncode==0 and allowed.stdout.strip()=='',(allowed.stdout,allowed.stderr)
    assert lock.read_bytes()==before

def test_direct_guard_without_adapter_override_preserves_original_fixture_routing(lane):
    script=lane['source']/'0-学习与工具/codex-handoff/guards/hooks-pretooluse-queue-read-guard.ps1'
    env=dict(lane['env']);env.pop('ZHUOPIN_SENTINEL_AUDIT_ROOT',None)
    value={'cwd':str(lane['source']),'tool_name':'Bash','tool_input':{'command':'Get-Date'},'session_id':'synthetic-direct'}
    result=subprocess.run(['pwsh','-NoProfile','-File',str(script)],cwd=lane['source'],env=env,
        input=json.dumps(value),text=True,capture_output=True,encoding='utf8')
    assert result.returncode==0,(result.stdout,result.stderr)
    assert (lane['main']/'reports/hooks-audit.jsonl').is_file()


@pytest.mark.parametrize('shared_gender,expected', [('女','pass'),('男','violation')])
def test_posttool_roster_still_comes_from_shared_main(lane, shared_gender, expected):
    relative = '6-人才与组织/人员名录-称谓与性别-正本.md'
    for checkout,gender in ((lane['main'],shared_gender),(lane['source'],'男' if shared_gender=='女' else '女')):
        roster=checkout/relative;roster.parent.mkdir(parents=True,exist_ok=True)
        roster.write_text('测试甲（'+gender+'，完全合成名录）\n',encoding='utf8')
    relative_letter='6-人才与组织/部门AI专员跟进/synthetic.md'
    target=lane['source']/relative_letter;target.parent.mkdir(parents=True)
    target.write_text('测试甲，她只是合成夹具。\n',encoding='utf8')
    result=lane['run'](lane['event']('PostToolUse','*** Add File: '+relative_letter+'\n+测试甲，她只是合成夹具。'))
    assert result.returncode==0,(result.stdout,result.stderr)
    record=json.loads((lane['source']/'reports/hooks-heartbeat.json').read_text(encoding='utf8'))
    assert record['sentinel']=='H4-代词哨兵'
    assert record['verdict']==expected
    assert not (lane['main']/'reports').exists()
