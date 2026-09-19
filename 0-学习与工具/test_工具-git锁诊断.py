"""`工具-git锁诊断.ps1` 单测（队列 §一 #618，陈旧锁哨兵）。

盯死的三条清除判据（三条齐备才 clearable）：
- 陈旧超阈值 ＋ 0 字节 ＋ 无 git 进程 ⇒ clearable；
- 未过阈值（新鲜）⇒ 不 clearable，即便 0 字节、无进程；
- 非 0 字节（哪怕过阈值、无进程）⇒ 不 clearable——锁文件有内容说明可能仍在被用。
另盯 `Find-WorktreeByBranch`：命中占用者路径；未被任何 worktree 检出的分支返回空。

🔴 需要 PowerShell 7（`pwsh`），缺了整文件跳过（同 `test_工具-worktree体检.py` 手法）。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().with_name("工具-git锁诊断.ps1")

pytestmark = pytest.mark.skipif(shutil.which("pwsh") is None, reason="需要 PowerShell 7（pwsh）")


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
    )
    return proc.stdout.strip()


def _run_ps(script: str) -> str:
    proc = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc.stdout


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-b", "master")
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    (r / "a.txt").write_text("a\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-m", "init")
    return r


def _touch_lock(repo: Path, rel: str, *, age_minutes: float, size_bytes: int) -> Path:
    p = repo / ".git" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x" * size_bytes)
    stale_ts = (Path(__file__).stat().st_mtime) - age_minutes * 60  # 基准时刻不重要，用相对当下即可
    import time
    past = time.time() - age_minutes * 60
    os.utime(p, (past, past))
    return p


def _get_lock_status_json(repo: Path, *, stale_minutes: int = 30, proc_count: int = 0) -> dict:
    script = textwrap.dedent(f"""
        . '{TOOL}'
        $r = Get-GitLockStatus -Repo '{repo}' -StaleMinutes {stale_minutes} -GitProcessCount {proc_count}
        $r | ConvertTo-Json -Depth 6 -Compress
    """)
    out = _run_ps(script)
    return json.loads(out)


def test_陈旧_零字节_无进程_三条齐备才clearable(repo: Path):
    _touch_lock(repo, "stale.lock", age_minutes=45, size_bytes=0)
    status = _get_lock_status_json(repo, stale_minutes=30, proc_count=0)
    locks = status["Locks"]
    assert isinstance(locks, dict) or isinstance(locks, list)
    row = locks[0] if isinstance(locks, list) else locks
    assert row["path"] == "stale.lock"
    assert row["clearable"] is True


def test_未过阈值_不clearable(repo: Path):
    _touch_lock(repo, "fresh.lock", age_minutes=5, size_bytes=0)
    status = _get_lock_status_json(repo, stale_minutes=30, proc_count=0)
    locks = status["Locks"]
    row = locks[0] if isinstance(locks, list) else locks
    assert row["clearable"] is False


def test_非零字节_不clearable(repo: Path):
    _touch_lock(repo, "inuse.lock", age_minutes=45, size_bytes=12)
    status = _get_lock_status_json(repo, stale_minutes=30, proc_count=0)
    locks = status["Locks"]
    row = locks[0] if isinstance(locks, list) else locks
    assert row["clearable"] is False


def test_有git进程_不clearable(repo: Path):
    _touch_lock(repo, "busy.lock", age_minutes=45, size_bytes=0)
    status = _get_lock_status_json(repo, stale_minutes=30, proc_count=1)
    locks = status["Locks"]
    row = locks[0] if isinstance(locks, list) else locks
    assert row["clearable"] is False


def test_无锁文件_locks为空(repo: Path):
    status = _get_lock_status_json(repo)
    assert status["Locks"] in (None, [], {})


def test_FindWorktreeByBranch_命中占用者(repo: Path):
    p = repo / "wt" / "occ"
    _git(repo, "worktree", "add", "-b", "feat/occ", str(p), "master")
    script = textwrap.dedent(f"""
        . '{TOOL}'
        Find-WorktreeByBranch -Repo '{repo}' -Branch 'feat/occ'
    """)
    out = _run_ps(script).strip()
    assert out.replace("/", "\\").rstrip("\\") == str(p).replace("/", "\\").rstrip("\\")


def test_FindWorktreeByBranch_未命中返回空(repo: Path):
    script = textwrap.dedent(f"""
        . '{TOOL}'
        $r = Find-WorktreeByBranch -Repo '{repo}' -Branch 'no/such-branch'
        if ($null -eq $r) {{ Write-Output 'NULL' }} else {{ Write-Output $r }}
    """)
    out = _run_ps(script).strip()
    assert out == "NULL"
