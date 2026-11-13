"""A native hook must have its complete guard closure before activation/use."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

BASE = Path(__file__).resolve().parents[1]
NAMES = (
    'hooks-common.ps1', 'hooks-pretooluse-dedup-guard.ps1',
    'hooks-pretooluse-editlock-guard.ps1', 'hooks-pretooluse-queue-read-guard.ps1',
    'mail-native.ps1', 'protected-native.ps1', 'protected-paths.json',
    'sentinel-mojibake.ps1', 'sentinel-pronoun.ps1', 'sentinels-mode.json',
)

def load(name):
    spec = importlib.util.spec_from_file_location('readiness_' + name, BASE/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

@pytest.fixture
def configuration():
    return load('hook_configuration')

def bundle(repo):
    folder = repo/'0-学习与工具/codex-handoff/guards'
    folder.mkdir(parents=True)
    expected = {}
    for name in NAMES:
        raw = ('synthetic guard dependency: '+name+'\n').encode()
        (folder/name).write_bytes(raw)
        expected[name] = hashlib.sha256(raw).hexdigest()
    return folder, expected

def test_complete_bundle_returns_all_bound_hashes(configuration, tmp_path):
    folder, expected = bundle(tmp_path)
    assert configuration.verify_native_guard_bundle(tmp_path, expected) == expected

@pytest.mark.parametrize('missing', NAMES)
def test_each_missing_dependency_is_fail_closed(configuration, tmp_path, missing):
    folder, expected = bundle(tmp_path)
    (folder/missing).unlink()
    with pytest.raises(ValueError, match='incomplete.*'+missing.replace('.', r'\.')):
        configuration.verify_native_guard_bundle(tmp_path, expected)

def test_unknown_guard_bytes_cannot_satisfy_approved_binding(configuration, tmp_path):
    folder, expected = bundle(tmp_path)
    victim = folder/'hooks-common.ps1'
    victim.write_bytes(b'unknown author content')
    before = victim.read_bytes()
    with pytest.raises(ValueError, match='changed.*hooks-common'):
        configuration.verify_native_guard_bundle(tmp_path, expected)
    assert victim.read_bytes() == before

@pytest.mark.parametrize('change', ['missing', 'extra'])
def test_partial_or_extended_expected_closure_is_rejected(configuration, tmp_path, change):
    folder, expected = bundle(tmp_path)
    if change == 'missing':
        expected.pop('sentinels-mode.json')
    else:
        expected['unapproved.ps1'] = '0'*64
    with pytest.raises(ValueError, match='closure'):
        configuration.verify_native_guard_bundle(tmp_path, expected)

def test_source_bindings_include_sentinel_mode(configuration, tmp_path):
    names = {path.name for path in configuration.binding_paths(tmp_path, tmp_path/'home')}
    assert set(NAMES) <= names

def test_incomplete_bundle_is_reported_before_configuration_access(configuration, tmp_path):
    repo = tmp_path/'repo'
    repo.mkdir()
    config = repo/'.codex/hooks.json'
    config.parent.mkdir()
    config.write_bytes(b'configuration must not be parsed before guards are ready')
    before = config.read_bytes()
    with pytest.raises(ValueError, match='native guard bundle incomplete'):
        configuration.build(repo, tmp_path/'home')
    assert {p: p.read_bytes() for p in repo.rglob('*') if p.is_file()} == {config: before}

def test_mode_change_after_review_cannot_activate_hooks(configuration, tmp_path):
    repo, home = tmp_path/'repo', tmp_path/'home'
    folder, expected = bundle(repo)
    for source in configuration.binding_paths(repo, home):
        source.parent.mkdir(parents=True, exist_ok=True)
        if not source.exists():
            source.write_bytes(b'synthetic source binding')
    for path in (repo/'.codex/hooks.json', home/'.codex/hooks.json'):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'hooks': {}, 'env': {'SYNTHETIC_SECRET': 'not copied'}}))
    package = configuration.build(repo, home)
    originals = {row['path']: Path(row['path']).read_bytes() for row in package['entries']}
    (folder/'sentinels-mode.json').write_bytes(b'changed after review')
    with pytest.raises(ValueError, match='guard source changed'):
        configuration.install(package, tmp_path/'install-state.json')
    assert all(Path(path).read_bytes() == raw for path, raw in originals.items())
    assert not (tmp_path/'install-state.json').exists()

def test_runtime_missing_bundle_denies_before_starting_a_guard(tmp_path, monkeypatch, capsys):
    bridge = load('hook_bridge')
    monkeypatch.setattr(bridge, 'ROOT', tmp_path)
    monkeypatch.setattr(bridge, 'HOOKS', tmp_path/'0-学习与工具/codex-handoff/guards')
    event = {'hook_event_name': 'PreToolUse', 'tool_name': 'exec_command',
             'cwd': str(tmp_path), 'tool_input': {'cmd': 'Get-Date'}}
    monkeypatch.setattr(bridge.sys, 'stdin', SimpleNamespace(buffer=io.BytesIO(json.dumps(event).encode())))
    monkeypatch.setattr(bridge, 'audit', lambda *args, **kwargs: None)
    def forbidden(*args, **kwargs):
        pytest.fail('incomplete guard bundle must be rejected before process startup')
    monkeypatch.setattr(bridge.subprocess, 'run', forbidden)
    assert bridge.main() == 0
    response = json.loads(capsys.readouterr().out)['hookSpecificOutput']
    assert response['permissionDecision'] == 'deny'
    assert 'native guard bundle incomplete' in response['permissionDecisionReason']
    assert 'hooks-common.ps1' in response['permissionDecisionReason']
