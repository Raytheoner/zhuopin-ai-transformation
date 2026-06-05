import sys
import json
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.audit_log import AuditLogger
from src.scoring import RiskScoringEngine


def _make_result():
    engine = RiskScoringEngine()
    return engine.evaluate(
        delivery_rate=92.0,
        iqc_rate=97.5,
        registered_capital_wan=1000.0,
        years_established=8.0,
        single_source_option=2,
    )


class TestAuditLogger:
    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.log_path = Path(self.tmp.name)
        self.logger = AuditLogger(self.log_path)

    def teardown_method(self):
        if self.log_path.exists():
            self.log_path.unlink()

    def test_append_creates_valid_json_line(self):
        result = _make_result()
        self.logger.append_record(
            evaluator="张三",
            supplier_name="测试供应商A",
            supplier_code="S001",
            result=result,
            delivery_source="SRM自动",
            ai_text_hash="abc123",
            report_path="/reports/test.md",
        )
        lines = self.log_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["supplier_name"] == "测试供应商A"
        assert record["evaluator"] == "张三"
        assert record["risk_level"] in range(1, 6)
        assert "composite_score" in record
        assert "weights" in record
        assert "ai_text_hash" in record

    def test_no_raw_financial_data_in_log(self):
        """核心安全测试：注册资本和 IQC 合格率原始值不得出现在日志中。"""
        result = _make_result()
        self.logger.append_record(
            evaluator="李四",
            supplier_name="测试供应商B",
            supplier_code="S002",
            result=result,
            delivery_source="人工录入",
            ai_text_hash="def456",
            report_path="/reports/test2.md",
        )
        raw_content = self.log_path.read_text(encoding="utf-8")
        # 确认原始注册资本（1000.0）和 IQC 合格率（97.5）不在日志中
        # 注意：维度评分 4.0 可以存在（这是评分，不是原始值）
        assert "1000.0" not in raw_content
        assert "97.5" not in raw_content

    def test_scores_are_recorded(self):
        result = _make_result()
        self.logger.append_record(
            evaluator="王五",
            supplier_name="测试供应商C",
            supplier_code="",
            result=result,
            delivery_source="SRM自动",
            ai_text_hash="",
            report_path="",
        )
        record = json.loads(self.log_path.read_text(encoding="utf-8").strip())
        assert "scores" in record
        assert set(record["scores"].keys()) == {"delivery", "iqc", "financial", "single_source"}
        for v in record["scores"].values():
            assert 1.0 <= v <= 5.0

    def test_failed_report_recorded(self):
        result = _make_result()
        self.logger.append_record(
            evaluator="赵六",
            supplier_name="测试供应商D",
            supplier_code="",
            result=result,
            delivery_source="人工录入",
            ai_text_hash="",
            report_path="",
            error="磁盘空间不足",
        )
        record = json.loads(self.log_path.read_text(encoding="utf-8").strip())
        assert record["report_path"] == "FAILED"
        assert record["error"] == "磁盘空间不足"

    def test_query_by_supplier(self):
        result = _make_result()
        for i in range(3):
            self.logger.append_record(
                evaluator="评估人",
                supplier_name="目标供应商",
                supplier_code="",
                result=result,
                delivery_source="人工录入",
                ai_text_hash="",
                report_path=f"/reports/{i}.md",
            )
        self.logger.append_record(
            evaluator="评估人",
            supplier_name="其他供应商",
            supplier_code="",
            result=result,
            delivery_source="人工录入",
            ai_text_hash="",
            report_path="/reports/other.md",
        )
        records = self.logger.query_by_supplier("目标供应商")
        assert len(records) == 3
        for r in records:
            assert "timestamp" in r
            assert "risk_level" in r

    def test_verify_integrity_empty_file(self):
        empty_path = Path(self.tmp.name + "_empty.jsonl")
        logger = AuditLogger(empty_path)
        result = logger.verify_integrity()
        assert result["status"] == "empty"
        assert result["total"] == 0

    def test_verify_integrity_with_corrupt_line(self):
        self.log_path.write_text(
            '{"valid": true, "timestamp": "2026-01-01T00:00:00+00:00", '
            '"supplier_name": "X", "evaluator": "Y", "composite_score": 3.5, '
            '"risk_level": 3, "scores": {}, "weights": {}, "data_sources": {}, '
            '"report_path": "", "ai_text_hash": ""}\n'
            'THIS IS NOT JSON\n',
            encoding="utf-8"
        )
        result = self.logger.verify_integrity()
        assert result["valid"] == 1
        assert result["invalid"] == 1
        assert result["status"] == "warn"

    def test_query_skips_corrupt_lines(self):
        self.log_path.write_text(
            '{"supplier_name": "好供应商", "timestamp": "2026-01-01T00:00:00+00:00", '
            '"risk_level": 2, "composite_score": 4.1, "evaluator": "A", '
            '"report_path": ""}\n'
            'BAD JSON LINE\n',
            encoding="utf-8"
        )
        records = self.logger.query_by_supplier("好供应商")
        assert len(records) == 1
