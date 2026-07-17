"""对账聚合 + L3 门禁 + 审计单测（spec: fi2-recon-report，v3 口径修正 2026-07-09）。"""
from __future__ import annotations

import json

from zhuopin_platform.audit import AuditLogger

from fi2.models import APLine, InvoiceLine, POLine
from fi2.price_check import check_ap_po_price
from fi2.recon_report import build_report
from fi2.result_classify import classify_all


def _po(po_no, line_no, item_code, unit_price):
    return POLine(po_no, line_no, item_code, 100, unit_price, 0.13, round(100 * unit_price * 1.13, 6))


def _ap(ap_no, po_no, line_no, item_code, unit_price, qty=100, tax_rate=0.13):
    untaxed = round(qty * unit_price, 6)
    return APLine(ap_no, po_no, line_no, item_code, qty, unit_price, untaxed, round(untaxed * tax_rate, 6))


def _inv(inv_no, ap_no, item_code, qty, unit_price, tax_rate, untaxed=None, tax_amount=None):
    u = untaxed if untaxed is not None else round(qty * unit_price, 6)
    t = tax_amount if tax_amount is not None else round(u * tax_rate, 6)
    return InvoiceLine(inv_no, ap_no, item_code, "件", unit_price, qty, u, tax_rate, t)


def _sample_items(cfg):
    ap = [
        _ap("AP-1", "PO-1", "10", "A001", 10),   # 完全匹配
        _ap("AP-3", "PO-3", "10", "C001", 10),   # 数量金额不符
    ]
    inv = [
        _inv("I1", "AP-1", "A001", 100, 10, 0.13),
        _inv("I2", "AP-3", "C001", 100, 10.44, 0.13),
    ]
    return classify_all(ap, inv, cfg=cfg)


def test_needs_review_vs_l3_suggested_pass(cfg):
    items = _sample_items(cfg)
    orphaned = [InvoiceLine("I9", "AP-9999", "X001", "件", 1, 1, 1, 0.13, 0.13)]
    report = build_report(items, orphaned, data_sources={"po": "mock"}, cfg=cfg)
    assert report["summary"]["l3_suggested_pass"] == 1
    assert report["summary"]["needs_review"] == 1
    assert report["summary"]["orphaned_invoices"] == 1
    assert "未过账" in report["disclaimer"]


def test_orphaned_invoices_listed_separately(cfg):
    items = _sample_items(cfg)
    orphaned = [InvoiceLine("I9", "AP-9999", "X001", "件", 1, 1, 1, 0.13, 0.13)]
    report = build_report(items, orphaned, data_sources={"po": "mock"}, cfg=cfg)
    assert report["orphaned_invoices"][0]["inv_no"] == "I9"
    assert report["orphaned_invoices"][0]["ap_no"] == "AP-9999"


def test_price_check_failure_forces_needs_review_even_if_fully_matched(cfg):
    """design D12：完全匹配料品若价格超差，报告层须强制改写为 needs_review（分类不变）。"""
    po = [_po("PO-8000", "10", "H001", 10)]
    ap = [_ap("AP-8000", "PO-8000", "10", "H001", 10.6)]  # AP 单价 +6%，超 R7 占位容差
    inv = [_inv("I1", "AP-8000", "H001", 100, 10.6, 0.13)]  # 与 AP 完全一致 → 四维判定"完全匹配"

    items = classify_all(ap, inv, cfg=cfg)
    assert items[0].classification == "完全匹配"  # 分类本身不受价格校验影响

    price_results = check_ap_po_price(ap, po, cfg=cfg)
    report = build_report(items, [], price_results, data_sources={"po": "mock"}, cfg=cfg)

    row = report["items"][0]
    assert row["classification"] == "完全匹配"
    assert row["price_check_failed"] is True
    assert row["status"] == "needs_review"
    assert row["needs_review"] is True
    assert report["summary"]["l3_suggested_pass"] == 0
    assert report["summary"]["needs_review"] == 1
    assert report["summary"]["price_check_alerts"] == 1


def test_price_check_within_tolerance_does_not_override(cfg):
    po = [_po("PO-9000", "10", "J001", 10)]
    ap = [_ap("AP-9000", "PO-9000", "10", "J001", 10.2)]  # +2%，R7 占位容差内
    inv = [_inv("I1", "AP-9000", "J001", 100, 10.2, 0.13)]

    items = classify_all(ap, inv, cfg=cfg)
    price_results = check_ap_po_price(ap, po, cfg=cfg)
    report = build_report(items, [], price_results, data_sources={"po": "mock"}, cfg=cfg)

    row = report["items"][0]
    assert row["price_check_failed"] is False
    assert row["status"] == "l3_suggested_pass"
    assert report["summary"]["price_check_alerts"] == 0


# ── R5 门禁（design D14，2026-07-10）：仅对"金额微差"生效，整单差异总额分级 L2/L3 ────

