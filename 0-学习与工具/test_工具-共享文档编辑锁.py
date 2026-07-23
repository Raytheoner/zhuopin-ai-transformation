"""工具-共享文档编辑锁.py 单测（协议〇.7）。

黑盒方式：每个用例起子进程调用脚本，`--file` 指向本用例专属的临时文件，
不触碰真实的跨桌任务队列.md 锁，用例之间互不干扰。

覆盖交接文件《开场prompt-队列编辑锁-协议〇.7-CC建造交接.md》第5点要求的五种场景：
acquire 空锁成功 / 新鲜锁被占返回非0 / 陈旧锁可接管 / release 只删本人 / 并发两 who 只一个拿到。
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
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
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


if __name__ == "__main__":
    unittest.main()
