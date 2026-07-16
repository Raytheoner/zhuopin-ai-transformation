from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from aibot_service.gap_alert import check_gap_and_format_alert


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
