from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zhuopin_platform.audit import AuditEvent, AuditLogger

from aibot_service.queue_reconcile_sentinel import (
    build_reconciliation_report,
    find_unreconciled_archives,
    run_reconciliation_sentinel,
    _collect_reconciliation_text,
)

QUEUE_TEXT = """\
## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 69 | 企微反馈归档拆件：tangyanping 07-21 回复 docx | 财务专线 | \
`7-外部文档/财务部/财务部-tangyanping-回复-2026-07-21-abc123.docx` | 拆件回灌 | 待领 | — | 07-22 |
"""


def _archived_event(ts: str, filename: str, sender: str = "tangyanping") -> dict:
    return {
        "scenario": "wecom-aibot",
        "action": "archived",
        "timestamp": ts,
        "decision": {
            "department": "财务部",
            "matched": True,
            "archived_path": f"C:\\repo\\7-外部文档\\财务部\\{filename}",
        },
        "data_sources": {"sender": sender, "msgtype": "file"},
    }


def _queue_appended_event(ts: str, owner: str = "财务专线") -> dict:
    return {
        "scenario": "wecom-aibot",
        "action": "queue_appended",
        "timestamp": ts,
        "decision": {"owner": owner},
        "data_sources": {"queue_path": "C:\\repo\\1-转型规划\\0-全景路线图\\跨桌任务队列.md"},
    }


def _queue_append_pending_flushed_event(ts: str, sender: str = "YaoZuYi") -> dict:
    return {
        "scenario": "wecom-aibot",
        "action": "queue_append_pending_flushed",
        "timestamp": ts,
        "decision": {"recorded_at": ts},
        "data_sources": {"sender": sender},
    }


# ── 判据核心：审计日志内部配对（队列 #107）────────────────────────────────
#
# intake.py::archive_inbound_message 对每条消息总是先记一条 "archived"、
# 随后立刻记一条 "queue_appended"（全库唯一 emitter）——本节验证 FIFO 配对
# 本身，不依赖队列文件文本。

def test_find_unreconciled_archives_paired_event_is_reconciled():
    now = datetime(2026, 7, 22, 6, 0, tzinfo=timezone.utc)
    events = [
        _archived_event("2026-07-21T01:19:13+00:00", "abc123.docx"),
        _queue_appended_event("2026-07-21T01:19:14+00:00"),
    ]
    assert find_unreconciled_archives(events, now=now) == []


def test_find_unreconciled_archives_unpaired_event_is_flagged():
    """2026-07-21 唐燕萍那条归档的真实事故场景——archived 记录成功，但
    append_pending_task 最终抛错（重试耗尽），队列里没有配对的 queue_appended
    事件。"""
    now = datetime(2026, 7, 22, 6, 0, tzinfo=timezone.utc)
    events = [_archived_event("2026-07-21T01:19:13+00:00", "neverappeared.docx")]
    result = find_unreconciled_archives(events, now=now)
    assert len(result) == 1
    assert result[0]["decision"]["archived_path"].endswith("neverappeared.docx")


def test_find_unreconciled_archives_core_regression_paired_event_not_flagged_even_when_filename_missing_everywhere():
    """队列 #107 核心场景（本案即队列 #99 首次清扫后 10 条历史误报的复现）：
    文件名已被值周巡检整行迁出队列正文/归档件——旧判据（子串匹配）在此场景
    下必定误报；新判据只看审计日志里 archived 是否配对到 queue_appended，
    与文件名此刻躺在哪、叫什么全部无关，因此不受清扫影响。`queue_text=""`
    模拟"文件名在队列文本的任何地方都找不到"这一最坏情形，验证配对判据
    本身足以给出正确结论，不依赖文本兜底。"""
    now = datetime(2026, 7, 26, 6, 0, tzinfo=timezone.utc)
    events = [
        _archived_event("2026-07-21T01:19:13+00:00", "已被清扫迁出正文的-abc123.docx"),
        _queue_appended_event("2026-07-21T01:19:14+00:00"),
    ]
    assert find_unreconciled_archives(events, now=now, queue_text="") == []


