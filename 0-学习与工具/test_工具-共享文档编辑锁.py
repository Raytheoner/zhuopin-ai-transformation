"""工具-共享文档编辑锁.py 单测（协议〇.7）。

黑盒方式：每个用例起子进程调用脚本，`--file` 指向本用例专属的临时文件，
不触碰真实的跨桌任务队列.md 锁，用例之间互不干扰。

覆盖交接文件《开场prompt-队列编辑锁-协议〇.7-CC建造交接.md》第5点要求的五种场景：
acquire 空锁成功 / 新鲜锁被占返回非0 / 陈旧锁可接管 / release 只放行本人 / 并发两 who 只一个拿到。

另覆盖 2026-07-23 供应链看板批1 worktree 会话发现的 gap（REPO_ROOT 曾按
`__file__` 所在 checkout 推算，不同 worktree 各算各的锁、互相看不见）：
用真实 `git worktree add` 建一个主工作区+一个 linked worktree，验证同一份
脚本无论从哪个 checkout 跑，锁都落在同一个物理文件上。

另覆盖 #121 两处修法（2026-07-27）：
(a) release 改写"released"标记而非 unlink（Cowork 沙箱对本文件 unlink 会
    PermissionError，改写规避了这个问题）——released 标记应等价于"无锁"。
(c) acquire 成功时回显持锁瞬间从目标文件读到的"编号高水位线"行，供新行编号
    在锁保护窗口内重算，从机制上消灭"编号在 acquire 之前算、锁前读到的高水位
    线已被推高"这类撞号。

另覆盖 #197（2026-08-02）：acquire 原是"读判定→写"两步、中间无互斥，两个
进程可同一窗口内都读到"无锁"、都写入成功、都相信自己持锁。新增更强并发
用例（比既有两进程用例更多并发、更可靠地证伪"双授权"）+ 白盒用例（直接
import 模块，覆盖子进程黑盒难以可靠触发的"陈旧互斥标记被接管"路径）。
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-共享文档编辑锁.py")


def _load_module():
    """白盒 import 脚本本体（文件名含连字符/中文，不能直接 `import`）。"""
    spec = importlib.util.spec_from_file_location("_edit_lock_tool_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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

    def test_release_by_owner_writes_released_marker_not_unlink(self):
        # #121(a)：Cowork 沙箱对本文件 unlink 会 PermissionError，release 改为
        # 改写"released"标记——文件应仍然存在（不是被删除），但标记内容表明已释放。
        self._write_lock("A", minutes_ago=1)
        result = run("--file", self.target, "release", "--who", "A")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.lock_path.exists(), "release 不应删除锁文件，应改写为释放标记")
        marker = json.loads(self.lock_path.read_text(encoding="utf-8"))
        self.assertTrue(marker.get("released"))
        self.assertEqual(marker.get("who"), "A")
        # released 标记应等价于"无锁"：status 报告无锁，下一次 acquire 立即
        # 成功且不出现"陈旧"接管提示（因为它压根不被当作陈旧锁，而是无锁）。
        status = run("--file", self.target, "status")
        self.assertIn("无锁", status.stdout)
        result2 = run("--file", self.target, "acquire", "--who", "B")
        self.assertEqual(result2.returncode, 0, result2.stdout + result2.stderr)
        self.assertNotIn("陈旧", result2.stdout)
        self.assertEqual(json.loads(self.lock_path.read_text(encoding="utf-8"))["who"], "B")

    def test_release_by_non_owner_does_not_touch_lock(self):
        self._write_lock("A", minutes_ago=1)
        result = run("--file", self.target, "release", "--who", "B")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.lock_path.exists(), "非本人 release 不应动别人的锁")
        lock_data = json.loads(self.lock_path.read_text(encoding="utf-8"))
        self.assertEqual(lock_data["who"], "A")
        self.assertNotIn("released", lock_data, "非本人 release 被拒绝时不应写入释放标记")

    def test_release_without_who_force_releases(self):
        # 已文档化的常见用法：不带 --who 时无条件释放（不做保护）——
        # 释放后应仍是"改写标记"，不是删除文件。
        self._write_lock("A", minutes_ago=1)
        result = run("--file", self.target, "release")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.lock_path.exists())
        self.assertTrue(json.loads(self.lock_path.read_text(encoding="utf-8")).get("released"))

    def test_acquire_echoes_high_water_mark_from_target_file(self):
        # #121(c)：目标文件（如跨桌任务队列.md）含"编号高水位线"行时，acquire
        # 成功应回显持锁瞬间读到的值，供新行编号在锁保护窗口内重算。
        Path(self.target).write_text(
            "> **编号高水位线：§一 #123 ｜ §四 #36**（说明文字，2026-07-24 起启用）\n",
            encoding="utf-8",
        )
        result = run("--file", self.target, "acquire", "--who", "A")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("持锁瞬间高水位线", result.stdout)
        self.assertIn("§一 #123", result.stdout)
        self.assertIn("§四 #36", result.stdout)

    def test_acquire_without_high_water_mark_line_does_not_crash(self):
        Path(self.target).write_text("没有高水位线这一行的普通文件\n", encoding="utf-8")
        result = run("--file", self.target, "acquire", "--who", "A")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("持锁瞬间高水位线", result.stdout)

    def test_acquire_target_file_missing_does_not_crash(self):
        # self.target 本身不存在（只有 .editlock 会被创建）——不应报错，只是不回显。
        self.assertFalse(Path(self.target).exists())
        result = run("--file", self.target, "acquire", "--who", "A")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("持锁瞬间高水位线", result.stdout)

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

    def test_concurrent_acquire_many_processes_exactly_one_winner(self):
        # #197：比上一用例（仅两进程）更强的回归——原 check-then-act 实现
        # 下，并发进程数越多、"都读到无锁"的重叠概率越高，更可靠地证伪
        # "双授权"这一具体 bug 形态（而非依赖两进程恰好撞上的运气）。
        whos = [f"P{i}" for i in range(16)]
        procs = [
            subprocess.Popen([sys.executable, str(SCRIPT), "--file", self.target,
                               "acquire", "--who", who],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                              encoding="utf-8")
            for who in whos
        ]
        results = [p.communicate() for p in procs]
        codes = [p.returncode for p in procs]

        winners = [who for who, code in zip(whos, codes) if code == 0]
        self.assertEqual(len(winners), 1,
                          f"期望恰好一个成功，实际 codes={list(zip(whos, codes))}\n{results}")
        self.assertEqual(
            json.loads(self.lock_path.read_text(encoding="utf-8"))["who"], winners[0]
        )
        mutex_path = Path(str(self.lock_path) + ".mutex")
        self.assertFalse(mutex_path.exists(), "互斥标记不应在全部调用结束后遗留")

    def test_concurrent_stale_takeover_exactly_one_winner(self):
        # #197 修法要点③：陈旧锁被多个进程同时接管——只允许恰好一个成功，
        # 不能像原实现那样多个进程都判定"陈旧、可接管"并各自写入。
        self._write_lock("OLD", minutes_ago=31)  # > STALE_MINUTES=30
        whos = [f"P{i}" for i in range(10)]
        procs = [
            subprocess.Popen([sys.executable, str(SCRIPT), "--file", self.target,
                               "acquire", "--who", who],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                              encoding="utf-8")
            for who in whos
        ]
        results = [p.communicate() for p in procs]
        codes = [p.returncode for p in procs]

        winners = [who for who, code in zip(whos, codes) if code == 0]
        self.assertEqual(len(winners), 1,
                          f"陈旧锁接管应恰好一个成功，实际 codes={list(zip(whos, codes))}\n{results}")
        self.assertEqual(
            json.loads(self.lock_path.read_text(encoding="utf-8"))["who"], winners[0]
        )


class AcquireMutexInternalsTests(unittest.TestCase):
    """#197：白盒直接测试互斥锁内部实现——覆盖子进程黑盒测试难以可靠
    触发的"陈旧互斥标记被接管"路径（需要一个"崩溃后遗留互斥文件"的
    人为场景，比起真的杀掉子进程，直接摆好文件状态更稳定可靠）。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.lock_path = Path(self._tmpdir.name) / "假想队列.md.editlock"
        self.module = _load_module()

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_mutex_not_left_behind_after_normal_use(self):
        mutex_path = self.module._mutex_path(self.lock_path)
        with self.module._acquire_mutex(self.lock_path):
            self.assertTrue(mutex_path.exists())
        self.assertFalse(mutex_path.exists())

    def test_mutex_blocks_concurrent_holder(self):
        mutex_path = self.module._mutex_path(self.lock_path)
        with self.module._acquire_mutex(self.lock_path):
            with self.assertRaises(FileExistsError):
                fd = os.open(str(mutex_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)

    def test_stale_mutex_is_reclaimed_promptly(self):
        # 模拟"上一个持有互斥的进程异常退出、未清理"——新调用应很快接管，
        # 不应傻等到 MUTEX_WAIT_TIMEOUT_SECONDS 超时才成功。
        mutex_path = self.module._mutex_path(self.lock_path)
        mutex_path.write_text("", encoding="utf-8")
        stale_time = time.time() - (self.module.MUTEX_STALE_SECONDS + 5)
        os.utime(mutex_path, (stale_time, stale_time))

        start = time.monotonic()
        with self.module._acquire_mutex(self.lock_path):
            pass
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, self.module.MUTEX_WAIT_TIMEOUT_SECONDS)
        self.assertFalse(mutex_path.exists())

    def test_stale_mutex_unlink_always_fails_falls_back_to_rename_away(self):
        # #322：Cowork 沙箱对挂载目录无删除权限，unlink 恒 PermissionError；
        # 退路 os.replace 到固定 .stale 伴生路径应让 canonical 路径立即清空，
        # _acquire_mutex 不应挂起（旧实现在此死循环，MUTEX_WAIT_TIMEOUT_SECONDS
        # 形同虚设）。
        mutex_path = self.module._mutex_path(self.lock_path)
        mutex_path.write_text("", encoding="utf-8")
        stale_time = time.time() - (self.module.MUTEX_STALE_SECONDS + 5)
        os.utime(mutex_path, (stale_time, stale_time))

        with unittest.mock.patch.object(Path, "unlink", side_effect=PermissionError("模拟无删除权限")):
            start = time.monotonic()
            with self.module._acquire_mutex(self.lock_path):
                pass
            elapsed = time.monotonic() - start

        self.assertLess(elapsed, self.module.MUTEX_WAIT_TIMEOUT_SECONDS,
                         "unlink 恒失败时应走 rename-away 退路立即接管，不应等满超时")
        self.assertFalse(mutex_path.exists(), "canonical 路径应已被改名清空")
        self.assertTrue(Path(str(mutex_path) + ".stale").exists(),
                         "应改名到固定 .stale 伴生路径")

    def test_cleanup_completely_fails_raises_timeout_not_hang(self):
        # #322 核心回归：unlink 与改名退路都失败时，不得无条件 continue 跳过
        # deadline 判断（那正是死循环的成因）；须在 MUTEX_WAIT_TIMEOUT_SECONDS
        # 内 fail-loud 抛 TimeoutError，而不是无限挂起、零输出。
        mutex_path = self.module._mutex_path(self.lock_path)
        mutex_path.write_text("", encoding="utf-8")
        stale_time = time.time() - (self.module.MUTEX_STALE_SECONDS + 5)
        os.utime(mutex_path, (stale_time, stale_time))

        with unittest.mock.patch.object(Path, "unlink", side_effect=PermissionError("模拟无删除权限")), \
             unittest.mock.patch.object(self.module.os, "replace", side_effect=PermissionError("模拟改名也失败")):
            start = time.monotonic()
            with self.assertRaises(TimeoutError):
                with self.module._acquire_mutex(self.lock_path):
                    pass
            elapsed = time.monotonic() - start

        self.assertLess(elapsed, self.module.MUTEX_WAIT_TIMEOUT_SECONDS + 2,
                         "清理彻底失败应在超时窗口内报错退出，不应无限挂起")

    def test_stale_companion_path_is_fixed_not_proliferating(self):
        # #322：伴生路径固定复用，不随每次清理事件新增一个文件（避免像本次
        # 巡逻手工处置那样无界堆积）。
        mutex_path = self.module._mutex_path(self.lock_path)
        with unittest.mock.patch.object(Path, "unlink", side_effect=PermissionError("模拟无删除权限")):
            for _ in range(3):
                mutex_path.write_text("", encoding="utf-8")
                stale_time = time.time() - (self.module.MUTEX_STALE_SECONDS + 5)
                os.utime(mutex_path, (stale_time, stale_time))
                with self.module._acquire_mutex(self.lock_path):
                    pass

        companions = sorted(
            p.name for p in self.lock_path.parent.glob(mutex_path.name + "*")
        )
        self.assertEqual(companions, [mutex_path.name + ".stale"],
                          "多轮清理事件应复用同一固定伴生文件，不应堆积多个")

    def test_release_falls_back_to_rename_when_unlink_fails(self):
        # #322：release（finally 块）unlink 失败时也应立即改名清空 canonical
        # 路径，不必等 MUTEX_STALE_SECONDS 超时才被下一次 acquire 的陈旧清理
        # 分支接管——Cowork 沙箱下每次正常 release 后都应能让路径立即空闲。
        mutex_path = self.module._mutex_path(self.lock_path)
        with unittest.mock.patch.object(Path, "unlink", side_effect=PermissionError("模拟无删除权限")):
            with self.module._acquire_mutex(self.lock_path):
                pass
        self.assertFalse(mutex_path.exists(), "release 后 canonical 路径应已清空")
        self.assertTrue(Path(str(mutex_path) + ".stale").exists())

    def test_atomic_write_json_readback_matches(self):
        target = self.lock_path
        self.module._atomic_write_json(target, {"who": "A", "held_since": "t0"})
        self.assertEqual(
            json.loads(target.read_text(encoding="utf-8")),
            {"who": "A", "held_since": "t0"},
        )
        # 无临时文件遗留。
        leftovers = list(target.parent.glob(f"{target.name}.tmp.*"))
        self.assertEqual(leftovers, [])


class ReserveIdsTests(unittest.TestCase):
    """队列 #163：`acquire --reserve N --section 一|四` 预留取号。

    覆盖分析件 §一 §1.4 列出的 8 条验收要求：单号/多号预留、§一/§四 互不
    干扰、写后核验高水位线已回写、高水位线缺失/格式漂移 fail-loud、锁忙
    时不分配、两次并发 acquire+reserve 编号不重叠、预留未用留空洞、release
    不影响已推进的高水位线。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.target = str(Path(self._tmpdir.name) / "假想队列.md")
        self.lock_path = Path(self.target + ".editlock")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write_queue(self, section_one: int = 168, section_four: int = 37) -> None:
        Path(self.target).write_text(
            f"> **编号高水位线：§一 #{section_one} ｜ §四 #{section_four}**"
            "（2026-07-24 首次清扫起启用）\n\n"
            "## 一、任务看板\n\n"
            "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
            "|---|------|--------|-------------|----------|------|--------|------|\n",
            encoding="utf-8",
        )

    def test_reserve_single_id_returns_next_literal_number(self):
        self._write_queue(section_one=168)
        result = run("--file", self.target, "acquire", "--who", "A",
                      "--reserve", "1", "--section", "一")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("§一 #169", result.stdout)
        self.assertNotIn("§一 #170", result.stdout)

    def test_reserve_multiple_ids_returns_consecutive_literal_numbers(self):
        self._write_queue(section_one=168)
        result = run("--file", self.target, "acquire", "--who", "A",
                      "--reserve", "3", "--section", "一")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for expected in ("§一 #169", "§一 #170", "§一 #171"):
            self.assertIn(expected, result.stdout)

    def test_reserve_section_one_and_four_count_independently(self):
        self._write_queue(section_one=168, section_four=37)
        result_one = run("--file", self.target, "acquire", "--who", "A",
                          "--reserve", "2", "--section", "一")
        self.assertEqual(result_one.returncode, 0, result_one.stdout + result_one.stderr)
        self.assertIn("§一 #169", result_one.stdout)
        self.assertIn("§一 #170", result_one.stdout)
        run("--file", self.target, "release", "--who", "A")

        result_four = run("--file", self.target, "acquire", "--who", "A",
                           "--reserve", "1", "--section", "四")
        self.assertEqual(result_four.returncode, 0, result_four.stdout + result_four.stderr)
        self.assertIn("§四 #38", result_four.stdout)  # 未被 §一 的预留影响

        final_text = Path(self.target).read_text(encoding="utf-8")
        self.assertIn("编号高水位线：§一 #170 ｜ §四 #38", final_text)

    def test_reserve_writes_back_high_water_mark_verified_by_reread(self):
        """写后核验：不只看返回值/终端输出，重新读一次目标文件确认高水位
        线行确已回写到位。"""
        self._write_queue(section_one=168, section_four=37)
        run("--file", self.target, "acquire", "--who", "A", "--reserve", "2", "--section", "一")

        reread = Path(self.target).read_text(encoding="utf-8")
        self.assertIn("编号高水位线：§一 #170 ｜ §四 #37", reread)

    def test_reserve_fails_loud_when_high_water_mark_line_missing(self):
        Path(self.target).write_text("没有高水位线这一行的普通文件\n", encoding="utf-8")
        original = Path(self.target).read_text(encoding="utf-8")

        result = run("--file", self.target, "acquire", "--who", "A",
                      "--reserve", "1", "--section", "一")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("拒绝预留", result.stdout)
        # 不写任何内容——目标文件原封不动。
        self.assertEqual(Path(self.target).read_text(encoding="utf-8"), original)
        # 且不留下一个"锁被占但没预留成功"的半成品状态——回滚为已释放。
        marker = json.loads(self.lock_path.read_text(encoding="utf-8"))
        self.assertTrue(marker.get("released"))

    def test_reserve_fails_loud_when_section_number_malformed(self):
        """高水位线行存在，但目标分区号解析失败（格式漂移）——同样 fail-loud，
        不回落"仅取可见最大号"之类的替代计算。"""
        Path(self.target).write_text(
            "> **编号高水位线：§一 格式已变 ｜ §四 #37**（说明文字）\n", encoding="utf-8"
        )
        original = Path(self.target).read_text(encoding="utf-8")

        result = run("--file", self.target, "acquire", "--who", "A",
                      "--reserve", "1", "--section", "一")

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(Path(self.target).read_text(encoding="utf-8"), original)

    def test_reserve_requires_section_argument(self):
        self._write_queue()
        result = run("--file", self.target, "acquire", "--who", "A", "--reserve", "1")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.lock_path.exists(), "校验失败时不应连锁文件都创建")

    def test_reserve_not_granted_when_lock_held_by_other(self):
        """锁已被他人持有时——占锁失败，不得分配任何编号（高水位线不应被
        改动）。"""
        self._write_queue(section_one=168)
        self._write_lock("B", minutes_ago=1)
        original = Path(self.target).read_text(encoding="utf-8")

        result = run("--file", self.target, "acquire", "--who", "A",
                      "--reserve", "1", "--section", "一")

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(Path(self.target).read_text(encoding="utf-8"), original)

    def _write_lock(self, who: str, minutes_ago: float, note: str = "") -> None:
        held_since = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        self.lock_path.write_text(
            json.dumps({"who": who, "note": note, "held_since": held_since.isoformat()},
                       ensure_ascii=False),
            encoding="utf-8",
        )

    def test_two_sequential_reserves_do_not_overlap(self):
        """模拟两桌先后各预留——第二桌看到的必须是第一桌推进后的高水位
        线，两次拿到的编号区间不重叠（顺序执行即真实还原两桌各自
        acquire→reserve→release 的协议约束，无需真并发也能验证不重叠这一
        核心性质）。"""
        self._write_queue(section_one=168)
        first = run("--file", self.target, "acquire", "--who", "A",
                    "--reserve", "2", "--section", "一")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        run("--file", self.target, "release", "--who", "A")

        second = run("--file", self.target, "acquire", "--who", "B",
                     "--reserve", "2", "--section", "一")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)

        self.assertIn("§一 #169", first.stdout)
        self.assertIn("§一 #170", first.stdout)
        self.assertIn("§一 #171", second.stdout)
        self.assertIn("§一 #172", second.stdout)

    def test_reserve_then_release_without_using_leaves_gap_and_keeps_high_water_mark(self):
        """预留后不写任何行、直接 release——高水位线应保持已推进（空洞可
        接受，协议〇.8：编号永不复用），不做任何"释放未用编号"的回收。"""
        self._write_queue(section_one=168)
        run("--file", self.target, "acquire", "--who", "A", "--reserve", "3", "--section", "一")
        release_result = run("--file", self.target, "release", "--who", "A")
        self.assertEqual(release_result.returncode, 0)

        final_text = Path(self.target).read_text(encoding="utf-8")
        self.assertIn("编号高水位线：§一 #171 ｜", final_text)  # 168+3，未回退
        # 表格本身没有新增任何行——预留不等于写行。
        self.assertNotIn("| 169 |", final_text)
        self.assertNotIn("| 170 |", final_text)
        self.assertNotIn("| 171 |", final_text)


class ReserveMultiTests(unittest.TestCase):
    """队列 #185：`--reserve-multi 一:2 四:1` 一次性跨多分区预留 +
    竞态防护（高水位线滞后于文件实际内容时 fail-loud）。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.target = str(Path(self._tmpdir.name) / "假想队列.md")
        self.lock_path = Path(self.target + ".editlock")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write_queue(self, section_one: int = 168, section_four: int = 37,
                      section_one_rows: str = "") -> None:
        Path(self.target).write_text(
            f"> **编号高水位线：§一 #{section_one} ｜ §四 #{section_four}**"
            "（2026-07-24 首次清扫起启用）\n\n"
            "## 一、任务看板\n\n"
            "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
            "|---|------|--------|-------------|----------|------|--------|------|\n"
            f"{section_one_rows}"
            "\n## 四、需 Shao Peishen 的动作（例外与拍板）\n\n"
            "| # | 事项 | 等谁 | 截止 |\n"
            "|---|------|------|------|\n",
            encoding="utf-8",
        )

    def test_reserve_multi_reserves_both_sections_in_one_call(self):
        self._write_queue(section_one=168, section_four=37)
        result = run("--file", self.target, "acquire", "--who", "A",
                      "--reserve-multi", "一:2", "四:1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("§一 #169", result.stdout)
        self.assertIn("§一 #170", result.stdout)
        self.assertIn("§四 #38", result.stdout)

        final_text = Path(self.target).read_text(encoding="utf-8")
        self.assertIn("编号高水位线：§一 #170 ｜ §四 #38", final_text)

        lock = json.loads(self.lock_path.read_text(encoding="utf-8"))
        self.assertEqual(lock["reserved"], {"一": [169, 170], "四": [38]})

    def test_reserve_multi_rejects_when_combined_with_single_reserve(self):
        self._write_queue()
        result = run("--file", self.target, "acquire", "--who", "A",
                      "--reserve", "1", "--section", "一", "--reserve-multi", "四:1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不能与", result.stdout)
        self.assertFalse(self.lock_path.exists(), "参数校验失败不应连锁文件都创建")

    def test_reserve_multi_rejects_malformed_token(self):
        self._write_queue()
        result = run("--file", self.target, "acquire", "--who", "A",
                      "--reserve-multi", "一2")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.lock_path.exists())

    def test_reserve_multi_rejects_unknown_section(self):
        self._write_queue()
        result = run("--file", self.target, "acquire", "--who", "A",
                      "--reserve-multi", "五:1")
        self.assertNotEqual(result.returncode, 0)

    def test_reserve_multi_rejects_duplicate_section(self):
        self._write_queue()
        result = run("--file", self.target, "acquire", "--who", "A",
                      "--reserve-multi", "一:1", "一:2")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("重复", result.stdout)

    def test_reserve_multi_partial_failure_rolls_back_and_keeps_first_section_advance(self):
        """第二个分区因高水位线行格式漂移而预留失败——整体回滚（锁被
        释放），但第一个分区已成功推进的高水位线不回退（协议〇.8：允许
        留空洞）。"""
        Path(self.target).write_text(
            "> **编号高水位线：§一 #168 ｜ §四 格式已变**（说明文字）\n\n"
            "## 一、任务看板\n\n"
            "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
            "|---|------|--------|-------------|----------|------|--------|------|\n",
            encoding="utf-8",
        )
        result = run("--file", self.target, "acquire", "--who", "A",
                      "--reserve-multi", "一:2", "四:1")
        self.assertNotEqual(result.returncode, 0)

        final_text = Path(self.target).read_text(encoding="utf-8")
        self.assertIn("§一 #170", final_text)  # 168+2，第一分区已推进、不回退

        marker = json.loads(self.lock_path.read_text(encoding="utf-8"))
        self.assertTrue(marker.get("released"), "回滚后锁应已释放，不留半成品锁")

    def test_reserve_collision_with_live_row_blocks_reserve(self):
        """队列 #185 竞态防护：若高水位线滞后于文件实际内容（如绕锁直写
        了一行新编号但没同步推高水位线，见 #200），reserve 应拒绝而不是
        静默分配一个已被占用的号。"""
        self._write_queue(
            section_one=149,
            section_one_rows="| 150 | 绕锁直写的行 | 某人 | 指针 | 产出 | 待领 | 触碰区 | 2026-08-04 |\n",
        )
        result = run("--file", self.target, "acquire", "--who", "A",
                      "--reserve", "1", "--section", "一")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("已存在于当前文件", result.stdout)
        # 高水位线不应被推进——拒绝发生在写回之前。
        final_text = Path(self.target).read_text(encoding="utf-8")
        self.assertIn("§一 #149", final_text)
        # 且不留半成品锁。
        marker = json.loads(self.lock_path.read_text(encoding="utf-8"))
        self.assertTrue(marker.get("released"))

    def test_reserve_no_collision_when_no_live_row_conflicts(self):
        """反向对照：高水位线领先于所有可见行号（正常情形）——预留照常
        成功，新加的这一处校验不应误伤既有用法。"""
        self._write_queue(
            section_one=200,
            section_one_rows="| 150 | 历史已完成行 | 某人 | 指针 | 产出 | ✅ 已完成 | 触碰区 | 2026-07-01 |\n",
        )
        result = run("--file", self.target, "acquire", "--who", "A",
                      "--reserve", "1", "--section", "一")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("§一 #201", result.stdout)


class BypassDetectionTests(unittest.TestCase):
    """队列 #200：绕过锁直接改写目标文件的检测机制（通用，任意 --file
    均生效）。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.target = str(Path(self._tmpdir.name) / "假想队列.md")
        self.lock_path = Path(self.target + ".editlock")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_first_ever_release_writes_lastknown_without_warning(self):
        Path(self.target).write_text("初始内容\n", encoding="utf-8")
        acquire_result = run("--file", self.target, "acquire", "--who", "A")
        self.assertEqual(acquire_result.returncode, 0, acquire_result.stdout)
        self.assertNotIn("绕过", acquire_result.stdout)

        result = run("--file", self.target, "release", "--who", "A")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        lastknown_path = Path(self.target + ".editlock.lastknown")
        self.assertTrue(lastknown_path.exists())
        self.assertEqual(lastknown_path.read_text(encoding="utf-8"), "初始内容\n")

    def test_no_warning_when_content_unchanged_between_release_and_acquire(self):
        Path(self.target).write_text("内容\n", encoding="utf-8")
        run("--file", self.target, "acquire", "--who", "A")
        run("--file", self.target, "release", "--who", "A")

        result = run("--file", self.target, "acquire", "--who", "B")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("绕过", result.stdout)

    def test_bypass_edit_between_release_and_acquire_is_detected(self):
        Path(self.target).write_text("原始内容\n", encoding="utf-8")
        run("--file", self.target, "acquire", "--who", "A")
        run("--file", self.target, "release", "--who", "A")

        # 模拟绕过锁直接改写（不经 acquire）。
        Path(self.target).write_text("原始内容\n绕锁写入的新行\n", encoding="utf-8")

        result = run("--file", self.target, "acquire", "--who", "B")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)  # 不阻断，仅回显
        self.assertIn("绕过协议〇.7", result.stdout)
        self.assertIn("1→2 行", result.stdout)

    def test_legitimate_reserve_release_acquire_cycle_shows_no_warning(self):
        """正常经工具完成的 acquire→reserve→release 循环（含高水位线行被
        自身改写）不应触发误报。"""
        Path(self.target).write_text(
            "> **编号高水位线：§一 #10 ｜ §四 #1**（说明）\n\n"
            "## 一、任务看板\n\n"
            "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
            "|---|------|--------|-------------|----------|------|--------|------|\n",
            encoding="utf-8",
        )
        run("--file", self.target, "acquire", "--who", "A", "--reserve", "1", "--section", "一")
        run("--file", self.target, "release", "--who", "A")

        result = run("--file", self.target, "acquire", "--who", "B")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("绕过", result.stdout)

    def test_stale_lock_takeover_also_checks_bypass(self):
        """陈旧锁被接管时同样跑绕锁检测——不局限于"全新锁"路径。"""
        Path(self.target).write_text("原始内容\n", encoding="utf-8")
        run("--file", self.target, "acquire", "--who", "A")
        run("--file", self.target, "release", "--who", "A")
        Path(self.target).write_text("原始内容\n绕锁写入\n", encoding="utf-8")

        # 手工构造一把陈旧锁（模拟"有人 acquire 后异常退出，从未 release"）。
        stale_since = (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat()
        self.lock_path.write_text(
            json.dumps({"who": "STALE", "note": "", "held_since": stale_since}),
            encoding="utf-8",
        )

        result = run("--file", self.target, "acquire", "--who", "B")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("陈旧", result.stdout)
        self.assertIn("绕过协议〇.7", result.stdout)


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
        # release 改写标记而非 unlink（#121(a)）：锁文件仍在主工作区那一份，
        # 但应已是 released 标记——从 linked worktree 里再 acquire 应立即成功。
        lock_path = self.main_root / "queue.md.editlock"
        self.assertTrue(lock_path.exists())
        self.assertTrue(json.loads(lock_path.read_text(encoding="utf-8")).get("released"))
        r2 = run_at(self._tool(self.linked_root), "--file", "queue.md",
                    "acquire", "--who", "B")
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)


class RecentAcquireHistoryTests(unittest.TestCase):
    """队列 #230-1c：acquire 成功时回显"最近 120 分钟内还有哪些其它身份
    acquire 过本锁"（纯回显，复用 `.editlock` 自身的 history 字段，零新增
    状态文件）。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.target = str(Path(self._tmpdir.name) / "假想队列.md")
        self.lock_path = Path(self.target + ".editlock")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_first_ever_acquire_has_no_recent_others(self):
        result = run("--file", self.target, "acquire", "--who", "A")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("其它身份", result.stdout)

    def test_recent_acquirer_within_window_is_echoed(self):
        run("--file", self.target, "acquire", "--who", "Cowork-财务专线", "--note", "登记#1")
        run("--file", self.target, "release", "--who", "Cowork-财务专线")

        result = run("--file", self.target, "acquire", "--who", "CC-QD-B")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("120 分钟内还有其它身份", result.stdout)
        self.assertIn("Cowork-财务专线", result.stdout)

    def test_acquirer_outside_window_is_not_echoed(self):
        run("--file", self.target, "acquire", "--who", "A")
        run("--file", self.target, "release", "--who", "A")
        # 直接改写历史时间戳到 121 分钟前，模拟"很久以前来过"。
        data = json.loads(self.lock_path.read_text(encoding="utf-8"))
        stale_at = (datetime.now(timezone.utc) - timedelta(minutes=121)).isoformat()
        data["history"] = [{"who": "A", "note": "", "at": stale_at}]
        self.lock_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        result = run("--file", self.target, "acquire", "--who", "B")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("其它身份", result.stdout)

    def test_history_survives_stale_lock_takeover(self):
        """陈旧锁被接管时，历史记录不应丢失——下一位调用者仍应看到更早
        之前的在场者，不因"接管"这个动作而清空记忆。"""
        self._write_lock_with_history("A", minutes_ago=31, history=[
            {"who": "PRIOR", "note": "", "at": (
                datetime.now(timezone.utc) - timedelta(minutes=60)
            ).isoformat()},
        ])
        result = run("--file", self.target, "acquire", "--who", "B")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PRIOR", result.stdout)

    def test_reserve_failure_rollback_still_records_history(self):
        """预留失败回滚（acquire 整体失败）也应把这次尝试计入历史——本人
        确实在这个时刻出现过，即便最终没能真正持锁。"""
        Path(self.target).write_text("没有高水位线这一行\n", encoding="utf-8")
        result = run("--file", self.target, "acquire", "--who", "A",
                      "--reserve", "1", "--section", "一")
        self.assertNotEqual(result.returncode, 0)
        history = json.loads(self.lock_path.read_text(encoding="utf-8")).get("history")
        self.assertTrue(history)
        self.assertEqual(history[-1]["who"], "A")

    def _write_lock_with_history(self, who: str, minutes_ago: float, history: list) -> None:
        held_since = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        self.lock_path.write_text(
            json.dumps({
                "who": who, "note": "", "held_since": held_since.isoformat(),
                "history": history,
            }, ensure_ascii=False),
            encoding="utf-8",
        )


