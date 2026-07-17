"""料品汇总归集匹配引擎单测（spec: fi2-match-engine，v3 口径修正 2026-07-09）。"""
from __future__ import annotations

from fi2.match_engine import assign_category, build_item_matches, detect_misaligned_items
from fi2.models import APLine, InvoiceLine


def _ap(ap_no, item_code, qty, unit_price, tax_rate, po_no="PO-1", line_no="10"):
    untaxed = round(qty * unit_price, 6)
    return APLine(ap_no, po_no, line_no, item_code, qty, unit_price, untaxed, round(untaxed * tax_rate, 6))


def _inv(inv_no, ap_no, item_code, qty, unit_price, tax_rate, untaxed=None, tax_amount=None):
    u = untaxed if untaxed is not None else round(qty * unit_price, 6)
    t = tax_amount if tax_amount is not None else round(u * tax_rate, 6)
    return InvoiceLine(inv_no, ap_no, item_code, "件", unit_price, qty, u, tax_rate, t)


def test_all_dims_in_tolerance(cfg):
    ap = [_ap("AP-1", "A001", 100, 10, 0.13)]
    inv = [_inv("I1", "AP-1", "A001", 100, 10, 0.13)]
    items = build_item_matches(ap, inv)
    assert items[0].qty_diff == 0
    assert items[0].untaxed_amount_diff == 0
    assert items[0].tax_amount_diff == 0
    assert assign_category(items[0], is_misaligned=False, cfg=cfg) == "完全匹配"


def test_single_dim_over_tolerance_qty(cfg):
    ap = [_ap("AP-1", "A001", 100, 10, 0.13)]
    inv = [_inv("I1", "AP-1", "A001", 120, 10, 0.13)]  # 数量多开 20（超±2%/±5容差）
    items = build_item_matches(ap, inv)
    assert items[0].qty_diff == 20
    assert assign_category(items[0], is_misaligned=False, cfg=cfg) == "数量金额不符"


# ── R1 定稿真值（design D14，2026-07-10）：数量合计±0/税额随税率/未税金额比例备用 ──────

def test_qty_exact_match_required_under_r1(cfg):
    """R1 真值：数量合计 ±0（精确匹配），CC 此前占位的 ±5 个/±2% 容差已取消。"""
    ap = [_ap("AP-22", "P001", 100, 10, 0.13)]
    # 数量多开 1 个，未税金额刚好对齐（隔离数量维度，不受金额容差影响）
    inv = [_inv("I1", "AP-22", "P001", 101, 10, 0.13, untaxed=1000, tax_amount=130)]
    items = build_item_matches(ap, inv)
    assert items[0].qty_diff == 1
    assert items[0].untaxed_amount_diff == 0
    assert assign_category(items[0], is_misaligned=False, cfg=cfg) == "数量金额不符"


def test_tax_tolerance_scales_with_rate_high_rate_passes(cfg):
    """R1"税额随税率"：同样 ¥0.08 税额差，税率越高（0.5×税率的容差越宽）越容易判在容差内。"""
    ap = [_ap("AP-20", "N001", 100, 10, 0.17)]  # untaxed=1000, tax=170
    inv = [_inv("I1", "AP-20", "N001", 100, 10, 0.17, untaxed=1000, tax_amount=170.08)]
    items = build_item_matches(ap, inv)
    assert items[0].untaxed_amount_diff == 0
    assert round(items[0].tax_amount_diff, 2) == 0.08
    assert assign_category(items[0], is_misaligned=False, cfg=cfg) == "完全匹配"


def test_tax_tolerance_scales_with_rate_low_rate_fails(cfg):
    """同样 ¥0.08 税额差，税率更低（容差更窄）时判"数量金额不符"——证明容差非固定值。"""
    ap = [_ap("AP-21", "N002", 100, 10, 0.06)]  # untaxed=1000, tax=60
    inv = [_inv("I1", "AP-21", "N002", 100, 10, 0.06, untaxed=1000, tax_amount=60.08)]
    items = build_item_matches(ap, inv)
    assert items[0].untaxed_amount_diff == 0
    assert round(items[0].tax_amount_diff, 2) == 0.08
    assert assign_category(items[0], is_misaligned=False, cfg=cfg) == "数量金额不符"