def test_r5_gate_downgrades_small_amount_diff_to_l2(cfg):
    """整单差异总额在门禁线（¥1）内的"金额微差"降级为 L2 自行消化，不转人工。"""
    po = [_po("PO-1", "10", "A001", 10)]
    ap = [_ap("AP-1", "PO-1", "10", "A001", 10)]  # untaxed=1000
    inv = [_inv("I1", "AP-1", "A001", 100, 10, 0.13, untaxed=1000.3, tax_amount=130)]  # +0.3
    items = classify_all(ap, inv, cfg=cfg)
    assert items[0].classification == "金额微差"

    report = build_report(items, [], ap_lines=ap, po_lines=po, data_sources={"po": "mock"}, cfg=cfg)
    row = report["items"][0]
    assert row["status"] == "l2_self_resolved"
    assert row["needs_review"] is False
    assert report["summary"]["l2_self_resolved"] == 1
    assert report["summary"]["needs_review"] == 0


def test_r5_gate_aggregates_whole_document_not_just_per_item(cfg):
    """R5"差异总额"按整单（同一 ap_no）累计——单料品各自在容差内，但整单累计超门禁线仍转 L3。"""
    po = [
        _po("PO-2", "10", "X001", 0.1),
        _po("PO-2", "20", "X002", 0.1),
        _po("PO-2", "30", "X003", 0.1),
    ]
    ap = [
        _ap("AP-2", "PO-2", "10", "X001", 0.1),
        _ap("AP-2", "PO-2", "20", "X002", 0.1),
        _ap("AP-2", "PO-2", "30", "X003", 0.1),
    ]
    inv = [
        _inv("I1", "AP-2", "X001", 100, 0.1, 0.13, untaxed=10.4, tax_amount=1.3),
        _inv("I2", "AP-2", "X002", 100, 0.1, 0.13, untaxed=10.4, tax_amount=1.3),
        _inv("I3", "AP-2", "X003", 100, 0.1, 0.13, untaxed=10.4, tax_amount=1.3),
    ]
    items = classify_all(ap, inv, cfg=cfg)
    assert all(it.classification == "金额微差" for it in items)  # 单料品各自 +0.4，在¥0.5容差内

    report = build_report(items, [], ap_lines=ap, po_lines=po, data_sources={"po": "mock"}, cfg=cfg)
    # 整单累计差异 1.2 > 门禁 ¥1，且 1.2/30=4% > 0.5% 比例线，两者均超线 → 维持 L3
    assert all(row["status"] == "needs_review" for row in report["items"])
    assert report["summary"]["l2_self_resolved"] == 0
    assert report["summary"]["needs_review"] == 3


def test_r5_gate_overridden_by_price_check_failure(cfg):
    """价格超差优先级高于 R5 门禁——即便整单差异总额在门禁线内，价格超差仍强制转人工。"""
    po = [_po("PO-3", "10", "Y001", 10)]
    ap = [_ap("AP-3", "PO-3", "10", "Y001", 10.6)]  # AP 单价 +6%，超 R7 真值 ±2%
    inv = [_inv("I1", "AP-3", "Y001", 100, 10.6, 0.13, untaxed=1060.3, tax_amount=137.839)]  # 未税+0.3

    items = classify_all(ap, inv, cfg=cfg)
    assert items[0].classification == "金额微差"
    price_results = check_ap_po_price(ap, po, cfg=cfg)
    assert price_results[0].exceeds_tolerance is True

    report = build_report(items, [], price_results, ap_lines=ap, po_lines=po,
                           data_sources={"po": "mock"}, cfg=cfg)
    row = report["items"][0]
    assert row["classification"] == "金额微差"  # 分类本身不受价格校验/门禁影响
    assert row["price_check_failed"] is True
    assert row["status"] == "needs_review"
    assert row["needs_review"] is True
    assert report["summary"]["l2_self_resolved"] == 0


def test_r5_gate_not_applied_when_ap_po_lines_omitted(cfg):
    """向后兼容：不传 `ap_lines`/`po_lines` 时不计算 R5 门禁，"金额微差"维持 needs_review。"""
    ap = [_ap("AP-1", "PO-1", "10", "A001", 10)]
    inv = [_inv("I1", "AP-1", "A001", 100, 10, 0.13, untaxed=1000.3, tax_amount=130)]
    items = classify_all(ap, inv, cfg=cfg)
    assert items[0].classification == "金额微差"

    report = build_report(items, [], data_sources={"po": "mock"}, cfg=cfg)
    assert report["items"][0]["status"] == "needs_review"
    assert report["summary"]["l2_self_resolved"] == 0


def test_audit_event_masks_raw_amount(cfg, tmp_path):
    items = _sample_items(cfg)
    audit = AuditLogger.jsonl(tmp_path / "fi2_audit.jsonl")
    build_report(items, [], data_sources={"po": "mock"}, audit=audit, cfg=cfg)

    raw = (tmp_path / "fi2_audit.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(raw) == 2
    for entry in raw:
        event = json.loads(entry)
        decision = event["decision"]
        assert "untaxed_amount_diff" not in decision   # 不落原始金额绝对值
        assert "tax_amount_diff" not in decision
        assert "untaxed_amount_diff_pct" in decision   # 只留差异比例
        assert event["scenario"] == "FI2"
        assert event["automation_level"] == "L3"
