"""四维匹配引擎单测（spec: fi2-match-engine）。"""
from __future__ import annotations

from fi2.match_engine import assign_category, build_line_matches, detect_misaligned_lines
from fi2.models import GRNLine, InvoiceLine, POLine


def _po(po_no, line_no, item_code, qty, unit_price, tax_rate):
    amount = round(qty * unit_price * (1 + tax_rate), 6)
    return POLine(po_no, line_no, item_code, qty, unit_price, tax_rate, amount)


def test_all_dims_in_tolerance(cfg):
    po = [_po("PO-1", "10", "A001", 100, 10, 0.13)]
    grn = [GRNLine("G1", "PO-1", "10", "A001", 100)]
    inv = [InvoiceLine("I1", "PO-1", "10", "A001", 100, 10, 1130, 0.13)]
    lines = build_line_matches(po, grn, inv)
    assert lines[0].qty_diff == 0
    assert lines[0].amount_diff == 0
    assert lines[0].item_code_match is True
    assert lines[0].tax_rate_match is True


def test_single_dim_over_tolerance_qty(cfg):
    po = [_po("PO-1", "10", "A001", 100, 10, 0.13)]
    grn = [GRNLine("G1", "PO-1", "10", "A001", 100)]
    inv = [InvoiceLine("I1", "PO-1", "10", "A001", 120, 10, 1130, 0.13)]  # 数量多开 20（超±2%/±5容差）
    lines = build_line_matches(po, grn, inv)
    assert lines[0].qty_diff == 20


def test_priority_no_grn_wins_over_qty_mismatch(cfg):
    """无 GRN 时即使数量也算不出，仍应优先判定为无GR支撑。"""
    po = [_po("PO-1", "10", "A001", 100, 10, 0.13)]
    inv = [InvoiceLine("I1", "PO-1", "10", "A001", 120, 10, 1130, 0.13)]
    lines = build_line_matches(po, [], inv)
    assert lines[0].has_grn is False
    category = assign_category(lines[0], is_misaligned=False, cfg=cfg)
    assert category == "无GR支撑"


def test_misalignment_positive_negative_pair_within_po_tolerance(cfg):
    """明细错位正例：同 PO 下两行方向相反超容差，PO 级总额一致。"""
    po = [
        _po("PO-2", "10", "B001", 100, 5, 0.13),
        _po("PO-2", "20", "B002", 100, 8, 0.13),
    ]
    grn = [
        GRNLine("G1", "PO-2", "10", "B001", 100),
        GRNLine("G2", "PO-2", "20", "B002", 100),
    ]
    inv = [
        InvoiceLine("I1", "PO-2", "10", "B001", 100, 5.2, 585, 0.13),   # +20
        InvoiceLine("I2", "PO-2", "20", "B002", 100, 7.8, 884, 0.13),   # -20
    ]
    lines = build_line_matches(po, grn, inv)
    misaligned = detect_misaligned_lines(lines, cfg=cfg)
    assert ("PO-2", "10") in misaligned
    assert ("PO-2", "20") in misaligned
    for line in lines:
        assert assign_category(line, is_misaligned=True, cfg=cfg) == "明细错位"


def test_misalignment_reflex_single_line_no_pair_not_misaligned(cfg):
    """反例①：单行超容差、无配对行，不得判错位。"""
    po = [_po("PO-3", "10", "C001", 100, 10, 0.13)]
    grn = [GRNLine("G1", "PO-3", "10", "C001", 100)]
    inv = [InvoiceLine("I1", "PO-3", "10", "C001", 100, 10.44, 1180, 0.13)]  # +50，无配对
    lines = build_line_matches(po, grn, inv)
    misaligned = detect_misaligned_lines(lines, cfg=cfg)
    assert misaligned == set()
    assert assign_category(lines[0], is_misaligned=False, cfg=cfg) == "数量金额不符"


def test_misalignment_reflex_same_direction_not_misaligned(cfg):
    """反例②：两行同向超容差（非相反），不得判错位。"""
    po = [
        _po("PO-4", "10", "D001", 100, 10, 0.13),
        _po("PO-4", "20", "D002", 100, 10, 0.13),
    ]
    grn = [
        GRNLine("G1", "PO-4", "10", "D001", 100),
        GRNLine("G2", "PO-4", "20", "D002", 100),
    ]
    inv = [
        InvoiceLine("I1", "PO-4", "10", "D001", 100, 10.44, 1180, 0.13),  # +50
        InvoiceLine("I2", "PO-4", "20", "D002", 100, 10.44, 1180, 0.13),  # +50 同向
    ]
    lines = build_line_matches(po, grn, inv)
    misaligned = detect_misaligned_lines(lines, cfg=cfg)
    assert misaligned == set()
    for line in lines:
        assert assign_category(line, is_misaligned=False, cfg=cfg) == "数量金额不符"


def test_tax_rate_mismatch_forces_mismatch_even_if_amount_exact(cfg):
    po = [_po("PO-6", "10", "F001", 100, 10, 0.13)]
    grn = [GRNLine("G1", "PO-6", "10", "F001", 100)]
    inv = [InvoiceLine("I1", "PO-6", "10", "F001", 100, 9.66, 1130, 0.17)]  # 金额恰好对上但税率不符
    lines = build_line_matches(po, grn, inv)
    assert lines[0].tax_rate_match is False
    assert assign_category(lines[0], is_misaligned=False, cfg=cfg) == "数量金额不符"


def test_item_code_mismatch_forces_mismatch(cfg):
    po = [_po("PO-7", "10", "G001", 100, 10, 0.13)]
    grn = [GRNLine("G1", "PO-7", "10", "G001", 100)]
    inv = [InvoiceLine("I1", "PO-7", "10", "G002", 100, 10, 1130, 0.13)]  # 物料编码不符
    lines = build_line_matches(po, grn, inv)
    assert lines[0].item_code_match is False
    assert assign_category(lines[0], is_misaligned=False, cfg=cfg) == "数量金额不符"


def test_amount_tail_tolerance_classified_as_slight_diff(cfg):
    po = [_po("PO-8", "10", "H001", 50, 20, 0.13)]
    grn = [GRNLine("G1", "PO-8", "10", "H001", 50)]
    inv = [InvoiceLine("I1", "PO-8", "10", "H001", 50, 20.006, 1130.3, 0.13)]  # +0.3，尾差容差内
    lines = build_line_matches(po, grn, inv)
    assert lines[0].amount_diff == 0.3
    assert assign_category(lines[0], is_misaligned=False, cfg=cfg) == "金额微差"


def test_build_line_matches_raises_on_orphan_invoice():
    po = [_po("PO-1", "10", "A001", 100, 10, 0.13)]
    inv = [InvoiceLine("I1", "PO-9999", "10", "X001", 10, 10, 113, 0.13)]
    try:
        build_line_matches(po, [], inv)
        assert False, "应抛出 ValueError（孤立发票未经 partition_invoices 过滤）"
    except ValueError:
        pass
