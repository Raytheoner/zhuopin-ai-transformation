"""E: native location, preserved old tree, branch rejection and real detached output."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import subprocess
import time
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('_E_original_batch', Path(__file__).with_name('test_工具-opener批处理执行v2.py'))
original = importlib.util.module_from_spec(spec); spec.loader.exec_module(original)

def execute(root, shell, detached=False):
    script = root / '0-学习与工具/工具-opener批处理执行v2.ps1'
    argv = [shell, '-NoProfile', '-File', str(script), '-Plan', str(root / 'plan.md'),
            '-LogDir', str(root / 'reports/batch'), '-Yes', '-StaggerSec', '0', '-ContextPollSec', '1', '-ConsumerEnabled']
    if detached: argv.append('-Detach')
    return subprocess.run(argv, cwd=root, capture_output=True, text=True, encoding='utf8', errors='replace')

def test_native_tree_and_old_marker_preserved(tmp_path):
    original.TestBatchCodex().setup(tmp_path)
    marker = tmp_path / '.claude/worktrees/keep/old.txt'; marker.parent.mkdir(parents=True); marker.write_text('keep original')
    result = execute(tmp_path, shutil.which('pwsh'))
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / '.worktrees/fixture/made.txt').read_text() == 'fixture'
    assert marker.read_text() == 'keep original'
    assert not (tmp_path / '.claude/worktrees/fixture').exists()

def test_old_branch_rejected_before_provider(tmp_path):
    original.TestBatchCodex().setup(tmp_path)
    plan = tmp_path / 'plan.md'; text = plan.read_text(encoding='utf8')
    assert text.count('codex/fixture') == 1
    plan.write_text(text.replace('codex/fixture', 'claude/fixture'), encoding='utf8')
    result = execute(tmp_path, shutil.which('pwsh'))
    assert result.returncode != 0
    assert not list((tmp_path / 'reports/batch').rglob('result.json'))
    assert not (tmp_path / '.worktrees/fixture').exists()

@pytest.mark.parametrize('parent_shell', ['ps7', 'ps5'])
def test_detach_normal_policy_and_complete_output(tmp_path, parent_shell):
    source = ROOT / '0-学习与工具/工具-opener批处理执行v2.ps1'
    assert "'-ExecutionPolicy'" not in source.read_text(encoding='utf-8-sig'), 'Detach must not request an execution-policy bypass'
    root = tmp_path / 'space fixture'; root.mkdir()
    original.TestBatchCodex().setup(root)
    shell = shutil.which('pwsh') if parent_shell == 'ps7' else str(Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe')
    result = execute(root, shell, detached=True)
    assert result.returncode == 0, result.stdout + result.stderr
    done = root / 'reports/batch/exit.txt'
    deadline = time.monotonic() + 45
    while not done.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    assert done.exists(), 'Detached worker must produce its own exit evidence'
    assert done.read_text(encoding='utf-8-sig').strip() == '0'
    assert (root / '.worktrees/fixture/made.txt').read_text() == 'fixture'
    assert (root / 'reports/batch/launcher-stdout.log').stat().st_size > 0
    rows = json.loads((root / 'reports/batch/summary.json').read_text(encoding='utf-8-sig'))
    assert len(rows) == 1 and rows[0]['DeliveryAccepted'] is False
