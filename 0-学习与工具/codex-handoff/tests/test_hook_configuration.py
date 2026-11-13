import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import pytest

BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('candidate_config',BASE/'hook_configuration.py')
config=importlib.util.module_from_spec(spec);spec.loader.exec_module(config)


@pytest.fixture
def machine(tmp_path):
    repo=tmp_path/'中文 仓库';home=tmp_path/'user home'
    for folder in (repo/'.claude',repo/'.codex',home/'.claude/hooks',home/'.codex',repo/'0-学习与工具/codex-handoff'):
        folder.mkdir(parents=True,exist_ok=True)
    protected={'PreToolUse':[{'matcher':'Edit','hooks':[{'type':'command','command':'pwsh -File pretooluse-guard.ps1'}]},
                             {'matcher':'old-mail','hooks':[{'type':'command','command':'pwsh -File outlook-draft-guard.ps1'}]}]}
    for path in (repo/'.claude/settings.json',repo/'.codex/hooks.json',home/'.claude/settings.json',home/'.codex/hooks.json'):
        path.write_bytes(b'\xef\xbb\xbf'+json.dumps({'hooks':protected,'env':{'TEST_SECRET':'NEVER_BACKUP_THIS'}},ensure_ascii=False,indent=2).replace('\n','\r\n').encode())
    shutil.copyfile(BASE/'hook_policy.ps1',repo/'0-学习与工具/codex-handoff/hook_policy.ps1')
    for source in config.binding_paths(repo,home):
        if source==repo/'0-学习与工具/codex-handoff/hook_policy.ps1':continue
        source.parent.mkdir(parents=True,exist_ok=True)
        source.write_text('synthetic binding',encoding='utf8')
    for name in ('pretooluse-guard.ps1','outlook-draft-guard.ps1'):
        (home/'.claude/hooks'/name).write_text('[Console]::In.ReadToEnd() | Write-Output; exit 17',encoding='utf8')
    guards=repo/'0-学习与工具/codex-handoff/guards'
    for name in ('protected-native.ps1','mail-native.ps1'):
        (guards/name).write_text('[Console]::In.ReadToEnd() | Write-Output; exit 17',encoding='utf8')
    (guards/'protected-paths.json').write_text(json.dumps({'mode':'block','patterns':['*/.claude/settings.json','*/.codex/*','*/.agents/*']}),encoding='utf8')
    return repo,home


def test_candidate_contains_only_hooks_not_credentials(machine,tmp_path):
    package=config.build(*machine)
    assert 'NEVER_BACKUP_THIS' not in json.dumps(package)
    assert package['trust_required'] is True
    before={e['path']:Path(e['path']).read_bytes() for e in package['entries']}
    state=tmp_path/'state.json'
    assert config.install(package,state)['changed'] is True
    assert config.install(package,state)['changed'] is False
    config.rollback(package,state)
    assert all(Path(p).read_bytes()==raw for p,raw in before.items())


def test_failure_rolls_back_only_owned_changes(machine,tmp_path):
    package=config.build(*machine);before={e['path']:Path(e['path']).read_bytes() for e in package['entries']}
    calls=[]
    def fail_second(path,data):
        calls.append(path)
        if len(calls)==2: raise PermissionError('synthetic occupied file')
        config.io.atomic(path,data)
    with pytest.raises(PermissionError):config.install(package,tmp_path/'state.json',fail_second)
    assert all(Path(p).read_bytes()==raw for p,raw in before.items())


def test_recovery_preserves_author_edit(machine,tmp_path):
    package=config.build(*machine);state=tmp_path/'state.json'
    config.install(package,state)
    path=Path(package['entries'][0]['path']);path.write_bytes(path.read_bytes()+b' ')
    author=path.read_bytes()
    with pytest.raises(ValueError,match='author edits preserved'):config.rollback(package,state)
    assert path.read_bytes()==author
    assert json.loads(state.read_bytes())['status']=='conflict'


def test_author_edit_between_files_is_not_overwritten(machine,tmp_path):
    package=config.build(*machine);victim=Path(package['entries'][1]['path']);author=victim.read_bytes()+b' '
    def edit_after_first(path,data):
        config.io.atomic(path,data);victim.write_bytes(author)
    with pytest.raises(ValueError,match='author edits preserved'):
        config.install(package,tmp_path/'state.json',edit_after_first)
    assert victim.read_bytes()==author


def test_other_repo_identity_conflict(machine,tmp_path):
    package=config.build(*machine)
    package['entries'][0]['path']=str(tmp_path/'other-repo/.claude/settings.json')
    with pytest.raises(ValueError,match='ownership'):config.install(package,tmp_path/'state.json')


def test_duplicate_keys_not_silently_rebound():
    with pytest.raises(ValueError,match='duplicate'):config.hooks_span(b'{"hooks":{},"hooks":{}}')