def test_find_unreconciled_archives_multiple_messages_pair_independently_in_order():
    """真实生产序列（`on_message` 逐条 await 顺序处理，同一时刻至多一条
    消息"在途"）：b 的 queue_appended 缺失后，处理立刻推进到下一条消息 c
    （b 的异常已被 connection.py 捕获吞掉，不阻塞后续消息）——即审计日志
    实际形状是 archived_a, queue_appended_a, archived_b, archived_c,
    queue_appended_c。若用朴素 FIFO 队列配对，c 的 queue_appended 会错配
    给"队首"的 b、导致真正漏行的 b 被判定为已配对、反而误报本该没问题的
    c——这正是本判据必须用"单件在途"而非普通 FIFO 队列的原因（见函数
    docstring）。"""
    now = datetime(2026, 7, 26, 6, 0, tzinfo=timezone.utc)
    events = [
        _archived_event("2026-07-21T01:00:00+00:00", "a-ok.docx"),
        _queue_appended_event("2026-07-21T01:00:01+00:00"),
        _archived_event("2026-07-21T02:00:00+00:00", "b-lost.docx"),
        # b 的 queue_appended 缺失（append_pending_task 抛错），处理推进到 c
        _archived_event("2026-07-21T03:00:00+00:00", "c-ok.docx"),
        _queue_appended_event("2026-07-21T03:00:01+00:00"),
    ]
    result = find_unreconciled_archives(events, now=now)
    assert len(result) == 1
    assert result[0]["decision"]["archived_path"].endswith("b-lost.docx")


def test_find_unreconciled_archives_ignores_events_older_than_within_days():
    now = datetime(2026, 7, 22, 6, 0, tzinfo=timezone.utc)
    stale = _archived_event(
        (now - timedelta(days=10)).isoformat(), "old-neverappeared-too.docx",
    )
    assert find_unreconciled_archives([stale], now=now, within_days=7) == []


def test_find_unreconciled_archives_ignores_missing_or_bad_timestamp():
    now = datetime(2026, 7, 22, 6, 0, tzinfo=timezone.utc)
    no_ts = {"action": "archived", "decision": {"archived_path": "C:\\x\\neverappeared.docx"}, "data_sources": {}}
    bad_ts = {
        "action": "archived", "timestamp": "not-a-date",
        "decision": {"archived_path": "C:\\x\\neverappeared.docx"}, "data_sources": {},
    }
    assert find_unreconciled_archives([no_ts, bad_ts], now=now) == []


def test_find_unreconciled_archives_ignores_missing_archived_path():
    now = datetime(2026, 7, 22, 6, 0, tzinfo=timezone.utc)
    event = {"action": "archived", "timestamp": now.isoformat(), "decision": {}, "data_sources": {}}
    assert find_unreconciled_archives([event], now=now) == []


def test_find_unreconciled_archives_sorted_by_timestamp_ascending():
    now = datetime(2026, 7, 22, 6, 0, tzinfo=timezone.utc)
    later = _archived_event("2026-07-21T10:00:00+00:00", "b-neverappeared.docx")
    earlier = _archived_event("2026-07-21T01:00:00+00:00", "a-neverappeared.docx")
    result = find_unreconciled_archives([later, earlier], now=now)
    assert [r["timestamp"] for r in result] == [
        "2026-07-21T01:00:00+00:00", "2026-07-21T10:00:00+00:00",
    ]


def test_find_unreconciled_archives_ignores_unrelated_actions_interleaved():
    """归档流程之外还会穿插很多其它 action（连接生命周期/群通报/转发等）——
    这些必须被忽略，不得干扰配对计数。"""
    now = datetime(2026, 7, 22, 6, 0, tzinfo=timezone.utc)
    events = [
        {"scenario": "wecom-aibot", "action": "connection_established", "timestamp": "2026-07-21T00:00:00+00:00"},
        _archived_event("2026-07-21T01:00:00+00:00", "ok.docx"),
        {"scenario": "wecom-aibot", "action": "group_notify_sent", "timestamp": "2026-07-21T01:00:00+00:00"},
        _queue_appended_event("2026-07-21T01:00:01+00:00"),
        {"scenario": "wecom-aibot", "action": "forward_delivered", "timestamp": "2026-07-21T01:00:02+00:00"},
    ]
    assert find_unreconciled_archives(events, now=now) == []


