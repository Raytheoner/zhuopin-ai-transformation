"""Explicit child effort and request evidence; no actual CLI/model invocation."""
import importlib.util
import json
from pathlib import Path
import tomllib

import pytest


SOURCE = Path(__file__).resolve().parents[1] / 'model_provider.py'
THREAD = '01234567-89ab-cdef-0123-456789abcdef'


def provider():
    spec = importlib.util.spec_from_file_location('effort_contract_provider', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def config_values(argv):
    result = []
    for index, value in enumerate(argv[:-1]):
        if value in ('-c', '--config'):
            result.append(tomllib.loads(argv[index + 1]))
    return result


@pytest.mark.parametrize('thread', [None, THREAD], ids=['new', 'resume'])
@pytest.mark.parametrize('default', [None, 'low', 'high', 'xhigh'], ids=['missing', 'low', 'high', 'xhigh'])
def test_new_and_resume_bind_luna_high_above_workspace_defaults(tmp_path, thread, default):
    workspace = tmp_path / 'checkout with spaces'
    (workspace / '.codex').mkdir(parents=True)
    (workspace / '.codex/config.toml').write_text(
        '' if default is None else f'model_reasoning_effort = "{default}"\n', encoding='utf8')
    argv = provider().command('codex.exe', workspace, workspace / 'final.txt', 'read-only', thread=thread)
    assert argv[:5] == ['codex.exe', '-a', 'never', '-s', 'read-only']
    assert argv[argv.index('-m') + 1] == 'gpt-6-luna'
    effort = [value['model_reasoning_effort'] for value in config_values(argv) if 'model_reasoning_effort' in value]
    assert effort == ['high'], 'Each child invocation must bind high explicitly, including resume'
    assert ('resume' in argv) is (thread is not None)
    assert argv[-1] == '-'


@pytest.mark.parametrize('thread', [None, THREAD], ids=['new', 'resume'])
def test_run_passes_explicit_effort_and_records_requested_not_actual(tmp_path, monkeypatch, thread):
    module = provider()
    monkeypatch.setenv('CODEX_HOME', str(tmp_path / 'empty native home'))
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    evidence = tmp_path / 'evidence'
    observed = []

    class CompletedFixture:
        pid = 424242
        returncode = None

        def __init__(self, argv, **kwargs):
            observed.append(list(argv))
            self.output = kwargs['stdout']

        def communicate(self, value, timeout=None):
            self.output.write(json.dumps({'type': 'thread.started', 'thread_id': THREAD}) + '\n')
            self.output.write(json.dumps({'type': 'turn.completed'}) + '\n')
            self.output.flush()
            self.returncode = 0
            return None, None

        def poll(self):
            return self.returncode

    result = module.run(workspace=workspace, evidence=evidence, prompt='synthetic', enabled=True,
                        executable='codex.exe', popen=CompletedFixture, thread=thread, timeout=10)
    assert result['status'] == 'output_needs_review'
    assert len(observed) == 1
    request = json.loads((evidence / 'request.json').read_text(encoding='utf8'))
    assert request['argv'] == observed[0]
    assert {'model_reasoning_effort': 'high'} in config_values(observed[0])
    assert request['requested_model'] == result['requested_model'] == 'gpt-6-luna'
    assert request['requested_reasoning_effort'] == result['requested_reasoning_effort'] == 'high'
    assert result['actual_model'] is None
    assert result.get('actual_reasoning_effort') is None
    assert result['accepted'] is False


@pytest.mark.parametrize('model', ['inherit', '', 'gpt-6-astra', 'sonnet'])
def test_effort_binding_preserves_rejection_of_other_model_routes(tmp_path, model):
    with pytest.raises(ValueError):
        provider().command('codex.exe', tmp_path, tmp_path / 'final.txt', 'read-only', model=model)
