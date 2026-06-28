"""对账引擎纯算法单测（spec: fi1-reconcile-engine）。"""
from __future__ import annotations

from zhuopin_platform.shared_tools.models import BomRow

from fi1.models import MaterialFeed, ProductionOutput
from fi1.reconcile_engine import compute_reconcile


def _by_id(comp):
    return {c.component_id: c for c in comp}


def test_single_product_single_component_theoretical_and_loss():
    bom = [BomRow("P", "C", "件", 1, 2, 0.05, "PCS")]
    out = [ProductionOutput("P", "成品", 100)]
    feed = [MaterialFeed("C", "件", 200, "PCS")]
    r = compute_reconcile(bom, out, feed)
    c = _by_id(r.components)["C"]
    assert c.theoretical_net == 200          # 100 × 2
    assert c.standard_loss == 10.0           # 200 × 0.05
    assert c.total_variance == 0
    assert c.variance_pct == 0.0


def test_multi_product_shared_component_accumulates(simple_bom, simple_outputs, simple_feeds):
    r = compute_reconcile(simple_bom, simple_outputs, simple_feeds)
    c001 = _by_id(r.components)["C001"]
    # 100×2 + 50×3 = 350
    assert c001.theoretical_net == 350
    # 100×2×0.05 + 50×3×0.05 = 10 + 7.5 = 17.5
    assert c001.standard_loss == 17.5
    assert c001.actual_feed == 360
    assert c001.total_variance == 10


def test_zero_output_no_contribution():
    bom = [BomRow("P", "C", "件", 1, 2, 0.05, "PCS")]
    out = [ProductionOutput("P", "成品", 0)]
    feed = [MaterialFeed("C", "件", 5, "PCS")]
    r = compute_reconcile(bom, out, feed)
    c = _by_id(r.components)["C"]
    # 产出 0 → 理论净 0 → 无理论基准
    assert c.theoretical_net == 0
    assert c.variance_pct is None
    assert c.bom_incomplete is True


def test_positive_variance():
    bom = [BomRow("P", "C", "件", 1, 2, 0.05, "PCS")]
    out = [ProductionOutput("P", "成品", 100)]
    feed = [MaterialFeed("C", "件", 215, "PCS")]
    c = _by_id(compute_reconcile(bom, out, feed).components)["C"]
    assert c.total_variance == 15
    assert c.variance_pct == 0.075


def test_negative_variance():
    bom = [BomRow("P", "C", "件", 1, 2, 0.05, "PCS")]
    out = [ProductionOutput("P", "成品", 100)]
    feed = [MaterialFeed("C", "件", 190, "PCS")]
    c = _by_id(compute_reconcile(bom, out, feed).components)["C"]
    assert c.total_variance == -10
    assert c.variance_pct == -0.05


def test_no_theoretical_basis_feed_only():
    bom = [BomRow("P", "C", "件", 1, 2, 0.05, "PCS")]
    out = [ProductionOutput("P", "成品", 100)]
    feed = [MaterialFeed("C", "件", 200, "PCS"), MaterialFeed("X", "意外件", 8, "PCS")]
    r = compute_reconcile(bom, out, feed)
    x = _by_id(r.components)["X"]
    assert x.theoretical_net == 0
    assert x.variance_pct is None
    assert x.bom_incomplete is True
    assert x.total_variance == 8


def test_feed_lines_for_same_component_accumulate():
    bom = [BomRow("P", "C", "件", 1, 1, 0.0, "PCS")]
    out = [ProductionOutput("P", "成品", 100)]
    feed = [MaterialFeed("C", "件", 60, "PCS"), MaterialFeed("C", "件", 45, "PCS")]
    c = _by_id(compute_reconcile(bom, out, feed).components)["C"]
    assert c.actual_feed == 105
    assert c.total_variance == 5


def test_bom_failed_products_surfaced():
    bom = [BomRow("P1", "C", "件", 1, 2, 0.0, "PCS")]
    out = [ProductionOutput("P1", "成品1", 100), ProductionOutput("P2", "成品2", 50)]
    feed = [MaterialFeed("C", "件", 200, "PCS")]
    r = compute_reconcile(bom, out, feed, bom_failed_product_ids=["P2"])
    assert "P2" in r.incomplete_products