# ── 队列 #192-B：锁忙推迟→补录成功的配对不变式 ─────────────────────────────
#
# queue_lock_pending.py 补录成功时记的是 queue_append_pending_flushed，不是
# queue_appended——修复前只认后者，导致这类消息被误判"未配对"（当日 9 个
# archived vs 8 个 queue_appended，差的正是被补录的那条），只是恰好被
# queue_text 二级交叉校验兜住、未造成误报。

def test_find_unreconciled_archives_deferred_then_flushed_is_reconciled():
    """真实场景（队列 #192 行内记录）：13:04 姚祖怡回件因编辑锁占用被推迟
    （archived 已记，queue_appended 因锁忙未记），17:06 唐燕萍新消息到达
    触发补录成功（记 queue_append_pending_flushed）——应视为已配对，不应
    被判定为漏行。"""
    now = datetime(2026, 7, 31, 18, 0, tzinfo=timezone.utc)
    events = [
        _archived_event("2026-07-31T13:04:31+00:00", "姚祖怡回件.docx", sender="YaoZuYi"),
        _queue_append_pending_flushed_event("2026-07-31T17:06:56+00:00", sender="YaoZuYi"),
    ]
    assert find_unreconciled_archives(events, now=now) == []


def test_find_unreconciled_archives_deferred_flush_does_not_swallow_next_genuine_gap():
    """补录事件只清空它对应的那一个 pending，不应把后续真实漏行也一并
    误判为已配对——同一"单件在途"配对逻辑，只是新增一种能清空 pending 的
    事件类型，不改变整体判定结构。"""
    now = datetime(2026, 7, 31, 18, 0, tzinfo=timezone.utc)
    events = [
        _archived_event("2026-07-31T13:04:31+00:00", "姚祖怡回件.docx", sender="YaoZuYi"),
        _queue_append_pending_flushed_event("2026-07-31T17:06:56+00:00", sender="YaoZuYi"),
        _archived_event("2026-07-31T18:00:00+00:00", "后续真实漏行.docx"),
    ]
    result = find_unreconciled_archives(events, now=now)
    assert len(result) == 1
    assert result[0]["decision"]["archived_path"].endswith("后续真实漏行.docx")