def test_failed_or_stale_full_evidence_cannot_activate(machine,tmp_path):
    repo,home=machine;report=tmp_path/'result.json'
    report.write_text(json.dumps({'full_verified':False,'exit':2}))
    with pytest.raises(ValueError,match='not passed'):config.verify_release(report,repo)
    paths=config.binding_paths(repo,home)
    (tmp_path/'candidate-after.json').write_text(json.dumps({str(p):config.sha(p.read_bytes()) for p in paths}))
    report.write_text(json.dumps({'full_verified':True,'exit':0,'source_drift':[],'projects':[{'project':'tools','exit':0},{'project':'handoff','exit':0}]}))
    assert config.verify_release(report,repo)==str(report)
    paths[0].write_bytes(b'changed after full test')
    with pytest.raises(ValueError,match='candidate changed'):config.verify_release(report,repo)


@pytest.mark.skipif(os.name!='nt',reason='Windows file sharing semantics')
def test_real_windows_occupied_file_retains_recovery_and_other_originals(machine,tmp_path):
    import ctypes
    package=config.build(*machine);state=tmp_path/'state.json'
    first=Path(package['entries'][0]['path']);before=first.read_bytes()
    victim=Path(package['entries'][1]['path']);handles=[]
    create=ctypes.windll.kernel32.CreateFileW
    create.argtypes=[ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p]
    create.restype=ctypes.c_void_p
    close=ctypes.windll.kernel32.CloseHandle;close.argtypes=[ctypes.c_void_p]
    def occupy_after_first(path,data):
        config.io.atomic(path,data)
        handle=create(str(victim),0x80000000,0,None,3,0x80,None)
        if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError()
        handles.append(handle)
    try:
        with pytest.raises(ValueError,match='file unavailable'):config.install(package,state,occupy_after_first)
        assert first.read_bytes()==before
        assert json.loads(state.read_bytes())['status']=='conflict'
    finally:
        for handle in handles:close(handle)
    config.rollback(package,state)
    assert json.loads(state.read_bytes())['status']=='rolled_back'


@pytest.mark.parametrize('tool,data,expected',[
    ('Read',{'file_path':'.claude/settings.json'},0),
    ('exec_command',{'cmd':'Get-Content -LiteralPath ".claude/settings.json"'},0),
    ('exec_command',{'cmd':'Set-Content -LiteralPath ".claude/settings.json" -Value x'},2),
    ('exec_command',{'cmd':'Get-Content "doc.md" > ".claude/settings.json"'},2),
])
def test_scoped_guard_distinguishes_read_from_write(machine,tool,data,expected):
    repo,home=machine
    (home/'.claude/protected-paths.json').write_text(json.dumps({'mode':'block','patterns':['*/.claude/settings.json']}))
    event={'cwd':str(repo),'tool_name':tool,'tool_input':data}
    result=subprocess.run(['pwsh','-NoProfile','-File',str(repo/'0-学习与工具/codex-handoff/hook_policy.ps1'),'-Kind','Protected','-RepoRoot',str(repo),'-LegacyGuard',str(home/'.claude/hooks/pretooluse-guard.ps1')],input=json.dumps(event),capture_output=True,text=True,encoding='utf8',env=dict(os.environ,USERPROFILE=str(home)),timeout=20)
    assert result.returncode==expected,result.stderr


def test_other_project_receives_unchanged_payload_through_native_guard(machine,tmp_path):
    repo,home=machine;event={'cwd':str(tmp_path),'tool_name':'Read','tool_input':{'file_path':'other'}}
    result=subprocess.run(['pwsh','-NoProfile','-File',str(repo/'0-学习与工具/codex-handoff/hook_policy.ps1'),'-Kind','Protected','-RepoRoot',str(repo),'-LegacyGuard',str(home/'.claude/hooks/pretooluse-guard.ps1')],input=json.dumps(event),capture_output=True,text=True,encoding='utf8',timeout=20)
    assert result.returncode==17
    assert json.loads(result.stdout)==event


def test_native_mail_is_denied_without_sending_anything(machine):
    repo,home=machine
    event={'cwd':str(repo),'tool_name':'mcp__codex_apps__microsoft_outlook_email_send_email','tool_input':{'synthetic':True}}
    result=subprocess.run(['pwsh','-NoProfile','-File',str(repo/'0-学习与工具/codex-handoff/hook_policy.ps1'),'-Kind','Mail','-RepoRoot',str(repo),'-LegacyGuard',str(home/'.claude/hooks/outlook-draft-guard.ps1')],input=json.dumps(event),capture_output=True,text=True,encoding='utf8',timeout=20)
    assert result.returncode==0
    assert json.loads(result.stdout)['hookSpecificOutput']['permissionDecision']=='deny'
