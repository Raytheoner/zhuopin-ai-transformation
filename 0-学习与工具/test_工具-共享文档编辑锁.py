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
import types
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


def _load_gate_query():
    """白盒 import `工具-跟进闸查询.py`（供 T6 两端同判用例比对 append 前置）。"""
    path = SCRIPT.parent / "工具-跟进闸查询.py"
    spec = importlib.util.spec_from_file_location("_gate_query_under_test", path)
    module = importlib.util.module_from_spec(spec)
    # 🔴 必须先注册进 `sys.modules` 再 exec：该模块体内有 `@dataclass`，而
    # dataclass 装饰器会回查 `sys.modules[cls.__module__].__dict__` 解注解，
    # 不注册就当场 AttributeError（实测撞过）。
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _queue_table():
    """取权威解析模块（队列 #455 用例要按读侧口径回读落盘结果）。

    经被测模块自身取，而不是本文件另写一份 `sys.path` 引导——被测模块顶部
    已有 worktree 路径引导（队列 #300），从它身上取到的必然是**本 worktree**
    那一份，不会静默拿到别的 worktree 经 `pip install -e` 顶替进去的版本。
    """
    return _load_module().queue_table


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
        """**跨度外**的真裸竖线仍一律拒绝——队列 #455 只放宽了"合法闭合
        反引号跨度内的竖线"那一半，这一半不放松（原用例名与断言保留，
        只更新 docstring：#455 之后拒绝它的是 ② 回读列数校验，不再是
        `has_bare_pipe`，见 `WriteGuardHardeningTests`）。"""
        r = self._run("append-row", "--section", "一", "--number", "510",
                      *self._positional("任务|撑列", "待领（CC）", "指针", "产出",
                                        "[S:open][D:机] x", "区", "2026-08-26"))
        self.assertEqual(r.returncode, 1)
        self.assertIsNone(self._row("510"))
        self.assertIn("回读列数", r.stdout)

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

    def test_mechanism_wip_rejection_no_longer_carries_candidates_but_keeps_ways_out(self):
        """🔴 队列 §一 #454（2026-09-06，OP-0906-N，Shao Peishen 答 D3=(a)）：
        **本用例已由"须附带候选清单"翻转为"不得再附带"**（tasks 5.3）。

        原判据（`#435` 子项 E）让主拒绝文案附上改判候选清单，帮被拦的 session
        执行出路⑴。2026-09-06 实测证明那条路走不通：**被拦的 session 无权改他人
        的行**（`#422` 先例），它对候选唯一能做的动作是给自己标 🛑 排队——那不是
        分诊，那是排队。候选改由 `工具-落库sweep.py` 第 12 类常驻轮次推给有权
        改判的人（one-in-one-out）。

        **翻转的只有候选清单这一段**：WIP 计数与"两条出路"必须原样还在——那才是
        "读者此刻该怎么办"的答案，退候选接线不等于把拒绝文案退成不可行动的。"""
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
        self.assertNotIn("改判候选清单", out)
        self.assertNotIn("#151", out)
        self.assertIn("两条出路", out)
        self.assertIn("3／2", out)  # WIP 计数仍在

    def test_reclassification_helpers_survive_the_retirement(self):
        """退的是**接线**、不是判据（spec「两函数 MUST 原样保留在该模块」）：
        `_suggest_status_reclassification()`／`_render_reclassification_candidates()`
        与 `STALE_STATUS_PHRASES` 必须仍在——sweep 侧的第 12 类正是靠它们取候选，
        判据的权威实现全项目只此一份。"""
        m = _load_module()
        self.assertTrue(callable(m._suggest_status_reclassification))
        self.assertTrue(callable(m._render_reclassification_candidates))
        self.assertTrue(m.STALE_STATUS_PHRASES)
        # 渲染侧的格式仍可用（它是那份格式的活文档，不是死代码）
        self.assertIn("改判候选清单",
                      m._render_reclassification_candidates([("151", "partial", "blocked", "片段")]))

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
        # 队列 ⓘ1（2026-09-04）：本用例只验证"空 §二 分区插入机制"本身，
        # 文件清单不是本用例焦点——`docs/文件.md` 这个占位路径从未真实
        # 存在过。新增的 git 落地性预检会对真实 REPO_ROOT（本用例走
        # 黑盒子进程，`--file` 是自定义临时文件，但 REPO_ROOT 解析与
        # `--file` 无关、恒定指向真实主仓，见 `_resolve_repo_root`）核验
        # 该片段是否落在脏集/未跟踪/最近 3 个 commit 内——用一个真实占位
        # 路径必然测不稳（依赖主仓当下的实时 git 状态）。改用范围性速记
        # `X/tests/test_*.py`（含通配符）——`_file_list_git_state_
        # violations` 与既有 `_file_list_path_violations` 同一豁免口径，
        # 对这类片段一律不做存在性核验，因此不依赖主仓实时状态、稳定可测。
        result = self._append(
            "--section", "二",
            "--cell", "B-测试批次", "--cell", "`X/tests/test_*.py`", "--cell", "说明", "--cell", "待处理",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = self.target.read_text(encoding="utf-8")
        self.assertIn("| B-测试批次 | `X/tests/test_*.py` | 说明 | 待处理 |", text)

    def test_bare_pipe_rejected(self):
        before = self.target.read_text(encoding="utf-8")
        result = self._append(
            "--section", "四", "--number", "51",
            "--cell", "A|B", "--cell", "Shao Peishen", "--cell", "不急",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    def test_backtick_wrapped_pipe_now_accepted(self):
        """🔴 **本用例于队列 #455（2026-09-05）整体反转，是 proposal 明写的
        BREAKING 行为修正，不是回归。**

        原用例名 `test_backtick_wrapped_pipe_also_rejected`，断言"反引号不
        豁免裸竖线检测"，其成立前提是 #258 apply 期写下的那句——**「本项目
        表格解析对反引号无感知」**。该前提已于队列 #314 失效：读侧
        `queue_table.split_row_cells` 自那时起按 CommonMark 游程规则识别
        跨度、跨度内竖线不算列分隔符（同文件
        `test_pipe_inside_backtick_no_longer_causes_column_mismatch` 即
        #314 当时同步反转的 release 侧对应用例）。写侧却一直没跟上，于是
        "写入时放行、release 又拒绝"的自相矛盾状态早已不存在，真正存在的是
        **反过来的矛盾：读侧放行、写侧拒绝** —— `#324` 就是被它锁死的
        （行内 4 处合法反引号包裹竖线 ⇒ 状态字段整格重写被拒 ⇒ 写定即锁死）。

        #455 让写侧口径追上读侧：合法闭合跨度内的竖线**放行**。真正会撑列
        的跨度外裸竖线仍被拒，见 `test_bare_pipe_rejected`。
        """
        result = self._append(
            "--section", "四", "--number", "51",
            "--cell", "`A|B`", "--cell", "Shao Peishen", "--cell", "不急",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = self.target.read_text(encoding="utf-8")
        self.assertIn("| 51 | `A|B` | Shao Peishen | 不急 |", text)
        # 落盘后按读侧回读，仍是 4 列——写侧与读侧口径一致。
        row = next(l for l in text.splitlines() if l.startswith("| 51 |"))
        self.assertEqual(len(_queue_table().split_row_cells(row)), 4)

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


class FollowupReadmeRowLengthGuardTests(unittest.TestCase):
    """`followup-readme-phase2` D3：跟进信 README 行长判据——「发送状态」
    列复用队列 `ROW_LENGTH_CAP_BYTES`（4 KB），「主要事项」列另立
    `README_TOPIC_CAP_BYTES`（600 B）。fixture 手法与
    `FollowupReadmeStructuralValidationTests` 一致（白盒 monkeypatch），
    冻结当前日期的手法复刻队列 ⑪ 测试的 `_freeze_module_now`。

    🔴 每个用例只改动**一个既有行**、且不新增行——避免触发两态语义／串行闸
    校验（那两项校验各自已有独立测试类覆盖），使行长判据能被单独观测。
    """

    HEADER = (
        "| 编号 | 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |\n"
        "|--------|------|--------|---------|---------|---------|\n"
    )
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

    def _write_readme(self, rows=""):
        text = (
            "## 现有跟进信清单\n\n" + self.HEADER + rows
            + "\n## 补件登记（不占编号、不占串行闸）\n\n" + self.SUPPLEMENT_HEADER
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

    def _freeze_module_now(self, year, month, day):
        real_datetime = datetime

        class _Frozen(real_datetime):
            @classmethod
            def now(cls, tz=None):
                base = real_datetime(year, month, day)
                return base.replace(tzinfo=tz) if tz is not None else base

        self.module.datetime = _Frozen

    @staticmethod
    def _long_status(filler_chars=1500):
        """中文字符 UTF-8 三字节，1500 个即 4500 B，必超 `ROW_LENGTH_CAP_
        BYTES`（4096 B）。"""
        return "⏳ 待你审｜历史填充：" + ("填" * filler_chars)

    @staticmethod
    def _long_topic(filler_chars=250):
        """250 个中文字符 ≈ 750 B，必超 `README_TOPIC_CAP_BYTES`（600 B）。"""
        return "事项：" + ("填" * filler_chars)

    def test_within_both_caps_no_warning(self):
        self._write_readme(
            "| 采购部#11 | 2026-08-05 | 采购部 · 姚祖怡 | 短事项 | 不急 | ⏳ 待你审 |\n"
        )
        self.assertEqual(self._acquire(who="A"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        text = text.replace("短事项", "短事项（已确认）")
        self.target_path.write_text(text, encoding="utf-8")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A")
        self.assertEqual(result, 0)
        self.assertNotIn("上限", buf.getvalue())

    def test_status_over_cap_warns_before_cutoff_does_not_block(self):
        """判据落地当天（2026-09-06）早于阻断日期 2026-09-13——超限只告警、
        不拒绝 release。"""
        long_status = self._long_status()
        self._write_readme(
            f"| 采购部#11 | 2026-08-05 | 采购部 · 姚祖怡 | 短事项 | 不急 | {long_status} |\n"
        )
        self.assertEqual(self._acquire(who="A"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        text = text.replace(long_status, long_status + "（追加一段）")
        self.target_path.write_text(text, encoding="utf-8")

        self._freeze_module_now(2026, 9, 6)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A")
        out = buf.getvalue()
        self.assertEqual(result, 0, "阻断日期前应仅告警、不拒绝 release")
        self.assertIn("采购部#11", out)
        self.assertIn("发送状态列", out)
        self.assertIn("上限", out)
        self.assertIn("仅告警不阻断", out)

    def test_status_over_cap_blocks_after_cutoff(self):
        """阻断日期（2026-09-13）当天或之后——超限拒绝 release，锁保持占用。"""
        long_status = self._long_status()
        self._write_readme(
            f"| 采购部#11 | 2026-08-05 | 采购部 · 姚祖怡 | 短事项 | 不急 | {long_status} |\n"
        )
        self.assertEqual(self._acquire(who="A"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        text = text.replace(long_status, long_status + "（追加一段）")
        self.target_path.write_text(text, encoding="utf-8")

        self._freeze_module_now(2026, 9, 13)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A")
        out = buf.getvalue()
        self.assertNotEqual(result, 0, "阻断日期起超限须拒绝 release")
        self.assertIn("发送状态列", out)
        self.assertIsNotNone(
            self.module._read_lock(self.module._lock_path(self.module.FOLLOWUP_README_TARGET)),
            "拒绝不等于释放，锁应保持占用",
        )

    def test_topic_over_cap_blocks_after_cutoff(self):
        """「主要事项」列另立 600 B 独立阈值——与「发送状态」列判据互不影响，
        单独触发时也能被拦。"""
        long_topic = self._long_topic()
        self._write_readme(
            f"| 采购部#11 | 2026-08-05 | 采购部 · 姚祖怡 | {long_topic} | 不急 | ⏳ 待你审 |\n"
        )
        self.assertEqual(self._acquire(who="A"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        text = text.replace(long_topic, long_topic + "（追加说明）")
        self.target_path.write_text(text, encoding="utf-8")

        self._freeze_module_now(2026, 9, 13)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A")
        out = buf.getvalue()
        self.assertNotEqual(result, 0, "阻断日期起超限须拒绝 release")
        self.assertIn("主要事项列", out)

    def test_waiver_marker_allows_release_after_cutoff(self):
        """行内 `行长豁免：<理由>` ⇒ 阻断日期起仍放行（任一超限列命中即放行
        该列，逃生阀是逐列独立判定，写在任一单元格内均可被扫到——本例写在
        发送状态列自身）。"""
        long_status = "⏳ 待你审｜行长豁免：K2 搬迁排期中，本周先保留｜历史填充：" + ("填" * 1500)
        self._write_readme(
            f"| 采购部#11 | 2026-08-05 | 采购部 · 姚祖怡 | 短事项 | 不急 | {long_status} |\n"
        )
        self.assertEqual(self._acquire(who="A"), 0)
        text = self.target_path.read_text(encoding="utf-8")
        text = text.replace(long_status, long_status + "（追加一段）")
        self.target_path.write_text(text, encoding="utf-8")

        self._freeze_module_now(2026, 9, 13)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A")
        out = buf.getvalue()
        self.assertEqual(result, 0, "逃生阀齐备应放行")
        self.assertIn("已放行", out)

    def test_untouched_historical_row_not_blocked_after_cutoff(self):
        """只对本次持锁期间 touched 的行生效——存量超限但本次未碰的行，
        阻断日期起也不应挡住 release。"""
        long_status = self._long_status()
        self._write_readme(
            f"| 采购部#11 | 2026-08-05 | 采购部 · 姚祖怡 | 短事项 | 不急 | {long_status} |\n"
            "| 财务部#5 | 2026-08-06 | 财务部 · 唐燕萍 | 另一事项 | 不急 | ⏳ 待你审 |\n"
        )
        self.assertEqual(self._acquire(who="A"), 0)
        # 本次只编辑财务部#5，不碰采购部#11（存量超限行）。
        text = self.target_path.read_text(encoding="utf-8")
        text = text.replace("另一事项", "另一事项（已更新）")
        self.target_path.write_text(text, encoding="utf-8")

        self._freeze_module_now(2026, 9, 13)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._release(who="A")
        self.assertEqual(result, 0, "未 touched 的存量超限行不应挡住本次 release")
        self.assertNotIn("上限", buf.getvalue())


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
        # 队列 ⓘ1（2026-09-04）：本类只测锁归属校验，不测文件清单内容——
        # 用范围性速记 `X/tests/test_*.py`（含通配符）而非占位真实路径，
        # 理由同 `AppendRowTests.test_append_to_empty_section_two` 上方
        # 注释：新增的 git 落地性预检不对这类片段做存在性核验，测试结果
        # 不随主仓当下的实时 git 状态漂移。
        return run("--file", self.target, "append-row", "--section", "二",
                   "--cell", "B-0823_1_测试", "--cell", "`X/tests/test_*.py`",
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


class WriteGuardHardeningTests(unittest.TestCase):
    """队列 #455（openspec 变更包 `editlock-write-guard-hardening`，
    Shao Peishen 2026-09-05 design 审逐条拍板）：写侧三缺陷合并处置。

    覆盖三条新判据的正例反例：① 新值反引号游程须闭合（不闭合即拒）；
    ② 拼装结果按读侧同款切列回读列数（不符即拒）；③ `edit-row --repair`
    只跳过"旧行列数须先合法"这一项，且须带 `修复说明：` 行内留痕，
    `append-row` 不接受该参数。

    🔴 **非恒真自证**见 `test_reverse_*` 三个用例：关掉/还原旧逻辑后，
    同一批输入必须由"拒绝"变回"放行"（或反之），证明结论确实来自本包
    新增的判据，而不是别处早已存在的某道检查顺手拦下的。
    """

    SECTION_ONE_HEADER = (
        "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|------|--------|-------------|----------|------|--------|------|\n"
    )
    # 正常 8 列行。
    GOOD_ROW = (
        "| 600 | 既有任务 | 待领（CC） | 指针 | 产出 | [S:open][D:机] 在办 | 区域 | 2026-09-05 |\n"
    )
    # `#324` 历史场景夹具：行内合法存在反引号包裹的竖线，整行仍是 8 列。
    # 这一行在 #455 之前会让 `edit-row` 的 `has_bare_pipe` 前置检查对任何
    # 含同类内容的**新值**报错，导致状态字段整格重写被拒、写定即锁死。
    BACKTICK_PIPE_ROW = (
        "| 601 | 引用 `a | b` 的任务 | 待领（CC） | 指针 | 产出 "
        "| [S:open][D:机] 在办 | 区域 | 2026-09-05 |\n"
    )
    # `#454` 历史场景夹具：**已塌列**的行（只有 7 列，缺「登记」列）——
    # 成因是写入的引文片段恰好在一个反引号处被截断，反引号配对全线错位，
    # 真正的列分隔符被当成受保护字符吞掉。#455 之前 `edit-row` 对它拒绝
    # 一切操作（含 `--append`），当次只能持锁状态下用脚本改文件绕过。
    COLLAPSED_ROW = (
        "| 602 | 塌列的历史行 | 待领（CC） | 指针 | 产出 "
        "| [S:blocked][D:机] 引文被截断：`工具-队列查询.py --row N | 区域 |\n"
    )

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.target = self.root / "toy-queue.md"
        self.target.write_text(
            "# 玩具队列\n\n## 一、任务看板\n\n"
            + self.SECTION_ONE_HEADER + self.GOOD_ROW
            + self.BACKTICK_PIPE_ROW + self.COLLAPSED_ROW
            + "\n## 二、待 commit 批次\n\n| 批次 | 文件清单 | 建议 message | 状态 |\n|---|---|---|---|\n"
            "\n## 四、需 Shao Peishen 的动作\n\n| # | 事项 | 等谁 | 截止 |\n|---|---|---|---|\n",
            encoding="utf-8",
        )
        self.qt = _queue_table()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _run(self, *args: str):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--file", str(self.target), *args],
            capture_output=True, text=True, encoding="utf-8",
        )

    def _row(self, number: str) -> str | None:
        for line in self.target.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"| {number} |"):
                return line
        return None

    def _cells(self, number: str) -> list[str]:
        return self.qt.split_row_cells(self._row(number) or "|") or []

    # ---------- 夹具自证：两条历史夹具确实是它们声称的形态 ----------

    def test_fixtures_are_what_they_claim(self):
        """先证夹具本身没写歪——否则后面所有断言都可能在测一个假场景。"""
        self.assertEqual(len(self._cells("601")), 8, "#324 夹具须是合法 8 列")
        self.assertIn("|", self._cells("601")[1], "#324 夹具的竖线须真的落在格内")
        self.assertEqual(len(self._cells("602")), 7, "#454 夹具须是已塌列的 7 列")

    # ---------- ① 反引号游程奇偶（tasks 3.1 / 3.2 / 3.3） ----------

    def test_31_unbalanced_backtick_in_new_value_rejected_without_writing(self):
        """3.1：新值含未闭合反引号游程 ⇒ 拒绝写入，且**不落盘**。"""
        before = self.target.read_text(encoding="utf-8")
        r = self._run("edit-row", "--section", "一", "--number", "600",
                      "--set", "状态=[S:done][D:机] 见 `工具-队列查询.py")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("未闭合的反引号游程", r.stdout)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before,
                         "拒绝时不得修改目标文件")

    def test_31b_append_row_unbalanced_backtick_rejected(self):
        """3.1 的 append-row 侧：同一判据装在两个入口上，不是只装一半。"""
        before = self.target.read_text(encoding="utf-8")
        r = self._run("append-row", "--section", "一", "--number", "610",
                      "--set", "任务=见 `工具-队列查询.py", "--set", "领取方=待领（CC）",
                      "--set", "输入指针=指针", "--set", "期望产出=产出",
                      "--set", "状态=[S:open][D:机] x", "--set", "触碰区=区",
                      "--set", "登记=2026-09-05")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("未闭合的反引号游程", r.stdout)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    def test_32_closed_backtick_span_containing_pipe_is_accepted(self):
        """3.2（#324 历史场景回归夹具）：反引号闭合、跨度内含竖线 ⇒ **放行**。

        这正是 #455 之前被 `has_bare_pipe` 一律拒绝、导致 #324 状态字段
        写定即锁死的那种值。"""
        r = self._run("edit-row", "--section", "一", "--number", "601",
                      "--set", "状态=[S:done][D:机] ✅ 已完成，判据见 `a | b` 一节")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        cells = self._cells("601")
        self.assertEqual(len(cells), 8, "放行后仍须是合法 8 列")
        self.assertIn("`a | b`", cells[5])

    def test_32b_locked_row_status_prefix_can_now_be_flipped(self):
        """3.2 的真正要害（#324 的伤害形态）：**含合法反引号竖线的行，其
        `[S:]` 前缀此前无法翻转**——`--append` 只能加尾巴，整格重写又被
        写侧竖线守卫拒绝，于是状态被锁死。本用例证明锁已解开。"""
        self.assertTrue(self._cells("601")[5].startswith("[S:open]"))
        r = self._run("edit-row", "--section", "一", "--number", "601",
                      "--set", "状态=[S:done][D:机] 已完成（原行含 `a | b`，前缀可翻转了）")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(self._cells("601")[5].startswith("[S:done]"))

    def test_33_odd_backtick_count_but_balanced_runs_is_accepted(self):
        """3.3 **非恒真自证**：反引号**总数为奇数**但游程全闭合 ⇒ 放行，
        证明实现没有偷懒用"总数奇偶"这个简化判据（design 决策点① 的 (b)）。

        取材＝生产队列 §一 #414 行的真实写法（apply 期 1.2 全量取证实测到
        的唯一一条奇数行）：用 CommonMark 双反引号游程包裹"内容本身是一个
        反引号"这件事。下面这个值共 5 个反引号——奇数，但两个双游程各自
        闭合、中间夹一个字面反引号，完全合法。"""
        value = "[S:done][D:机] bash 把 `` ` `` 当命令替换执行"
        self.assertEqual(value.count("`") % 2, 1, "夹具须真的是奇数个反引号")
        self.assertFalse(self.qt.has_unbalanced_backtick_run(value),
                         "游程配对下它应是合法的——若这里为 True，说明实现退化成了总数奇偶")
        r = self._run("edit-row", "--section", "一", "--number", "600",
                      "--set", f"状态={value}")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("`` ` ``", self._cells("600")[5])

    # ---------- ② 回读列数（tasks 3.4 / 3.5） ----------

    def test_34_readback_column_mismatch_rejected_without_writing(self):
        """3.4：拼装结果回读列数不符 ⇒ 拒绝写入，不落盘。"""
        before = self.target.read_text(encoding="utf-8")
        r = self._run("edit-row", "--section", "一", "--number", "600",
                      "--set", "触碰区=区域甲|区域乙")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("回读列数", r.stdout)
        self.assertIn("应为 8", r.stdout)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    def test_35_append_row_with_legal_backtick_pipe_reads_back_correctly(self):
        """3.5：`append-row` 新增行含合法反引号跨度内竖线 ⇒ 回读列数吻合、
        放行——证明 L2067 的裸 `str.split("|")` 确已换成反引号感知切列。"""
        r = self._run("append-row", "--section", "一", "--number", "611",
                      "--set", "任务=引用 `x | y` 的新任务", "--set", "领取方=待领（CC）",
                      "--set", "输入指针=指针", "--set", "期望产出=产出",
                      "--set", "状态=[S:open][D:机] 待领", "--set", "触碰区=区",
                      "--set", "登记=2026-09-05")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(self._cells("611")), 8)
        self.assertIn("`x | y`", self._cells("611")[1])

    # ---------- ③ --repair（tasks 3.6 / 3.7 / 3.8 / 3.9） ----------

    REPAIR_FIX = ("[S:done][D:机] 修复说明：该行引文被截断致塌列，本次补回闭合反引号与登记列")

    def test_36_collapsed_row_rejected_without_repair(self):
        """3.6：未传 `--repair`，已塌列行的任何操作（含 `--append`）⇒ 拒绝。
        默认路径不变，维持"不假装能安全编辑一个已经不知道结构的行"。"""
        before = self.target.read_text(encoding="utf-8")
        r = self._run("edit-row", "--section", "一", "--number", "602",
                      "--append", "状态=（追加一句）")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("列数为 7", r.stdout)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    def test_37_repair_with_reason_restores_row(self):
        """3.7：传 `--repair` 且改动后合法 ⇒ 写入成功，行列数恢复。

        🔴 塌列行是**少了一列**（7/8），故修复必须把缺失的「登记」列显式
        写回——`--repair` 会先把单元格补白到预期列数，使这一列可被 `--set`
        寻址；不补白的话该下标越界，`--repair` 将是一个永远不可能成功的
        开关（apply 期跑本用例当场撞出，见 `cmd_edit_row` 内长注释）。"""
        r = self._run("edit-row", "--section", "一", "--number", "602",
                      "--set", f"状态={self.REPAIR_FIX}",
                      "--set", "触碰区=区域", "--set", "登记=2026-09-05", "--repair")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        cells = self._cells("602")
        self.assertEqual(len(cells), 8, "修复后须恢复为合法 8 列")
        self.assertIn("修复说明：", cells[5], "④ 留痕须真的随行落盘、进 git")
        self.assertEqual(cells[7], "2026-09-05", "补白出的列须由调用方显式填回")

    def test_37b_repair_padding_does_not_bypass_key_cell_sentinels(self):
        """3.7 反例：补白**不是**放宽校验——补出来的空格子仍要过关键格
        哨兵。只补白、不把「状态」格填成合法机器字段 ⇒ 仍拒绝。"""
        before = self.target.read_text(encoding="utf-8")
        r = self._run("edit-row", "--section", "一", "--number", "602",
                      "--set", "状态=修复说明：只写了理由，丢了 [S:] 机器字段",
                      "--set", "触碰区=区域", "--set", "登记=2026-09-05", "--repair")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("状态", r.stdout)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    def test_37c_repair_leaves_over_long_rows_to_human_judgement(self):
        """3.7 边界：`--repair` **只补短、不裁长**——删列＝丢内容，且无从
        知道该并回哪一格。列数多于预期时如实拒绝，不猜。"""
        text = self.target.read_text(encoding="utf-8")
        self.target.write_text(text.replace(
            "| 600 | 既有任务 |", "| 600 | 多出一列 | 既有任务 |"), encoding="utf-8")
        self.assertEqual(len(self._cells("600")), 9)
        before = self.target.read_text(encoding="utf-8")
        r = self._run("edit-row", "--section", "一", "--number", "600",
                      "--set", "状态=[S:done][D:机] 修复说明：试图裁掉多出的列",
                      "--repair")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    def test_38a_repair_does_not_relax_backtick_parity(self):
        """3.8：传 `--repair` 但新值未过 ① 奇偶校验 ⇒ 仍拒绝。
        `--repair` 能且只能把一行从不合法改成合法，不能引入新的不合法。"""
        before = self.target.read_text(encoding="utf-8")
        r = self._run("edit-row", "--section", "一", "--number", "602",
                      "--set", "状态=[S:done][D:机] 修复说明：补回 `未闭合的引用",
                      "--set", "触碰区=区域", "--repair")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("未闭合的反引号游程", r.stdout)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    def test_38b_repair_does_not_relax_readback_column_count(self):
        """3.8 另一半：传 `--repair`，但修复动作**自己又引入了一处撑列**
        （新值里带跨度外裸竖线）⇒ 回读列数仍不符 ⇒ 仍拒绝。

        证明 `--repair` 能且只能把一行从不合法改成合法，不能在修复过程中
        引入新的不合法——② 对它一项不放宽。"""
        before = self.target.read_text(encoding="utf-8")
        r = self._run("edit-row", "--section", "一", "--number", "602",
                      "--set", f"状态={self.REPAIR_FIX}",
                      "--set", "触碰区=区域甲|区域乙",
                      "--set", "登记=2026-09-05", "--repair")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("回读列数", r.stdout)
        self.assertIn("--repair", r.stdout, "拒绝文案须说明 --repair 不放宽本项")
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    def test_39_append_row_rejects_repair_and_points_to_edit_row(self):
        """3.9（design 决策点⑤）：`append-row --repair` ⇒ 明确拒绝，
        且**带去向**（指向 `edit-row --repair`），不是 argparse 的
        "unrecognized arguments"。"""
        before = self.target.read_text(encoding="utf-8")
        r = self._run("append-row", "--section", "四", "--number", "52",
                      "--set", "事项=x", "--set", "等谁=Shao Peishen",
                      "--set", "截止=不急", "--repair")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("不接受 `--repair`", r.stdout)
        self.assertIn("edit-row", r.stdout)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    # ---------- ④ 行内留痕（design 决策点④，Shao Peishen 拍板 (a)） ----------

    def test_repair_without_reason_marker_is_inert(self):
        """④：`--repair` 不带 `修复说明：` ⇒ 视为未传，塌列行照旧拒绝。"""
        before = self.target.read_text(encoding="utf-8")
        r = self._run("edit-row", "--section", "一", "--number", "602",
                      "--set", "状态=[S:done][D:机] 修好了", "--set", "触碰区=区域",
                      "--repair")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("未生效", r.stdout)
        self.assertIn("修复说明：", r.stdout, "拒绝文案须给出正确写法")
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    def test_repair_reason_placeholder_does_not_count(self):
        """④ 反例：只是在**描述**这条规则（写了字面占位符 `<理由>`）不算
        真实留痕——判据与 `_has_genuine_row_length_waiver` 逐字同源。"""
        r = self._run("edit-row", "--section", "一", "--number", "602",
                      "--set", "状态=[S:done][D:机] 修复说明：<理由>",
                      "--set", "触碰区=区域", "--repair")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("未生效", r.stdout)

    def test_repair_without_reason_is_rejected_even_on_a_healthy_row(self):
        """④ 读法钉死：`--repair` 缺留痕 ⇒ **整次调用被拒**，而不是"静默当
        没传、继续按默认路径写入"。

        两种读法只在"目标行本来就合法"这一种情形上有差异（本用例），取严的
        代价仅是多一条提示、不可能丢数据；取松则会让塌列行上的调用方收到
        「列数为 7，应为 8」这条答非所问的报错。理由见 `cmd_edit_row` 内注释。"""
        before = self.target.read_text(encoding="utf-8")
        r = self._run("edit-row", "--section", "一", "--number", "600",
                      "--set", "状态=[S:done][D:机] 合法行，但没写修复说明", "--repair")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("未生效", r.stdout)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before,
                         "取严读法：拒绝时不得写入")

    def test_repair_flag_is_inert_on_healthy_rows(self):
        """`--repair` 对本来就合法的行不改变任何结果（只跳过一项前置检查，
        不是"跳过校验"的总开关）——含理由时正常写入，其余判据照跑。"""
        r = self._run("edit-row", "--section", "一", "--number", "600",
                      "--set", "状态=[S:done][D:机] 修复说明：顺手复核，本行本就合法",
                      "--repair")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(self._cells("600")), 8)

    # ---------- 3.10 反向用例：非恒真自证 ----------

    def test_reverse_31_passes_once_the_new_parity_judge_is_disabled(self):
        """3.10-a：把 ① 判据 mock 成恒 False（＝本包实现前的状态），3.1 的
        同一输入必须由"拒绝"变成"放行"——证明拒绝确实来自新增判据本身，
        不是别处早已存在的某道检查顺手拦下的。

        （② 不会替 ① 兜底：未闭合游程被读侧当普通文本处理，回读列数不变，
        所以关掉 ① 之后这条真的会落盘——这正是 ① 存在的理由。）"""
        m = _load_module()
        bad_value = "[S:done][D:机] 见 `工具-队列查询.py"
        ns = argparse.Namespace(
            file=str(self.target), section="一", number="600", who="",
            set=[f"状态={bad_value}"], append=[], changes_json=None,
            stdin_json=False, append_sep=" ", domain=None, repair=False,
        )
        with unittest.mock.patch.object(
            m.queue_table, "has_unbalanced_backtick_run", lambda _t: False
        ):
            rc = m.cmd_edit_row(ns)
        self.assertEqual(rc, 0, "关掉 ① 之后旧行为＝放行；若这里非 0，说明本用例"
                                "测的不是 ①，断言不成立")
        self.assertIn("`工具-队列查询.py", self._cells("600")[5])

    def test_reverse_35_old_naive_split_gives_a_different_verdict(self):
        """3.10-b：② 那一处替换（裸 `str.split("|")` → `split_row_cells`）
        的行为差异，在 #324 夹具上直接比给出来。

        旧实现会把合法跨度内的竖线数成额外的列 ⇒ 9 列 ≠ 8 ⇒ 拒绝一条完全
        正常的行；新实现回读得 8 列 ⇒ 放行。**两者在同一输入上结论相反**，
        故 `test_35_...` 的放行确实来自这次替换。"""
        line = "| 611 | 引用 `x | y` 的新任务 | 待领（CC） | 指针 | 产出 | [S:open][D:机] 待领 | 区 | 2026-09-05 |"
        naive = [c.strip() for c in line.strip("|").split("|")]
        new = self.qt.split_row_cells(line)
        self.assertEqual(len(new), 8, "新实现（反引号感知）应回读为 8 列")
        self.assertNotEqual(len(naive), 8, "旧实现（裸 split）应把它数错")
        self.assertEqual(len(naive), 9)

    def test_reverse_34_bare_pipe_now_rejected_by_readback_not_has_bare_pipe(self):
        """3.10-c：证明 `has_bare_pipe` 前置检查**确已移除**，且 3.4 的拒绝
        来自 ② 而非它——把 `has_bare_pipe` 换成"一被调用就炸"，3.4 的同一
        输入仍须被正常拒绝（走到 ② 并返回 1，而不是抛异常）。

        若旧的前置检查还在，这里会抛 `AssertionError: has_bare_pipe 不该
        再被写侧准入路径调用`，用例变红。"""
        m = _load_module()

        def _boom(_cell):
            raise AssertionError("has_bare_pipe 不该再被写侧准入路径调用")

        ns = argparse.Namespace(
            file=str(self.target), section="一", number="600", who="",
            set=["触碰区=区域甲|区域乙"], append=[], changes_json=None,
            stdin_json=False, append_sep=" ", domain=None, repair=False,
        )
        before = self.target.read_text(encoding="utf-8")
        with unittest.mock.patch.object(m.queue_table, "has_bare_pipe", _boom):
            rc = m.cmd_edit_row(ns)
        self.assertEqual(rc, 1)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    def test_repair_filter_stays_pinned_to_queue_table_message(self):
        """`--repair` 靠"重建 `validate_row_cells` 的列数 problem 前缀"来
        精确滤掉那一条。本用例把这层耦合钉住：`queue_table` 那侧改了文案而
        编辑锁没跟 ⇒ 这里变红，而不是静默退化成"什么都没滤掉"（--repair
        失效）或"滤掉了别的项"（放行了不该放行的）。"""
        problems = self.qt.validate_row_cells("一", ["x"] * 7, source="parsed")
        expected_total = self.qt.SECTION_COLUMN_COUNTS["一"]
        prefix = f"§一 列数为 7，应为 {expected_total}"
        self.assertTrue(
            any(p.startswith(prefix) for p in problems),
            f"queue_table 的列数 problem 文案已变，编辑锁 --repair 的滤除前缀须同步："
            f"期望以 {prefix!r} 开头，实得 {problems!r}",
        )


class CredentialShapeGuardTests(unittest.TestCase):
    """队列 #480（openspec 变更包 `editlock-credential-shape-guard`，
    Shao Peishen 2026-09-06 design 审当场拍板五点）：写入侧「凭据形状即拒」闸。

    覆盖：反例（四条结构化规则 ＋ 通用启发式，两个入口各一）／正例（正常
    队列文本、叙述性占位符写法）／拒绝文案含出路且不回显完整值／④⑤ 两条
    边界（`--note` 不被拦、含凭据形状的历史行改其它列不被误拒）／fail-loud。

    🔴 **非恒真自证**见 `test_38_*`：把判据加载器 mock 成"零条规则"（＝本包
    实现前的状态），3.1 的同一输入必须由**拒绝变放行并真的落盘**——证明拒绝
    确实来自本包新增判据，而不是别处早已存在的某道检查顺手拦下。

    ⚠️ **本文件里的假凭据一律用拼接构造、不写成字面量**：`工具-密钥扫描lint.py`
    的四条结构化 `CREDENTIAL_PATTERNS` 对**测试文件同样生效**（它只对通用
    启发式那一族跳过测试文件），写成字面量会让 CI `凭据扫描` job 当场变红。
    """

    # ---------- 形状合规的固定假串（非任何真实凭据，拼接以避开 CI 自扫） ----------
    FAKE_WEBHOOK = (
        "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key="
        + "0000dead-beef-0000-1111-222233334444"
    )
    FAKE_AWS = "AKIA" + "TESTONLYFAKE0000"
    FAKE_PRIVATE_KEY_HEADER = "-----BEGIN " + "RSA " + "PRIVATE KEY-----"
    FAKE_ANTHROPIC = "sk-ant-" + "TESTONLYFAKE0000000000000"
    # 通用启发式反例：变量名含 SECRET，右值是带匹配引号的字面量、非占位符、
    # 非纯大写标识符、长度 ≥8 —— 四道过滤全部越过。
    FAKE_GENERIC = 'WECOM_WEBHOOK_SECRET = "' + "fakeSecret1234567890" + '"'

    SECTION_ONE_HEADER = (
        "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|------|--------|-------------|----------|------|--------|------|\n"
    )
    GOOD_ROW = (
        "| 700 | 既有任务 | 待领（CC） | 指针 | 产出 | [S:open][D:机] 在办 | 区域 | 2026-09-06 |\n"
    )
    # ⑤ 边界夹具：**历史行的某一格已经含凭据形状**（`#351` 的真实形态）。
    # 本闸只校验本次新值 ⇒ 改这一行的**其它列**不得被误拒，把该列改写成
    # `<REDACTED>` 也不得被拒——否则唯一能修复它的入口把自己也关上了
    # （`#324`／`#454` 的形态，`#455` 为此不得不专造 `--repair`）。
    LEGACY_ROW_WITH_CREDENTIAL = (
        "| 701 | 历史行：IT 群 webhook "
        + FAKE_WEBHOOK
        + " | 待领（CC） | 指针 | 产出 | [S:open][D:机] 在办 | 区域 | 2026-08-24 |\n"
    )

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.target = self.root / "toy-queue.md"
        self.target.write_text(
            "# 玩具队列\n\n## 一、任务看板\n\n"
            + self.SECTION_ONE_HEADER + self.GOOD_ROW + self.LEGACY_ROW_WITH_CREDENTIAL
            + "\n## 二、待 commit 批次\n\n| 批次 | 文件清单 | 建议 message | 状态 |\n|---|---|---|---|\n"
            "\n## 四、需 Shao Peishen 的动作\n\n| # | 事项 | 等谁 | 截止 |\n|---|---|---|---|\n",
            encoding="utf-8",
        )
        self.qt = _queue_table()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _run(self, *args: str):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--file", str(self.target), *args],
            capture_output=True, text=True, encoding="utf-8",
        )

    def _row(self, number: str) -> str | None:
        for line in self.target.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"| {number} |"):
                return line
        return None

    def _cells(self, number: str) -> list[str]:
        return self.qt.split_row_cells(self._row(number) or "|") or []

    def _append_args(self, number: str, **overrides: str) -> list[str]:
        cells = {
            "任务": "占位任务", "领取方": "待领（CC）", "输入指针": "指针",
            "期望产出": "产出", "状态": "[S:open][D:机] 待领", "触碰区": "区",
            "登记": "2026-09-06",
        }
        cells.update(overrides)
        args = ["append-row", "--section", "一", "--number", number]
        for name, value in cells.items():
            args += ["--set", f"{name}={value}"]
        return args

    # ---------- 夹具自证 ----------

    def test_fixtures_are_what_they_claim(self):
        """先证假串真的命中判据、且历史行夹具确实是 8 列——否则后面所有
        断言都可能在测一个假场景（同 `#455` 的夹具自证惯例）。"""
        m = _load_module()
        lint = m._load_credential_lint_module()
        labels = {label for label, pat in lint.CREDENTIAL_PATTERNS
                  if pat.search(self.FAKE_WEBHOOK)}
        self.assertEqual(labels, {"企微 webhook 真实 key 参数"})
        self.assertEqual(len(self._cells("701")), 8, "⑤ 边界夹具须是合法 8 列")
        self.assertIn("qyapi.weixin.qq.com", self._cells("701")[1])

    # ---------- 3.1 / 3.2 反例：两个入口各一 ----------

    def test_31_edit_row_rejects_credential_shape_without_writing(self):
        """3.1：`edit-row --set` 写入形状合规的假 key ⇒ 返回 1、点名规则、
        **目标文件字节不变**。"""
        before = self.target.read_bytes()
        r = self._run("edit-row", "--section", "一", "--number", "700",
                      "--set", f"状态=[S:done][D:机] 群机器人 {self.FAKE_WEBHOOK}")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("企微 webhook 真实 key 参数", r.stdout)
        self.assertIn("「状态」格", r.stdout)
        self.assertEqual(self.target.read_bytes(), before, "拒绝时不得修改目标文件")

    def test_32_append_row_rejects_credential_shape_without_writing(self):
        """3.2：同一假串走 `append-row` ⇒ 同上。**与 3.1 成对存在**，证明
        判据装在**两个**入口上，不是只装了一半。"""
        before = self.target.read_bytes()
        r = self._run(*self._append_args(
            "710", 任务=f"记录群 webhook {self.FAKE_WEBHOOK}"))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("企微 webhook 真实 key 参数", r.stdout)
        self.assertIn("「任务」格", r.stdout)
        self.assertEqual(self.target.read_bytes(), before)

    # ---------- 3.3 其余三条结构化规则各一条，各自点名到正确的规则 ----------

    def test_33_each_structured_rule_is_named_individually(self):
        """3.3：AWS／私钥头／`sk-ant-` 三条各测一次，拒绝文案须点名**那一条**
        规则名，而不是笼统一句"命中凭据"。"""
        cases = [
            (self.FAKE_AWS, "AWS Access Key"),
            (self.FAKE_PRIVATE_KEY_HEADER, "私钥文件头"),
            (self.FAKE_ANTHROPIC, "Anthropic API Key"),
        ]
        for payload, label in cases:
            with self.subTest(rule=label):
                before = self.target.read_bytes()
                r = self._run("edit-row", "--section", "一", "--number", "700",
                              "--set", f"触碰区={payload}")
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn(label, r.stdout)
                self.assertEqual(self.target.read_bytes(), before)

    def test_33b_generic_assignment_rule_is_named(self):
        """决策点① ＝ (b) 的那一族：通用启发式命中也须点名到变量名。

        🔴 **本用例是 (a)/(b) 之别的唯一钉子**——若日后有人把范围偷偷改回
        (a)（只取结构化四条），这里会立刻变红，而不是静默留出漏网面。"""
        before = self.target.read_bytes()
        r = self._run("edit-row", "--section", "一", "--number", "700",
                      "--set", f"触碰区=配置片段：{self.FAKE_GENERIC}")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("WECOM_WEBHOOK_SECRET", r.stdout)
        self.assertEqual(self.target.read_bytes(), before)

    # ---------- 3.4 / 3.5 正例 ----------

    def test_34_normal_queue_text_is_unaffected(self):
        """3.4 正例：正常队列文本（中文叙述／反引号包路径／`[S:]` 状态串／
        `.env` 指针写法）⇒ 返回 0、正常落盘。"""
        value = ("[S:done][D:机] ✅ 已完成，推送地址见 `.env` 的 "
                 "`WECOM_WEBHOOK_URL_OPS`，判据见 `工具-密钥扫描lint.py`")
        r = self._run("edit-row", "--section", "一", "--number", "700",
                      "--set", f"状态={value}")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(self._cells("700")), 8)
        self.assertIn("WECOM_WEBHOOK_URL_OPS", self._cells("700")[5])

    def test_35_placeholder_prose_is_not_a_false_positive(self):
        """3.5 正例：「环境变量 `XKY_APP_KEY=<value>`」这类叙述 ＋ 占位符写法
        ⇒ 放行。钉住 lint 的 `PLACEHOLDER_VALUE_RE`／标识符／长度三重过滤
        确实在起作用——这正是 lint 排除 `.md` 时担心的那种句子。"""
        for value in (
            "环境变量 `XKY_APP_KEY=<value>` 由运维配置",
            'API_TOKEN = "TODO"',
            '_GATE_ENV_VAR = "ZP_GATE_PASSWORD"',
        ):
            with self.subTest(value=value):
                r = self._run("edit-row", "--section", "一", "--number", "700",
                              "--set", f"触碰区={value}")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    # ---------- 3.6 / 3.7 拒绝文案 ----------

    def test_36_rejection_message_carries_a_way_out(self):
        """3.6：拒绝文案必须给出路，不是只有一句"拒绝"。"""
        r = self._run("edit-row", "--section", "一", "--number", "700",
                      "--set", f"状态={self.FAKE_WEBHOOK}")
        self.assertEqual(r.returncode, 1)
        self.assertIn(".env", r.stdout)
        self.assertIn("指针", r.stdout)
        self.assertIn("WECOM_WEBHOOK_URL_OPS", r.stdout, "须给出可照抄的替代写法")

    def test_37_rejection_message_does_not_echo_the_full_hit(self):
        """3.7：拒绝文案**不得**回显完整命中串（决策点③ ＝ 前 8 字符 ＋ 截断
        标记）——拒绝的目的正是让这串东西不被传播，而终端 scrollback 恰恰
        最容易被再粘一次。"""
        m = _load_module()
        r = self._run("edit-row", "--section", "一", "--number", "700",
                      "--set", f"状态={self.FAKE_WEBHOOK}")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn(self.FAKE_WEBHOOK, r.stdout, "完整命中串不得出现在文案里")
        self.assertNotIn("0000dead-beef", r.stdout, "key 主体不得出现在文案里")
        self.assertIn("已截断", r.stdout)
        self.assertEqual(m.CREDENTIAL_HIT_PREFIX_LEN, 8,
                         "决策点③ ＝ (b) 前 8 字符；改这个数须回 design 决策点，"
                         "🔴 尤其不得为了「与 lint 的 24 字符对齐」而改")

    # ---------- 3.8 非恒真自证 ----------

    def test_38_zero_rule_stub_turns_rejection_back_into_a_write(self):
        """3.8：把 `_load_credential_lint_module` mock 成返回"零条规则"的桩
        （＝本包实现前的状态）⇒ 3.1 的同一输入由**拒绝变放行并真的落盘**。

        证明两件事：⑴ 拒绝确实来自本包新增判据，不是别处早已存在的某道检查
        顺手拦下；⑵ 编辑锁内**不存在第二份复制的判据**（若复制了，桩换不掉它，
        这里仍会被拒，用例变红）。"""
        m = _load_module()
        empty_lint = types.SimpleNamespace(
            CREDENTIAL_PATTERNS=[],
            GENERIC_ASSIGNMENT_RE=re.compile(r"(?!x)x"),  # 恒不匹配
            _looks_like_real_secret=lambda _n, _v: False,
        )
        ns = argparse.Namespace(
            file=str(self.target), section="一", number="700", who="",
            set=[f"状态=[S:done][D:机] {self.FAKE_WEBHOOK}"], append=[],
            changes_json=None, stdin_json=False, append_sep=" ",
            domain=None, repair=False,
        )
        with unittest.mock.patch.object(
            m, "_load_credential_lint_module", lambda: empty_lint
        ):
            rc = m.cmd_edit_row(ns)
        self.assertEqual(rc, 0, "关掉判据之后旧行为＝放行；若这里非 0，说明本用例"
                                "测的不是本包新增的那道闸，断言不成立")
        self.assertIn("qyapi.weixin.qq.com", self._cells("700")[5],
                      "关掉判据后同一输入须真的落盘")

    # ---------- 3.9 fail-loud ----------

    def test_39_unloadable_criteria_fails_loud_not_silent_pass(self):
        """3.9：判据正本不可加载 ⇒ 报错退出、文案点名**文件路径与修复方向**，
        **不静默放行**、也不只抛一个未加工的 traceback。"""
        m = _load_module()

        def _boom():
            raise RuntimeError("模拟：判据正本被改名")

        ns = argparse.Namespace(
            file=str(self.target), section="一", number="700", who="",
            set=["状态=[S:done][D:机] 完全正常的值"], append=[],
            changes_json=None, stdin_json=False, append_sep=" ",
            domain=None, repair=False,
        )
        before = self.target.read_bytes()
        buf = io.StringIO()
        with unittest.mock.patch.object(m, "_load_credential_lint_module", _boom), \
                contextlib.redirect_stdout(buf):
            rc = m.cmd_edit_row(ns)
        out = buf.getvalue()
        self.assertEqual(rc, 1, "fail-closed：判据不可用时不得放行")
        self.assertIn("工具-密钥扫描lint.py", out, "须点名判据正本文件路径")
        self.assertIn("修复方向", out)
        self.assertEqual(self.target.read_bytes(), before)

    # ---------- 决策点 ④⑤ 的边界 ----------

    def test_boundary_04_note_channel_is_not_guarded(self):
        """④ ＝ (a) 的边界：作用面**不含** `acquire --note`（锁文件被
        `.gitignore:69:*.editlock*` 覆盖、不进 git）。

        ⚠️ 这不是"note 是安全的"——note 被回显后若再被粘进队列行，**那一次
        粘贴走的仍是本闸**（见下方 3.1/3.2），覆盖是闭合的，不是留了个洞。"""
        r = self._run("acquire", "--who", "tester", "--note",
                      f"待记录：群机器人 {self.FAKE_WEBHOOK}")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lock = json.loads(Path(str(self.target) + ".editlock").read_text(encoding="utf-8"))
        self.assertIn("qyapi.weixin.qq.com", lock["note"], "note 通道确未被本闸拦截")

    def test_boundary_05_legacy_row_other_columns_still_editable(self):
        """⑤ ＝ (a) 的边界之一：**历史行的某一格已含凭据形状**时，改该行的
        **其它列**不得被误拒——校验对象只是本次新值，不是改动后的整行。"""
        r = self._run("edit-row", "--section", "一", "--number", "701",
                      "--set", "状态=[S:done][D:机] ✅ 已闭环")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(self._cells("701")[5].startswith("[S:done]"))

    def test_boundary_05b_legacy_credential_can_be_redacted(self):
        """⑤ 的要害（`#324`／`#454` 的伤害形态）：把含凭据形状的那一格**改写
        成 `<REDACTED>` 指针**这个修复动作本身必须被放行。

        若按 (b) 校验改动后整行，这一步会被拒 ⇒ 唯一能修复它的入口把自己
        也关上了，那正是 `#455` 不得不专造 `--repair` 的那口井。"""
        r = self._run("edit-row", "--section", "一", "--number", "701",
                      "--set", "任务=历史行：IT 群 webhook `<REDACTED-见§四#118>`")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("REDACTED", self._cells("701")[1])
        self.assertNotIn("qyapi.weixin.qq.com", self._cells("701")[1])

    # ---------- 判据正本唯一 ----------

    def test_no_credential_regex_literal_is_copied_into_editlock(self):
        """spec「判据正本唯一，复用不重写」的机器守：编辑锁源码里**不得**
        出现任何凭据形状正则的字面量。

        判据取自 lint 本体的 `CREDENTIAL_PATTERNS`／`GENERIC_ASSIGNMENT_RE`
        的 `.pattern` 字符串——lint 那侧改了正则，这里自动跟着比对新的那个，
        不需要在本文件维护第二份"禁止出现的字符串"清单。"""
        m = _load_module()
        lint = m._load_credential_lint_module()
        source = SCRIPT.read_text(encoding="utf-8")
        patterns = [p.pattern for _label, p in lint.CREDENTIAL_PATTERNS]
        patterns.append(lint.GENERIC_ASSIGNMENT_RE.pattern)
        for pat in patterns:
            with self.subTest(pattern=pat[:40]):
                self.assertNotIn(pat, source,
                                 "判据正本恒在 `工具-密钥扫描lint.py`，编辑锁只加载不复制"
                                 "——两处判据分叉正是 `#312` 付过学费的形态")


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


class FileListGitStateViolationTests(unittest.TestCase):
    """ⓘ1（2026-09-04）：§二「文件清单」git 落地性预检
    ——`_file_list_git_state_violations`。

    成因：sweep 每轮约 13 个批次被跳过，根因是登记时「文件清单」写了不是
    真实存在、这一批确实改过的路径——非路径的文字说明、"同名 docx"/"同上"
    这类偷懒速记、或路径写错；sweep 校验不过就静默跳过，登记方长期零反馈
    （2026-09-04 甚至因此引发一次主仓分叉事故）。本判据在既有 ⑶
    `_file_list_path_violations`（只管格式）之外新增一层：反引号串还须
    命中主仓当前 git 状态（脏集∪未跟踪∪最近 3 个 commit）之一。

    白盒方式：真实临时 git 仓库 + `_load_module()` 独立模块实例，
    monkeypatch `REPO_ROOT` 指向该仓库——与既有 `ReleaseStructuralValidation
    Tests._make_git_repo_with_committed_queue` 同一惯例，不依赖也不影响
    真实主仓的实时 git 状态。
    """

    def setUp(self):
        self.m = _load_module()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.m.REPO_ROOT = self.root
        self._git("init", "-q")
        self._git("config", "user.email", "t@example.com")
        self._git("config", "user.name", "t")
        # 基线提交——没有它 `git log -3` 在空仓库上会失败，⑵ 会整体
        # fail-open 跳过，届时"应拒绝"的用例会假绿。
        (self.root / "README.md").write_text("baseline", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-qm", "baseline")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _git(self, *args: str):
        return subprocess.run(["git", *args], cwd=self.root,
                              capture_output=True, text=True, encoding="utf-8")

    def _violations(self, file_list: str, status: str = "待处理"):
        return self.m._file_list_git_state_violations(
            ["B-TEST", file_list, "msg", status], self.root,
        )

    # ---------------- 情形①：合格——真实路径命中三种 git 状态之一 ----------------

    def test_modified_tracked_file_in_dirty_set_passes(self):
        """脏集：已跟踪文件被本地修改、尚未提交。"""
        (self.root / "已跟踪.py").write_text("v1", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-qm", "track it")
        (self.root / "已跟踪.py").write_text("v2", encoding="utf-8")
        self.assertEqual(self._violations("`已跟踪.py`"), [])

    def test_untracked_new_file_passes(self):
        """未跟踪：新建但从未 `git add` 过的文件。"""
        (self.root / "新文件.md").write_text("x", encoding="utf-8")
        self.assertEqual(self._violations("`新文件.md`"), [])

    def test_untracked_nested_path_passes(self):
        """未跟踪、且写成含斜杠的嵌套仓库相对路径。"""
        (self.root / "sub").mkdir()
        (self.root / "sub" / "nested.py").write_text("x", encoding="utf-8")
        self.assertEqual(self._violations("`sub/nested.py`"), [])

    def test_recently_committed_file_passes(self):
        """最近 3 个 commit 内：文件已提交、当前工作区已干净。"""
        (self.root / "近期提交.py").write_text("x", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-qm", "add recent file")
        self.assertEqual(self._violations("`近期提交.py`"), [])

    # ---------------- 情形②：路径不存在 ----------------

    def test_nonexistent_path_rejected(self):
        """反引号串是路径形态（有扩展名、带目录），但磁盘上根本没有这个
        文件，也不在任何 git 状态里——须拒绝。"""
        violations = self._violations("`4-数字员工/不存在的场景/不存在的文件.py`")
        self.assertTrue(violations)
        self.assertIn("未在主仓 git 状态里找到对应实体", violations[0])

    # ---------------- 情形③：非路径反引号文本（自然语言描述） ----------------

    def test_natural_language_description_rejected(self):
        """反引号里是一段自然语言描述，既不含斜杠也不含扩展名，仓库根下
        也没有同名文件——不是 `_looks_like_non_file_bare_token` 认得的
        flag／代码引用形态，须拒绝。"""
        violations = self._violations("`本次仅完成口径确认，无产出文件`")
        self.assertTrue(violations)
        self.assertIn("不是合格的仓库根相对路径", violations[0])

    # ---------------- 情形④：速记（同名/同上） ----------------

    def test_shorthand_same_as_above_rejected(self):
        violations = self._violations("`同上`")
        self.assertTrue(violations)
        self.assertIn("速记引用", violations[0])

    def test_shorthand_same_name_docx_rejected(self):
        violations = self._violations("`同名 docx`")
        self.assertTrue(violations)
        self.assertIn("速记引用", violations[0])

    # ---------------- 既有豁免口径不因新判据而失效 ----------------

    def test_preregistered_row_is_exempt(self):
        status = self.m.PREREGISTERED_STATUS_PREFIX + "，收工时精确化）"
        self.assertEqual(self._violations("`不存在的文件.py`", status=status), [])

    def test_wildcard_and_directory_prefix_still_exempt_from_existence_check(self):
        """反例：⑶ 已用真实数字（98 个）证明"范围性速记加存在性校验＝大量
        误报"——本项新增的 ⑵ 存在性核验不得把这条已验证的豁免收窄回去。"""
        self.assertEqual(self._violations("`X/tests/test_*.py`"), [])
        self.assertEqual(self._violations("`openspec/changes/x/{proposal,design}.md`"), [])
        self.assertEqual(self._violations("`4-数字员工/采购部/`"), [])

    def test_non_path_bare_tokens_still_exempt(self):
        """反例：flag／代码引用／范列举式非路径文本——⑶ 既有豁免面原样保留。"""
        self.assertEqual(self._violations("`--force-mechanism-wip`"), [])
        self.assertEqual(self._violations("`queue_table.iter_queue_paths()`"), [])
        self.assertEqual(self._violations("`采购/财务/质量`"), [])

    def test_git_state_unavailable_skips_existence_check_but_keeps_shape_check(self):
        """`repo_root` 不在 git 工作树内（⑵ 拿不到基线）时 fail-open——只
        跳过⑵存在性核验，⑴/ⓐ 的格式与速记判据依然生效，不因此连带失效。"""
        non_git_dir = Path(tempfile.mkdtemp())
        try:
            # ⑴ 依然生效：绝对路径这一形态格式违规。
            self.assertTrue(self.m._file_list_git_state_violations(
                ["B-TEST", "`C:\\x\\y.md`", "msg", "待处理"], non_git_dir,
            ))
            # ⑵ 静默跳过：形态合法但"存不存在"这一步无从核验，不误伤。
            self.assertEqual(self.m._file_list_git_state_violations(
                ["B-TEST", "`4-数字员工/x/y.py`", "msg", "待处理"], non_git_dir,
            ), [])
        finally:
            non_git_dir.rmdir()

    # ---------------- append-row／edit-row 集成生效（真正接线，非只是函数存在） ----------------

    SECTION_TWO_HEADER = (
        "| 批次 | 文件清单 | 建议 message | 状态 |\n"
        "|------|---------|--------------|------|\n"
    )

    def _write_queue(self, path: Path, section_two_rows: str = "") -> None:
        path.write_text(
            "## 二、待 commit 批次（CC 取活销行）\n\n" +
            self.SECTION_TWO_HEADER + section_two_rows,
            encoding="utf-8",
        )

    def test_append_row_rejects_shorthand_file_list(self):
        target = self.root / "test-queue.md"
        self._write_queue(target)
        ns = argparse.Namespace(
            file=str(target), section="二", number=None,
            cell=["B-集成测试", "`同上`", "说明", "待处理"], domain=None,
        )
        self.assertEqual(self.m.cmd_append_row(ns), 1)
        self.assertNotIn("B-集成测试", target.read_text(encoding="utf-8"))

    def test_append_row_accepts_real_untracked_file(self):
        target = self.root / "test-queue.md"
        self._write_queue(target)
        (self.root / "真实新文件.py").write_text("x", encoding="utf-8")
        ns = argparse.Namespace(
            file=str(target), section="二", number=None,
            cell=["B-集成测试2", "`真实新文件.py`", "说明", "待处理"], domain=None,
        )
        self.assertEqual(self.m.cmd_append_row(ns), 0)
        self.assertIn("B-集成测试2", target.read_text(encoding="utf-8"))

    def test_edit_row_rejects_nonexistent_path_written_into_file_list(self):
        target = self.root / "test-queue.md"
        self._write_queue(
            target, "| B-既有批次 | `真实新文件.py` | 说明 | 待处理 |\n",
        )
        (self.root / "真实新文件.py").write_text("x", encoding="utf-8")
        ns = argparse.Namespace(
            file=str(target), section="二", number="B-既有批次",
            set=["文件清单=`压根不存在的路径/x.py`"], append=[],
            changes_json=None, stdin_json=False, append_sep="、", domain=None,
        )
        self.assertEqual(self.m.cmd_edit_row(ns), 1)
        self.assertIn("`真实新文件.py`", target.read_text(encoding="utf-8"),
                       "未通过预检时不得改动目标文件")

    def test_edit_row_accepts_valid_edit(self):
        target = self.root / "test-queue.md"
        self._write_queue(
            target, "| B-既有批次 | `真实新文件.py` | 说明 | 待处理 |\n",
        )
        (self.root / "真实新文件.py").write_text("x", encoding="utf-8")
        ns = argparse.Namespace(
            file=str(target), section="二", number="B-既有批次",
            set=["状态=✅ 已处理"], append=[],
            changes_json=None, stdin_json=False, append_sep="、", domain=None,
        )
        self.assertEqual(self.m.cmd_edit_row(ns), 0)
        self.assertIn("✅ 已处理", target.read_text(encoding="utf-8"))


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

    def _run(self, queue_texts, lock_data=None, note=""):
        """🔴 第四个实参自 2026-09-07（队列 #416 ⑶）起是**一个字符串**——本
        持锁窗口的 acquire note（＋本次 `release --waiver`，由生产调用点拼
        接）。**它曾经是一个 `waiver_sources: list[str]`**，里面还塞着"本次
        触碰过的队列行"，而那正是 `#416` ⑶ 的病灶：豁免一旦落盘就会被后来
        的、与它无关的持锁窗口捡到。签名收成字符串之后，想再加来源必须改
        签名——改签名的人会看见这条注释。"""
        return self.m._registration_completeness_violations(
            queue_texts, lock_data or {}, self.root, note,
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

    # ── 逃生阀（2026-09-07 时间维收窄，队列 #416 ⑶）─────────────────
    #
    # 🔴 **这一组用例的共同判据：豁免必须「一次一用」，而一次一用只能用
    # 时间维判据。** 旧口径的取材面是"本次 note ＋ 本次触碰过的队列行"，
    # 想表达一次一用，用的却是空间维（这段文字在不在我碰过的范围里）；而
    # 只要那段文字**落了盘**，它就会被后来的、与它无关的持锁窗口反复取到。
    def _waiver(self, body: str) -> str:
        return f"{self.m.REGISTRATION_WAIVER_MARKER}{body}"

    def test_named_waiver_in_note_passes(self):
        """点名了本次真实脏文件的豁免 ⇒ 放行。"""
        self._dirty("某文件.md")
        note = self._waiver("某文件.md（作者 OP-测试，到期 12-31）")
        self.assertEqual(self._run(self._queue(), note=note), [])

    def test_blanket_waiver_is_rejected(self):
        """🔴 **本变更包的立项事由。** 一句「他线脏文件由其作者线自登」此前
        把 `uncovered` 里全部未登记脏文件当场放行——不论它们是谁的、有几个、
        是不是真的会有人去登。2026-09-07 16:21 一轮 sweep 实测：21 个孤儿、
        来自 ≥5 个会话、最老 18 小时、**无一自登**。
        """
        self._dirty("某文件.md")
        violations = self._run(self._queue(), note=self._waiver("他线脏文件由其作者线自登"))
        self.assertEqual(len(violations), 1)
        self.assertIn("没有点名任何有效路径", violations[0])

    def test_blanket_waiver_message_differs_from_no_waiver(self):
        """泛豁免与"压根没写豁免"的拒绝文案必须可区分——不可区分的后果是
        写豁免的人以为工具没读到他那句话，于是把它写得更宽。"""
        self._dirty("某文件.md")
        blanket = self._run(self._queue(), note=self._waiver("他线脏文件由其作者线自登"))[0]
        silent = self._run(self._queue(), note="本次只改队列行")[0]
        self.assertIn(self.m.REGISTRATION_WAIVER_MARKER, blanket)
        self.assertNotIn("没有点名任何有效路径", silent)
        self.assertNotEqual(blanket, silent)

    def test_named_waiver_releases_only_named_files(self):
        """D2：**只放行点名件**。旧实现一命中标记就 `return []`——2026-09-07
        `OP-0907-AM` 本人持锁时实测输出「点名 19 个 / 放行 16 个」，那三个
        数字对不上它也不看。"""
        self._dirty("甲.md")
        self._dirty("乙.md")
        violations = self._run(self._queue(), note=self._waiver("甲.md（作者 OP-测试，到期 12-31）"))
        self.assertEqual(len(violations), 1)
        self.assertIn("乙.md", violations[0])
        self.assertNotIn("- 甲.md", violations[0])
        self.assertIn("已点名放行 1 个", violations[0])

    def test_stale_inline_waiver_in_touched_row_no_longer_passes(self):
        """🔴 **用 `#382` 任务列那句真实残留做用例**（队列 #416 ⑶ 派单件指名）。

        原文至今躺在 `#382` 的任务列里，且它**点了名、格式也不难看**——正因
        为如此，旧口径下任何一次碰了那一行的持锁都会把它当成本次的豁免，把
        当刻工作区里任何未登记脏文件一并放行。本用例把它原样放进一条**本次
        触碰过**的队列行，note 里不写豁免 ⇒ 应仍然拒绝。

        ⚠️ **这条用例本身证明不了收窄，如实记在这里**：它直接调校验函数，而
        "本次触碰过的队列行"是**调用点**拼进 `waiver_sources` 的，白盒走不到
        那一步（反向对照实测：本条在 master 版上同样是绿的）。真正的证明是
        `ReleaseWaiverCliTests::test_stale_waiver_in_touched_queue_row_no_
        longer_passes_end_to_end`——那条走真 CLI 完整时间线，在 master 版上
        放行、在本版上拒绝。本条留着的价值是**让读者一眼看见那句残留长什么
        样**。
        """
        residue = (
            "登记豁免：`.claude/settings.local.json`"
            "（并发 session 遗留的本机个人配置，不属本线改动、不入库，留待其属主处置）"
        )
        self._dirty("某文件.md")
        rows = (f"| B-旧 | `x/y.md` | msg | 待处理 {residue} |\n",)
        violations = self._run(self._queue(*rows), note="")
        self.assertEqual(len(violations), 1)
        self.assertIn("某文件.md", violations[0])
        # 队列行里的残留连"检测到标记"都不该触发——它压根不在取材面里。
        self.assertNotIn("没有点名任何有效路径", violations[0])

    def test_expired_waiver_does_not_pass(self):
        """到期已过 ⇒ 整条失效，等同没写。"""
        from datetime import date, timedelta
        yesterday = date.today() - timedelta(days=1)
        self._dirty("某文件.md")
        note = self._waiver(
            f"某文件.md（作者 OP-测试，到期 {yesterday.month:02d}-{yesterday.day:02d}）")
        self.assertTrue(self._run(self._queue(), note=note))

    def test_unexpired_waiver_passes(self):
        from datetime import date, timedelta
        tomorrow = date.today() + timedelta(days=1)
        self._dirty("某文件.md")
        note = self._waiver(
            f"某文件.md（作者 OP-测试，到期 {tomorrow.month:02d}-{tomorrow.day:02d}）")
        self.assertEqual(self._run(self._queue(), note=note), [])

    def test_waiver_without_due_defaults_to_today(self):
        """决策 3＝(a)：缺 `到期` ⇒ 当日有效（不是永久有效、也不是失效）。"""
        self._dirty("某文件.md")
        self.assertEqual(self._run(self._queue(), note=self._waiver("某文件.md")), [])

    def test_due_year_inference_survives_year_boundary(self):
        """跨年：12-31 写下的豁免在 01-02 读到，不该被解成"11 个月前已过期"。"""
        from datetime import date
        self.assertEqual(
            self.m._resolve_waiver_due_date(12, 31, today=date(2027, 1, 2)),
            date(2027, 12, 31),
        )
        self.assertEqual(
            self.m._resolve_waiver_due_date(1, 2, today=date(2026, 12, 31)),
            date(2027, 1, 2),
        )

    def test_waiver_separator_and_backtick_variants(self):
        """不为格式差异拒掉一次合法豁免：`；`／`;`／`、` 与反引号都接受。"""
        for sep in ("；", ";", "、"):
            with self.subTest(sep=sep):
                self._dirty("甲.md")
                self._dirty("乙.md")
                note = self._waiver(f"`甲.md`{sep}乙.md（作者 OP-测试，到期 12-31）")
                self.assertEqual(self._run(self._queue(), note=note), [])

    def test_waiver_naming_nonexistent_path_is_not_valid(self):
        """点名了一个既不在工作树、也不在本次脏文件集合里的路径 ⇒ 不算有效，
        整条按泛豁免拒。"""
        self._dirty("某文件.md")
        note = self._waiver("根本不存在的/文件.md（作者 OP-测试，到期 12-31）")
        violations = self._run(self._queue(), note=note)
        self.assertEqual(len(violations), 1)
        self.assertIn("没有点名任何有效路径", violations[0])

    def test_named_waiver_also_covers_status_failure(self):
        """取数失败时豁免仍适用，但适用的是"点名了真实文件"的豁免。"""
        self._dirty("某文件.md")
        note = self._waiver("某文件.md（作者 OP-测试，到期 12-31）")
        with unittest.mock.patch.object(self.m, "_local_git_status_paths", return_value=None):
            self.assertEqual(self._run(self._queue(), note=note), [])

    def test_blanket_waiver_still_rejected_on_status_failure(self):
        """🔴 取数失败 ＋ 一句谁也没点名的豁免 ＝ 最该停下的组合。"""
        self._dirty("某文件.md")
        with unittest.mock.patch.object(self.m, "_local_git_status_paths", return_value=None):
            violations = self._run(self._queue(), note=self._waiver("他线脏文件由其作者线自登"))
        self.assertEqual(len(violations), 1)
        self.assertIn("fail-closed", violations[0])

    def test_deleted_dirty_file_can_be_named(self):
        """有效路径 ＝ 工作树内存在**或**出现在本次脏文件集合中。后半句不是
        冗余：被删除的脏文件在磁盘上恰恰不存在，只按"存在"判会把一次合法的
        删除豁免拒掉。"""
        seed = self.root / "seed.txt"
        seed.unlink()
        note = self._waiver("seed.txt（作者 OP-测试，到期 12-31）")
        self.assertEqual(self._run(self._queue(), note=note), [])

    def test_registration_waiver_scope_excludes_touched_rows(self):
        """判据锚定：⑹ 的第四个形参是**一个字符串**（本次 note），不是
        `waiver_sources` 列表。把它改回列表的人会看见这条变红——而"取材面
        多了一个会落盘的来源"正是 `#416` ⑶ 的整个病灶。"""
        import inspect
        params = list(inspect.signature(
            self.m._registration_completeness_violations).parameters)
        self.assertEqual(params[3], "acquire_note")


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


class ReleaseWaiverCliTests(unittest.TestCase):
    """`release --waiver` 的真 CLI ＋ 真 git 仓库端到端（队列 §一 #416 ⑶，
    Shao Peishen 2026-09-07 答决策 2＝(b)）。

    🔴 **为什么必须有真 CLI 用例、白盒调函数不够**：本参数存在的**唯一**
    理由，是 D1 收窄之后留下的那个缺口——豁免只认本持锁窗口的 acquire
    note，而 note 在窗口内改不了。这个缺口只在"真的先 acquire、中途工作区
    变脏、再 release"这条时间线上才成立；直接调校验函数是看不见它的。

    同 `ShadowCopyCrossWorktreeTests` 惯例：脚本复制进真实 git 仓库，黑盒
    子进程跑，不 monkeypatch 任何常量。
    """

    MECH_REL = Path("1-转型规划") / "0-全景路线图" / "跨桌任务队列-机制环境.md"
    QUEUE_BODY = (
        "## 二、待 commit 批次\n\n"
        "| 批次 | 文件清单 | 建议 message | 状态 |\n"
        "|------|---------|--------------|------|\n"
    )

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name) / "repo"
        self.root.mkdir()
        self._git("init", "-q")
        self._git("config", "user.email", "t@example.com")
        self._git("config", "user.name", "t")
        (self.root / "0-学习与工具").mkdir()
        self.tool = self.root / "0-学习与工具" / "工具-共享文档编辑锁.py"
        self.tool.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
        # opener 守卫（#437）从**同目录兄弟**加载判据正本，取不到即 fail-loud
        # （#493 刻意不回退成本地简化版）。真 CLI 用例必须把它一起带上，
        # 否则测的是"环境缺件"而不是本次改动。
        opener_lint = SCRIPT.with_name("工具-opener块lint.py")
        (self.root / "0-学习与工具" / opener_lint.name).write_text(
            opener_lint.read_text(encoding="utf-8"), encoding="utf-8")
        # 加载 opener lint 会产生 `__pycache__/*.pyc`——生产仓库的
        # `.gitignore` 覆盖它，玩具仓库不带就会被 ⑹ 判成一个"孤儿脏文件"，
        # 测出来的是环境差异而不是本次改动。
        (self.root / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        (self.root / self.MECH_REL).parent.mkdir(parents=True)
        (self.root / self.MECH_REL).write_text(self.QUEUE_BODY, encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-qm", "init")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=self.root, check=True,
                              capture_output=True, text=True)

    def _acquire(self, note: str = "本次只改队列行") -> subprocess.CompletedProcess:
        return run_at(self.tool, "acquire", "--who", "OP-测试", "--note", note)

    def _release(self, *extra: str) -> subprocess.CompletedProcess:
        return run_at(self.tool, "release", "--who", "OP-测试", *extra)

    def test_mid_window_dirty_file_can_be_waived_at_release(self):
        """**本参数的立项场景**：acquire 时工作区干净，持锁中途另一个并发
        会话弄脏了一个文件 —— note 里不可能事先写上它。"""
        acq = self._acquire()
        self.assertEqual(acq.returncode, 0, acq.stdout + acq.stderr)
        (self.root / "别人的在办件.md").write_text("并发会话的改动", encoding="utf-8")

        blocked = self._release()
        self.assertEqual(blocked.returncode, 1)
        self.assertIn("别人的在办件.md", blocked.stdout + blocked.stderr)

        ok = self._release("--waiver", "登记豁免：别人的在办件.md（作者 OP-他线，到期 12-31）")
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertIn("点名放行", ok.stdout)

    def test_blanket_waiver_on_cli_is_rejected(self):
        """🔴 反例：`--waiver` 不是一个"想放行就放行"的开关——泛豁免在这条
        路上同样被拒，否则它就成了给 D3 开的后门。"""
        self.assertEqual(self._acquire().returncode, 0)
        (self.root / "别人的在办件.md").write_text("并发会话的改动", encoding="utf-8")
        r = self._release("--waiver", "登记豁免：他线脏文件由其作者线自登")
        self.assertEqual(r.returncode, 1)
        self.assertIn("没有点名任何有效路径", r.stdout + r.stderr)

    def test_waiver_only_releases_named_file(self):
        """反例：`--waiver` 点名一个，另一个仍拦。"""
        self.assertEqual(self._acquire().returncode, 0)
        (self.root / "甲.md").write_text("x", encoding="utf-8")
        (self.root / "乙.md").write_text("y", encoding="utf-8")
        r = self._release("--waiver", "登记豁免：甲.md（作者 OP-测试，到期 12-31）")
        self.assertEqual(r.returncode, 1)
        self.assertIn("乙.md", r.stdout + r.stderr)

    def test_waiver_is_recorded_in_lock_history(self):
        """留痕：放行理由落进锁 history，下一次 acquire 的回显会打出来——
        同 `进度豁免：` 既有惯例，不新起一套。**放行了什么、凭什么放行，
        必须有人能在事后看见。**"""
        self.assertEqual(self._acquire().returncode, 0)
        (self.root / "别人的在办件.md").write_text("并发会话的改动", encoding="utf-8")
        waiver = "登记豁免：别人的在办件.md（作者 OP-他线，到期 12-31）"
        self.assertEqual(self._release("--waiver", waiver).returncode, 0)

        lock_file = (self.root / self.MECH_REL).with_suffix(".md.editlock")
        history = json.loads(lock_file.read_text(encoding="utf-8"))["history"]
        self.assertTrue(any("release --waiver" in e.get("note", "") for e in history))

    def test_stale_waiver_in_touched_queue_row_no_longer_passes_end_to_end(self):
        """🔴 **`#416` ⑶ 的真正证明，必须走真 CLI。**

        白盒那条同名用例（`RegistrationCompletenessTests::test_stale_inline_
        waiver_in_touched_row_no_longer_passes`）**证明不了收窄**——它直接调
        校验函数，而"本次触碰过的队列行"是**调用点**拼进去的，白盒根本走不到
        那一步（反向对照实测：它在 master 版上同样是绿的）。**如实记在这里，
        不让一条自我感觉良好的用例冒充证据。**

        本用例走完整时间线：acquire → 在队列行里写下一句点了名的旧豁免 →
        另有一个它**没**点名的脏文件 → release。旧口径下那句行内豁免会被
        当成本次的豁免、把该脏文件一并放行；新口径下取材面只有 note ⇒ 拒绝。
        （反向对照：本条在 master 版上是绿的通过态，在本版上必须拒绝。）
        """
        self.assertEqual(self._acquire(note="本次不写任何豁免").returncode, 0)
        queue = self.root / self.MECH_REL
        queue.write_text(
            queue.read_text(encoding="utf-8")
            + "| B-旧 | `x/y.md` | msg | 待处理 "
              "登记豁免：`别的文件.md`（历史残留，不属本线改动，不入库） |\n",
            encoding="utf-8")
        (self.root / "没被点名的脏文件.md").write_text("并发会话的改动", encoding="utf-8")

        r = self._release()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("没被点名的脏文件.md", r.stdout + r.stderr)

    def test_waiver_does_not_leak_into_next_hold_window(self):
        """🔴 **本变更包的核心断言：一次一用。** 上一把锁上用过的 `--waiver`
        对下一把锁**不生效**——它随进程消失，不落盘到任何会被再次读到的
        地方。若哪天有人把它写进 note 之外的持久位置，这条会变红。"""
        self.assertEqual(self._acquire().returncode, 0)
        (self.root / "别人的在办件.md").write_text("并发会话的改动", encoding="utf-8")
        waiver = "登记豁免：别人的在办件.md（作者 OP-他线，到期 12-31）"
        self.assertEqual(self._release("--waiver", waiver).returncode, 0)

        # 第二把锁：同样的脏文件还在，但这次不带 --waiver ⇒ 必须被拦。
        self.assertEqual(self._acquire().returncode, 0)
        again = self._release()
        self.assertEqual(again.returncode, 1)
        self.assertIn("别人的在办件.md", again.stdout + again.stderr)


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
        """opener 豁免的取材面 ＝ 本次 note ＋ 本次触碰过的队列行（不含队列
        全文）。

        🔴 **同时是「只收窄 ⑹ 一项」的反例锚点**（队列 #416 ⑶，2026-09-07）：
        `登记豁免：` 的取材面已被收窄成"只有本次 note"，而**本项一个字没
        动**。三项此前共用同一个 `waiver_sources` 列表，图省事把那个列表
        整体收窄，就会顺手改掉这道门禁的对外语义——而它既没立项、也没取证。
        这条用例存在的意义：那样做的人会看见它变红。
        """
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

    # ── 形态⑥（队列 §一 #487，(甲)）：看护者 Task/Agent 派发的子任务泳道
    #     opener 不该有 set_session_title——本守卫与 lint CLI 逐字复用同一判据，
    #     此处只验证「有没有正确传上下文」，不重复 lint 自身的单测。────────
    def test_watcher_pattern_lane_without_title_passes(self):
        """`## 三bis` 之前的块（§三 泳道 opener）不放 title 是正确写法，
        不该被形态①误伤（同 lint 模块 `_is_subtask_lane_block` 判据）。"""
        path = self.root / "看护件-x.md"
        path.write_text("\n".join([
            "### A1 · 示例泳道", "", "粘贴端：CC ｜ 泳道：示例泳道", "",
            "```", self.TITLE_LINE_CC, self.SETTINGS_CC, "做什么：建造到底。", "```", "",
            "## 三bis、看护opener（单次粘贴，Task/Agent 工具起子任务）", "",
            "```", "[OP-0905-C]【CC】看护示例", self.SETTINGS_CC, self.TITLE_LINE_WITH_EXC, "```",
        ]), encoding="utf-8")
        self.assertEqual(self._run(), [])

    def test_watcher_pattern_lane_with_title_rejects_f6(self):
        """同一结构，但 §三 泳道 opener 错误保留了 title ⇒ 应命中 F6，
        而不是被旧判据放行或误判成别的形态。"""
        path = self.root / "看护件-y.md"
        path.write_text("\n".join([
            "### A1 · 示例泳道", "", "粘贴端：CC ｜ 泳道：示例泳道", "",
            "```", self.TITLE_LINE_CC, self.SETTINGS_CC, self.TITLE_LINE_WITH_EXC, "```", "",
            "## 三bis、看护opener（单次粘贴，Task/Agent 工具起子任务）", "",
            "```", "[OP-0905-C]【CC】看护示例", self.SETTINGS_CC, self.TITLE_LINE_WITH_EXC, "```",
        ]), encoding="utf-8")
        violations = self._run()
        self.assertEqual(len(violations), 1)
        self.assertIn("F6", violations[0])

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

    # ── 队列 §一 #493 ⑴／#489 ⑴：判据正本自己的占位符不是违规 ────
    #: 中性陪衬块：只为把 opener 块数顶到 `C0` 门槛（≥2，见 `#489` ⑴ 防外溢条）。
    #: 不含 title、不含例外句 ⇒ 对 C1/C2 零影响；首行与六字段皆占位符原形 ⇒ 自身不报。
    CANON_FILLER = (
        "[OP-MMDD-X]【Cowork】<短名，≤12字>\n"
        "【设置】执行环境：Cowork ｜ 分支：master ｜ worktree：☐ ｜ 工作区：无 ｜ "
        "session：新开 ｜ 派出线：<线名 OP-MMDD-X>\n"
        "读 CLAUDE.md。"
    )

    def _write_canon(self, rel: str, role: str, *body_lines: str) -> None:
        """写一份**自称判据正本**的件（`#489` ⑴ 起判据是 frontmatter 声明，不是路径）。"""
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        lint = self.m._load_opener_lint_module()
        path.write_text(
            "---\ntitle: \"夹具\"\nstatus: 生效\n"
            f"{lint.CANON_ROLE_KEY}: {role}\n---\n\n"
            + "```\n" + "\n".join(body_lines) + "\n```\n\n"
            + "```\n" + self.CANON_FILLER + "\n```\n",
            encoding="utf-8")

    def test_format_canon_placeholders_do_not_block_release(self):
        """🔴 `#493` 立项形态：`opener骨架.md` 一脏，release 就被**它自己的
        格式正本**判成 8 处违规、锁保持占用（2026-09-06 15:53 UTC 主仓实跑
        坐实，`#398` ⑺「sweep 自撞锁」当天四轮的触发源）。

        判据正本在 lint 本体（`canon_role`／`check_canon_file`），此处
        只验 release 侧把上下文传对了——不重复 lint 自身那些单测。"""
        lint = self.m._load_opener_lint_module()
        self._write_canon(lint.SKELETON_CANON_REL, lint.CANON_ROLE_SKELETON,
                          "[OP-MMDD-X]【CC】<短名，≤12字>", self.SETTINGS_CC,
                          '开工第一件事：调 mcp__ccd_session_mgmt__set_session_title'
                          '（session_id 传字面量 "self"），标题：[Win]MMDDX-<短名>。'
                          "🔴 例外：你若是被 Task/Agent 起的子任务，跳过本行不要执行。")
        self.assertEqual(self._run(), [])

    def test_format_canon_drift_still_blocks(self):
        """🔴 **换判据，不是关掉**：正本的占位符自己漂了，照样拦。"""
        lint = self.m._load_opener_lint_module()
        self._write_canon(lint.SKELETON_CANON_REL, lint.CANON_ROLE_SKELETON,
                          "[OP-0907-Z]【CC】随手写的", self.SETTINGS_CC,
                          '开工第一件事：调 mcp__ccd_session_mgmt__set_session_title'
                          '（session_id 传字面量 "self"），标题：[Win]MMDDX-<短名>。'
                          "🔴 例外：你若是被 Task/Agent 起的子任务，跳过本行不要执行。")
        violations = self._run()
        self.assertEqual(len(violations), 1)
        self.assertIn("C5", violations[0])

    # ── 队列 §一 #489 ⑴：模板库同样被覆盖（此前不在名单里，恒报 13 处）──
    def test_template_library_role_does_not_block_release(self):
        """🔴 `#489` ⑴ 立项形态：`专线opener模板库.md` **不在 `#493` 那份路径名单里**
        ⇒ release 侧对它恒报 13 处，每次触碰都被迫写一次 `opener豁免：`；
        **豁免用滥则守卫失效**。改成声明式判据后本侧自动覆盖到它。"""
        lint = self.m._load_opener_lint_module()
        self._write_canon("1-转型规划/0-全景路线图/专线opener模板库.md",
                          lint.CANON_ROLE_LIBRARY,
                          "【设置】执行环境：**CC** ｜ 分支：master ｜ worktree：☐",
                          "开工第一件事：调 set_session_title，标题：[Win]MMDDX-〔主题短名〕。"
                          "🔴 例外：你若是被 Task/Agent 起的子任务，跳过本行不要执行。",
                          "读队列 §二 取批次。")
        self.assertEqual(self._run(), [])

    def test_fake_canon_claim_still_blocks(self):
        """🔴 防外溢：普通派单件贴一行 `opener正本:` 想躲开 F3/F5 ⇒ `C0` 点名、
        且原形态照报，声明什么也换不来。"""
        lint = self.m._load_opener_lint_module()
        path = self.root / "派单件-冒充.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\ntitle: \"冒充\"\nstatus: 生效\n"
            f"{lint.CANON_ROLE_KEY}: {lint.CANON_ROLE_LIBRARY}\n---\n\n"
            + "```\n" + "\n".join([
                "[OP-MMDD-X]【CC】某个活", self.SETTINGS_CC,
                '开工第一件事：调 mcp__ccd_session_mgmt__set_session_title'
                '（session_id 传字面量 "self"），标题：[Win]MMDDX-<短名>。'
                "🔴 例外：你若是被 Task/Agent 起的子任务，跳过本行不要执行。",
            ]) + "\n```\n",
            encoding="utf-8")
        violations = self._run()
        self.assertEqual(len(violations), 1)
        self.assertIn("C0", violations[0])
        self.assertIn("F3", violations[0])

    # ── 队列 §一 #493 ⑵：归属分流（无人值守持有者的出路）─────────
    #     🔴 判据＝「违规落不落在本次持锁者触碰过的文件里」，不是「持锁者是谁」
    #     ——按身份开豁免就是 `SELF_COMMITTING_LOCK_HOLDERS` 那条路，而人类会话
    #     同样修不了别人的文件（`#493` 原文：「对人类会话是硬拦截」）。
    def _lock(self, *dirty_at_acquire: str) -> dict:
        return {"who": "某会话", "dirty_at_acquire": list(dirty_at_acquire)}

    def test_violation_in_others_file_downgrades_to_warning(self):
        """acquire 之前就已经脏、且不在本次 §二 清单里 ⇒ 降级为告警、放行。

        2026-09-07 06:0x 实撞原形：被拦下的是**另一条会话正在写的**看护件
        （`看护件-泳道看护批B-0907_E-2026-09-07.md:61` 缺 `[OP-MMDD-X]` 前缀，
        **判得对**），而持锁者是 sweep——它既没造成、也管不了那处违规，只能把
        锁扣到 30 分钟陈旧，期间全员写队列被拒。"""
        self._write_block("看护件-他线在办.md", self.SETTINGS_CC, "读队列。")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            violations = self.m._opener_guard_violations(
                self.root, [], self._lock("看护件-他线在办.md"), {})
        self.assertEqual(violations, [])
        # 🔴 降级 ≠ 静默：那一处仍须**逐条打印**并说明由谁承接。
        self.assertIn("看护件-他线在办.md", out.getvalue())
        self.assertIn("不落在本次持锁者触碰过的文件里", out.getvalue())
        self.assertIn("这不是关掉守卫", out.getvalue())

    def test_violation_in_own_new_file_still_blocks(self):
        """持锁期间新出现的（不在 acquire 快照里）＝ 本次持锁者弄脏的 ⇒ 照旧拒绝。
        这才是 `#437` 要守的那一半：自己刚写坏的 opener 马上要粘出去。"""
        self._write_block("派单件-本次新写.md", self.SETTINGS_CC, "读队列。")
        violations = self.m._opener_guard_violations(
            self.root, [], self._lock("别的文件.md"), {})
        self.assertEqual(len(violations), 1)
        self.assertIn("F1", violations[0])

    def test_preexisting_but_registered_in_own_batch_still_blocks(self):
        """🔴 **反例，堵规避口**：「先写坏 opener、再 acquire」会让它落进
        acquire 快照、看着像别人的。但脏文件要不被 ⑹ 拦死就必须登进 §二，
        一登进来就重新归本人管 ⇒ 照旧拒绝。两道守卫互锁。"""
        self._write_block("派单件-先写后锁.md", self.SETTINGS_CC, "读队列。")
        queue_texts = {"queue-mech.md": "\n".join([
            "## 二、待 commit 批次", "",
            "| 批次 | 文件清单 | 建议 message | 状态 |",
            "|------|---------|--------------|------|",
            "| B-0907_V | `派单件-先写后锁.md` | docs(x) | 待处理 |",
            "",
        ])}
        violations = self.m._opener_guard_violations(
            self.root, [], self._lock("派单件-先写后锁.md"), queue_texts)
        self.assertEqual(len(violations), 1)
        self.assertIn("F1", violations[0])

    def test_no_acquire_snapshot_blocks_everything(self):
        """🔴 **判不了归属 ≠ 判定不归我**（同 ⑹ 的 fail-closed 方向）：没有
        acquire 快照时一律判「归我」，行为与本项引入前逐字一致。"""
        self._write_block("派单件-无快照.md", self.SETTINGS_CC, "读队列。")
        violations = self.m._opener_guard_violations(
            self.root, [], {"who": "某会话"}, {})
        self.assertEqual(len(violations), 1)
        self.assertIn("F1", violations[0])

    def test_others_violation_printed_even_when_own_also_blocks(self):
        """本次自己也有一处被拦时，别人那处**照样打印**——否则「本次被拦了」
        会把别人那几处一起变成静默。"""
        self._write_block("派单件-本次新写.md", self.SETTINGS_CC, "读队列。")
        self._write_block("看护件-他线在办.md", self.SETTINGS_CC, "读队列。")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            violations = self.m._opener_guard_violations(
                self.root, [], self._lock("看护件-他线在办.md"), {})
        self.assertEqual(len(violations), 1)
        self.assertIn("派单件-本次新写.md", violations[0])
        self.assertNotIn("看护件-他线在办.md", violations[0])
        self.assertIn("看护件-他线在办.md", out.getvalue())

    def test_waiver_does_not_silence_others_bucket(self):
        """逃生阀放行的是**本人那一组**；别人那组本来就不阻断，但仍须打印。"""
        self._write_block("看护件-他线在办.md", self.SETTINGS_CC, "读队列。")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            violations = self.m._opener_guard_violations(
                self.root, [f"{self.m.OPENER_EXEMPT_MARK}理由"],
                self._lock("看护件-他线在办.md"), {})
        self.assertEqual(violations, [])
        self.assertIn("看护件-他线在办.md", out.getvalue())

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


# ============================================================
# 队列 §一 #454（2026-09-06，OP-0906-N，变更包 status-triage-resident-round）
# ============================================================

# 🔴 **下列夹具行的状态列原文，全部来自 2026-09-06 对两份队列真身的实测**
# （design §1.2 精度实测那张表），不是编造的例句——本包 tasks 1.2 的回测
# 阻断项就是"这 8 条逐条比对"，夹具一旦改成编造例句，回测就失去意义。
_REAL_ROW_455 = (
    "| 455 | edit-row 写侧守卫 | CC | 指针 | 产出 | "
    "[S:open][D:机] 停在合并决策点：泳道 `455-apply` 已 pause，"
    "是否 ff 进 master 待 Shao Peishen 拍板，未合入前不归档。 | 触碰区 | 2026-09-05 |"
)
_REAL_ROW_394 = (
    "| 394 | 企微群路由 | CC | 指针 | 产出 | "
    "[S:partial][D:业] O-10 有结论且比原设想强一档，待 Shao Peishen 追认：原设想"
    "「合建一份、按场景字段分流」，实现下来发现分流根本不需要 | 触碰区 | 2026-08-25 |"
)
_REAL_ROW_418 = (
    "| 418 | 齐套分析修复 | CC | 指针 | 产出 | "
    "[S:open][D:业] 代码已修、根因已用真实数据坐实；余下部署与全量重跑留步待批"
    "（2026-08-26 CC OP-0826-K，commit 已合入 master） | 触碰区 | 2026-08-26 |"
)
_REAL_ROW_340 = (
    "| 340 | C05 表核对 | CC | 指针 | 产出 | "
    "[S:partial][D:业] 本行 2026-08-27 OP-0827-E 自身已明确结论「LAN 留步早已闭合，"
    "本轮属扫描器形态1误报」，剩余三项均与 LAN 无关 | 触碰区 | 2026-08-27 |"
)
_REAL_ROW_470 = (
    "| 470 | 判据链 A3 段 | CC | 指针 | 产出 | "
    "[S:open][D:业] 看护批 B-0903_50 泳道 criteria-chain A3 段 —— 上一条留步的 ⑤"
    "「A4 段是否与本包同批批准」已由 Shao Peishen 当日答 G-6 = (a) 批准，"
    "五条定夺项全部依赖解除 | 触碰区 | 2026-09-03 |"
)
_REAL_ROW_462 = (
    "| 462 | 规划倒逼开工扫描器 | CC | 指针 | 产出 | "
    "[S:open][D:机] #454 命中的是它并入审核里那句「#422 现卡在待 Shao Peishen "
    "人工安装」）。同族＝ #460 日核假阳性——都是判据只看字面、不看这句话在说谁 "
    "| 触碰区 | 2026-09-02 |"
)


class TriageCandidateTierUnitTests(unittest.TestCase):
    """队列 §一 #454 / design D2：强弱两档分档与否定词表。

    🔴 **本类就是 tasks 1.2 那条回测阻断项本身**：2026-09-06 实测 8 条候选里
    只有 3 条是真的（3/8 ＝ 37.5%），5 条假阳性分两个亚型——亚型 A「不看这句话
    在说谁」、亚型 B「不看时态」。判据不能把这 5 条原样推进企微群（§四 #73 已
    实测「采购内部工作群累计收到 58 条机制告警，其中一条正文是一段 Python
    traceback」），故必须有降档；而降档一旦写宽，真阳性会被一并吞掉——**两个
    方向都要被守住，这也是本类分成"降档"与"保档"两组用例的原因。**
    """

    def setUp(self):
        self.module = _load_module()

    def _tiers(self, *rows: str) -> dict[str, dict]:
        candidates, drift = self.module._collect_triage_candidates(_reclass_section(*rows))
        self.assertEqual(drift, [], "判据漂移：本函数与权威判定走出的行集不一致")
        return {c["row_id"]: c for c in candidates}

    def test_回测阻断项_亚型B四条全部降弱档(self):
        """亚型 B「不看时态」：命中的全是「那个留步**已经**闭合／解除／被批准」
        这类否定或完成时的句子。四条真实行（`#340`／`#470`／`#471`／`#472`，
        后三条同源同文）须全部降至弱档。**达不到即词表不合格、不得 apply。**"""
        got = self._tiers(_REAL_ROW_340, _REAL_ROW_470)
        for row_id in ("340", "470"):
            self.assertEqual(got[row_id]["tier"], "weak", f"#{row_id} 应降弱档：{got[row_id]}")
            self.assertTrue(got[row_id]["downgrade_reasons"], f"#{row_id} 须写明降档因")
        self.assertIn("已闭合", got["340"]["downgrade_reasons"])
        self.assertIn("已由 Shao Peishen", got["470"]["downgrade_reasons"])

    def test_回测阻断项_三条真阳性全部保持强档(self):
        """`#455`／`#394`／`#418` 是逐条读原文核对过的真阳性——否定词表写宽时
        它们会被误降，本用例是那个方向的守卫。"""
        got = self._tiers(_REAL_ROW_455, _REAL_ROW_394, _REAL_ROW_418)
        for row_id in ("455", "394", "418"):
            self.assertEqual(got[row_id]["tier"], "strong", f"#{row_id} 应保持强档：{got[row_id]}")
            self.assertEqual(got[row_id]["downgrade_reasons"], [])

    def test_亚型A本包不试图机器解决_但仍被如实登记为候选(self):
        """亚型 A「不看这句话在说谁」（`#462`：命中的是本行引用**别人**阻塞
        状态的说明文字）——判断主语需句法级理解，字符串判据做不到，design D2
        已如实登记为残留边界。本用例只钉住"它仍会作为候选被产出、且命中片段
        被原样附上"，**不断言它被正确判成假阳性**：那是本包没有解决的问题，
        用例不该假装它解决了。"""
        got = self._tiers(_REAL_ROW_462)
        self.assertIn("462", got)
        self.assertIn("#422", got["462"]["excerpt"], "命中片段须原样附上，读者据此看出这是引文")

    def test_降档因逐条可见_不只给一个布尔(self):
        """"因为哪个词被降的"必须随告警一起可见——否则词表写宽时无从复盘。"""
        got = self._tiers(_REAL_ROW_340)
        self.assertEqual(sorted(got["340"]["downgrade_reasons"]), ["已闭合", "误报"])

    def test_blocked_行降弱档_已自陈受阻无处再改判(self):
        """design 已知边界 2：`blocked` 行确实在等他，但已自陈受阻、改判无处
        可改 ⇒ 不进强档。（分诊器本身只扫 open/partial，本断言是双保险。）"""
        row = (
            "| 900 | 某行 | CC | 指针 | 产出 | "
            "[S:blocked][D:机] 硬阻塞于待 Shao Peishen 给窗口 | 触碰区 | 2026-09-01 |"
        )
        self.assertEqual(self._tiers(row), {})

    def test_否定词表每条都附真实来源行号(self):
        """同 `STALE_STATUS_PHRASES` 上方那条纪律：可增不可删、新增须附真实
        来源。空来源＝编造的例句，是这类词表失效的第一步。"""
        for phrase, source in self.module.TRIAGE_NEGATION_PHRASES:
            self.assertTrue(phrase.strip(), "措辞不得为空")
            self.assertRegex(source, r"^#\d+$", f"「{phrase}」缺真实来源行号")


class TriageExcerptBacktickGuardTests(unittest.TestCase):
    """design D6：命中片段的反引号奇偶守卫。

    🔴 **成因是一次真实事故**：分诊器现行的 `idx-10 / idx+len+20` 窄窗在
    `#337`／`#422` 两行恰好把一个反引号截在中间 ⇒ 整格反引号变奇数 ⇒ 未闭合
    跨度吞掉行尾列分隔符，两行由 8 列塌为 7 列；而 `edit-row` 对**已塌列的行**
    拒绝一切操作 ⇒ **行一旦被写坏，唯一能修它的入口就把自己关上了。**
    告警正文本身不写回文件，但它会被人复制粘贴回队列行——故守在输出侧。
    """

    def setUp(self):
        self.module = _load_module()

    def test_偶数反引号原样保留(self):
        self.assertEqual(self.module._balance_backticks("跑 `git status` 看"), "跑 `git status` 看")

    def test_奇数反引号整体去掉_宁可丢格式不可丢列(self):
        self.assertEqual(self.module._balance_backticks("截断在 `git sta"), "截断在 git sta")

    def test_候选片段永不含奇数反引号(self):
        row = (
            "| 901 | 某行 | CC | 指针 | 产出 | "
            "[S:open][D:机] " + "填" * 55 + "`未闭合跨度 待 Shao Peishen 拍板" + "尾" * 80
            + " | 触碰区 | 2026-09-01 |"
        )
        candidates, _drift = self.module._collect_triage_candidates(_reclass_section(row))
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["excerpt"].count("`") % 2, 0, candidates[0]["excerpt"])

    def test_上下文宽度足够读者判断主语(self):
        """窗口宽度不是装饰——亚型 A 的唯一兜底手段就是"把片段附够长，让读者
        一眼看出这是不是一句引文"。窗口太窄，这条兜底就失效。"""
        left = "前" * 80
        row = (
            "| 902 | 某行 | CC | 指针 | 产出 | "
            f"[S:open][D:机] {left}待拍板{'后' * 80} | 触碰区 | 2026-09-01 |"
        )
        candidates, _drift = self.module._collect_triage_candidates(_reclass_section(row))
        excerpt = candidates[0]["excerpt"]
        self.assertGreaterEqual(excerpt.count("前"), self.module.TRIAGE_EXCERPT_CONTEXT_CHARS)
        self.assertGreaterEqual(excerpt.count("后"), self.module.TRIAGE_EXCERPT_CONTEXT_CHARS)


class AwaitingDecisionScanTests(unittest.TestCase):
    """⑵ 的扫描面：**刻意与分诊器不同**（design 已知边界 2）。

    2026-09-06 实测 16 条「自陈在等他一次动作」的行里 **13 条状态已是
    `blocked`**——它们确实在等他，只是无处可改判。沿用分诊器的 open/partial
    限制会让 ⑵ 一开始就漏掉 81%。**两半扫描面不同不是疏漏，是设计。**
    """

    def setUp(self):
        self.module = _load_module()

    def _ids(self, *rows: str) -> list[str]:
        return [r["row_id"] for r in
                self.module._collect_awaiting_decision_rows(_reclass_section(*rows))]

    def test_覆盖blocked行_分诊器看不到的那13条(self):
        row = (
            "| 337 | 某行 | CC | 指针 | 产出 | "
            "[S:blocked][D:机] 判据类，待 Shao Peishen 裁 | 触碰区 | 2026-08-20 |"
        )
        self.assertEqual(self._ids(row), ["337"])

    def test_done行不进扫描面(self):
        row = (
            "| 338 | 某行 | CC | 指针 | 产出 | "
            "[S:done][D:机] 曾待 Shao Peishen 拍板，已答 | 触碰区 | 2026-08-20 |"
        )
        self.assertEqual(self._ids(row), [])

    def test_timed行不进扫描面(self):
        row = (
            "| 339 | 常驻巡检 | CC | 指针 | 产出 | "
            "[S:timed=周][D:机] 本行常驻不销，需人在场 | 触碰区 | 2026-08-20 |"
        )
        self.assertEqual(self._ids(row), [])

    def test_open与partial同样收(self):
        self.assertEqual(sorted(self._ids(_REAL_ROW_455, _REAL_ROW_394)), ["394", "455"])


class TriageCandidatesCliTests(unittest.TestCase):
    """`triage-candidates` 子命令：**纯只读**（tasks 2.3）。

    三条断言合起来是同一句话：这个出口**不占锁、不写盘、不改一个字节**。
    它每小时被 sweep 调一次、读的是两份队列真身——任何一次写盘都直接落在
    `#326`／`#322` 那一族事故上。
    """

    def setUp(self):
        self.module = _load_module()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.queue_rel = "queue.md"
        (self.root / self.queue_rel).write_text(
            "## 一、任务看板\n\n" + _reclass_section(_REAL_ROW_455, _REAL_ROW_340)
            + "\n## 四、决策台账\n\n| # | 事项 | 等谁 | 截止 |\n|---|---|---|---|\n"
            "| 1 | 复核 #455 | Shao Peishen | 2026-09-10 |\n",
            encoding="utf-8")
        self._orig_root = self.module.REPO_ROOT
        self.module.REPO_ROOT = self.root

    def tearDown(self):
        self.module.REPO_ROOT = self._orig_root
        self._tmp.cleanup()

    def _run(self, as_json: bool):
        ns = argparse.Namespace(queue=self.queue_rel, json=as_json)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self.module.cmd_triage_candidates(ns)
        self.assertEqual(rc, 0)
        return buf.getvalue()

    def test_json出口含分档与自陈行(self):
        payload = json.loads(self._run(as_json=True))
        by_id = {c["row_id"]: c for c in payload["candidates"]}
        self.assertEqual(by_id["455"]["tier"], "strong")
        self.assertEqual(by_id["340"]["tier"], "weak")
        self.assertEqual(payload["has_section_four"], True)
        self.assertEqual([r["row_id"] for r in payload["awaiting_rows"]], ["455"])
        self.assertEqual(payload["row_ids"], ["455", "340"])
        self.assertEqual(payload["criteria_drift"], [])

    def test_不acquire任何锁_运行后无锁文件(self):
        self._run(as_json=True)
        leftovers = [p.name for p in self.root.iterdir() if ".editlock" in p.name]
        self.assertEqual(leftovers, [], f"只读出口不得留下锁文件：{leftovers}")

    def test_运行后目标文件逐字节不变(self):
        before = (self.root / self.queue_rel).read_bytes()
        self._run(as_json=True)
        self._run(as_json=False)
        self.assertEqual((self.root / self.queue_rel).read_bytes(), before)

    def test_目标文件缺失时不崩_如实报queue_exists为假(self):
        ns = argparse.Namespace(queue="不存在的队列.md", json=True)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(self.module.cmd_triage_candidates(ns), 0)
        payload = json.loads(buf.getvalue())
        self.assertFalse(payload["queue_exists"])
        self.assertEqual(payload["candidates"], [])

    def test_人读出口标出强弱档(self):
        out = self._run(as_json=False)
        self.assertIn("强档 1／弱档 1", out)
        self.assertIn("降档：已闭合", out)



class FollowupSerialGateIdentityTests(unittest.TestCase):
    """变更包 `followup-serial-gate-hardening` D7：串行闸的**双向**回归用例。

    🔴 **取材于 2026-09-07 对生产 README 真身的实测行，不构造理想样本**——
    `#124` 的整个成因就是「误放不会有人看见」，用构造样本写这两条测试等于
    放弃了唯一一次把真实误放钉进断言的机会。

    白盒方式同 `FollowupReadmeStructuralValidationTests`：monkeypatch
    REPO_ROOT/FOLLOWUP_README_TARGET 指向本用例专属临时目录。
    """

    HEADER = (
        "| 编号 | 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |\n"
        "|--------|------|--------|---------|---------|---------|\n"
    )
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

    def _write_readme(self, rows=""):
        text = (
            "## 现有跟进信清单\n\n" + self.HEADER + rows
            + "\n## 补件登记（不占编号、不占串行闸）\n\n" + self.SUPPLEMENT_HEADER
        )
        self.target_path.write_text(text, encoding="utf-8")

    def _acquire(self, who="A"):
        ns = argparse.Namespace(
            file=self.module.FOLLOWUP_README_TARGET, who=who, note="",
            reserve=None, section=None, reserve_multi=None, domain=None,
        )
        return self.module.cmd_acquire(ns)

    def _release(self, who="A"):
        ns = argparse.Namespace(
            file=self.module.FOLLOWUP_README_TARGET, who=who,
            mechanism_wip_cap=self.module.MECHANISM_WIP_CAP_DEFAULT,
            force_mechanism_wip=False,
        )
        return self.module.cmd_release(ns)

    def _violations(self, prior_rows, current_rows):
        """直接跑权威校验函数——比整条 acquire/release 更能指名违规文案。"""
        def _wrap(rows):
            return (
                "## 现有跟进信清单\n\n" + self.HEADER + rows
                + "\n## 补件登记（不占编号、不占串行闸）\n\n" + self.SUPPLEMENT_HEADER
            )
        return self.module._validate_followup_readme_release(
            _wrap(current_rows), _wrap(prior_rows)
        )

    # ---- T1：🔴 误放（本包核心，取材 `质量部#7` 实况） -------------------

    def test_T1_误放_新增行多写后括号注记不得绕过串行闸(self):
        """表内已有 `质量部 · 陈忱`（`✅ 已推送`，在途）；新增一行收信人写
        `质量部 · 陈忱（可分担朱映桦）`。

        🔴 改造前这条必然失败（整格逐字比对判成两个人 ⇒ 现状**静默放行**）
        ——这条测试的价值就在这里。"""
        prior = (
            "| 质量部#7 | 2026-08-13 | 质量部 · 陈忱 | 前一封事项 | 不用回 | "
            "✅ 已推送 2026-08-13 06:00 UTC |\n"
        )
        new_row = (
            "| 质量部#8 | 2026-08-20 | 质量部 · 陈忱（可分担朱映桦） | 新事项 | "
            "不卡时间 | ⏳ 待你审 |\n"
        )
        violations = self._violations(prior, prior + new_row)
        self.assertTrue(violations, "多写一个后括号注记不得让串行原则被静默绕过")
        self.assertTrue(
            any("质量部#7" in v for v in violations),
            f"拒绝文案 MUST 指名前一封的编号，实得：{violations}",
        )

    # ---- T2：⚠ 误拦（取材 `质量部#10` 实况） ----------------------------

    def test_T2_误拦_前一封已闭环时少写注记不需要任何豁免(self):
        """表内已有 `质量部 · 陈忱（可请朱映桦先初标）`（`📥 已回件并回灌`，
        闭环）；新增一行写 `质量部 · 陈忱` ⇒ MUST 放行，且**不需要任何豁免
        标记**（`质量部#10` 那条名不副实的豁免正是这么来的）。"""
        prior = (
            "| 质量部#9 | 2026-08-25 | 质量部 · 陈忱（可请朱映桦先初标） | 前一封 | "
            "不卡时间 | 📥 已回件并回灌（2026-08-25，拆件巡逻第二班） |\n"
        )
        new_row = (
            "| 质量部#10 | 2026-08-26 | 质量部 · 陈忱 | 新事项 | 不卡时间 | ⏳ 待你审 |\n"
        )
        self.assertEqual(self._violations(prior, prior + new_row), [])

    # ---- T3：反向镜像（少写注记，取材 `采购部#21` 实况） -----------------

    def test_T3_误放镜像_新增行少写后括号注记同样不得绕过(self):
        prior = (
            "| 采购部#20 | 2026-08-31 | 采购部 · 姚祖怡（采购域 AI 专员） | 前一封 | "
            "不卡时间 | ✅ 已推送 2026-08-31 02:00 UTC |\n"
        )
        new_row = (
            "| 采购部#21 | 2026-09-05 | 采购部 · 姚祖怡 | 新事项 | 不卡时间 | ⏳ 待你审 |\n"
        )
        violations = self._violations(prior, prior + new_row)
        self.assertTrue(violations, "多写与少写必须同判（T1 的镜像）")
        self.assertTrue(any("采购部#20" in v for v in violations), violations)

    # ---- T4／T5：身份解析失败与跨部门同名 -------------------------------

    def test_T4_收信人解析失败不判为同一人且出声(self):
        """两行收信人列均无 `·` ⇒ MUST NOT 判为同一人；MUST 出声（记 violation
        并指名该行）。🔴 两个解析不出来的收信人不是同一个人。"""
        prior = (
            "| 销售部#1 | 2026-08-01 | 销售部 | 前一封 | 不急 | ✅ 已推送 2026-08-01 |\n"
        )
        new_row = "| 销售部#2 | 2026-08-05 | 销售部 | 新事项 | 不急 | ⏳ 待你审 |\n"
        violations = self._violations(prior, prior + new_row)
        self.assertTrue(
            any("解析" in v for v in violations),
            f"解析失败必须出声、不得静默放行，实得：{violations}",
        )

    def test_T5_跨部门同名不合并(self):
        """`质量部 · 张三` 与 `采购部 · 张三` 是两个人（D1 二元组）——把它们
        判成同一人是**错误的严**：制造误拦，而误拦会把合规的信永久染成豁免行。"""
        prior = (
            "| 质量部#20 | 2026-08-01 | 质量部 · 张三 | 前一封 | 不急 | ✅ 已推送 2026-08-01 |\n"
        )
        new_row = "| 采购部#30 | 2026-08-05 | 采购部 · 张三 | 新事项 | 不急 | ⏳ 待你审 |\n"
        self.assertEqual(self._violations(prior, prior + new_row), [])

    # ---- T6：两端同判（append 前置 vs release 后置） ---------------------

    def test_T6_append前置与release后置对同一形态给出同一结论(self):
        """`工具-跟进信README登记.py` 的 append 前置（走 `gate_query.build_report`）
        与编辑锁 release 后置 MUST 给出同一结论。🔴 改造前二者相反：append 侧
        只取姓名 ⇒ 判锁；release 侧整格逐字 ⇒ 判开。"""
        gate_query = _load_gate_query()
        rows = (
            "| 质量部#7 | 2026-08-13 | 质量部 · 陈忱 | 前一封事项 | 不用回 | "
            "✅ 已推送 2026-08-13 06:00 UTC |\n"
        )
        new_row = (
            "| 质量部#8 | 2026-08-20 | 质量部 · 陈忱（可分担朱映桦） | 新事项 | "
            "不卡时间 | ⏳ 待你审 |\n"
        )
        readme_text = (
            "## 现有跟进信清单\n\n" + self.HEADER + rows
            + "\n## 补件登记（不占编号、不占串行闸）\n\n" + self.SUPPLEMENT_HEADER
        )
        append_blocks = not gate_query.build_report("陈忱", readme_text).gate_open
        release_blocks = bool(self._violations(rows, rows + new_row))
        self.assertEqual(
            append_blocks, release_blocks,
            f"append 前置判 {append_blocks}、release 后置判 {release_blocks}——两端必须同判",
        )
        self.assertTrue(append_blocks, "前一封在途，两端都应判锁")

    # ---- T7／T8／T9：`❌ 已作废` 防滥用（design D4） ---------------------

    def test_T7_已发出的信改作废且理由为开闸措辞时被拒并指名判据(self):
        prior = (
            "| 采购部#40 | 2026-08-01 | 采购部 · 姚祖怡 | 事项 | 不急 | "
            "✅ 已推送 2026-08-01 06:00 UTC |\n"
        )
        voided = (
            "| 采购部#40 | 2026-08-01 | 采购部 · 姚祖怡 | 事项 | 不急 | "
            "❌ 已作废（为了开闸，先把这封作废） |\n"
        )
        violations = self._violations(prior, voided)
        self.assertTrue(violations)
        self.assertTrue(any("R2" in v for v in violations), violations)

    def test_T8_已发出的信改作废且理由过短无凭据时被拒(self):
        prior = (
            "| 采购部#40 | 2026-08-01 | 采购部 · 姚祖怡 | 事项 | 不急 | "
            "✅ 已推送 2026-08-01 06:00 UTC |\n"
        )
        voided = (
            "| 采购部#40 | 2026-08-01 | 采购部 · 姚祖怡 | 事项 | 不急 | "
            "❌ 已作废（不需要了） |\n"
        )
        violations = self._violations(prior, voided)
        self.assertTrue(violations)
        self.assertTrue(any("R1" in v for v in violations), violations)
        self.assertTrue(any("R3" in v for v in violations), violations)

    def test_T9_正例_归档件里那行真实作废理由不被拦死(self):
        """🔴 取归档件里那行**真实**作废的理由文本——防止判据把合法作废拦死。"""
        prior = (
            "| 销售部（未发，不编号） | 2026-07-28 | 销售部 · 泓钦 | 事项 | 首周 | "
            "⏳ 待你审 |\n"
        )
        voided = (
            "| 销售部（未发，不编号） | 2026-07-28 | 销售部 · 泓钦 | 事项 | 首周 | "
            "❌ 已作废 · 9 月重写（2026-08-04，队列 #137，Shao Peishen 选 (a) 线下当面说）"
            "——信中三件事已全部随销售域推迟失效 |\n"
        )
        self.assertEqual(self._violations(prior, voided), [])

    def test_T9b_作废豁免逃生阀放行_但空理由拒绝(self):
        prior = (
            "| 采购部#40 | 2026-08-01 | 采购部 · 姚祖怡 | 事项 | 不急 | "
            "✅ 已推送 2026-08-01 06:00 UTC |\n"
        )
        waived = (
            "| 采购部#40 | 2026-08-01 | 采购部 · 姚祖怡 | 事项｜作废豁免：线下已当面确认，"
            "口径另立队列行承接 | 不急 | ❌ 已作废（不需要了） |\n"
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(self._violations(prior, waived), [])
        self.assertIn("作废豁免", buf.getvalue())

        empty_waiver = (
            "| 采购部#40 | 2026-08-01 | 采购部 · 姚祖怡 | 事项｜作废豁免： | 不急 | "
            "❌ 已作废（不需要了） |\n"
        )
        self.assertTrue(self._violations(prior, empty_waiver))

    # ---- D5(a)：行身份改用编号列主键 ------------------------------------

    def test_D5a_改主要事项列不再被判成新增行(self):
        """行长外置压缩「主要事项」列 ⇒ 改造前身份改变 ⇒ 被误判成新增行 ⇒
        撞串行闸 ⇒ 工具自动写豁免绕过（现网 5 行、单调增长）。改用编号列
        主键后，这一整类误报一次消掉。"""
        prior = (
            "| 采购部#12 | 2026-08-09 | 采购部 · 姚祖怡 | 事项一 | 不急 | "
            "✅ 已推送 2026-08-09 06:00 UTC |\n"
            "| 采购部#13 | 2026-08-12 | 采购部 · 姚祖怡 | 很长很长的原始摘要 | 不急 | "
            "📥 已回件并回灌 2026-08-14 |\n"
        )
        # 🔴 被压缩的是**第二行**：它前面还有一封 `采购部#12` 在途——改造前
        # 这一改会让 `采购部#13` 被判成新增行、撞上 `#12` 未闭环这条闸，于是
        # 工具自动写一条豁免绕过（现网 5 行就是这么来的）。
        compressed = prior.replace("很长很长的原始摘要", "压缩后摘要（行日志：#13）")
        self.assertEqual(self._violations(prior, compressed), [])

    def test_D5a_编号行状态被改成终态仍被两态语义拦住(self):
        """🔴 D5(a) 的代价缓解：改主键后「身份不在快照里」不再能拦住
        「把一个已发出行的状态直接改成 `🆕 待发`」，故两态语义检查改为
        **同时**看身份与状态迁移。"""
        prior = (
            "| 采购部#12 | 2026-08-09 | 采购部 · 姚祖怡 | 事项 | 不急 | "
            "✅ 已推送 2026-08-09 06:00 UTC |\n"
        )
        tampered = prior.replace("✅ 已推送 2026-08-09 06:00 UTC", "🆕 待发")
        violations = self._violations(prior, tampered)
        self.assertTrue(violations, "已发出行被直接改写成终态，MUST 拒绝")

    def test_D5a_无编号行回落到全单元格身份并出声(self):
        """无 `<部门>#<数字>` 的行（实测：归档件 `销售部（未发，不编号）`）
        回落到既有「全单元格」身份，并**出声**说明走的是回落路径。"""
        prior = ""
        new_row = (
            "| 销售部（未发，不编号） | 2026-08-01 | 销售部 · 泓钦 | 事项 | 首周 | "
            "🆕 待发 |\n"
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            violations = self._violations(prior, new_row)
        self.assertTrue(violations, "新增行直接写终态仍应被两态语义拦住")
        self.assertIn("回落", buf.getvalue())

    def test_串行豁免收窄_有标记没理由不再放行(self):
        """design D5「两案共同要求 2」：`串行豁免：` 收窄为「标记后 MUST 跟
        非空理由」。不做语义判断，只拦「有标记没理由」这一种。"""
        prior = (
            "| 采购部#11 | 2026-08-05 | 采购部 · 姚祖怡 | 事项 | 不急 | 🆕 待发 |\n"
        )
        empty = prior + (
            "| 采购部#12 | 2026-08-09 | 采购部 · 姚祖怡 | 新事项，串行豁免： | 不急 | "
            "⏳ 待你审 |\n"
        )
        self.assertTrue(self._violations(prior, empty))
        filled = prior + (
            "| 采购部#12 | 2026-08-09 | 采购部 · 姚祖怡 | 新事项，串行豁免：业务方要求两条并行跟进 | "
            "不急 | ⏳ 待你审 |\n"
        )
        self.assertEqual(self._violations(prior, filled), [])




class FollowupSerialGateIdentityFallbackTests(FollowupSerialGateIdentityTests):
    """design 1.5：**同一份用例**在「无平台包」的隔离环境上再跑一遍。

    🔴 **为什么必须双跑而不是各写一份断言**：编辑锁在无平台包时会回落到
    本文件内的 `_FollowupGateFallback`。回落分支若与权威实现漂移，漂移
    **不会有任何报错**——闸会按一份没人在看的判据继续工作，而那正是 `#482`
    在修的那一族毛病（四处各写一份、四份互不一致、零告警）。

    实现手法 ＝ 继承上面那个类，`setUp` 里把 `module.followup_gate` 置 None。
    编辑锁侧的取用口 `_gate()` 写成函数而不是模块级常量，正是为了让这一步
    成立。
    """

    def setUp(self):
        super().setUp()
        self.module.followup_gate = None
        self.assertIsNone(self.module.followup_gate)

    def test_T6_append前置与release后置对同一形态给出同一结论(self):
        """跳过：T6 要跑 `工具-跟进闸查询.py`，那一侧本就**硬依赖**平台包
        （顶部是无兜底的 `from zhuopin_platform...import followup_gate`），
        隔离环境根本到不了这条路径。如实说明，不静默跳过。"""
        self.skipTest("闸查询侧硬依赖平台包，无回落分支可测——非遗漏，见 docstring")

    def test_回落实现与权威实现对同一批收信人写法给出同一身份(self):
        """逐条比对两份实现的输出，把「漂移」这件事本身钉进断言。"""
        import importlib

        sys.path.insert(0, str(SCRIPT.parent.parent / "5-平台底座" / "zhuopin_platform"))
        authority = importlib.import_module("zhuopin_platform.shared_tools.followup_gate")
        fallback = self.module._FOLLOWUP_GATE_FALLBACK
        samples = [
            "质量部 · 陈忱",
            "质量部 · 陈忱（可分担朱映桦）",
            "采购部 · 姚祖怡（+团队）",
            "采购部 · 姚祖怡（转汤易水第④项）",
            "IT部 · 陈承（抄唐燕萍）",
            "财务部 · 唐燕萍（财务总监 / 财务域 AI 专员）",
            "**质量部 · 陈忱**",
            "销售部",
            "· 陈忱",
            "质量部 · ",
            "",
        ]
        for cell in samples:
            with self.subTest(cell=cell):
                self.assertEqual(
                    fallback.recipient_identity(cell),
                    authority.recipient_identity(cell),
                )
        numbers = ["采购部#17", "IT部#7（待发，暂不占号）", "销售部（未发，不编号）", ""]
        for cell in numbers:
            with self.subTest(cell=cell):
                self.assertEqual(
                    fallback.letter_row_identity(cell),
                    authority.letter_row_identity(cell),
                )
        voids = [
            "❌ 已作废（为了开闸，先把这封作废）",
            "❌ 已作废（不需要了）",
            "❌ 已作废 · 9 月重写（2026-08-04，队列 #137，Shao Peishen 选 (a)）",
        ]
        for cell in voids:
            for risk in ("low", "high"):
                with self.subTest(cell=cell, risk=risk):
                    self.assertEqual(
                        bool(fallback.validate_void_reason(cell, risk)),
                        bool(authority.validate_void_reason(cell, risk)),
                    )


class AppendRowHighWaterMarkTests(unittest.TestCase):
    """队列 §一 #505（openspec 变更包 `editlock-append-row-highwater-writeback`）：
    `append-row --number N` 写入新编号后同步推进编号高水位线。

    **病灶**：该计数器此前只有 `_reserve_ids` 一个写入方，`append-row --number`
    同样让新编号落盘却不推线、且返回 0 ⇒ 线滞后于文件，**下一个人**的
    `--reserve` 才被整体拒绝（2026-09-07／2026-09-08 两天四次实证）。

    白盒方式：monkeypatch REPO_ROOT/DEFAULT_TARGET/QUEUE_MECHANISM_PATH_REL/
    QUEUE_BUSINESS_PATH_REL/QUEUE_LOCK_ANCHOR 指向本用例专属临时目录，与既有
    `DualFileRoutingTests` 同一惯例——本项只在「队列系统目标」下生效（D4），
    子进程 + 临时 `--file` 那条黑盒路子恰好落在不生效的那一侧，测不到。
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

    # ---- 夹具 ----

    def _write(self, path: Path, hwm_one=300, hwm_four=40, *, hwm_line=None,
               section_one_rows="", section_four_rows=""):
        """`hwm_line=None` ⇒ 写一条正常声明行；传字符串则原样使用（供缺失／
        格式漂移两个反例用，传 `""` 即整行不存在）。"""
        head = (
            f"> **编号高水位线：§一 #{hwm_one} ｜ §四 #{hwm_four}**（说明）\n\n"
            if hwm_line is None else hwm_line
        )
        path.write_text(
            head
            + "## 一、任务看板\n\n" + self.SECTION_ONE_HEADER + section_one_rows
            + "\n## 二、待 commit 批次（CC 取活销行）\n\n" + self.SECTION_TWO_HEADER
            + "\n## 四、需 Shao Peishen 定夺\n\n" + self.SECTION_FOUR_HEADER
            + section_four_rows,
            encoding="utf-8",
        )

    def _hwm(self, section: str, path: Path | None = None) -> int:
        text = (path or self.mech_path).read_text(encoding="utf-8")
        match = self.module.SECTION_NUMBER_PATTERNS[section].search(text)
        self.assertIsNotNone(match, f"目标文件里读不到 §{section} 高水位线")
        return int(match.group(2))

    def _four_ns(self, number: str, *, file=None, task="定夺事项"):
        return argparse.Namespace(
            file=file if file is not None else self.module.DEFAULT_TARGET,
            section="四", number=number,
            cell=[task, "Shao Peishen", "2026-09-11"],
            domain=None,
        )

    def _one_ns(self, number: str, *, domain=None, file=None, task="新任务"):
        return argparse.Namespace(
            file=file if file is not None else self.module.DEFAULT_TARGET,
            section="一", number=number,
            cell=[task, "CC", "无", "无", "[S:open][D:机] 待领", "无", "2026-09-08"],
            domain=domain,
        )

    # ---- 组⑴：写入后线跟上（派单件明写的第一组） ----

    def test_append_row_number_advances_high_water_mark(self):
        self._write(self.mech_path, hwm_four=173)
        self._write(self.biz_path, hwm_four=173)

        self.assertEqual(self.module.cmd_append_row(self._four_ns("174")), 0)

        self.assertEqual(self._hwm("四"), 174)
        self.assertIn("定夺事项", self.mech_path.read_text(encoding="utf-8"))

    # ---- 组⑵：紧接的预留取到不撞的号（派单件明写的第二组） ----

    def test_reserve_right_after_append_row_gets_next_free_number(self):
        """本用例即 2026-09-08 那次事故的受控复现：修前 `--reserve` 会算出
        174、撞上刚落盘的可见行、整体拒绝并回滚 ⇒ 该分区对全线取不到号。"""
        self._write(self.mech_path, hwm_four=173)
        self._write(self.biz_path, hwm_four=173)
        self.assertEqual(self.module.cmd_append_row(self._four_ns("174")), 0)

        reserved = self.module._reserve_ids("queue-mech.md", "四", 1)

        self.assertEqual(reserved, [175])
        self.assertEqual(self._hwm("四"), 175)

    # ---- D3：单调，不回退、幂等 ----

    def test_number_below_high_water_mark_does_not_regress_it(self):
        """补写一个此前预留未用的空洞号（协议〇.8 明文允许）——线不回退、
        命令照常成功。严格赋值会把线往回拉，等于亲手制造一次滞后。"""
        self._write(self.mech_path, hwm_one=507)
        self._write(self.biz_path, hwm_one=507)

        self.assertEqual(self.module.cmd_append_row(self._one_ns("505")), 0)

        self.assertEqual(self._hwm("一"), 507)
        self.assertIn("新任务", self.mech_path.read_text(encoding="utf-8"))

    def test_repeated_append_of_same_number_does_not_drift(self):
        self._write(self.mech_path, hwm_four=173)
        self._write(self.biz_path, hwm_four=173)

        self.assertEqual(self.module.cmd_append_row(self._four_ns("174")), 0)
        after_first = self._hwm("四")
        self.assertEqual(self.module.cmd_append_row(self._four_ns("174")), 0)

        self.assertEqual(self._hwm("四"), after_first)

    # ---- D2：推线失败 ⇒ 拒绝写行，零残留 ----

    def test_missing_high_water_mark_line_rejects_and_writes_nothing(self):
        self._write(self.mech_path, hwm_line="")
        self._write(self.biz_path, hwm_line="")
        before = self.mech_path.read_text(encoding="utf-8")

        rc = self.module.cmd_append_row(self._four_ns("174"))

        self.assertEqual(rc, 1)
        # 🔴 不只看返回码：表格行必须**一个字都没写进去**——先推线后写行的
        # 全部意义就在这里（失败只留一个空洞号，不留「行已写、线未推」）。
        self.assertEqual(self.mech_path.read_text(encoding="utf-8"), before)

    def test_malformed_section_number_rejects_and_writes_nothing(self):
        drifted = "> **编号高水位线：§一 #300 ｜ §四 格式已变**（说明）\n\n"
        self._write(self.mech_path, hwm_line=drifted)
        self._write(self.biz_path, hwm_line=drifted)
        before = self.mech_path.read_text(encoding="utf-8")

        rc = self.module.cmd_append_row(self._four_ns("174"))

        self.assertEqual(rc, 1)
        self.assertEqual(self.mech_path.read_text(encoding="utf-8"), before)

    # ---- D4：非队列系统目标不适用 ----

    def test_explicit_file_override_never_touches_high_water_mark(self):
        """显式 `--file` 覆盖到队列系统之外的文件——即便那份文件**恰好也有**
        一条高水位线声明行，本项也不动它、更不因此报错（口径与 `acquire` 侧
        既有做法同源）。"""
        other = self.repo_root / "other.md"
        self._write(other, hwm_one=300)

        rc = self.module.cmd_append_row(self._one_ns("301", file="other.md", task="旁路任务"))

        self.assertEqual(rc, 0)
        text = other.read_text(encoding="utf-8")
        self.assertIn("旁路任务", text)
        self.assertEqual(self._hwm("一", path=other), 300)

    # ---- 三个量各归各位：写入目标／锁锚点／计数器目标 ----

    def test_domain_ye_row_lands_in_business_file_but_hwm_advances_in_mechanism(self):
        self._write(self.mech_path, hwm_one=300)
        # 业务场景文件本身**不含**高水位线声明行——断言本项不会在那边造一条。
        self._write(self.biz_path, hwm_line="")

        rc = self.module.cmd_append_row(self._one_ns("301", domain="业", task="业务任务"))

        self.assertEqual(rc, 0)
        biz_text = self.biz_path.read_text(encoding="utf-8")
        self.assertIn("业务任务", biz_text)
        self.assertNotIn("编号高水位线", biz_text)
        self.assertEqual(self._hwm("一"), 301)
        self.assertNotIn("业务任务", self.mech_path.read_text(encoding="utf-8"))

    def test_section_two_has_no_number_column_and_never_touches_hwm(self):
        self._write(self.mech_path, hwm_one=300, hwm_four=40)
        self._write(self.biz_path, hwm_one=300, hwm_four=40)

        ns = argparse.Namespace(
            file=self.module.DEFAULT_TARGET, section="二", number=None,
            cell=["B-测试批次", "`queue-biz.md`", "说明", "待处理"],
            domain="业",
        )
        self.assertEqual(self.module.cmd_append_row(ns), 0)

        self.assertEqual(self._hwm("一"), 300)
        self.assertEqual(self._hwm("四"), 40)

    # ---- `_reserve_ids` 侧行为不变（抽出共用回写路径后的回归闸） ----

    def test_reserve_still_advances_and_still_fails_loud_on_missing_line(self):
        self._write(self.mech_path, hwm_one=300)
        self.assertEqual(self.module._reserve_ids("queue-mech.md", "一", 2), [301, 302])
        self.assertEqual(self._hwm("一"), 302)

        self._write(self.mech_path, hwm_line="")
        with self.assertRaises(self.module.ReserveFailedError) as ctx:
            self.module._reserve_ids("queue-mech.md", "一", 1)
        self.assertIn("拒绝预留", str(ctx.exception))


# ══════════════════════════════════════════════════════════════════════
# 队列 §一 #513 ＋ #523（2026-09-09，OP-0909-W）——写侧同族三缺陷
#
# 三条合并成一棒改的理由（协议〇.10 并入优先）：全在同一份文件的**写侧**，
# 且共享同一个失效形态——**登记的东西看起来生效、实则没被任何消费方取到**：
#   ⑴ #513 文件清单写裸路径 ⇒ sweep 与 release ⑹ 都只提取反引号内的串 ⇒
#      整批静默不入库；
#   ⑵ #523 §一 状态列缺 `[D:]` ⇒ 可动行不计入 WIP ⇒ 计数算少、该拦的没拦；
#   ⑶ `release --waiver` 括注截断／尾随说明 ⇒ 豁免点名的路径被静默丢掉。
# ══════════════════════════════════════════════════════════════════════


class FileListBarePathGuardTests(unittest.TestCase):
    """⑴ `#513`：§二「文件清单」裸路径写侧守卫（`_file_list_bare_path_
    violations`）。

    白盒：判据不碰文件系统、不调 git（它回答的只是"sweep 能不能看见这些
    串"），故无需 git 夹具。
    """

    def setUp(self):
        self.m = _load_module()

    def _violations(self, file_list: str, status: str = "待处理"):
        return self.m._file_list_bare_path_violations(
            ["B-TEST", file_list, "msg", status]
        )

    # ---- 正向：裸路径必须被拦 ----

    def test_bare_path_rejected(self):
        """#513 的真实形态：`队列行日志/#506.md` 写成裸路径 ⇒ 未被跟踪。"""
        problems = self._violations(
            "1-转型规划/0-全景路线图/队列行日志/#506.md"
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("未用反引号包裹", problems[0])
        self.assertIn("#506.md", problems[0])

    def test_multiple_bare_paths_all_named(self):
        problems = self._violations(
            "0-学习与工具/工具-共享文档编辑锁.py；0-学习与工具/test_工具-共享文档编辑锁.py"
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("工具-共享文档编辑锁.py", problems[0])
        self.assertIn("test_工具-共享文档编辑锁.py", problems[0])
        self.assertIn("2 个", problems[0])

    def test_bare_path_with_parenthetical_annotation_still_caught(self):
        """真实存量写法：路径后紧跟 `（新建）` 一类括注，中间无空白。"""
        self.assertTrue(self._violations(
            "1-转型规划/0-全景路线图/修法建议-2026-09-04.md（新建，只读诊断）"
        ))

    def test_mixed_cell_flags_only_the_unprotected_one(self):
        """半数带反引号这种最危险的形态：带的那半会入库、裸的那半静默掉地上。"""
        problems = self._violations(
            "`0-学习与工具/工具-共享文档编辑锁.py`；0-学习与工具/漏网.py"
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("漏网.py", problems[0])
        self.assertNotIn("工具-共享文档编辑锁.py", problems[0])

    # ---- 反向：不得误报 ----

    def test_backticked_paths_pass(self):
        self.assertEqual(self._violations(
            "`1-转型规划/0-全景路线图/队列行日志/#506.md`"
        ), [])

    def test_prose_without_any_path_passes(self):
        """存量真实行 `B-0903_80`：本批只改队列文件，没有独立产出件。"""
        self.assertEqual(self._violations(
            "（本批只改队列文件，由锁流程自带；无独立产出件）"
        ), [])

    def test_directory_prefix_in_prose_not_flagged(self):
        """🔴 判据刻意**不认**以 `/` 收尾的目录前缀（对照 `_fragment_is_
        path_like` 的另一支）：`reports/` 这类串即便写进反引号，sweep 的
        后缀匹配也永远匹配不到任何脏文件（脏路径是文件、不以 `/` 收尾），
        拦它不改变任何结果、纯属噪声；而正文里"落 reports/ 目录"这种叙述
        极常见（存量 `B-0902_47` 行即如此），按含 `/` 收尾判会当场误伤。"""
        self.assertEqual(self._violations(
            "🔴 本批零可落库文件，如实登记：两个产出均落 reports/ 目录，"
            "而 .gitignore:35 的 **/reports/ 规则把该目录整体排除"
        ), [])

    def test_preregistered_row_is_exempt(self):
        """与 ⑶／ⓘ1 同一豁免口径：预登记行的清单本就允许是范围性描述。"""
        status = self.m.PREREGISTERED_STATUS_PREFIX + "，收工时精确化）"
        self.assertEqual(self._violations(
            "1-转型规划/0-全景路线图/队列行日志/#506.md", status=status
        ), [])

    def test_short_row_not_crashing(self):
        self.assertEqual(self.m._file_list_bare_path_violations(["B-TEST"]), [])

    # ---- 与消费侧对齐：本守卫拦的正是 sweep 取不到的那一类 ----

    def test_guard_fires_exactly_when_fragment_extraction_yields_nothing(self):
        """🔑 判据与消费侧同源的证明：被拦的那一格，`_pending_batch_
        fragments`（release ⑹ 侧，与 sweep `_resolve_batch_fragments` 同源）
        提取到 0 个片段；改成反引号后提取到 2 个。"""
        bare = "0-学习与工具/a.py；0-学习与工具/b.py"
        quoted = "`0-学习与工具/a.py`；`0-学习与工具/b.py`"
        section_two = (
            "| 批次 | 文件清单 | 说明 | 状态 |\n"
            "|---|---|---|---|\n"
            "| B-X | %s | m | 待处理 |\n"
        )
        self.assertEqual(
            self.m._pending_batch_fragments({"q": "## 二、批次\n\n" + section_two % bare}),
            [],
        )
        self.assertTrue(self._violations(bare))
        self.assertEqual(
            len(self.m._pending_batch_fragments(
                {"q": "## 二、批次\n\n" + section_two % quoted}
            )),
            2,
        )
        self.assertEqual(self._violations(quoted), [])


class SectionOneDomainFieldGuardTests(unittest.TestCase):
    """⑵ `#523`：§一 状态列 `[D:机|业]` 写侧守卫 ＋ WIP 计数的非静默降级。

    🔴 **读侧宽容与写侧严格是两件事、方向相反且都要有用例钉住**：`#523`
    立行当天的错误结论（"`--digest` 漏 9 行"）正来自值周方自写正则
    `\\[S:…\\]\\[D:…\\]` **不容忍** `[D:]` 缺失。故本类既测"写侧拒"，也测
    "读侧仍解析得出、不丢行"。
    """

    def setUp(self):
        self.m = _load_module()

    def _row(self, status_cell: str, row_id: str = "901"):
        return [row_id, "任务", "CC", "指针", "产出", status_cell, "触碰区", "2026-09-09"]

    # ---- 正向：缺 [D:] 必须被拦 ----

    def test_missing_domain_field_rejected(self):
        problems = self.m._section_one_domain_field_violations(
            self._row("[S:open] 待领（机器人写入形态）")
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("缺 `[D:机|业]`", problems[0])
        self.assertIn("#901", problems[0])

    def test_missing_domain_field_rejected_for_every_movable_status(self):
        for value in ("open", "partial", "hold"):
            with self.subTest(value=value):
                self.assertTrue(self.m._section_one_domain_field_violations(
                    self._row(f"[S:{value}] 正文")
                ))

    # ---- 反向：不得误报 ----

    def test_domain_field_present_passes(self):
        for domain in ("机", "业"):
            with self.subTest(domain=domain):
                self.assertEqual(self.m._section_one_domain_field_violations(
                    self._row(f"[S:open][D:{domain}] 待领")
                ), [])

    def test_non_movable_status_without_domain_passes(self):
        """🔴 **判据面与危害面对齐的那道闸**（apply 期实测收窄）：done／
        blocked／`timed=` 本就被 `_count_mechanism_wip` 结构性排除，缺不缺
        `[D:]` 对 WIP 计数没有任何影响——`#523` 自己的实证就是这句话（那 9 行
        缺域行"没出事纯属巧合，因为恰好全是 `[S:done]`"）。守到这里等于把
        "补齐元数据"变成"关行"的前置条件，还会让存量缺域行连销号都做不了。
        实撞：不收窄时 `DualFileRoutingTests` 三条**测双文件路由**的用例当场
        转红——它们红得对，改的是判据、不是断言。"""
        for value in ("done", "blocked", "timed=2026-09-30"):
            with self.subTest(value=value):
                self.assertEqual(self.m._section_one_domain_field_violations(
                    self._row(f"[S:{value}] 正文")
                ), [])

    def test_guarded_statuses_are_exactly_the_counted_ones(self):
        """守卫面与计数面同一个常量，改一处必然同改另一处。"""
        self.assertEqual(self.m.MOVABLE_STATUS_VALUES, ("open", "partial", "hold"))

    def test_status_field_absent_is_not_this_guards_business(self):
        """缺 `[S:]` 由既有 CI 硬门禁 `工具-队列结构lint.py` 与关键格哨兵
        管——同一件事有两个说法比没有说法更坏。"""
        self.assertEqual(self.m._section_one_domain_field_violations(
            self._row("待领（完全没有机器字段）")
        ), [])

    def test_short_row_not_crashing(self):
        self.assertEqual(self.m._section_one_domain_field_violations(["901", "任务"]), [])

    # ---- 读侧仍须宽容（反向闸，防止把写侧严格误推广到读侧）----

    def test_read_side_still_tolerates_missing_domain(self):
        status, domain, rest = self.m._parse_status_domain_fields("[S:open] 待领")
        self.assertEqual(status, "open")
        self.assertIsNone(domain)
        self.assertEqual(rest, " 待领")

    # ---- WIP 计数：非静默降级 ----

    SECTION_ONE = (
        "| # | 任务 | 领取方 | 输入 | 产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| 901 | 甲 | - | - | - | [S:open][D:机] 待领 | - | 2026-09-09 |\n"
        "| 902 | 乙 | - | - | - | [S:open] 待领（缺 D） | - | 2026-09-09 |\n"
        "| 903 | 丙 | - | - | - | [S:done] 已完（缺 D） | - | 2026-09-09 |\n"
    )

    def test_movable_domainless_row_produces_degraded_log(self):
        count, degraded = self.m._count_mechanism_wip(self.SECTION_ONE)
        self.assertEqual(count, 1)  # 计数不变：真实域未知，不猜
        self.assertTrue(any("#902" in d and "缺 [D:机|业]" in d for d in degraded),
                        degraded)

    def test_done_domainless_row_stays_silent(self):
        """噪声控制：done/blocked/timed 本就不进计数，为它们刷屏会让这条
        告警噪声化——噪声化的告警等于没有（`#143` 教训）。"""
        _count, degraded = self.m._count_mechanism_wip(self.SECTION_ONE)
        self.assertFalse(any("#903" in d for d in degraded), degraded)


class RegistrationWaiverAnnotationParsingTests(unittest.TestCase):
    """⑶ `release --waiver`／acquire note 的 `登记豁免：` 路径解析。

    改前口径 ＝「在第一个左括号处截断」，两次独立实证各撞一头：
      ⒜ 泳道 `519-scanner-test`：多个路径各带括注 ⇒ 只有第一个生效，其余
         **静默丢失**；
      ⒝ 看护者 `OP-0909-Q`：避开括号后，最后一个 `；` 之后的说明性文字被
         当成路径去匹配。
    """

    def setUp(self):
        self.m = _load_module()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _touch(self, rel: str):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
        return rel

    # ---- ⒜ 多路径各带括注 ----

    def test_every_path_survives_its_own_annotation(self):
        clauses = self.m._parse_registration_waiver_clauses(
            "登记豁免：a/b/c.md（本批新建）；d/e/f.md（同批）"
            "（作者 OP-0909-W，到期 09-09）"
        )
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0]["paths"], ["a/b/c.md", "d/e/f.md"])

    def test_author_and_due_still_parsed_after_annotation_stripping(self):
        """反向闸：括注改成"整段剔除"之后，`作者`／`到期` 仍须解析得出——
        否则修好一条就打坏另一条。"""
        clauses = self.m._parse_registration_waiver_clauses(
            "登记豁免：a/b/c.md（本批新建）；d/e/f.md（作者 OP-0909-W，到期 12-31）"
        )
        self.assertEqual(clauses[0]["author"], "OP-0909-W")
        self.assertEqual(clauses[0]["due_raw"], "12-31")

    def test_half_width_parentheses_also_stripped(self):
        clauses = self.m._parse_registration_waiver_clauses(
            "登记豁免：a/b/c.md(new);d/e/f.md(same)(作者 OP-X,到期 09-09)"
        )
        self.assertEqual(clauses[0]["paths"], ["a/b/c.md", "d/e/f.md"])
        self.assertEqual(clauses[0]["author"], "OP-X")

    def test_unclosed_paren_falls_back_to_truncation(self):
        """保守侧：括号没闭合时从左括号起全算括注——宁可少认一个路径并显式
        告警，也不要把半句话当路径去匹配。"""
        head, annotation = self.m._split_parenthetical_annotations(
            "a/b/c.md（作者 OP-X，到期 09-09"
        )
        self.assertEqual(head.strip(), "a/b/c.md")
        self.assertIn("作者 OP-X", annotation)

    def test_multiple_waiver_clauses_still_separated(self):
        clauses = self.m._parse_registration_waiver_clauses(
            "登记豁免：a/b.md（甲）登记豁免：c/d.md（乙）"
        )
        self.assertEqual([c["paths"] for c in clauses], [["a/b.md"], ["c/d.md"]])

    # ---- ⒝ 尾随说明性文字：显式告警，不静默降级 ----

    def test_trailing_prose_reported_as_non_path(self):
        clauses = self.m._parse_registration_waiver_clauses(
            "登记豁免：a/b.md；他线脏文件由其作者线自登（作者 OP-X，到期 09-09）"
        )
        self._touch("a/b.md")
        valid, notes = self.m._valid_waiver_paths(clauses, self.root, ["a/b.md"])
        self.assertEqual(valid, {"a/b.md"})
        self.assertTrue(any("不形如路径" in n and "他线脏文件" in n for n in notes), notes)

    def test_zero_valid_candidates_gets_clause_level_summary(self):
        """🔴 逐条 `✗` 仍可能被读成"少放行了一个"——整条 0 生效必须单独说
        出来，那才是 `#513` 那族"看起来生效、实则没覆盖到"的形态。"""
        clauses = self.m._parse_registration_waiver_clauses(
            "登记豁免：不存在/的/路径.md（作者 OP-X，到期 09-09）"
        )
        valid, notes = self.m._valid_waiver_paths(clauses, self.root, [])
        self.assertEqual(valid, set())
        self.assertTrue(any("0 个生效" in n for n in notes), notes)

    def test_all_valid_clause_gets_no_summary_warning(self):
        self._touch("a/b.md")
        clauses = self.m._parse_registration_waiver_clauses(
            "登记豁免：a/b.md（作者 OP-X，到期 09-09）"
        )
        valid, notes = self.m._valid_waiver_paths(clauses, self.root, ["a/b.md"])
        self.assertEqual(valid, {"a/b.md"})
        self.assertEqual(notes, [])

    # ---- 形态只写文案、不做判定（防止修一个静默降级又造一个）----

    def test_real_file_with_unrecognised_extension_still_valid(self):
        """🔴 无回归闸：`PATH_LIKE_EXTENSIONS` 里没有 `.vbs`，但工作树里真有
        这份文件 ⇒ 必须照常生效。若把"形如路径"升格成生效判据，这类文件会
        被静默拒掉——那是把一条同族缺陷从 ⑶ 搬到 ⑵。"""
        self._touch("0-学习与工具/run-commit-sweep-hidden.vbs")
        clauses = self.m._parse_registration_waiver_clauses(
            "登记豁免：0-学习与工具/run-commit-sweep-hidden.vbs（作者 OP-X，到期 09-09）"
        )
        valid, notes = self.m._valid_waiver_paths(clauses, self.root, [])
        self.assertEqual(valid, {"0-学习与工具/run-commit-sweep-hidden.vbs"})
        self.assertEqual(notes, [])

    def test_deleted_dirty_file_still_valid(self):
        """既有口径不得被本次改动动到：被删除的脏文件在磁盘上恰恰不存在，
        只按"文件存在"判会把一次合法的删除豁免拒掉。"""
        clauses = self.m._parse_registration_waiver_clauses(
            "登记豁免：已删/的/件.md（作者 OP-X，到期 09-09）"
        )
        valid, _notes = self.m._valid_waiver_paths(clauses, self.root, ["已删/的/件.md"])
        self.assertEqual(valid, {"已删/的/件.md"})

    def test_missing_path_shaped_candidate_keeps_original_wording(self):
        clauses = self.m._parse_registration_waiver_clauses(
            "登记豁免：不存在/的/路径.md（作者 OP-X，到期 09-09）"
        )
        _valid, notes = self.m._valid_waiver_paths(clauses, self.root, [])
        self.assertTrue(any("既不在工作树内" in n for n in notes), notes)


class WriteSideGuardCliTests(unittest.TestCase):
    """⑴＋⑵ 的端到端闸：`append-row` 硬拒、`edit-row` 按归属分档。

    黑盒方式：`--file` 指向本用例专属临时文件（同 `AppendRowTests` 惯例），
    不触碰真实队列锁／REPO_ROOT。
    """

    FIXTURE = (
        "## 一、任务看板\n\n"
        "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|------|--------|-------------|----------|------|--------|------|\n"
        "| 100 | 存量缺域行 | CC | 无 | 无 | [S:open] 待领 | 无 | 2026-09-09 |\n"
        "\n## 二、待 commit 批次（CC 取活销行）\n\n"
        "| 批次 | 文件清单 | 说明 | 状态 |\n"
        "|------|---------|------|------|\n"
        "| B-存量 | 0-学习与工具/存量裸路径.py | 说明 | 待处理 |\n"
        "\n## 四、需 Shao Peishen 的动作（例外与拍板）\n\n"
        "| # | 事项 | 等谁 | 截止 |\n"
        "|---|------|------|------|\n"
    )

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.target = Path(self._tmpdir.name) / "假想队列.md"
        self.target.write_text(self.FIXTURE, encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return run("--file", str(self.target), *args)

    # ---- ⑴ append-row ----

    def test_append_row_rejects_bare_path_without_writing(self):
        before = self.target.read_text(encoding="utf-8")
        result = self._run(
            "append-row", "--section", "二",
            "--cell", "B-新批次", "--cell", "0-学习与工具/工具-共享文档编辑锁.py",
            "--cell", "说明", "--cell", "待处理",
        )
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("未用反引号包裹", result.stdout)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    def test_append_row_accepts_range_shorthand_in_backticks(self):
        """正向对照：同一条命令把清单改成反引号包裹的范围性速记即通过
        （速记不做存在性核验，故不依赖主仓实时 git 状态，可稳定复现）。"""
        result = self._run(
            "append-row", "--section", "二",
            "--cell", "B-新批次", "--cell", "`X/tests/test_*.py`",
            "--cell", "说明", "--cell", "待处理",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("| B-新批次 | `X/tests/test_*.py` | 说明 | 待处理 |",
                      self.target.read_text(encoding="utf-8"))

    # ---- ⑵ append-row ----

    def test_append_row_rejects_section_one_row_without_domain_field(self):
        before = self.target.read_text(encoding="utf-8")
        result = self._run(
            "append-row", "--section", "一", "--number", "101",
            "--cell", "新任务", "--cell", "CC", "--cell", "无", "--cell", "无",
            "--cell", "[S:open] 待领", "--cell", "无", "--cell", "2026-09-09",
        )
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("缺 `[D:机|业]`", result.stdout)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    def test_append_row_accepts_section_one_row_with_domain_field(self):
        result = self._run(
            "append-row", "--section", "一", "--number", "101",
            "--cell", "新任务", "--cell", "CC", "--cell", "无", "--cell", "无",
            "--cell", "[S:open][D:机] 待领", "--cell", "无", "--cell", "2026-09-09",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("| 101 | 新任务 |", self.target.read_text(encoding="utf-8"))

    # ---- 存量分档：本次没碰那一格就不该由你负责 ----

    def test_edit_row_only_warns_when_legacy_file_list_untouched(self):
        """🔴 存量降级用例（`#513` 明写"只建写侧守卫、不回改存量"）：
        2026-09-09 实测 §二 待处理 34 行里 28 行零反引号片段——一律硬拦会把
        "给存量批次销状态"这个动作整个堵死，而销状态的人并没有写坏那一格。"""
        result = self._run(
            "edit-row", "--section", "二", "--number", "B-存量",
            "--set", "状态=✅ 已完成",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("未用反引号包裹", result.stdout)   # 告警照打、照点名
        self.assertIn("只告警、不阻断", result.stdout)
        self.assertIn("| B-存量 | 0-学习与工具/存量裸路径.py | 说明 | ✅ 已完成 |",
                      self.target.read_text(encoding="utf-8"))

    def test_edit_row_blocks_when_file_list_itself_is_written(self):
        before = self.target.read_text(encoding="utf-8")
        result = self._run(
            "edit-row", "--section", "二", "--number", "B-存量",
            "--set", "文件清单=0-学习与工具/又一个裸路径.py",
        )
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("未用反引号包裹", result.stdout)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    def test_edit_row_only_warns_when_legacy_status_cell_untouched(self):
        result = self._run(
            "edit-row", "--section", "一", "--number", "100",
            "--set", "触碰区=新触碰区",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("缺 `[D:机|业]`", result.stdout)
        self.assertIn("只告警、不阻断", result.stdout)
        self.assertIn("| 新触碰区 |", self.target.read_text(encoding="utf-8"))

    def test_edit_row_blocks_when_status_cell_itself_is_written(self):
        before = self.target.read_text(encoding="utf-8")
        result = self._run(
            "edit-row", "--section", "一", "--number", "100",
            "--set", "状态=[S:partial] 在办",
        )
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("缺 `[D:机|业]`", result.stdout)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    def test_edit_row_status_rewrite_with_domain_field_passes(self):
        result = self._run(
            "edit-row", "--section", "一", "--number", "100",
            "--set", "状态=[S:partial][D:机] 在办",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("[S:partial][D:机] 在办", self.target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
