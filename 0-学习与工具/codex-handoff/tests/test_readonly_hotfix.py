"""Real PowerShell guard contract, synthetic profiles, no models or networking."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('readonly_hotfix', BASE/'install_readonly_hotfix.py')
fix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fix)


@pytest.fixture
def machine(tmp_path):
    repo = tmp_path/'仓库 with spaces'
    home = tmp_path/'synthetic home'
    helper = repo/'0-学习与工具/codex-handoff/readonly_guard_hotfix.ps1'
    helper.parent.mkdir(parents=True)
    shutil.copyfile(BASE/'readonly_guard_hotfix.ps1', helper)
    guard = home/'.claude/hooks/pretooluse-guard.ps1'
    guard.parent.mkdir(parents=True)
    shutil.copyfile(BASE/'tests/fixtures/legacy_protected_guard.ps1', guard)
    (home/'.claude/protected-paths.json').write_text(json.dumps({
        'mode': 'block', 'patterns': ['*/.claude/settings.json', '*/.claude/hooks/*']
    }), encoding='utf8')
    return repo, home, guard, tmp_path/'state'


def invoke(machine, command=None, tool='PowerShell', cwd=None):
    repo, home, guard, state = machine
    event = {'cwd': str(cwd or repo), 'tool_name': tool,
             'tool_input': {'command': command} if command is not None else
             {'file_path': str(repo/'.claude/settings.json')}}
    return subprocess.run(['pwsh', '-NoProfile', '-File', str(guard)],
                          input=json.dumps(event), text=True, capture_output=True,
                          encoding='utf8', env=dict(os.environ, USERPROFILE=str(home)), timeout=20)


def test_reproduce_live_legacy_read_false_positive_then_fix(machine):
    repo, home, guard, state = machine
    command = 'Get-Content "C:/example/.claude/hooks/example.ps1"'
    assert invoke(machine, command).returncode == 2
    assert fix.operate(repo, guard, state, 'install')['installed']
    assert invoke(machine, command).returncode == 0


@pytest.mark.parametrize('command', [
    'Get-Content -LiteralPath "C:/example/.claude/hooks/example.ps1" -Raw',
    'Get-Item "C:/example/.claude/hooks/example.ps1" | Select-Object Name,Length',
    'Get-FileHash "C:/example/.claude/hooks/example.ps1" -Algorithm SHA256',
    'Select-String -LiteralPath "C:/example/.claude/hooks/example.ps1" -Pattern foo',
    'Get-Content "C:/example/.claude/hooks/example.ps1" | Select-Object -First 5',
    'Write-Output "说明 C:/example/.claude/hooks/example.ps1"',
])
def test_explicit_read_commands_are_allowed(machine, command):
    repo, home, guard, state = machine
    fix.operate(repo, guard, state, 'install')
    assert invoke(machine, command).returncode == 0


@pytest.mark.parametrize('tool', ['Read', 'Grep', 'Glob'])
def test_read_tools_are_allowed(machine, tool):
    repo, home, guard, state = machine
    fix.operate(repo, guard, state, 'install')
    assert invoke(machine, tool=tool).returncode == 0


@pytest.mark.parametrize('command', [
    'Set-Content "C:/example/.claude/hooks/example.ps1" -Value x',
    'Get-Content doc.md > "C:/example/.claude/hooks/example.ps1"',
    'Get-Content doc.md | Set-Content "C:/example/.claude/hooks/example.ps1"',
    'Get-Content "$(Set-Content C:/example/.claude/hooks/example.ps1 x)"',
    '& "Set-Content" "C:/example/.claude/hooks/example.ps1" x',
    '$x="C:/example/.claude/hooks/example.ps1"; Get-Content $x',
    'Get-Content "C:/example/.claude/hooks/example.ps1"; Remove-Item other',
    'Get-Content "C:/example/.claude/hooks/example.ps1" | ForEach-Object { $_ }',
    '[IO.File]::WriteAllText("C:/example/.claude/hooks/example.ps1", "x")',
    'python -c "print(open(\'C:/example/.claude/hooks/example.ps1\').read())"',
])
def test_write_or_ambiguous_commands_keep_original_guard(machine, command):
    repo, home, guard, state = machine
    fix.operate(repo, guard, state, 'install')
    assert invoke(machine, command).returncode == 2


def test_other_project_and_file_edit_keep_original_guard(machine, tmp_path):
    repo, home, guard, state = machine
    fix.operate(repo, guard, state, 'install')
    assert invoke(machine, 'Get-Content "C:/example/.claude/hooks/example.ps1"',
                  cwd=tmp_path/'other').returncode == 2
    assert invoke(machine, tool='Edit').returncode == 2


def test_hash_binding_rejects_changed_helper(machine):
    repo, home, guard, state = machine
    fix.operate(repo, guard, state, 'install')
    helper = repo/'0-学习与工具/codex-handoff/readonly_guard_hotfix.ps1'
    helper.write_bytes(helper.read_bytes()+b'\n# author edit\n')
    assert invoke(machine, 'Get-Content "C:/example/.claude/hooks/example.ps1"').returncode == 2
    with pytest.raises(ValueError, match='classifier changed'):
        fix.operate(repo, guard, state, 'install')


def test_preflight_idempotence_and_byte_exact_rollback(machine):
    repo, home, guard, state = machine
    original = guard.read_bytes()
    assert not fix.operate(repo, guard, state)['installed']
    assert guard.read_bytes() == original
    assert fix.operate(repo, guard, state, 'install')['changed']
    assert not fix.operate(repo, guard, state, 'install')['changed']
    assert fix.operate(repo, guard, state, 'rollback')['changed']
    assert guard.read_bytes() == original


def test_author_edit_is_preserved(machine):
    repo, home, guard, state = machine
    fix.operate(repo, guard, state, 'install')
    author = guard.read_bytes()+b'\n# author edit\n'
    guard.write_bytes(author)
    with pytest.raises(ValueError, match='author edit preserved'):
        fix.operate(repo, guard, state, 'rollback')
    assert guard.read_bytes() == author


@pytest.mark.parametrize('prefix,newline', [(b'', b'\n'), (b'\xef\xbb\xbf', b'\r\n')])
def test_encoding_and_newlines_are_retained(machine, prefix, newline):
    repo, home, guard, state = machine
    original = prefix+guard.read_bytes().decode('utf8').replace('\r\n','\n').encode().replace(b'\n',newline)
    guard.write_bytes(original)
    fix.operate(repo, guard, state, 'install')
    assert guard.read_bytes().startswith(prefix)
    fix.operate(repo, guard, state, 'rollback')
    assert guard.read_bytes() == original