class StatusDomainFieldParsingTests(unittest.TestCase):
    """队列 #308 决策点 1/2/6：状态机器字段/域字段解析与措施 C 计数——纯
    函数级白盒用例，不涉及 acquire/release 锁流程。"""

    def setUp(self):
        self.module = _load_module()

    def test_all_six_status_values_parse(self):
        for value in ("done", "open", "partial", "hold", "blocked"):
            with self.subTest(value=value):
                status, domain, rest = self.module._parse_status_domain_fields(
                    f"[S:{value}] 一些正文"
                )
                self.assertEqual(status, value)
                self.assertIsNone(domain)
                self.assertEqual(rest, " 一些正文")

    def test_timed_value_with_date_parses(self):
        status, domain, rest = self.module._parse_status_domain_fields(
            "[S:timed=2026-08-25] 定时触发型，日期未到"
        )
        self.assertEqual(status, "timed=2026-08-25")
        self.assertIsNone(domain)
        self.assertEqual(rest, " 定时触发型，日期未到")

    def test_status_and_domain_fields_together(self):
        status, domain, rest = self.module._parse_status_domain_fields(
            "[S:open][D:机] 待领（P1）"
        )
        self.assertEqual(status, "open")
        self.assertEqual(domain, "机")
        self.assertEqual(rest, " 待领（P1）")

    def test_domain_business_value_parses(self):
        _, domain, _ = self.module._parse_status_domain_fields("[S:partial][D:业] 在办中")
        self.assertEqual(domain, "业")

    def test_missing_field_returns_none_none_original_text(self):
        """字段缺失——不得静默假定某个默认状态，返回 (None, None, 原文)。"""
        original = "待领（P1，历史遗留行，尚未回填机器字段）"
        status, domain, rest = self.module._parse_status_domain_fields(original)
        self.assertIsNone(status)
        self.assertIsNone(domain)
        self.assertEqual(rest, original)

    def test_malformed_status_value_returns_none(self):
        """取值集合外的值（如中文枚举、拼写错误）不匹配语法，视同缺失。"""
        status, domain, rest = self.module._parse_status_domain_fields("[S:已完成] 正文")
        self.assertIsNone(status)
        self.assertIsNone(domain)

    def test_leading_whitespace_before_field_stripped(self):
        status, domain, _ = self.module._parse_status_domain_fields("  [S:done][D:机] 正文")
        self.assertEqual(status, "done")
        self.assertEqual(domain, "机")

    def test_count_mechanism_wip_counts_open_partial_hold_with_domain_ji(self):
        section = (
            "| 1 | 任务A | CC | 指针 | 产出 | [S:open][D:机] 待领 | 触碰区 | 登记 |\n"
            "| 2 | 任务B | CC | 指针 | 产出 | [S:partial][D:机] 在办 | 触碰区 | 登记 |\n"
            "| 3 | 任务C | CC | 指针 | 产出 | [S:hold][D:机] 暂缓 | 触碰区 | 登记 |\n"
        )
        count, degraded = self.module._count_mechanism_wip(section)
        self.assertEqual(count, 3)
        self.assertEqual(degraded, [])

    def test_count_mechanism_wip_excludes_blocked_timed_done(self):
        section = (
            "| 1 | 任务A | CC | 指针 | 产出 | [S:blocked][D:机] 等专员签认 | 触碰区 | 登记 |\n"
            "| 2 | 任务B | CC | 指针 | 产出 | [S:timed=2026-09-01][D:机] 定时触发 | 触碰区 | 登记 |\n"
            "| 3 | 任务C | CC | 指针 | 产出 | [S:done][D:机] 已完成 | 触碰区 | 登记 |\n"
        )
        count, degraded = self.module._count_mechanism_wip(section)
        self.assertEqual(count, 0)

    def test_count_mechanism_wip_excludes_business_domain(self):
        section = "| 1 | 任务A | CC | 指针 | 产出 | [S:open][D:业] 待领 | 触碰区 | 登记 |\n"
        count, _ = self.module._count_mechanism_wip(section)
        self.assertEqual(count, 0)

    def test_count_mechanism_wip_excludes_stop_marker_rows(self):
        """🛑（永久关闭·仅手动唤醒）与状态字段正交——即便 [S:open][D:机]，
        自然语言正文以 🛑 开头即不计入可动 WIP。"""
        section = "| 1 | 任务A | CC | 指针 | 产出 | [S:open][D:机] 🛑 永久关闭，仅手动唤醒 | 触碰区 | 登记 |\n"
        count, _ = self.module._count_mechanism_wip(section)
        self.assertEqual(count, 0)

    def test_count_mechanism_wip_missing_field_degrades_not_silently(self):
        section = "| 1 | 任务A | CC | 指针 | 产出 | 待领（未回填机器字段的历史行） | 触碰区 | 登记 |\n"
        count, degraded = self.module._count_mechanism_wip(section)
        self.assertEqual(count, 0)
        self.assertEqual(len(degraded), 1)
        self.assertIn("#1", degraded[0])
        self.assertIn("非静默降级", degraded[0])


