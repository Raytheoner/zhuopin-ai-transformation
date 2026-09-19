"""`工具-worktree体检.ps1` 单测（队列 §一 #576，构建闭环第 13 环）。

盯死的六条：
- 缺 `commondir` 能被认出来，`-Repair` 后该 worktree 恢复可读；
- 有未合 commit 的，即便工作区干净也绝不删；
- 有真脏（未跟踪文件）的绝不删；
- 「仅缺文件」（脏行全是 D）默认只报不删，`-IncludeMissingOnly` 才删；
- 干净且 ahead=0 的，`-Apply` 才删，dry-run 不动；
- `-Keep` 点名的一律不删。

另盯陈旧锁扫描（队列 §一 #618）三条：
- 三条清除判据齐备（陈旧超阈值＋0 字节＋无 git 进程）时报「可清」，不加 `-ClearStaleLocks` 不动手；
- 加 `-ClearStaleLocks` 后真删掉、且只删三条齐备的那些，未过阈值/非零字节的原样留着；
- 留痕 jsonl 里带锁扫描字段。

🔴 需要 PowerShell 7（`pwsh`），缺了整文件跳过（同 `test_工具-待合分支巡检-白名单判据.py` 手法）。
每个用例在临时目录 `git init -b master` 造一个小仓库并挂若干 worktree，不碰真仓库。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().with_name("工具-worktree体检.ps1")

pytestmark = pytest.mark.skipif(shutil.which("pwsh") is None, reason="需要 PowerShell 7（pwsh）")


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
    )
    return proc.stdout.strip()


def _run(repo: Path, *args: str):
    proc = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(TOOL), "-Repo", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc.stdout


def _worktree_names(repo: Path):
    out = _git(repo, "worktree", "list", "--porcelain")
    return {
        Path(line[len("worktree "):]).name
        for line in out.splitlines()
        if line.startswith("worktree ")
    } - {repo.name}


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


def _add_wt(repo: Path, name: str, *, ahead: int = 0) -> Path:
    p = repo / "wt" / name
    _git(repo, "worktree", "add", "-b", f"b/{name}", str(p), "master")
    for i in range(ahead):
        (p / f"x{i}.txt").write_text("x\n", encoding="utf-8")
        _git(p, "add", "-A")
        _git(p, "commit", "-m", f"c{i}")
    return p


def test_缺commondir_被认出且Repair后恢复(repo: Path):
    p = _add_wt(repo, "broken")
    (repo / ".git" / "worktrees" / "broken" / "commondir").unlink()
    assert subprocess.run(["git", "-C", str(p), "status"], capture_output=True).returncode != 0

    out = _run(repo)
    assert "缺 commondir：1 条" in out
    assert "broken" in out
    # dry-run 不修
    assert not (repo / ".git" / "worktrees" / "broken" / "commondir").exists()

    out = _run(repo, "-Repair")
    assert (repo / ".git" / "worktrees" / "broken" / "commondir").exists()
    assert subprocess.run(["git", "-C", str(p), "status"], capture_output=True).returncode == 0


def test_有未合commit的即便干净也不删(repo: Path):
    _add_wt(repo, "ahead1", ahead=1)
    out = _run(repo, "-Apply", "-IncludeMissingOnly")
    assert "有未合commit" in out
    assert "ahead1" in _worktree_names(repo)


def test_有真脏的不删(repo: Path):
    p = _add_wt(repo, "dirty")
    (p / "untracked.txt").write_text("u\n", encoding="utf-8")
    out = _run(repo, "-Apply", "-IncludeMissingOnly")
    assert "有真脏" in out
    assert "dirty" in _worktree_names(repo)


def test_仅缺文件_默认不删_加开关才删(repo: Path):
    p = _add_wt(repo, "missing")
    (p / "a.txt").unlink()

    out = _run(repo, "-Apply")
    assert "仅缺文件" in out
    assert "missing" in _worktree_names(repo)

    _run(repo, "-Apply", "-IncludeMissingOnly")
    assert "missing" not in _worktree_names(repo)


def test_干净已并_dry_run不动_Apply才删(repo: Path):
    _add_wt(repo, "clean")
    out = _run(repo)
    assert "dry-run" in out
    assert "clean" in _worktree_names(repo)

    _run(repo, "-Apply")
    assert "clean" not in _worktree_names(repo)


def test_保留名单点名的不删(repo: Path):
    _add_wt(repo, "keepme")
    _run(repo, "-Apply", "-IncludeMissingOnly", "-Keep", "keepme")
    assert "keepme" in _worktree_names(repo)


def test_留痕每次一行且记录模式(repo: Path):
    _add_wt(repo, "clean")
    _run(repo)
    _run(repo, "-Apply")
    traces = sorted((repo / "reports" / "worktree-guard").glob("*.jsonl"))
    assert len(traces) == 1
    rows = [json.loads(l) for l in traces[0].read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 2
    assert rows[0]["mode"] == "dry-run"
    assert rows[1]["mode"] == "apply"
    assert rows[1]["removed"] == ["clean"] or "clean" in rows[1]["removed"]

def _touch_lock(repo: Path, name: str, *, age_minutes: float, size_bytes: int = 0) -> Path:
    p = repo / ".git" / name
    p.write_bytes(b"x" * size_bytes)
    past = time.time() - age_minutes * 60
    os.utime(p, (past, past))
    return p


def test_陈旧锁_三条齐备才报可清_不加开关不动手(repo: Path):
    _touch_lock(repo, "stale.lock", age_minutes=45)
    _touch_lock(repo, "fresh.lock", age_minutes=5)
    out = _run(repo, "-StaleLockMinutes", "30")
    assert "stale.lock" in out and "可清" in out
    assert "fresh.lock" in out
    # 未加 -ClearStaleLocks，两个锁文件都原样留着
    assert (repo / ".git" / "stale.lock").exists()
    assert (repo / ".git" / "fresh.lock").exists()


def test_ClearStaleLocks只删三条齐备的(repo: Path):
    _touch_lock(repo, "stale.lock", age_minutes=45, size_bytes=0)
    _touch_lock(repo, "fresh.lock", age_minutes=5, size_bytes=0)
    _touch_lock(repo, "inuse.lock", age_minutes=45, size_bytes=8)
    out = _run(repo, "-StaleLockMinutes", "30", "-ClearStaleLocks")
    assert "已清 stale.lock" in out
    assert not (repo / ".git" / "stale.lock").exists()
    assert (repo / ".git" / "fresh.lock").exists()
    assert (repo / ".git" / "inuse.lock").exists()


def test_留痕带锁扫描字段(repo: Path):
    _touch_lock(repo, "stale.lock", age_minutes=45)
    _run(repo, "-StaleLockMinutes", "30")
    traces = sorted((repo / "reports" / "worktree-guard").glob("*.jsonl"))
    rows = [json.loads(l) for l in traces[0].read_text(encoding="utf-8").splitlines() if l.strip()]
    assert rows[-1]["locks_total"] == 1
    assert "stale.lock" in rows[-1]["locks_clearable"]


def test_目录已消失的worktree不让整份体检崩掉(repo: Path):
    """🔴 2026-09-17 首轮真跑就栽在这里：合入脚本刚收掉基线件、`.git/worktrees/` 里管理记录还在，
    `git -C <已消失目录> status` 抛 fatal，$ErrorActionPreference='Stop' 下整个体检直接终止。
    现在它应归为「目录已消失」一类，照常出报告。"""
    p = _add_wt(repo, "vanished")
    _add_wt(repo, "clean")
    shutil.rmtree(p)          # 只删工作目录，管理记录留着（复刻当时的现场）

    out = _run(repo)          # 不得抛、不得非零
    assert "目录已消失" in out
    assert "clean" in out     # 崩掉的话后面这条根本不会被打印
