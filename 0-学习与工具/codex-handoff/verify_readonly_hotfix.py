"""Run only the emergency read/write boundary contract with synthetic profiles."""
import contextlib
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import uuid

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    out = ROOT/'reports/hook-optimization-20261031'/(
        'readonly-verify-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
    out.mkdir(parents=True)
    fixtures = out/'fixtures'; fixtures.mkdir()
    paths = [HERE/'readonly_guard_hotfix.ps1', HERE/'install_readonly_hotfix.py',
             HERE/'verify_readonly_hotfix.py', HERE/'tests/test_readonly_hotfix.py',
             HERE/'tests/fixtures/legacy_protected_guard.ps1']
    def hashes():
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    before = hashes()

    class Isolation:
        @pytest.fixture
        def tmp_path(self):
            path = fixtures/uuid.uuid4().hex
            path.mkdir()
            return path

        @pytest.fixture(autouse=True)
        def no_network(self, monkeypatch):
            def deny(*args, **kwargs):
                raise AssertionError('network prohibited in hotfix tests')
            monkeypatch.setattr(socket.socket, 'connect', deny)

    os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    os.chdir(HERE)
    argv = ['-q', '-s', '-p', 'no:cacheprovider', '--tb=short',
            '--junitxml', str(out/'junit.xml'), 'tests/test_readonly_hotfix.py']
    with (out/'pytest.log').open('w', encoding='utf8') as stream:
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            code = int(pytest.main(argv, plugins=[Isolation()]))
    after = hashes()
    result = dict(exit=code if before == after else 2, pytest_exit=code,
                  source_drift=before != after, source_sha256=before,
                  argv=argv, cwd=str(HERE), full_project_suite=False,
                  isolation='synthetic profiles; real PowerShell; no model or network commands')
    (out/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps(dict(result=str(out/'result.json'), exit=result['exit'],
                         log=(out/'pytest.log').read_text(encoding='utf8')[-3500:]), ensure_ascii=False))
    return result['exit']


if __name__ == '__main__':
    sys.exit(main())