def test_untaxed_amount_pct_backup_within_tolerance(cfg):
    """R1"比例口径备用：未税 ≤0.5%"——大额料品下绝对值超 ¥0.5 但比例 ≤0.5% 仍判金额微差。"""
    ap = [_ap("AP-23", "Q001", 1000, 100, 0.13)]  # untaxed=100000, tax=13000
    # 未税金额 +400（比例0.4%，超¥0.5绝对值但在0.5%比例备用线内）；税额独立核对，差异仍在其容差内
    inv = [_inv("I1", "AP-23", "Q001", 1000, 100, 0.13, untaxed=100400, tax_amount=13000.05)]
    items = build_item_matches(ap, inv)
    assert items[0].untaxed_amount_diff == 400
    assert assign_category(items[0], is_misaligned=False, cfg=cfg) == "金额微差"


def test_untaxed_amount_pct_backup_exceeded_still_mismatch(cfg):
    """比例超 0.5% 备用线（此处 0.6%）时，即便是大额料品也不得放行。"""
    ap = [_ap("AP-24", "Q002", 1000, 100, 0.13)]  # untaxed=100000
    inv = [_inv("I1", "AP-24", "Q002", 1000, 100, 0.13, untaxed=100600, tax_amount=13000.05)]
    items = build_item_matches(ap, inv)
    assert items[0].untaxed_amount_diff == 600
    assert assign_category(items[0], is_misaligned=False, cfg=cfg) == "数量金额不符"


# ── 料品编码归一化预处理（design D14）：空格/全半角/括号/"-"与"/"等价类不误判无发票支撑 ──

def test_item_code_normalization_merges_fullwidth_separator_variant(cfg):
    """AP 用半角"-"记法，INV(OCR)用全角"／"+全角数字，应归一化为同一料品。"""
    ap = [_ap("AP-25", "A-001", 100, 10, 0.13)]
    inv = [_inv("I1", "AP-25", "A／００１", 100, 10, 0.13)]
    items = build_item_matches(ap, inv)
    assert len(items) == 1
    assert items[0].has_invoice is True
    assert items[0].item_code == "A-001"  # 报告展示 AP 侧原始写法，不展示归一化中间结果


def test_item_code_normalization_strips_spaces_and_brackets(cfg):
    """AP 用半角括号无空格，INV 用全角括号+前置空格，应归一化为同一料品。"""
    ap = [_ap("AP-26", "C(01)", 100, 10, 0.13)]
    inv = [_inv("I1", "AP-26", "C （01）", 100, 10, 0.13)]
    items = build_item_matches(ap, inv)
    assert len(items) == 1
    assert items[0].has_invoice is True


def test_priority_no_invoice_wins_over_qty_mismatch(cfg):
    """无发票支撑（AP 有料品行但该 ap_no 下找不到对应发票）优先级最高。"""
    ap = [_ap("AP-1", "A001", 100, 10, 0.13)]
    items = build_item_matches(ap, [])
    assert items[0].has_invoice is False
    assert assign_category(items[0], is_misaligned=False, cfg=cfg) == "无发票支撑"


def test_misalignment_positive_negative_pair_within_ap_tolerance(cfg):
    """明细错位正例：同 AP 下两料品方向相反超容差，AP 级总额一致。"""
    ap = [
        _ap("AP-2", "B001", 100, 5, 0.13),
        _ap("AP-2", "B002", 100, 8, 0.13),
    ]
    inv = [
        _inv("I1", "AP-2", "B001", 100, 5.2, 0.13),   # untaxed +20
        _inv("I2", "AP-2", "B002", 100, 7.8, 0.13),   # untaxed -20
    ]
    items = build_item_matches(ap, inv)
    misaligned = detect_misaligned_items(items, cfg=cfg)
    assert ("AP-2", "B001") in misaligned
    assert ("AP-2", "B002") in misaligned
    for item in items:
        assert assign_category(item, is_misaligned=True, cfg=cfg) == "明细错位"


def test_misalignment_reflex_single_item_no_pair_not_misaligned(cfg):
    """反例①：单料品超容差、无配对料品，不得判错位。"""
    ap = [_ap("AP-3", "C001", 100, 10, 0.13)]
    inv = [_inv("I1", "AP-3", "C001", 100, 10.44, 0.13)]  # +44，无配对
    items = build_item_matches(ap, inv)
    misaligned = detect_misaligned_items(items, cfg=cfg)
    assert misaligned == set()
    assert assign_category(items[0], is_misaligned=False, cfg=cfg) == "数量金额不符"


