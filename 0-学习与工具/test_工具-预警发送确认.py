"""A callback result is not delivery evidence; only a bound platform ACK is."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

@pytest.fixture
def delivery(tmp_path, monkeypatch):
    path = Path(__file__).with_name('工具-落库sweep.py')
    spec = importlib.util.spec_from_file_location('strict_delivery_sweep', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, '_load_webhook_url', lambda _: 'https://example.invalid/fixture')
    return module, tmp_path

def notify(module, root):
    log = []
    module._track_and_alert_standing_state(root, 'fixture', 'reports/state.json', {'one'}, 24,
        lambda _: 'synthetic candidate', lambda _: 'resolved', log)
    return log

@pytest.mark.parametrize('callback_result', [None, True, False, 'ok', {}])
def test_unverified_callback_cannot_commit_success_or_replay(delivery, monkeypatch, callback_result):
    module, root = delivery
    calls = []
    def callback(*args):
        calls.append(args)
        return callback_result
    monkeypatch.setattr(module, '_send_wecom_markdown', callback)
    log = notify(module, root)
    assert not (root/'reports/state.json').exists(), 'unverified callback was recorded as delivered'
    progress = json.loads((root/'reports/state.delivery.json').read_text(encoding='utf8'))['alert']
    assert progress['status'] == 'unknown'
    assert progress['in_flight'] == 0
    assert progress['acked'] == {}
    assert any('status=unknown' in line for line in log)
    notify(module, root)
    assert len(calls) == 1

def test_bound_platform_ack_records_success(delivery, monkeypatch):
    module, root = delivery
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return b'{"errcode":0,"req_id":"synthetic-ack"}'
    monkeypatch.setattr(module.urllib.request, 'urlopen', lambda *a, **k: Response())
    notify(module, root)
    assert set(json.loads((root/'reports/state.json').read_text(encoding='utf8'))) == {'one'}
    progress = json.loads((root/'reports/state.delivery.json').read_text(encoding='utf8'))['alert']
    assert progress['status'] == 'success'
    assert 'in_flight' not in progress
    assert progress['acked']['0']['receipt']['errcode'] == 0
