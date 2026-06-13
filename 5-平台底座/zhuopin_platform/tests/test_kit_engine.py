"""底座 kit_engine 单测（task 2.2）。

三组测试：
  1. TestExplodeBom  — 递归展开、子件展开、损耗率累乘、多计划叠加
  2. TestCalcShortage — 可用量公式、在途抵扣、只输出正缺口
  3. TestCycleProtection — visited 集合防循环引用

黄金值用夹具 CSV（全量 3 计划 × 15 物料），与 O2 及 SC5 共用同一数据。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zhuopin_platform.agents.kit_engine import calc_shortage, explode_bom
from zhuopin_platform.shared_tools import csv_loaders
from zhuopin_platform.shared_tools.models import (
    BomRow,
    InventoryRow,
    ProductionPlan,
    PurchaseOrder,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ── helpers ──────────────────────────────────────────────────────────────────

def _bom(product_id, component_id, qty, loss=0.0):
    return BomRow(product_id=product_id, component_id=component_id,
                  component_name="", level=1,
                  qty_per_unit=float(qty), loss_rate=float(loss), unit="个")


def _inv(material_id, stock, safety=0):
    return InventoryRow(material_id=material_id, material_name="",
                        current_stock=stock, safety_stock=safety,
                        unit="个", last_updated="2026-01-01")


def _po(material_id, ordered, received=0):
    return PurchaseOrder(po_id="PO-X", material_id=material_id,
                         qty_ordered=ordered, qty_received=received,
                         expected_date="2026-05-10",
                         supplier_confirmed_date="2026-05-10",
                         supplier_id="S001", status="in_transit")


def _plan(product_id, qty):
    return ProductionPlan(plan_id="PP-X", product_id=product_id,
                          product_name="", planned_qty=qty,
                          planned_date="2026-05-10")


# ── 1. explode_bom ────────────────────────────────────────────────────────────

class TestExplodeBom:
    def test_single_level_no_loss(self):
        bom = [_bom("P1", "M1", 10), _bom("P1", "M2", 5)]
        plans = [_plan("P1", 100)]
        gross = explode_bom(bom, plans)
        assert gross["M1"] == pytest.approx(1000.0)
        assert gross["M2"] == pytest.approx(500.0)

    def test_single_level_with_loss_rate(self):
        bom = [_bom("P1", "M1", 100, loss=0.02)]
        plans = [_plan("P1", 500)]
        gross = explode_bom(bom, plans)
        # 500 × 100 × 1.02
        assert gross["M1"] == pytest.approx(51000.0)

    def test_sub_assembly_expansion(self):
        """SUB001 是子件 → 展开至叶节点 M6/M7，不出现在 gross 结果中。"""
        bom = [
            _bom("P1", "SUB1", 1, loss=0.0),
            _bom("SUB1", "M6", 2, loss=0.005),
            _bom("SUB1", "M7", 20, loss=0.02),
        ]
        plans = [_plan("P1", 500)]
        gross = explode_bom(bom, plans)
        assert "SUB1" not in gross
        assert gross["M6"] == pytest.approx(500 * 2 * 1.005)
        assert gross["M7"] == pytest.approx(500 * 20 * 1.02)

    def test_loss_rate_cumulative_through_sub_assembly(self):
        """损耗率逐层累乘：P1 → SUB(qty=2, loss=0.1) → M1(qty=3, loss=0.05)。"""
        bom = [
            _bom("P1", "SUB1", 2, loss=0.1),
            _bom("SUB1", "M1", 3, loss=0.05),
        ]
        plans = [_plan("P1", 100)]
        gross = explode_bom(bom, plans)
        # P1(100) × SUB(2×1.1=220) × M1(3×1.05=3.15) = 693
        assert gross["M1"] == pytest.approx(100 * 2 * 1.1 * 3 * 1.05)

    def test_multiple_plans_summed(self):
        bom = [_bom("P1", "M1", 10)]
        plans = [_plan("P1", 100), _plan("P1", 50)]
        gross = explode_bom(bom, plans)
        assert gross["M1"] == pytest.approx(1500.0)

    def test_empty_plan_returns_empty(self):
        bom = [_bom("P1", "M1", 10)]
        assert explode_bom(bom, []) == {}

    def test_golden_baseline_fixture(self):
        """全量夹具：3 计划 / 15 物料黄金值。"""
        bom = csv_loaders.load_bom(FIXTURES)
        plans = csv_loaders.load_production_plan(FIXTURES)
        gross = explode_bom(bom, plans)

        # 子件 SUB001 不出现
        assert "SUB001" not in gross

        # P001(500) + P002(300) + P003(200) 各自贡献 M001 和 M002
        assert gross["M001"] == pytest.approx(64260.0)  # 51000+9180+4080
        assert gross["M002"] == pytest.approx(33660.0)  # 25500+6120+2040
        assert gross["M015"] == pytest.approx(904.5)    # 300×3×1.005
        assert gross["M006"] == pytest.approx(1005.0)   # 500×2×1.005


# ── 2. calc_shortage ──────────────────────────────────────────────────────────

class TestCalcShortage:
    def test_no_shortage_when_stock_sufficient(self):
        gross = {"M1": 100.0}
        inv = [_inv("M1", stock=200, safety=0)]
        result, _missing = calc_shortage(gross, inv, [])
        assert "M1" not in result

    def test_shortage_equals_gap(self):
        gross = {"M1": 500.0}
        inv = [_inv("M1", stock=300, safety=50)]  # available=250
        result, _missing = calc_shortage(gross, inv, [])
        assert result["M1"] == pytest.approx(250.0)  # 500-250

    def test_in_transit_po_reduces_shortage(self):
        gross = {"M1": 500.0}
        inv = [_inv("M1", stock=100, safety=0)]   # without PO: gap=400
        po = _po("M1", ordered=300, received=0)   # in_transit=300 → available=400
        result, _missing = calc_shortage(gross, [inv[0]], [po])
        assert result["M1"] == pytest.approx(100.0)  # 500-400

    def test_partially_received_po(self):
        gross = {"M1": 500.0}
        inv = [_inv("M1", stock=100, safety=0)]
        po = _po("M1", ordered=300, received=200)  # in_transit=100 → available=200
        result, _missing = calc_shortage(gross, [inv[0]], [po])
        assert result["M1"] == pytest.approx(300.0)  # 500-200

    def test_missing_inventory_row_no_po_is_full_gap(self):
        """无库存记录且无在途：可用量=0，缺口=全部毛需求；该物料进 missing 告警清单。"""
        gross = {"UNKNOWN": 250.0}
        result, missing = calc_shortage(gross, [], [])
        assert result["UNKNOWN"] == pytest.approx(250.0)
        assert "UNKNOWN" in missing

    def test_missing_inventory_row_still_counts_in_transit(self):
        """B6 核心：物料不在库存快照但有在途 → 在途仍计入，不再高估缺口。"""
        gross = {"UNKNOWN": 250.0}
        po = _po("UNKNOWN", ordered=200, received=0)   # in_transit=200
        result, missing = calc_shortage(gross, [], [po])
        assert result["UNKNOWN"] == pytest.approx(50.0)   # 250-200（旧逻辑会算 250）
        assert "UNKNOWN" in missing                        # 仍提示缺快照

    def test_safety_stock_reduces_available(self):
        gross = {"M1": 100.0}
        inv = [_inv("M1", stock=200, safety=150)]  # available=50
        result, _missing = calc_shortage(gross, inv, [])
        assert result["M1"] == pytest.approx(50.0)

    def test_only_positive_gaps_returned(self):
        gross = {"M1": 50.0, "M2": 300.0}
        inv = [_inv("M1", stock=100, safety=0), _inv("M2", stock=100, safety=0)]
        result, _missing = calc_shortage(gross, inv, [])
        assert "M1" not in result         # 50-100 < 0
        assert result["M2"] == pytest.approx(200.0)

    def test_golden_baseline_fixture(self):
        """全量夹具黄金值：5 种缺料物料，数值精确对齐 O2 场景。"""
        bom = csv_loaders.load_bom(FIXTURES)
        plans = csv_loaders.load_production_plan(FIXTURES)
        inv = csv_loaders.load_inventory(FIXTURES)
        pos = csv_loaders.load_purchase_orders(FIXTURES)

        gross = explode_bom(bom, plans)
        shortages, _missing = calc_shortage(gross, inv, pos)

        # M001 有 30000 在途，不缺货
        assert "M001" not in shortages

        assert shortages["M002"] == pytest.approx(8660.0)
        assert shortages["M003"] == pytest.approx(720.0)
        assert shortages["M006"] == pytest.approx(605.0)
        assert shortages["M010"] == pytest.approx(523.0)
        assert shortages["M015"] == pytest.approx(754.5)
        assert len(shortages) == 5


# ── 3. 防循环引用 ──────────────────────────────────────────────────────────────

class TestCycleProtection:
    def test_direct_cycle_does_not_hang(self):
        """A → B → A 循环引用，应在 visited 集合截断，不死循环。"""
        bom = [
            _bom("A", "B", 1),
            _bom("B", "A", 1),  # 循环
        ]
        plans = [_plan("A", 10)]
        # 不应抛异常 / 无限递归，只要能返回即通过
        result = explode_bom(bom, plans)
        assert isinstance(result, dict)

    def test_indirect_cycle_does_not_hang(self):
        """A → B → C → A 间接循环，同样能正常返回。"""
        bom = [
            _bom("A", "B", 2),
            _bom("B", "C", 3),
            _bom("C", "A", 1),  # 间接循环
        ]
        plans = [_plan("A", 5)]
        result = explode_bom(bom, plans)
        assert isinstance(result, dict)

    def test_dag_without_cycle_processes_correctly(self):
        """有向无环图（共享子件）：M_leaf 从两条路径贡献，不被 visited 误截断。"""
        # A → B → M_leaf
        # A → C → M_leaf
        # B 和 C 共享同一叶件 M_leaf（不同路径，非循环）
        bom = [
            _bom("A", "B", 1),
            _bom("A", "C", 1),
            _bom("B", "M_leaf", 5),
            _bom("C", "M_leaf", 3),
        ]
        plans = [_plan("A", 10)]
        result = explode_bom(bom, plans)
        # B路径: 10×1×5=50, C路径: 10×1×3=30 → total=80
        assert result["M_leaf"] == pytest.approx(80.0)
