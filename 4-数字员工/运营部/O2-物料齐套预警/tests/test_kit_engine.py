"""explode_bom 引擎测试（先写测试）。"""
import pytest
from zhuopin_platform.shared_tools.models import BomRow, ProductionPlan
from o2_kit_shortage.kit_engine import explode_bom


def _plan(product_id: str, qty: int) -> ProductionPlan:
    return ProductionPlan(
        plan_id="P001", product_id=product_id,
        product_name=product_id, planned_qty=qty, planned_date="2026-07-01",
    )


def _bom(product_id: str, component_id: str, qty: float, loss: float = 0.0) -> BomRow:
    return BomRow(
        product_id=product_id, component_id=component_id,
        component_name=component_id, level=1,
        qty_per_unit=qty, loss_rate=loss, unit="PCS",
    )


class TestExplodeBom:

    def test_single_level_gross_demand(self):
        """单层 BOM：毛需求 = 生产计划量 × 用量 × (1 + 损耗率)。"""
        bom = [_bom("FIN001", "MAT001", qty=2, loss=0.05)]
        plans = [_plan("FIN001", 100)]
        result = explode_bom(bom, plans)
        assert result == {"MAT001": pytest.approx(210.0, rel=1e-6)}

    def test_two_level_recursive_expansion(self):
        """两层 BOM：中间件 SUB001 继续展开，自身不进结果。"""
        bom = [
            _bom("FIN001", "SUB001", qty=1, loss=0.0),
            _bom("SUB001", "MAT002", qty=3, loss=0.0),
        ]
        plans = [_plan("FIN001", 100)]
        result = explode_bom(bom, plans)
        assert "SUB001" not in result
        assert result == {"MAT002": pytest.approx(300.0, rel=1e-6)}

    def test_multi_product_demand_merged(self):
        """多成品依赖同一物料时合并求和。"""
        bom = [
            _bom("FIN001", "MAT001", qty=2),
            _bom("FIN002", "MAT001", qty=2),
        ]
        plans = [_plan("FIN001", 50), _plan("FIN002", 50)]
        result = explode_bom(bom, plans)
        assert result == {"MAT001": pytest.approx(200.0, rel=1e-6)}

    def test_circular_reference_no_infinite_loop(self):
        """循环引用（A → B → A）时正常返回，不死循环。"""
        bom = [
            _bom("A", "B", qty=1),
            _bom("B", "A", qty=1),
        ]
        plans = [_plan("A", 10)]
        result = explode_bom(bom, plans)
        # 循环不爆栈，返回空或有限结果均可（B 既是子件也是父件，A 再遇到时跳过）
        assert isinstance(result, dict)

    def test_loss_rate_zero_no_markup(self):
        """损耗率 0 时毛需求无放大。"""
        bom = [_bom("FIN001", "MAT001", qty=5, loss=0.0)]
        plans = [_plan("FIN001", 10)]
        result = explode_bom(bom, plans)
        assert result == {"MAT001": pytest.approx(50.0, rel=1e-6)}

    def test_three_level_loss_accumulates(self):
        """三层 BOM 损耗率逐层累乘。
        FIN001 → SUB001（qty=1, loss=0.1）→ MAT001（qty=2, loss=0.1）
        计划 100 件：
          SUB001 毛需求 = 100 × 1 × 1.1 = 110
          MAT001 毛需求 = 110 × 2 × 1.1 = 242
        """
        bom = [
            _bom("FIN001", "SUB001", qty=1, loss=0.1),
            _bom("SUB001", "MAT001", qty=2, loss=0.1),
        ]
        plans = [_plan("FIN001", 100)]
        result = explode_bom(bom, plans)
        assert "SUB001" not in result
        assert result == {"MAT001": pytest.approx(242.0, rel=1e-6)}
