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

    def test_classify_transfer_covered(self):
        # 2026-09-02 架构收敛：`.51` 部署由 🟡 移入新第四档 ⏭️ 转出。
        cls = self.module.classify("deploy_51")
        self.assertEqual(cls.tier, self.module.TIER_TRANSFER)
        self.assertTrue(cls.covered)

    def test_deploy_51_no_longer_in_yellow_actions(self):
        self.assertNotIn("deploy_51", self.module.YELLOW_ACTIONS)
        self.assertIn("deploy_51", self.module.TRANSFER_ACTIONS)

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

    def test_pause_rejects_transfer_action(self):
        # ⏭️ 转出档不进 pause/resume 问答循环，须走 transfer_out_lane。
        with self.assertRaises(ValueError):
            self.module.pause_lane(
                batch="B1", wave=1, lane="A", action_key="deploy_51",
                waiting_for="不该问", notify_fn=_StubNotifier(),
            )

    def test_pause_writes_state_and_history(self):
        notifier = _StubNotifier()
        state = self.module.pause_lane(
            batch="B1", wave=2, lane="A", action_key="change_criteria",
            waiting_for="口径该怎么改", options=["方案一", "方案二"],
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

    # ---------------- transfer-out（⏭️ D1 第四档，3.5） ----------------

    def test_transfer_out_rejects_green_action(self):
        with self.assertRaises(ValueError):
            self.module.transfer_out_lane(
                batch="B1", wave=1, lane="A", action_key="doc_edit",
                notify_fn=_StubNotifier(),
            )

    def test_transfer_out_rejects_yellow_action(self):
        with self.assertRaises(ValueError):
            self.module.transfer_out_lane(
                batch="B1", wave=1, lane="A", action_key="merge_to_master",
                notify_fn=_StubNotifier(),
            )

    def test_transfer_out_records_transfer_without_touching_status(self):
        notifier = _StubNotifier()
        state = self.module.transfer_out_lane(
            batch="B1", wave=1, lane="A", action_key="deploy_51",
            note="需部署到 .51", notify_fn=notifier,
        )
        # 不进 pause 问答循环：status 保持初始 "running"，不是 "paused"。
        self.assertEqual(state["status"], "running")
        self.assertEqual(len(state["transfers"]), 1)
        self.assertEqual(state["transfers"][0]["action_key"], "deploy_51")
        self.assertEqual(state["transfers"][0]["note"], "需部署到 .51")

        on_disk = self.module._read_state()
        self.assertEqual(len(on_disk["lanes"]["A"]["transfers"]), 1)

    def test_transfer_out_notify_contains_lane_and_destination(self):
        notifier = _StubNotifier()
        self.module.transfer_out_lane(
            batch="B1", wave=1, lane="灯箱", action_key="deploy_51", notify_fn=notifier,
        )
        self.assertEqual(len(notifier.messages), 1)
        self.assertIn("灯箱", notifier.messages[0])
        self.assertIn("zhuopin-lan-closeout", notifier.messages[0])

    def test_transfer_out_notify_exception_does_not_break_state_write(self):
        def _boom(_content: str) -> None:
            raise RuntimeError("网络挂了")

        state = self.module.transfer_out_lane(
            batch="B1", wave=1, lane="A", action_key="deploy_51", notify_fn=_boom,
        )
        self.assertEqual(len(state["transfers"]), 1)
        on_disk = self.module._read_state()
        self.assertEqual(len(on_disk["lanes"]["A"]["transfers"]), 1)

    def test_transfer_out_multiple_lanes_do_not_leak_into_each_other(self):
        self.module.transfer_out_lane(
            batch="B1", wave=1, lane="A", action_key="deploy_51", notify_fn=_StubNotifier(),
        )
        self.module.transfer_out_lane(
            batch="B1", wave=1, lane="B", action_key="deploy_51", notify_fn=_StubNotifier(),
        )
        on_disk = self.module._read_state()
        self.assertEqual(len(on_disk["lanes"]["A"]["transfers"]), 1)
        self.assertEqual(len(on_disk["lanes"]["B"]["transfers"]), 1)

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

    def test_check_timeout_ignores_lane_with_only_transfers(self):
        # 转出记录不设 status=paused，check-timeout（只扫 paused 态）须原样跳过。
        self.module.transfer_out_lane(
            batch="B1", wave=1, lane="A", action_key="deploy_51", notify_fn=_StubNotifier(),
        )
        reverted = self.module.check_timeouts(hours=4.0)
        self.assertEqual(reverted, [])
        self.assertEqual(self.module._read_state()["lanes"]["A"]["status"], "running")

    # ---------------- check-heartbeat（5.6 波间看门狗） ----------------

    def test_check_heartbeat_fresh_file_is_not_stale(self):
        hb_dir = self.root / "reports" / "lane-heartbeat"
        hb_dir.mkdir(parents=True)
        hb_file = hb_dir / "OP-TEST.md"
        hb_file.write_text("00:00:00 ｜ 已开工", encoding="utf-8")

        result = self.module.check_heartbeat(
            batch="B1", wave=1, lane="A",
            heartbeat_file="reports/lane-heartbeat/OP-TEST.md",
            stale_minutes=30.0, notify_fn=_StubNotifier(),
        )
        self.assertFalse(result["stale"])
        self.assertEqual(self.module._read_state().get("lanes", {}), {})

    def test_check_heartbeat_missing_file_is_stale_and_pauses(self):
        notifier = _StubNotifier()
        result = self.module.check_heartbeat(
            batch="B1", wave=1, lane="A",
            heartbeat_file="reports/lane-heartbeat/不存在.md",
            stale_minutes=30.0, notify_fn=notifier,
        )
        self.assertTrue(result["stale"])
        self.assertFalse(result["already_paused"])
        state = self.module._read_state()["lanes"]["A"]
        self.assertEqual(state["status"], "paused")
        self.assertEqual(state["tier"], self.module.TIER_WATCHDOG)
        self.assertEqual(state["action_key"], "heartbeat_stale")
        self.assertEqual(len(notifier.messages), 1)
        self.assertIn("看门狗", notifier.messages[0])

    def test_check_heartbeat_stale_mtime_pauses(self):
        hb_dir = self.root / "reports" / "lane-heartbeat"
        hb_dir.mkdir(parents=True)
        hb_file = hb_dir / "OP-TEST.md"
        hb_file.write_text("00:00:00 ｜ 已开工", encoding="utf-8")
        old = time.time() - 31 * 60  # 31 分钟前，超过默认 30 分钟阈值
        os.utime(hb_file, (old, old))

        result = self.module.check_heartbeat(
            batch="B1", wave=1, lane="A",
            heartbeat_file="reports/lane-heartbeat/OP-TEST.md",
            notify_fn=_StubNotifier(),
        )
        self.assertTrue(result["stale"])
        self.assertGreaterEqual(result["age_minutes"], 31.0)

    def test_check_heartbeat_skips_already_paused_lane(self):
        # 泳道已在等 D1 决策点——「没心跳」是预期状态，不该被看门狗二次触发。
        self.module.pause_lane(
            batch="B1", wave=1, lane="A", action_key="merge_to_master",
            waiting_for="是否合入 master", notify_fn=_StubNotifier(),
        )
        notifier = _StubNotifier()
        result = self.module.check_heartbeat(
            batch="B1", wave=1, lane="A",
            heartbeat_file="reports/lane-heartbeat/不存在.md",
            notify_fn=notifier,
        )
        self.assertTrue(result["stale"])
        self.assertTrue(result["already_paused"])
        self.assertEqual(notifier.messages, [])  # 未重复通知
        # 原判据（merge_to_master／🟡）未被看门狗覆盖改写。
        state = self.module._read_state()["lanes"]["A"]
        self.assertEqual(state["action_key"], "merge_to_master")

    def test_check_heartbeat_appears_in_build_summary(self):
        self.module.check_heartbeat(
            batch="B1", wave=1, lane="A",
            heartbeat_file="reports/lane-heartbeat/不存在.md",
            notify_fn=_StubNotifier(),
        )
        rows = self.module.build_summary(batch="B1")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["tier"], self.module.TIER_WATCHDOG)
        self.assertEqual(rows[0]["answer"], "仍在等")

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
            batch="B1", wave=1, lane="B", action_key="openspec_design_review",
            waiting_for="design 是否通过", notify_fn=_StubNotifier(),
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

    # ---------------- build_transfer_summary（D6 邻接：转出清单） ----------------

    def test_transfer_summary_empty(self):
        rows = self.module.build_transfer_summary(batch="B1")
        self.assertEqual(self.module.format_transfer_line(rows), "本批转出 0 项")

    def test_transfer_summary_counts_and_filters_by_batch(self):
        self.module.transfer_out_lane(
            batch="B1", wave=1, lane="A", action_key="deploy_51",
            note="需部署到 .51", notify_fn=_StubNotifier(),
        )
        self.module.transfer_out_lane(
            batch="B2", wave=1, lane="D", action_key="deploy_51", notify_fn=_StubNotifier(),
        )
        rows = self.module.build_transfer_summary(batch="B1")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["lane"], "A")
        line = self.module.format_transfer_line(rows)
        self.assertIn("本批转出 1 项", line)
        self.assertIn("zhuopin-lan-closeout", line)
        self.assertIn("需部署到 .51", line)

    def test_transfer_summary_line_omits_empty_note(self):
        self.module.transfer_out_lane(
            batch="B1", wave=1, lane="A", action_key="deploy_51", notify_fn=_StubNotifier(),
        )
        rows = self.module.build_transfer_summary(batch="B1")
        line = self.module.format_transfer_line(rows)
        # 无 note 时不应出现多余的「／」空段。
        self.assertNotIn("／／", line)

    # ---------------- lan_status（3.5 LAN 探针） ----------------

    def test_lan_status_effective_on(self):
        result = self.module.lan_status(prober=lambda: {"status": "on", "on_lan": True})
        self.assertEqual(result["effective"], "on")

    def test_lan_status_effective_off(self):
        result = self.module.lan_status(prober=lambda: {"status": "off", "on_lan": False})
        self.assertEqual(result["effective"], "off")

    def test_lan_status_effective_unknown_fails_safe_to_off(self):
        # design 3.5：探针不过（unknown）⇒ 按 off-LAN 处理，不可对着不可达的内网瞎跑。
        result = self.module.lan_status(prober=lambda: {"status": "unknown", "on_lan": None})
        self.assertEqual(result["effective"], "off")

    def test_lan_status_preserves_raw_probe_fields(self):
        result = self.module.lan_status(prober=lambda: {"status": "on", "on_lan": True, "probes": ["x"]})
        self.assertEqual(result["probes"], ["x"])
        self.assertEqual(result["status"], "on")

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

    def test_cli_criteria_json_lists_all_four_tiers(self):
        code, out = self._run_cli(["criteria", "--json"])
        self.assertEqual(code, 0)
        for tier in (self.module.TIER_GREEN, self.module.TIER_YELLOW,
                     self.module.TIER_TRANSFER, self.module.TIER_RED):
            self.assertIn(tier, out)
        # 看门狗不是 D1 判据表的一档，不应出现在 criteria 现取列表里。
        self.assertNotIn(self.module.TIER_WATCHDOG, out)

    def test_cli_transfer_out_then_summary(self):
        code, out = self._run_cli([
            "transfer-out", "--batch", "B1", "--wave", "1", "--lane", "A",
            "--action-key", "deploy_51", "--note", "需部署", "--no-notify",
        ])
        self.assertEqual(code, 0)
        self.assertIn("⏭", out)
        self.assertIn("zhuopin-lan-closeout", out)

        code, out = self._run_cli(["summary", "--batch", "B1"])
        self.assertEqual(code, 0)
        self.assertIn("本批转出 1 项", out)

    def test_cli_transfer_out_rejects_non_transfer_action_returns_exit_1(self):
        code, _out = self._run_cli([
            "transfer-out", "--batch", "B1", "--wave", "1", "--lane", "A",
            "--action-key", "merge_to_master", "--no-notify",
        ])
        self.assertEqual(code, 1)

    def test_cli_check_heartbeat_stale_then_summary(self):
        code, out = self._run_cli([
            "check-heartbeat", "--batch", "B1", "--wave", "1", "--lane", "A",
            "--heartbeat-file", "reports/lane-heartbeat/不存在.md",
        ])
        self.assertEqual(code, 0)
        self.assertIn("🐕", out)

        code, out = self._run_cli(["summary", "--batch", "B1"])
        self.assertEqual(code, 0)
        self.assertIn("本批停 1 次", out)

    def test_cli_lan_status_effective_off_on_unknown_probe(self):
        self.module._load_lan_prober = lambda: (lambda: {"status": "unknown", "on_lan": None})
        code, out = self._run_cli(["lan-status"])
        self.assertEqual(code, 0)
        self.assertIn("探针不可用", out)
        self.assertIn("effective=off", out)

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
