"""`工具-worktree体检.ps1` 单测（队列 §一 #576，构建闭环第 13 环）。

盯死的六条：
- 缺 `commondir` 能被认出来，`-Repair` 后该 worktree 恢复可读；
- 有未合 commit 的，即便工作区干净也绝不删；
- 有真脏（未跟踪文件）的绝不删；
- 「仅缺文件」（脏行全是 D）默认只报不删，`-IncludeMissingOnly` 才删；
- 干净且 ahead=0 的，`-Apply` 才删，dry-run 不动；
- `-Keep` 点名的一律不删。

🔴 需要 PowerShell 7（`pwsh`），缺了整文件跳过（同 `test_工具-待合分支巡检-白名单判据.py` 手法）。
每个用例在临时目录 `git init -b master` 造一个小仓库并挂若干 worktree，不碰真仓库。
"""
from __future__ import annotations

import json
import shutil
import subprocess
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
