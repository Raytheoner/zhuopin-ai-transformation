"""decision_reminder.py 单测（队列 #172）。

覆盖四类：新增检测 / 超期检测 / 去重（同一天不重复） / 静默期（1/3/7 天
递减升级节奏），以及贴合真实队列行文本结构的解析回归（§四"截止列判据"
——2026-07-31 对 #33-#40 八行逐行核证得出的真实结构）。

沿用本服务既有测试风格（本目录其余 test_*.py 均为纯函数式用例、不套
unittest.TestCase/pytest 类分组，见 `test_queue_git_sync.py` 等）。
"""
from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

from zhuopin_platform.audit import AuditLogger

from aibot_service.decision_reminder import (
    ESCALATION_INTERVALS_DAYS,
    ReminderItem,
    compute_overdue_section_four_ids,
    compute_stale_priority_pending_ids,
    default_state,
    evaluate_candidates,
    format_digest_message,
    parse_priority_pending_rows,
    parse_section_four_rows,
    send_decision_reminder,
)

SECTION_FOUR_SAMPLE = """\
## 四、需 Shao Peishen 的动作（例外与拍板）

| # | 事项 | 等谁 | 截止 |
|---|------|------|------|
| 33 | 已收口事项 | Paul | **✅ 已拍 2026-07-24：登记风险接受**——private 仓库，零成本留痕 |
| 35 | R1 Champion 指定 | Paul | **2026-08-31**（Paul 定，双前提①） |
| 38 | **✅ 已拍板：接受（选项 A）**——安全隐患①已收口，②本地口令如何处置仍需裁定 | Paul | 建议 2026-08-07 前给结论（原建议截止 8/1 已到期） |

## 五、占位
"""

SECTION_ONE_SAMPLE = """\
## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 171 | sweep 分叉静默告警 | CC | 输入 | 产出 | 待领（P1，建议尽早） | 工具-落库sweep.py | 07-30 |
| 180 | ⏳标记不自愈 | CC 平台 | 输入 | 产出 | 待领（P0，紧急） | queue_git_sync.py | 07-30 |
| 172 | 主动提醒机制 | CC 平台 | 输入 | 产出 | 待领（P2，建议与 #171 同批） | wecom-aibot-service | 07-30 |
| 11 | 月度记分牌 | Cowork 总线 | 输入 | 产出 | 待领（口径已备，可直接出） | — | 07-09 |
| 90 | 常驻监听迁移 | 待领 | 输入 | 产出 | 待领（前置 #59 未解锁前不可开工） | — | 07-23 |

## 二、占位
"""


def _combined() -> str:
    return SECTION_FOUR_SAMPLE + "\n" + SECTION_ONE_SAMPLE


# ── 解析：§四 ────────────────────────────────────────────────────────────


def test_section_four_closed_row_detected_via_check_mark_in_deadline_cell_only():
    rows = {r.row_id: r for r in parse_section_four_rows(SECTION_FOUR_SAMPLE)}
    assert rows["33"].is_closed is True


def test_section_four_open_row_with_future_full_date_parsed():
    rows = {r.row_id: r for r in parse_section_four_rows(SECTION_FOUR_SAMPLE)}
    assert rows["35"].is_closed is False
    assert rows["35"].deadline_date == date(2026, 8, 31)


def test_section_four_check_mark_only_in_item_cell_not_deadline_cell_stays_open():
    """真实活样本（队列 #38）：事项列开头带✅描述子问题①已收口，但截止列
    仍写"建议…前给结论"（子问题②待裁）——只看截止列本身，不该被整行的
    ✅ 误判为已关闭。"""
    rows = {r.row_id: r for r in parse_section_four_rows(SECTION_FOUR_SAMPLE)}
    assert "✅" in rows["38"].item_cell
    assert rows["38"].is_closed is False
    assert rows["38"].deadline_date == date(2026, 8, 7)