class QueueWriteRootFixTests(unittest.TestCase):
    """队列 #414：队列写入根治——三条修复面各配反例。

    每条用例都能对**旧实现**变红，这是派单件 A4 明确的验收条件：
      - **A（正文不进 argv）**：`--cells-json`/`--stdin-json` 此前不存在，
        含反引号/`$()` 的正文只能经 argv，由 bash 决定它是不是命令。
      - **B（守卫覆盖所有入口）**：关键格哨兵此前完全没有——列位错置时
        格数是对的，旧实现一路放行（#412 真实事故）。
      - **C（按列名）**：`--set`/`edit-row` 此前不存在，调用方必须自己数
        `split` 后的下标。
    """

    SECTION_ONE_HEADER = (
        "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|------|--------|-------------|----------|------|--------|------|\n"
    )
    EXISTING_ROW = (
        "| 500 | 既有任务 | 待领（CC） | 指针 | 产出 | [S:open][D:机] 在办 | 区域 | 2026-08-26 |\n"
    )

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.target = self.root / "toy-queue.md"
        self.target.write_text(
            "# 玩具队列\n\n## 一、任务看板\n\n" + self.SECTION_ONE_HEADER + self.EXISTING_ROW +
            "\n## 二、待 commit 批次\n\n| 批次 | 文件清单 | 建议 message | 状态 |\n|---|---|---|---|\n"
            "\n## 四、需 Shao Peishen 的动作\n\n| # | 事项 | 等谁 | 截止 |\n|---|---|---|---|\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def _run(self, *args: str, stdin: str | None = None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--file", str(self.target), *args],
            capture_output=True, text=True, encoding="utf-8", input=stdin,
        )

    def _row(self, number: str) -> str | None:
        for line in self.target.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"| {number} |"):
                return line
        return None

    def _cells(self, number: str) -> list[str]:
        return [c.strip() for c in (self._row(number) or "").strip().strip("|").split("|")]

    # ---------- 修复面 A：正文不再经过 shell ----------

    def test_cells_json_keeps_backticks_and_dollar_parens_verbatim(self):
        """反引号与 `$()` 原样落地——这正是 2026-08-25/26 两次事故的字符。"""
        payload = {
            "任务": "修 `工具-共享文档编辑锁.py` 里的 $(whoami) 与 `git worktree list`",
            "领取方": "待领（CC）", "输入（指针）": "`0-学习与工具/`", "期望产出": "产出",
            "状态": "[S:open][D:机] 新立", "触碰区": "`queue_table.py`", "登记": "2026-08-26",
        }
        jf = self.root / "cells.json"
        jf.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        r = self._run("append-row", "--section", "一", "--number", "501",
                      "--cells-json", str(jf))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        cells = self._cells("501")
        self.assertEqual(cells[1], payload["任务"])
        self.assertIn("$(whoami)", cells[1])

    def test_stdin_json_equivalent_to_cells_json(self):
        payload = ["任务", "待领（CC）", "指针", "产出", "[S:open][D:机] x", "区", "2026-08-26"]
        r = self._run("append-row", "--section", "一", "--number", "502", "--stdin-json",
                      stdin=json.dumps(payload, ensure_ascii=False))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIsNotNone(self._row("502"))

    def test_multiple_cell_inputs_rejected_rather_than_silently_picked(self):
        r = self._run("append-row", "--section", "一", "--number", "503",
                      "--cell", "x", "--set", "任务=y")
        self.assertEqual(r.returncode, 1)
        self.assertIn("只能用一个", r.stdout)

    # ---------- 修复面 C：按列名，调用方永不数下标 ----------

    def test_set_by_column_name_lands_in_right_columns_regardless_of_order(self):
        r = self._run(
            "append-row", "--section", "一", "--number", "504",
            "--set", "触碰区=区域乙", "--set", "状态=[S:open][D:机] 由列名写入",
            "--set", "任务=任务甲", "--set", "登记=2026-08-26",
            "--set", "领取方=待领（CC）", "--set", "输入指针=指针丙",
            "--set", "期望产出=产出丁",
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        cells = self._cells("504")
        self.assertEqual(len(cells), 8)
        self.assertEqual(cells[1], "任务甲")
        self.assertEqual(cells[6], "区域乙")
        self.assertTrue(cells[5].startswith("[S:open]"))

    def test_unknown_column_name_fails_loud_and_lists_legal_names(self):
        r = self._run("append-row", "--section", "一", "--number", "505", "--set", "状況=x")
        self.assertEqual(r.returncode, 1)
        self.assertIn("合法列名", r.stdout)

    def test_missing_column_is_not_silently_filled_with_blank(self):
        r = self._run("append-row", "--section", "一", "--number", "506", "--set", "任务=只给一列")
        self.assertEqual(r.returncode, 1)
        self.assertIn("缺少这些列", r.stdout)
        self.assertIsNone(self._row("506"))

    def test_edit_row_append_touches_only_named_column(self):
        r = self._run("edit-row", "--section", "一", "--number", "500",
                      "--append", "状态=✅ 已完成（2026-08-26）")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        cells = self._cells("500")
        self.assertEqual(len(cells), 8)
        self.assertTrue(cells[5].startswith("[S:open][D:机] 在办"))
        self.assertIn("✅ 已完成", cells[5])
        self.assertEqual(cells[1], "既有任务", "其余格不得被动到")

    def test_edit_row_changes_json_flips_status_prefix_without_argv(self):
        """🔴 **翻转 `[S:xxx]` 前缀必须整格重写**（`--append` 只能加尾巴），
        而真实队列行的状态格动辄数千字、密集使用反引号 ⇒ 只能走 JSON 入口。
        本用例即 2026-08-26 回写 #414 时实测撞上的那个缺口。"""
        payload = {
            "set": {"状态": "[S:done][D:机] ✅ 已完成 —— 含 `路径/` 与 $(whoami)"},
            "append": {"触碰区": "、`queue_table.py`"},
        }
        jf = self.root / "changes.json"
        jf.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        r = self._run("edit-row", "--section", "一", "--number", "500",
                      "--changes-json", str(jf), "--append-sep", "")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        cells = self._cells("500")
        self.assertEqual(len(cells), 8)
        self.assertTrue(cells[5].startswith("[S:done]"))
        self.assertIn("$(whoami)", cells[5], "正文不得经 shell 求值")
        self.assertEqual(cells[6], "区域、`queue_table.py`")

    def test_edit_row_result_still_subject_to_key_cell_sentinels(self):
        """反例：改动后若状态格丢了机器字段，必须被拦下且**不写文件**。"""
        jf = self.root / "bad.json"
        jf.write_text(json.dumps({"set": {"状态": "已完成，但忘了机器字段"}},
                                 ensure_ascii=False), encoding="utf-8")
        r = self._run("edit-row", "--section", "一", "--number", "500",
                      "--changes-json", str(jf))
        self.assertEqual(r.returncode, 1)
        self.assertTrue(self._cells("500")[5].startswith("[S:open]"),
                        "拒绝时不得修改目标文件")

    def test_edit_row_same_column_in_both_json_and_flag_fails_loud(self):
        jf = self.root / "dup.json"
        jf.write_text(json.dumps({"set": {"状态": "[S:done][D:机] x"}},
                                 ensure_ascii=False), encoding="utf-8")
        r = self._run("edit-row", "--section", "一", "--number", "500",
                      "--changes-json", str(jf), "--set", "状态=[S:done][D:机] y")
        self.assertEqual(r.returncode, 1)
        self.assertIn("各出现一次", r.stdout)

    def test_edit_row_on_missing_number_fails_loud(self):
        r = self._run("edit-row", "--section", "一", "--number", "999",
                      "--set", "状态=[S:open][D:机] x")
        self.assertEqual(r.returncode, 1)
        self.assertIn("找不到编号", r.stdout)

    # ---------- 修复面 B：关键格哨兵（列位错置唯一会留下的痕迹） ----------

    def test_status_cell_without_machine_field_is_rejected(self):
        r = self._run("append-row", "--section", "一", "--number", "507",
                      *self._positional("任务", "待领（CC）", "指针", "产出",
                                        "在办但没有机器字段", "区", "2026-08-26"))
        self.assertEqual(r.returncode, 1)
        self.assertIsNone(self._row("507"))

    def test_done_marker_landing_in_product_column_is_rejected(self):
        """#412 真实形态：「✅ 已完成…」被写进期望产出格，而状态列仍 [S:open]
        ⇒ 机器读状态列，一直认为该任务没做完。旧实现完全放行。"""
        r = self._run("append-row", "--section", "一", "--number", "508",
                      *self._positional("任务", "待领（CC）", "指针",
                                        "✅ 已完成（2026-08-26）",
                                        "[S:open][D:机] 在办", "区", "2026-08-26"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("期望产出", r.stdout)
        self.assertIsNone(self._row("508"))

    def test_non_numeric_row_number_is_rejected_as_broken_head(self):
        r = self._run("append-row", "--section", "一", "--number", "不是数字",
                      *self._positional("任务", "待领（CC）", "指针", "产出",
                                        "[S:open][D:机] x", "区", "2026-08-26"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("行头断裂", r.stdout)

    def test_newline_inside_cell_is_rejected(self):
        """2026-08-25 事故形态：25 行 `git worktree list` 输出被注入进一个格。"""
        jf = self.root / "nl.json"
        jf.write_text(json.dumps({
            "任务": "worktree 列表\n第二行\n第三行", "领取方": "待领（CC）",
            "输入（指针）": "指针", "期望产出": "产出", "状态": "[S:open][D:机] x",
            "触碰区": "区", "登记": "2026-08-26"}, ensure_ascii=False), encoding="utf-8")
        r = self._run("append-row", "--section", "一", "--number", "509",
                      "--cells-json", str(jf))
        self.assertEqual(r.returncode, 1)
        self.assertIn("换行", r.stdout)
        self.assertIsNone(self._row("509"))

    def test_bare_pipe_still_rejected_on_write_side(self):
        """既有语义不放宽：写侧竖线一律拒绝，反引号包裹亦不豁免。"""
        r = self._run("append-row", "--section", "一", "--number", "510",
                      *self._positional("任务|撑列", "待领（CC）", "指针", "产出",
                                        "[S:open][D:机] x", "区", "2026-08-26"))
        self.assertEqual(r.returncode, 1)
        self.assertIsNone(self._row("510"))

    @staticmethod
    def _positional(*cells: str) -> list[str]:
        out: list[str] = []
        for c in cells:
            out.extend(["--cell", c])
        return out


class ReleaseStructuralValidationTests(unittest.TestCase):
    """队列 #225：release 时对跨桌任务队列.md 的四项结构校验。

    白盒方式：用 `_load_module()` 加载独立模块实例，monkeypatch
    `REPO_ROOT`/`DEFAULT_TARGET` 指向本用例专属临时目录——不能像其它用例
    那样用任意 `--file` 走黑盒子进程：结构校验只在 `args.file ==
    DEFAULT_TARGET` 时生效，而生产脚本里 DEFAULT_TARGET 是真实项目队列
    文件的相对路径，子进程黑盒调用会解到真实 REPO_ROOT、误触真实队列锁。
    """

    SECTION_ONE_HEADER = (
        "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|------|--------|-------------|----------|------|--------|------|\n"
    )
    SECTION_FOUR_HEADER = (
        "| # | 事项 | 等谁 | 截止 |\n"
        "|---|------|------|------|\n"
    )
    SECTION_TWO_HEADER = (
        "| 批次 | 文件清单 | 建议 message | 状态 |\n"
        "|------|---------|--------------|------|\n"
    )

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmpdir.name)
        self.module = _load_module()
        self.module.REPO_ROOT = self.repo_root
        self.module.DEFAULT_TARGET = "queue.md"
        # 队列 #315：既有用例把 §一/§二/§三/§四 全部写在同一份 "queue.md"
        # 里——本模块拆分后的"队列系统模式"会遍历机制/业务两份文件，这里
        # 让机制文件复用既有单文件、业务文件指向一份本用例内不存在的路径
        # （`_read_target_text` 对不存在的文件返回空串，不视为错误），使
        # 大量既有单文件用例不必逐个改写即可继续验证原有行为；需要真实
        # 验证双文件路由的用例另行覆盖这两个值。
        self.module.QUEUE_MECHANISM_PATH_REL = "queue.md"
        self.module.QUEUE_BUSINESS_PATH_REL = "queue-business.md"
        self.module.QUEUE_LOCK_ANCHOR = "queue.md"
        self.target_path = self.repo_root / "queue.md"

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write_queue(self, section_one_rows="", section_two_rows="", section_four_rows="",
                      hwm_one=200, hwm_four=40):
        text = (
            f"> **编号高水位线：§一 #{hwm_one} ｜ §四 #{hwm_four}**（说明文字）\n\n"
            "## 一、任务看板\n\n" + self.SECTION_ONE_HEADER + section_one_rows +
            "\n## 二、待 commit 批次（CC 取活销行）\n\n" + section_two_rows +
            self.SECTION_TWO_HEADER +
            "\n## 三、口径冻结标（重梳期防在途建造撞车）\n\n"
            "| 域/场景 | 冻结原因 | 挂标 | 解除条件 |\n"
            "|---------|---------|------|---------|\n"
            "\n## 四、需 Shao Peishen 的动作（例外与拍板）\n\n" +
            self.SECTION_FOUR_HEADER + section_four_rows
        )
        self.target_path.write_text(text, encoding="utf-8")

    def _acquire(self, who="A", reserve=None, section=None, reserve_multi=None, domain=None):
        ns = argparse.Namespace(
            file=self.module.DEFAULT_TARGET, who=who, note="",
            reserve=reserve, section=section, reserve_multi=reserve_multi, domain=domain,
        )
        return self.module.cmd_acquire(ns)

    def _release(self, who="", mechanism_wip_cap=None, force_mechanism_wip=False):
        ns = argparse.Namespace(
            file=self.module.DEFAULT_TARGET, who=who,
            mechanism_wip_cap=(
                mechanism_wip_cap if mechanism_wip_cap is not None
                else self.module.MECHANISM_WIP_CAP_DEFAULT
            ),
            force_mechanism_wip=force_mechanism_wip,
        )
        return self.module.cmd_release(ns)

    # ---------------- 队列 #414 A3-2：release 对"自愈"的出口 ----------------
    #
    # 死锁形态（2026-08-26 实测）：acquire 取快照那一刻某行行头是断的，
    # **快照解析不出它的编号**；持锁期间修好之后，release 看到一个"快照里
    # 没有、现在有"的编号 ⇒ 判为凭空新增、未经 --reserve 预留 ⇒ 拒绝释放；
    # 而此时 acquire 又被自己那把锁挡住 ⇒ 只能等 30 分钟自动陈旧。

    _BROKEN_HEAD_ROW = "|  | 破损行 | CC | 指针 | 产出 | [S:open][D:机] 在办 | 区 | 2026-08-26 |\n"
    _REPAIRED_ROW = "| 101 | 破损行 | CC | 指针 | 产出 | [S:open][D:机] 在办 | 区 | 2026-08-26 |\n"

    def _git(self, *args: str):
        return subprocess.run(["git", *args], cwd=self.repo_root,
                              capture_output=True, text=True, encoding="utf-8")

    def _make_git_repo_with_committed_queue(self, rows: str):
        """把 repo_root 变成真 git 仓库，并把给定队列内容提交进 HEAD。"""
        self._git("init", "-q")
        self._git("config", "user.email", "t@example.com")
        self._git("config", "user.name", "t")
        self._write_queue(section_one_rows=rows)
        self._git("add", "-A")
        self._git("commit", "-qm", "baseline")

    def test_repairing_broken_row_head_does_not_deadlock_release(self):
        """#414 A3-2：修好一条行头断裂的**既有**行后，release 必须能放行。

        反例价值：去掉 HEAD 存在性豁免时本用例变红（已实测——见同名判据在
        `_head_row_numbers` 上方的长注释）。
        """
        self._make_git_repo_with_committed_queue(self._REPAIRED_ROW)
        # 现场：#101 此刻行头断裂（编号格被清空）——快照将解析不出它
        self._write_queue(section_one_rows=self._BROKEN_HEAD_ROW)
        self.assertEqual(self._acquire(who="A"), 0)
        # 持锁期间把它修好
        self._write_queue(section_one_rows=self._REPAIRED_ROW)
        self.assertEqual(
            self._release(who="A"), 0,
            "修复一条 HEAD 里本就存在的行，不应被当成『未预留的新增行』拒绝",
        )

    def test_genuinely_new_unreserved_row_still_blocked_in_git_repo(self):
        """🔴 **配套反例：豁免不得把它本要守的东西一并放过。**

        同样在 git 仓库里，但这次是一条 HEAD 里**根本不存在**的新编号且未
        `--reserve` ⇒ 必须照旧拒绝。没有这一条，上面那个用例无法区分
        "豁免生效"与"整项校验被我改废了"。
        """
        self._make_git_repo_with_committed_queue("")
        self._write_queue(
            section_one_rows="| 201 | 凭空新增 | CC | 指针 | 产出 | "
                             "[S:open][D:机] 待领 | 区 | 2026-08-26 |\n")
        self.assertEqual(self._acquire(who="A"), 0)
        self.assertNotEqual(
            self._release(who="A"), 0,
            "HEAD 里不存在且未预留的新行，必须仍被③预留归属校验拒绝",
        )

    def test_aibot_registration_exemption_does_not_cover_other_checks(self):
        """🔴 **反例（队列 #416 ⑶ tasks 2.3）：⑹ 的身份豁免只作用于 ⑹。**

        场景刻意做成"⑹ 本会放行、①会拦"：真 git 仓库 ＋ 工作区有未登记脏
        文件（⑹ 的触发条件已满足，机器人身份下被豁免），同时机器人写下的
        行**列数不对** ⇒ release 必须仍被拒。豁免一旦滑成"机器人整体免检"，
        本用例变红。
        """
        self._make_git_repo_with_committed_queue("")
        (self.repo_root / "别的会话正在改的方案件.md").write_text("脏", encoding="utf-8")
        self.assertEqual(self._acquire(who=self.module.AIBOT_LOCK_WHO), 0)
        self._write_queue(
            section_one_rows=f"| 203 | {self.module.AIBOT_INTAKE_TASK_PREFIX}某回件 | "
                             f"CC | 指针 | 产出 | [S:open][D:机] 待领 |\n")  # 6 列，应为 8
        self.assertNotEqual(
            self._release(who=self.module.AIBOT_LOCK_WHO), 0,
            "①列数校验对机器人照常生效——⑹ 的豁免不得外溢成整体免检",
        )

    def test_reserve_waiver_marker_releases_when_head_unreadable(self):
        """HEAD 也读不到时（破损在 HEAD 里就已存在／不在 git 工作树内），
        行内逃生阀 `预留豁免：<理由>` 放行并留痕——完全复用 `WIP豁免：`
        既有范式，不新增写盘路径。"""
        self._write_queue(section_one_rows="")  # 非 git 仓库 ⇒ 读不到 HEAD 基线
        self.assertEqual(self._acquire(who="A"), 0)
        self._write_queue(
            section_one_rows="| 202 | 修复破损行 | CC | 指针 | 产出 | "
                             "[S:open][D:机] 预留豁免：修复 HEAD 里即已破损的行 | "
                             "区 | 2026-08-26 |\n")
        self.assertEqual(
            self._release(who="A"), 0,
            "行内写了 预留豁免：<理由> 应放行（并随行留痕，可 grep 计数）",
        )

    def test_reserve_waiver_absent_without_git_still_blocks(self):
        """不在 git 工作树内、又没写逃生阀标记 ⇒ 仍拒绝（否则"读不到 HEAD"
        就成了一个人人可用的静默后门）。"""
        self._write_queue(section_one_rows="")
        self.assertEqual(self._acquire(who="A"), 0)
        self._write_queue(
            section_one_rows="| 203 | 无标记新增 | CC | 指针 | 产出 | "
                             "[S:open][D:机] 待领 | 区 | 2026-08-26 |\n")
        self.assertNotEqual(self._release(who="A"), 0)

    def test_release_succeeds_with_no_changes(self):
        self._write_queue()
        self.assertEqual(self._acquire(who="A"), 0)
        self.assertEqual(self._release(who="A"), 0)

    def test_new_well_formed_reserved_row_passes(self):
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        new_row = "| 201 | 测试任务 | CC | 指针 | 产出 | 待领 | 触碰区 | 2026-08-04 |\n"
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        self.assertEqual(self._release(who="A"), 0)

    def test_column_count_mismatch_blocks_release(self):
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        # 少一列（7 列，缺"登记"）。
        malformed_row = "| 201 | 测试任务 | CC | 指针 | 产出 | 待领 | 触碰区 |\n"
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + malformed_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        result = self._release(who="A")
        self.assertNotEqual(result, 0)
        # 锁应保持占用，不因校验失败而被释放。
        self.assertFalse(json.loads((self.repo_root / "queue.md.editlock").read_text(
            encoding="utf-8")).get("released"))

    def test_pipe_inside_backtick_no_longer_causes_column_mismatch(self):
        """队列 #314（openspec 变更包 `queue-table-backtick-aware-split`）：
        反引号跨度内的竖线不再被当作列分隔符，行为与本用例改造前（#164
        同族形态，曾断言"反引号内裸竖线致列数偏移，应被①拦下"）相反——
        这是本变更 proposal.md 明写的 BREAKING 行为修正，不是新缺陷。
        真正的裸竖线（不在反引号内）仍须被拦下，见
        `test_bare_pipe_outside_backtick_still_causes_column_mismatch`。"""
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        row = (
            "| 201 | 测试任务 `a|b` | CC | 指针 | 产出 | 待领 | 触碰区 | 2026-08-04 |\n"
        )
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        self.assertEqual(self._release(who="A"), 0)

    def test_bare_pipe_outside_backtick_still_causes_column_mismatch(self):
        """#164 原始形态：反引号外的裸竖线仍是真实撑列，须被①拦下——
        反引号感知只保护跨度内的竖线，不豁免跨度外的。"""
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        bad_row = (
            "| 201 | 测试任务 a|b（不在反引号内） | CC | 指针 | 产出 | 待领 | 触碰区 | 2026-08-04 |\n"
        )
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + bad_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        self.assertNotEqual(self._release(who="A"), 0)

    def test_new_batch_without_declaring_queue_file_itself_no_longer_blocks(self):
        """校验②「§二 新增批次行的文件清单须含队列文件自身路径」**已于
        2026-08-23 退休**（协议〇.9 措施 B 一进一出，openspec 变更包
        `editlock-chokepoint-six-fixes`）。本用例**是就地改判、不是删除**——
        留一条会跑的用例，比一个消失的用例更能让下一位读者知道这里发生过
        什么：② 曾经存在、为什么退、退了之后这条路径的行为是什么。

        退休依据：② 是个**代理判据**（"每条新批次行都得把队列文件写进自己
        的清单"），而同批新增的 ⑹ 直接度量它真正想保证的那件事——"全部脏
        文件都须被某个待处理 §二 批次覆盖"，覆盖面严格更大。② 残余的额外
        严格性（拒绝"新批次行只列代码文件、而队列文件已被另一条既有待处理
        批次覆盖"）拦的是一个不存在的问题。

        ⚠️ **代价如实记在这里**：② 没有逃生阀，⑹ 有（`登记豁免：`）⇒ 写了
        豁免的 session 同时也不再受 ② 约束。这是一次实质放松。
        """
        self.assertEqual(self._acquire(who="A"), 0)
        self._write_queue(section_two_rows=(
            "| B-TEST | `docs/某个文件.md` | `docs(test): 测试` | 待处理 |\n"
        ))

        self.assertEqual(self._release(who="A"), 0)

    def test_new_batch_declaring_queue_file_itself_passes(self):
        self.assertEqual(self._acquire(who="A"), 0)
        self._write_queue(section_two_rows=(
            "| B-TEST | `docs/某个文件.md`、`queue.md` | `docs(test): 测试` | 待处理 |\n"
        ))

        self.assertEqual(self._release(who="A"), 0)

    def test_new_row_number_not_reserved_blocks_release(self):
        """协议〇.7：此后新行编号一律用 --reserve 取——未预留就手写一个新
        编号，即便该号本身并未与任何既有行重复，仍应被拒绝。"""
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A"), 0)  # 未 --reserve
        text = self.target_path.read_text(encoding="utf-8")
        new_row = "| 201 | 测试任务 | CC | 指针 | 产出 | 待领 | 触碰区 | 2026-08-04 |\n"
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        result = self._release(who="A")
        self.assertNotEqual(result, 0)

    def test_aibot_intake_row_without_reserve_passes(self):
        """队列 #333②：企微机器人收件登记路径（who=企微机器人 且任务列以
        「企微反馈自动归档：」开头）即便未 --reserve 也应放行——协议〇.10
        ⑶ 早已明文豁免这条路径的并入审核，`queue_appender.py::
        _next_task_id` 走独立取号路径、从不 --reserve，此前③预留归属
        校验不识别这条既有豁免，导致机器人 release 必被拒（#333 真实
        事故，锁卡满 30 分钟才被陈旧接管）。"""
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="企微机器人"), 0)  # 未 --reserve
        text = self.target_path.read_text(encoding="utf-8")
        new_row = (
            "| 201 | 企微反馈自动归档：姚祖怡 发来文本反馈 | 采购专线 | 指针 | "
            "产出 | [S:open] 待领 | 触碰区 | 2026-08-12 |\n"
        )
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        self.assertEqual(self._release(who="企微机器人"), 0)

    def test_aibot_non_intake_row_without_reserve_still_blocked(self):
        """防止豁免被当成绕过口（协议〇.10 ⑶ 自带的失效条款）：who=企微
        机器人 但任务列不以「企微反馈自动归档：」开头——不是收件登记，
        必须仍走正常预留校验，未预留即拒绝。"""
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="企微机器人"), 0)  # 未 --reserve
        text = self.target_path.read_text(encoding="utf-8")
        new_row = "| 201 | 测试任务（非收件登记） | 采购专线 | 指针 | 产出 | 待领 | 触碰区 | 2026-08-12 |\n"
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        result = self._release(who="企微机器人")
        self.assertNotEqual(result, 0)

    def test_non_aibot_who_with_intake_prefix_text_still_blocked(self):
        """豁免判据要求 who 与前缀同时成立——非机器人身份即便写出一模一样
        的「企微反馈自动归档：」前缀文本，也不构成豁免（防止有人手写模仿
        前缀绕开并入审核，这正是协议〇.10 ⑶ 明写的风险场景）。"""
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="Cowork-采购专线"), 0)  # 未 --reserve
        text = self.target_path.read_text(encoding="utf-8")
        new_row = (
            "| 201 | 企微反馈自动归档：手写模仿前缀 | 采购专线 | 指针 | "
            "产出 | 待领 | 触碰区 | 2026-08-12 |\n"
        )
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        result = self._release(who="Cowork-采购专线")
        self.assertNotEqual(result, 0)

    def test_duplicate_number_within_file_blocks_release(self):
        """组内重复校验独立于 --reserve 触发——手写一行沿用了已存在的编号，
        不经 --reserve（队列 #185 落地后，若真走 --reserve 撞上这种情况会
        在预留阶段就先被拦下，见 `ReserveIdsTests` 的竞态用例；本用例改为
        直接手写，验证 #225 release 时的组内重复检查本身仍然独立生效）。"""
        self._write_queue(
            section_one_rows="| 150 | 既有任务 | 姚祖怡 | 指针 | 产出 | 在办 | 触碰区 | 2026-07-01 |\n",
            hwm_one=200,
        )
        self.assertEqual(self._acquire(who="A"), 0)  # 不使用 --reserve
        text = self.target_path.read_text(encoding="utf-8")
        new_row = "| 150 | 撞号新任务 | CC | 指针 | 产出 | 待领 | 触碰区 | 2026-08-04 |\n"
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        result = self._release(who="A")
        self.assertNotEqual(result, 0)

    def test_duplicate_number_with_archive_blocks_release(self):
        archive_dir = self.repo_root  # DEFAULT_TARGET="queue.md" 的父目录即 repo_root
        (archive_dir / "跨桌任务队列-归档-202607.md").write_text(
            "## 一、任务看板（已完成行）\n\n" + self.SECTION_ONE_HEADER +
            "| 150 | 已归档任务 | 姚祖怡 | 指针 | 产出 | ✅ 已完成 | 触碰区 | 2026-07-01 |\n",
            encoding="utf-8",
        )
        self._write_queue(hwm_one=149)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        new_row = "| 150 | 撞归档号新任务 | CC | 指针 | 产出 | 待领 | 触碰区 | 2026-08-04 |\n"
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        result = self._release(who="A")
        self.assertNotEqual(result, 0)

    def test_editing_existing_row_status_does_not_trigger_number_checks(self):
        """只是改一个既有行的状态列（编号不变、此前已在快照里出现过），
        不应触发③编号校验——那是给"真正新增行"用的，不是给"编辑既有行"
        用的。"""
        self._write_queue(
            section_one_rows="| 150 | 既有任务 | 姚祖怡 | 指针 | 产出 | 在办 | 触碰区 | 2026-07-01 |\n",
            hwm_one=200,
        )
        self.assertEqual(self._acquire(who="A"), 0)  # 未 --reserve，也应无妨
        text = self.target_path.read_text(encoding="utf-8")
        text = text.replace(
            "| 150 | 既有任务 | 姚祖怡 | 指针 | 产出 | 在办 | 触碰区 | 2026-07-01 |",
            "| 150 | 既有任务 | 姚祖怡 | 指针 | 产出 | 待验收 | 触碰区 | 2026-07-01 |",
        )
        self.target_path.write_text(text, encoding="utf-8")

        self.assertEqual(self._release(who="A"), 0)

    def test_fixing_a_row_truncated_before_closing_pipe_does_not_need_reserve(self):
        """队列 #314②：真实事故复现——#313 行结构损坏（触碰区/日期两列被
        `git grep` 正则交替符撑破后整体吞掉，行不再以 `|` 收尾）期间，两次
        尝试修复均被 release 拒绝，理由是"该编号不属于本次 --reserve 预留
        的编号集合"，即便修复方并未新增任何编号、只是把一个既有行修好。

        根因链：`_diff_touched_rows` 靠 `_table_data_rows(old_text)` 算
        `old_numbers`；旧版 `_table_data_rows` 要求行首行尾都必须是 `|`，
        而快照里这个既有行本就因结构损坏而不以 `|` 收尾——于是它连
        `old_numbers` 都进不去。一旦有人把行修复到重新以 `|` 收尾（哪怕
        编号和内容都没变，只是把被吞的两列补回来），`_table_data_rows
        (new_text)` 首次能正确解析出该行，`_diff_touched_rows` 判定"内容
        变了"→touched；但 `number not in old_numbers` 仍为真（因为
        old_numbers 从未见过这一行）→ 被误判成"全新行"，要求必须在
        --reserve 预留集合内，而修复方当然没有为一个既有编号申请预留。

        修复后：只要求行首是 `|`，旧版快照里这行虽然列数不对，但已能被
        `_table_data_rows` 收录、`cells[0]` 正确取到编号，`old_numbers`
        因此包含该编号——修复该行结构不再被误判为新增行。"""
        truncated_row = (
            "| 150 | 结构损坏的既有任务（模拟 #313：触碰区/日期两列被吞，"
            "行不以竖线收尾） | 姚祖怡 | 指针 | 产出 | 在办，正文写到一半就断了"
        )
        self.assertFalse(truncated_row.rstrip().endswith("|"))
        self._write_queue(section_one_rows=truncated_row + "\n", hwm_one=200)

        self.assertEqual(self._acquire(who="A"), 0)  # 未 --reserve——修复既有行，不是新增

        fixed_row = (
            "| 150 | 结构损坏的既有任务（模拟 #313：触碰区/日期两列被吞，"
            "行不以竖线收尾） | 姚祖怡 | 指针 | 产出 | 待验收（已补回缺失两列） "
            "| 触碰区 | 2026-08-09 |\n"
        )
        text = self.target_path.read_text(encoding="utf-8")
        text = text.replace(truncated_row + "\n", fixed_row)
        self.target_path.write_text(text, encoding="utf-8")

        result = self._release(who="A")
        self.assertEqual(
            result, 0,
            "修复一个既有行的结构损坏（未新增编号）不应被③编号校验误判为"
            "「不属于预留集合」而拒绝——见队列 #313/#314 真实事故",
        )

    def test_p0_p1_row_with_unverified_phrase_blocks_release(self):
        """④检查的是状态列本身（本项目约定优先级标注写在状态列，见
        #219/#225/#234 等现存行）——P1 定级与「未核」须同时出现在状态列
        才算命中。"""
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        risky_row = (
            "| 201 | 风险项：待确认影响面 | CC | 指针 | 产出 | 待领（P1）**未核** | 触碰区 | 2026-08-04 |\n"
        )
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + risky_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        result = self._release(who="A")
        self.assertNotEqual(result, 0)

    def test_p0_p1_row_without_unverified_phrase_passes(self):
        """状态列须含反引号包裹的证伪命令片段（⑩，队列 #285）才能通过——
        本用例只测④本身（无「未核」字样即不因④而拦），故状态列另附一条
        证伪命令片段以满足⑩，避免与⑩混淆而误判本用例。"""
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        row = (
            "| 201 | 风险项：已核实影响面仅限本模块 | CC | 指针 | 产出 | "
            "待领（P1）`git log --oneline -1` | 触碰区 | 2026-08-04 |\n"
        )
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        self.assertEqual(self._release(who="A"), 0)

    def test_non_priority_row_with_unverified_phrase_is_not_blocked(self):
        """④断言门槛只对状态列同时含 P0/P1 定级的行生效——状态列不含
        P0/P1 时，即便提到「未核」也不应被拦（哪怕任务描述列里恰好也提到
        了 P1，见 test_editing_status_of_existing_p0_p1_row_ignores_
        unchanged_description_wording 覆盖的正是这一分离）。"""
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        row = "| 201 | 普通任务，细节未核 | CC | 指针 | 产出 | 待领 | 触碰区 | 2026-08-04 |\n"
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        self.assertEqual(self._release(who="A"), 0)

    def test_editing_status_of_existing_p0_p1_row_ignores_unchanged_description_wording(self):
        """④断言门槛真实 dogfooding 案例（2026-08-04）：一行本身就是在
        记录/提议这条规则，其（未改动的）任务描述天然含"P1"与"未核"这两个
        词——只把状态列改成已完成时，不应因历史描述里的措辞被误拦，只应
        检查真正新写入的单元格。"""
        self._write_queue(
            section_one_rows=(
                "| 150 | 断言门槛提案（P1）：成因见 #221，标注未核不等于可据此下结论 "
                "| 姚祖怡 | 指针 | 产出 | 待领（P1） | 触碰区 | 2026-07-01 |\n"
            ),
            hwm_one=200,
        )
        self.assertEqual(self._acquire(who="A"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        text = text.replace(
            "| 150 | 断言门槛提案（P1）：成因见 #221，标注未核不等于可据此下结论 "
            "| 姚祖怡 | 指针 | 产出 | 待领（P1） | 触碰区 | 2026-07-01 |",
            "| 150 | 断言门槛提案（P1）：成因见 #221，标注未核不等于可据此下结论 "
            "| 姚祖怡 | 指针 | 产出 | ✅ 已完成 | 触碰区 | 2026-07-01 |",
        )
        self.target_path.write_text(text, encoding="utf-8")

        self.assertEqual(self._release(who="A"), 0)

    def test_editing_status_that_newly_introduces_unverified_phrase_still_blocks(self):
        """反向用例：编辑既有行的状态列时，若这次改动把 P0/P1 定级与「未核」
        字样同时写进状态列，仍必须拦——只是把检查范围缩小到状态列本身，
        不是彻底放弃对既有行的校验（成因即 #221：determination 与免责声明
        同时出现在"当前判断"里）。"""
        self._write_queue(
            section_one_rows=(
                "| 150 | 某风险项 | 姚祖怡 | 指针 | 产出 | 待领（P1） | 触碰区 | 2026-07-01 |\n"
            ),
            hwm_one=200,
        )
        self.assertEqual(self._acquire(who="A"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        text = text.replace(
            "| 150 | 某风险项 | 姚祖怡 | 指针 | 产出 | 待领（P1） | 触碰区 | 2026-07-01 |",
            "| 150 | 某风险项 | 姚祖怡 | 指针 | 产出 | 待领（P1），未核实影响面 | 触碰区 | 2026-07-01 |",
        )
        self.target_path.write_text(text, encoding="utf-8")

        result = self._release(who="A")
        self.assertNotEqual(result, 0)

    def test_quoted_unverified_phrase_alongside_unquoted_p1_does_not_block(self):
        """队列 #248 真实取证复现（#221 行）：状态列同时含未加引号保护的 P1
        定级 token 与被「」引号包裹的"未做的核实"字样——后者是在引用/复述
        这条规则本身（如"「未做的核实如实登记」起了作用的正面案例"），不是
        在断言当前判断未核实，不应拦截。状态列另附一条反引号命令片段以
        满足⑩（队列 #285），避免与本用例要测的④混淆。"""
        self._write_queue(
            section_one_rows=(
                "| 150 | 某降级项 | 姚祖怡 | 指针 | 产出 | 待领（P1） | 触碰区 | 2026-07-01 |\n"
            ),
            hwm_one=200,
        )
        self.assertEqual(self._acquire(who="A"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        text = text.replace(
            "| 150 | 某降级项 | 姚祖怡 | 指针 | 产出 | 待领（P1） | 触碰区 | 2026-07-01 |",
            "| 150 | 某降级项 | 姚祖怡 | 指针 | 产出 | "
            "🔽 P1 → P3 降级：本行是「未做的核实如实登记」起了作用的正面案例"
            "（`git log --oneline -1` 核实无相关改动） "
            "| 触碰区 | 2026-07-01 |",
        )
        self.target_path.write_text(text, encoding="utf-8")

        self.assertEqual(self._release(who="A"), 0, "引号内的未核实字样不应触发断言门槛")

    def test_unquoted_unverified_phrase_outside_quotes_still_blocks(self):
        """反向用例：即便状态列里有一部分被引号保护，只要引号之外仍存在真实
        的 P0/P1 定级 + 未核实字样共现，仍必须拦——引号剔除不能被用来"藏"
        一处真实的未核实断言。"""
        self._write_queue(
            section_one_rows=(
                "| 150 | 某风险项 | 姚祖怡 | 指针 | 产出 | 待领 | 触碰区 | 2026-07-01 |\n"
            ),
            hwm_one=200,
        )
        self.assertEqual(self._acquire(who="A"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        text = text.replace(
            "| 150 | 某风险项 | 姚祖怡 | 指针 | 产出 | 待领 | 触碰区 | 2026-07-01 |",
            "| 150 | 某风险项 | 姚祖怡 | 指针 | 产出 | "
            "「引用讨论未做的核实这条规则」，但本行结论 P1 未核实影响面 "
            "| 触碰区 | 2026-07-01 |",
        )
        self.target_path.write_text(text, encoding="utf-8")

        result = self._release(who="A")
        self.assertNotEqual(result, 0, "引号之外的真实 P1+未核实共现仍须拦截")

    def test_p0_row_missing_falsifiability_command_blocks_release(self):
        """⑩因果断言证伪命令（队列 #285）正例：P0 定级但状态列不含任何
        反引号包裹的片段——即便不含「未核」字样（不触发④），仍须因缺证伪
        命令而拦。"""
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        row = "| 201 | 高危项 | CC | 指针 | 产出 | 待领（P0） | 触碰区 | 2026-08-09 |\n"
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        result = self._release(who="A")
        self.assertNotEqual(result, 0)

    def test_p0_row_with_falsifiability_command_passes(self):
        """⑩反例：P0 定级且状态列含反引号包裹的证伪命令片段——正常放行。"""
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        row = (
            "| 201 | 高危项 | CC | 指针 | 产出 | "
            "待领（P0）`git rev-parse HEAD~1` | 触碰区 | 2026-08-09 |\n"
        )
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        self.assertEqual(self._release(who="A"), 0)

    def test_quoted_p1_reference_without_command_does_not_trigger_falsifiability_gate(self):
        """⑩回归：状态列中的 P1 定级 token 完整落在「」引号包裹片段内（引用
        /复述判据本身，非本行当前断言），即便整个单元格没有任何反引号命令
        片段，也不应因⑩而拦——与④共用同一套引号剔除逻辑（#248）。"""
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        row = (
            "| 201 | 讨论 #285 断言门槛 | CC | 指针 | 产出 | "
            "已完成：本行示例引用「P1 定级」这一说法，非本行当前断言 "
            "| 触碰区 | 2026-08-09 |\n"
        )
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        self.assertEqual(self._release(who="A"), 0)

    def test_p0_row_missing_both_command_and_verification_reports_two_violations(self):
        """⑩与④相互独立：一行同时缺证伪命令、又同时含 P0/P1 定级与「未核」
        字样，应各自独立命中，不因命中其一而跳过另一项。"""
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        row = "| 201 | 高危项 | CC | 指针 | 产出 | 待领（P0）未核 | 触碰区 | 2026-08-09 |\n"
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A")
        self.assertNotEqual(result, 0)
        output = buf.getvalue()
        self.assertIn("缺证伪命令", output)
        self.assertIn("未核／未做的核实", output)

    def test_new_batch_ambiguous_status_blocks_release(self):
        """队列 #247②：状态列开头片段既不含"待"也不含"✅"——会被 sweep 判为
        "状态列模糊"、每轮跳过并重复告警——须在写入那一刻就拦下。"""
        self.assertEqual(self._acquire(who="A"), 0)
        self._write_queue(section_two_rows=(
            "| B-TEST | `docs/某个文件.md`、`queue.md` | `docs(test): 测试` | "
            "本session直接commit+push |\n"
        ))

        result = self._release(who="A")
        self.assertNotEqual(result, 0)

    def test_new_batch_pending_status_passes(self):
        self.assertEqual(self._acquire(who="A"), 0)
        self._write_queue(section_two_rows=(
            "| B-TEST | `docs/某个文件.md`、`queue.md` | `docs(test): 测试` | 待处理 |\n"
        ))

        self.assertEqual(self._release(who="A"), 0)

    def test_existing_batch_transitioning_to_done_status_passes(self):
        """⑤不拦"✅"本身；队列 #308 子项 F1 新增的边界是"新增批次不得以 ✅
        开头"，既有批次（本次持锁前已在快照里）合法转 ✅（sweep 或 CC 收工
        标记完成）不受影响——用"先注册待处理、本次持锁内编辑为已完成"复现
        这一合法路径（与 F1 用例集的"真正新增"场景区分开，见
        `test_new_batch_status_starting_with_check_mark_blocks_release`）。"""
        self._write_queue(section_two_rows=(
            "| B-TEST | `docs/某个文件.md`、`queue.md` | `docs(test): 测试` | 待处理 |\n"
        ))
        self.assertEqual(self._acquire(who="A"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        text = text.replace(
            "| B-TEST | `docs/某个文件.md`、`queue.md` | `docs(test): 测试` | 待处理 |",
            "| B-TEST | `docs/某个文件.md`、`queue.md` | `docs(test): 测试` | "
            "✅ 已完成（CC 直接提交，未走 sweep） |",
        )
        self.target_path.write_text(text, encoding="utf-8")

        self.assertEqual(self._release(who="A"), 0)

    def test_new_batch_preregistered_status_passes(self):
        """队列 #236(1)：认领即预登记的约定文本——虽然既不含"待"也不含
        "✅"，但这是有意为之的合法第三态，不应被⑤误拦。"""
        self.assertEqual(self._acquire(who="A"), 0)
        self._write_queue(section_two_rows=(
            "| B-TEST | `4-数字员工/采购部/SC8-.../` 全部改动、`queue.md` "
            "| `docs(test): 待精确化` | 在办（预登记，收工时精确化） |\n"
        ))

        self.assertEqual(self._release(who="A"), 0)

    def test_editing_existing_ambiguous_status_row_not_touched_this_session_does_not_block(self):
        """⑤只对本次持锁期间新增/修改的行生效——历史遗留的模糊状态行（如
        #247①所述、修复前留存的旧行）不因本次持锁而被追溯拦截。"""
        self._write_queue(section_two_rows=(
            "| B-OLD | `docs/某个文件.md`、`queue.md` | `docs(old): 历史遗留` | "
            "本session直接commit+push |\n"
        ))
        self.assertEqual(self._acquire(who="A"), 0)
        # 本次持锁期间不改动 §二，只改 §一 之外的内容不存在——直接 release，
        # 验证未触碰的 §二 历史行不参与①~⑤任何一项校验。
        self.assertEqual(self._release(who="A"), 0)

    def test_non_default_target_skips_structural_validation(self):
        """`--file` 指向非默认队列文件时，四项校验一律不生效——即便内容
        显然不合规（列数错、无高水位线行等）。"""
        other_path = self.repo_root / "其他共享文件.md"
        other_path.write_text("随便写点内容 | 只有两列\n", encoding="utf-8")
        ns = argparse.Namespace(file="其他共享文件.md", who="A", note="",
                                 reserve=None, section=None, reserve_multi=None, domain=None)
        self.assertEqual(self.module.cmd_acquire(ns), 0)
        release_ns = argparse.Namespace(
            file="其他共享文件.md", who="A",
            mechanism_wip_cap=self.module.MECHANISM_WIP_CAP_DEFAULT,
            force_mechanism_wip=False,
        )
        self.assertEqual(self.module.cmd_release(release_ns), 0)

    def test_bypass_detection_writes_durable_log_for_default_target(self):
        """队列 #200：锁定默认队列文件时，检测到绕锁改写除了终端回显，
        还应落一条持久审计记录（reports/queue_edit_lock_bypass.jsonl）。"""
        self._write_queue()
        self.assertEqual(self._acquire(who="A"), 0)
        self.assertEqual(self._release(who="A"), 0)

        text = self.target_path.read_text(encoding="utf-8")
        self.target_path.write_text(text + "\n绕锁写入的一行\n", encoding="utf-8")

        self.assertEqual(self._acquire(who="B"), 0)

        log_path = self.repo_root / "reports" / "queue_edit_lock_bypass.jsonl"
        self.assertTrue(log_path.exists())
        entry = json.loads(log_path.read_text(encoding="utf-8").strip().splitlines()[-1])
        self.assertEqual(entry["acquiring_who"], "B")
        self.assertEqual(entry["target"], "queue.md")

    def test_bypass_detection_does_not_write_durable_log_for_non_default_target(self):
        """通用检测机制对任意 --file 都生效（回显警告，见
        `BypassDetectionTests` 黑盒覆盖），但落盘审计记录只在锁定默认队列
        文件时才写——避免任意 --file 都往 REPO_ROOT/reports/ 写，污染真实
        项目目录（本用例用白盒 monkeypatch 过的临时 REPO_ROOT，验证"其他
        文件"路径确实不产生落盘记录）。"""
        other_target = "其他共享文件.md"
        (self.repo_root / other_target).write_text("原始内容\n", encoding="utf-8")
        self.assertEqual(self.module.cmd_acquire(argparse.Namespace(
            file=other_target, who="A", note="", reserve=None, section=None,
            reserve_multi=None, domain=None,
        )), 0)
        self.assertEqual(self.module.cmd_release(
            argparse.Namespace(
                file=other_target, who="A",
                mechanism_wip_cap=self.module.MECHANISM_WIP_CAP_DEFAULT,
                force_mechanism_wip=False,
            )
        ), 0)
        (self.repo_root / other_target).write_text("原始内容\n绕锁写入\n", encoding="utf-8")

        self.assertEqual(self.module.cmd_acquire(argparse.Namespace(
            file=other_target, who="B", note="", reserve=None, section=None,
            reserve_multi=None, domain=None,
        )), 0)

        log_path = self.repo_root / "reports" / "queue_edit_lock_bypass.jsonl"
        self.assertFalse(log_path.exists())

    # ---- 队列 #308 子项 F1（§二新增即终态防写）----------------------------

    def test_new_batch_status_starting_with_check_mark_blocks_release(self):
        """真正新增的批次（identity＝批次名，不在快照 §二 批次名集合内）
        状态列以「✅」开头即拒绝——复现 `B-0728财务专线核实`/
        `B-0728队列#125回填` 两批真实事故：登记时写了 ✅、被 sweep 判为
        已处理、内容石沉大海。"""
        self.assertEqual(self._acquire(who="A"), 0)
        self._write_queue(section_two_rows=(
            "| B-NEW | `docs/某个文件.md`、`queue.md` | `docs(test): 测试` | "
            "✅ 已完成（新增批次直接写终态） |\n"
        ))

        result = self._release(who="A")
        self.assertNotEqual(result, 0)

    # ---- 队列 #308 子项 F2（头尾不一致）------------------------------------

    def test_section_one_check_mark_not_leading_blocks_release(self):
        """开头片段（句级分隔符"。"之前）为"待处理"，✅ 出现在分隔符之后的
        正文段落——头尾不一致，见 2026-08-03 六行真实事故。"""
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        new_row = (
            "| 201 | 测试任务 | CC | 指针 | 产出 | "
            "待处理。子项已 ✅ 完成待收尾 | 触碰区 | 2026-08-09 |\n"
        )
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        result = self._release(who="A")
        self.assertNotEqual(result, 0)

    def test_section_two_check_mark_not_leading_blocks_release(self):
        self.assertEqual(self._acquire(who="A"), 0)
        self._write_queue(section_two_rows=(
            "| B-NEW | `docs/某个文件.md`、`queue.md` | `docs(test): 测试` | "
            "待处理。其中一步已 ✅ 完成 |\n"
        ))

        result = self._release(who="A")
        self.assertNotEqual(result, 0)

    def test_section_one_check_mark_leading_passes(self):
        """§一（不同于 §二）没有"新增即终态"限制（F1 仅 §二）——新增行状态列
        直接以「✅」开头且在最前（如补登记一件已实际完成的任务）应放行。"""
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        new_row = "| 201 | 测试任务 | CC | 指针 | 产出 | ✅ 已完成（补登记） | 触碰区 | 2026-08-09 |\n"
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        self.assertEqual(self._release(who="A"), 0)

    def test_section_one_check_mark_not_leading_but_status_field_present_passes(self):
        """队列 #308 收尾 session（2026-08-09）退休 ⑧ 对 §一 的适用范围：
        行首已带可解析的 `[S:...]` 机器字段时，字段本身即该行是否完成的
        权威源，本判据不再对该行生效——不论字段取值是否 `done`，正文later
        出现的「✅」（真实场景常见形态：带日期的子里程碑追记，如"✅ 节奏
        已定（日期）"）都不应被误判为"头尾不一致"。复现 2026-08-09 §一
        首次全量重跑本判据命中的 9 行同型假阳性（#22/#67/#96/#98/#118/
        #170/#234/#240/#264，均为 `[S:partial]`/`[S:blocked]`/`[S:hold]`/
        `[S:open]` 且正文含晚出现的「✅」子里程碑记录）。"""
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        new_row = (
            "| 201 | 测试任务 | CC | 指针 | 产出 | "
            "[S:partial][D:机] 待处理。子项已 ✅ 完成待收尾 | 触碰区 | 2026-08-09 |\n"
        )
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        self.assertEqual(self._release(who="A"), 0)

    def test_section_one_check_mark_not_leading_status_field_done_passes(self):
        """字段取值为 `done` 时同样退休（字段已是最强信号，正文位置无需
        再查）——覆盖字段取值的另一端，避免只用 `partial` 一种取值验证。"""
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        new_row = (
            "| 201 | 测试任务 | CC | 指针 | 产出 | "
            "[S:done][D:机] 已完成。附带说明：另一步骤 ✅ 已核验 | 触碰区 | 2026-08-09 |\n"
        )
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        self.assertEqual(self._release(who="A"), 0)

    # ---- 队列 §四 #58 ⑶（措施 C：机制类可动 WIP 上限，2026-08-17 起阻断）----

    def _write_two_existing_mechanism_rows(self):
        self._write_queue(
            section_one_rows=(
                "| 150 | 既有机制行1 | CC | 指针 | 产出 | [S:open][D:机] 待领 | 触碰区 | 2026-08-01 |\n"
                "| 151 | 既有机制行2 | CC | 指针 | 产出 | [S:open][D:机] 待领 | 触碰区 | 2026-08-01 |\n"
            ),
            hwm_one=200,
        )

    def _append_new_mechanism_row(self, status="[S:open][D:机] 待领", number="201"):
        text = self.target_path.read_text(encoding="utf-8")
        new_row = f"| {number} | 新机制行 | CC | 指针 | 产出 | {status} | 触碰区 | 2026-08-17 |\n"
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

    def test_mechanism_wip_over_cap_blocks_release(self):
        """2026-08-17 起由提示改为阻断：新增机制行且超限 ⇒ release 被拒绝、
        锁保持占用（§四 #58 ⑶ 的核心断言）。"""
        self._write_two_existing_mechanism_rows()
        self.assertEqual(self._acquire(who="A", reserve=1, section="一", domain="机"), 0)
        self._append_new_mechanism_row()

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A", mechanism_wip_cap=2)
        self.assertNotEqual(result, 0, "超限须拒绝 release，不再是仅提示")
        out = buf.getvalue()
        self.assertIn("机制类可动 WIP 当前 3／2", out)
        # 锁保持占用——拒绝不等于释放
        self.assertIsNotNone(self.module._read_lock(self.module._lock_path(
            self.module.QUEUE_LOCK_ANCHOR)))

    def test_mechanism_wip_rejection_message_is_actionable(self):
        """决策点 6：拒绝必须可行动——含当前计数／上限、本次新增行编号、
        两条出路的确切写法。否则只是把噪音从"每次都响"换成"每次都堵"。"""
        self._write_two_existing_mechanism_rows()
        self.assertEqual(self._acquire(who="A", reserve=1, section="一", domain="机"), 0)
        self._append_new_mechanism_row()

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self._release(who="A", mechanism_wip_cap=2)
        out = buf.getvalue()
        self.assertIn("3／2", out)          # 当前计数／上限
        self.assertIn("#201", out)          # 本次新增的是哪一行
        self.assertIn("[S:done]", out)      # 出路⑴ 的确切写法
        self.assertIn("WIP豁免：", out)      # 出路⑵ 的确切写法
        self.assertIn("--force-mechanism-wip", out)

    def test_mechanism_wip_waiver_switch_and_marker_together_pass(self):
        """逃生阀齐备（开关 ＋ 行内 `WIP豁免：<理由>`）⇒ 放行，理由随行落盘。"""
        self._write_two_existing_mechanism_rows()
        self.assertEqual(self._acquire(who="A", reserve=1, section="一", domain="机"), 0)
        self._append_new_mechanism_row(
            status="[S:open][D:机] 待领（WIP豁免：生产链路已停摆，须立刻立行止血）")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A", mechanism_wip_cap=2, force_mechanism_wip=True)
        self.assertEqual(result, 0, "开关与行内标记齐备时应放行")
        self.assertIn("逃生阀齐备", buf.getvalue())
        # 理由确实留在队列行里（进 git 的那一份），不是只出现在终端
        self.assertIn("WIP豁免：生产链路已停摆",
                      self.target_path.read_text(encoding="utf-8"))

    def test_mechanism_wip_switch_without_inline_marker_rejected(self):
        """只给开关、行内未写理由 ⇒ 仍拒绝——理由的唯一真源是行内标记，
        命令行参数随窗口关闭即消失。"""
        self._write_two_existing_mechanism_rows()
        self.assertEqual(self._acquire(who="A", reserve=1, section="一", domain="机"), 0)
        self._append_new_mechanism_row()

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A", mechanism_wip_cap=2, force_mechanism_wip=True)
        self.assertNotEqual(result, 0)
        self.assertIn("理由必须写在队列行里", buf.getvalue())

    def test_mechanism_wip_inline_marker_without_switch_rejected(self):
        """只写行内理由、未给开关 ⇒ 仍拒绝——越过须是一次显式选择。"""
        self._write_two_existing_mechanism_rows()
        self.assertEqual(self._acquire(who="A", reserve=1, section="一", domain="机"), 0)
        self._append_new_mechanism_row(
            status="[S:open][D:机] 待领（WIP豁免：紧急止血）")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A", mechanism_wip_cap=2)
        self.assertNotEqual(result, 0)
        self.assertIn("未传 `--force-mechanism-wip` 开关", buf.getvalue())

    def test_mechanism_wip_multiple_new_rows_each_need_own_waiver(self):
        """一次新增多条机制行时每条都须自带理由——只在其中一条写理由，
        后来的读者无从判断另一条凭什么立起来。"""
        self._write_two_existing_mechanism_rows()
        self.assertEqual(self._acquire(who="A", reserve=2, section="一", domain="机"), 0)
        self._append_new_mechanism_row(
            status="[S:open][D:机] 待领（WIP豁免：紧急止血）", number="201")
        self._append_new_mechanism_row(status="[S:open][D:机] 待领", number="202")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A", mechanism_wip_cap=2, force_mechanism_wip=True)
        self.assertNotEqual(result, 0)
        out = buf.getvalue()
        self.assertIn("#202", out)
        self.assertNotIn("新增行 #201／#202 的状态列", out)  # 只点名缺的那条

    def test_mechanism_wip_rejection_carries_reclassification_candidates(self):
        """队列 §一 #435 子项 E（tasks.md 5.3）：主拒绝文案（"两条出路"那
        条）须附带改判候选清单——既有行里若有命中外部阻塞措辞的
        open/partial 行，须被列出，帮读者直接执行出路⑴。"""
        self._write_queue(
            section_one_rows=(
                "| 150 | 既有机制行1 | CC | 指针 | 产出 | [S:open][D:机] 待领 | 触碰区 | 2026-08-01 |\n"
                "| 151 | 真实留步行 | CC | 指针 | 产出 | "
                "[S:partial][D:机] 五处缺陷代码全部修完、四项需人在场的动作未做 | 触碰区 | 2026-08-01 |\n"
            ),
            hwm_one=200,
        )
        self.assertEqual(self._acquire(who="A", reserve=1, section="一", domain="机"), 0)
        self._append_new_mechanism_row()

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self._release(who="A", mechanism_wip_cap=2)
        out = buf.getvalue()
        self.assertIn("改判候选清单", out)
        self.assertIn("#151", out)
        self.assertIn("建议 `blocked`", out)

    def test_mechanism_wip_escape_hatch_messages_omit_candidates(self):
        """已选定走逃生阀的两个分支（差开关／差行内标记）不该被塞进一份
        不相关的改判候选清单——那不是读者此刻要看的东西。"""
        self._write_queue(
            section_one_rows=(
                "| 150 | 既有机制行1 | CC | 指针 | 产出 | [S:open][D:机] 待领 | 触碰区 | 2026-08-01 |\n"
                "| 151 | 真实留步行 | CC | 指针 | 产出 | "
                "[S:partial][D:机] 五处缺陷代码全部修完、四项需人在场的动作未做 | 触碰区 | 2026-08-01 |\n"
            ),
            hwm_one=200,
        )
        self.assertEqual(self._acquire(who="A", reserve=1, section="一", domain="机"), 0)
        self._append_new_mechanism_row()

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self._release(who="A", mechanism_wip_cap=2, force_mechanism_wip=True)
        self.assertNotIn("改判候选清单", buf.getvalue())

    def test_mechanism_wip_within_cap_no_warning(self):
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一", domain="机"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        new_row = "| 201 | 新机制行 | CC | 指针 | 产出 | [S:open][D:机] 待领 | 触碰区 | 2026-08-09 |\n"
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A", mechanism_wip_cap=8)
        self.assertEqual(result, 0)
        self.assertNotIn("机制类可动 WIP", buf.getvalue())

    def test_mechanism_wip_not_recomputed_when_new_row_is_business_domain(self):
        """新增行域为「业」（非「机」）——不触发本项重新计数（无提示，也不
        因不触发本项而误判为通过失败，release 正常放行）。"""
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一", domain="业"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        new_row = "| 201 | 新业务行 | CC | 指针 | 产出 | [S:open][D:业] 待领 | 触碰区 | 2026-08-09 |\n"
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A", mechanism_wip_cap=0)
        self.assertEqual(result, 0)
        self.assertNotIn("机制类可动 WIP", buf.getvalue())

    def test_mechanism_wip_not_recomputed_when_only_existing_rows_edited(self):
        """本次持锁期间只编辑既有行（无真正新增的 [D:机] 行）——不触发重新
        计数，即便全表早已超过上限。

        🔴 **⑨ 阻断化之后这条是关键回归（design.md 决策点 4）**：若判据写成
        "release 时超限即拒绝"，在存量已超限时每一次 release 都会失败，而编辑
        锁是全项目唯一写入咽喉——**连这个正在关行降 WIP 的 session 也会被挡
        在门外，规则把自己的解法一起锁死**。本用例正是"来关行的那个 session"
        （cap=0、全表超限、只改既有行状态），必须放行。"""
        self._write_queue(
            section_one_rows=(
                "| 150 | 既有机制行 | CC | 指针 | 产出 | [S:open][D:机] 待领 | 触碰区 | 2026-08-01 |\n"
            ),
            hwm_one=200,
        )
        self.assertEqual(self._acquire(who="A"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        text = text.replace(
            "| 150 | 既有机制行 | CC | 指针 | 产出 | [S:open][D:机] 待领 | 触碰区 | 2026-08-01 |",
            "| 150 | 既有机制行 | CC | 指针 | 产出 | [S:partial][D:机] 在办中 | 触碰区 | 2026-08-01 |",
        )
        self.target_path.write_text(text, encoding="utf-8")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A", mechanism_wip_cap=0)
        self.assertEqual(result, 0)
        self.assertNotIn("机制类可动 WIP", buf.getvalue())

    # ---- 队列 §一 #381⑸ⓗ3：⑪ 行长上限（§一 状态列／§四 事项列 >4 KB）----

    @staticmethod
    def _long_status_cell(prefix="[S:open][D:业] 待领｜历史填充：", filler_chars=1500):
        """构造一个必超 `ROW_LENGTH_CAP_BYTES`（4096 B）的单元格文本——中文
        字符 UTF-8 三字节，1500 个即 4500 B，另加前缀更宽裕，不精确卡边界。"""
        return prefix + ("填" * filler_chars)

    def _freeze_module_now(self, year, month, day):
        """把 `self.module.datetime` 换成"冻住 `.now()`"的真 `datetime` 子类
        （而非替换成不相关的桩类）——模块内 `_now()` 另有 `datetime.now
        (timezone.utc)` 带参调用（写锁时间戳），桩类若不接受/兼容该签名与
        返回类型会连带打坏无关路径（本用例最初版本即如此撞坏，改为子类后
        `isoformat()`/时区等原生行为全部继承，只有 `.now()` 本身被冻结）。"""
        real_datetime = datetime

        class _Frozen(real_datetime):
            @classmethod
            def now(cls, tz=None):
                base = real_datetime(year, month, day)
                return base.replace(tzinfo=tz) if tz is not None else base

        self.module.datetime = _Frozen

    def test_row_length_within_cap_no_warning(self):
        self._write_queue(
            section_one_rows=(
                "| 150 | 既有行 | CC | 指针 | 产出 | [S:open][D:业] 待领 | 触碰区 | 2026-08-01 |\n"
            ),
            hwm_one=200,
        )
        self.assertEqual(self._acquire(who="A"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        text = text.replace(
            "| 150 | 既有行 | CC | 指针 | 产出 | [S:open][D:业] 待领 | 触碰区 | 2026-08-01 |",
            "| 150 | 既有行 | CC | 指针 | 产出 | [S:partial][D:业] 在办中 | 触碰区 | 2026-08-01 |",
        )
        self.target_path.write_text(text, encoding="utf-8")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A")
        self.assertEqual(result, 0)
        self.assertNotIn("上限", buf.getvalue())

    def test_row_length_over_cap_warns_before_cutoff_does_not_block(self):
        """判据落地当天（2026-09-04）早于阻断日期 2026-09-11——超限只告警、
        不拒绝 release（打印行号与字节，见 K2/K3 口径正本）。"""
        long_status = self._long_status_cell()
        self._write_queue(
            section_one_rows=(
                f"| 150 | 既有行 | CC | 指针 | 产出 | {long_status} | 触碰区 | 2026-08-01 |\n"
            ),
            hwm_one=200,
        )
        self.assertEqual(self._acquire(who="A"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        text = text.replace(long_status, long_status + "（追加一段）")
        self.target_path.write_text(text, encoding="utf-8")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A")
        out = buf.getvalue()
        self.assertEqual(result, 0, "阻断日期前应仅告警、不拒绝 release")
        self.assertIn("§一 #150", out)
        self.assertIn("上限", out)
        self.assertIn("仅告警不阻断", out)

    def test_row_length_over_cap_blocks_after_cutoff(self):
        """阻断日期（2026-09-11）当天或之后——超限拒绝 release，锁保持占用。"""
        long_status = self._long_status_cell()
        self._write_queue(
            section_one_rows=(
                f"| 150 | 既有行 | CC | 指针 | 产出 | {long_status} | 触碰区 | 2026-08-01 |\n"
            ),
            hwm_one=200,
        )
        self.assertEqual(self._acquire(who="A"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        text = text.replace(long_status, long_status + "（追加一段）")
        self.target_path.write_text(text, encoding="utf-8")

        self._freeze_module_now(2026, 9, 11)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A")
        out = buf.getvalue()
        self.assertNotEqual(result, 0, "阻断日期起超限须拒绝 release")
        self.assertIn("§一 #150", out)
        self.assertIn("上限", out)
        self.assertIsNotNone(
            self.module._read_lock(self.module._lock_path(self.module.QUEUE_LOCK_ANCHOR)),
            "拒绝不等于释放，锁应保持占用",
        )

    def test_row_length_waiver_marker_allows_release_after_cutoff(self):
        """行内 `行长豁免：<理由>` ⇒ 阻断日期起仍放行，理由随行落盘。"""
        long_status = self._long_status_cell(
            prefix="[S:open][D:业] 待领｜行长豁免：K2 搬迁排期中，本周先保留｜历史填充：",
        )
        self._write_queue(
            section_one_rows=(
                f"| 150 | 既有行 | CC | 指针 | 产出 | {long_status} | 触碰区 | 2026-08-01 |\n"
            ),
            hwm_one=200,
        )
        self.assertEqual(self._acquire(who="A"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        text = text.replace(long_status, long_status + "（追加一段）")
        self.target_path.write_text(text, encoding="utf-8")

        self._freeze_module_now(2026, 9, 11)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A")
        out = buf.getvalue()
        self.assertEqual(result, 0, "逃生阀齐备应放行")
        self.assertIn("已放行", out)
        self.assertIn(
            "行长豁免：K2 搬迁排期中",
            self.target_path.read_text(encoding="utf-8"),
        )

    def test_row_length_section_four_topic_column_checked(self):
        """§四「事项」列（非「状态」列）同样受本判据管辖。"""
        long_topic = "既有事项｜" + ("填" * 1500)
        self._write_queue(
            section_four_rows=f"| 50 | {long_topic} | CC | 2026-08-01 |\n",
            hwm_four=60,
        )
        self.assertEqual(self._acquire(who="A"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        text = text.replace(long_topic, long_topic + "（追加一段）")
        self.target_path.write_text(text, encoding="utf-8")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A")
        out = buf.getvalue()
        self.assertEqual(result, 0, "阻断日期前应仅告警")
        self.assertIn("§四 #50", out)
        self.assertIn("事项列", out)

    def test_row_length_marker_mention_in_spec_prose_is_not_a_real_waiver(self):
        """真实回归（2026-09-04，#381 本行自己撞见）：状态列里以反引号代码引用
        形式**说明**逃生阀写法（如 `行长豁免：<理由>`，占位符字面是 `<理由>`）
        不应被当成真实豁免——那是"正在解释规则"，不是"正在援引规则"。阻断
        日期起，只提及占位符的行仍应被正常拦截（而非因误判豁免而放行）。"""
        long_status = self._long_status_cell(
            prefix="[S:open][D:业] 待领｜逃生阀写法说明：行长豁免：<理由>｜历史填充：",
        )
        self._write_queue(
            section_one_rows=(
                f"| 150 | 既有行 | CC | 指针 | 产出 | {long_status} | 触碰区 | 2026-08-01 |\n"
            ),
            hwm_one=200,
        )
        self.assertEqual(self._acquire(who="A"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        text = text.replace(long_status, long_status + "（追加一段）")
        self.target_path.write_text(text, encoding="utf-8")

        self._freeze_module_now(2026, 9, 11)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A")
        out = buf.getvalue()
        self.assertNotEqual(result, 0, "占位符提及不构成真实豁免，阻断日期起应仍被拦")
        self.assertNotIn("已放行", out)
        self.assertIn("上限", out)

    def test_row_length_real_waiver_still_works_alongside_placeholder_mention(self):
        """同一单元格内混杂"文档式提及占位符"与"真实豁免"两种写法时，真实
        豁免仍应生效（`_has_genuine_row_length_waiver` 逐处扫描、任一处满足
        即算数，不因先遇到占位符提及就提前判定为无豁免）。"""
        long_status = self._long_status_cell(
            prefix=(
                "[S:open][D:业] 待领｜逃生阀写法说明：行长豁免：<理由>｜"
                "行长豁免：K2 搬迁排期中，本周先保留｜历史填充："
            ),
        )
        self._write_queue(
            section_one_rows=(
                f"| 150 | 既有行 | CC | 指针 | 产出 | {long_status} | 触碰区 | 2026-08-01 |\n"
            ),
            hwm_one=200,
        )
        self.assertEqual(self._acquire(who="A"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        text = text.replace(long_status, long_status + "（追加一段）")
        self.target_path.write_text(text, encoding="utf-8")

        self._freeze_module_now(2026, 9, 11)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A")
        self.assertEqual(result, 0, "混杂占位符提及时，真实豁免仍应生效")
        self.assertIn("已放行", buf.getvalue())

    def test_row_length_untouched_historical_row_not_blocked_after_cutoff(self):
        """只对本次持锁期间 touched 的行生效——存量超限但本次未碰的行，
        阻断日期起也不应挡住 release（同⑨ WIP 上限"不能把来关行的 session
        也挡在门外"的教训同构）。"""
        long_status = self._long_status_cell()
        self._write_queue(
            section_one_rows=(
                f"| 150 | 既有超限行 | CC | 指针 | 产出 | {long_status} | 触碰区 | 2026-08-01 |\n"
                "| 151 | 另一既有行 | CC | 指针 | 产出 | [S:open][D:业] 待领 | 触碰区 | 2026-08-01 |\n"
            ),
            hwm_one=200,
        )
        self.assertEqual(self._acquire(who="A"), 0)
        # 本次只编辑 #151，不碰 #150（存量超限行）。
        text = self.target_path.read_text(encoding="utf-8")
        text = text.replace(
            "| 151 | 另一既有行 | CC | 指针 | 产出 | [S:open][D:业] 待领 | 触碰区 | 2026-08-01 |",
            "| 151 | 另一既有行 | CC | 指针 | 产出 | [S:partial][D:业] 在办中 | 触碰区 | 2026-08-01 |",
        )
        self.target_path.write_text(text, encoding="utf-8")

        self._freeze_module_now(2026, 9, 11)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A")
        self.assertEqual(result, 0, "未 touched 的存量超限行不应挡住本次 release")
        self.assertNotIn("上限", buf.getvalue())

    # ---- 队列 #308 决策点 2（--domain 用法校验）----------------------------

    def test_domain_without_section_one_in_request_rejected(self):
        """--domain 仅对 §一 有意义——只预留 §四 时提供 --domain 是用法
        错误，不静默忽略。"""
        self._write_queue(hwm_four=40)
        ns = argparse.Namespace(
            file=self.module.DEFAULT_TARGET, who="A", note="",
            reserve=1, section="四", reserve_multi=None, domain="机",
        )
        result = self.module.cmd_acquire(ns)
        self.assertNotEqual(result, 0)

    def test_domain_recorded_in_lock_data_when_reserving_section_one(self):
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一", domain="机"), 0)
        lock_data = json.loads((self.repo_root / "queue.md.editlock").read_text(encoding="utf-8"))
        self.assertEqual(lock_data.get("domains"), {"一": "机"})


_RECLASS_SECTION_ONE_HEADER = (
    "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
    "|---|------|--------|-------------|----------|------|--------|------|\n"
)


def _reclass_section(*rows: str) -> str:
    return _RECLASS_SECTION_ONE_HEADER + "\n".join(rows) + "\n"


class StatusReclassificationSuggestionUnitTests(unittest.TestCase):
    """队列 §一 #435 子项 E：`_suggest_status_reclassification()` 纯函数
    单测——只读文本、无副作用，不需要完整 release 夹具。"""

    def setUp(self):
        self.module = _load_module()

    def test_命中真实分诊原话_如387(self):
        row = (
            "| 387 | 归档回执路由 | CC | 指针 | 产出 | "
            "[S:partial][D:机] 🟡 **五处缺陷代码全部修完、"
            "四项需人在场的动作未做（2026-08-24）** | 触碰区 | 2026-08-24 |"
        )
        candidates = self.module._suggest_status_reclassification(_reclass_section(row))
        self.assertEqual(len(candidates), 1)
        row_id, status, suggested, excerpt = candidates[0]
        self.assertEqual(row_id, "387")
        self.assertEqual(status, "partial")
        self.assertEqual(suggested, "blocked")
        self.assertIn("需人在场", excerpt)

    def test_常驻不销建议改判为timed(self):
        row = (
            "| 98 | 月度环境体检 | Cowork | 指针 | 产出 | "
            "[S:open][D:机] ✅ **首期体检已执行"
            "（2026-08-24；本行常驻不销，只滚动）** | 触碰区 | 2026-08-24 |"
        )
        candidates = self.module._suggest_status_reclassification(_reclass_section(row))
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0][2], "timed=")

    def test_不命中96反例的短标题(self):
        """`#96` 反例——防误伤：这类"两方各完成一半、都还有事可做"的
        协作语言，不应被误判为外部阻塞。"""
        row = (
            "| 96 | .51部署标准清单 | Cowork/CC | 指针 | 产出 | "
            "[S:partial][D:机] 🟡 **Cowork 半边完成、CC 半边待领"
            "（2026-08-01，环境保障线）** | 触碰区 | 2026-08-01 |"
        )
        candidates = self.module._suggest_status_reclassification(_reclass_section(row))
        self.assertEqual(candidates, [])

    def test_非open或partial状态不入选(self):
        for status in ("done", "blocked", "hold", "timed=2026-09-25"):
            row = (
                f"| 200 | 某行 | CC | 指针 | 产出 | "
                f"[S:{status}][D:机] 硬阻塞于某事 | 触碰区 | 2026-08-01 |"
            )
            candidates = self.module._suggest_status_reclassification(_reclass_section(row))
            self.assertEqual(candidates, [], f"status={status} 不应入选")

    def test_每行只取第一个命中措辞不重复列出(self):
        """同一行同时命中"需人在场"与"留步"两个措辞——只应产出一条
        候选，不因命中多个措辞而重复列出同一行（人工分诊按行过目，
        候选条数应等于待分诊行数，不是措辞命中次数）。"""
        row = (
            "| 387 | x | CC | 指针 | 产出 | "
            "[S:partial][D:机] 四项需人在场的动作未做，仅剩最后一步留步 | "
            "触碰区 | 2026-08-24 |"
        )
        candidates = self.module._suggest_status_reclassification(_reclass_section(row))
        self.assertEqual(len(candidates), 1)

    def test_只读不改变入参文本(self):
        row = (
            "| 387 | x | CC | 指针 | 产出 | "
            "[S:partial][D:机] 四项需人在场的动作未做 | 触碰区 | 2026-08-24 |"
        )
        section = _reclass_section(row)
        before = section
        self.module._suggest_status_reclassification(section)
        self.assertEqual(section, before, "design D5：只建议、不自动改，函数不得有副作用")


class ReclassificationCandidateRenderingUnitTests(unittest.TestCase):
    """`_render_reclassification_candidates()`：接在 WIP 阻断消息"两条
    出路"之后的候选清单渲染（tasks.md 5.3）。"""

    def setUp(self):
        self.module = _load_module()

    def test_零候选返回空字符串(self):
        """零候选时不占用阻断消息任何一行——消息已经够长。"""
        self.assertEqual(self.module._render_reclassification_candidates([]), "")

    def test_有候选时含行号现状态建议字段与命中原话(self):
        text = self.module._render_reclassification_candidates(
            [("380", "partial", "blocked", "真实冒烟仍未做")]
        )
        self.assertIn("#380", text)
        self.assertIn("partial", text)
        self.assertIn("blocked", text)
        self.assertIn("真实冒烟仍未做", text)


class RealSnapshotReclassificationRegressionTests(unittest.TestCase):
    """队列 §一 #435 子项 E，tasks.md 5.6（**本子项唯一验收判据**）：
    对 2026-08-30 改判前的真实队列快照跑，须列全当天人工分诊出的那
    8 行（`#282`／`#413`／`#419`／`#398`／`#380`／`#387`／`#399`／`#98`）。
    列不全就是漏报。

    下列行文本逐字取自改判落地那次真实提交（`178979c`）的**父提交**
    内容——`git log --oneline -S"[S:blocked][D:机] 🟢 **apply 已完成、
    真实冒烟仍未做" -- 1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md`
    定位到 `178979c` 后，用 `git diff 178979c^ 178979c -- <同路径>` 的
    "-" 侧原样摘取（未改写用词，超长行只截到命中措辞之后一小段）。
    """

    def setUp(self):
        self.module = _load_module()

    def test_列全当天人工分诊出的八行(self):
        rows = [
            "| 380 | 李姣龙接入企微机器人可达通道 | CC | 指针 | 产出 | "
            "[S:partial][D:机] 🟢 **apply 已完成、真实冒烟仍未做"
            "（2026-08-25，CC 无头批处理 A30）** —— 详见 §四 #116。"
            "🔴 **两项留步，均非遗漏**： **①真实发送冒烟仍未做** | "
            "触碰区 | 2026-08-22 |",
            "| 387 | 归档回执对IT域静默丢失 | CC | 指针 | 产出 | "
            "[S:partial][D:机] 🟡 **五处缺陷代码全部修完、"
            "四项需人在场的动作未做（2026-08-24，CC）** | 触碰区 | 2026-08-24 |",
            "| 398 | 机制自身失效批次 | CC | 指针 | 产出 | "
            "[S:partial][D:机] 🟢 **三处根因全部定位并实测坐实，"
            "可修的已修完；两处留步（守卫拦截／待拍板）"
            "（CC-A28，2026-08-25）** | 触碰区 | 2026-08-24 |",
            "| 399 | 补件登记与发送通道脱节 | CC | 指针 | 产出 | "
            "[S:partial][D:机] ✅ **apply 已完成、单测已本地实跑取证；"
            "仅剩 6.4 端到端真实发送留步（2026-08-25 15:12 本地）** | "
            "触碰区 | 2026-08-24 |",
            "| 413 | 通知通道二阶段窗口切换 | CC | 指针 | 产出 | "
            "[S:partial][D:机] 🆕 **2026-08-26 立行**。"
            "**硬阻塞于两条**：⑴ #412（M1）完成；"
            "⑵ Shao Peishen 给出窗口日期。| 触碰区 | 2026-08-26 |",
            "| 419 | 运维逃生通道第三道防线 | CC | 指针 | 产出 | "
            "[S:open][D:机] 🔴 **2026-08-26 立行，无默认项**："
            "提出该项的 session 已收工、回合制无法自我唤醒，"
            "两条前提均不成立，须他明确答复。 ━━━ 🟢 **2026-08-27 "
            "`OP-0827-E`：本行的 LAN 留步已解除** | 触碰区 | 2026-08-26 |",
            "| 282 | 通知通道过渡群广播全迁aibot | CC | 指针 | 产出 | "
            "[S:partial][D:机] ⏸ **已押后，暂不派"
            "（Shao Peishen 2026-08-08 选 (a)：先只推 #300，本行押后）** | "
            "触碰区 | 2026-08-06 |",
            "| 98 | 月度环境体检例行 | Cowork | 指针 | 产出 | "
            "[S:open][D:机] ✅ **首期体检已执行"
            "（2026-08-24，Cowork 环境总线；本行常驻不销，只滚动）** | "
            "触碰区 | 2026-07-24 |",
        ]
        candidates = self.module._suggest_status_reclassification(_reclass_section(*rows))
        got_ids = {row_id for row_id, *_ in candidates}
        target_ids = {"282", "413", "419", "398", "380", "387", "399", "98"}
        missing = target_ids - got_ids
        self.assertEqual(
            missing, set(),
            f"漏报：{missing}——本子项唯一验收判据，列不全就是漏报",
        )
        # 附带核对建议字段方向：7 行建议 blocked，仅 #98（常驻不销）
        # 建议 timed=。
        by_id = {row_id: suggested for row_id, _status, suggested, _excerpt in candidates}
        self.assertEqual(by_id["98"], "timed=")
        for rid in target_ids - {"98"}:
            self.assertEqual(by_id[rid], "blocked", f"#{rid} 应建议 blocked")

    def test_已知限制_96的完整正文含一处过期提及会被列为候选(self):
        """如实记录一个已知边界情形，供未来维护者查证时不必重新发现
        一次：`#96` 的**短标题**不会误报（见上一测试类），但它 6,000+
        字的完整正文里有一处**已解决的历史提及**"待 Shao Peishen"——
        下方摘取的是该正文里真实存在、彼此间隔约 900 字的两段（用
        "……" 标记省略的中段，未改写措辞本身）。本函数按行扫描全文、
        不分辨"当前状态"与"历史叙事"，会把这处过期提及也列为候选。

        **这不是需要修的缺陷**：D2/D7 同族取舍——宁可多列一条candidate
        让人一眼跳过，也不可为消灭这类误报而收紧到可能漏掉真实案例
        （#419 的真实触发同样落在正文靠后位置，见 design D2 的两向
        如实登记原则）。"""
        row = (
            "| 96 | .51部署标准清单与工程手册 | Cowork/CC | 指针 | 产出 | "
            "[S:partial][D:机] 🟡 **Cowork 半边完成、CC 半边待领"
            "（2026-08-01，环境保障线）**：清单已落"
            "`3-治理与合规/.51部署标准清单.md`（status=待发）。"
            "……（中略约 900 字真实取证细节）……"
            "**§十 两点待 Shao Peishen 定**"
            "（本件放置位置＝治理件 vs 工程手册；"
            "门禁强度＝自证型 vs 须贴冒烟原始输出）。"
            "**✅ 清单已转「生效」（Shao Peishen 2026-08-01 拍板）**："
            "frontmatter status: 待发→生效 | 触碰区 | 2026-08-01 |"
        )
        candidates = self.module._suggest_status_reclassification(_reclass_section(row))
        self.assertEqual(len(candidates), 1, "如实记录已知的过度报告行为")
        self.assertEqual(candidates[0][0], "96")


class FollowupReadmeStructuralValidationTests(unittest.TestCase):
    """队列 #124 阶段二（design.md D1）：跟进信 README 两态语义的结构性
    拦截"新建即终态"反模式。

    白盒方式，同 ReleaseStructuralValidationTests：monkeypatch
    REPO_ROOT/FOLLOWUP_README_TARGET 指向本用例专属临时目录（不能用真实
    生产路径走黑盒子进程，会误触真实文件）。
    """

    HEADER = (
        "| 编号 | 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |\n"
        "|--------|------|--------|---------|---------|---------|\n"
    )

    # 队列 #399：真身 README 自本包起恒有两张表，release 校验断言两个章节
    # 标题均在（决策点 3(b)）⇒ 本类 fixture **改判**（不是放宽）：此前只写
    # 主表章节的写法，在新契约下本就是一份不合法的 README。
    SUPPLEMENT_HEADER = (
        "| 承接编号 | 日期 | 收信人 | 主要事项 | 需回复 | 发送状态 |\n"
        "|---------|------|--------|---------|--------|---------|\n"
    )

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmpdir.name)
        self.module = _load_module()
        self.module.REPO_ROOT = self.repo_root
        self.module.FOLLOWUP_README_TARGET = "README.md"
        self.target_path = self.repo_root / "README.md"

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write_readme(self, rows="", supplement_rows=""):
        text = (
            "## 现有跟进信清单\n\n" + self.HEADER + rows
            + "\n## 补件登记（不占编号、不占串行闸）\n\n"
            + self.SUPPLEMENT_HEADER + supplement_rows
        )
        self.target_path.write_text(text, encoding="utf-8")

    def _acquire(self, who="A"):
        ns = argparse.Namespace(
            file=self.module.FOLLOWUP_README_TARGET, who=who, note="",
            reserve=None, section=None, reserve_multi=None, domain=None,
        )
        return self.module.cmd_acquire(ns)

    def _release(self, who=""):
        ns = argparse.Namespace(
            file=self.module.FOLLOWUP_README_TARGET, who=who,
            mechanism_wip_cap=self.module.MECHANISM_WIP_CAP_DEFAULT,
            force_mechanism_wip=False,
        )
        return self.module.cmd_release(ns)

    def test_release_succeeds_with_no_changes(self):
        self._write_readme()
        self.assertEqual(self._acquire(who="A"), 0)
        self.assertEqual(self._release(who="A"), 0)

    def test_new_row_with_draft_status_passes(self):
        self._write_readme()
        self.assertEqual(self._acquire(who="A"), 0)
        new_row = "| 采购部#11 | 2026-08-05 | 采购部 · 姚祖怡 | 测试事项 | 不急 | ⏳ 待你审 |\n"
        self._write_readme(new_row)
        self.assertEqual(self._release(who="A"), 0)

    def test_new_row_with_finalized_status_blocks_release(self):
        """D1 核心场景：起草物理上不能一步到位写终态——本次持锁窗口内
        新增的行若直接是「🆕 待发」，release 必须被拒绝、锁保持占用。"""
        self._write_readme()
        self.assertEqual(self._acquire(who="A"), 0)
        new_row = "| 采购部#11 | 2026-08-05 | 采购部 · 姚祖怡 | 测试事项 | 不急 | 🆕 待发 |\n"
        self._write_readme(new_row)

        result = self._release(who="A")
        self.assertNotEqual(result, 0)
        self.assertFalse(
            json.loads((self.repo_root / "README.md.editlock").read_text(
                encoding="utf-8")).get("released")
        )

    def test_existing_row_draft_to_finalized_transition_passes(self):
        """既有行从「⏳ 待你审」转为「🆕 待发」是批准脚本
        （approve_followup_letter.py）的合法产物，其身份在快照里能找到，
        不应被本拦截误伤。"""
        existing_row = "| 采购部#11 | 2026-08-05 | 采购部 · 姚祖怡 | 测试事项 | 不急 | ⏳ 待你审 |\n"
        self._write_readme(existing_row)
        self.assertEqual(self._acquire(who="A"), 0)
        finalized_row = existing_row.replace("⏳ 待你审", "🆕 待发")
        self._write_readme(finalized_row)

        self.assertEqual(self._release(who="A"), 0)

    def test_unrelated_edit_to_non_finalized_row_passes(self):
        """编辑一个既有行、但改动后状态列不是终态（如仍是「✅ 已发」）——
        即便非状态列内容也变了（身份不再匹配快照），也不应被拦：本拦截
        只关心「新增行 + 终态」这一种组合。"""
        existing_row = "| 采购部#11 | 2026-08-05 | 采购部 · 姚祖怡 | 测试事项 | 不急 | ✅ 已发 |\n"
        self._write_readme(existing_row)
        self.assertEqual(self._acquire(who="A"), 0)
        edited_row = "| 采购部#11 | 2026-08-05 | 采购部 · 姚祖怡 | 测试事项（已更新） | 不急 | ✅ 已发 |\n"
        self._write_readme(edited_row)

        self.assertEqual(self._release(who="A"), 0)

    # ---- 队列 #308 子项 G（跟进信串行原则闸）--------------------------------

    def test_serial_gate_blocks_when_prior_status_is_draft(self):
        prior = "| 采购部#11 | 2026-08-05 | 采购部 · 姚祖怡 | 测试事项 | 不急 | ⏳ 待你审 |\n"
        self._write_readme(prior)
        self.assertEqual(self._acquire(who="A"), 0)
        new_row = "| 采购部#12 | 2026-08-09 | 采购部 · 姚祖怡 | 新事项 | 不急 | ⏳ 待你审 |\n"
        self._write_readme(prior + new_row)

        self.assertNotEqual(self._release(who="A"), 0)

    def test_serial_gate_blocks_when_prior_status_is_finalized(self):
        prior = "| 采购部#11 | 2026-08-05 | 采购部 · 姚祖怡 | 测试事项 | 不急 | 🆕 待发 |\n"
        self._write_readme(prior)
        self.assertEqual(self._acquire(who="A"), 0)
        new_row = "| 采购部#12 | 2026-08-09 | 采购部 · 姚祖怡 | 新事项 | 不急 | ⏳ 待你审 |\n"
        self._write_readme(prior + new_row)

        self.assertNotEqual(self._release(who="A"), 0)

    def test_serial_gate_blocks_when_prior_status_is_paused(self):
        prior = "| 采购部#11 | 2026-08-05 | 采购部 · 姚祖怡 | 测试事项 | 不急 | ⏸ 暂缓 |\n"
        self._write_readme(prior)
        self.assertEqual(self._acquire(who="A"), 0)
        new_row = "| 采购部#12 | 2026-08-09 | 采购部 · 姚祖怡 | 新事项 | 不急 | ⏳ 待你审 |\n"
        self._write_readme(prior + new_row)

        self.assertNotEqual(self._release(who="A"), 0)

    def test_serial_gate_blocks_when_prior_status_is_pushed_but_not_closed(self):
        """「✅ 已推送 <时刻>」不是闭环态——闭环态唯一取值是
        「📥 已回件并回灌 <日期>」（信推送出去不等于对方已回件回灌完毕）。"""
        prior = "| 采购部#11 | 2026-08-05 | 采购部 · 姚祖怡 | 测试事项 | 不急 | ✅ 已推送 2026-08-06 01:30 UTC |\n"
        self._write_readme(prior)
        self.assertEqual(self._acquire(who="A"), 0)
        new_row = "| 采购部#12 | 2026-08-09 | 采购部 · 姚祖怡 | 新事项 | 不急 | ⏳ 待你审 |\n"
        self._write_readme(prior + new_row)

        self.assertNotEqual(self._release(who="A"), 0)

    def test_serial_gate_passes_when_prior_status_closed(self):
        prior = "| 采购部#11 | 2026-08-05 | 采购部 · 姚祖怡 | 测试事项 | 不急 | 📥 已回件并回灌 2026-08-08 |\n"
        self._write_readme(prior)
        self.assertEqual(self._acquire(who="A"), 0)
        new_row = "| 采购部#12 | 2026-08-09 | 采购部 · 姚祖怡 | 新事项 | 不急 | ⏳ 待你审 |\n"
        self._write_readme(prior + new_row)

        self.assertEqual(self._release(who="A"), 0)

    def test_serial_gate_waiver_allows_release_and_prints_notice(self):
        prior = "| 采购部#11 | 2026-08-05 | 采购部 · 姚祖怡 | 测试事项 | 不急 | 🆕 待发 |\n"
        self._write_readme(prior)
        self.assertEqual(self._acquire(who="A"), 0)
        new_row = (
            "| 采购部#12 | 2026-08-09 | 采购部 · 姚祖怡 | "
            "新事项，串行豁免：业务方要求两条并行跟进 | 不急 | ⏳ 待你审 |\n"
        )
        self._write_readme(prior + new_row)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A")
        self.assertEqual(result, 0)
        self.assertIn("检测到串行豁免声明", buf.getvalue())

    def test_serial_gate_not_triggered_for_first_time_recipient(self):
        """该收信人历史上首次出现——无「前一封」可比对，不受串行原则约束。"""
        self._write_readme()
        self.assertEqual(self._acquire(who="A"), 0)
        new_row = "| 财务部#1 | 2026-08-09 | 财务部 · 唐燕萍 | 首次跟进 | 不急 | ⏳ 待你审 |\n"
        self._write_readme(new_row)

        self.assertEqual(self._release(who="A"), 0)

    def test_serial_gate_not_triggered_by_editing_existing_row(self):
        """本次持锁期间只编辑既有行（approve_followup_letter.py 的合法产物），
        不涉及"新增"某收信人的登记行——即便同一收信人另有一封非闭环的旧信，
        也不应触发串行闸（本项只管新增行）。"""
        rows = (
            "| 采购部#11 | 2026-08-05 | 采购部 · 姚祖怡 | 测试事项一 | 不急 | 🆕 待发 |\n"
            "| 采购部#12 | 2026-08-06 | 采购部 · 姚祖怡 | 测试事项二 | 不急 | ⏳ 待你审 |\n"
        )
        self._write_readme(rows)
        self.assertEqual(self._acquire(who="A"), 0)
        edited_rows = rows.replace(
            "| 采购部#12 | 2026-08-06 | 采购部 · 姚祖怡 | 测试事项二 | 不急 | ⏳ 待你审 |",
            "| 采购部#12 | 2026-08-06 | 采购部 · 姚祖怡 | 测试事项二 | 不急 | 🆕 待发 |",
        )
        self._write_readme(edited_rows)

        self.assertEqual(self._release(who="A"), 0)


class AppendRowTests(unittest.TestCase):
    """队列 #258：`append-row` 子命令——插入位置/列数/裸竖线校验交给工具，
    替代此前"用全文最后一个 # 数字 形态的行定位分区末尾"这一容易插错分区
    的启发式（#248/#254 同一根因两次踩坑）。

    黑盒方式：`--file` 指向本用例专属临时文件的绝对路径（同 `EditLockTests`
    既有惯例），不触碰真实队列锁/REPO_ROOT。
    """

    FIXTURE = (
        "## 一、任务看板\n\n"
        "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|------|--------|-------------|----------|------|--------|------|\n"
        "| 100 | 示例 | CC | 无 | 无 | ✅ 已完成 | 无 | 2026-08-01 |\n"
        "\n## 二、待 commit 批次（CC 取活销行）\n\n"
        "| 批次 | 文件清单 | 说明 | 状态 |\n"
        "|------|---------|------|------|\n"
        "\n## 四、需 Shao Peishen 的动作（例外与拍板）\n\n"
        "| # | 事项 | 等谁 | 截止 |\n"
        "|---|------|------|------|\n"
        "| 50 | 示例 | Shao Peishen | 不急 |\n"
    )

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.target = Path(self._tmpdir.name) / "假想队列.md"
        self.target.write_text(self.FIXTURE, encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _append(self, *args: str) -> subprocess.CompletedProcess:
        return run("--file", str(self.target), "append-row", *args)

    def test_structured_cells_assemble_correct_column_count(self):
        result = self._append(
            "--section", "一", "--number", "101",
            "--cell", "新任务", "--cell", "CC", "--cell", "无",
            "--cell", "无", "--cell", "[S:open][D:机] 待领", "--cell", "无", "--cell", "2026-08-07",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = self.target.read_text(encoding="utf-8")
        self.assertIn(
            "| 101 | 新任务 | CC | 无 | 无 | [S:open][D:机] 待领 | 无 | 2026-08-07 |", text,
        )

    def test_wrong_cell_count_rejected_without_writing(self):
        before = self.target.read_text(encoding="utf-8")
        result = self._append(
            "--section", "一", "--number", "101",
            "--cell", "只有一个字段",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    def test_insert_lands_in_target_section_not_a_lookalike_section(self):
        """核心场景（#248/#254 复现）：§一 与 §四 行格式相似（均以 `| 数字 |`
        开头），插入 §一 不得影响 §四，反之亦然。"""
        result = self._append(
            "--section", "一", "--number", "101",
            "--cell", "新任务", "--cell", "CC", "--cell", "无",
            "--cell", "无", "--cell", "[S:open][D:机] 待领", "--cell", "无", "--cell", "2026-08-07",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = self.target.read_text(encoding="utf-8")
        section_four_start = text.index("## 四、")
        self.assertNotIn("| 101 |", text[section_four_start:])
        section_one_text = text[text.index("## 一、"):text.index("## 二、")]
        self.assertIn("| 101 |", section_one_text)

    def test_append_to_section_four_after_section_one(self):
        result = self._append(
            "--section", "四", "--number", "51",
            "--cell", "新事项", "--cell", "Shao Peishen", "--cell", "不急",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = self.target.read_text(encoding="utf-8")
        section_four_text = text[text.index("## 四、"):]
        self.assertIn("| 51 | 新事项 | Shao Peishen | 不急 |", section_four_text)
        section_one_text = text[text.index("## 一、"):text.index("## 二、")]
        self.assertNotIn("| 51 |", section_one_text)

    def test_append_to_empty_section_two(self):
        result = self._append(
            "--section", "二",
            "--cell", "B-测试批次", "--cell", "`docs/文件.md`", "--cell", "说明", "--cell", "待处理",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = self.target.read_text(encoding="utf-8")
        self.assertIn("| B-测试批次 | `docs/文件.md` | 说明 | 待处理 |", text)

    def test_bare_pipe_rejected(self):
        before = self.target.read_text(encoding="utf-8")
        result = self._append(
            "--section", "四", "--number", "51",
            "--cell", "A|B", "--cell", "Shao Peishen", "--cell", "不急",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    def test_backtick_wrapped_pipe_also_rejected(self):
        """apply 阶段修正（design.md 有记录）：反引号不豁免裸竖线检测——
        本项目表格解析对反引号无感知，豁免会制造"写入时放行、release ①
        校验又拒绝"的自相矛盾状态。"""
        before = self.target.read_text(encoding="utf-8")
        result = self._append(
            "--section", "四", "--number", "51",
            "--cell", "`A|B`", "--cell", "Shao Peishen", "--cell", "不急",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    def test_number_provided_for_section_two_rejected(self):
        before = self.target.read_text(encoding="utf-8")
        result = self._append(
            "--section", "二", "--number", "1",
            "--cell", "B-测试", "--cell", "`x.md`", "--cell", "说明", "--cell", "待处理",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    def test_missing_number_for_section_one_rejected(self):
        before = self.target.read_text(encoding="utf-8")
        result = self._append(
            "--section", "一",
            "--cell", "新任务", "--cell", "CC", "--cell", "无",
            "--cell", "无", "--cell", "[S:open][D:机] 待领", "--cell", "无", "--cell", "2026-08-07",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    def test_missing_section_heading_rejected(self):
        self.target.write_text("没有任何分区标题的文件", encoding="utf-8")
        before = self.target.read_text(encoding="utf-8")
        result = self._append(
            "--section", "一", "--number", "101",
            "--cell", "新任务", "--cell", "CC", "--cell", "无",
            "--cell", "无", "--cell", "[S:open][D:机] 待领", "--cell", "无", "--cell", "2026-08-07",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)


class FollowupReplyStateSyncTests(unittest.TestCase):
    """队列 #366 / S4 桥二：回灌完成（§一 入信行 `[S:done]`）⇒ README 必须
    转闭环态，否则拒绝 release。

    白盒方式，同 `HoldConsistencyValidationTests`：monkeypatch REPO_ROOT 与
    两个目标路径常量指向本用例专属临时目录，不触碰真实文件。
    """

    SECTION_ONE_HEADER = (
        "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|------|--------|-------------|----------|------|--------|------|\n"
    )
    SECTION_TWO_HEADER = (
        "| 批次 | 文件清单 | 建议 message | 状态 |\n"
        "|------|---------|--------------|------|\n"
    )
    SECTION_FOUR_HEADER = (
        "| # | 事项 | 等谁 | 截止 |\n"
        "|---|------|------|------|\n"
    )
    README_HEADER = (
        "| 编号 | 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |\n"
        "|--------|------|--------|---------|---------|---------|\n"
    )
    # 取自真实归档件与真实 README 标注（2026-08-21 实测）。
    ARCHIVED = (
        "财务部-tangyanping-回复-2026-08-06-财务部-唐燕萍-跟进-2026-08-05-"
        "FI2面板6项显示问题已修复请复核-回复-b01f0dd5ed0005b5ac01d9ccd9eb3006.docx"
    )
    LETTER_FILE = "财务部-唐燕萍-跟进-2026-08-05-FI2面板6项显示问题已修复请复核.md"

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmpdir.name)
        self.module = _load_module()
        self.module.REPO_ROOT = self.repo_root
        self.module.DEFAULT_TARGET = "queue.md"
        self.module.FOLLOWUP_README_TARGET = "readme.md"
        self.module.QUEUE_MECHANISM_PATH_REL = "queue.md"
        self.module.QUEUE_BUSINESS_PATH_REL = "queue-business.md"
        self.module.QUEUE_LOCK_ANCHOR = "queue.md"
        self.target_path = self.repo_root / "queue.md"
        self.business_path = self.repo_root / "queue-business.md"
        self.readme_path = self.repo_root / "readme.md"
        self._write_queue()
        self.business_path.write_text(self._queue_text(), encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _queue_text(self, section_one_rows="", hwm_one=200):
        return (
            f"> **编号高水位线：§一 #{hwm_one} ｜ §四 #40**（说明文字）\n\n"
            "## 一、任务看板\n\n" + self.SECTION_ONE_HEADER + section_one_rows +
            "\n## 二、待 commit 批次（CC 取活销行）\n\n" + self.SECTION_TWO_HEADER +
            "\n## 三、口径冻结标（重梳期防在途建造撞车）\n\n"
            "| 域/场景 | 冻结原因 | 挂标 | 解除条件 |\n"
            "|---------|---------|------|---------|\n"
            "\n## 四、需 Shao Peishen 的动作（例外与拍板）\n\n" +
            self.SECTION_FOUR_HEADER
        )

    def _write_queue(self, section_one_rows="", hwm_one=200):
        self.target_path.write_text(
            self._queue_text(section_one_rows, hwm_one), encoding="utf-8")

    def _write_readme(self, status, number="财务部#11"):
        self.readme_path.write_text(
            "## 现有跟进信清单\n\n" + self.README_HEADER
            + f"| {number} | 2026-08-05 | 财务部 · 唐燕萍 | FI2 面板复核 → "
              f"目标文件：`{self.LETTER_FILE}` | 尽快 | {status} |\n",
            encoding="utf-8",
        )

    def _intake_row(self, row_id, status, extra=""):
        return (
            f"| {row_id} | 企微反馈自动归档：tangyanping 发来文件 {self.ARCHIVED} | "
            f"财务专线 | `7-外部文档/财务部/{self.ARCHIVED}` | 核实内容 | "
            f"{status}{extra} | 队列 | 2026-08-07 |\n"
        )

    def _acquire(self, who="A", reserve=None, section=None):
        return self.module.cmd_acquire(argparse.Namespace(
            file=self.module.DEFAULT_TARGET, who=who, note="",
            reserve=reserve, section=section, reserve_multi=None, domain=None,
        ))

    def _release(self, who=""):
        return self.module.cmd_release(argparse.Namespace(
            file=self.module.DEFAULT_TARGET, who=who,
            mechanism_wip_cap=self.module.MECHANISM_WIP_CAP_DEFAULT,
            force_mechanism_wip=False,
        ))

    def _stdout_of_release(self, who="A"):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = self._release(who=who)
        return code, buf.getvalue()

    # -------------------------------------------------------------- 核心

    def _readme_status(self, number="财务部#11"):
        line = [l for l in self.readme_path.read_text(encoding="utf-8").splitlines()
                if l.startswith(f"| {number} ")][0]
        return line.rstrip("|").rsplit("|", 1)[-1].strip()

    def test_已拆件时机器自动把README转闭环态(self):
        """`OP-0823-D` 改判：由「校验人有没有改」改成「机器代写」。

        真实存量复现：财务部#11 的回件 2026-08-06 到、§一 #291 早已
        `[S:done]`，README 状态列却停在「✅ 已推送」至 2026-08-21 未动。
        """
        self._write_readme("✅ 已推送 2026-08-06 01:30 UTC")
        self._write_queue(self._intake_row("291", "[S:done][D:业] ✅ 已拆件"))
        self.assertEqual(self._acquire(who="A"), 0)
        code, out = self._stdout_of_release(who="A")
        self.assertEqual(code, 0, f"机器代写成功就不该再拦人：{out}")
        status = self._readme_status()
        self.assertTrue(status.startswith(self.module.FOLLOWUP_SERIAL_CLOSED_PREFIX))
        self.assertIn("§一 #291", status, "须写明依据哪条入信行")
        self.assertIn("✅ 已推送 2026-08-06 01:30 UTC", status,
                      "原状态不得被覆盖丢失——这一格没有别处的副本")
        self.assertIn("财务部#11", out)

    def test_自动转态后闸对该收信人放行(self):
        self._write_readme("✅ 已推送 2026-08-06 01:30 UTC")
        self._write_queue(self._intake_row("291", "[S:done][D:业] ✅ 已拆件"))
        self.assertEqual(self._acquire(who="A"), 0)
        self.assertEqual(self._release(who="A"), 0)
        import zhuopin_platform.shared_tools.followup_gate as fg
        self.assertTrue(fg.is_closed_status(self._readme_status()),
                        "「转态 → 闭环 → 开闸」必须一次走完，不分两步")

    def test_重跑幂等不会把闭环态再写一层(self):
        self._write_readme("✅ 已推送 2026-08-06 01:30 UTC")
        self._write_queue(self._intake_row("291", "[S:done][D:业] ✅ 已拆件"))
        self.assertEqual(self._acquire(who="A"), 0)
        self.assertEqual(self._release(who="A"), 0)
        once = self.readme_path.read_text(encoding="utf-8")
        self.assertEqual(self._acquire(who="A"), 0)
        self.assertEqual(self._release(who="A"), 0)
        self.assertEqual(self.readme_path.read_text(encoding="utf-8"), once)

    def test_写入后同步lastknown基准免得下次acquire误报绕锁(self):
        """#200 绕锁检测读的是 lastknown。机器合法写入却不更新它，下一次
        acquire 就会把我们自己的写入报成「被绕过锁直接改写」——一条我们
        亲手制造的假警报。"""
        self._write_readme("✅ 已推送 2026-08-06 01:30 UTC")
        self._write_queue(self._intake_row("291", "[S:done][D:业] ✅ 已拆件"))
        self.assertEqual(self._acquire(who="A"), 0)
        self.assertEqual(self._release(who="A"), 0)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.module.cmd_acquire(argparse.Namespace(
                file=self.module.FOLLOWUP_README_TARGET, who="B", note="",
                reserve=None, section=None, reserve_multi=None, domain=None,
            ))
        self.assertNotIn("绕过协议", buf.getvalue())

    def test_README锁被别人占用时不写也不装作没事(self):
        """机器代写是为了省掉人的手工步骤，**不是为了在失败时静默**。"""
        self._write_readme("✅ 已推送 2026-08-06 01:30 UTC")
        self._write_queue(self._intake_row("291", "[S:done][D:业] ✅ 已拆件"))
        self.assertEqual(self._acquire(who="A"), 0)
        self.assertEqual(self.module.cmd_acquire(argparse.Namespace(
            file=self.module.FOLLOWUP_README_TARGET, who="别人", note="正在拆件",
            reserve=None, section=None, reserve_multi=None, domain=None,
        )), 0)
        before = self.readme_path.read_text(encoding="utf-8")
        code, out = self._stdout_of_release(who="A")
        self.assertNotEqual(code, 0, "写不成必须拦，不得放行")
        self.assertEqual(self.readme_path.read_text(encoding="utf-8"), before)
        self.assertIn("别人", out, "须说清是被谁占着")
        self.assertIn("财务部#11", out, "须指名道姓说是哪封信没转成")

    def test_README已转闭环态即放行(self):
        self._write_readme("📥 已回件并回灌（2026-08-07 拆件巡逻）")
        self._write_queue(self._intake_row("291", "[S:done][D:业] ✅ 已拆件"))
        self.assertEqual(self._acquire(who="A"), 0)
        self.assertEqual(self._release(who="A"), 0)

    def test_闭环四态里的任一态都放行(self):
        for status in ("✅ **无需回复**（发出即闭环）", "📨 **已确认闭环 2026-08-10**",
                       "**❌ 已作废 · 9 月重写**"):
            with self.subTest(status=status):
                self._write_readme(status)
                self._write_queue(self._intake_row("291", "[S:done][D:业] ✅ 已拆件"))
                self.assertEqual(self._acquire(who="A"), 0)
                self.assertEqual(self._release(who="A"), 0)

    def test_入信行未拆件时不拦(self):
        """桥二治的是「拆完了忘转态」；「还没拆」是桥一那一侧的事。"""
        self._write_readme("✅ 已推送 2026-08-06 01:30 UTC")
        self._write_queue(self._intake_row("291", "[S:open][D:业] 待领"))
        self.assertEqual(self._acquire(who="A"), 0)
        self.assertEqual(self._release(who="A"), 0)

    def test_第九态不算闭环会被转成闭环态(self):
        self._write_readme("📨 回件已到，待拆件 2026-08-06T01:30:00Z（企微机器人自动标记）")
        self._write_queue(self._intake_row("291", "[S:done][D:业] ✅ 已拆件"))
        self.assertEqual(self._acquire(who="A"), 0)
        self.assertEqual(self._release(who="A"), 0)
        self.assertTrue(self._readme_status().startswith(
            self.module.FOLLOWUP_SERIAL_CLOSED_PREFIX))

    # -------------------------------------------- `OP-0823-D` 第九态溯源回指

    TEXT_FEEDBACK = (
        "财务部-tangyanping-回复-2026-08-10-文本反馈-"
        "7340bdb81dd43aaaafcfa502e3f74e75.md"
    )

    def _text_intake_row(self, row_id="323", status="[S:done][D:业] ✅ 已拆件"):
        return (
            f"| {row_id} | 企微反馈自动归档：tangyanping 发来文本反馈 | 财务专线 | "
            f"`7-外部文档/财务部/{self.TEXT_FEEDBACK}` | 核实 | {status} | "
            f"队列 | 2026-08-10 |\n"
        )

    def test_纯文字回件靠桥一写下的溯源回指被配上(self):
        """`OP-0823-D` 的第二条确定通道——**纯文字回件第一次进入桥二覆盖面**。

        它配不上 stem（主题段恒为「文本反馈」），README 行也没有 `目标文件：`
        标注；能配上，全靠桥一在回件到达那一刻把归档文件名写进了第九态单元格。
        """
        self.readme_path.write_text(
            "## 现有跟进信清单\n\n" + self.README_HEADER
            + f"| 财务部#11 | 2026-08-05 | 财务部 · 唐燕萍 | FI2 面板复核 | 尽快 | "
              f"📨 回件已到，待拆件 2026-08-10T02:00:00Z（企微机器人自动标记，"
              f"入信归档 `{self.TEXT_FEEDBACK}`） ━━━ 原状态 ━━━ ✅ 已推送 |\n",
            encoding="utf-8",
        )
        self._write_queue(self._text_intake_row())
        self.assertEqual(self._acquire(who="A"), 0)
        code, out = self._stdout_of_release(who="A")
        self.assertEqual(code, 0)
        self.assertTrue(self._readme_status().startswith(
            self.module.FOLLOWUP_SERIAL_CLOSED_PREFIX))
        self.assertIn("reply_arrived", self._readme_status(),
                      "须写明是靠哪条通道配上的")

    def test_溯源写的是另一份归档件时不认(self):
        """回指必须**逐字**对上，不能只看「这一行是第九态」。"""
        self.readme_path.write_text(
            "## 现有跟进信清单\n\n" + self.README_HEADER
            + "| 财务部#11 | 2026-08-05 | 财务部 · 唐燕萍 | FI2 面板复核 | 尽快 | "
              "📨 回件已到，待拆件 2026-08-10T02:00:00Z（入信归档 `另一份完全无关的.docx`） |\n",
            encoding="utf-8",
        )
        self._write_queue(self._text_intake_row())
        self.assertEqual(self._acquire(who="A"), 0)
        self.assertEqual(self._release(who="A"), 0)
        self.assertTrue(self._readme_status().startswith("📨 回件已到"),
                        "配不上就不动，绝不猜")

    def test_桥二不得按最新一封去配纯文字回件(self):
        """🔴 反例锁死：**桥二没有时间上下文**，绝不能跑桥一那条通道②。

        场景取自 2026-08-23 真身：`财务部#14` 的回件与 `财务部#15` 的发出
        同为一天。若桥二按「该部门最新一封已发出的信」去配，这条 7 月的
        `[S:done]` 入信行会把今天刚发出、根本还没人回的 `财务部#15` 自动
        闭环并开闸——**错得悄无声息**。
        """
        self.readme_path.write_text(
            "## 现有跟进信清单\n\n" + self.README_HEADER
            + "| 财务部#14 | 2026-08-22 | 财务部 · 唐燕萍 | 上一封 | 尽快 | "
              "📥 已回件并回灌（2026-08-23） |\n"
            + "| 财务部#15 | 2026-08-23 | 财务部 · 唐燕萍 | 今天刚发、还没人回 | 尽快 | "
              "✅ 已推送 2026-08-23 08:26 UTC |\n",
            encoding="utf-8",
        )
        self._write_queue(self._text_intake_row())
        self.assertEqual(self._acquire(who="A"), 0)
        self.assertEqual(self._release(who="A"), 0)
        self.assertEqual(self._readme_status("财务部#15"),
                         "✅ 已推送 2026-08-23 08:26 UTC",
                         "刚发出、还没人回的信绝不能被自动闭环")

    def test_文本反馈类入信配不上时不误拦(self):
        self._write_readme("✅ 已推送 2026-08-06 01:30 UTC")
        self._write_queue(self._text_intake_row())
        self.assertEqual(self._acquire(who="A"), 0)
        self.assertEqual(self._release(who="A"), 0)
        self.assertEqual(self._readme_status(), "✅ 已推送 2026-08-06 01:30 UTC")

    def test_README行未带目标文件标注时判不出就不拦(self):
        self.readme_path.write_text(
            "## 现有跟进信清单\n\n" + self.README_HEADER
            + "| 财务部#3 | 2026-07-10 | 财务部 · 唐燕萍 | 规则定稿回灌 | 尽快 | ✅ 已推送 |\n",
            encoding="utf-8",
        )
        self._write_queue(self._intake_row("291", "[S:done][D:业] ✅ 已拆件"))
        self.assertEqual(self._acquire(who="A"), 0)
        self.assertEqual(self._release(who="A"), 0)

    # -------------------------------------------------------------- 逃生阀

    def test_本次触碰的行里写转态豁免即放行并留痕(self):
        self._write_readme("✅ 已推送 2026-08-06 01:30 UTC")
        self._write_queue(self._intake_row("291", "[S:done][D:业] ✅ 已拆件"))
        self.assertEqual(self._acquire(who="A"), 0)
        # 持锁窗口内改这一行，写上豁免理由。
        text = self.target_path.read_text(encoding="utf-8").replace(
            "✅ 已拆件 |", "✅ 已拆件 转态豁免：闭环依据待唐燕萍口头确认后再转 |", 1)
        self.target_path.write_text(text, encoding="utf-8")
        code, out = self._stdout_of_release(who="A")
        self.assertEqual(code, 0)
        self.assertIn("转态豁免", out, "放行必须留痕，不得静默")
        self.assertEqual(self._readme_status(), "✅ 已推送 2026-08-06 01:30 UTC",
                         "声明了豁免，机器就不该代写")

    def test_豁免只认本次持锁触碰过的行不认文件里的陈年旧字(self):
        """🔴 逃生阀必须一次一用。若按队列全文匹配，`转态豁免：` 写进这两份
        1.9 MB 文件任何一处就等于把整道门禁永久关掉，且此后无人会发现。

        改判后这条不变，只是**观测点换了**：从「是否拒绝 release」换成
        「机器是否照常代写」——陈年旧字不该有能力叫停机器。
        """
        self._write_readme("✅ 已推送 2026-08-06 01:30 UTC")
        self._write_queue(
            self._intake_row("291", "[S:done][D:业] ✅ 已拆件")
            + "| 99 | 一条陈年旧行 转态豁免：当年某个理由 | CC | `x` | y | "
              "[S:done][D:机] ✅ 完成 | 无 | 2026-07-01 |\n"
        )
        self.assertEqual(self._acquire(who="A"), 0)
        # 本次持锁期间**什么都没改** ⇒ 那句陈年豁免不该生效。
        self.assertEqual(self._release(who="A"), 0)
        self.assertTrue(self._readme_status().startswith(
            self.module.FOLLOWUP_SERIAL_CLOSED_PREFIX),
            "陈年豁免不得叫停机器代写")

    def test_持锁note里写转态豁免同样认(self):
        self._write_readme("✅ 已推送 2026-08-06 01:30 UTC")
        self._write_queue(self._intake_row("291", "[S:done][D:业] ✅ 已拆件"))
        self.assertEqual(self.module.cmd_acquire(argparse.Namespace(
            file=self.module.DEFAULT_TARGET, who="A",
            note="转态豁免：本次只改机制行，README 归拆件班转", reserve=None,
            section=None, reserve_multi=None, domain=None,
        )), 0)
        self.assertEqual(self._release(who="A"), 0)
        self.assertEqual(self._readme_status(), "✅ 已推送 2026-08-06 01:30 UTC")

    # ------------------------------------------------------ 双文件与降级

    def test_两份队列文件逐份解析后合并(self):
        """入信行落在业务场景文件时同样要被看见。🔴 不得先拼接文本再解析
        ——`_split_live_sections` 同名 label 后写覆盖先写，拼接会把第一份的
        §一 静默顶掉（队列 #312 缺口一踩过一模一样的坑）。"""
        self._write_readme("✅ 已推送 2026-08-06 01:30 UTC")
        self._write_queue()  # 机制环境文件里没有入信行
        self.business_path.write_text(
            self._queue_text(self._intake_row("291", "[S:done][D:业] ✅ 已拆件")),
            encoding="utf-8",
        )
        self.assertEqual(self._acquire(who="A"), 0)
        self.assertEqual(self._release(who="A"), 0)
        self.assertTrue(self._readme_status().startswith(
            self.module.FOLLOWUP_SERIAL_CLOSED_PREFIX),
            "业务场景文件里的入信行同样要被看见——看不见就不会转态")

    def test_权威模块缺失时fail_loud而不是静默跳过(self):
        self._write_readme("✅ 已推送 2026-08-06 01:30 UTC")
        queue_texts = {"queue.md": self._queue_text(
            self._intake_row("291", "[S:done][D:业] ✅ 已拆件"))}
        with unittest.mock.patch.object(self.module, "followup_gate", None):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                violations, notes = self.module._auto_sync_followup_reply_state(
                    queue_texts, self.repo_root, [], "A")
        self.assertEqual((violations, notes), ([], []))
        self.assertIn("未能加载", buf.getvalue(), "降级必须打印，不得无声无息")


class HoldConsistencyValidationTests(unittest.TestCase):
    """队列 #258（接管 #294 修法⑵）：release 时对队列暂缓结论与 README
    跟进信状态的交叉一致性校验（⑥）。

    白盒方式，同 ReleaseStructuralValidationTests：monkeypatch
    REPO_ROOT/DEFAULT_TARGET/FOLLOWUP_README_TARGET 指向本用例专属临时
    目录，同一 repo_root 下同时放队列文件与 README 文件。
    """

    SECTION_ONE_HEADER = (
        "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|------|--------|-------------|----------|------|--------|------|\n"
    )
    SECTION_FOUR_HEADER = (
        "| # | 事项 | 等谁 | 截止 |\n"
        "|---|------|------|------|\n"
    )
    SECTION_TWO_HEADER = (
        "| 批次 | 文件清单 | 建议 message | 状态 |\n"
        "|------|---------|--------------|------|\n"
    )
    README_HEADER = (
        "| 编号 | 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |\n"
        "|--------|------|--------|---------|---------|---------|\n"
    )

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmpdir.name)
        self.module = _load_module()
        self.module.REPO_ROOT = self.repo_root
        self.module.DEFAULT_TARGET = "queue.md"
        self.module.FOLLOWUP_README_TARGET = "readme.md"
        # 队列 #315：见 ReleaseStructuralValidationTests.setUp 同款注释。
        self.module.QUEUE_MECHANISM_PATH_REL = "queue.md"
        self.module.QUEUE_BUSINESS_PATH_REL = "queue-business.md"
        self.module.QUEUE_LOCK_ANCHOR = "queue.md"
        self.target_path = self.repo_root / "queue.md"
        self.readme_path = self.repo_root / "readme.md"

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write_queue(self, section_one_rows="", section_four_rows="", hwm_one=200, hwm_four=40):
        text = (
            f"> **编号高水位线：§一 #{hwm_one} ｜ §四 #{hwm_four}**（说明文字）\n\n"
            "## 一、任务看板\n\n" + self.SECTION_ONE_HEADER + section_one_rows +
            "\n## 二、待 commit 批次（CC 取活销行）\n\n" + self.SECTION_TWO_HEADER +
            "\n## 三、口径冻结标（重梳期防在途建造撞车）\n\n"
            "| 域/场景 | 冻结原因 | 挂标 | 解除条件 |\n"
            "|---------|---------|------|---------|\n"
            "\n## 四、需 Shao Peishen 的动作（例外与拍板）\n\n" +
            self.SECTION_FOUR_HEADER + section_four_rows
        )
        self.target_path.write_text(text, encoding="utf-8")

    def _write_readme(self, rows=""):
        text = "## 现有跟进信清单\n\n" + self.README_HEADER + rows
        self.readme_path.write_text(text, encoding="utf-8")

    def _acquire(self, who="A", reserve=None, section=None):
        ns = argparse.Namespace(
            file=self.module.DEFAULT_TARGET, who=who, note="",
            reserve=reserve, section=section, reserve_multi=None, domain=None,
        )
        return self.module.cmd_acquire(ns)

    def _release(self, who=""):
        ns = argparse.Namespace(
            file=self.module.DEFAULT_TARGET, who=who,
            mechanism_wip_cap=self.module.MECHANISM_WIP_CAP_DEFAULT,
            force_mechanism_wip=False,
        )
        return self.module.cmd_release(ns)

    def test_hold_row_with_readme_still_pending_blocks_release(self):
        """正向核心场景（#150 真实事故复现）：队列行含暂缓关键词+反引号
        文件名引用，README 对应行仍是「🆕 待发」——release 必须被拒绝。"""
        self._write_readme(
            "| 采购部#10 | 2026-07-29 | 采购部 · 姚祖怡 | 判例包 → 目标文件：`某跟进信.md` | 不急 | 🆕 待发 |\n"
        )
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        new_row = "| 201 | 测试 | CC | `某跟进信.md` | 产出 | 本行拍板暂不发，待前信闭环 | 无 | 2026-08-07 |\n"
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        result = self._release(who="A")
        self.assertNotEqual(result, 0)

    def test_hold_row_with_readme_already_non_pending_passes(self):
        """README 已同步非待发（如 ⏳待你审）——正常放行。"""
        self._write_readme(
            "| 采购部#10 | 2026-07-29 | 采购部 · 姚祖怡 | 判例包 → 目标文件：`某跟进信.md` | 不急 | ⏳ 待你审 |\n"
        )
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        new_row = "| 201 | 测试 | CC | `某跟进信.md` | 产出 | 本行拍板暂不发，待前信闭环 | 无 | 2026-08-07 |\n"
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        self.assertEqual(self._release(who="A"), 0)

    def test_hold_row_without_readme_match_passes(self):
        """README 中找不到匹配行——判不出，不拦（design.md 决策点3）。"""
        self._write_readme()  # 空表
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        new_row = "| 201 | 测试 | CC | `不存在的信.md` | 产出 | 暂不发 | 无 | 2026-08-07 |\n"
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        self.assertEqual(self._release(who="A"), 0)

    def test_reverse_readme_already_sent_neither_blocks_nor_warns(self):
        """反向：README 已是"已推送"类终态，队列行仍称暂缓——**既不拒绝、
        也不再打印告警**（队列 #324 退休后的断言，2026-08-17）。

        原行为是"仅告警不阻断"；该告警半边已按协议〇.9 措施 B 一进一出退休
        （它在现网唯一的命中 #150 恰是 spec 自己承认合法的写法，一条只在合法
        写法上响的规则产出的是噪音而非约束）。此处断言 stdout 不含该告警，
        使"退休"这件事被钉住——否则代码删了、下次有人凭印象加回来也没人拦。
        """
        self._write_readme(
            "| 采购部#10 | 2026-07-29 | 采购部 · 姚祖怡 | 判例包 → 目标文件：`某跟进信.md` | 不急 | ✅ 已推送 2026-08-06 01:30 UTC |\n"
        )
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        new_row = "| 201 | 测试 | CC | `某跟进信.md` | 产出 | 本行拍板暂不发（事后追述） | 无 | 2026-08-17 |\n"
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A")
        self.assertEqual(result, 0)
        self.assertNotIn("疑似终态已推送", buf.getvalue())
        self.assertNotIn("仍称暂缓", buf.getvalue())

    def test_hold_keyword_without_filename_reference_does_not_trigger(self):
        """仅命中暂缓关键词、无反引号文件名引用——不触发本校验。"""
        self._write_readme(
            "| 采购部#10 | 2026-07-29 | 采购部 · 姚祖怡 | 判例包 → 目标文件：`某跟进信.md` | 不急 | 🆕 待发 |\n"
        )
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        new_row = "| 201 | 测试 | CC | 无 | 产出 | 暂不发 | 无 | 2026-08-07 |\n"
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        self.assertEqual(self._release(who="A"), 0)

    def test_filename_reference_without_hold_keyword_does_not_trigger(self):
        """仅有反引号文件名引用、无暂缓关键词——不触发本校验（即便 README
        仍待发）。"""
        self._write_readme(
            "| 采购部#10 | 2026-07-29 | 采购部 · 姚祖怡 | 判例包 → 目标文件：`某跟进信.md` | 不急 | 🆕 待发 |\n"
        )
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        new_row = "| 201 | 测试 | CC | `某跟进信.md` | 产出 | 待领 | 无 | 2026-08-07 |\n"
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        self.assertEqual(self._release(who="A"), 0)

    def test_section_four_hold_row_uses_topic_column_as_status(self):
        """§四 无独立状态列，检测应作用于"事项"列本身。"""
        self._write_readme(
            "| 采购部#10 | 2026-07-29 | 采购部 · 姚祖怡 | 判例包 → 目标文件：`某跟进信.md` | 不急 | 🆕 待发 |\n"
        )
        self._write_queue(hwm_four=40)
        self.assertEqual(self._acquire(who="A", reserve=1, section="四"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        new_row = "| 41 | 暂不发`某跟进信.md`，待其闭环 | Shao Peishen | 不急 |\n"
        text = text.replace(self.SECTION_FOUR_HEADER, self.SECTION_FOUR_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        result = self._release(who="A")
        self.assertNotEqual(result, 0)

    def test_150_real_incident_row_recreated_passes_silently(self):
        """历史兼容核对固化（design.md「历史兼容核对」）：#150 真实事故场景
        重现——README 已终态推送、队列行称暂缓，放行。

        队列 #324（2026-08-17）：原断言是"仅告警放行"，反向告警退休后改为
        **静默放行**。#150 这一行正是本能力 spec 明文列为合法的写法（事故后
        新增文本、如实记录"本应暂缓却已被机制误发"的经过），它同时也是该告警
        在现网队列上唯一的命中——这正是退休它的第一条理由。"""
        self._write_readme(
            "| 采购部（未发，不编号） | 2026-07-29 | 采购部 · 姚祖怡 | "
            "批2引擎最后一项口径判例包 → 目标文件："
            "`采购部-姚祖怡-跟进-2026-07-29-批2上月未齐套跨月占用判例批改.md` | "
            "不卡时间 | ✅ 已推送 2026-08-06 01:30 UTC |\n"
        )
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        new_row = (
            "| 201 | #150 事后追述 | CC | "
            "`采购部-姚祖怡-跟进-2026-07-29-批2上月未齐套跨月占用判例批改.md` | "
            "产出 | 本行此前拍板暂不发，该信已因机制误判自动推送，信不可撤回 | 无 | 2026-08-07 |\n"
        )
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        self.assertEqual(self._release(who="A"), 0)

    # ---- 队列 #324（2026-08-17）：⑥ 扫描面收窄到「当前结论段」-------------

    def test_leading_conclusion_segment_splits_on_separator(self):
        """`_leading_conclusion_segment` 单元行为：有 `━━━` 取首段，
        无 `━━━` 原样返回。"""
        self.assertEqual(
            self.module._leading_conclusion_segment("当前结论 ━━━ 以下为原文 ━━━ 历史"),
            "当前结论 ",
        )
        self.assertEqual(self.module._leading_conclusion_segment("没有分隔符"), "没有分隔符")
        self.assertEqual(self.module._leading_conclusion_segment(""), "")

    def test_hold_keyword_only_in_history_segment_passes(self):
        """🔴 #52 误报回归（本次收窄的全部理由）：暂缓关键词只出现在 `━━━`
        之后的历史段、当前结论段是"已闭环"类结论，而行内点名了一封 README
        仍为 `🆕 待发` 的信——收窄前拒绝（真实误报，2026-08-10 业务总线），
        收窄后应放行。"""
        self._write_readme(
            "| 采购部#13 | 2026-08-10 | 采购部 · 姚祖怡 | 判例包 → 目标文件：`某跟进信.md` | 不急 | 🆕 待发 |\n"
        )
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        new_row = (
            "| 201 | 测试 | CC | `某跟进信.md` | 产出 | "
            "✅ 本行已完全闭环，判例包已回件并回灌 "
            "━━━ 以下为 2026-08-05 原文 ━━━ 07-29 判例包仍被压着，暂不发 "
            "━━━ 以下为 2026-08-07 原文 ━━━ 该件继续暂缓 "
            "| 无 | 2026-08-17 |\n"
        )
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        self.assertEqual(self._release(who="A"), 0,
                         "暂缓字样只在历史段时不应触发 ⑥（#52 真实误报）")

    def test_hold_keyword_in_leading_segment_still_blocks(self):
        """收窄不得削掉正向拦截力：暂缓结论写在**当前结论段**、README 仍
        `🆕 待发` ⇒ 照旧拒绝（即便该格另有大量历史沉积）。"""
        self._write_readme(
            "| 采购部#13 | 2026-08-10 | 采购部 · 姚祖怡 | 判例包 → 目标文件：`某跟进信.md` | 不急 | 🆕 待发 |\n"
        )
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        new_row = (
            "| 201 | 测试 | CC | `某跟进信.md` | 产出 | "
            "本行拍板：该信暂不发，待前信闭环 "
            "━━━ 以下为 2026-08-05 原文 ━━━ 当时判定可发 "
            "| 无 | 2026-08-17 |\n"
        )
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        self.assertNotEqual(self._release(who="A"), 0)

    def test_section_four_filename_in_history_segment_not_paired(self):
        """§四 的文件名提取同步收窄到首段（决策点 3：§四 关键词与文件名本就
        同格，不同步会自相矛盾）——首段有暂缓字样但文件名在历史段 ⇒ 提取不到
        文件名，不触发。"""
        self._write_readme(
            "| 采购部#13 | 2026-08-10 | 采购部 · 姚祖怡 | 判例包 → 目标文件：`某跟进信.md` | 不急 | 🆕 待发 |\n"
        )
        self._write_queue(hwm_four=40)
        self.assertEqual(self._acquire(who="A", reserve=1, section="四"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        new_row = (
            "| 41 | 本项暂缓，等口径定了再说 "
            "━━━ 以下为原文 ━━━ 当时点名的是 `某跟进信.md` "
            "| Shao Peishen | 不急 |\n"
        )
        text = text.replace(self.SECTION_FOUR_HEADER, self.SECTION_FOUR_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        self.assertEqual(self._release(who="A"), 0)

    def test_cell_without_separator_behaves_exactly_as_before(self):
        """无 `━━━` 的单元格行为与收窄前逐字一致——既有短单元格（本项目绝
        大多数行）不因本次改动产生任何差异。"""
        self._write_readme(
            "| 采购部#10 | 2026-07-29 | 采购部 · 姚祖怡 | 判例包 → 目标文件：`某跟进信.md` | 不急 | 🆕 待发 |\n"
        )
        self._write_queue(hwm_one=200)
        self.assertEqual(self._acquire(who="A", reserve=1, section="一"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        new_row = "| 201 | 测试 | CC | `某跟进信.md` | 产出 | 本行拍板暂不发，待前信闭环 | 无 | 2026-08-17 |\n"
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + new_row, 1)
        self.target_path.write_text(text, encoding="utf-8")

        self.assertNotEqual(self._release(who="A"), 0)


class DualFileRoutingTests(unittest.TestCase):
    """队列 #315（openspec 变更包 `queue-dual-file-split`）：队列系统双文件
    路由——`_resolve_append_target`/`_iter_queue_paths`/`_resolve_queue_
    path_for_domain`/幽灵副本检测（决策点3/4/5）。白盒方式：monkeypatch
    REPO_ROOT/DEFAULT_TARGET/QUEUE_MECHANISM_PATH_REL/QUEUE_BUSINESS_
    PATH_REL/QUEUE_LOCK_ANCHOR 指向本用例专属临时目录，与既有
    ReleaseStructuralValidationTests 同一惯例。"""

    SECTION_ONE_HEADER = (
        "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|------|--------|-------------|----------|------|--------|------|\n"
    )
    SECTION_TWO_HEADER = (
        "| 批次 | 文件清单 | 建议 message | 状态 |\n"
        "|------|---------|--------------|------|\n"
    )

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmpdir.name)
        self.module = _load_module()
        self.module.REPO_ROOT = self.repo_root
        self.module.DEFAULT_TARGET = "queue.md"
        self.module.QUEUE_MECHANISM_PATH_REL = "queue-mech.md"
        self.module.QUEUE_BUSINESS_PATH_REL = "queue-biz.md"
        self.module.QUEUE_LOCK_ANCHOR = "queue-mech.md"
        self.mech_path = self.repo_root / "queue-mech.md"
        self.biz_path = self.repo_root / "queue-biz.md"

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write(self, path: Path, hwm_one=300, section_one_rows="", section_two_rows=""):
        text = (
            f"> **编号高水位线：§一 #{hwm_one} ｜ §四 #40**（说明）\n\n"
            "## 一、任务看板\n\n" + self.SECTION_ONE_HEADER + section_one_rows +
            "\n## 二、待 commit 批次（CC 取活销行）\n\n" + self.SECTION_TWO_HEADER + section_two_rows
        )
        path.write_text(text, encoding="utf-8")

    # ---- _resolve_append_target ----

    def test_resolve_append_target_section_one_domain_ji(self):
        target, used_default = self.module._resolve_append_target("一", "机")
        self.assertEqual(target, "queue-mech.md")
        self.assertFalse(used_default)

    def test_resolve_append_target_section_one_domain_ye(self):
        target, used_default = self.module._resolve_append_target("一", "业")
        self.assertEqual(target, "queue-biz.md")
        self.assertFalse(used_default)

    def test_resolve_append_target_no_domain_defaults_to_mechanism(self):
        target, used_default = self.module._resolve_append_target("二", None)
        self.assertEqual(target, "queue-mech.md")
        self.assertTrue(used_default)

    def test_resolve_append_target_section_four_ignores_domain(self):
        target, used_default = self.module._resolve_append_target("四", "业")
        self.assertEqual(target, "queue-mech.md")
        self.assertFalse(used_default)

    # ---- _resolve_queue_path_for_domain / _iter_queue_paths ----

    def test_resolve_queue_path_for_domain_illegal_value_raises(self):
        with self.assertRaises(ValueError):
            self.module._resolve_queue_path_for_domain("其它")

    def test_iter_queue_paths_returns_both(self):
        self.assertEqual(
            self.module._iter_queue_paths(), ["queue-mech.md", "queue-biz.md"],
        )

    # ---- cmd_append_row 端到端：域路由落到正确物理文件 ----

    def test_append_row_domain_ye_lands_in_business_file(self):
        self._write(self.mech_path)
        self._write(self.biz_path)
        ns = argparse.Namespace(
            file=self.module.DEFAULT_TARGET, section="一", number="301",
            cell=["新业务任务", "CC", "无", "无", "[S:open][D:业] 待领", "无", "2026-08-11"],
            domain="业",
        )
        self.assertEqual(self.module.cmd_append_row(ns), 0)
        self.assertIn("新业务任务", self.biz_path.read_text(encoding="utf-8"))
        self.assertNotIn("新业务任务", self.mech_path.read_text(encoding="utf-8"))

    def test_append_row_no_domain_defaults_to_mechanism_file(self):
        self._write(self.mech_path)
        self._write(self.biz_path)
        ns = argparse.Namespace(
            file=self.module.DEFAULT_TARGET, section="一", number="301",
            cell=["未声明域任务", "CC", "无", "无", "[S:open][D:机] 待领", "无", "2026-08-11"],
            domain=None,
        )
        self.assertEqual(self.module.cmd_append_row(ns), 0)
        self.assertIn("未声明域任务", self.mech_path.read_text(encoding="utf-8"))
        self.assertNotIn("未声明域任务", self.biz_path.read_text(encoding="utf-8"))

    def test_append_row_section_two_business_batch(self):
        self._write(self.mech_path)
        self._write(self.biz_path)
        ns = argparse.Namespace(
            file=self.module.DEFAULT_TARGET, section="二", number=None,
            cell=["B-测试批次", "`queue-biz.md`", "说明", "待处理"],
            domain="业",
        )
        self.assertEqual(self.module.cmd_append_row(ns), 0)
        self.assertIn("B-测试批次", self.biz_path.read_text(encoding="utf-8"))
        self.assertNotIn("B-测试批次", self.mech_path.read_text(encoding="utf-8"))

    def test_append_row_explicit_file_override_bypasses_routing(self):
        """显式 --file 覆盖（如跟进信 README 场景）不触发域路由，行为与
        拆分前完全一致——这里用一个第三方文件验证不受 --domain 影响。"""
        other = self.repo_root / "other.md"
        self._write(other)
        ns = argparse.Namespace(
            file="other.md", section="一", number="301",
            cell=["旁路任务", "CC", "无", "无", "[S:open][D:机] 待领", "无", "2026-08-11"],
            domain=None,
        )
        self.assertEqual(self.module.cmd_append_row(ns), 0)
        self.assertIn("旁路任务", other.read_text(encoding="utf-8"))

    # ---- 跨文件编号碰撞检测（决策点2：单一编号空间） ----

    def test_reserve_collision_detected_across_both_files(self):
        """号已被业务文件占用时，即便机制文件本身干净，预留也须拒绝——
        编号空间是单一的，不能只查目标文件自己。"""
        self._write(self.mech_path, hwm_one=300)
        self._write(
            self.biz_path, hwm_one=300,
            section_one_rows="| 301 | 已存在于业务文件 | CC | 无 | 无 | 待领 | 无 | 2026-08-10 |\n",
        )
        with self.assertRaises(self.module.ReserveFailedError):
            self.module._reserve_ids(
                "queue-mech.md", "一", 1,
                extra_collision_texts=[self.biz_path.read_text(encoding="utf-8")],
            )

    def test_reserve_no_collision_when_number_unused_in_either_file(self):
        self._write(self.mech_path, hwm_one=300)
        self._write(self.biz_path, hwm_one=300)
        result = self.module._reserve_ids(
            "queue-mech.md", "一", 1,
            extra_collision_texts=[self.biz_path.read_text(encoding="utf-8")],
        )
        self.assertEqual(result, [301])

    # ---- acquire/release 队列系统模式：双文件快照与结构校验 ----

    def test_acquire_release_queue_system_mode_validates_both_files(self):
        self._write(self.mech_path, hwm_one=300)
        self._write(self.biz_path, hwm_one=300)
        ns_acquire = argparse.Namespace(
            file=self.module.DEFAULT_TARGET, who="A", note="",
            reserve=None, section=None, reserve_multi=None, domain=None,
        )
        self.assertEqual(self.module.cmd_acquire(ns_acquire), 0)
        ns_release = argparse.Namespace(
            file=self.module.DEFAULT_TARGET, who="A",
            mechanism_wip_cap=self.module.MECHANISM_WIP_CAP_DEFAULT,
            force_mechanism_wip=False,
        )
        self.assertEqual(self.module.cmd_release(ns_release), 0)
        # release 后两份文件均应有各自的 lastknown 基准。
        self.assertTrue(self.module._lastknown_path("queue-mech.md").exists())
        self.assertTrue(self.module._lastknown_path("queue-biz.md").exists())

    def test_release_reports_violations_from_either_file_with_path_prefix(self):
        self._write(self.mech_path, hwm_one=300)
        self._write(self.biz_path, hwm_one=300)
        ns_acquire = argparse.Namespace(
            file=self.module.DEFAULT_TARGET, who="A", note="",
            reserve=None, section=None, reserve_multi=None, domain=None,
        )
        self.assertEqual(self.module.cmd_acquire(ns_acquire), 0)
        # 业务文件里加一行列数不对的行（触发①列数校验）。
        text = self.biz_path.read_text(encoding="utf-8")
        bad_row = "| 301 | 列数不对的行 | CC |\n"
        text = text.replace(self.SECTION_ONE_HEADER, self.SECTION_ONE_HEADER + bad_row, 1)
        self.biz_path.write_text(text, encoding="utf-8")
        ns_release = argparse.Namespace(
            file=self.module.DEFAULT_TARGET, who="A",
            mechanism_wip_cap=self.module.MECHANISM_WIP_CAP_DEFAULT,
            force_mechanism_wip=False,
        )
        self.assertNotEqual(self.module.cmd_release(ns_release), 0)

    # ---- 幽灵副本检测（决策点5，队列 #315 子项⑥，2026-08-10 #321 真实事故）----

    def test_detect_shadow_copy_returns_none_when_repo_root_equals_script_dir(self):
        # 本用例 __file__ 就在 REPO_ROOT 下（白盒直接调用），samefile 应为
        # True，不触发误报——这是最常见的"主工作区内运行"场景。
        self.mech_path.write_text("内容\n", encoding="utf-8")
        result = self.module._detect_shadow_copy("queue-mech.md")
        self.assertIsNone(result)

    # ---- 锁域分裂止血：绝对路径归一化判定（队列 #315 apply 中途追加，
    # Shao Peishen 2026-08-11 现时风险提醒——企微机器人 SubprocessQueueEdit
    # Lock 传绝对路径，字面量比较永不命中，双文件路由从不触发）----

    def test_absolute_path_to_default_target_is_recognized_as_queue_system(self):
        absolute = str(self.repo_root / "queue.md")
        self.assertTrue(self.module._is_queue_system_target(absolute))

    def test_absolute_path_to_mechanism_file_is_recognized_as_queue_system(self):
        absolute = str(self.repo_root / "queue-mech.md")
        self.assertTrue(self.module._is_queue_system_target(absolute))

    def test_absolute_path_to_business_file_is_recognized_as_queue_system(self):
        absolute = str(self.repo_root / "queue-biz.md")
        self.assertTrue(self.module._is_queue_system_target(absolute))

    def test_absolute_path_to_unrelated_file_is_not_queue_system(self):
        absolute = str(self.repo_root / "跟进信README.md")
        self.assertFalse(self.module._is_queue_system_target(absolute))

    # ---- 队列 §一 #420：edit-row／append-row 不共锁（2026-08-28 修）----
    #
    # 🔴 **不变式（本组用例钉死的那一条）**：两份物理队列文件共用**同一把**
    # 锁，锚点恒为 `QUEUE_LOCK_ANCHOR`（机制环境文件）。故「A 持锁时 B 以
    # `--domain 业` 写业务场景文件」必须被拒——修复前它会通过，且只打印一行
    # 「ℹ 本次为无锁写入」。
    #
    # **根因（实测得来，不是推演）**：`_is_queue_system_target` 对**相对**路径
    # 走 `Path(file_arg).resolve()` —— `Path.resolve()` 按**进程 CWD** 解析，
    # 而本项目全线用「仓库根相对路径」。于是 CWD ≠ REPO_ROOT 时（worktree
    # 会话、`0-学习与工具/` 下直接跑、任何 `cd` 过的脚本）该判定静默返回
    # False，锁锚点退化成「目标文件自己」：`--domain 机` 算出的恰是机制文件
    # 自己的锁 ⇒ **碰巧仍是对的**；`--domain 业` 算出 `…-业务场景.md.editlock`
    # ⇒ 那个文件**从来不存在** ⇒ 每次都走「无锁写入」分支。
    # 🔑 与本波次同族：**判定「正常返回」了，只是它看的根本不是那把锁**——
    # 错误不产生任何信号，而机制侧因为碰巧对，掩盖了业务侧一直失效。
    #
    # ⚠️ 本组用例本身即 CWD 独立性的证据：REPO_ROOT 被 monkeypatch 到临时
    # 目录，而 pytest 的 CWD 是 `0-学习与工具/`，两者恒不相等。

    def test_相对路径的机制文件也应判为队列系统本体(self):
        """反例守卫：修复前此处为 False（`Path('queue-mech.md').resolve()`
        解到 CWD 下），机制侧碰巧不出事只因锚点与目标同名。"""
        self.assertTrue(self.module._is_queue_system_target("queue-mech.md"))

    def test_相对路径的业务文件也应判为队列系统本体(self):
        self.assertTrue(self.module._is_queue_system_target("queue-biz.md"))

    def test_相对路径的无关文件仍不是队列系统本体(self):
        """反例：修得过头会把任何相对路径都当队列系统——必须仍为 False。"""
        self.assertFalse(self.module._is_queue_system_target("跟进信README.md"))

    def _hold_shared_lock(self, who: str = "A", minutes_ago: float = 1.0) -> Path:
        """在**锚点**（机制环境文件）上造一把新鲜锁，模拟他人持锁。"""
        held_since = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        lock_path = self.repo_root / (self.module.QUEUE_LOCK_ANCHOR + ".editlock")
        lock_path.write_text(
            json.dumps({"who": who, "note": "在办", "held_since": held_since.isoformat()},
                       ensure_ascii=False),
            encoding="utf-8",
        )
        return lock_path

    def _edit_ns(self, domain: str, who: str | None = None) -> argparse.Namespace:
        return argparse.Namespace(
            file=self.module.DEFAULT_TARGET, section="一", number="301",
            domain=domain, who=who,
            set=["状态=[S:done] 已办"], append=None, append_sep="；",
            changes_json=None, stdin_json=False,
        )

    def _append_ns(self, domain: str, who: str | None = None) -> argparse.Namespace:
        return argparse.Namespace(
            file=self.module.DEFAULT_TARGET, section="一", number="302",
            domain=domain, who=who,
            cell=["新行", "CC", "无", "无", "[S:open][D:业] 待领", "无", "2026-08-28"],
        )

    def _seed_both(self):
        row = ("| 301 | 既有业务行 | CC | 无 | 无 | [S:open][D:业] 待领 | 无 | "
               "2026-08-28 |" + chr(10))
        self._write(self.mech_path, section_one_rows=row)
        self._write(self.biz_path, section_one_rows=row)

    def test_他人持共用锁时edit_row域业必须被拒(self):
        """🔴 **本行的核心断言**：修复前返回 0 并写入成功（只打一行"无锁
        写入"）；修复后必须拒绝。"""
        self._seed_both()
        self._hold_shared_lock("A")
        before = self.biz_path.read_text(encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self.module.cmd_edit_row(self._edit_ns("业"))
        self.assertNotEqual(rc, 0, buf.getvalue())
        self.assertIn("未传 --who", buf.getvalue())
        self.assertEqual(self.biz_path.read_text(encoding="utf-8"), before)

    def test_他人持共用锁时append_row域业必须被拒(self):
        """#420 子项③：复核 `append-row --domain 业` 是否同病——实测同病。"""
        self._seed_both()
        self._hold_shared_lock("A")
        before = self.biz_path.read_text(encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self.module.cmd_append_row(self._append_ns("业"))
        self.assertNotEqual(rc, 0, buf.getvalue())
        self.assertIn("未传 --who", buf.getvalue())
        self.assertEqual(self.biz_path.read_text(encoding="utf-8"), before)

    def test_他人持共用锁时edit_row域机同样被拒(self):
        """对照组：机制侧修复前后都该被拒（它此前是"碰巧对"，不是"对"）。"""
        self._seed_both()
        self._hold_shared_lock("A")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self.module.cmd_edit_row(self._edit_ns("机"))
        self.assertNotEqual(rc, 0, buf.getvalue())

    def test_who与持锁人一致时域业照常写入(self):
        """反例：不得修成"业务侧一律拦死"——持锁人本人必须写得进去。"""
        self._seed_both()
        self._hold_shared_lock("A")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self.module.cmd_edit_row(self._edit_ns("业", who="A"))
        self.assertEqual(rc, 0, buf.getvalue())
        self.assertIn("[S:done] 已办", self.biz_path.read_text(encoding="utf-8"))
        self.assertNotIn("[S:done] 已办", self.mech_path.read_text(encoding="utf-8"))

    def test_陈旧锁下域业仍按无锁写入放行(self):
        """反例：陈旧锁等价于无锁——与 acquire 接管口径一致，本次不改。"""
        self._seed_both()
        self._hold_shared_lock("A", minutes_ago=self.module.STALE_MINUTES + 1)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self.module.cmd_edit_row(self._edit_ns("业"))
        self.assertEqual(rc, 0, buf.getvalue())
        self.assertIn("无锁写入", buf.getvalue())

    def test_无锁时域业仍放行不变成硬互斥(self):
        """反例：协议〇.7 是协作性质，本次**只修锁归属**，不把无锁写入改成
        阻断——那属改变全项目口径，须另走 openspec。"""
        self._seed_both()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self.module.cmd_edit_row(self._edit_ns("业"))
        self.assertEqual(rc, 0, buf.getvalue())
        self.assertIn("无锁写入", buf.getvalue())

    def test_业务场景文件不得产生第二把物理锁(self):
        """不变式的另一面：全程只应存在锚点那一个 `.editlock`；一旦业务文件
        旁出现同名锁文件，"共用一把锁"就已经名存实亡。"""
        self._seed_both()
        ns_acquire = argparse.Namespace(
            file=self.module.DEFAULT_TARGET, who="A", note="",
            reserve=None, section=None, reserve_multi=None, domain=None,
        )
        self.assertEqual(self.module.cmd_acquire(ns_acquire), 0)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.module.cmd_edit_row(self._edit_ns("业", who="A"))
            self.module.cmd_append_row(self._append_ns("业", who="A"))
        self.assertTrue((self.repo_root / "queue-mech.md.editlock").exists())
        self.assertFalse(
            (self.repo_root / "queue-biz.md.editlock").exists(),
            "业务场景文件旁出现了第二把物理锁——「两份共用一把锁」已名存实亡",
        )

    def test_acquire_with_absolute_path_to_old_pointer_file_routes_dual_file(self):
        """真实复现：企微机器人常驻服务当前仍以 `DEFAULT_QUEUE_RELATIVE_
        PATH`（旧指针文件相对路径）算出的绝对路径调用编辑锁 CLI——本用例
        验证即便调用方传的是这个"迁移前"的绝对路径，`cmd_acquire` 仍应
        正确识别为队列系统本体、双文件路由生效（锁锚定机制文件、两份内容
        文件都被读到快照里），而不是把它当成一个无关的普通共享文件。"""
        self._write(self.mech_path, hwm_one=300)
        self._write(self.biz_path, hwm_one=300)
        absolute_old_pointer = str(self.repo_root / "queue.md")
        ns = argparse.Namespace(
            file=absolute_old_pointer, who="A", note="",
            reserve=None, section=None, reserve_multi=None, domain=None,
        )
        self.assertEqual(self.module.cmd_acquire(ns), 0)
        lock_path = self.repo_root / "queue-mech.md.editlock"
        self.assertTrue(lock_path.exists(), "锁应锚定在机制文件，而非旧指针文件")
        ns_release = argparse.Namespace(
            file=absolute_old_pointer, who="A",
            mechanism_wip_cap=self.module.MECHANISM_WIP_CAP_DEFAULT,
            force_mechanism_wip=False,
        )
        self.assertEqual(self.module.cmd_release(ns_release), 0)


class ShadowCopyCrossWorktreeTests(unittest.TestCase):
    """幽灵副本检测的真实跨 worktree 复现（队列 #315 子项⑥，直接承接
    2026-08-10 #321 真实事故）——黑盒子进程方式，同 `EditLockCrossWorktree
    Tests` 惯例：脚本复制进真实 git 仓库 + linked worktree，`REPO_ROOT` 按
    `--git-common-dir` 恒定解析到主工作区，而 worktree 本地路径下若也存在
    同名文件，即为幽灵副本风险场景。"""

    MECH_REL = Path("1-转型规划") / "0-全景路线图" / "跨桌任务队列-机制环境.md"

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.main_root = Path(self._tmpdir.name) / "main"
        self.main_root.mkdir()
        self._git("init", "-q")
        self._git("config", "user.email", "test@example.com")
        self._git("config", "user.name", "Test")
        script_dir = self.main_root / "0-学习与工具"
        script_dir.mkdir()
        (script_dir / "工具-共享文档编辑锁.py").write_text(
            SCRIPT.read_text(encoding="utf-8"), encoding="utf-8"
        )
        # 与生产布局一致的嵌套路径——不 monkeypatch 常量，走脚本内建的
        # 隔离环境兜底桩（本用例不复制 zhuopin_platform 包，与
        # `EditLockCrossWorktreeTests` 同一取舍），验证兜底桩的路径常量
        # 与真实值一致（本次已同步修过，见模块顶部隔离桩定义）。
        (self.main_root / self.MECH_REL).parent.mkdir(parents=True)
        (self.main_root / self.MECH_REL).write_text("主工作区权威内容\n", encoding="utf-8")
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

    def test_status_warns_when_linked_worktree_has_divergent_local_copy(self):
        # linked worktree 本地也有一份同名文件（git checkout 出主工作区已
        # 提交的版本）——先验证内容相同时不误报。
        r_clean = run_at(self._tool(self.linked_root), "status")
        self.assertNotIn("幽灵副本", r_clean.stdout)

        # 复现 #321：linked worktree 里的本地副本被直接改写（通用 Edit
        # 工具按 worktree 本地路径改的效果），与主工作区权威内容产生分歧
        # ——而锁 CLI 恒定解析主工作区，两者是两个不同的物理文件。
        (self.linked_root / self.MECH_REL).write_text(
            "worktree 本地被直接改写的内容\n", encoding="utf-8",
        )
        r = run_at(self._tool(self.linked_root), "status")
        self.assertIn("幽灵副本", r.stdout)
        self.assertIn(str((self.main_root / self.MECH_REL).resolve()), r.stdout)


class ClaudeProgressOpenItemTests(unittest.TestCase):
    """判据 J4（队列 §四 #80 / 派单件 OP-0821-C）：根 CLAUDE.md 顶部进度段
    新增条目含未闭合措辞却未点名队列行时，release 必须被拒绝。

    白盒方式，同 FollowupReadmeStructuralValidationTests：monkeypatch
    REPO_ROOT 指向本用例专属临时目录，不触碰真实生产 CLAUDE.md。
    """

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmpdir.name)
        self.module = _load_module()
        self.module.REPO_ROOT = self.repo_root
        self.target_path = self.repo_root / self.module.CLAUDE_PROGRESS_TARGET

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write(self, entry_lines):
        parts = [
            "# CLAUDE.md — 测试夹具", "",
            "> **当前进度**：历史进度已迁 CHANGELOG。", ">",
        ]
        for line in entry_lines:
            parts += [line, ">"]
        parts += [
            "> **📦 更早条目已迁 CHANGELOG**（2026-08-05，队列 #253）：原文保留。",
            "", "---", "", "## 1. 正文", "",
        ]
        self.target_path.write_text("\n".join(parts), encoding="utf-8")

    def _acquire(self, who="A"):
        ns = argparse.Namespace(
            file=self.module.CLAUDE_PROGRESS_TARGET, who=who, note="",
            reserve=None, section=None, reserve_multi=None, domain=None,
        )
        return self.module.cmd_acquire(ns)

    def _release(self, who=""):
        ns = argparse.Namespace(
            file=self.module.CLAUDE_PROGRESS_TARGET, who=who,
            mechanism_wip_cap=self.module.MECHANISM_WIP_CAP_DEFAULT,
            force_mechanism_wip=False,
        )
        return self.module.cmd_release(ns)

    def _lock_released(self) -> bool:
        raw = json.loads(
            (self.repo_root / (self.module.CLAUDE_PROGRESS_TARGET + ".editlock")
             ).read_text(encoding="utf-8")
        )
        return bool(raw.get("released"))

    # ── 判据本身 ──────────────────────────────────────────────────────────

    def test_零改动可正常release(self):
        self._write(["> **甲（2026-08-01，CC）**：已全部完成。"])
        self.assertEqual(self._acquire(), 0)
        self.assertEqual(self._release(who="A"), 0)

    def test_新增条目含未结且未点名队列行即拒绝release(self):
        """派单件反例单测⑶：「未结」必须触发 J4。

        这个词是 2026-08-21 逐行读原文才发现词表漏掉的两个之一（另一个是
        「未接线」）——**词表只能当筛子、不能当判官**，本用例把补进去的这
        两个锁死，防止后续有人"精简"词表时又把它们删回去。
        """
        self._write([])
        self.assertEqual(self._acquire(), 0)
        self._write(["> **甲（2026-08-01，CC）**：三项已办，9.2 archive 未结。"])
        self.assertNotEqual(self._release(who="A"), 0)
        self.assertFalse(self._lock_released(), "拒绝时锁必须保持占用")

    def test_新增条目含未接线同样触发(self):
        self._write([])
        self.assertEqual(self._acquire(), 0)
        self._write(["> **乙（2026-08-02，CC）**：告警通道尚未接线。"])
        self.assertNotEqual(self._release(who="A"), 0)

    def test_新增条目含未闭合措辞但点名了队列行即放行(self):
        self._write([])
        self.assertEqual(self._acquire(), 0)
        self._write(["> **甲（2026-08-01，CC）**：9.2 archive 未结，已登记 §一 #361 承接。"])
        self.assertEqual(self._release(who="A"), 0)
        self.assertTrue(self._lock_released())

    def test_新增条目无未闭合措辞不受约束(self):
        self._write([])
        self.assertEqual(self._acquire(), 0)
        self._write(["> **甲（2026-08-01，CC）**：全部完成并已部署冒烟通过。"])
        self.assertEqual(self._release(who="A"), 0)

    def test_历史条目含未闭合措辞不追溯(self):
        """只对本次持锁窗口内新增的条目生效——既有口径，历史行不秋后算账。"""
        self._write(["> **旧条（2026-07-01，CC）**：某事尚未完成。"])
        self.assertEqual(self._acquire(), 0)
        self._write([
            "> **旧条（2026-07-01，CC）**：某事尚未完成。",
            "> **新条（2026-08-01，CC）**：全部完成。",
        ])
        self.assertEqual(self._release(who="A"), 0)

    def test_在上方插入新条不会把既有条目误判为新增(self):
        """新增判定按**正文**比对而非行号——上方插入一条会让所有既有条目
        行号整体下移，按行号比对会把整段历史误判成新增、当场全线拒绝。"""
        self._write(["> **旧条（2026-07-01，CC）**：某事尚未完成。"])
        self.assertEqual(self._acquire(), 0)
        self._write([
            "> **新条（2026-08-01，CC）**：全部完成。",
            "> **旧条（2026-07-01，CC）**：某事尚未完成。",
        ])
        self.assertEqual(self._release(who="A"), 0)

    # ── 逃生阀 ────────────────────────────────────────────────────────────

    def test_进度豁免带理由可放行且理由落进history(self):
        self._write([])
        self.assertEqual(self._acquire(who="A"), 0)
        self._write([
            "> **甲（2026-08-01，CC）**：某项暂不做。进度豁免：属产品侧，本项目无承接对象。"
        ])
        self.assertEqual(self._release(who="A"), 0)
        raw = json.loads(
            (self.repo_root / (self.module.CLAUDE_PROGRESS_TARGET + ".editlock")
             ).read_text(encoding="utf-8")
        )
        notes = [e.get("note", "") for e in raw.get("history", [])]
        self.assertTrue(any("进度豁免：属产品侧" in n for n in notes),
                        f"逃生阀理由须落进 release 的 history，实际：{notes}")

    def test_进度豁免无理由仍拒绝(self):
        """空豁免不接受——否则逃生阀退化成一个只要写四个字就能过的开关。"""
        self._write([])
        self.assertEqual(self._acquire(), 0)
        self._write(["> **甲（2026-08-01，CC）**：某项暂不做。进度豁免："])
        self.assertNotEqual(self._release(who="A"), 0)

    # ── 解析器契约（与 lint 侧共用同一份实现） ──────────────────────────

    def test_红色前缀条目必须被数到(self):
        text = (
            "# t\n\n> **当前进度**：说明。\n>\n"
            "> **甲（2026-08-01，CC）**：正文。\n>\n"
            "> 🔴 **乙（2026-08-02，CC）**：正文。\n\n---\n\n## 1. 正文\n"
        )
        entries = self.module._claude_progress_entries(text)
        self.assertEqual(len(entries), 2)

    def test_迁移指针行之后的元说明不算条目(self):
        text = (
            "# t\n\n> **当前进度**：说明。\n>\n"
            "> **甲（2026-08-01，CC）**：正文。\n>\n"
            "> **📦 更早条目已迁 CHANGELOG**（2026-08-05，队列 #253）：保留。\n>\n"
            "> **🔴 memory 层已收割并停用（2026-08-21，OP-0821-B）**：元说明。\n"
            "\n---\n\n## 1. 正文\n"
        )
        entries = self.module._claude_progress_entries(text)
        self.assertEqual(len(entries), 1,
                         "📦 之后的两行是元说明，不是进度条目（2026-08-21 实测："
                         "裸正则在真身上数出 4 条而真值是 2 条）")

    def test_无当前进度头行返回空表不猜(self):
        self.assertEqual(
            self.module._claude_progress_entries("# t\n\n> 无头行。\n\n---\n\n## 1\n"), []
        )

    def test_非CLAUDE目标不跑本判据(self):
        """`--file` 指向别的共享文件时，J4 完全不生效——不同判据各管各的
        目标，同 FOLLOWUP_README_TARGET 既有分支。"""
        other = self.repo_root / "别的共享文件.md"
        other.write_text("> **当前进度**：\n>\n> **甲（2026-08-01，CC）**：尚未完成。\n\n---\n",
                         encoding="utf-8")
        ns_a = argparse.Namespace(file="别的共享文件.md", who="A", note="",
                                  reserve=None, section=None, reserve_multi=None, domain=None)
        self.assertEqual(self.module.cmd_acquire(ns_a), 0)
        other.write_text("> **当前进度**：\n>\n> **甲（2026-08-01，CC）**：尚未完成。\n"
                         "> **乙（2026-08-02，CC）**：也尚未完成。\n\n---\n", encoding="utf-8")
        ns_r = argparse.Namespace(file="别的共享文件.md", who="A",
                                  mechanism_wip_cap=self.module.MECHANISM_WIP_CAP_DEFAULT,
                                  force_mechanism_wip=False)
        self.assertEqual(self.module.cmd_release(ns_r), 0)

    def test_绝对路径指向根CLAUDE同样被识别(self):
        """字面量相等只覆盖"没传 --file"这一种写法——机器人常驻服务传的是
        绝对路径，字面量恒不相等会让判据永不触发且零报错（`_is_queue_
        system_target` 的既有教训）。"""
        self.assertTrue(self.module._is_claude_progress_target(str(self.target_path)))
        self.assertFalse(self.module._is_claude_progress_target("别的共享文件.md"))

# ═══════════════════════════════════════════════════════════════════════
# 队列 §一 #351 咽喉六修（openspec 变更包 `editlock-chokepoint-six-fixes`，
# 2026-08-23）。每一项都配**反例单测**——判据说不该拦的，要有用例证明它
# 真的不拦；否则只测了"拦得住"，等于没测误报。
# ═══════════════════════════════════════════════════════════════════════


class AppendRowOwnershipTests(unittest.TestCase):
    """⑴ `append-row` 锁归属校验。

    成因（2026-08-18 真实事故，12 分钟内两次）：`acquire`／`append-row`／
    `release` 打包成一条命令、中间不查退出码——`acquire` **已被正确拒绝**
    （锁在别人手上），脚本照跑照写，在他人持锁期间写入两次。**那次调用
    根本没有 `--who` 可比**，所以"只在 `--who` 不符时拒绝"拦不住它。
    """

    SECTION_TWO_HEADER = (
        "| 批次 | 文件清单 | 建议 message | 状态 |\n"
        "|------|---------|--------------|------|\n"
    )

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.target = str(self.root / "假想队列.md")
        (self.root / "假想队列.md").write_text(
            "## 二、待 commit 批次\n\n" + self.SECTION_TWO_HEADER, encoding="utf-8",
        )
        self.lock_path = Path(self.target + ".editlock")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write_lock(self, who: str, minutes_ago: float) -> None:
        held_since = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        self.lock_path.write_text(
            json.dumps({"who": who, "note": "在办", "held_since": held_since.isoformat()},
                       ensure_ascii=False),
            encoding="utf-8",
        )

    def _append(self, *extra: str) -> subprocess.CompletedProcess:
        return run("--file", self.target, "append-row", "--section", "二",
                   "--cell", "B-0823_1_测试", "--cell", "`docs/x.md`",
                   "--cell", "说明", "--cell", "待处理", *extra)

    def test_other_holds_fresh_lock_and_no_who_refuses(self):
        self._write_lock("A", minutes_ago=1)
        result = self._append()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未传 --who", result.stdout)
        self.assertNotIn("B-0823_1_测试", Path(self.target).read_text(encoding="utf-8"))

    def test_other_holds_fresh_lock_and_who_mismatch_refuses(self):
        self._write_lock("A", minutes_ago=1)
        result = self._append("--who", "B")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("与你传入的「B」不同", result.stdout)
        self.assertNotIn("B-0823_1_测试", Path(self.target).read_text(encoding="utf-8"))

    def test_who_matches_holder_writes(self):
        self._write_lock("A", minutes_ago=1)
        result = self._append("--who", "A")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("B-0823_1_测试", Path(self.target).read_text(encoding="utf-8"))

    def test_stale_lock_equals_no_lock(self):
        """反例：陈旧锁等价于无锁——与 `acquire` 的既有接管口径一致，
        不因本项变成"陈旧锁也把人挡在门外"。"""
        self._write_lock("A", minutes_ago=31)  # > STALE_MINUTES
        result = self._append()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("无锁写入", result.stdout)

    def test_no_lock_writes_with_notice_not_blocked(self):
        """🔴 **本项刻意不阻断无锁写入**——协议〇.7 是协作性质，opener §〇.7
        明文"手写整行仍是允许的"。把 `append-row` 变成"必须先持锁"属改变
        全项目口径，须另走 openspec。**本项要修的是「锁归属不校验」，不是
        「无锁写入」。**"""
        result = self._append()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("无锁写入", result.stdout)


class ArityBarePipeDiagnosticsTests(unittest.TestCase):
    """⑵-a 裸竖线诊断被 arity 遮蔽。

    #351 行内自带的证伪命令已跑，实测 `True`——`len(cells) != expected` 的
    arity 检查确实排在裸竖线检查之前且失败即 raise，故裸竖线最高频的形态
    （漏写 `--cell` 分隔符）**必然**先触发 arity、裸竖线检查永不执行。
    """

    def setUp(self):
        self.m = _load_module()

    def test_arity_failure_merges_bare_pipe_diagnosis_and_gives_command(self):
        with self.assertRaises(self.m.AppendRowFailedError) as ctx:
            self.m._build_append_row_line("二", None, ["B-x", "`a.md` | 说明文字", "待处理"])
        msg = str(ctx.exception)
        self.assertIn("收到 3 个", msg)                 # 原 arity 诊断仍在
        self.assertIn("第 2 个 --cell 内含裸竖线", msg)   # 合并进来的第二条
        self.assertIn("漏写了 `--cell` 分隔符", msg)      # 指向真因
        self.assertIn("append-row --section 二", msg)    # 修正后的命令行
        self.assertIn('--cell "说明文字"', msg)

    def test_arity_failure_without_bare_pipe_stays_quiet(self):
        """反例：纯数数问题不添噪音——不该让每一次列数写错都收到一段
        关于裸竖线的长篇解释。"""
        with self.assertRaises(self.m.AppendRowFailedError) as ctx:
            self.m._build_append_row_line("二", None, ["a", "b"])
        msg = str(ctx.exception)
        self.assertIn("收到 2 个", msg)
        self.assertNotIn("裸竖线", msg)

    def test_unrecoverable_split_gives_no_command_line(self):
        """反例：恢复后数量仍不符 ⇒ **不猜命令行**。宁可少给，不给一条错的
        ——一条看起来可以直接复制、实则是错的命令行，比没有命令行更糟。"""
        with self.assertRaises(self.m.AppendRowFailedError) as ctx:
            self.m._build_append_row_line("二", None, ["a|b|c|d|e", "g"])
        msg = str(ctx.exception)
        self.assertIn("裸竖线", msg)
        self.assertIn("无法可靠恢复原意", msg)
        self.assertNotIn("append-row --section", msg)

    def test_section_one_recovered_command_carries_number(self):
        with self.assertRaises(self.m.AppendRowFailedError) as ctx:
            self.m._build_append_row_line(
                "一", "352", ["任务", "CC", "无", "无 | [S:open][D:机] 待领", "无", "2026-08-23"],
            )
        msg = str(ctx.exception)
        self.assertIn("--number 352", msg)


class FileListPathFormatTests(unittest.TestCase):
    """⑶ §二「文件清单」路径格式。

    判据只认**形态**、不认存在性（裸文件名那一支除外）。实测定标见变更包
    design.md §1：加一条存在性校验会让 98 个合法的范围性速记变成误报。
    """

    def setUp(self):
        self.m = _load_module()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        (self.root / "CLAUDE.md").write_text("根文件", encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _violations(self, file_list: str, status: str = "待处理"):
        return self.m._file_list_path_violations(
            ["B-TEST", file_list, "msg", status], self.root,
        )

    def test_bare_filename_not_at_repo_root_rejected(self):
        self.assertTrue(self._violations("`工具-落库sweep.py`"))

    def test_bare_filename_that_is_a_root_file_passes(self):
        """反例：根目录文件的裸文件名**本身就是**合法的仓库根相对路径。
        一刀切拒绝会误伤根 `CLAUDE.md`／`.gitignore`。"""
        self.assertEqual(self._violations("`CLAUDE.md`"), [])

    def test_absolute_path_rejected(self):
        self.assertTrue(self._violations("`C:\\Users\\x\\SKILL.md`"))

    def test_backslash_separator_rejected(self):
        self.assertTrue(self._violations("`Claude\\Scheduled\\x\\SKILL.md`"))

    def test_dot_prefix_rejected(self):
        self.assertTrue(self._violations("`./0-学习与工具/x.md`"))

    def test_wildcard_repo_relative_path_passes(self):
        """反例：合法的范围性速记不做存在性校验。加了它，实测 98 个这类
        片段会全部变成误报，而逃生阀一旦常规化，门禁就废了。"""
        self.assertEqual(self._violations("`X/tests/test_*.py`"), [])
        self.assertEqual(self._violations("`openspec/changes/x/{proposal,design}.md`"), [])

    def test_non_path_fragments_untouched(self):
        """反例：判据刻意**不把"含斜杠"当路径特征**——`采购/财务/质量` 这类
        并列写法在队列里极常见，按"含斜杠"判会把它们全拖进来。"""
        self.assertEqual(self._violations("`--force-mechanism-wip`"), [])
        self.assertEqual(self._violations("`采购/财务/质量`"), [])
        self.assertEqual(self._violations("`queue_table.iter_queue_paths()`"), [])

    def test_preregistered_row_is_exempt(self):
        """反例：预登记批次豁免——`queue-claim-time-preregistration` 明文允许
        其文件清单为目录前缀或范围性描述。两条 spec 各守一段生命周期；该行
        走到"收工时精确化"会被重新触碰，届时 ⑶ 自然接管。"""
        status = self.m.PREREGISTERED_STATUS_PREFIX + "，收工时精确化）"
        self.assertEqual(self._violations("`工具-落库sweep.py`", status=status), [])

    def test_directory_prefix_form_is_path_like(self):
        self.assertTrue(self.m._fragment_is_path_like("4-数字员工/采购部/"))
        self.assertEqual(self._violations("`4-数字员工/采购部/`"), [])


class GenderPronounLintTests(unittest.TestCase):
    """⑷ 人的属性（性别代词）。

    判据比 #351 原文（"同一行内同时出现"）**收窄**了——实测整行判据命中
    65 行、25 字窗口 18 行，而残余的绝大多数是**引用规则条文本身**的行。
    收窄依据与实测曲线见变更包 design.md §1。
    """

    def setUp(self):
        self.m = _load_module()

    def _v(self, line: str):
        return self.m._gender_pronoun_violations("一", ["351", line], line)

    def test_male_name_followed_by_she_violates(self):
        self.assertTrue(self._v("姚祖怡今天回件了，她说答交口径要改"))

    def test_female_name_followed_by_he_violates(self):
        self.assertTrue(self._v("唐燕萍圈定了这条口径，他还补了一句"))

    def test_qita_does_not_false_positive(self):
        """🔴 **`其他` 在队列里极高频，不排除会把真报淹掉**（#351 ⑷ 行内
        已用红字点名这一条）。"""
        self.assertEqual(self._v("唐燕萍圈定了这条口径，其他几项待定"), [])
        self.assertEqual(self._v("陈忱回件三点全答，其它两项并入"), [])
        self.assertEqual(self._v("陈忱与他们约了微会"), [])

    def test_multiple_people_in_one_row_is_legal(self):
        """反例：姓名与代词之间隔着异性名字 ⇒ 代词指中间那个人，合法。
        判据复刻 2026-08-21 那次 244 处追改所用的脚本口径。"""
        self.assertEqual(self._v("姚祖怡和唐燕萍都回了件，她补了一条税务口径"), [])

    def test_pronoun_beyond_window_not_flagged(self):
        far = "姚祖怡" + "补充说明" * 12 + "她"
        self.assertEqual(self._v(far), [])

    def test_in_row_waiver_passes(self):
        line = "姚祖怡这一行历史正文写作她（性别豁免：历史记录不追改）"
        self.assertEqual(self._v(line), [])

    def test_roster_stays_in_sync_with_authoritative_roster_file(self):
        """🔴 **名录再扩而常量没跟，这条用例会当场变红。**

        方向是「正本§一 ⊆ 常量」而不是「＝」，刻意如此：真正要抓的失效形态
        是*名录扩了而常量没跟*，用 ⊆ 即可抓住；要求相等则等于要求正本文件
        写成机器可解析的格式，那是对一份**人读的文件**提错要求（实测正本
        §一里 `邵培申` 写作「`邵培申` ＝ Shao Peishen 本人」，没有「（男）」
        标注）。

        **数据源 ＝ `6-人才与组织/人员名录-称谓与性别-正本.md` §一**（原文
        原样迁自根 `CLAUDE.md` §1，2026-08-28，OP-0828-Q，队列 #433 A2，
        CHANGELOG 附录 G-5；迁移时已用同一条正则对迁前／迁后两侧取
        name→gender 差集核过，缺失 0、新增 0）。本用例一度仍指向根
        `CLAUDE.md` §1：瘦身后 §1 只剩指针、不再含名录正文，抽取正则从此
        只抓到 0 个人名——不是判据被绕开，恰恰是下面的数量下限断言按设计
        抓住了它、当场把"抓不到"变成硬失败，只是这次失败在提示"数据源
        指针没跟着迁移改"，不是在提示"名录与常量真的漂移了"。这里把数据
        源指针改到位，判据设计本身不变。

        **为什么不在运行时解析正本文件**：§一是会随人事变动而改的散文，
        措辞一变解析就抽不到人名，判据随即变成**恒真、零信息量，而没有
        任何东西会报错**——用一个失效不产生信号的实现，去做一条专为
        根治"错误不产生信号"而立的校验，是原地打转。
        """
        roster_md = (SCRIPT.resolve().parents[1] / "6-人才与组织"
                     / "人员名录-称谓与性别-正本.md")
        text = roster_md.read_text(encoding="utf-8")
        start, end = text.index("## 一、"), text.index("## 二、")
        declared = {}
        for match in re.finditer(r"([\u4e00-\u9fa5]{2,4})（(男|女)[^）]*）", text[start:end]):
            declared.setdefault(match.group(1), set()).add(match.group(2))

        self.assertGreaterEqual(
            len(declared), 15,
            "从正本 §一只抽到极少的人名——多半是那一节的写法变了、"
            "本用例的抽取正则已失效。**这时候它是恒真的，等于没有校验**，"
            "请先修抽取，不要直接放宽断言。",
        )
        for name, genders in sorted(declared.items()):
            self.assertIn(
                name, self.m.PERSON_GENDER_ROSTER,
                f"正本 §一里的「{name}」不在 PERSON_GENDER_ROSTER 里"
                f"——名录扩了，常量没跟。",
            )
            self.assertEqual(
                genders, {self.m.PERSON_GENDER_ROSTER[name]},
                f"「{name}」在正本 §一与常量里的性别不一致。",
            )


class BatchNumberCollisionTests(unittest.TestCase):
    """⑸ §二 批次号前缀查重。

    立行时以为是"同族第三次"，**实测现存 174 个前缀中 27 个撞号（15.5%）**。
    """

    HEADER = ("| 批次 | 文件清单 | 建议 message | 状态 |\n"
              "|------|---------|--------------|------|\n")

    def setUp(self):
        self.m = _load_module()

    def _texts(self, *rows: str) -> dict:
        body = "## 二、待 commit 批次\n\n" + self.HEADER + "".join(rows)
        return {"queue-mech.md": body}

    def test_same_prefix_rejected(self):
        texts = self._texts("| B-0823_5_别的事 | `a/b.md` | msg | 待处理 |\n")
        problem = self.m._batch_prefix_collision("B-0823_5_我的事", texts)
        self.assertIsNotNone(problem)
        self.assertIn("B-0823_5_别的事", problem)

    def test_suggestion_is_next_numeric_serial(self):
        texts = self._texts(
            "| B-0823_5_甲 | `a/b.md` | msg | 待处理 |\n"
            "| B-0823_9_乙 | `a/b.md` | msg | ✅ 已处理 |\n"
        )
        problem = self.m._batch_prefix_collision("B-0823_5_丙", texts)
        self.assertIn("B-0823_10", problem)

    def test_cross_physical_file_collision_caught(self):
        """批次号在两份物理队列文件间**共用同一命名空间**——2026-08-20 那两次
        真实撞号里，`B-0820_11` 与 `B-0820_13` 各是两个不同 session 写的。"""
        texts = {
            "queue-mech.md": "## 二、待 commit 批次\n\n" + self.HEADER,
            "queue-biz.md": ("## 二、待 commit 批次\n\n" + self.HEADER
                             + "| B-0823_7_业务侧 | `a/b.md` | msg | 待处理 |\n"),
        }
        self.assertIsNotNone(self.m._batch_prefix_collision("B-0823_7_机制侧", texts))

    def test_no_collision_passes(self):
        texts = self._texts("| B-0823_5_别的事 | `a/b.md` | msg | 待处理 |\n")
        self.assertIsNone(self.m._batch_prefix_collision("B-0823_6_我的事", texts))

    def test_non_conforming_batch_name_not_constrained(self):
        """反例：不符 `B-MMDD_<第二段>` 形态的批次名不受本项约束——**判据只判
        前缀字面重复，不解释第二段语义**。实测两种写法并存（`B-0818_18_…`
        的 18 是当日流水号，`B-0808_309_…` 的 309 是队列行号），不为这件事
        再造一套命名判据。"""
        texts = self._texts("| 临时批次 | `a/b.md` | msg | 待处理 |\n")
        self.assertIsNone(self.m._batch_prefix_collision("临时批次", texts))


class RegistrationCompletenessTests(unittest.TestCase):
    """⑹ release 登记完整性校验（队列 §一 #351 ⑹）。

    用**真实 git 仓库**（`git init` 到临时目录）跑，不用桩——本项的整个价值
    就在于"机器亲眼看到工作区脏了"，用桩测等于把要验的那一段换掉了。同一
    惯例见 `EditLockCrossWorktreeTests`（那里用真实 `git worktree add`）。

    ━━━ 🔴 **本项判据与 #351 原文不同，理由必须留在这里** ━━━
    #351 ⑹ 原文写的是「本次持锁窗口内**新增**的脏文件」（快照差集）。
    **取证证明那个判据抓不住它自己的立项实证**：`reports/sweep-commit.log`
    实测 `OP-0822-E` 的六个孤儿文件在 **2026-08-22 12:20 UTC** 那轮 sweep
    就已全部报为脏，而 E 于 **12:26:16 UTC** 才 acquire——**晚 6 分钟**。
    按差集口径它们在占锁那一刻已进基线，release 时差集为空、照样放行。
    ⇒ 判据改为「release 时**全部**脏文件都须被某个待处理批次覆盖」，这不是
    新造判据——它逐字等同 sweep 孤儿检测已在用的那一条，本项只是把它从
    "只进日志的事后告警"前移到"有阻断力、且 session 还活着"的时点。
    acquire 快照**保留但改用途**：只用于归因，见 `test_..._attribution`。
    """

    HEADER = ("| 批次 | 文件清单 | 建议 message | 状态 |\n"
              "|------|---------|--------------|------|\n")

    def setUp(self):
        self.m = _load_module()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        for args in (["init", "-q"],
                     ["config", "user.email", "t@example.com"],
                     ["config", "user.name", "t"]):
            subprocess.run(["git", *args], cwd=self.root, check=True,
                           capture_output=True, text=True)
        (self.root / "seed.txt").write_text("seed", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "seed"], cwd=self.root, check=True,
                       capture_output=True)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _dirty(self, rel: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("脏内容", encoding="utf-8")

    def _queue(self, *rows: str) -> dict:
        return {"queue-mech.md": "## 二、待 commit 批次\n\n" + self.HEADER + "".join(rows)}

    def _run(self, queue_texts, lock_data=None, waivers=None):
        return self.m._registration_completeness_violations(
            queue_texts, lock_data or {}, self.root, waivers or [],
        )

    # ── 主判据 ────────────────────────────────────────────────────
    def test_uncovered_dirty_file_rejects(self):
        self._dirty("1-转型规划/接力件.md")
        violations = self._run(self._queue())
        self.assertEqual(len(violations), 1)
        self.assertIn("1-转型规划/接力件.md", violations[0])
        self.assertIn("不属于任何待处理 §二 批次", violations[0])

    def test_covered_dirty_file_passes(self):
        self._dirty("1-转型规划/接力件.md")
        rows = ("| B-1 | `1-转型规划/接力件.md` | msg | 待处理 |\n",)
        self.assertEqual(self._run(self._queue(*rows)), [])

    def test_done_batch_does_not_count_as_coverage(self):
        """已完成批次不会再被 sweep 取活，其清单不构成归属——这正是
        `OP-0822-E` 那种"以为登记过了"的第二种形态。"""
        self._dirty("1-转型规划/接力件.md")
        rows = ("| B-1 | `1-转型规划/接力件.md` | msg | ✅ 已处理 |\n",)
        self.assertTrue(self._run(self._queue(*rows)))

    def test_preregistered_batch_counts_as_coverage(self):
        """反例：预登记批次属**待处理**态（涵盖在 `_leading_status_segment`
        既有口径里），其目录前缀声明构成有效覆盖。"""
        self._dirty("4-数字员工/采购部/SC8/x.py")
        rows = (f"| B-1 | `4-数字员工/采购部/SC8/x.py` | msg | "
                f"{self.m.PREREGISTERED_STATUS_PREFIX}，收工时精确化） |\n",)
        self.assertEqual(self._run(self._queue(*rows)), [])

    def test_suffix_matching_matches_sweep(self):
        """覆盖判定逐字复刻 sweep 的后缀匹配（`p == f` 或 `p.endswith("/" + f)`）
        ——**不新造判据**。"""
        self._dirty("1-转型规划/接力件.md")
        rows = ("| B-1 | `接力件.md` | msg | 待处理 |\n",)
        self.assertEqual(self._run(self._queue(*rows)), [])

    def test_editlock_sidecars_not_required_to_register(self):
        """反例：锁自身的伴生文件不该被要求登记。**这一条是从 #322 学来的**
        ——那次给编辑锁加"删不掉就改名"退路，改名凭空造出一种没人回头看的
        文件形态（`*.editlock.mutex.stale`），被 sweep 判为孤儿、企微群连响
        17.1 小时。"""
        self._dirty("queue-mech.md.editlock")
        self._dirty("queue-mech.md.editlock.snapshot")
        self.assertEqual(self._run(self._queue()), [])

    # ── 归因（acquire 快照的新用途） ──────────────────────────────
    def test_attribution_splits_by_acquire_snapshot(self):
        """并发场景（#351 边界一）：占锁前就已脏的文件**仍然被要求登记**，
        但在提示里单独成组并注明"可能来自并发 session"。

        🔴 **差集过滤是让机器替人做一个它做不了的判断**（这脏文件是谁造的），
        并且默默判成"不是你"；归因提示是把判断交还给人，同时把机器确实知道
        的那点信息（时间先后）如实给出。
        """
        self._dirty("并发方改的.md")            # 占锁前就脏（模拟另一 session）
        snapshot = self.m._local_git_status_paths(self.root)
        self._dirty("我改的.md")                 # 占锁后才脏
        violations = self._run(self._queue(), lock_data={"dirty_at_acquire": snapshot})
        self.assertEqual(len(violations), 1)
        text = violations[0]
        self.assertIn("本次持锁期间新出现", text)
        self.assertIn("acquire 之前就已经脏（可能来自并发 session）", text)
        self.assertLess(text.index("我改的.md"), text.index("并发方改的.md"))

    def test_no_snapshot_does_not_guess(self):
        """反例：锁记录里没有快照时**不臆断**归到哪一组——这类"没有数据就
        默默按某个默认值处理"正是本项目反复吃亏的形态。"""
        self._dirty("某文件.md")
        violations = self._run(self._queue(), lock_data={})
        self.assertIn("无法判定出现时刻", violations[0])

    # ── fail-closed 与适用前提 ────────────────────────────────────
    def test_not_a_work_tree_skips_with_notice(self):
        """反例：**根本不在 git 工作树内** ⇒ "脏文件"这个概念不成立，判据的
        适用前提不成立，跳过是正确的（且会打印一行明示）。它与"在工作树内
        但取数失败"是两回事，后者必须 fail-closed，见下一条。"""
        with tempfile.TemporaryDirectory() as plain:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                violations = self.m._registration_completeness_violations(
                    self._queue(), {}, Path(plain), [],
                )
            self.assertEqual(violations, [])
            self.assertIn("适用前提不成立", out.getvalue())

    def test_status_failure_is_fail_closed(self):
        """在工作树内、但 `git status` 拿不到答案 ⇒ **拒绝 release**，不静默
        放行。本变更同批退休了校验②（一进一出），静默放行会让这道咽喉上
        什么都不剩。"""
        self._dirty("某文件.md")
        with unittest.mock.patch.object(self.m, "_local_git_status_paths", return_value=None):
            violations = self._run(self._queue())
        self.assertEqual(len(violations), 1)
        self.assertIn("fail-closed", violations[0])

    # ── 身份豁免 ──────────────────────────────────────────────────
    def test_sweep_identity_is_exempt(self):
        """🔴 **这一条锁死的是 apply 期当场撞出的一次真实断链，不是假想。**

        `工具-落库sweep.py` 在一次持锁窗口内做的事是：`git add` 本批文件 →
        把该批次行改成 `✅ 已完成` → release → commit。⇒ **release 那一刻
        工作区必然是脏的**，而它刚把那条批次行标成完成 ⇒ 那条清单已不再是
        "待处理批次" ⇒ ⑹ **必然判为未覆盖、必然拒绝**。

        **后果不是多一条告警，是全项目停摆**：`_strike_off_rows` 在 `finally`
        里调 release 且**不看返回码**，被拒 ⇒ 锁保持占用 ⇒ 下一轮 sweep 起跑
        探锁判定"有人正在编辑"直接跳过 ⇒ 此后每一轮都跳过，而 sweep 是唯一
        会 commit 队列改动的机制。2026-08-23 由 `test_工具-落库sweep.py::
        PendingCriteriaIntegrationTests::test_four_status_forms_processed_
        correctly_end_to_end` 当场撞出，**未进生产**。

        🔑 **教训值得写在这里**：本变更包自己的 239 条单测**全绿**，是跑
        **邻居工具的测试套**才发现的——一道守卫的影响面不止于它自己那个文件。
        """
        self._dirty("1-转型规划/接力件.md")
        self.assertTrue(self._run(self._queue()))          # 换个身份就该拦
        self.assertEqual(                                   # sweep 身份放行
            self._run(self._queue(), lock_data={"who": self.m.SWEEP_LOCK_WHO}), [],
        )

    def test_aibot_identity_is_exempt_from_others_dirty_files(self):
        """🔴 **队列 #416 ⑶ 的真实事故场景，逐字复刻。**

        机器人持锁、只追加自己那一行收件登记，而工作区里**另有一个属于别的
        会话的脏文件**（人在改方案件）⇒ 改前 ⑹ 当场判"未覆盖"、release 被拒
        ⇒ 锁挂到 30 分钟自动陈旧才被接管，**期间任何人写不了队列**。全历史
        5 次（08-24 三次、08-26 两次），每次都紧跟专员回件到达。

        机器人**两条出路一条都走不了**：它从不登记 §二 批次（走
        `append_task_and_sync_to_git` 自己 commit 自己 push），也无法判断别人
        的脏文件该不该登记——那是别人的活。
        """
        self._dirty("1-转型规划/某个别的会话正在改的方案件.md")   # 别人造的脏
        self._dirty("queue-mech.md")                              # 机器人自己写的
        self.assertTrue(self._run(self._queue()),
                        "普通会话在同一场景下必须仍被拦——否则下一条断言没有意义")
        self.assertEqual(
            self._run(self._queue(), lock_data={"who": self.m.AIBOT_LOCK_WHO}), [],
            "机器人自己 commit 自己 push，⑹「你的脏文件没人管」这个前提对它不成立",
        )

    def test_human_session_still_blocked_by_uncovered_dirty_file(self):
        """🔴 **反例（tasks 2.2）：没有它就无法区分"豁免生效"与"⑹ 被改废"。**

        人类会话恰恰是 ⑹ 真正的适用对象——人改完东西要靠 sweep 提交。
        """
        self._dirty("1-转型规划/接力件.md")
        violations = self._run(self._queue(), lock_data={"who": "Shao Peishen 的 CC"})
        self.assertEqual(len(violations), 1)
        self.assertIn("不属于任何待处理 §二 批次", violations[0])

    def test_aibot_still_fail_closed_when_status_unavailable(self):
        """🔴 **反例（tasks 2.4）：豁免不覆盖 fail-closed 那一支。**

        校验**无法执行**（git 挂了／超时）与校验**不适用**是两回事，混为一谈
        就正是本项目反复吃亏的"工具静默回退"。判据体现在**代码位置**上：身份
        豁免写在 `dirty_now is None` 之后，不是函数开头。
        """
        self._dirty("某文件.md")
        with unittest.mock.patch.object(self.m, "_local_git_status_paths", return_value=None):
            violations = self._run(self._queue(),
                                   lock_data={"who": self.m.AIBOT_LOCK_WHO})
        self.assertEqual(len(violations), 1)
        self.assertIn("fail-closed", violations[0])

    def test_exemption_criterion_is_self_committing_not_being_a_bot(self):
        """判据登记在 `SELF_COMMITTING_LOCK_HOLDERS` 上——"是否自行提交自身
        改动"，不是"是不是机器人"。下一个自动化持锁者的挂靠点在这里；这条
        断言存在的意义是：把常量删空或改名的人会看见它变红。"""
        self.assertEqual(
            tuple(self.m.SELF_COMMITTING_LOCK_HOLDERS),
            (self.m.SWEEP_LOCK_WHO, self.m.AIBOT_LOCK_WHO),
        )

    # ── 逃生阀 ────────────────────────────────────────────────────
    def test_waiver_in_note_passes(self):
        self._dirty("某文件.md")
        waivers = [f"{self.m.REGISTRATION_WAIVER_MARKER}临时取证脚本，不入库"]
        self.assertEqual(self._run(self._queue(), waivers=waivers), [])

    def test_waiver_also_covers_status_failure(self):
        self._dirty("某文件.md")
        waivers = [f"{self.m.REGISTRATION_WAIVER_MARKER}git 环境异常，已另行处置"]
        with unittest.mock.patch.object(self.m, "_local_git_status_paths", return_value=None):
            self.assertEqual(self._run(self._queue(), waivers=waivers), [])

    def test_waiver_only_in_untouched_history_row_does_not_pass(self):
        """🔴 取材面刻意**不含队列全文**：`登记豁免：` 一旦写进这两份 1.9 MB
        的文件任何一处，全文匹配就等于把这道门禁**永久关掉，且此后没有任何
        人会发现**。逃生阀必须一次一用，不能变成一个写一次就长期生效的开关。
        （与既有 `转态豁免：` 同一收敛方向。）

        本用例把豁免写进队列正文里一条**本次未触碰**的历史行，`waiver_sources`
        为空 ⇒ 仍应拒绝。
        """
        self._dirty("某文件.md")
        rows = (f"| B-旧 | `x/y.md` | msg | 待处理 "
                f"{self.m.REGISTRATION_WAIVER_MARKER}历史行里的豁免 |\n",)
        self.assertTrue(self._run(self._queue(*rows), waivers=[]))


OPENER_LINT_TEST_SCRIPT = Path(__file__).resolve().with_name("test_工具-opener块lint.py")


def _load_opener_lint_fixtures():
    """白盒 import `test_工具-opener块lint.py`，只取其共享 opener 块 fixture 常量
    （`SETTINGS_CC`/`SETTINGS_COWORK`/`TITLE_LINE_*`），不重抄一份——理由见
    `OpenerGuardReleaseTests` 类文档字符串。"""
    spec = importlib.util.spec_from_file_location(
        "_opener_lint_test_fixtures_under_test", OPENER_LINT_TEST_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_OPENER_FIXTURES = _load_opener_lint_fixtures()


class OpenerGuardReleaseTests(unittest.TestCase):
    """release 前的 opener 守卫（队列 §一 `#437`，`#284` 形态①的真根治）。

    用**真实 git 仓库**跑，理由同 `RegistrationCompletenessTests`——本项的
    整个价值就在于"机器亲眼看到工作区里刚写出来、还没 commit 的 .md"，用桩
    测等于把要验的那一段换掉了。

    fixture（`SETTINGS_CC`/`SETTINGS_COWORK`/`TITLE_LINE_*`）直接从
    `test_工具-opener块lint.py` 导入，不另抄一份——两边测的是**同一份判据**
    （`check_block`），各自维护一份文本必然不同源漂移：2026-09-04 当天已
    第三次撞上这族问题（`SETTINGS_CC` 字段顺序错、`SETTINGS_COWORK` 字段
    残缺，且两者都没配过形态⑤要求的合规首行）。单一来源是唯一解，不是
    "抄得更认真一点"。
    """

    TITLE_LINE_NO_EXC = _OPENER_FIXTURES.TITLE_LINE_NO_EXC
    TITLE_LINE_WITH_EXC = _OPENER_FIXTURES.TITLE_LINE_WITH_EXC
    TITLE_LINE_CC = _OPENER_FIXTURES.TITLE_LINE_CC
    TITLE_LINE_COWORK = _OPENER_FIXTURES.TITLE_LINE_COWORK
    SETTINGS_CC = _OPENER_FIXTURES.SETTINGS_CC
    SETTINGS_COWORK = _OPENER_FIXTURES.SETTINGS_COWORK

    def setUp(self):
        self.m = _load_module()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        for args in (["init", "-q"],
                     ["config", "user.email", "t@example.com"],
                     ["config", "user.name", "t"]):
            subprocess.run(["git", *args], cwd=self.root, check=True,
                           capture_output=True, text=True)
        (self.root / "seed.txt").write_text("seed", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "seed"], cwd=self.root, check=True,
                       capture_output=True)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write_block(self, rel: str, *body_lines: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("```\n" + "\n".join(body_lines) + "\n```\n", encoding="utf-8")

    def _run(self, waivers=None):
        return self.m._opener_guard_violations(self.root, waivers or [])

    # ── tasks 2.1：形态①，CC 块缺 title ──────────────────────────
    def test_cc_block_missing_title_rejects(self):
        self._write_block("派单件-x.md", self.SETTINGS_CC, "读队列 #999。")
        violations = self._run()
        self.assertEqual(len(violations), 1)
        self.assertIn("F1", violations[0])
        self.assertIn("派单件-x.md", violations[0])

    # ── tasks 2.2：形态②，有 title 无例外句 ──────────────────────
    def test_cc_block_title_without_exception_rejects(self):
        self._write_block("派单件-y.md", self.SETTINGS_CC, self.TITLE_LINE_NO_EXC)
        violations = self._run()
        self.assertEqual(len(violations), 1)
        self.assertIn("F2", violations[0])

    # ── tasks 2.3：写对的放行 ────────────────────────────────────
    def test_correct_cc_block_passes(self):
        self._write_block("派单件-z.md", self.TITLE_LINE_CC, self.SETTINGS_CC,
                          self.TITLE_LINE_WITH_EXC)
        self.assertEqual(self._run(), [])

    # ── tasks 2.4：🔴 反例，防误伤 Cowork（D4）───────────────────
    def test_cowork_block_without_title_passes(self):
        """本项不过则本线自己每次 release 都会被拦死——`set_session_title`
        在 Cowork 侧根本不存在（补充一 2026-08-27 已实测）。"""
        self._write_block("派单件-cowork.md", self.TITLE_LINE_COWORK, self.SETTINGS_COWORK,
                          "读接力文件继续。")
        self.assertEqual(self._run(), [])

    # ── tasks 2.5：未声明环境不校验（宁可漏，不误伤）─────────────
    def test_env_unlabeled_block_passes(self):
        """与 `test_工具-opener块lint.py::形态一_缺set_session_title
        .test_执行环境未标_不猜_不判形态一` 同一份真实原文（`本周计划-2026-08-03.md`
        形态）。🔴 "环境未标不猜、不误伤 CC 专属项（F1）"与"六字段不全该报（F4）"
        是两件独立的事，2026-09-04 形态四生效后不能再用一句 `assertEqual(..., [])`
        把两者混在一起——那样会让本文件比对面那份"更宽松"，读的人会误以为这条
        真实历史形态在新判据下依然全干净。"""
        self._write_block("本周计划-x.md",
                          "【设置】分支：master ｜ worktree：☐", "读队列继续。")
        violations = self._run()
        self.assertEqual(len(violations), 1)
        self.assertNotIn("F1", violations[0])
        self.assertIn("F4", violations[0])

    # ── tasks 2.6：逃生阀，note 与队列行两处各测一次 ─────────────
    def test_waiver_in_note_passes(self):
        self._write_block("派单件-w1.md", self.SETTINGS_CC, "读队列。")
        waivers = [f"{self.m.OPENER_EXEMPT_MARK}临时手写，来不及补 title"]
        self.assertEqual(self._run(waivers=waivers), [])

    def test_waiver_in_touched_queue_row_passes(self):
        """逃生阀取材面＝本次 note ＋ 本次触碰过的队列行——与 `登记豁免：`
        同一收敛方向（不含队列全文，一次一用）。"""
        self._write_block("派单件-w2.md", self.SETTINGS_CC, "读队列。")
        waivers = [f"| 999 | 已知漏 title，{self.m.OPENER_EXEMPT_MARK}紧急止血 | ... |"]
        self.assertEqual(self._run(waivers=waivers), [])

    # ── tasks 2.7：🔴 零 opener 块时仍有回显 ──────────────────────
    def test_echo_prints_even_when_zero_opener_blocks(self):
        """连回显都没有时，无法区分「没问题」与「没跑」（队列 #284 第 18 次
        违反的教训）。"""
        (self.root / "普通文档.md").write_text("没有 opener 块的普通内容。\n",
                                              encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            violations = self._run()
        self.assertEqual(violations, [])
        self.assertIn("已校验本次触碰的 1 个", out.getvalue())
        self.assertIn("opener 块 0 个", out.getvalue())

    def test_echo_wording_does_not_imply_full_coverage(self):
        """🔴 D2：回显措辞不得暗示全覆盖——本守卫只覆盖走了队列锁流程的 opener。"""
        (self.root / "x.md").write_text("普通内容\n", encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self._run()
        self.assertNotIn("opener 已全部合规", out.getvalue())

    # ── 非 .md 脏文件不进扫描面 ────────────────────────────────
    def test_non_md_dirty_file_ignored(self):
        (self.root / "脚本.py").write_text(self.SETTINGS_CC, encoding="utf-8")
        self.assertEqual(self._run(), [])

    # ── fail-closed 与适用前提（同 ⑹ 判据方向）───────────────────
    def test_not_a_work_tree_skips_with_notice(self):
        """反例：根本不在 git 工作树内 ⇒ 适用前提不成立，跳过（不是
        fail-closed 拒绝）——同 `_is_inside_git_work_tree` 判据方向。"""
        with tempfile.TemporaryDirectory() as plain:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                violations = self.m._opener_guard_violations(Path(plain), [])
            self.assertEqual(violations, [])
            self.assertIn("适用前提不成立", out.getvalue())

    def test_status_failure_is_fail_closed(self):
        """在工作树内、但 `git status` 取不到答案 ⇒ 拒绝，不静默放行。"""
        self._write_block("某文件.md", self.SETTINGS_CC, "读队列。")
        with unittest.mock.patch.object(self.m, "_local_git_status_paths", return_value=None):
            violations = self._run()
        self.assertEqual(len(violations), 1)
        self.assertIn("fail-closed", violations[0])

    def test_status_failure_with_waiver_passes(self):
        self._write_block("某文件.md", self.SETTINGS_CC, "读队列。")
        waivers = [f"{self.m.OPENER_EXEMPT_MARK}git 环境异常，已另行处置"]
        with unittest.mock.patch.object(self.m, "_local_git_status_paths", return_value=None):
            self.assertEqual(self._run(waivers=waivers), [])


class AcquireRoutingHintTests(unittest.TestCase):
    """ⓔ acquire 触碰区路由提示（队列 §一 #381⑸ⓔ，openspec 变更包 cc-hooks-p3）。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.target = str(Path(self._tmpdir.name) / "假想队列.md")
        self.lock_path = Path(self.target + ".editlock")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_note含跟进信关键词命中对应规则文件(self):
        result = run("--file", self.target, "acquire", "--who", "A", "--note", "起草IT部#7跟进信")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("命中根 §4 路由表 → 先读 `.claude/rules/跟进信与专员.md`", result.stdout)

    def test_note含openspec关键词命中场景建造规则(self):
        result = run("--file", self.target, "acquire", "--who", "A", "--note", "走openspec propose")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("场景建造与合规.md", result.stdout)

    def test_note含取证关键词命中两桌同步规则(self):
        result = run("--file", self.target, "acquire", "--who", "A", "--note", "查企微推送与fsck")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("两桌同步与取证.md", result.stdout)

    def test_同时命中多条规则各打印一次且不重复(self):
        result = run("--file", self.target, "acquire", "--who", "A",
                     "--note", "跟进信起草，顺带走openspec")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count("命中根 §4 路由表"), 2)
        self.assertIn("跟进信与专员.md", result.stdout)
        self.assertIn("场景建造与合规.md", result.stdout)

    def test_note不含任何关键词时不打印路由提示(self):
        result = run("--file", self.target, "acquire", "--who", "A", "--note", "纯粹改个错别字")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("命中根 §4 路由表", result.stdout)

    def test_file路径本身含关键词也能命中(self):
        subdir = Path(self._tmpdir.name) / "6-人才与组织" / "部门AI专员跟进"
        subdir.mkdir(parents=True, exist_ok=True)
        target = str(subdir / "README-跟进机制与命名约定.md")
        result = run("--file", target, "acquire", "--who", "A", "--note", "改一个错别字")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("跟进信与专员.md", result.stdout)

    def test_默认队列目标路径本身不含任何路由关键词(self):
        """design.md 决策点4：队列本身的编辑不提示"去读队列与落库.md"（调用者已在这条路径上）。

        🔴 白盒验证、不经 `acquire` 子进程——真跑 `acquire` 不传 `--file` 会打在**真实**
        项目队列锁上，与本 session 自己正在使用的锁互相干扰，此处不采用黑盒方式。
        """
        m = _load_module()
        self.assertEqual(m._routing_hint_targets(m.DEFAULT_TARGET, "常规队列登记"), [])

    def test_既有回归_不含关键词的acquire输出逐字节不变(self):
        """新增逻辑对无命中输入必须零输出差异——不改变既有字段顺序与既有文本。"""
        result = run("--file", self.target, "acquire", "--who", "A", "--note", "无关键词的备注")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("✓ 已占锁：A", result.stdout)
        self.assertIn("📍 权威物理路径", result.stdout)

    def test_routing_hint_targets白盒_大小写与去重(self):
        m = _load_module()
        hits = m._routing_hint_targets("无关路径.md", "跟进信 跟进信 专员")
        self.assertEqual(hits, [".claude/rules/跟进信与专员.md"])
        self.assertEqual(m._routing_hint_targets("无关路径.md", "不含任何关键词"), [])


if __name__ == "__main__":
    unittest.main()
