# -*- coding: utf-8 -*-
"""`工具-泳道看护等待.py` 单测（队列 §一 `#598` 期望产出 ①＋④）。

白盒方式：按文件路径 importlib 加载被测脚本（同 `test_工具-泳道看护状态机.py`
既定手法），把底层状态机子模块的 `REPO_ROOT` 指向临时夹具目录——不触碰真实
`reports/`。全程用极小的 `max_wait`／`poll_interval`（毫秒级）驱动轮询循环，
保持单测秒级跑完；不依赖真实 15 秒轮询间隔。
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
import unittest
from io import StringIO
from contextlib import redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-泳道看护等待.py")


def _load():
    spec = importlib.util.spec_from_file_location("_lane_watch_wait_cli_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class LaneWatchWaitTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.module = _load()
        self.module._state_machine.REPO_ROOT = self.root

    def tearDown(self):
        self._tmp.cleanup()

    # ---------------- 夹具 helpers ----------------

    def _write_state(self, lanes: dict) -> None:
        path = self.root / "reports" / "lane-watch-state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"lanes": lanes}, ensure_ascii=False), encoding="utf-8")

    def _write_heartbeat(self, lane: str, text: str, *, age_minutes: float = 0.0) -> Path:
        path = self.root / "reports" / "lane-heartbeat" / f"{lane}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        if age_minutes:
            old = time.time() - age_minutes * 60
            import os
            os.utime(path, (old, old))
        return path

    # ---------------- MAX-WAIT：健康运行、零信号 ----------------

    def test_无任何泳道留痕时跑满max_wait后报MAX_WAIT(self):
        result = self.module.wait_for_batch(
            batch="B-测试批", max_wait=0.05, poll_interval=0.02,
        )
        self.assertEqual(result["status"], "max_wait")
        self.assertEqual(result["lanes"], [])

    # ---------------- DONE：状态记录 ----------------

    def test_泳道已终态即报DONE(self):
        self._write_state({
            "lane-a": {"status": "done", "batch": "B-测试批", "history": []},
            "lane-b": {"status": "running", "batch": "B-其它批", "history": []},
        })
        result = self.module.wait_for_batch(batch="B-测试批", max_wait=1.0, poll_interval=0.02)
        self.assertEqual(result["status"], "done")
        self.assertEqual(result["lanes"], ["lane-a"])

    # ---------------- PAUSED：状态记录 ----------------

    def test_泳道已暂停即报PAUSED(self):
        self._write_state({
            "lane-a": {"status": "paused", "batch": "B-测试批", "history": []},
        })
        result = self.module.wait_for_batch(batch="B-测试批", max_wait=1.0, poll_interval=0.02)
        self.assertEqual(result["status"], "paused")
        self.assertEqual(result["lanes"], ["lane-a"])

    def test_DONE优先于PAUSED(self):
        """同一轮若既有 done 又有 paused，DONE 先判——他更关心已完工的那条。"""
        self._write_state({
            "lane-a": {"status": "done", "batch": "B-测试批", "history": []},
            "lane-b": {"status": "paused", "batch": "B-测试批", "history": []},
        })
        result = self.module.wait_for_batch(batch="B-测试批", max_wait=1.0, poll_interval=0.02)
        self.assertEqual(result["status"], "done")

    # ---------------- NO-HEARTBEAT／TIMEOUT：心跳文件 ----------------

    def test_已留痕泳道心跳文件缺失报NO_HEARTBEAT(self):
        # running 且已有 batch 留痕（模拟一条曾经历过 watchdog/resume 循环、
        # 现处于「原状态」但心跳文件从未落地的泳道）。
        self._write_state({
            "lane-a": {"status": "running", "batch": "B-测试批", "history": []},
        })
        result = self.module.wait_for_batch(batch="B-测试批", max_wait=0.05, poll_interval=0.02)
        self.assertEqual(result["status"], "no_heartbeat")
        self.assertEqual(result["lanes"], ["lane-a"])

    def test_心跳文件超龄报TIMEOUT(self):
        self._write_state({
            "lane-a": {"status": "running", "batch": "B-测试批", "history": []},
        })
        self._write_heartbeat("lane-a", "10:00:00 ｜ 仍在跑", age_minutes=40)
        result = self.module.wait_for_batch(
            batch="B-测试批", max_wait=0.05, poll_interval=0.02, stale_minutes=30,
        )
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["lanes"], ["lane-a"])

    def test_心跳新鲜且非终态时跑满max_wait(self):
        self._write_state({
            "lane-a": {"status": "running", "batch": "B-测试批", "history": []},
        })
        self._write_heartbeat("lane-a", "10:00:00 ｜ 仍在跑", age_minutes=1)
        result = self.module.wait_for_batch(
            batch="B-测试批", max_wait=0.05, poll_interval=0.02, stale_minutes=30,
        )
        self.assertEqual(result["status"], "max_wait")

    def test_命中DONE哨兵的心跳文件豁免超龄判定(self):
        """状态记录还没来得及写 done（如手工只写了心跳），但心跳末行已是
        `DONE｜` 哨兵——同 `check_heartbeat()` 的终态豁免，不判 TIMEOUT。"""
        self._write_state({
            "lane-a": {"status": "running", "batch": "B-测试批", "history": []},
        })
        self._write_heartbeat("lane-a", "10:00:00 ｜ DONE ｜ 已收工", age_minutes=90)
        result = self.module.wait_for_batch(
            batch="B-测试批", max_wait=0.05, poll_interval=0.02, stale_minutes=30,
        )
        self.assertEqual(result["status"], "max_wait", "命中收工哨兵不应报 TIMEOUT/NO-HEARTBEAT")

    # ---------------- 进程：--log-dir ----------------

    def test_日志目录exit文件存在即报DONE(self):
        log_dir = self.root / "reports" / "opener-batch" / "20260916-000000"
        log_dir.mkdir(parents=True)
        (log_dir / "exit.txt").write_text("0\n", encoding="utf-8")
        result = self.module.wait_for_batch(
            batch="B-测试批", max_wait=0.05, poll_interval=0.02, log_dirs=[str(log_dir)],
        )
        self.assertEqual(result["status"], "done")
        self.assertEqual(result["process"][0]["exit_code"], "0")

    def test_日志目录未生成exit文件时不误判(self):
        log_dir = self.root / "reports" / "opener-batch" / "20260916-000001"
        log_dir.mkdir(parents=True)
        result = self.module.wait_for_batch(
            batch="B-测试批", max_wait=0.05, poll_interval=0.02, log_dirs=[str(log_dir)],
        )
        self.assertEqual(result["status"], "max_wait", "既无 exit.txt 也无 launcher.json，不应误判已退出")

    # ---------------- 批次过滤：不同批互不影响 ----------------

    def test_其它批次的泳道不触发事件(self):
        self._write_state({
            "lane-a": {"status": "done", "batch": "B-别的批", "history": []},
        })
        result = self.module.wait_for_batch(batch="B-测试批", max_wait=0.05, poll_interval=0.02)
        self.assertEqual(result["status"], "max_wait")

    # ---------------- CLI：退出码＋输出行数 ----------------

    def test_cli_wait输出不超过20行且退出码对应DONE(self):
        self._write_state({
            "lane-a": {"status": "done", "batch": "B-测试批", "history": []},
        })
        buf = StringIO()
        with redirect_stdout(buf):
            code = self.module.main([
                "wait", "--batch", "B-测试批", "--max-wait", "0.05", "--poll-interval", "0.02",
            ])
        self.assertEqual(code, self.module.EXIT_CODES["done"])
        lines = [l for l in buf.getvalue().splitlines() if l.strip()]
        self.assertLessEqual(len(lines), 20)
        self.assertIn("DONE", lines[0])
        self.assertIn("lane-a", lines[0])

    def test_cli_maxwait退出码(self):
        buf = StringIO()
        with redirect_stdout(buf):
            code = self.module.main([
                "wait", "--batch", "B-测试批", "--max-wait", "0.05", "--poll-interval", "0.02",
            ])
        self.assertEqual(code, self.module.EXIT_CODES["max_wait"])


if __name__ == "__main__":
    unittest.main()