def test_section_four_malformed_row_column_count_is_skipped():
    malformed = (
        "## 四、需 Shao Peishen 的动作（例外与拍板）\n\n"
        "| # | 事项 | 等谁 | 截止 |\n|---|------|------|------|\n"
        "| 99 | 裸竖线切开的行 | 多出一列 | Paul | 07-31 |\n"
    )
    assert parse_section_four_rows(malformed) == []


# ── 超期：§四 ────────────────────────────────────────────────────────────


def test_overdue_closed_row_never_overdue_even_with_past_date():
    past_closed = (
        "## 四、需 Shao Peishen 的动作（例外与拍板）\n\n"
        "| # | 事项 | 等谁 | 截止 |\n|---|------|------|------|\n"
        "| 1 | 已解决 | Paul | ✅ 已拍板 2026-01-01：接受 |\n"
    )
    rows = parse_section_four_rows(past_closed)
    assert compute_overdue_section_four_ids(rows, date(2026, 7, 31)) == []


def test_overdue_open_row_with_past_date_is_overdue():
    rows = parse_section_four_rows(SECTION_FOUR_SAMPLE)
    overdue = compute_overdue_section_four_ids(rows, date(2026, 8, 10))
    assert "38" in overdue  # 截止 08-07，评估日 08-10，已过期
    assert "35" not in overdue  # 截止 08-31，尚未到


def test_overdue_open_row_without_parseable_date_never_flagged():
    no_date = (
        "## 四、需 Shao Peishen 的动作（例外与拍板）\n\n"
        "| # | 事项 | 等谁 | 截止 |\n|---|------|------|------|\n"
        "| 1 | 无法解析日期的开放行 | Paul | 尽快给结论 |\n"
    )
    rows = parse_section_four_rows(no_date)
    assert compute_overdue_section_four_ids(rows, date(2099, 1, 1)) == []


# ── 解析：§一 P0/P1 待领 ─────────────────────────────────────────────────


def test_priority_pending_only_p0_p1_tag_are_returned():
    rows = {r.row_id: r for r in parse_priority_pending_rows(SECTION_ONE_SAMPLE, date(2026, 7, 31))}
    assert set(rows) == {"171", "180"}
    assert rows["171"].priority == "P1"
    assert rows["180"].priority == "P0"


def test_priority_pending_p2_and_no_priority_rows_excluded():
    rows = {r.row_id: r for r in parse_priority_pending_rows(SECTION_ONE_SAMPLE, date(2026, 7, 31))}
    assert "172" not in rows  # P2 不在本机制范围（只管 P0/P1）
    assert "11" not in rows  # 无 P0/P1 标记
    assert "90" not in rows  # "待领" 出现在状态列括号说明里但无 P0/P1 标记


def test_priority_pending_registered_date_parsed_from_last_column():
    rows = {r.row_id: r for r in parse_priority_pending_rows(SECTION_ONE_SAMPLE, date(2026, 7, 31))}
    assert rows["171"].registered_date == date(2026, 7, 30)


def test_priority_pending_mmdd_rolls_back_a_year_when_later_than_today():
    future_lookalike = (
        "## 一、任务看板\n\n"
        "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|------|--------|-------------|----------|------|--------|------|\n"
        "| 1 | 跨年遗留行 | CC | 输入 | 产出 | 待领（P0，紧急） | — | 12-15 |\n"
    )
    rows = parse_priority_pending_rows(future_lookalike, date(2026, 1, 5))
    assert rows[0].registered_date == date(2025, 12, 15)


# ── 队列 #308 决策点 4：§一 状态列机器字段（改读字段，非静默降级）────────

