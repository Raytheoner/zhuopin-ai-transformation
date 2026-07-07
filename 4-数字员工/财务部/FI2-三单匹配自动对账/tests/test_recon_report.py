"""对账聚合 + L3 门禁 + 审计单测（spec: fi2-recon-report）。"""
from __future__ import annotations

import json

from zhuopin_platform.audit import AuditLogger

from fi2.models import GRNLine, InvoiceLine, POLine
from fi2.recon_report import build_report
from fi2.result_classify import classify_all


def _po(po_no, line_no, item_code, qty, unit_price, tax_rate):
    amount = round(qty * unit_price * (1 + tax_rate), 6)
    return POLine(po_no, line_no, item_code, qty, unit_price, tax_rate, amount)


def _sample_lines(cfg):
    po = [
        _po("PO-1", "10", "A001", 100, 10, 0.13),   # 完全匹配
        _po("PO-3", "10", "C001", 100, 10, 0.13),   # 数量金额不符
    ]
    grn = [
        GRNLine("G1", "PO-1", "10", "A001", 100),
        GRNLine("G2", "PO-3", "10", "C001", 100),
    ]
    inv = [
        InvoiceLine("I1", "PO-1", "10", "A001", 100, 10, 1130, 0.13),
        InvoiceLine("I2", "PO-3", "10", "C001", 100, 10.44, 1180, 0.13),
    ]
    return classify_all(po, grn, inv, cfg=cfg)


def test_needs_review_vs_l3_suggested_pass(cfg):
    lines = _sample_lines(cfg)
    orphaned = [InvoiceLine("I9", "PO-9999", "10", "X001", 1, 1, 1.13, 0.13)]
    report = build_report(lines, orphaned, data_sources={"po": "mock"}, cfg=cfg)
    assert report["summary"]["l3_suggested_pass"] == 1
    assert report["summary"]["needs_review"] == 1
    assert report["summary"]["orphaned_invoices"] == 1
    assert "未过账" in report["disclaimer"]


def test_orphaned_invoices_listed_separately(cfg):
    lines = _sample_lines(cfg)
    orphaned = [InvoiceLine("I9", "PO-9999", "10", "X001", 1, 1, 1.13, 0.13)]
    report = build_report(lines, orphaned, data_sources={"po": "mock"}, cfg=cfg)
    assert report["orphaned_invoices"][0]["inv_no"] == "I9"
    assert report["orphaned_invoices"][0]["po_no"] == "PO-9999"


def test_audit_event_masks_raw_amount(cfg, tmp_path):
    lines = _sample_lines(cfg)
    audit = AuditLogger.jsonl(tmp_path / "fi2_audit.jsonl")
    build_report(lines, [], data_sources={"po": "mock"}, audit=audit, cfg=cfg)

    raw = (tmp_path / "fi2_audit.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(raw) == 2
    for entry in raw:
        event = json.loads(entry)
        decision = event["decision"]
        assert "amount_diff" not in decision       # 不落原始金额绝对值
        assert "inv_amount" not in decision
        assert "amount_diff_pct" in decision       # 只留差异比例
        assert event["scenario"] == "FI2"
        assert event["automation_level"] == "L3"
