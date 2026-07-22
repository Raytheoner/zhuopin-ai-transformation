from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zhuopin_platform.audit import AuditEvent, AuditLogger

from aibot_service.queue_reconcile_sentinel import (
    build_reconciliation_report,
    find_unreconciled_archives,
    run_reconciliation_sentinel,
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


def test_find_unreconciled_archives_filename_present_in_queue_is_reconciled():
    now = datetime(2026, 7, 22, 6, 0, tzinfo=timezone.utc)
    events = [_archived_event(
        "2026-07-21T01:19:13+00:00",
        "财务部-tangyanping-回复-2026-07-21-abc123.docx",
    )]
    assert find_unreconciled_archives(events, QUEUE_TEXT, now=now) == []


def test_find_unreconciled_archives_filename_absent_is_flagged():
    """2026-07-21 唐燕萍那条归档的真实事故场景——文件名不在队列全文里出现，
    应被判定为疑似漏行。"""
    now = datetime(2026, 7, 22, 6, 0, tzinfo=timezone.utc)
    events = [_archived_event(
        "2026-07-21T01:19:13+00:00",
        "财务部-tangyanping-回复-2026-07-21-neverappeared.docx",
    )]
    result = find_unreconciled_archives(events, QUEUE_TEXT, now=now)
    assert len(result) == 1
    assert result[0]["decision"]["archived_path"].endswith("neverappeared.docx")


def test_find_unreconciled_archives_ignores_events_older_than_within_days():
    now = datetime(2026, 7, 22, 6, 0, tzinfo=timezone.utc)
    stale = _archived_event(
        (now - timedelta(days=10)).isoformat(),
        "财务部-old-回复-neverappeared-too.docx",
    )
    assert find_unreconciled_archives([stale], QUEUE_TEXT, now=now, within_days=7) == []


def test_find_unreconciled_archives_ignores_missing_or_bad_timestamp():
    now = datetime(2026, 7, 22, 6, 0, tzinfo=timezone.utc)
    no_ts = {"decision": {"archived_path": "C:\\x\\neverappeared.docx"}, "data_sources": {}}
    bad_ts = {"timestamp": "not-a-date", "decision": {"archived_path": "C:\\x\\neverappeared.docx"}, "data_sources": {}}
    assert find_unreconciled_archives([no_ts, bad_ts], QUEUE_TEXT, now=now) == []


def test_find_unreconciled_archives_ignores_missing_archived_path():
    now = datetime(2026, 7, 22, 6, 0, tzinfo=timezone.utc)
    event = {"timestamp": now.isoformat(), "decision": {}, "data_sources": {}}
    assert find_unreconciled_archives([event], QUEUE_TEXT, now=now) == []


def test_find_unreconciled_archives_sorted_by_timestamp_ascending():
    now = datetime(2026, 7, 22, 6, 0, tzinfo=timezone.utc)
    later = _archived_event("2026-07-21T10:00:00+00:00", "财务部-b-neverappeared.docx")
    earlier = _archived_event("2026-07-21T01:00:00+00:00", "财务部-a-neverappeared.docx")
    result = find_unreconciled_archives([later, earlier], QUEUE_TEXT, now=now)
    assert [r["timestamp"] for r in result] == [
        "2026-07-21T01:00:00+00:00", "2026-07-21T10:00:00+00:00",
    ]


def test_build_reconciliation_report_empty_returns_none():
    assert build_reconciliation_report([]) is None


def test_build_reconciliation_report_lists_all_entries_in_one_message():
    """告警汇总一条、不逐行发（队列 #70 要求 c）——一次 build 调用产出一条
    包含全部疑似漏行的汇总文本，不是每条各自一条消息。"""
    events = [
        _archived_event("2026-07-21T01:00:00+00:00", "财务部-a-neverappeared.docx", sender="tangyanping"),
        _archived_event("2026-07-21T02:00:00+00:00", "采购部-b-neverappeared.docx", sender="YaoZuYi"),
    ]
    report = build_reconciliation_report(events)
    assert report is not None
    assert report.count("\n") >= 2  # 标题行 + 至少两条明细行
    assert "a-neverappeared.docx" in report
    assert "b-neverappeared.docx" in report
    assert "tangyanping" in report and "YaoZuYi" in report
    assert "2 条疑似漏行" in report
    assert "不会自动写队列" in report


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
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    audit.record(AuditEvent(
        scenario="wecom-aibot", action="archived", evaluator="system", automation_level="L1",
        decision={"archived_path": "C:\\repo\\7-外部文档\\财务部\\财务部-tangyanping-回复-2026-07-21-abc123.docx"},
        data_sources={"sender": "tangyanping"},
    ))
    queue_path = tmp_path / "queue.md"
    queue_path.write_text(QUEUE_TEXT, encoding="utf-8")
    connector = _FakeConnector()

    asyncio.run(run_reconciliation_sentinel(
        connector, audit, queue_path, "ShaoPeiShen", now=datetime.now(timezone.utc)
    ))

    assert connector.calls == []
    assert _actions(audit) == []


def test_run_reconciliation_sentinel_gap_found_sends_one_summary_message(tmp_path: Path):
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
    """队列文件路径不存在（极端场景，如配置错误）——按空文本处理，等价于
    "全部疑似漏行"，不应因文件不存在而抛异常崩溃整个服务。"""
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
