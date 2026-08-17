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

    def test_new_batch_without_declaring_queue_file_itself_blocks_release(self):
        self.assertEqual(self._acquire(who="A"), 0)
        self._write_queue(section_two_rows=(
            "| B-TEST | `某个文件.md` | `docs(test): 测试` | 待处理 |\n"
        ))

        result = self._release(who="A")
        self.assertNotEqual(result, 0)

    def test_new_batch_declaring_queue_file_itself_passes(self):
        self.assertEqual(self._acquire(who="A"), 0)
        self._write_queue(section_two_rows=(
            "| B-TEST | `某个文件.md`、`queue.md` | `docs(test): 测试` | 待处理 |\n"
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
            "| B-TEST | `某个文件.md`、`queue.md` | `docs(test): 测试` | "
            "本session直接commit+push |\n"
        ))

        result = self._release(who="A")
        self.assertNotEqual(result, 0)

    def test_new_batch_pending_status_passes(self):
        self.assertEqual(self._acquire(who="A"), 0)
        self._write_queue(section_two_rows=(
            "| B-TEST | `某个文件.md`、`queue.md` | `docs(test): 测试` | 待处理 |\n"
        ))

        self.assertEqual(self._release(who="A"), 0)

    def test_existing_batch_transitioning_to_done_status_passes(self):
        """⑤不拦"✅"本身；队列 #308 子项 F1 新增的边界是"新增批次不得以 ✅
        开头"，既有批次（本次持锁前已在快照里）合法转 ✅（sweep 或 CC 收工
        标记完成）不受影响——用"先注册待处理、本次持锁内编辑为已完成"复现
        这一合法路径（与 F1 用例集的"真正新增"场景区分开，见
        `test_new_batch_status_starting_with_check_mark_blocks_release`）。"""
        self._write_queue(section_two_rows=(
            "| B-TEST | `某个文件.md`、`queue.md` | `docs(test): 测试` | 待处理 |\n"
        ))
        self.assertEqual(self._acquire(who="A"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        text = text.replace(
            "| B-TEST | `某个文件.md`、`queue.md` | `docs(test): 测试` | 待处理 |",
            "| B-TEST | `某个文件.md`、`queue.md` | `docs(test): 测试` | "
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
            "| B-OLD | `某个文件.md`、`queue.md` | `docs(old): 历史遗留` | "
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
            "| B-NEW | `某个文件.md`、`queue.md` | `docs(test): 测试` | "
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
            "| B-NEW | `某个文件.md`、`queue.md` | `docs(test): 测试` | "
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

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmpdir.name)
        self.module = _load_module()
        self.module.REPO_ROOT = self.repo_root
        self.module.FOLLOWUP_README_TARGET = "README.md"
        self.target_path = self.repo_root / "README.md"

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write_readme(self, rows=""):
        text = "## 现有跟进信清单\n\n" + self.HEADER + rows
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
            "--cell", "无", "--cell", "待领", "--cell", "无", "--cell", "2026-08-07",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = self.target.read_text(encoding="utf-8")
        self.assertIn(
            "| 101 | 新任务 | CC | 无 | 无 | 待领 | 无 | 2026-08-07 |", text,
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
            "--cell", "无", "--cell", "待领", "--cell", "无", "--cell", "2026-08-07",
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
            "--cell", "B-测试批次", "--cell", "`文件.md`", "--cell", "说明", "--cell", "待处理",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = self.target.read_text(encoding="utf-8")
        self.assertIn("| B-测试批次 | `文件.md` | 说明 | 待处理 |", text)

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
            "--cell", "无", "--cell", "待领", "--cell", "无", "--cell", "2026-08-07",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    def test_missing_section_heading_rejected(self):
        self.target.write_text("没有任何分区标题的文件", encoding="utf-8")
        before = self.target.read_text(encoding="utf-8")
        result = self._append(
            "--section", "一", "--number", "101",
            "--cell", "新任务", "--cell", "CC", "--cell", "无",
            "--cell", "无", "--cell", "待领", "--cell", "无", "--cell", "2026-08-07",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)


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
            cell=["旁路任务", "CC", "无", "无", "待领", "无", "2026-08-11"],
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


if __name__ == "__main__":
    unittest.main()
