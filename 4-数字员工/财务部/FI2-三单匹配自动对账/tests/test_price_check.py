"""AP-PO 单价强制比对单测（spec: fi2-price-check，design D12，v3 新增 2026-07-09）。"""
from __future__ import annotations

from fi2 import config as _default_cfg
from fi2.models import APLine, POLine
from fi2.price_check import check_ap_po_price, failed_item_keys


def test_foreign_currency_supplier_codes_configured():
    """R7 外币三家真值（design D15-c，队列 #60）——纯配置值守护，防止后续误改/误清点号。

    `ZA.0368`（安富利）含点号，`item_normalize.py` 的归一化只作用于 `item_code`（料品
    编码）聚合 key，不触碰供应商编码比对，这里断言值本身不被误"归一化"掉。
    """
    assert _default_cfg.FOREIGN_CURRENCY_SUPPLIERS == ("ZA0066", "ZA.0368", "ZA0020")


def _po(po_no, line_no, item_code, unit_price):
    return POLine(po_no, line_no, item_code, 100, unit_price, 0.13, round(100 * unit_price * 1.13, 6))


def _ap(ap_no, po_no, line_no, item_code, unit_price):
    untaxed = round(100 * unit_price, 6)
    return APLine(ap_no, po_no, line_no, item_code, 100, unit_price, untaxed, round(untaxed * 0.13, 6))


def test_price_within_tolerance_not_flagged(cfg):
    """R7 真值边界：AP 单价相对 PO 偏离恰 2%，等于 ±2% 拦截线（严格大于才算超差），不告警。"""
    po = [_po("PO-9000", "10", "J001", 10)]
    ap = [_ap("AP-9000", "PO-9000", "10", "J001", 10.2)]  # +2%
    results = check_ap_po_price(ap, po, cfg=cfg)
    assert results[0].exceeds_tolerance is False
    assert round(results[0].price_diff_pct, 2) == 0.02


def test_price_exceeds_tolerance_flagged(cfg):
    """超差场景：AP 单价相对 PO 偏离 6%，超 R7 真值 ±2% 容差，告警。"""
    po = [_po("PO-8000", "10", "H001", 10)]
    ap = [_ap("AP-8000", "PO-8000", "10", "H001", 10.6)]  # +6%
    results = check_ap_po_price(ap, po, cfg=cfg)
    assert results[0].exceeds_tolerance is True
    assert round(results[0].price_diff_pct, 2) == 0.06


def test_price_check_masks_raw_unit_price(cfg):
    """金额脱敏：结果只留差异比例，不落原始单价字段。"""
    po = [_po("PO-8000", "10", "H001", 10)]
    ap = [_ap("AP-8000", "PO-8000", "10", "H001", 10.6)]
    result = check_ap_po_price(ap, po, cfg=cfg)[0]
    assert not hasattr(result, "unit_price")
    assert not hasattr(result, "ap_unit_price")


def test_ap_without_po_reference_flagged():
    """AP 行找不到对应 PO 行（数据完整性异常）——视为无法比价，判超差。"""
    ap = [_ap("AP-99", "PO-NOTEXIST", "10", "Z001", 10)]
    results = check_ap_po_price(ap, [])
    assert results[0].has_po is False
    assert results[0].exceeds_tolerance is True
    assert results[0].price_diff_pct is None


def test_failed_item_keys_aggregates_by_ap_no_item_code():
    po = [_po("PO-8000", "10", "H001", 10), _po("PO-9000", "10", "J001", 10)]
    ap = [
        _ap("AP-8000", "PO-8000", "10", "H001", 10.6),  # 超差
        _ap("AP-9000", "PO-9000", "10", "J001", 10.2),  # 未超差
    ]
    results = check_ap_po_price(ap, po)
    keys = failed_item_keys(results)
    assert ("AP-8000", "H001") in keys
    assert ("AP-9000", "J001") not in keys
