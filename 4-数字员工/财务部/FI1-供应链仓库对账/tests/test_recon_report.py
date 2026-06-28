"""对账聚合 + L2 门禁 + 审计单测（spec: fi1-recon-report）。"""
from __future__ import annotations

from zhuopin_platform.audit import AuditLogger

from fi1.models import ComponentReconcile
from fi1.recon_report import DISCLAIMER, build_report
from fi1.reconcile_engine import compute_reconcile
from fi1.variance_classify import classify_all


def _c(cid, theoretical, std_loss, actual, *, bom_incomplete=False):
    variance = round(actual - theoretical, 6)
    pct = round(variance / theoretical, 6) if theoretical > 0 else None
    return ComponentReconcile(cid, "件", theoretical, std_loss, actual, variance, pct, bom_incomplete)


def test_report_contract_fields():
    comps = classify_all([_c("C1", 200, 20, 215)])
    rep = build_report(comps, [], data_sources={"bom": "mock", "feed": "mock", "output": "mock"})
    assert rep["scenario"] == "FI1"
    assert rep["automation_level"] == "L2"
    assert rep["disclaimer"] == DISCLAIMER
    item = rep["items"][0]
    for k in ("component_id", "theoretical_net", "standard_loss", "actual_feed",
              "total_variance", "variance_pct", "classification", "status", "rule_version"):
        assert k in item


def test_l2_over_threshold_marks_needs_review():
    comps = classify_all([_c("C1", 100, 5, 120)])   # 超损·需人工
    rep = build_report(comps, [], data_sources={})
    assert rep["items"][0]["status"] == "需人工确认"
    assert rep["summary"]["needs_review"] == 1


def test_l2_within_threshold_auto_suggest():
    comps = classify_all([_c("C1", 200, 20, 215)])  # 标准内
    rep = build_report(comps, [], data_sources={})
    assert rep["items"][0]["status"] == "AI建议通过"
    assert rep["summary"]["auto_suggest_pass"] == 1


def test_bom_incomplete_listed_separately():
    comps = classify_all([_c("X", 0, 0, 30, bom_incomplete=True)])
    rep = build_report(comps, ["P2"], data_sources={})
    assert rep["items"][0]["status"] == "待人工核"
    assert rep["summary"]["manual_check"] == 1
    assert "P2" in rep["incomplete_products"]


def test_audit_written_quantity_only_no_price(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "fi1_audit.jsonl")
    comps = classify_all([_c("C1", 100, 5, 120)])
    build_report(comps, [], data_sources={"bom": "u9c"}, evaluator="王经理", audit=audit)
    recs = audit.query_by(scenario="FI1")
    assert len(recs) == 1
    decision = recs[0]["decision"]
    # 数量为主，金额/单价不落 AI 侧（红线 D7）
    assert "total_variance" in decision
    for forbidden in ("unit_price", "amount", "金额", "单价", "price"):
        assert forbidden not in decision
    assert recs[0]["automation_level"] == "L2"
    assert audit.verify_chain().ok is True


def test_full_pipeline_from_engine(simple_bom, simple_outputs, simple_feeds, tmp_path):
    comp = compute_reconcile(simple_bom, simple_outputs, simple_feeds)
    classified = classify_all(comp.components)
    audit = AuditLogger.jsonl(tmp_path / "a.jsonl")
    rep = build_report(classified, comp.incomplete_products,
                       data_sources={"bom": "mock", "output": "mock", "feed": "mock"},
                       evaluator="李经理", audit=audit)
    assert rep["summary"]["total"] == len(classified)
    assert len(audit.query_by(scenario="FI1")) == len(classified)
