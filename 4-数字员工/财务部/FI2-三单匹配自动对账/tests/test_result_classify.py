"""五类判定规则编排单测（spec: fi2-result-classify）。"""
from __future__ import annotations

from types import SimpleNamespace

from fi2.models import GRNLine, InvoiceLine, POLine
from fi2.result_classify import classify_all, rule_version


def _po(po_no, line_no, item_code, qty, unit_price, tax_rate):
    amount = round(qty * unit_price * (1 + tax_rate), 6)
    return POLine(po_no, line_no, item_code, qty, unit_price, tax_rate, amount)


def test_five_categories_end_to_end(cfg):
    po = [
        _po("PO-1", "10", "A001", 100, 10, 0.13),   # 完全匹配
        _po("PO-3", "10", "C001", 100, 10, 0.13),   # 数量金额不符
        _po("PO-5", "10", "E001", 100, 10, 0.13),   # 无GR支撑
    ]
    grn = [
        GRNLine("G1", "PO-1", "10", "A001", 100),
        GRNLine("G2", "PO-3", "10", "C001", 100),
    ]
    inv = [
        InvoiceLine("I1", "PO-1", "10", "A001", 100, 10, 1130, 0.13),
        InvoiceLine("I2", "PO-3", "10", "C001", 100, 10.44, 1180, 0.13),
        InvoiceLine("I3", "PO-5", "10", "E001", 100, 10, 1130, 0.13),
    ]
    lines = classify_all(po, grn, inv, cfg=cfg)
    by_po = {line.po_no: line for line in lines}
    assert by_po["PO-1"].classification == "完全匹配"
    assert by_po["PO-1"].status == "l3_suggested_pass"
    assert by_po["PO-1"].needs_review is False
    assert by_po["PO-3"].classification == "数量金额不符"
    assert by_po["PO-3"].needs_review is True
    assert by_po["PO-5"].classification == "无GR支撑"
    assert by_po["PO-5"].needs_review is True
    assert all(line.rule_version == cfg.RULE_VERSION for line in lines)


def test_config_change_reclassifies_without_code_change():
    po = [_po("PO-1", "10", "A001", 100, 10, 0.13)]
    grn = [GRNLine("G1", "PO-1", "10", "A001", 100)]
    inv = [InvoiceLine("I1", "PO-1", "10", "A001", 100, 10.006, 1131, 0.13)]  # +1 元，超默认0.5尾差

    strict_cfg = SimpleNamespace(
        QTY_TOLERANCE_PCT=0.02, QTY_TOLERANCE_ABS=5,
        AMOUNT_TAIL_TOLERANCE=0.5, PO_LEVEL_AMOUNT_TOLERANCE=0.5,
        RULE_VERSION="strict",
    )
    loose_cfg = SimpleNamespace(
        QTY_TOLERANCE_PCT=0.02, QTY_TOLERANCE_ABS=5,
        AMOUNT_TAIL_TOLERANCE=2.0, PO_LEVEL_AMOUNT_TOLERANCE=2.0,
        RULE_VERSION="loose",
    )
    strict_result = classify_all(po, grn, inv, cfg=strict_cfg)[0]
    loose_result = classify_all(po, grn, inv, cfg=loose_cfg)[0]
    assert strict_result.classification == "数量金额不符"
    assert loose_result.classification == "金额微差"


def test_amount_diff_pct_computed_not_raw_amount(cfg):
    po = [_po("PO-1", "10", "A001", 100, 10, 0.13)]
    grn = [GRNLine("G1", "PO-1", "10", "A001", 100)]
    inv = [InvoiceLine("I1", "PO-1", "10", "A001", 100, 10.5, 1050, 0.13)]  # 应付 = 100*10*1.13=1130
    lines = classify_all(po, grn, inv, cfg=cfg)
    line = lines[0]
    assert line.amount_diff_pct == round((1050 - 1130) / 1130, 6)


def test_rule_version_helper(cfg):
    assert rule_version(cfg) == cfg.RULE_VERSION
