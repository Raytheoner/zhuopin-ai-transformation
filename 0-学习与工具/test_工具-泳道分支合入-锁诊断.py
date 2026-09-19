"""`工具-泳道分支合入.ps1` 的锁/占用诊断补丁单测（队列 §一 #618）。

覆盖两处新增诊断，各带一条端到端回归用例：

1. `git worktree add` 撞 "already used by worktree"（2026-09-19 `OP-0919-H` 实撞一次，
   当时只报 `exit=9 脚本异常`、不报成因）——现在须点名占用者路径，退出码仍为 9（流程未走到判定，
   归「被打断」），但 stdout 里必须能看到占用者。这条端到端可靠复现（预先在另一路径 `git worktree add`
   检出同一分支即可稳定触发），故直接跑整条脚本。

2. ff-only 失败时打印锁状态——`Get-GitLockStatus`/`Format-GitLockStatusLines` 本身已在
   `test_工具-git锁诊断.py` 逐条单测过（三条清除判据、Find-WorktreeByBranch 命中/未命中）；
   ff 失败是竞态触发（rebase 后 master 被并发推进），单线程测试里无法确定性复现，
   不在此处伪造一条会随 git 版本/时序漂移的集成用例——打印调用点在 `工具-泳道分支合入.ps1`
   `⑤ ff+push` 分支里就近调用同一对已单测函数，读代码可核，不重复造轮子。

🔴 需要 PowerShell 7（`pwsh`），缺了整文件跳过（同 `test_工具-worktree体检.py` 手法）。
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().with_name("工具-泳道分支合入.ps1")

pytestmark = pytest.mark.skipif(shutil.which("pwsh") is None, reason="需要 PowerShell 7（pwsh）")


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
    )
    return proc.stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path):
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-b", "master", str(origin)],
                    capture_output=True, text=True, check=True)
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-b", "master")
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    (r / "a.txt").write_text("a\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-m", "init")
    _git(r, "remote", "add", "origin", str(origin))
    _git(r, "push", "-u", "origin", "master")
    temp_root = tmp_path
    return r, temp_root


def test_worktree_add占用冲突时点名占用者(repo):
    r, temp_root = repo
    _git(r, "branch", "feat/busy")
    occ = temp_root / "已占用副本"
    _git(r, "worktree", "add", str(occ), "feat/busy")

    proc = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(TOOL),
         "-Branch", "feat/busy", "-Repo", str(r), "-TempRoot", str(temp_root),
         "-KeepWorktree"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 9, out
    assert "建临时 worktree 失败" in out
    assert "占用者" in out
    assert str(occ) in out or "已占用副本" in out
