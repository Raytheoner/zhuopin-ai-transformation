"""C 类 4 条转人工规则测试（任务 6.2）——只验在否不下结论，签字/决议真伪留人工。

用合成 ProposalDocument 覆盖：签字已填/未填/解析未命中三态；应对措施全填/部分缺失/
表未解析三态；立项决议恒不判。真实样本（EQ17/邦奇/华丰）交叉验证见
test_golden_product_class.py 的 build_report 集成用例。
"""
from qd_b_gate.models import ExtractStatus, FieldValue, ProposalDocument, Verdict
from qd_b_gate.rules.deterministic import _RULES
from qd_b_gate.rules.registry import load_registry

REG = load_registry()


def _doc_with_signatures(pm_value=None, gm_value=None, pm_status=ExtractStatus.EXTRACTED,
                          gm_status=ExtractStatus.EXTRACTED) -> ProposalDocument:
    doc = ProposalDocument(template_version="A2.1", project_type="产品类")
    doc.fields["十二、总结/项目经理签字及日期"] = FieldValue(
        key="十二、总结/项目经理签字及日期", value=pm_value, status=pm_status)
    doc.fields["十二、总结/总经理签字及日期"] = FieldValue(
        key="十二、总结/总经理签字及日期", value=gm_value, status=gm_status)
    return doc


def _run(rule_id: str, doc: ProposalDocument):
    rule = REG.get(rule_id)
    return _RULES[rule_id](doc, rule)


class TestRule80PMSignature:
    def test_signed_is_manual_not_pass(self):
        doc = _doc_with_signatures(pm_value="2026年6月1日")
        r = _run("80", doc)
        assert r.verdict == Verdict.MANUAL
        assert "真伪人工核" in r.evidence

    def test_unsigned_is_fail_and_blocking(self):
        doc = _doc_with_signatures(pm_value=None, pm_status=ExtractStatus.MISSING)
        r = _run("80", doc)
        assert r.verdict == Verdict.FAIL
        assert r.is_blocking
        assert "未签字" in r.evidence

    def test_not_found_is_pending_not_fail(self):
        """解析未命中（模板改版等）≠ 业务空，不可冒判不合格（D4 纪律）。"""
        doc = _doc_with_signatures(pm_status=ExtractStatus.NOT_FOUND)
        r = _run("80", doc)
        assert r.verdict == Verdict.PENDING


class TestRule81GMSignature:
    def test_signed_is_manual(self):
        doc = _doc_with_signatures(gm_value="2026年6月1日")
        r = _run("81", doc)
        assert r.verdict == Verdict.MANUAL

    def test_unsigned_is_fail_and_blocking(self):
        doc = _doc_with_signatures(gm_value=None, gm_status=ExtractStatus.MISSING)
        r = _run("81", doc)
        assert r.verdict == Verdict.FAIL
        assert r.is_blocking


class TestRule82Decision:
    def test_always_na_regardless_of_document_state(self):
        """立项决议在申请阶段恒不判（design.md 场景「立项决议申请阶段不判」）。"""
        doc = ProposalDocument(template_version="A2.1")
        r = _run("82", doc)
        assert r.verdict == Verdict.NA


class TestRule42MitigationPresence:
    def _doc_with_risk(self, rows):
        doc = ProposalDocument(template_version="A2.1")
        doc.tables["风险"] = rows
        return doc

    def test_all_rows_filled_is_manual(self):
        rows = [
            {"序号": 1, "类别": "技术", "描述": "x", "应对措施": "已制定方案A"},
            {"序号": 2, "类别": "商务", "描述": "y", "应对措施": "已制定方案B"},
        ]
        r = _run("42", self._doc_with_risk(rows))
        assert r.verdict == Verdict.MANUAL
        assert "有效性交评审委员会人工核实" in r.evidence

    def test_missing_mitigation_is_warn_not_fail(self):
        """规则42 severity_level=警告、非阻断——缺项只降级为待改进，不一票否决。"""
        rows = [
            {"序号": 1, "类别": "技术", "描述": "x", "应对措施": "已制定方案A"},
            {"序号": 2, "类别": "商务", "描述": "y", "应对措施": ""},
        ]
        r = _run("42", self._doc_with_risk(rows))
        assert r.verdict == Verdict.WARN
        assert not r.is_blocking
        assert "#2" in r.evidence or "[2]" in r.evidence

    def test_empty_table_is_pending(self):
        r = _run("42", self._doc_with_risk([]))
        assert r.verdict == Verdict.PENDING
