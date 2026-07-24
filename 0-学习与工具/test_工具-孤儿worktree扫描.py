"""工具-孤儿worktree扫描.py 单测（队列 #68④）。

用真实 `git worktree add` 建最小仓库拓扑（bare origin + 主工作区 + 若干 linked
worktree/分支），验证 ahead=0 判据与"只读不删"红线——覆盖设计文档原话
"值周巡检兜底：每周扫 ahead=0 孤儿 worktree/陈旧分支，生成清理任务交
CC（巡检只读不删）"的每一个关键词。
"""
from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-孤儿worktree扫描.py")

_spec = importlib.util.spec_from_file_location("orphan_scan", SCRIPT)
orphan_scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orphan_scan)


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=cwd,
                           capture_output=True, text=True, encoding="utf-8", check=check)


def _same_path(a: str, b: Path) -> bool:
    """git 输出用正斜杠、Windows 短文件名也可能与 tempfile 报告的长名不一致——
    路径比较一律 resolve() 后再比，不做原始字符串匹配。"""
    return Path(a).resolve() == b.resolve()


class OrphanWorktreeScanTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.origin = base / "origin.git"
        self.main = base / "main"
        _git(base, "init", "--bare", "-q", str(self.origin))
        _git(base, "init", "-q", str(self.main))
        _git(self.main, "config", "user.email", "test@example.com")
        _git(self.main, "config", "user.name", "Test")
        _git(self.main, "remote", "add", "origin", str(self.origin))
        (self.main / "README.md").write_text("init\n", encoding="utf-8")
        _git(self.main, "add", "-A")
        _git(self.main, "commit", "-q", "-m", "init")
        _git(self.main, "branch", "-M", "master")
        _git(self.main, "push", "-q", "-u", "origin", "master")

    def tearDown(self):
        self._tmp.cleanup()

    def _add_worktree(self, name: str, branch: str) -> Path:
        wt_path = self.main.parent / name
        _git(self.main, "worktree", "add", "-q", str(wt_path), "-b", branch)
        return wt_path

    def _merge_branch_into_master(self, branch: str) -> None:
        _git(self.main, "merge", "-q", "--no-ff", branch, "-m", f"merge {branch}")
        _git(self.main, "push", "-q", "origin", "master")

    def test_reports_orphan_worktree_fully_merged_and_clean(self):
        wt = self._add_worktree("done-work", "claude/done-work")
        (wt / "output.md").write_text("完成的产出\n", encoding="utf-8")
        _git(wt, "add", "-A")
        _git(wt, "commit", "-q", "-m", "worktree 产出")
        self._merge_branch_into_master("claude/done-work")

        findings = orphan_scan.scan(self.main)
        paths = [w["path"] for w in findings["orphan_worktrees"]]
        self.assertTrue(any(_same_path(p, wt) for p in paths), paths)
        report = orphan_scan.format_report(findings)
        self.assertIn("git worktree remove", report)

    def test_worktree_still_ahead_not_reported(self):
        wt = self._add_worktree("in-progress", "claude/in-progress")
        (wt / "output.md").write_text("还没合并的产出\n", encoding="utf-8")
        _git(wt, "add", "-A")
        _git(wt, "commit", "-q", "-m", "尚未合并")
        # 故意不合并进 master——应被判定为 ahead>0，不进候选清单。

        findings = orphan_scan.scan(self.main)
        paths = [w["path"] for w in findings["orphan_worktrees"]]
        self.assertNotIn(str(wt), paths)

    def test_dirty_but_merged_worktree_is_observation_only(self):
        wt = self._add_worktree("dirty-done", "claude/dirty-done")
        (wt / "output.md").write_text("完成的产出\n", encoding="utf-8")
        _git(wt, "add", "-A")
        _git(wt, "commit", "-q", "-m", "worktree 产出")
        self._merge_branch_into_master("claude/dirty-done")
        (wt / "未提交草稿.md").write_text("还没提交的东西\n", encoding="utf-8")  # 使其"脏"

        findings = orphan_scan.scan(self.main)
        orphan_paths = [w["path"] for w in findings["orphan_worktrees"]]
        dirty_paths = [w["path"] for w in findings["dirty_but_merged_worktrees"]]
        self.assertFalse(any(_same_path(p, wt) for p in orphan_paths),
                          "有未提交改动时不应直接建议删除")
        self.assertTrue(any(_same_path(p, wt) for p in dirty_paths), dirty_paths)

    def test_orphan_branch_without_worktree_reported(self):
        _git(self.main, "branch", "claude/stale-no-worktree")
        # 该分支从 master 分出、无新提交、也从未建过 worktree——天然 ahead=0。

        findings = orphan_scan.scan(self.main)
        branches = [b["branch"] for b in findings["orphan_branches"]]
        self.assertIn("claude/stale-no-worktree", branches)

    def test_scan_never_deletes_anything(self):
        wt = self._add_worktree("must-survive", "claude/must-survive")
        (wt / "output.md").write_text("完成的产出\n", encoding="utf-8")
        _git(wt, "add", "-A")
        _git(wt, "commit", "-q", "-m", "worktree 产出")
        self._merge_branch_into_master("claude/must-survive")
        _git(self.main, "branch", "claude/also-stale")

        orphan_scan.scan(self.main)  # 只读扫描

        self.assertTrue(wt.exists(), "扫描不应删除任何 worktree 目录")
        branches_after = _git(self.main, "branch", "--list").stdout
        self.assertIn("claude/must-survive", branches_after)
        self.assertIn("claude/also-stale", branches_after)
        # 路径含空格（"Paul Shao"），"worktree list"人类可读格式不能按空白 split
        # 取列——改用同一份 --porcelain 解析器（本项目路径全含空格，这也正是
        # SUT 自身必须用 --porcelain 而非人类可读格式的原因）。
        worktrees_after = orphan_scan._parse_worktree_porcelain(
            _git(self.main, "worktree", "list", "--porcelain").stdout)
        self.assertTrue(any(_same_path(w["path"], wt) for w in worktrees_after),
                         worktrees_after)


if __name__ == "__main__":
    unittest.main()
