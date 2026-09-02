"""`工具-泳道看护状态机.py` 单测（队列 §一 `#452`，`OP-0902-B`）。

白盒方式：按文件路径 importlib 加载被测脚本（本目录既定手法，同
`test_工具-跟进闸查询.py`），把 `REPO_ROOT` 指向临时夹具目录——不触碰
真实 `reports/`。企微推送一律注入 stub `notify_fn`，不发真实网络请求。
"""
from __future__ import annotations

import importlib.util
import io
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-泳道看护状态机.py")


def _load():
    spec = importlib.util.spec_from_file_location("_lane_watch_cli_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _StubNotifier:
    """记录收到的每条通知正文，不发真实请求。"""

    def __init__(self):
        self.messages: list[str] = []

    def __call__(self, content: str) -> None:
        self.messages.append(content)


class LaneWatchStateMachineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.module = _load()
        self.module.REPO_ROOT = self.root

    def tearDown(self):
        self._tmp.cleanup()

    # ---------------- classify（D1 三档 + fail-safe） ----------------

    def test_classify_green_covered(self):
        cls = self.module.classify("worktree_local_build")
        self.assertEqual(cls.tier, self.module.TIER_GREEN)
        self.assertTrue(cls.covered)

    def test_classify_yellow_covered(self):
        cls = self.module.classify("merge_to_master")
        self.assertEqual(cls.tier, self.module.TIER_YELLOW)
        self.assertTrue(cls.covered)

    def test_classify_red_covered(self):
        cls = self.module.classify("external_send")
        self.assertEqual(cls.tier, self.module.TIER_RED)
        self.assertTrue(cls.covered)

    def test_classify_unknown_action_is_fail_safe_yellow(self):
        cls = self.module.classify("some_never_seen_action")
        self.assertEqual(cls.tier, self.module.TIER_YELLOW)
        self.assertFalse(cls.covered)
        self.assertIn("未覆盖", cls.note)

    # ---------------- pause ----------------

    def test_pause_rejects_green_action(self):
        with self.assertRaises(ValueError):
            self.module.pause_lane(
                batch="B1", wave=1, lane="A", action_key="doc_edit",
                waiting_for="不该问", notify_fn=_StubNotifier(),
            )

    def test_pause_writes_state_and_history(self):
        notifier = _StubNotifier()
        state = self.module.pause_lane(
            batch="B1", wave=2, lane="A", action_key="deploy_51",
            waiting_for="是否现在部署 .51", options=["部署", "先不部署"],
            notify_fn=notifier,
        )
        self.assertEqual(state["status"], "paused")
        self.assertEqual(state["tier"], self.module.TIER_YELLOW)
        self.assertEqual(state["original_status"], "running")
        self.assertEqual(len(state["history"]), 1)
        self.assertIsNone(state["history"][0]["resolved_by"])

        # 落盘可从磁盘重读，且是真实文件（reports/ 下）
        on_disk = self.module._read_state()
        self.assertEqual(on_disk["lanes"]["A"]["status"], "paused")
        self.assertTrue(str(self.module._state_path()).endswith(
            os.path.join("reports", "lane-watch-state.json")
        ))

    def test_pause_calls_notify_with_lane_and_waiting_for(self):
        notifier = _StubNotifier()
        self.module.pause_lane(
            batch="B1", wave=1, lane="灯箱", action_key="external_send",
            waiting_for="是否发送跟进信", notify_fn=notifier,
        )
        self.assertEqual(len(notifier.messages), 1)
        self.assertIn("灯箱", notifier.messages[0])
        self.assertIn("是否发送跟进信", notifier.messages[0])
        self.assertIn(self.module.TIER_RED, notifier.messages[0])

    def test_pause_uncovered_action_notice_carries_fail_safe_note(self):
        notifier = _StubNotifier()
        self.module.pause_lane(
            batch="B1", wave=1, lane="A", action_key="unseen_action",
            waiting_for="不确定该不该做", notify_fn=notifier,
        )
        self.assertIn("未覆盖", notifier.messages[0])

    def test_pause_notify_exception_does_not_break_state_write(self):
        def _boom(_content: str) -> None:
            raise RuntimeError("网络挂了")

        state = self.module.pause_lane(
            batch="B1", wave=1, lane="A", action_key="merge_to_master",
            waiting_for="是否合入 master", notify_fn=_boom,
        )
        self.assertEqual(state["status"], "paused")
        on_disk = self.module._read_state()
        self.assertEqual(on_disk["lanes"]["A"]["status"], "paused")

    def test_pause_missing_wecom_script_degrades_gracefully(self):
        # notify_fn=None 时会尝试真实加载 发企微.py；本临时夹具目录里没有
        # 该脚本，应降级为仅落状态，不抛异常。
        state = self.module.pause_lane(
            batch="B1", wave=1, lane="A", action_key="merge_to_master",
            waiting_for="是否合入 master", notify_fn=None,
        )
        self.assertEqual(state["status"], "paused")

    # ---------------- resume ----------------

    def test_resume_records_answer_and_closes_history(self):
        self.module.pause_lane(
            batch="B1", wave=1, lane="A", action_key="merge_to_master",
            waiting_for="是否合入 master", notify_fn=_StubNotifier(),
        )
        state = self.module.resume_lane(lane="A", answer="合入")
        self.assertEqual(state["status"], "resumed")
        self.assertEqual(state["answer"], "合入")
        self.assertIsNotNone(state["answered_at"])
        self.assertEqual(state["history"][-1]["resolved_by"], "answered")
        self.assertEqual(state["history"][-1]["answer"], "合入")

    def test_resume_rejects_lane_not_paused(self):
        with self.assertRaises(ValueError):
            self.module.resume_lane(lane="从未存在过", answer="随便")

    def test_resume_rejects_double_resume(self):
        self.module.pause_lane(
            batch="B1", wave=1, lane="A", action_key="merge_to_master",
            waiting_for="是否合入 master", notify_fn=_StubNotifier(),
        )
        self.module.resume_lane(lane="A", answer="合入")
        with self.assertRaises(ValueError):
            self.module.resume_lane(lane="A", answer="再答一次")

    # ---------------- check-timeout（D5 解法 3） ----------------

    def test_check_timeout_leaves_fresh_pause_alone(self):
        self.module.pause_lane(
            batch="B1", wave=1, lane="A", action_key="merge_to_master",
            waiting_for="是否合入 master", notify_fn=_StubNotifier(),
        )
        reverted = self.module.check_timeouts(hours=4.0)
        self.assertEqual(reverted, [])
        self.assertEqual(self.module._read_state()["lanes"]["A"]["status"], "paused")

    def test_check_timeout_reverts_stale_pause(self):
        self.module.pause_lane(
            batch="B1", wave=1, lane="A", action_key="merge_to_master",
            waiting_for="是否合入 master", notify_fn=_StubNotifier(),
        )
        # 手工把 paused_at 拨回 5 小时前，模拟「触发后中途离开」。
        state = self.module._read_state()
        five_hours_ago = self.module._now() - self.module.timedelta(hours=5)
        state["lanes"]["A"]["paused_at"] = self.module._iso(five_hours_ago)
        self.module._atomic_write_state(state)

        reverted = self.module.check_timeouts(hours=4.0)
        self.assertEqual(len(reverted), 1)
        self.assertEqual(reverted[0]["lane"], "A")
        self.assertEqual(reverted[0]["reverted_to"], "running")

        on_disk = self.module._read_state()
        self.assertEqual(on_disk["lanes"]["A"]["status"], "running")
        self.assertEqual(on_disk["lanes"]["A"]["revert_reason"], "因超时未获答复而收回")
        self.assertEqual(on_disk["lanes"]["A"]["history"][-1]["resolved_by"], "timeout")

    def test_check_timeout_does_not_touch_resumed_lane(self):
        self.module.pause_lane(
            batch="B1", wave=1, lane="A", action_key="merge_to_master",
            waiting_for="是否合入 master", notify_fn=_StubNotifier(),
        )
        self.module.resume_lane(lane="A", answer="合入")
        state = self.module._read_state()
        five_hours_ago = self.module._now() - self.module.timedelta(hours=5)
        state["lanes"]["A"]["paused_at"] = self.module._iso(five_hours_ago)
        self.module._atomic_write_state(state)

        reverted = self.module.check_timeouts(hours=4.0)
        self.assertEqual(reverted, [])
        self.assertEqual(self.module._read_state()["lanes"]["A"]["status"], "resumed")

    # ---------------- summary（D6） ----------------

    def test_summary_empty(self):
        rows = self.module.build_summary(batch="B1")
        self.assertEqual(self.module.format_summary_line(rows), "本批停 0 次")

    def test_summary_counts_open_answered_and_timeout(self):
        # 泳道 A：答复关闭
        self.module.pause_lane(
            batch="B1", wave=1, lane="A", action_key="merge_to_master",
            waiting_for="是否合入 master", notify_fn=_StubNotifier(),
        )
        self.module.resume_lane(lane="A", answer="合入")

        # 泳道 B：仍在等
        self.module.pause_lane(
            batch="B1", wave=1, lane="B", action_key="deploy_51",
            waiting_for="是否部署", notify_fn=_StubNotifier(),
        )

        # 泳道 C：超时收回
        self.module.pause_lane(
            batch="B1", wave=1, lane="C", action_key="change_criteria",
            waiting_for="口径怎么改", notify_fn=_StubNotifier(),
        )
        state = self.module._read_state()
        five_hours_ago = self.module._now() - self.module.timedelta(hours=5)
        state["lanes"]["C"]["paused_at"] = self.module._iso(five_hours_ago)
        self.module._atomic_write_state(state)
        self.module.check_timeouts(hours=4.0)

        rows = self.module.build_summary(batch="B1")
        self.assertEqual(len(rows), 3)
        answers = {r["lane"]: r["answer"] for r in rows}
        self.assertEqual(answers["A"], "合入")
        self.assertEqual(answers["B"], "仍在等")
        self.assertEqual(answers["C"], "超时收回")

        line = self.module.format_summary_line(rows)
        self.assertTrue(line.startswith("本批停 3 次｜逐次："))

    def test_summary_filters_by_batch(self):
        self.module.pause_lane(
            batch="B1", wave=1, lane="A", action_key="merge_to_master",
            waiting_for="X", notify_fn=_StubNotifier(),
        )
        self.module.pause_lane(
            batch="B2", wave=1, lane="D", action_key="merge_to_master",
            waiting_for="Y", notify_fn=_StubNotifier(),
        )
        rows_b1 = self.module.build_summary(batch="B1")
        self.assertEqual([r["lane"] for r in rows_b1], ["A"])

    # ---------------- 锁：陈旧接管 + 超时 ----------------

    def test_lock_stale_takeover(self):
        state_path = self.module._state_path()
        state_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = Path(str(state_path) + ".lock")
        lock_path.write_text("99999999", encoding="utf-8")
        old = time.time() - (self.module.LOCK_STALE_SECONDS + 30)
        os.utime(lock_path, (old, old))

        # 陈旧锁应被接管，_with_state 正常完成且不抛超时。
        result = self.module._with_state(lambda data: data["lanes"].setdefault("A", {"status": "running", "history": []}))
        self.assertIn("A", result["lanes"])
        self.assertFalse(lock_path.exists())  # 用完即释放

    def test_lock_fresh_lock_causes_timeout(self):
        state_path = self.module._state_path()
        state_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = Path(str(state_path) + ".lock")
        lock_path.write_text(str(os.getpid()), encoding="utf-8")  # 新鲜锁，未过期

        with self.assertRaises(self.module._LockTimeout):
            with self.module._StateLock(state_path, timeout=0.3):
                pass

        lock_path.unlink()  # 清理，不影响其他用例

    # ---------------- CLI 冒烟 ----------------

    def _run_cli(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = self.module.main(argv)
        return code, buf.getvalue()

    def test_cli_criteria_json_lists_all_three_tiers(self):
        code, out = self._run_cli(["criteria", "--json"])
        self.assertEqual(code, 0)
        for tier in (self.module.TIER_GREEN, self.module.TIER_YELLOW, self.module.TIER_RED):
            self.assertIn(tier, out)

    def test_cli_pause_then_show_then_resume(self):
        code, out = self._run_cli([
            "pause", "--batch", "B1", "--wave", "1", "--lane", "A",
            "--action-key", "merge_to_master", "--waiting-for", "是否合入", "--no-notify",
        ])
        self.assertEqual(code, 0)
        self.assertIn("⏸", out)

        code, out = self._run_cli(["show", "--lane", "A"])
        self.assertEqual(code, 0)
        self.assertIn("paused", out)

        code, out = self._run_cli(["resume", "--lane", "A", "--answer", "合入"])
        self.assertEqual(code, 0)
        self.assertIn("▶", out)

    def test_cli_pause_green_action_returns_exit_1(self):
        code, _out = self._run_cli([
            "pause", "--batch", "B1", "--wave", "1", "--lane", "A",
            "--action-key", "doc_edit", "--waiting-for", "不该问", "--no-notify",
        ])
        self.assertEqual(code, 1)

    def test_cli_resume_unknown_lane_returns_exit_1(self):
        code, _out = self._run_cli(["resume", "--lane", "从未存在过", "--answer", "x"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
