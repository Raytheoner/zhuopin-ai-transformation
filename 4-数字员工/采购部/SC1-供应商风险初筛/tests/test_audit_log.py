import sys
import json
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.audit_log import SC1AuditAdapter as AuditLogger
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
        # 平台格式：顶层 evaluator + scenario，业务字段在 decision
        assert record["evaluator"] == "张三"
        assert record["scenario"] == "SC1"
        assert record["decision"]["supplier_name"] == "测试供应商A"
        assert record["decision"]["risk_level"] in range(1, 6)
        assert "composite_score" in record["decision"]
        assert "weights" in record["decision"]
        assert record["content_hash"] == "abc123"

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
        # 平台格式：scores 在 decision 内
        assert "scores" in record["decision"]
        assert set(record["decision"]["scores"].keys()) == {
            "delivery", "iqc", "financial", "single_source"
        }
        for v in record["decision"]["scores"].values():
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
        # report_path 在 decision 内；error 保留在顶层（AuditEvent.to_dict 规范）
        assert record["decision"]["report_path"] == "FAILED"
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

    def test_verify_integrity_returns_complete_fields(self):
        """verify_integrity() 返回 main.py 所依赖的全部字段（兼容补全）。"""
        result = _make_result()
        self.logger.append_record(
            evaluator="测试员",
            supplier_name="供应商X",
            supplier_code="SX001",
            result=result,
            delivery_source="人工录入",
            ai_text_hash="",
            report_path="/reports/x.md",
        )
        integrity = self.logger.verify_integrity()
        assert integrity["status"] == "ok"
        assert integrity["total"] == 1
        assert integrity["valid"] == 1
        assert integrity["invalid"] == 0
        assert "invalid_lines" in integrity
        assert "suppliers" in integrity
        assert "供应商X" in integrity["suppliers"]
        assert "recent_10" in integrity
        assert len(integrity["recent_10"]) == 1
        assert integrity["recent_10"][0]["supplier"] == "供应商X"

    def test_verify_chain_passes_with_3_records(self):
        """3 条记录后 verify_chain() 返回 ok=True, total=3。"""
        result = _make_result()
        for _ in range(3):
            self.logger.append_record(
                evaluator="链测试",
                supplier_name="供应商链",
                supplier_code="",
                result=result,
                delivery_source="人工录入",
                ai_text_hash="",
                report_path="",
            )
        chain_result = self.logger.verify_chain()
        assert chain_result.ok is True
        assert chain_result.total == 3

    def test_verify_chain_fails_on_tamper(self):
        """篡改 JSONL 文件内容后 verify_chain() 检出断链，ok=False。"""
        result = _make_result()
        for _ in range(3):
            self.logger.append_record(
                evaluator="链测试",
                supplier_name="供应商链",
                supplier_code="",
                result=result,
                delivery_source="人工录入",
                ai_text_hash="",
                report_path="",
            )
        # 直接篡改第一行的 evaluator（保持合法 JSON，但哈希链断裂）
        raw = self.log_path.read_bytes()
        lines = raw.split(b"\n")
        first = json.loads(lines[0].decode("utf-8"))
        first["evaluator"] = "黑客"
        lines[0] = json.dumps(first, ensure_ascii=False).encode("utf-8")
        self.log_path.write_bytes(b"\n".join(lines))

        chain_result = self.logger.verify_chain()
        assert chain_result.ok is False
        assert chain_result.broken_at is not None