def test_run_reconciliation_sentinel_deferred_then_flushed_sends_nothing(tmp_path: Path):
    """端到端：推迟补录成功场景下，哨兵不应发送任何疑似漏行私信。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    audit.record(AuditEvent(
        scenario="wecom-aibot", action="archived", evaluator="system", automation_level="L1",
        decision={"archived_path": "C:\\repo\\7-外部文档\\采购部\\姚祖怡回件.docx"},
        data_sources={"sender": "YaoZuYi"},
    ))
    audit.record(AuditEvent(
        scenario="wecom-aibot", action="queue_append_pending_flushed", evaluator="system",
        automation_level="L1", decision={"recorded_at": "2026-07-31T17:06:56+00:00"},
        data_sources={"sender": "YaoZuYi"},
    ))
    queue_path = tmp_path / "queue.md"
    queue_path.write_text("队列正文里完全没有这个文件名", encoding="utf-8")
    connector = _FakeConnector()

    asyncio.run(run_reconciliation_sentinel(
        connector, audit, queue_path, "ShaoPeiShen", now=datetime.now(timezone.utc)
    ))

    assert connector.calls == []
    assert _actions(audit) == []


# ── 二级交叉校验兜底（queue_text 可选参数）─────────────────────────────────
#
# 队列 #107 备注"兜底可保留扫现役+归档件作二次校验"——用于覆盖 FIFO 配对
# 本身理论上可能漏配的边界情形，不应掩盖真实漏行。

def test_find_unreconciled_archives_queue_text_rescues_unpaired_event_found_in_text():
    now = datetime(2026, 7, 22, 6, 0, tzinfo=timezone.utc)
    events = [_archived_event("2026-07-21T01:19:13+00:00", "abc123.docx")]  # 无配对
    assert find_unreconciled_archives(events, now=now, queue_text=QUEUE_TEXT) == []


def test_find_unreconciled_archives_queue_text_does_not_rescue_genuine_gap():
    now = datetime(2026, 7, 22, 6, 0, tzinfo=timezone.utc)
    events = [_archived_event("2026-07-21T01:19:13+00:00", "trulylost.docx")]  # 无配对
    result = find_unreconciled_archives(events, now=now, queue_text=QUEUE_TEXT)
    assert len(result) == 1
    assert result[0]["decision"]["archived_path"].endswith("trulylost.docx")


def test_find_unreconciled_archives_without_queue_text_param_skips_cross_check():
    """不传 `queue_text`（默认 None）时纯以配对结果为准，即便文件名其实
    躺在某处也不做交叉校验——用于单元测试只关心配对逻辑本身的场景。"""
    now = datetime(2026, 7, 22, 6, 0, tzinfo=timezone.utc)
    events = [_archived_event("2026-07-21T01:19:13+00:00", "abc123.docx")]  # 无配对
    result = find_unreconciled_archives(events, now=now)
    assert len(result) == 1


# ── build_reconciliation_report（无变化，判据切换不影响报告格式）─────────

def test_build_reconciliation_report_empty_returns_none():
    assert build_reconciliation_report([]) is None


def test_build_reconciliation_report_lists_all_entries_in_one_message():
    """告警汇总一条、不逐行发（队列 #70 要求 c）——一次 build 调用产出一条
    包含全部疑似漏行的汇总文本，不是每条各自一条消息。"""
    events = [
        _archived_event("2026-07-21T01:00:00+00:00", "a-neverappeared.docx", sender="tangyanping"),
        _archived_event("2026-07-21T02:00:00+00:00", "b-neverappeared.docx", sender="YaoZuYi"),
    ]
    report = build_reconciliation_report(events)
    assert report is not None
    assert report.count("\n") >= 2  # 标题行 + 至少两条明细行
    assert "a-neverappeared.docx" in report
    assert "b-neverappeared.docx" in report
    assert "tangyanping" in report and "YaoZuYi" in report
    assert "2 条疑似漏行" in report
    assert "不会自动写队列" in report


# ── _collect_reconciliation_text（无变化，仍供 run_reconciliation_sentinel
#    的二级交叉校验使用）───────────────────────────────────────────────────

ARCHIVE_TEXT = """\
| 21 | 企微反馈自动归档：tangyanping 07-05 回复 docx | 财务专线 | \
`7-外部文档/财务部/财务部-tangyanping-回复-2026-07-05-migrated.docx` | 已归档 | 07-05 |
"""


def test_collect_reconciliation_text_includes_matching_archive_files(tmp_path: Path):
    queue_path = tmp_path / "跨桌任务队列.md"
    queue_path.write_text(QUEUE_TEXT, encoding="utf-8")
    (tmp_path / "跨桌任务队列-归档-202607.md").write_text(ARCHIVE_TEXT, encoding="utf-8")

    combined = _collect_reconciliation_text(queue_path)
    assert "migrated.docx" in combined
    assert "abc123.docx" in combined  # 正文内容仍在


def test_collect_reconciliation_text_ignores_non_matching_filenames(tmp_path: Path):
    """同目录里其他归档件（如 session 接力归档）命名律不同，不应被当成
    跨桌任务队列的归档件纳入扫描——即便凑巧同名子串也不该误配，这里用
    完全不相关内容验证不会被纳入。"""
    queue_path = tmp_path / "跨桌任务队列.md"
    queue_path.write_text(QUEUE_TEXT, encoding="utf-8")
    (tmp_path / "session接力-归档-202607.md").write_text(
        "无关内容，不应被扫描-should-not-appear.docx", encoding="utf-8"
    )

    combined = _collect_reconciliation_text(queue_path)
    assert "should-not-appear.docx" not in combined


def test_collect_reconciliation_text_missing_queue_file_still_scans_archives(tmp_path: Path):
    queue_path = tmp_path / "跨桌任务队列.md"
    (tmp_path / "跨桌任务队列-归档-202607.md").write_text(ARCHIVE_TEXT, encoding="utf-8")

    combined = _collect_reconciliation_text(queue_path)
    assert "migrated.docx" in combined


# ── run_reconciliation_sentinel 端到端（新判据接线）────────────────────────

class _FakeConnector:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[tuple[str, str]] = []

    async def send_markdown(self, recipient: str, text: str) -> None:
        self.calls.append((recipient, text))
        if self.should_fail:
            raise RuntimeError("WebSocket not connected, unable to send data")


def _actions(audit: AuditLogger) -> list[str]:
    return [r["action"] for r in audit.query_by(scenario="wecom-aibot") if r["action"].startswith("reconcile_sentinel")]


def test_run_reconciliation_sentinel_no_gap_sends_nothing(tmp_path: Path):
    """真实生产形状：archived 与 queue_appended 成对记录——配对判据下不应
    误报，即便队列正文/归档件里完全找不到这个文件名（清扫后的常态）。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    audit.record(AuditEvent(
        scenario="wecom-aibot", action="archived", evaluator="system", automation_level="L1",
        decision={"archived_path": "C:\\repo\\7-外部文档\\财务部\\财务部-tangyanping-回复-2026-07-21-abc123.docx"},
        data_sources={"sender": "tangyanping"},
    ))
    audit.record(AuditEvent(
        scenario="wecom-aibot", action="queue_appended", evaluator="system", automation_level="L1",
        decision={"owner": "财务专线"}, data_sources={"queue_path": "x"},
    ))
    queue_path = tmp_path / "queue.md"
    queue_path.write_text("队列正文里完全没有这个文件名", encoding="utf-8")
    connector = _FakeConnector()

    asyncio.run(run_reconciliation_sentinel(
        connector, audit, queue_path, "ShaoPeiShen", now=datetime.now(timezone.utc)
    ))

    assert connector.calls == []
    assert _actions(audit) == []


