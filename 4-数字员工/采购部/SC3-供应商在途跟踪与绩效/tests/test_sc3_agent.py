"""
SC3 agent 层测试：执行后 audit JSONL 写入 SC3 事件，details 含风险计数。
"""
import json
import tempfile
from datetime import date
from pathlib import Path

from sc3_intransit.agent import run_sc3

TODAY = date(2026, 5, 9)
MOCK_DIR = Path(__file__).parent / "mock_data"


class TestSC3Agent:
    def test_returns_risk_list(self):
        """run_sc3 返回非空风险列表"""
        with tempfile.TemporaryDirectory() as tmp:
            results = run_sc3(MOCK_DIR, TODAY, audit_path=Path(tmp) / "audit.jsonl")
        assert len(results) == 5

    def test_audit_event_written(self):
        """执行后 audit JSONL 存在 SC3 in_transit_risk_eval 事件"""
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.jsonl"
            run_sc3(MOCK_DIR, TODAY, audit_path=audit_path)
            lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) >= 1
        event = json.loads(lines[-1])
        assert event["scenario"] == "SC3"
        assert event["action"] == "in_transit_risk_eval"
        assert event["automation_level"] == "L1"

    def test_audit_decision_contains_counts(self):
        """audit decision 字段含 total_pos / high_count / medium_count / low_count"""
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.jsonl"
            run_sc3(MOCK_DIR, TODAY, audit_path=audit_path)
            event = json.loads(audit_path.read_text(encoding="utf-8").strip().splitlines()[-1])
        d = event["decision"]
        assert d["total_pos"] == 5
        assert d["high_count"] == 2
        assert d["medium_count"] == 2
        assert d["low_count"] == 1

    def test_audit_chinese_reasons_encoded(self):
        """risk_reasons 含中文，序列化后应可读（不是 \\uXXXX 转义）"""
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.jsonl"
            run_sc3(MOCK_DIR, TODAY, audit_path=audit_path)
            raw = audit_path.read_text(encoding="utf-8")
        # 如果含中文字符（如"承诺"）则不应被 ASCII 转义
        assert "\\u627f" not in raw  # "承" 的 unicode
