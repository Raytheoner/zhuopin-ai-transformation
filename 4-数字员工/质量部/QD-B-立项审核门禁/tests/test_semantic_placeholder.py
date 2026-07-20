"""B 类 10 条语义判定 MVP 占位测试（任务 5.1/5.3）——极简版统一「待人工复核」。

真实 v4 判据 LLM 判定（任务 5.2）延后到扩容期；本批只锁定占位行为：
不擅自下 PASS/FAIL 结论，全部转人工，且覆盖注册表全部 10 条 B 类规则。
"""
from qd_b_gate.models import ProposalDocument, Verdict
from qd_b_gate.rules.engine import run_semantic_rules
from qd_b_gate.rules.registry import load_registry

REG = load_registry()


def test_covers_all_10_b_class_rules():
    doc = ProposalDocument(template_version="A2.1")
    results = run_semantic_rules(doc, REG)
    assert len(results) == 10
    assert {r.rule_id for r in results} == {r.rule_id for r in REG.by_class("B")}


def test_all_placeholder_verdicts_are_manual():
    """MVP 占位不做 AI 判定：无论文档内容如何，一律「转人工」，不冒判 PASS/FAIL。"""
    doc = ProposalDocument(template_version="A2.1")
    results = run_semantic_rules(doc, REG)
    assert all(r.verdict == Verdict.MANUAL for r in results)
    assert all(r.impl_class == "B" for r in results)


def test_placeholder_evidence_is_transparent_about_being_a_stub():
    """证据文本须如实说明"占位/待接入"，不能伪装成已判定，避免误导评审委员会。"""
    doc = ProposalDocument(template_version="A2.1")
    results = run_semantic_rules(doc, REG)
    assert all("占位" in r.evidence for r in results)
