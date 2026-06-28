"""差异分类规则注册表单测（spec: fi1-variance-classify）。"""
from __future__ import annotations

from fi1.models import ComponentReconcile
from fi1.variance_classify import build_registry, classify, classify_all, rule_version


def _c(theoretical, std_loss, actual, *, bom_incomplete=False):
    variance = round(actual - theoretical, 6)
    pct = round(variance / theoretical, 6) if theoretical > 0 else None
    return ComponentReconcile(
        component_id="C", component_name="件",
        theoretical_net=theoretical, standard_loss=std_loss, actual_feed=actual,
        total_variance=variance, variance_pct=pct, bom_incomplete=bom_incomplete,
    )


def test_within_standard_loss_no_review(cfg):
    # 理论 200，标准损耗 20，实际 215 → 差异 15 ≤ 20 → 标准内
    c = classify(_c(200, 20, 215), cfg)
    assert c.classification == "损耗溢短·标准内"
    assert c.needs_review is False
    assert c.rule_id == "R-STDLOSS"


def test_over_loss_triggers_review(cfg):
    # 理论 100，标准损耗 5，实际 120 → 差异 20 > 5；超损部分 15/100=0.15 > 0.02 → 超损·需人工
    c = classify(_c(100, 5, 120), cfg)
    assert c.classification == "超损"
    assert c.needs_review is True
    assert c.rule_id == "R-OVER"


def test_over_loss_small_within_l2_tolerance(cfg):
    # 理论 100，标准损耗 5，实际 106 → 差异 6 > 5；超损 1/100=0.01 ≤ 0.02 → 超损但不触发 L2
    c = classify(_c(100, 5, 106), cfg)
    assert c.classification == "超损"
    assert c.needs_review is False


def test_shortage_triggers_review(cfg):
    # 理论 500，标准损耗 25，实际 480 → 差异 -20，差异率 -0.04，|−0.04|>0.03 → 来料短缺·需人工
    c = classify(_c(500, 25, 480), cfg)
    assert c.classification == "来料短缺"
    assert c.needs_review is True
    assert c.rule_id == "R-SHORT"


def test_small_shortage_within_tolerance(cfg):
    # 差异率 -0.02 ≤ 0.03 → 来料短缺但不触发 L2
    c = classify(_c(500, 25, 490), cfg)
    assert c.classification == "来料短缺"
    assert c.needs_review is False


def test_no_basis_always_review(cfg):
    c = classify(_c(0, 0, 30, bom_incomplete=True), cfg)
    assert c.classification == "管理差异·无理论基准待核"
    assert c.needs_review is True
    assert c.rule_id == "R-NB"


def test_registry_is_data_driven_and_versioned(cfg):
    reg = build_registry(cfg)
    assert [r.id for r in reg] == ["R-NB", "R-SHORT", "R-STDLOSS", "R-OVER"]
    assert rule_version().startswith("fi1-temp")


def test_classify_all_marks_temp_version():
    items = classify_all([_c(200, 20, 215)])
    assert items[0].classification == "损耗溢短·标准内"
