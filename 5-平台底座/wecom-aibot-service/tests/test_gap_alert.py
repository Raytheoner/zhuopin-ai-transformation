from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from zhuopin_platform.audit import AuditLogger

from aibot_service.gap_alert import check_gap_and_format_alert, send_gap_alert


def _write_audit_line(path: Path, timestamp: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": timestamp, "action": "authenticated"}) + "\n")


def test_no_audit_file_returns_none(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    now = datetime.now(timezone.utc)
    assert check_gap_and_format_alert(audit_path, now) is None


def test_gap_within_threshold_returns_none(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    now = datetime.now(timezone.utc)
    last = now - timedelta(seconds=60)
    _write_audit_line(audit_path, last.isoformat())
    assert check_gap_and_format_alert(audit_path, now, threshold_seconds=180) is None


def test_gap_beyond_threshold_returns_alert_text(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    now = datetime.now(timezone.utc)
    last = now - timedelta(hours=23)
    _write_audit_line(audit_path, last.isoformat())
    message = check_gap_and_format_alert(audit_path, now, threshold_seconds=180)
    assert message is not None
    assert "监听已恢复" in message
    assert "1380 分钟" in message  # 23h = 1380min


def test_malformed_last_line_returns_none(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text("not json\n", encoding="utf-8")
    now = datetime.now(timezone.utc)
    assert check_gap_and_format_alert(audit_path, now) is None


def test_ignores_trailing_blank_lines(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    now = datetime.now(timezone.utc)
    last = now - timedelta(hours=1)
    _write_audit_line(audit_path, last.isoformat())
    with audit_path.open("a", encoding="utf-8") as f:
        f.write("\n\n")
    message = check_gap_and_format_alert(audit_path, now, threshold_seconds=180)
    assert message is not None


class _FakeConnector:
    """`send_markdown` 测试替身——可配置成功/失败，记录调用参数。"""

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[tuple[str, str]] = []

    async def send_markdown(self, recipient: str, text: str) -> None:
        self.calls.append((recipient, text))
        if self.should_fail:
            raise RuntimeError("WebSocket not connected, unable to send data")


def _actions(audit: AuditLogger) -> list[str]:
    return [r["action"] for r in audit.query_by(scenario="wecom-aibot")]


def test_send_gap_alert_primary_success_records_sent(tmp_path: Path) -> None:
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = _FakeConnector(should_fail=False)

    asyncio.run(send_gap_alert(connector, audit, "监听已恢复。中断约 5 分钟。", "ShaoPeiShen"))

    assert connector.calls == [("ShaoPeiShen", "ℹ️ 监听已恢复。中断约 5 分钟。")]
    assert _actions(audit) == ["gap_alert_sent"]


def test_send_gap_alert_falls_back_to_webhook_on_primary_failure(tmp_path: Path) -> None:
    """2026-07-19 真实事故：主通道（企微机器人私信）在其自身连接故障期间尝试
    发"已恢复"提醒，发送本身也失败——此前没有兜底，Paul 完全收不到通知。
    修复后：主通道失败时改走独立的 webhook 通道（不依赖同一条故障连接）。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = _FakeConnector(should_fail=True)
    fallback_calls: list[str] = []

    def fallback_send(text: str) -> None:
        fallback_calls.append(text)

    asyncio.run(send_gap_alert(
        connector, audit, "监听已恢复。中断约 2 分钟。", "ShaoPeiShen",
        fallback_send=fallback_send,
    ))

    assert fallback_calls == ["监听已恢复。中断约 2 分钟。"]
    assert _actions(audit) == ["gap_alert_send_failed", "gap_alert_fallback_sent"]


def test_send_gap_alert_fallback_failure_does_not_raise(tmp_path: Path) -> None:
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = _FakeConnector(should_fail=True)

    def failing_fallback(text: str) -> None:
        raise RuntimeError("webhook 也挂了")

    asyncio.run(send_gap_alert(
        connector, audit, "监听已恢复。", "ShaoPeiShen", fallback_send=failing_fallback
    ))

    assert _actions(audit) == ["gap_alert_send_failed", "gap_alert_fallback_failed"]


def test_send_gap_alert_no_fallback_configured_only_logs_failure(tmp_path: Path) -> None:
    """未配置 WECOM_WEBHOOK_URL 时的向后兼容行为——不崩溃、只记录主通道失败。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = _FakeConnector(should_fail=True)

    asyncio.run(send_gap_alert(connector, audit, "监听已恢复。", "ShaoPeiShen", fallback_send=None))

    assert _actions(audit) == ["gap_alert_send_failed"]
