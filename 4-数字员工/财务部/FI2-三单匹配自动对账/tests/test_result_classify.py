"""五类判定规则编排单测（spec: fi2-result-classify，v3 口径修正 2026-07-09）。"""
from __future__ import annotations

from types import SimpleNamespace

from fi2.models import APLine, InvoiceLine
from fi2.result_classify import classify_all, rule_version


def _ap(ap_no, item_code, qty, unit_price, tax_rate, po_no="PO-1", line_no="10"):
    untaxed = round(qty * unit_price, 6)
    return APLine(ap_no, po_no, line_no, item_code, qty, unit_price, untaxed, round(untaxed * tax_rate, 6))


def _inv(inv_no, ap_no, item_code, qty, unit_price, tax_rate, untaxed=None, tax_amount=None):
    u = untaxed if untaxed is not None else round(qty * unit_price, 6)
    t = tax_amount if tax_amount is not None else round(u * tax_rate, 6)
    return InvoiceLine(inv_no, ap_no, item_code, "件", unit_price, qty, u, tax_rate, t)


def test_five_categories_end_to_end(cfg):
    ap = [
        _ap("AP-1", "A001", 100, 10, 0.13),   # 完全匹配
        _ap("AP-3", "C001", 100, 10, 0.13),   # 数量金额不符
        _ap("AP-5", "E001", 100, 10, 0.13),   # 无发票支撑
    ]
    inv = [
        _inv("I1", "AP-1", "A001", 100, 10, 0.13),
        _inv("I2", "AP-3", "C001", 100, 10.44, 0.13),
    ]
    items = classify_all(ap, inv, cfg=cfg)
    by_key = {(it.ap_no, it.item_code): it for it in items}
    assert by_key[("AP-1", "A001")].classification == "完全匹配"
    assert by_key[("AP-1", "A001")].status == "l3_suggested_pass"
    assert by_key[("AP-1", "A001")].needs_review is False
    assert by_key[("AP-3", "C001")].classification == "数量金额不符"
    assert by_key[("AP-3", "C001")].needs_review is True
    assert by_key[("AP-5", "E001")].classification == "无发票支撑"
    assert by_key[("AP-5", "E001")].needs_review is True
    assert all(it.rule_version == cfg.RULE_VERSION for it in items)


def test_config_change_reclassifies_without_code_change():
    ap = [_ap("AP-1", "A001", 100, 10, 0.13)]
    inv = [_inv("I1", "AP-1", "A001", 100, 10, 0.13, untaxed=1001, tax_amount=130)]  # +1 元，超默认0.5尾差

    strict_cfg = SimpleNamespace(
        QTY_TOLERANCE_PCT=0.0, QTY_TOLERANCE_ABS=0.0,
        AMOUNT_TAIL_TOLERANCE=0.5, UNTAXED_AMOUNT_TOLERANCE_PCT=0.0, AP_LEVEL_AMOUNT_TOLERANCE=0.5,
        RULE_VERSION="strict",
    )
    loose_cfg = SimpleNamespace(
        QTY_TOLERANCE_PCT=0.0, QTY_TOLERANCE_ABS=0.0,
        AMOUNT_TAIL_TOLERANCE=2.0, UNTAXED_AMOUNT_TOLERANCE_PCT=0.0, AP_LEVEL_AMOUNT_TOLERANCE=2.0,
        RULE_VERSION="loose",
    )
    strict_result = classify_all(ap, inv, cfg=strict_cfg)[0]
    loose_result = classify_all(ap, inv, cfg=loose_cfg)[0]
    assert strict_result.classification == "数量金额不符"
    assert loose_result.classification == "金额微差"


def test_amount_diff_pct_computed_not_raw_amount(cfg):
    ap = [_ap("AP-1", "A001", 100, 10, 0.13)]   # untaxed=1000
    inv = [_inv("I1", "AP-1", "A001", 100, 10.5, 0.13, untaxed=1050, tax_amount=130)]
    items = classify_all(ap, inv, cfg=cfg)
    item = items[0]
    assert item.untaxed_amount_diff_pct == round((1050 - 1000) / 1000, 6)


def test_rule_version_helper(cfg):
    assert rule_version(cfg) == cfg.RULE_VERSION
