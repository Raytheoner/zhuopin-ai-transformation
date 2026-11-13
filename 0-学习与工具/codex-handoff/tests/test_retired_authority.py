"""Behavioral contracts for retired authority: legacy canaries must never run."""
import importlib.util
import json
import subprocess
from pathlib import Path
import pytest

BASE=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location('retirement_'+name,BASE/(name+'.py'))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod
provider=load('model_provider')
config=load('hook_configuration')

@pytest.mark.parametrize('model',['claude-opus-4-6','anthropic/claude-sonnet-4','sonnet','opus-4','haiku-latest'])
def test_retired_models_cannot_be_reactivated(model,tmp_path):
    with pytest.raises(ValueError,match='Legacy model'):
        provider.command('codex',tmp_path,tmp_path/'final','read-only',model=model)

@pytest.mark.parametrize('exe',['claude','claude.exe','C:/old/claude.cmd','anthropic-cli.exe'])
def test_retired_executable_override_is_rejected(exe,tmp_path,monkeypatch):
    monkeypatch.setenv('ZHUOPIN_CODEX_EXECUTABLE',exe)
    with pytest.raises(ValueError,match='Retired Claude'):
        provider.resolve_executable(tmp_path)

def test_explicit_native_executable_is_retained(tmp_path,monkeypatch):
    exe='C:/native/codex.exe'
    monkeypatch.setenv('ZHUOPIN_CODEX_EXECUTABLE',exe)
    assert provider.resolve_executable(tmp_path)==exe

def test_missing_native_config_does_not_consume_old_config(tmp_path):
    repo=tmp_path/'repo';home=tmp_path/'home'
    for root in (repo,home):
        (root/'.claude').mkdir(parents=True)
        (root/'.claude/settings.json').write_text('{"hooks":{}}',encoding='utf8')
    with pytest.raises(FileNotFoundError,match='hooks.json'):
        config.build(repo,home)
    assert all('.claude' not in str(p) for p in config.binding_paths(repo,home))

def test_missing_native_guard_does_not_execute_legacy_canary(tmp_path):
    folder=tmp_path/'adapter';folder.mkdir()
    (folder/'hook_policy.ps1').write_bytes((BASE/'hook_policy.ps1').read_bytes())
    marker=tmp_path/'legacy-ran'
    canary=tmp_path/'old.ps1'
    canary.write_text("Set-Content -LiteralPath '"+str(marker)+"' -Value invoked; exit 0",encoding='utf8')
    event={'cwd':str(tmp_path),'tool_name':'Write','tool_input':{'file_path':str(tmp_path/'plain.txt')}}
    run=subprocess.run(['pwsh','-NoProfile','-File',str(folder/'hook_policy.ps1'),'-Kind','Protected',
        '-RepoRoot',str(tmp_path),'-LegacyGuard',str(canary)],input=json.dumps(event),
        capture_output=True,text=True,encoding='utf8',cwd=tmp_path,timeout=20)
    assert run.returncode==2
    assert not marker.exists()