MACHINE_FIELD_SECTION_ONE = (
    "## 一、任务看板\n\n"
    "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
    "|---|------|--------|-------------|----------|------|--------|------|\n"
    "| 171 | 真待领 | CC | 输入 | 产出 | [S:open][D:机] 待领（P1，建议尽早） | 工具 | 07-30 |\n"
    "| 172 | 在办中不再提醒 | CC | 输入 | 产出 | [S:partial][D:机] 待领（P1，说明：三步已完成两步） | 工具 | 07-30 |\n"
    "| 129 | 定时触发型不应误判（E1） | CC | 输入 | 产出 | [S:timed=2026-08-25][D:机] 待领（定时触发型） | 工具 | 07-30 |\n"
    "| 224 | 受外部阻塞不应误判 | CC | 输入 | 产出 | [S:blocked][D:业] 待领（P1，依赖签认） | 工具 | 07-30 |\n"
)


def test_machine_field_open_p1_row_included():
    rows = {r.row_id: r for r in parse_priority_pending_rows(MACHINE_FIELD_SECTION_ONE, date(2026, 7, 31))}
    assert "171" in rows
    assert rows["171"].priority == "P1"


def test_machine_field_partial_row_excluded_even_with_pending_text():
    """`partial`（在办中）不触发"待领"提醒——即便自然语言正文里仍带"待领"
    字样，已有人认领、正在推进不需要"这条无人认领"式提醒。"""
    rows = {r.row_id: r for r in parse_priority_pending_rows(MACHINE_FIELD_SECTION_ONE, date(2026, 7, 31))}
    assert "172" not in rows


def test_machine_field_timed_row_excluded_e1_resolved():
    """队列 #308 子项 E1：定时触发型只在自然语言里写了触发日期，旧的
    "待领"子串判据会误判为立即待领——机器字段落地后天然排除。"""
    rows = {r.row_id: r for r in parse_priority_pending_rows(MACHINE_FIELD_SECTION_ONE, date(2026, 7, 31))}
    assert "129" not in rows


def test_machine_field_blocked_row_excluded():
    rows = {r.row_id: r for r in parse_priority_pending_rows(MACHINE_FIELD_SECTION_ONE, date(2026, 7, 31))}
    assert "224" not in rows


def test_missing_field_emits_runtime_warning_and_degrades():
    import warnings
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        rows = {r.row_id: r for r in parse_priority_pending_rows(SECTION_ONE_SAMPLE, date(2026, 7, 31))}
    assert "171" in rows  # 回退旧判据仍能正确识别
    assert any(
        issubclass(w.category, RuntimeWarning) and "状态字段缺失" in str(w.message)
        for w in caught
    )


# ── 超龄：§一 P0/P1 待领 ─────────────────────────────────────────────────


def test_stale_priority_pending_below_threshold_not_stale():
    rows = parse_priority_pending_rows(SECTION_ONE_SAMPLE, date(2026, 7, 31))
    stale = compute_stale_priority_pending_ids(rows, date(2026, 7, 31), min_age_days=3)
    assert stale == []  # 07-30 登记，07-31 评估，仅 1 天


def test_stale_priority_pending_at_or_above_threshold_is_stale():
    rows = parse_priority_pending_rows(SECTION_ONE_SAMPLE, date(2026, 8, 2))
    stale = compute_stale_priority_pending_ids(rows, date(2026, 8, 2), min_age_days=3)
    assert set(stale) == {"171", "180"}  # 07-30 登记，08-02 评估，满 3 天


# ── evaluate_candidates：新增检测 ────────────────────────────────────────


def test_evaluate_first_run_flags_all_open_and_priority_rows_as_new():
    items, new_state = evaluate_candidates(_combined(), date(2026, 7, 31), default_state())
    keys = {i.key for i in items}
    assert keys == {"§四#35", "§四#38", "§一#171", "§一#180"}
    for item in items:
        assert item.reason.startswith("新增")
    assert set(new_state["seen_section_four_ids"]) == {"35", "38"}
    assert set(new_state["seen_priority_pending_ids"]) == {"171", "180"}


def test_evaluate_closed_section_four_row_never_becomes_candidate():
    items, _ = evaluate_candidates(_combined(), date(2026, 7, 31), default_state())
    assert all(i.row_id != "33" for i in items)


