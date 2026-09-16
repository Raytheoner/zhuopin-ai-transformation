"""本机 outbox 直连适配器（队列 `#595`）——`LocalOutboxConnector` 是
`AibotConnector` 的伪替身，`send_markdown` 只做两件事：核存活戳、写本机
outbox；本身不持有任何网络连接。
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from zhuopin_platform.audit import AuditLogger

from aibot_service.liveness import write_liveness
from aibot_service.local_outbox_connector import (
    DEFAULT_LIVENESS_FRESHNESS_SECONDS,
    LocalOutboxConnector,
    MainServiceUnavailableError,
    ensure_local_outbox_exists,
    resolve_local_outbox_path,
)
from aibot_service.outbox_relay import CHANNEL_DIRECT


def _audit(tmp_path: Path) -> AuditLogger:
    return AuditLogger.jsonl(tmp_path / "audit.jsonl")


def _actions(audit: AuditLogger) -> list[str]:
    return [r["action"] for r in audit.query_by(scenario="wecom-aibot")]


def _connector(tmp_path: Path, audit: AuditLogger, **overrides) -> LocalOutboxConnector:
    kwargs = dict(
        outbox_path=tmp_path / "local_reminder_outbox.jsonl",
        liveness_path=tmp_path / "aibot_liveness.json",
        audit=audit,
        scenario="decision_reminder_check",
    )
    kwargs.update(overrides)
    return LocalOutboxConnector(**kwargs)


def test_resolve_local_outbox_path_is_under_reports() -> None:
    service_dir = Path("/svc")
    assert resolve_local_outbox_path(service_dir) == service_dir / "reports" / "local_reminder_outbox.jsonl"


def test_ensure_local_outbox_exists_touches_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "reports" / "local_reminder_outbox.jsonl"
    assert not path.exists()

    ensure_local_outbox_exists(path)

    assert path.exists()
    assert path.read_text(encoding="utf-8") == ""


def test_ensure_local_outbox_exists_does_not_clobber_existing_content(tmp_path: Path) -> None:
    path = tmp_path / "local_reminder_outbox.jsonl"
    path.write_text('{"already": "here"}\n', encoding="utf-8")

    ensure_local_outbox_exists(path)

    assert path.read_text(encoding="utf-8") == '{"already": "here"}\n'


def test_send_markdown_with_fresh_liveness_appends_direct_channel_record(tmp_path: Path) -> None:
    audit = _audit(tmp_path)
    liveness_path = tmp_path / "aibot_liveness.json"
    write_liveness(liveness_path, datetime.now(timezone.utc))
    outbox_path = tmp_path / "local_reminder_outbox.jsonl"
    connector = _connector(tmp_path, audit, outbox_path=outbox_path, liveness_path=liveness_path)

    result = asyncio.run(connector.send_markdown("ShaoPeiShen", "内容"))

    assert result == {"queued": True}
    lines = outbox_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["channel"] == CHANNEL_DIRECT
    assert record["to_userid"] == "ShaoPeiShen"
    assert record["msgtype"] == "markdown"
    assert record["text"] == "内容"
    assert record["scenario"] == "decision_reminder_check"
    assert "delivered" not in record  # 未投递前不预置该字段，outbox_relay 只认它自己写的
    assert "local_outbox_submit_queued" in _actions(audit)


def test_send_markdown_missing_liveness_raises_and_does_not_write_outbox(tmp_path: Path) -> None:
    audit = _audit(tmp_path)
    outbox_path = tmp_path / "local_reminder_outbox.jsonl"
    connector = _connector(
        tmp_path, audit, outbox_path=outbox_path, liveness_path=tmp_path / "missing_liveness.json",
    )

    with pytest.raises(MainServiceUnavailableError):
        asyncio.run(connector.send_markdown("ShaoPeiShen", "内容"))

    assert not outbox_path.exists()
    assert "local_outbox_submit_service_down" in _actions(audit)
    assert "local_outbox_submit_queued" not in _actions(audit)


def test_send_markdown_stale_liveness_raises_and_does_not_write_outbox(tmp_path: Path) -> None:
    audit = _audit(tmp_path)
    liveness_path = tmp_path / "aibot_liveness.json"
    stale_at = datetime.now(timezone.utc) - timedelta(
        seconds=DEFAULT_LIVENESS_FRESHNESS_SECONDS + 1
    )
    write_liveness(liveness_path, stale_at)
    outbox_path = tmp_path / "local_reminder_outbox.jsonl"
    connector = _connector(tmp_path, audit, outbox_path=outbox_path, liveness_path=liveness_path)

    with pytest.raises(MainServiceUnavailableError):
        asyncio.run(connector.send_markdown("ShaoPeiShen", "内容"))

    assert not outbox_path.exists()
    assert "local_outbox_submit_service_down" in _actions(audit)


def test_send_markdown_liveness_within_freshness_window_still_succeeds(tmp_path: Path) -> None:
    """核的是"过期"，不是"非本轮 5 分钟心跳整点"——留够抖动余量（模块 docstring）。"""
    audit = _audit(tmp_path)
    liveness_path = tmp_path / "aibot_liveness.json"
    almost_stale = datetime.now(timezone.utc) - timedelta(
        seconds=DEFAULT_LIVENESS_FRESHNESS_SECONDS - 1
    )
    write_liveness(liveness_path, almost_stale)
    outbox_path = tmp_path / "local_reminder_outbox.jsonl"
    connector = _connector(tmp_path, audit, outbox_path=outbox_path, liveness_path=liveness_path)

    asyncio.run(connector.send_markdown("ShaoPeiShen", "内容"))

    assert outbox_path.exists()
    assert len(outbox_path.read_text(encoding="utf-8").strip().splitlines()) == 1


def test_disconnect_is_a_noop(tmp_path: Path) -> None:
    audit = _audit(tmp_path)
    connector = _connector(tmp_path, audit)
    assert connector.disconnect() is None


def test_send_markdown_appends_without_clobbering_prior_entries(tmp_path: Path) -> None:
    audit = _audit(tmp_path)
    liveness_path = tmp_path / "aibot_liveness.json"
    write_liveness(liveness_path, datetime.now(timezone.utc))
    outbox_path = tmp_path / "local_reminder_outbox.jsonl"
    connector = _connector(tmp_path, audit, outbox_path=outbox_path, liveness_path=liveness_path)

    asyncio.run(connector.send_markdown("ShaoPeiShen", "第一条"))
    asyncio.run(connector.send_markdown("ShaoPeiShen", "第二条"))

    lines = outbox_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["text"] == "第一条"
    assert json.loads(lines[1])["text"] == "第二条"