def test_misalignment_reflex_same_direction_not_misaligned(cfg):
    """反例②：两料品同向超容差（非相反），不得判错位。"""
    ap = [
        _ap("AP-4", "D001", 100, 10, 0.13),
        _ap("AP-4", "D002", 100, 10, 0.13),
    ]
    inv = [
        _inv("I1", "AP-4", "D001", 100, 10.44, 0.13),  # +44
        _inv("I2", "AP-4", "D002", 100, 10.44, 0.13),  # +44 同向
    ]
    items = build_item_matches(ap, inv)
    misaligned = detect_misaligned_items(items, cfg=cfg)
    assert misaligned == set()
    for item in items:
        assert assign_category(item, is_misaligned=False, cfg=cfg) == "数量金额不符"


def test_tax_amount_mismatch_forces_mismatch_even_if_untaxed_exact(cfg):
    ap = [_ap("AP-6", "F001", 100, 10, 0.13)]
    inv = [_inv("I1", "AP-6", "F001", 100, 10, 0.13, untaxed=1000, tax_amount=170)]  # 未税金额恰好对上但税额不符
    items = build_item_matches(ap, inv)
    assert items[0].untaxed_amount_diff == 0
    assert items[0].tax_amount_diff == 40
    assert assign_category(items[0], is_misaligned=False, cfg=cfg) == "数量金额不符"


def test_amount_tail_tolerance_classified_as_slight_diff(cfg):
    ap = [_ap("AP-8", "H001", 50, 20, 0.13)]
    inv = [_inv("I1", "AP-8", "H001", 50, 20, 0.13, untaxed=1000.3, tax_amount=130)]  # +0.3，尾差容差内
    items = build_item_matches(ap, inv)
    assert items[0].untaxed_amount_diff == 0.3
    assert assign_category(items[0], is_misaligned=False, cfg=cfg) == "金额微差"


def test_build_item_matches_raises_on_orphan_invoice():
    ap = [_ap("AP-1", "A001", 100, 10, 0.13)]
    inv = [_inv("I1", "AP-9999", "X001", 10, 10, 0.13)]
    try:
        build_item_matches(ap, inv)
        assert False, "应抛出 ValueError（孤立发票未经 partition_invoices 过滤）"
    except ValueError:
        pass


# ── 料品汇总归集多重性（v3 核心新增：AP↔INV 多对一/一对多/多对多，design D11）──────

def test_aggregation_many_ap_to_one_invoice(cfg):
    """多对一：同一料品有 2 条 AP 行（分批配票），1 张发票覆盖合计。"""
    ap = [
        _ap("AP-10", "K001", 60, 10, 0.13),
        _ap("AP-10", "K001", 40, 10, 0.13),
    ]  # 合计 qty=100, untaxed=1000, tax=130
    inv = [_inv("I1", "AP-10", "K001", 100, 10, 0.13)]
    items = build_item_matches(ap, inv)
    assert len(items) == 1
    assert items[0].qty_diff == 0
    assert items[0].untaxed_amount_diff == 0
    assert assign_category(items[0], is_misaligned=False, cfg=cfg) == "完全匹配"


def test_aggregation_one_ap_to_many_invoices(cfg):
    """一对多：1 条 AP 行，2 张发票分开开票，合计与 AP 一致。"""
    ap = [_ap("AP-11", "L001", 100, 10, 0.13)]  # untaxed=1000, tax=130
    inv = [
        _inv("I1", "AP-11", "L001", 60, 10, 0.13),
        _inv("I2", "AP-11", "L001", 40, 10, 0.13),
    ]
    items = build_item_matches(ap, inv)
    assert len(items) == 1
    assert items[0].qty_diff == 0
    assert items[0].untaxed_amount_diff == 0
    assert assign_category(items[0], is_misaligned=False, cfg=cfg) == "完全匹配"


def test_aggregation_many_to_many(cfg):
    """多对多：2 条 AP 行 + 2 张发票，合计一致即完全匹配，不要求逐条一一对应。"""
    ap = [
        _ap("AP-12", "M001", 70, 10, 0.13),
        _ap("AP-12", "M001", 30, 10, 0.13),
    ]  # 合计 qty=100, untaxed=1000
    inv = [
        _inv("I1", "AP-12", "M001", 55, 10, 0.13),
        _inv("I2", "AP-12", "M001", 45, 10, 0.13),
    ]  # 合计 qty=100, untaxed=1000
    items = build_item_matches(ap, inv)
    assert len(items) == 1
    assert items[0].qty_diff == 0
    assert items[0].untaxed_amount_diff == 0
    assert assign_category(items[0], is_misaligned=False, cfg=cfg) == "完全匹配"
