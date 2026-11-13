"""No real model or process: verify explicit policy at each launch boundary."""
from pathlib import Path
import importlib.util
import io
import json
import sys
import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'model_provider.py'
LUNA = 'gpt-6-luna'
THREAD = '01234567-89ab-cdef-0123-456789abcdef'

@pytest.fixture
def provider():
    spec = importlib.util.spec_from_file_location('luna_entry_provider', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def explicit_luna(argv):
    assert argv.count('-m') == 1
    assert argv[argv.index('-m') + 1] == LUNA

@pytest.mark.parametrize('thread', [None, THREAD])
@pytest.mark.parametrize('model', [None, LUNA])
def test_new_and_resume_commands_always_bind_luna(provider, tmp_path, thread, model):
    argv = provider.command('codex.exe', tmp_path, tmp_path/'final.txt', 'read-only', thread=thread, model=model)
    explicit_luna(argv)
    assert ('resume' in argv) is bool(thread)

@pytest.mark.parametrize('model', ['inherit', '', 'routine', 'design', 'gpt-6-astra', 'gpt-6.1-sol', 'haiku', 'sonnet', 'opus', '-m'])
def test_command_refuses_unresolved_or_non_luna_selection(provider, tmp_path, model):
    with pytest.raises(ValueError):
        provider.command('codex.exe', tmp_path, tmp_path/'final.txt', 'read-only', model=model)

class FinishedFixture:
    pid = 12345
    returncode = 0
    def communicate(self, *args, **kwargs):
        return None, None
    def poll(self):
        return 0

def fake_run(provider, tmp_path, model=None):
    calls = []
    def popen(argv, **kwargs):
        calls.append(argv)
        return FinishedFixture()
    result = provider.run(workspace=tmp_path, evidence=tmp_path/'evidence', prompt='synthetic policy check',
                          enabled=True, model=model, executable='codex.exe', popen=popen)
    return calls, result

def test_run_default_has_explicit_command_and_honest_request(provider, tmp_path):
    calls, result = fake_run(provider, tmp_path)
    assert len(calls) == 1
    explicit_luna(calls[0])
    request = json.loads((tmp_path/'evidence/request.json').read_text(encoding='utf8'))
    assert request['requested_model'] == LUNA
    assert request['argv'] == calls[0]
    assert result['actual_model'] is None
    assert result['accepted'] is False

@pytest.mark.parametrize('model', ['inherit', '', 'gpt-6-astra', 'gpt-6.1-sol', 'sonnet'])
def test_run_refuses_other_selection_before_start(provider, tmp_path, model):
    calls, result = fake_run(provider, tmp_path, model)
    assert calls == []
    assert result['status'] == 'start_failed'
    assert result['actual_model'] is None
    assert result['accepted'] is False
    assert not (tmp_path/'evidence/process.json').exists()

@pytest.mark.parametrize('route', ['routine', 'design'])
@pytest.mark.parametrize('effective', [None, 'gpt-6-astra', LUNA])
def test_configured_route_still_requires_luna(provider, tmp_path, route, effective):
    config = tmp_path/'.codex'
    config.mkdir()
    (config/'model-policy.json').write_text(json.dumps({'routes': {route: effective}}), encoding='utf8')
    calls, result = fake_run(provider, tmp_path, route)
    if effective == LUNA:
        assert len(calls) == 1
        explicit_luna(calls[0])
    else:
        assert calls == []
        assert result['status'] == 'start_failed'
    assert result['actual_model'] is None
    assert result['accepted'] is False

def test_cli_default_is_explicit_luna(provider, tmp_path, monkeypatch, capsys):
    calls = []
    def run(**kwargs):
        calls.append(kwargs)
        return {'status': 'paused'}
    monkeypatch.setattr(provider, 'run', run)
    monkeypatch.setattr(sys, 'argv', ['model_provider.py', '--workspace', str(tmp_path), '--evidence', str(tmp_path/'e')])
    monkeypatch.setattr(sys, 'stdin', io.StringIO('synthetic'))
    assert provider.main() == 1
    assert calls[0]['model'] == LUNA
    assert calls[0]['enabled'] is False
