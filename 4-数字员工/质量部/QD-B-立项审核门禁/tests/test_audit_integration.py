"""任务 6.5 验收：QD-B 评估 → audit JSONL 完整判定链 + verify_chain 通过。"""
import json
import tempfile
from pathlib import Path

import pytest
from zhuopin_platform.audit import AuditLogger

from qd_b_gate.evaluate import RULE_VERSION, evaluate
from qd_b_gate.models import Verdict


def _run_with_tmp_audit(doc_path: Path) -> tuple:
    """在临时文件写 audit，返回 (EvaluationResult, audit_path)。"""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        audit_path = Path(f.name)
    result = evaluate(doc_path, audit_path=audit_path, sample_id="test_sample")
    return result, audit_path


class TestAuditWithMockDocument:
    """无需真实立项书文件的 mock 测试。"""

    def test_evaluate_writes_audit_event(self, tmp_path):
        """evaluate() 应写出含完整字段的 audit event。"""
        from unittest.mock import MagicMock, patch
        from qd_b_gate.models import ProposalDocument, RuleResult
        from qd_b_gate.scoring import ScoreResult, ModuleScore

        mock_doc = ProposalDocument(template_version="A2.1", project_type="技术服务类",
                                    source_path="mock.xlsx")
        mock_results = [
            RuleResult(rule_id="1", check_item="必填校验", verdict=Verdict.PASS, impl_class="A"),
            RuleResult(rule_id="11", check_item="结束日期", verdict=Verdict.FAIL,
                       severity_level="错误", evidence="结束日期未填", impl_class="A"),
        ]
        mock_score = ScoreResult(
            veto=True, veto_rules=["11"], total_score=0.0, tier="不合格",
            module_scores={}, provisional=False, evaluated=2, pending=0,
        )

        audit_path = tmp_path / "test_audit.jsonl"

        with (
            patch("qd_b_gate.evaluate.ProposalParser") as MockParser,
            patch("qd_b_gate.evaluate.run_all", return_value=mock_results),
            patch("qd_b_gate.evaluate.score", return_value=mock_score),
        ):
            MockParser.return_value.parse.return_value = mock_doc
            er = evaluate("mock.xlsx", audit_path=audit_path, sample_id="mock_sample")

        assert audit_path.exists()
        lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        rec = json.loads(lines[0])

        assert rec["scenario"] == "QD-B"
        assert rec["action"] == "project_gate_review"
        assert rec["automation_level"] == "L2"
        assert rec["decision"]["rule_version"] == RULE_VERSION
        assert rec["decision"]["sample_id"] == "mock_sample"
        assert rec["decision"]["veto"] is True
        assert rec["decision"]["veto_rules"] == ["11"]
        assert rec["decision"]["tier"] == "不合格"
        assert len(rec["decision"]["per_rule"]) == 2
        assert rec["content_hash"] != ""
        assert rec["timestamp"] != ""

    def test_evaluate_per_rule_contains_all_verdicts(self, tmp_path):
        """per_rule 列表应包含每条规则的 verdict、severity 和 evidence。"""
        from unittest.mock import patch
        from qd_b_gate.models import ProposalDocument, RuleResult
        from qd_b_gate.scoring import ScoreResult

        mock_doc = ProposalDocument(template_version="A2.1")
        mock_results = [
            RuleResult(rule_id="1", check_item="必填", verdict=Verdict.PASS, impl_class="A"),
            RuleResult(rule_id="2", check_item="待改进项", verdict=Verdict.WARN,
                       severity_level="警告", evidence="字数偏少", impl_class="A"),
            RuleResult(rule_id="3", check_item="未实现", verdict=Verdict.PENDING, impl_class="A"),
        ]
        mock_score = ScoreResult(
            veto=False, veto_rules=[], total_score=85.0, tier="合格",
            module_scores={}, provisional=True, evaluated=2, pending=1,
        )
        audit_path = tmp_path / "chain_test.jsonl"

        with (
            patch("qd_b_gate.evaluate.ProposalParser") as MockParser,
            patch("qd_b_gate.evaluate.run_all", return_value=mock_results),
            patch("qd_b_gate.evaluate.score", return_value=mock_score),
        ):
            MockParser.return_value.parse.return_value = mock_doc
            evaluate("mock.xlsx", audit_path=audit_path, sample_id="s1")

        rec = json.loads(audit_path.read_text(encoding="utf-8").strip())
        by_id = {r["rule_id"]: r for r in rec["decision"]["per_rule"]}
        assert by_id["1"]["verdict"] == "通过"
        assert by_id["2"]["verdict"] == "待改进"
        assert by_id["2"]["evidence"] == "字数偏少"
        assert by_id["3"]["verdict"] == "未实现"

    def test_verify_chain_passes_after_evaluate(self, tmp_path):
        """多次 evaluate 写同一 audit 文件后，verify_chain 必须通过（hash-chain 完整性）。"""
        from unittest.mock import patch
        from qd_b_gate.models import ProposalDocument, RuleResult
        from qd_b_gate.scoring import ScoreResult

        mock_doc = ProposalDocument(template_version="A2.1")
        mock_results = [RuleResult(rule_id="1", check_item="必填", verdict=Verdict.PASS, impl_class="A")]
        mock_score = ScoreResult(
            veto=False, veto_rules=[], total_score=90.0, tier="合格",
            module_scores={}, provisional=False, evaluated=1, pending=0,
        )
        audit_path = tmp_path / "chain_verify.jsonl"

        with (
            patch("qd_b_gate.evaluate.ProposalParser") as MockParser,
            patch("qd_b_gate.evaluate.run_all", return_value=mock_results),
            patch("qd_b_gate.evaluate.score", return_value=mock_score),
        ):
            MockParser.return_value.parse.return_value = mock_doc
            for sid in ("sample_A", "sample_B", "sample_C"):
                evaluate("mock.xlsx", audit_path=audit_path, sample_id=sid)

        audit = AuditLogger.jsonl(audit_path)
        chain_result = audit.verify_chain()
        assert chain_result.ok, f"hash-chain 校验失败：{chain_result.error}"
        assert chain_result.total == 3

    def test_content_hash_changes_with_different_input(self, tmp_path):
        """不同样本 → 不同 content_hash（hash 对决策内容敏感）。"""
        from unittest.mock import patch
        from qd_b_gate.models import ProposalDocument, RuleResult
        from qd_b_gate.scoring import ScoreResult

        def _run(sid: str, verdict: Verdict, audit_path: Path) -> str:
            mock_doc = ProposalDocument(template_version="A2.1")
            mock_results = [RuleResult(rule_id="1", check_item="必填",
                                       verdict=verdict, impl_class="A")]
            mock_score = ScoreResult(
                veto=(verdict == Verdict.FAIL), veto_rules=["1"] if verdict == Verdict.FAIL else [],
                total_score=0.0 if verdict == Verdict.FAIL else 100.0, tier="不合格" if verdict == Verdict.FAIL else "合格",
                module_scores={}, provisional=False, evaluated=1, pending=0,
            )
            with (
                patch("qd_b_gate.evaluate.ProposalParser") as MockParser,
                patch("qd_b_gate.evaluate.run_all", return_value=mock_results),
                patch("qd_b_gate.evaluate.score", return_value=mock_score),
            ):
                MockParser.return_value.parse.return_value = mock_doc
                er = evaluate("mock.xlsx", audit_path=audit_path, sample_id=sid)
            return er.audit_event.content_hash

        audit_path = tmp_path / "hash_test.jsonl"
        h1 = _run("pass_sample", Verdict.PASS, audit_path)
        h2 = _run("fail_sample", Verdict.FAIL, audit_path)
        assert h1 != h2


class TestAuditWithHuafeng:
    """需要华丰真实文件的集成测试（文件不存在时自动跳过）。"""

    def test_huafeng_audit_chain(self, huafeng_path, tmp_path):
        """华丰试评 → audit JSONL 有完整判定链 + verify_chain 通过。"""
        audit_path = tmp_path / "huafeng_audit.jsonl"
        er = evaluate(huafeng_path, audit_path=audit_path, sample_id="huafeng_deidentified")

        assert audit_path.exists()
        rec = json.loads(audit_path.read_text(encoding="utf-8").strip())

        assert rec["scenario"] == "QD-B"
        assert rec["decision"]["rule_version"] == RULE_VERSION
        assert rec["decision"]["sample_id"] == "huafeng_deidentified"
        # evaluate() 现跑 run_all()（A68+C4+B10=82，任务6.1/6.2/6.5 全链审计，非只审 A 类）
        assert len(rec["decision"]["per_rule"]) == 82, "应有 82 条 A+B+C 类规则判定（全链审计）"

        audit = AuditLogger.jsonl(audit_path)
        chain = audit.verify_chain()
        assert chain.ok, f"hash-chain 校验失败：{chain.error}"