def test_run_reconciliation_sentinel_gap_found_sends_one_summary_message(tmp_path: Path):
    """archived 后 append_pending_task 抛错（无配对的 queue_appended），
    队列文本/归档件里也确实找不到——真实漏行，应发送汇总私信。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    audit.record(AuditEvent(
        scenario="wecom-aibot", action="archived", evaluator="system", automation_level="L1",
        decision={"archived_path": "C:\\repo\\7-外部文档\\财务部\\财务部-tangyanping-回复-2026-07-21-lost.docx"},
        data_sources={"sender": "tangyanping"},
    ))
    queue_path = tmp_path / "queue.md"
    queue_path.write_text(QUEUE_TEXT, encoding="utf-8")
    connector = _FakeConnector()

    asyncio.run(run_reconciliation_sentinel(
        connector, audit, queue_path, "ShaoPeiShen", now=datetime.now(timezone.utc)
    ))

    assert len(connector.calls) == 1
    recipient, text = connector.calls[0]
    assert recipient == "ShaoPeiShen"
    assert "lost.docx" in text
    assert _actions(audit) == ["reconcile_sentinel_report_sent"]


def test_run_reconciliation_sentinel_send_failure_is_audited_not_raised(tmp_path: Path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    audit.record(AuditEvent(
        scenario="wecom-aibot", action="archived", evaluator="system", automation_level="L1",
        decision={"archived_path": "C:\\repo\\7-外部文档\\财务部\\财务部-tangyanping-回复-2026-07-21-lost.docx"},
        data_sources={"sender": "tangyanping"},
    ))
    queue_path = tmp_path / "queue.md"
    queue_path.write_text(QUEUE_TEXT, encoding="utf-8")
    connector = _FakeConnector(should_fail=True)

    asyncio.run(run_reconciliation_sentinel(
        connector, audit, queue_path, "ShaoPeiShen", now=datetime.now(timezone.utc)
    ))

    assert _actions(audit) == ["reconcile_sentinel_send_failed"]


def test_run_reconciliation_sentinel_missing_queue_file_treated_as_empty(tmp_path: Path):
    """队列文件路径不存在（极端场景，如配置错误）——按空文本处理，不应因
    文件不存在而抛异常崩溃整个服务；真实漏行（无配对）仍应被正确上报。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    audit.record(AuditEvent(
        scenario="wecom-aibot", action="archived", evaluator="system", automation_level="L1",
        decision={"archived_path": "C:\\repo\\7-外部文档\\财务部\\财务部-x-回复-2026-07-21-y.docx"},
        data_sources={"sender": "tangyanping"},
    ))
    connector = _FakeConnector()

    asyncio.run(run_reconciliation_sentinel(
        connector, audit, tmp_path / "does-not-exist.md", "ShaoPeiShen", now=datetime.now(timezone.utc)
    ))

    assert len(connector.calls) == 1