def test_evaluate_seen_row_that_is_neither_new_nor_overdue_is_silent():
    # 模拟"上一轮已见过、且本轮既非新增也未超期/未超龄"——不应重复提醒。
    state = default_state()
    state["seen_section_four_ids"] = ["35", "38"]
    state["seen_priority_pending_ids"] = ["171", "180"]
    state["escalation"] = {
        "§四#35": {"first_flagged_at": "2026-07-25", "alert_count": 1, "last_alerted_at": "2026-07-25"},
    }
    items, _ = evaluate_candidates(_combined(), date(2026, 7, 31), state)
    # #35 截止 08-31 尚未过期、已见过——不应出现；#38 已见过但尚未过 08-07
    # 截止（评估日 07-31）——同样不应出现；#171/#180 已见过且刚登记 1 天
    # （< 3 天阈值）未超龄——不应出现。
    assert items == []


# ── evaluate_candidates：超期 + 去重（同一天）+ 静默期（1/3/7 天升级）────


def test_evaluate_overdue_row_flagged_even_if_already_seen():
    state = default_state()
    state["seen_section_four_ids"] = ["38"]
    items, _ = evaluate_candidates(SECTION_FOUR_SAMPLE, date(2026, 8, 10), state)
    matched = [i for i in items if i.key == "§四#38"]
    assert len(matched) == 1
    assert matched[0].reason == "已过截止"


def test_evaluate_same_day_second_call_does_not_repeat_alert():
    """红线核心：同一天内两次调用（如巡逻+同日手动重跑）不得重复提醒。"""
    state = default_state()
    items1, state1 = evaluate_candidates(_combined(), date(2026, 7, 31), state)
    assert len(items1) == 4

    items2, _state2 = evaluate_candidates(_combined(), date(2026, 7, 31), state1)
    assert items2 == [], "同一天内重复评估不应再次提醒（silence 核心红线）"


def test_evaluate_escalation_follows_1_3_7_day_decreasing_schedule():
    """完整多日序列验证 1/3/7 天递减升级节奏。"""
    assert ESCALATION_INTERVALS_DAYS == (0, 3, 7)

    overdue_only = (
        "## 四、需 Shao Peishen 的动作（例外与拍板）\n\n"
        "| # | 事项 | 等谁 | 截止 |\n|---|------|------|------|\n"
        "| 1 | 持续超期项 | Paul | 2026-07-01 |\n"
    )
    s = default_state()
    # Day 0：首次发现即已超期（截止 07-01 早于评估日 07-05），立即提醒 alert #1。
    items, s = evaluate_candidates(overdue_only, date(2026, 7, 5), s)
    assert len(items) == 1 and s["escalation"]["§四#1"]["alert_count"] == 1

    # Day+1（07-06，距上次 1 天）：未到第 2 档间隔（需 >=3），静默。
    items, s = evaluate_candidates(overdue_only, date(2026, 7, 6), s)
    assert items == []

    # Day+3（07-08，距上次 3 天）：第 2 档到期，提醒 alert #2。
    items, s = evaluate_candidates(overdue_only, date(2026, 7, 8), s)
    assert len(items) == 1 and s["escalation"]["§四#1"]["alert_count"] == 2

    # Day+3+2（07-10，距上次 2 天 < 7）：第 3 档未到，静默。
    items, s = evaluate_candidates(overdue_only, date(2026, 7, 10), s)
    assert items == []

    # Day+3+7（07-15，距上次 7 天）：第 3 档到期，提醒 alert #3。
    items, s = evaluate_candidates(overdue_only, date(2026, 7, 15), s)
    assert len(items) == 1 and s["escalation"]["§四#1"]["alert_count"] == 3

    # 之后固定每 >=7 天一次：07-21（距上次 6 天）静默，07-22（7 天）到期。
    items, s = evaluate_candidates(overdue_only, date(2026, 7, 21), s)
    assert items == []
    items, s = evaluate_candidates(overdue_only, date(2026, 7, 22), s)
    assert len(items) == 1 and s["escalation"]["§四#1"]["alert_count"] == 4


