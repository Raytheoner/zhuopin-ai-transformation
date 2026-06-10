"""SC5 agent 合规测试（TDD task 5.4）。

验证：audit JSONL 写入 SC5 事件 / L1 含 auto_count / L2 含 review_count + human_required=True。
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from sc5_purchase.agent import run_sc5

MOCK_DATA = Path(__file__).parent / "mock_data"


@pytest.fixture()
def sc5_result(tmp_path):
    audit_path = tmp_path / "sc5_audit.jsonl"
    recs = run_sc5(mock_dir=MOCK_DATA, today="2026-06-11", audit_path=audit_path)
    events = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    return recs, events


def test_audit_file_written(sc5_result):
    _, events = sc5_result
    assert len(events) >= 1


def test_audit_has_sc5_scenario(sc5_result):
    _, events = sc5_result
    assert all(e["scenario"] == "SC5" for e in events)


def test_l1_event_present(sc5_result):
    _, events = sc5_result
    l1 = [e for e in events if e["automation_level"] == "L1"]
    assert len(l1) >= 1
    d = l1[0]["decision"]
    assert "auto_count" in d
    assert d["auto_count"] >= 1


def test_l2_event_present_with_human_required(sc5_result):
    _, events = sc5_result
    l2 = [e for e in events if e["automation_level"] == "L2"]
    assert len(l2) >= 1
    d = l2[0]["decision"]
    assert d.get("human_required") is True
    assert "review_count" in d
    assert d["review_count"] >= 1


def test_l2_decision_contains_triggered_rules(sc5_result):
    _, events = sc5_result
    l2 = [e for e in events if e["automation_level"] == "L2"]
    d = l2[0]["decision"]
    assert "triggered_rules" in d
    assert len(d["triggered_rules"]) >= 1


def test_audit_chinese_readable(sc5_result, tmp_path):
    """ensure_ascii=False — 中文原文可直接读取，不是 \\uXXXX 转义。"""
    audit_path = tmp_path / "sc5_audit.jsonl"
    run_sc5(mock_dir=MOCK_DATA, today="2026-06-11", audit_path=audit_path)
    raw = audit_path.read_text(encoding="utf-8")
    assert "\\u" not in raw or "待人工审核" in raw


def test_run_sc5_returns_recommendations(sc5_result):
    recs, _ = sc5_result
    assert isinstance(recs, list)
    assert len(recs) == 5


def test_run_sc5_without_audit_path_no_error():
    """不传 audit_path 时不报错（agent 可选落盘）。"""
    recs = run_sc5(mock_dir=MOCK_DATA, today="2026-06-11", audit_path=None)
    assert isinstance(recs, list)
