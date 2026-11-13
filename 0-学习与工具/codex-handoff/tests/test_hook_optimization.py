import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import pytest

BASE = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location('optimization_' + name, BASE/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bridge = load('hook_bridge')
store = load('hook_audit_store')


@pytest.mark.parametrize('name', ['UserPromptSubmit', 'Stop', 'PostToolUse'])
def test_empty_events_have_no_context_process_or_journal(name, monkeypatch, capsys):
    monkeypatch.setattr(bridge.sys, 'stdin', SimpleNamespace(buffer=io.BytesIO(json.dumps({'hook_event_name':name}).encode())))
    def forbidden(*a, **kw):
        raise AssertionError('empty event did work')
    monkeypatch.setattr(bridge, 'audit', forbidden)
    monkeypatch.setattr(bridge.subprocess, 'run', forbidden)
    assert bridge.main() == 0
    assert capsys.readouterr().out == ''


def test_exec_still_checks_queue_without_count_only_process(tmp_path):
    event = {'hook_event_name':'PreToolUse', 'tool_name':'exec_command', 'cwd':str(tmp_path), 'tool_input':{'cmd':'Get-Date'}}
    assert [s for s, p in bridge.effective_calls(event)] == ['hooks-pretooluse-queue-read-guard.ps1']


@pytest.mark.parametrize('path,expected', [('docs/one.md',1), ('6-人才与组织/部门AI专员跟进/合成.md',2)])
def test_post_only_starts_relevant_sentinels(tmp_path, path, expected):
    event = {'hook_event_name':'PostToolUse', 'tool_name':'apply_patch', 'cwd':str(tmp_path), 'tool_input':'*** Add File: '+path+'\n+synthetic'}
    scripts = [s for s, p in bridge.effective_calls(event)]
    assert len(scripts) == expected
    assert scripts[0] == 'sentinel-mojibake.ps1'


def test_journal_shards_and_latest_summary_keep_all_events(tmp_path):
    for n in range(20):
        store.append(tmp_path, {'session_id':'synthetic', 'number':n}, max_bytes=180)
    logs = sorted(tmp_path.glob('events-*.jsonl'))
    rows = [json.loads(line) for p in logs for line in p.read_text(encoding='utf8').splitlines()]
    assert [r['number'] for r in rows] == list(range(20))
    assert all(p.stat().st_size <= 180 for p in logs)
    summaries = list(tmp_path.glob('*.json'))
    assert len(summaries) == 1 and json.loads(summaries[0].read_text())['number'] == 19


def test_torn_journal_preserved_and_refuses_append(tmp_path):
    path = store.append(tmp_path, {'session_id':'synthetic'})
    with path.open('ab') as f: f.write(b'{broken')
    before = path.read_bytes()
    with pytest.raises(ValueError, match='incomplete'):
        store.append(tmp_path, {'session_id':'synthetic'})
    assert path.read_bytes() == before


def test_old_json_untouched(tmp_path):
    old = tmp_path/'legacy.json'; old.write_bytes(b'{"legacy":true}\r\n')
    store.append(tmp_path, {'session_id':'synthetic'})
    assert old.read_bytes() == b'{"legacy":true}\r\n'


def test_cross_process_lock_prevents_interleaved_json(tmp_path):
    code = ('import sys;sys.path.insert(0,sys.argv[1]);from hook_audit_store import append;'
            'from pathlib import Path;[(append(Path(sys.argv[2]),{"session_id":sys.argv[3],"n":n})) for n in range(15)]')
    jobs = [subprocess.Popen([sys.executable,'-c',code,str(BASE),str(tmp_path),str(n)], stdout=subprocess.PIPE,stderr=subprocess.PIPE) for n in range(3)]
    for job in jobs:
        out, err = job.communicate(timeout=30)
        assert job.returncode == 0, err
    rows = [json.loads(line) for p in tmp_path.glob('events-*.jsonl') for line in p.read_text().splitlines()]
    assert len(rows) == 45
    assert len({(r['session_id'], r['n']) for r in rows}) == 45


def test_lock_contention_preserves_lock_file(tmp_path):
    path = tmp_path/'owned.lock'
    with store.locked(path):
        with pytest.raises(TimeoutError):
            with store.locked(path, timeout=.1):
                pass
    assert path.exists()
    with store.locked(path): pass