def test_evaluate_resolved_item_prunes_escalation_state():
    overdue_only = (
        "## 四、需 Shao Peishen 的动作（例外与拍板）\n\n"
        "| # | 事项 | 等谁 | 截止 |\n|---|------|------|------|\n"
        "| 1 | 曾经超期项 | Paul | 2026-07-01 |\n"
    )
    resolved = (
        "## 四、需 Shao Peishen 的动作（例外与拍板）\n\n"
        "| # | 事项 | 等谁 | 截止 |\n|---|------|------|------|\n"
        "| 1 | 曾经超期项 | Paul | ✅ 已拍板 2026-07-08：接受 |\n"
    )
    state = default_state()
    _, state = evaluate_candidates(overdue_only, date(2026, 7, 5), state)
    assert "§四#1" in state["escalation"]

    _, state = evaluate_candidates(resolved, date(2026, 7, 9), state)
    assert "§四#1" not in state["escalation"], "已关闭的行应清掉陈旧升级状态，防止未来重开时误判间隔"


# ── format_digest_message ────────────────────────────────────────────────


def test_format_digest_message_empty_list_returns_none():
    assert format_digest_message([]) is None


def test_format_digest_message_non_empty_list_includes_reason_and_summary():
    items = [ReminderItem(key="§四#38", section="§四", row_id="38", reason="已过截止", summary="安全隐患②待裁")]
    text = format_digest_message(items)
    assert text is not None
    assert "§四#38" in text
    assert "已过截止" in text
    assert "安全隐患②待裁" in text


# ── send_decision_reminder：主通道/兜底（形状仿 gap_alert 同款测试）───────


class _FakeConnector:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[tuple[str, str]] = []

    async def send_markdown(self, recipient: str, text: str) -> None:
        self.calls.append((recipient, text))
        if self.should_fail:
            raise RuntimeError("WebSocket not connected, unable to send data")


def _actions(audit: AuditLogger) -> list[str]:
    return [r["action"] for r in audit.query_by(scenario="wecom-aibot")]


def test_send_decision_reminder_primary_success_records_sent(tmp_path: Path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = _FakeConnector(should_fail=False)

    asyncio.run(send_decision_reminder(connector, audit, "📌 队列有 1 项需要你留意", "ShaoPeiShen"))

    assert connector.calls == [("ShaoPeiShen", "📌 队列有 1 项需要你留意")]
    assert _actions(audit) == ["decision_reminder_sent"]


def test_send_decision_reminder_falls_back_to_webhook_on_primary_failure(tmp_path: Path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = _FakeConnector(should_fail=True)
    fallback_calls: list[str] = []

    asyncio.run(send_decision_reminder(
        connector, audit, "📌 队列有 1 项需要你留意", "ShaoPeiShen",
        fallback_send=fallback_calls.append,
    ))

    assert fallback_calls == ["📌 队列有 1 项需要你留意"]
    assert _actions(audit) == ["decision_reminder_send_failed", "decision_reminder_fallback_sent"]


def test_send_decision_reminder_fallback_failure_does_not_raise(tmp_path: Path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = _FakeConnector(should_fail=True)

    def failing_fallback(text: str) -> None:
        raise RuntimeError("webhook 也挂了")

    asyncio.run(send_decision_reminder(
        connector, audit, "📌 队列有 1 项需要你留意", "ShaoPeiShen", fallback_send=failing_fallback,
    ))

    assert _actions(audit) == ["decision_reminder_send_failed", "decision_reminder_fallback_failed"]


def test_send_decision_reminder_no_fallback_configured_only_logs_failure(tmp_path: Path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = _FakeConnector(should_fail=True)

    asyncio.run(send_decision_reminder(
        connector, audit, "📌 队列有 1 项需要你留意", "ShaoPeiShen", fallback_send=None,
    ))

    assert _actions(audit) == ["decision_reminder_send_failed"]
