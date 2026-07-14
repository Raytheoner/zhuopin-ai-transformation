"""B1 多层 BOM 递归分解（半成品子件展开）——姚祖怡批改反馈独立验证过的真实缺口
（F02N.0226 需分解半成品 S02Y.0198，"所有 F 开头需求的共性问题"）。

方案：复用 `kit_engine.explode_bom`（O2/SC7 已用、已测试的递归展开算法），替代
`_gross_need`/`estimate_material_arrivals` 现状的 level==1 硬过滤。单层 BOM（无
半成品）场景验证向后兼容；多层场景验证正确递归到叶子件、loss_rate 跨层复合。
"""
from __future__ import annotations

from datetime import date

import pytest
from zhuopin_platform.shared_tools.models import BomRow

from sc8.baoguan import _gross_need
from sc8.forecast import estimate_material_arrivals
from sc8.models import SalesOrder


def _so(item="S02Y.0035", qty=100):
    return SalesOrder(so_id=f"FO-{item}", customer_id="", customer_name="客户A",
                      item_code=item, qty=qty, required_date="2026-07-20",
                      doc_type="预测订单", item_name="ECU")


def _row(product_id, component_id, qty_per_unit=1.0, loss_rate=0.0, level=1):
    return BomRow(product_id=product_id, component_id=component_id, component_name=component_id,
                  level=level, qty_per_unit=qty_per_unit, loss_rate=loss_rate, unit="PCS")


class TestGrossNeedBackwardCompat:
    """单层 BOM（现状唯一场景）：结果必须与改造前完全一致。"""

    def test_single_level_unchanged(self):
        bom = [_row("F02N.0226", "R01"), _row("F02N.0226", "R02", qty_per_unit=2.0)]
        need = _gross_need(_so("F02N.0226", qty=10), bom)
        assert need == {"R01": 10.0, "R02": 20.0}

    def test_single_level_with_loss_rate_unchanged(self):
        bom = [_row("F02N.0226", "R01", qty_per_unit=1.0, loss_rate=0.1)]
        need = _gross_need(_so("F02N.0226", qty=100), bom)
        assert need["R01"] == pytest.approx(110.0)  # 浮点乘法精度，与原算法表达式同构


class TestGrossNeedMultiLevelExplosion:
    """多层 BOM（半成品子件）：Paul/姚祖怡反馈的真实场景——F02N.0226 需要
    继续分解半成品 S02Y.0198 的子件需求。"""

    def test_semi_finished_component_decomposed_to_leaf(self):
        """F02N.0226 直接子件含半成品 S02Y.0198；S02Y.0198 自己还有子件 R03。
        毛需求应落到叶子件 R03，不应停在半成品 S02Y.0198 本身。"""
        bom = [
            _row("F02N.0226", "R01"),                 # 普通子件（叶子）
            _row("F02N.0226", "S02Y.0198"),           # 半成品子件
            _row("S02Y.0198", "R03", qty_per_unit=2.0),  # 半成品自己的 BOM
        ]
        need = _gross_need(_so("F02N.0226", qty=600), bom)
        assert need == {"R01": 600.0, "R03": 1200.0}
        assert "S02Y.0198" not in need, "半成品本身不应作为需求物料出现，只有叶子件才算"

    def test_multi_level_loss_rate_compounds(self):
        """损耗率跨层复合：母件→半成品(损耗10%)→叶子件(损耗20%)。"""
        bom = [
            _row("TOP", "MID", qty_per_unit=1.0, loss_rate=0.1),
            _row("MID", "LEAF", qty_per_unit=1.0, loss_rate=0.2),
        ]
        need = _gross_need(_so("TOP", qty=100), bom)
        # 100 * 1.1(母→半成品) = 110；110 * 1.2(半成品→叶子) = 132
        assert need == {"LEAF": 132.0}

    def test_three_level_deep_nesting(self):
        """三层嵌套（母件→半成品A→半成品B→叶子件）全部正确展开到叶子。"""
        bom = [
            _row("TOP", "SEMI_A"),
            _row("SEMI_A", "SEMI_B", qty_per_unit=3.0),
            _row("SEMI_B", "LEAF", qty_per_unit=2.0),
        ]
        need = _gross_need(_so("TOP", qty=10), bom)
        assert need == {"LEAF": 60.0}  # 10 * 3 * 2
        assert "SEMI_A" not in need and "SEMI_B" not in need


class TestEstimateMaterialArrivalsMultiLevel:
    """forecast.py::estimate_material_arrivals 的 components 取数同步改叶子件。"""

    def test_components_are_leaf_materials_not_semi_finished(self):
        bom = [
            _row("F02N.0226", "R01"),
            _row("F02N.0226", "S02Y.0198"),
            _row("S02Y.0198", "R03"),
        ]
        mat = estimate_material_arrivals(
            "F02N.0226", bom, srm_deliveries=[], demand_date=date(2026, 7, 20))
        assert set(mat.arrivals.keys()) == {"R01", "R03"}
        assert "S02Y.0198" not in mat.arrivals

    def test_single_level_arrivals_unchanged(self):
        bom = [_row("F02N.0226", "R01"), _row("F02N.0226", "R02")]
        mat = estimate_material_arrivals(
            "F02N.0226", bom, srm_deliveries=[], demand_date=date(2026, 7, 20))
        assert set(mat.arrivals.keys()) == {"R01", "R02"}
