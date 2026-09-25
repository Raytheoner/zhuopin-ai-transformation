"""Exercise the real PowerShell launcher without any model process."""
import json, os, shutil, subprocess, sys
from pathlib import Path
import pytest

@pytest.mark.parametrize('failure',['missing-runtime','invalid-runtime','missing-python','bridge-exit'])
def test_hook_launcher_failure_returns_native_deny(tmp_path,failure):
    source=Path(__file__).resolve().parents[1]/'invoke.ps1'
    folder=tmp_path/'0-tools'/'handoff'; folder.mkdir(parents=True)
    shutil.copyfile(source,folder/'invoke.ps1')
    config=tmp_path/'runtime.json'
    if failure=='invalid-runtime': config.write_text('{',encoding='utf8')
    elif failure!='missing-runtime':
        config.write_text(json.dumps({'python':str(tmp_path/'absent.exe') if failure=='missing-python' else sys.executable,'state_root':str(tmp_path/'state')}),encoding='utf8')
    (folder/'hook_bridge.py').write_text('raise SystemExit(2)\n',encoding='utf8')
    env=dict(os.environ,ZHUOPIN_CODEX_RUNTIME=str(config))
    result=subprocess.run(['pwsh','-NoProfile','-File',str(folder/'invoke.ps1'),'-Mode','Hook'],input='{}',text=True,capture_output=True,encoding='utf8',env=env,timeout=30)
    assert result.returncode==0,(result.stdout,result.stderr)
    decision=json.loads(result.stdout)['hookSpecificOutput']
    assert decision['hookEventName']=='PreToolUse' and decision['permissionDecision']=='deny'

def test_non_hook_launcher_failure_remains_nonzero(tmp_path):
    config=tmp_path/'invalid.json';config.write_text('{',encoding='utf8')
    env=dict(os.environ,ZHUOPIN_CODEX_RUNTIME=str(config))
    result=subprocess.run(['pwsh','-NoProfile','-File',str(Path(__file__).resolve().parents[1]/'invoke.ps1'),'-Mode','Probe'],text=True,capture_output=True,encoding='utf8',env=env,timeout=30)
    assert result.returncode!=0
    assert 'permissionDecision' not in result.stdout

def test_posttool_failure_preserves_error_feedback(tmp_path):
    folder=tmp_path/'0-tools'/'handoff';folder.mkdir(parents=True)
    shutil.copyfile(Path(__file__).resolve().parents[1]/'invoke.ps1',folder/'invoke.ps1')
    config=tmp_path/'runtime.json'
    config.write_text(json.dumps({'python':sys.executable,'state_root':str(tmp_path/'state')}),encoding='utf8')
    (folder/'hook_bridge.py').write_text('import sys\nsys.stderr.write("sentinel fixture failed")\nraise SystemExit(2)\n',encoding='utf8')
    env=dict(os.environ,ZHUOPIN_CODEX_RUNTIME=str(config))
    result=subprocess.run(['pwsh','-NoProfile','-File',str(folder/'invoke.ps1'),'-Mode','Hook'],input=json.dumps({'hook_event_name':'PostToolUse'}),text=True,capture_output=True,encoding='utf8',env=env,timeout=30)
    assert result.returncode==2
    assert 'sentinel fixture failed' in result.stderr
    assert 'permissionDecision' not in result.stdout

def test_hook_launcher_preserves_utf8_input(tmp_path):
    folder=tmp_path/'0-tools'/'handoff';folder.mkdir(parents=True)
    shutil.copyfile(Path(__file__).resolve().parents[1]/'invoke.ps1',folder/'invoke.ps1')
    config=tmp_path/'runtime.json'
    config.write_text(json.dumps({'python':sys.executable,'state_root':str(tmp_path/'state')}),encoding='utf8')
    (folder/'hook_bridge.py').write_text('import sys,json\nprint(json.dumps(json.load(sys.stdin),ensure_ascii=False))\n',encoding='utf8')
    event={'hook_event_name':'PreToolUse','tool_input':{'command':'*** Add File: 含 空格/中文.md\n+原样正文 → 验收'}}
    env=dict(os.environ,ZHUOPIN_CODEX_RUNTIME=str(config))
    result=subprocess.run(['pwsh','-NoProfile','-File',str(folder/'invoke.ps1'),'-Mode','Hook'],input=json.dumps(event,ensure_ascii=False),text=True,capture_output=True,encoding='utf8',env=env,timeout=30)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)==event

def test_portable_hook_wrapper_preserves_child_exit(tmp_path):
    config=json.loads((Path(__file__).resolve().parents[3]/'.codex/hooks.json').read_text(encoding='utf8'))
    command=config['hooks']['PostToolUse'][0]['hooks'][0]['command']
    inner=command.split(' -Command "',1)[1][:-1]
    (tmp_path/'.git').mkdir()
    folder=tmp_path/'0-学习与工具/codex-handoff';folder.mkdir(parents=True)
    (folder/'invoke.ps1').write_text('[Console]::Error.WriteLine("fixture sentinel failed"); exit 2\n',encoding='utf8')
    result=subprocess.run(['pwsh','-NoProfile','-Command',inner],cwd=tmp_path,text=True,capture_output=True,encoding='utf8',timeout=30)
    assert result.returncode==2
    assert 'fixture sentinel failed' in result.stderr
