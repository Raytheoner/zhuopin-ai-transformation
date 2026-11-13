"""Native discipline carriers retain the existing non-whitelist boundary."""
import json
from pathlib import Path
import subprocess

import pytest


LIB = Path(__file__).resolve().with_name('工具-待合分支巡检-白名单判据.ps1')
NATIVE_CARRIERS = [
    'AGENTS.md', 'domain/AGENTS.md', 'domain/aGeNtS.MD',
    'CODEX-RULES.md', 'domain/CODEX-RULES.md', 'domain/cOdEx-RuLeS.MD',
    '.codex/notes.md', 'nested/.codex/notes.md', '.CODEX/notes.md',
    '.agents/skills/example/SKILL.md', 'nested/.agents/example.md', 'nested/.AGENTS/example.md',
    'openspec/change/.codex/config.toml', 'openspec/change/.agents/role.toml',
    'docs/codex/rules/环境保障线.md', 'docs/codex/rules/nested/规则.md',
    'DOCS/CODEX/RULES/example.md', 'docs/codex/执行纪律.md', 'docs/codex/沟通纪律.md',
    chr(92).join(['nested', 'AGENTS.md']),
    chr(92).join(['nested', 'CODEX-RULES.md']),
    chr(92).join(['nested', '.codex', 'notes.md']),
    chr(92).join(['nested', '.agents', 'SKILL.md']),
    chr(92).join(['docs', 'codex', 'rules', '规则.md']),
]
ORIGINAL_CARRIERS = ['CLAUDE.md', 'domain/CLAUDE.md', '.claude/rules/example.md',
                     '.gitignore', 'sub/.gitattributes', '1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md']
ORDINARY_DOCUMENTS = ['notes.md', 'docs/codex/README.md', '.codexish/notes.md', '.agents-reference/notes.md',
                      'notes/AGENTS.md.backup.md', 'notes/CODEX-RULES.md.example.md', 'openspec/change/config.toml']


def path_probe_body():
    paths = ','.join("'" + path.replace("'", "''") + "'" for path in NATIVE_CARRIERS + ORIGINAL_CARRIERS + ORDINARY_DOCUMENTS)
    return f'@({paths}) | ForEach-Object {{ Get-FfWhitelistFileVerdict -Path $_ }} | ConvertTo-Json -AsArray -Compress'


def run_json(tmp, body):
    script = tmp / 'verdict.ps1'
    script.write_text(f". '{LIB.as_posix()}'\n{body}\n", encoding='utf8')
    result = subprocess.run(['pwsh', '-NoProfile', '-NonInteractive', '-File', str(script)], cwd=tmp,
                            capture_output=True, text=True, encoding='utf8', check=True)
    return json.loads(result.stdout)


@pytest.fixture(scope='module')
def verdicts(tmp_path_factory):
    tmp = tmp_path_factory.mktemp('carrier-paths')
    return {row['Path']: row for row in run_json(tmp, path_probe_body())}


@pytest.mark.parametrize('path', NATIVE_CARRIERS)
def test_native_carrier_never_enters_low_risk_whitelist(verdicts, path):
    row = verdicts[path.replace(chr(92), '/')]
    assert row['Allowed'] is False, path
    assert row['Rule'] == 'carrier', row


@pytest.mark.parametrize('path', ORIGINAL_CARRIERS)
def test_original_carrier_protection_is_preserved(verdicts, path):
    assert verdicts[path]['Allowed'] is False
    assert verdicts[path]['Rule'] == 'carrier'


@pytest.mark.parametrize('path', ORDINARY_DOCUMENTS)
def test_ordinary_documents_keep_original_allowance(verdicts, path):
    assert verdicts[path]['Allowed'] is True
    assert verdicts[path]['Rule'] == 'allow'


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True,
                          encoding='utf8', check=True).stdout.strip()


@pytest.mark.parametrize('changed, expected', [('AGENTS.md', False), ('notes.md', True)], ids=['native-carrier', 'ordinary-document'])
def test_real_branch_preserves_all_five_whitelist_checks(tmp_path, changed, expected):
    repo = tmp_path / 'repo'
    repo.mkdir()
    git(repo, 'init', '-q', '-b', 'master')
    git(repo, 'config', 'user.email', 'fixture@example.invalid')
    git(repo, 'config', 'user.name', 'fixture')
    git(repo, 'config', 'commit.gpgsign', 'false')
    (repo / 'README.md').write_text('synthetic baseline\n', encoding='utf8')
    git(repo, 'add', '-A')
    git(repo, 'commit', '-q', '-m', 'synthetic baseline')
    git(repo, 'checkout', '-q', '-b', 'codex/native-carrier')
    (repo / changed).write_text('synthetic change\n', encoding='utf8')
    git(repo, 'add', '-A')
    git(repo, 'commit', '-q', '-m', 'synthetic change')
    git(repo, 'checkout', '-q', 'master')
    body = f"Test-FfWhitelist -Repo '{repo.as_posix()}' -Branch 'codex/native-carrier' -Base 'master' | ConvertTo-Json -Depth 6 -Compress"
    result = run_json(tmp_path, body)
    assert result['Hit'] is expected
    checks = {row['Id']: row for row in result['Checks']}
    assert set(checks) == {'⑴', '⑵', '⑶', '⑷', '⑸'}
    assert checks['⑵']['Ok'] and checks['⑷']['Ok'] and checks['⑸']['Ok']
    assert checks['⑴']['Ok'] is expected and checks['⑶']['Ok'] is expected