# ── 队列 #99 清扫场景 · 队列 #107 回归基准（历史 10 条假阳性复现）─────────

def test_run_reconciliation_sentinel_after_sweep_paired_row_no_false_positive(tmp_path: Path):
    """队列 #107 的确切历史场景：值周巡检把已完成行整行迁出队列正文、搬进
    同目录《跨桌任务队列-归档-YYYYMM.md》——文件名因此在现役正文里找不到。
    旧判据（子串匹配）曾在这一场景下一次性产生 10 条假阳性私信；新判据下
    只要 archived/queue_appended 在审计日志里正确配对（本场景即是），完全
    不受"文件名此刻躺在哪"影响，不会误报。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    audit.record(AuditEvent(
        scenario="wecom-aibot", action="archived", evaluator="system", automation_level="L1",
        decision={"archived_path": "C:\\repo\\7-外部文档\\财务部\\财务部-tangyanping-回复-2026-07-21-abc123.docx"},
        data_sources={"sender": "tangyanping"},
    ))
    audit.record(AuditEvent(
        scenario="wecom-aibot", action="queue_appended", evaluator="system", automation_level="L1",
        decision={"owner": "财务专线"}, data_sources={"queue_path": "x"},
    ))
    queue_path = tmp_path / "跨桌任务队列.md"
    # 正文里已不含该行（已被清扫搬走），只剩一条无关行；归档件里也没有——
    # 完全模拟"文件名在队列文本任何地方都找不到"的最坏情形。
    queue_path.write_text(
        "## 一、任务看板\n\n"
        "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|------|--------|-------------|----------|------|--------|------|\n"
        "| 99 | 无关任务 | CC | p | e | 待领 | — | 07-24 |\n",
        encoding="utf-8",
    )
    connector = _FakeConnector()

    asyncio.run(run_reconciliation_sentinel(
        connector, audit, queue_path, "ShaoPeiShen", now=datetime.now(timezone.utc)
    ))

    assert connector.calls == []
    assert _actions(audit) == []


def test_run_reconciliation_sentinel_after_sweep_genuine_gap_still_flagged(tmp_path: Path):
    """清扫场景下的对照组：archived 无配对的 queue_appended（真实漏行），
    文件名也确实不在正文/归档件任何地方——应正确识别，证明判据切换没有
    把哨兵变成"什么都不报"的哑摆设。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    audit.record(AuditEvent(
        scenario="wecom-aibot", action="archived", evaluator="system", automation_level="L1",
        decision={"archived_path": "C:\\repo\\7-外部文档\\财务部\\财务部-tangyanping-回复-2026-07-25-trulylost.docx"},
        data_sources={"sender": "tangyanping"},
    ))
    queue_path = tmp_path / "跨桌任务队列.md"
    queue_path.write_text(QUEUE_TEXT, encoding="utf-8")
    (tmp_path / "跨桌任务队列-归档-202607.md").write_text(ARCHIVE_TEXT, encoding="utf-8")
    connector = _FakeConnector()

    asyncio.run(run_reconciliation_sentinel(
        connector, audit, queue_path, "ShaoPeiShen", now=datetime.now(timezone.utc)
    ))

    assert len(connector.calls) == 1
    assert "trulylost.docx" in connector.calls[0][1]


# ── 队列 #416 ⑺：「Shao Peishen 本人入站」不得被报成漏行 ──────────────────
#
# 2026-08-24 已拍板「本人入站不建行（归档保留）」并为此**专门新增**了
# `queue_append_skipped` 字段，而哨兵这一侧从未读过它 ⇒ 他每自己发一条
# 消息，哨兵就报一条永远修不掉的疑似漏行。素材＝2026-08-26 20:18 群内实例
# （审计 `2026-08-26T04:35:09Z`，归档件
# `待分拣-ShaoPeiShen-回复-2026-08-26-文本反馈-565bedf4…`）。
#
# 🔴 这是「恒真判据、零信息量」族：一个永远红着的告警等于把整条哨兵训练
# 成噪音——它比漏报更贵，因为它同时废掉了所有真报。

