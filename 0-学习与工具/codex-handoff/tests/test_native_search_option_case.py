"""rg options are case-sensitive; no actual rg or protected source is read."""
from pathlib import Path
import json
import os
import subprocess
import pytest

BASE=Path(__file__).resolve().parents[1]
QUEUE='1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md'

@pytest.fixture
def guard_fixture(tmp_path):
    guards=tmp_path/'0-学习与工具/codex-handoff/guards'
    guards.mkdir(parents=True)
    for name in ('hooks-common.ps1','hooks-pretooluse-queue-read-guard.ps1',
        'hooks-pretooluse-dedup-guard.ps1','hooks-pretooluse-editlock-guard.ps1',
        'mail-native.ps1','protected-native.ps1','protected-paths.json','sentinel-mojibake.ps1','sentinel-pronoun.ps1'):
        (guards/name).write_bytes((BASE/'guards'/name).read_bytes())
    (guards/'sentinels-mode.json').write_bytes((BASE/'guards/sentinels-mode.json').read_bytes())
    for relative in ('docs/source.py','docs/patterns.txt',QUEUE):
        path=tmp_path/relative;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('synthetic only\n',encoding='utf8')
    env=dict(os.environ)
    for key in list(env):
        if key.startswith('ZHUOPIN_'):env.pop(key,None)
    env['ZHUOPIN_SENTINEL_REPO_ROOT']=str(tmp_path)
    subprocess.run(['git','init','-q','-b','master','--separate-git-dir',str(tmp_path/'owned-git-admin')],cwd=tmp_path,env=env,check=True,capture_output=True)
    assert not (tmp_path/'.codex/hooks.json').exists()
    return tmp_path,guards/'hooks-pretooluse-queue-read-guard.ps1',env

@pytest.mark.parametrize('command,allowed',[
    ("rg -n -F 'literal' 'docs/source.py'",True),
    ("rg --line-number --fixed-strings 'literal' 'docs/source.py'",True),
    ("rg -F '跨桌任务队列-机制环境.md' 'docs/source.py'",True),
    ("rg -n -F -- 'literal' 'docs/source.py'",True),
    ("rg -f 'docs/patterns.txt' 'docs/source.py'",True),
    ("rg -F -f 'docs/patterns.txt' 'docs/source.py'",True),
    ("rg -F 'literal' '"+QUEUE+"'",False),
    ("rg -f '"+QUEUE+"' 'docs/source.py'",False),
    ("rg -f 'docs/missing-patterns.txt' 'docs/source.py'",False),
    ("rg --FILES 'docs'",False),
])
def test_native_rg_option_case_keeps_protected_reads_denied(guard_fixture,command,allowed):
    root,script,env=guard_fixture
    payload={'cwd':str(root),'tool_name':'Bash','session_id':'synthetic-search-option',
             '_zhuopin_codex_adapter':'native-v1','tool_input':{'cwd':str(root),'command':command}}
    result=subprocess.run(['pwsh','-NoProfile','-File',str(script)],cwd=root,env=env,
        input=json.dumps(payload,ensure_ascii=False),capture_output=True,text=True,encoding='utf8',timeout=20)
    assert result.returncode==(0 if allowed else 2),(result.stdout,result.stderr)
    assert ('读侧禁通读' in result.stderr) is not allowed
