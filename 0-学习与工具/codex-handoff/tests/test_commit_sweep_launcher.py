"""Native scheduled launcher: private Git/runtime and synthetic sweep only."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


TOOLS = Path(__file__).resolve().parents[2]
LAUNCHER = TOOLS / 'codex-handoff/launch_commit_sweep.ps1'
VBS = TOOLS / 'run-commit-sweep-hidden.vbs'
SHELLS = ['pwsh', 'powershell.exe']


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True,
                          text=True, encoding='utf8').stdout.strip()


def sweep_source(code=0):
    return (
        'import json,sys\nfrom pathlib import Path\n'
        'root=Path(__file__).resolve().parents[1]\n'
        '(root/"synthetic-sweep-call.json").write_text(json.dumps({"script":str(Path(__file__).resolve()),"argv":sys.argv[1:]}),encoding="utf8")\n'
        f'raise SystemExit({code})\n'
    )


class Case:
    def __init__(self, root):
        self.root = root
        root.mkdir()
        git(root, 'init', '-q', '-b', 'master')
        git(root, 'config', 'user.email', 'fixture@example.invalid')
        git(root, 'config', 'user.name', 'fixture')
        git(root, 'config', 'commit.gpgsign', 'false')
        (root / 'README.md').write_text('synthetic baseline\n', encoding='utf8')
        git(root, 'add', 'README.md')
        git(root, 'commit', '-q', '-m', 'synthetic baseline')
        self.populate(root)

    def populate(self, root):
        tools = root / '0-学习与工具'
        (tools / 'codex-handoff').mkdir(parents=True, exist_ok=True)
        if LAUNCHER.is_file():
            (tools / 'codex-handoff/launch_commit_sweep.ps1').write_bytes(LAUNCHER.read_bytes())
        (tools / '工具-落库sweep.py').write_text(sweep_source(), encoding='utf8')
        self.runtime(root, {'python': sys.executable})

    def runtime(self, root, data):
        path = root / '.codex/runtime.local.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding='utf8')
        return path

    def run(self, shell, *args, root=None):
        root = root or self.root
        return subprocess.run([shell, '-NoProfile', '-NonInteractive', '-File',
                               str(root / '0-学习与工具/codex-handoff/launch_commit_sweep.ps1'), *args],
                              cwd=root, capture_output=True, text=True, encoding='utf8', errors='replace')

    def linked(self):
        linked = self.root.parent / 'linked checkout with spaces'
        git(self.root, 'worktree', 'add', '-b', 'main', str(linked), 'master')
        self.populate(linked)
        (linked / '.codex/runtime.local.json').unlink()
        return linked


@pytest.fixture(params=SHELLS)
def shell(request):
    assert shutil.which(request.param), f'Required native shell unavailable: {request.param}'
    return request.param


@pytest.fixture
def case(tmp_path):
    return Case(tmp_path / 'checkout with spaces')


def test_default_preview_never_executes_sweep(case, shell):
    result = case.run(shell)
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert data['mode'] == 'verify-only'
    assert Path(data['code_root']).resolve() == case.root.resolve()
    assert Path(data['sweep_path']).resolve() == (case.root / '0-学习与工具/工具-落库sweep.py').resolve()
    assert data['sweep_arguments'] == []
    assert not (case.root / 'synthetic-sweep-call.json').exists()


def test_verify_only_on_non_main_branch_still_has_no_execution(case, shell):
    git(case.root, 'checkout', '-q', '-b', 'codex/fixture')
    result = case.run(shell, '-VerifyOnly')
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)['branch'] == 'codex/fixture'
    assert not (case.root / 'synthetic-sweep-call.json').exists()


@pytest.mark.parametrize('exit_code', [0, 7])
def test_explicit_run_uses_own_checkout_code_and_propagates_exit(case, shell, exit_code):
    (case.root / '0-学习与工具/工具-落库sweep.py').write_text(sweep_source(exit_code), encoding='utf8')
    result = case.run(shell, '-Run')
    assert result.returncode == exit_code, result.stdout + result.stderr
    called = json.loads((case.root / 'synthetic-sweep-call.json').read_text(encoding='utf8'))
    assert Path(called['script']).resolve() == (case.root / '0-学习与工具/工具-落库sweep.py').resolve()
    assert called['argv'] == []


@pytest.mark.parametrize('branch', ['codex/fixture', 'MAIN'])
def test_run_rejects_non_main_or_wrong_case_branch(case, shell, branch):
    git(case.root, 'checkout', '-q', '-b', branch)
    result = case.run(shell, '-Run')
    assert result.returncode == 9, result.stdout + result.stderr
    assert not (case.root / 'synthetic-sweep-call.json').exists()


def test_missing_runtime_never_falls_back_to_old_machine_wrapper(case, shell):
    (case.root / '.codex/runtime.local.json').unlink()
    (case.root / '0-学习与工具/run-commit-sweep.ps1').write_text('exit 0\n', encoding='utf8')
    result = case.run(shell, '-Run')
    assert result.returncode == 9, result.stdout + result.stderr
    assert not (case.root / 'synthetic-sweep-call.json').exists()


@pytest.mark.parametrize('value', ['{', '{"python":"python.exe"}', '{"python":"missing-value"}'])
def test_invalid_runtime_fails_closed_without_execution(case, shell, value):
    (case.root / '.codex/runtime.local.json').write_text(value, encoding='utf8')
    result = case.run(shell, '-Run')
    assert result.returncode == 9, result.stdout + result.stderr
    assert not (case.root / 'synthetic-sweep-call.json').exists()


def test_missing_absolute_python_or_sweep_fails_closed(case, shell):
    case.runtime(case.root, {'python': str(case.root / 'absent/python.exe')})
    result = case.run(shell, '-Run')
    assert result.returncode == 9, result.stdout + result.stderr
    case.runtime(case.root, {'python': sys.executable})
    (case.root / '0-学习与工具/工具-落库sweep.py').unlink()
    result = case.run(shell, '-Run')
    assert result.returncode == 9, result.stdout + result.stderr
    assert not (case.root / 'synthetic-sweep-call.json').exists()


def test_linked_checkout_uses_common_runtime_but_never_common_code(case, shell):
    linked = case.linked()
    result = case.run(shell, '-VerifyOnly', root=linked)
    assert result.returncode == 0, result.stdout + result.stderr
    assert Path(json.loads(result.stdout)['runtime_path']).resolve() == (case.root / '.codex/runtime.local.json').resolve()
    result = case.run(shell, '-Run', root=linked)
    assert result.returncode == 0, result.stdout + result.stderr
    called = json.loads((linked / 'synthetic-sweep-call.json').read_text(encoding='utf8'))
    assert Path(called['script']).resolve() == (linked / '0-学习与工具/工具-落库sweep.py').resolve()
    assert not (case.root / 'synthetic-sweep-call.json').exists()


def test_broken_local_runtime_does_not_hide_behind_valid_common_runtime(case, shell):
    linked = case.linked()
    path = case.runtime(linked, {})
    path.write_text('{', encoding='utf8')
    result = case.run(shell, '-Run', root=linked)
    assert result.returncode == 9, result.stdout + result.stderr
    assert not (linked / 'synthetic-sweep-call.json').exists()


def test_run_and_verify_only_cannot_be_combined(case, shell):
    result = case.run(shell, '-Run', '-VerifyOnly')
    assert result.returncode == 9, result.stdout + result.stderr
    assert not (case.root / 'synthetic-sweep-call.json').exists()


@pytest.mark.parametrize('exit_code', [0, 7])
def test_vbs_targets_versioned_launcher_hidden_and_propagates_exit(tmp_path, exit_code):
    assert b'ExecutionPolicy Bypass' not in VBS.read_bytes()
    target = tmp_path / 'run-commit-sweep-hidden.vbs'
    target.write_bytes(VBS.read_bytes())
    launcher = tmp_path / 'codex-handoff/launch_commit_sweep.ps1'
    launcher.parent.mkdir()
    launcher.write_text(f'exit {exit_code}\n', encoding='utf-8-sig')
    result = subprocess.run(['cscript', '//nologo', str(target)], cwd=tmp_path,
                            capture_output=True, text=True, encoding='utf8', errors='replace')
    assert result.returncode == exit_code, result.stdout + result.stderr