from pathlib import PurePath  # noqa: E402

from aibot_service.constants import PAUL_USERID  # noqa: E402
from aibot_service.forwarding import should_forward  # noqa: E402
from aibot_service.frame_parsing import InboundMessage  # noqa: E402
from aibot_service.queue_reconcile_sentinel import (  # noqa: E402
    PENDING_CLEARING_ACTIONS,
)

REAL_SELF_INBOUND = "待分拣-ShaoPeiShen-回复-2026-08-26-文本反馈-565bedf4ab8e3fc9ba186206ce0b7b4a.md"


def _queue_append_skipped_event(ts: str, sender: str = PAUL_USERID) -> dict:
    return {
        "scenario": "wecom-aibot",
        "action": "queue_append_skipped",
        "timestamp": ts,
        "decision": {"reason": "sender_is_paul", "owner": "Paul"},
        "data_sources": {"sender": sender, "queue_path": r"C:\repo\queue.md"},
    }


def test_self_inbound_archive_is_not_reported_as_missing_row():
    """2026-08-26 20:18 群内那条误报的直接复现——对旧实现必定变红。"""
    now = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
    events = [
        _archived_event("2026-08-26T04:35:09+00:00", REAL_SELF_INBOUND, sender=PAUL_USERID),
        _queue_append_skipped_event("2026-08-26T04:35:09+00:00"),
    ]
    assert find_unreconciled_archives(events, now=now) == []


def test_self_inbound_not_reported_even_if_skipped_event_is_missing():
    """第二道（判据同源）：`intake` 万一在记那条事件之前就抛了，本人入站
    也不得变回一条恒真告警——发送人这一条判据自己就认得他。"""
    now = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
    events = [_archived_event("2026-08-26T04:35:09+00:00", REAL_SELF_INBOUND,
                              sender=PAUL_USERID)]
    assert find_unreconciled_archives(events, now=now) == []


def test_real_missing_row_from_a_specialist_still_reported():
    """🔴 护栏：⑺ 的修法**不得**顺手把真漏行也一起消音。"""
    now = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
    events = [_archived_event("2026-08-26T04:35:09+00:00", "neverappeared.docx",
                              sender="tangyanping")]
    result = find_unreconciled_archives(events, now=now)
    assert len(result) == 1


def test_skipped_event_clears_pending_without_swallowing_the_next_archive():
    """`queue_append_skipped` 只清掉它自己那一条，后面专员的真漏行照报。"""
    now = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
    events = [
        _archived_event("2026-08-26T04:35:09+00:00", REAL_SELF_INBOUND, sender=PAUL_USERID),
        _queue_append_skipped_event("2026-08-26T04:35:09+00:00"),
        _archived_event("2026-08-26T05:00:00+00:00", "lost.docx", sender="tangyanping"),
    ]
    result = find_unreconciled_archives(events, now=now)
    assert [PurePath(e["decision"]["archived_path"]).name for e in result] == ["lost.docx"]


def test_skipped_action_is_registered_in_the_clearing_set():
    assert "queue_append_skipped" in PENDING_CLEARING_ACTIONS


def test_sentinel_criterion_is_same_source_as_should_forward():
    """拍板原文要求「判据与 `forwarding.should_forward` 同源」——两侧对同一个
    发送人必须给出同一个结论，不是各写一份 `== PAUL_USERID`。"""
    for sender, forwards in (("tangyanping", True), (PAUL_USERID, False)):
        msg = InboundMessage(sender=sender, msgtype="text", text_content="x")
        assert should_forward(msg) is forwards
        events = [_archived_event("2026-08-26T04:35:09+00:00", "x.md", sender=sender)]
        reported = bool(find_unreconciled_archives(
            events, now=datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)))
        # 转发得出去的人 ⇒ 该建行 ⇒ 缺行要报；转发不出去的人 ⇒ 本就不建行 ⇒ 不报。
        assert reported is forwards
