"""工具-共享文档编辑锁.py 单测（协议〇.7）。

黑盒方式：每个用例起子进程调用脚本，`--file` 指向本用例专属的临时文件，
不触碰真实的跨桌任务队列.md 锁，用例之间互不干扰。

覆盖交接文件《开场prompt-队列编辑锁-协议〇.7-CC建造交接.md》第5点要求的五种场景：
acquire 空锁成功 / 新鲜锁被占返回非0 / 陈旧锁可接管 / release 只删本人 / 并发两 who 只一个拿到。

另覆盖 2026-07-23 供应链看板批1 worktree 会话发现的 gap（REPO_ROOT 曾按
`__file__` 所在 checkout 推算，不同 worktree 各算各的锁、互相看不见）：
用真实 `git worktree add` 建一个主工作区+一个 linked worktree，验证同一份
脚本无论从哪个 checkout 跑，锁都落在同一个物理文件上。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-共享文档编辑锁.py")


def run(*args: str) -> subprocess.CompletedProcess:
    return run_at(SCRIPT, *args)


def run_at(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True, text=True, encoding="utf-8",
    )


class EditLockTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        # 目标文件本身不需要真实存在——锁只依附同名 .editlock，用绝对路径
        # 避开 REPO_ROOT，保证测试不影响真实队列锁。
        self.target = str(Path(self._tmpdir.name) / "假想队列.md")
        self.lock_path = Path(self.target + ".editlock")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write_lock(self, who: str, minutes_ago: float, note: str = "") -> None:
        held_since = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        self.lock_path.write_text(
            json.dumps({"who": who, "note": note, "held_since": held_since.isoformat()},
                       ensure_ascii=False),
            encoding="utf-8",
        )

    def test_acquire_empty_lock_succeeds(self):
        self.assertFalse(self.lock_path.exists())
        result = run("--file", self.target, "acquire", "--who", "A")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.lock_path.exists())
        self.assertEqual(json.loads(self.lock_path.read_text(encoding="utf-8"))["who"], "A")

    def test_acquire_fresh_lock_held_by_other_returns_nonzero(self):
        self._write_lock("A", minutes_ago=1)
        result = run("--file", self.target, "acquire", "--who", "B")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("占用中", result.stdout)
        # 锁未被 B 顶替
        self.assertEqual(json.loads(self.lock_path.read_text(encoding="utf-8"))["who"], "A")

    def test_acquire_stale_lock_is_taken_over(self):
        self._write_lock("A", minutes_ago=31)  # > STALE_MINUTES=30
        result = run("--file", self.target, "acquire", "--who", "B")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("陈旧", result.stdout)
        self.assertEqual(json.loads(self.lock_path.read_text(encoding="utf-8"))["who"], "B")

    def test_release_by_owner_deletes_lock(self):
        self._write_lock("A", minutes_ago=1)
        result = run("--file", self.target, "release", "--who", "A")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.lock_path.exists())

    def test_release_by_non_owner_does_not_delete_lock(self):
        self._write_lock("A", minutes_ago=1)
        result = run("--file", self.target, "release", "--who", "B")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.lock_path.exists(), "非本人 release 不应删掉别人的锁")
        self.assertEqual(json.loads(self.lock_path.read_text(encoding="utf-8"))["who"], "A")

    def test_release_without_who_force_releases(self):
        # 已文档化的常见用法：不带 --who 时无条件释放（不做保护）
        self._write_lock("A", minutes_ago=1)
        result = run("--file", self.target, "release")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.lock_path.exists())

    def test_concurrent_acquire_only_one_winner(self):
        # 模拟两会话同时首次 acquire：用两个子进程近似并发触发，
        # 断言最终只有一个 who 持锁（先到先得，后到者应看到占用返回非0）。
        procs = [
            subprocess.Popen([sys.executable, str(SCRIPT), "--file", self.target,
                               "acquire", "--who", who],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                              encoding="utf-8")
            for who in ("A", "B")
        ]
        outs = [p.communicate() for p in procs]
        codes = [p.returncode for p in procs]

        self.assertEqual(sorted(codes), [0, 1],
                          f"期望恰好一个成功一个失败，实际 codes={codes} outs={outs}")
        self.assertTrue(self.lock_path.exists())
        winner = json.loads(self.lock_path.read_text(encoding="utf-8"))["who"]
        self.assertIn(winner, ("A", "B"))


class EditLockCrossWorktreeTests(unittest.TestCase):
    """回归 2026-07-23 供应链看板批1 worktree 会话发现的 gap：
    REPO_ROOT 若按 __file__ 所在 checkout 推算，主工作区与
    linked worktree 会各算各的锁、互相看不见。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.main_root = Path(self._tmpdir.name) / "main"
        self.main_root.mkdir()
        self._git("init", "-q")
        self._git("config", "user.email", "test@example.com")
        self._git("config", "user.name", "Test")
        # 脚本放进仓库同名子目录，模拟生产布局（脚本在仓库根下一层子目录）。
        script_dir = self.main_root / "0-学习与工具"
        script_dir.mkdir()
        (script_dir / "工具-共享文档编辑锁.py").write_text(
            SCRIPT.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (self.main_root / "queue.md").write_text("占位\n", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "init")
        self.linked_root = Path(self._tmpdir.name) / "linked"
        self._git("worktree", "add", "-q", str(self.linked_root), "-b", "linked-branch")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=self.main_root, check=True,
            capture_output=True, text=True,
        )

    def _tool(self, root: Path) -> Path:
        return root / "0-学习与工具" / "工具-共享文档编辑锁.py"

    def test_lock_visible_across_worktrees(self):
        r1 = run_at(self._tool(self.main_root), "--file", "queue.md",
                    "acquire", "--who", "A")
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)

        # 从 linked worktree 里跑同一份脚本：修复前会各算各的 REPO_ROOT，
        # 看不到主工作区的锁，acquire 会“误成功”（本应因占用中被拒绝）。
        r2 = run_at(self._tool(self.linked_root), "--file", "queue.md",
                    "acquire", "--who", "B")
        self.assertNotEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertIn("占用中", r2.stdout)

        # 锁物理文件应且仅应落在主工作区那一份，不应在 linked worktree 里另长一份。
        self.assertTrue((self.main_root / "queue.md.editlock").exists())
        self.assertFalse((self.linked_root / "queue.md.editlock").exists())

    def test_release_from_linked_worktree_releases_main_lock(self):
        run_at(self._tool(self.main_root), "--file", "queue.md",
               "acquire", "--who", "A")
        r = run_at(self._tool(self.linked_root), "--file", "queue.md",
                   "release", "--who", "A")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.main_root / "queue.md.editlock").exists())


if __name__ == "__main__":
    unittest.main()
