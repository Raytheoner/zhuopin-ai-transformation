"""黄金对照测试：两成品 × 三层 BOM，与手工预算偏差 < 1%。

手工预算（此测试的真值来源，保持不变）：

BOM 结构：
  FIN001（100件）→ SUB001（qty=1, loss=0.1）
                      └→ MAT001（qty=2, loss=0.05）
                      └→ MAT002（qty=3, loss=0.0）
  FIN002（50件） → MAT001（qty=4, loss=0.0）
                 → MAT003（qty=1, loss=0.2）

手工毛需求：
  SUB001 中间件，不计入叶节点：
    FIN001 → SUB001：100 × 1 × (1+0.1) = 110 件（中间件）
    MAT001 来自 FIN001：110 × 2 × (1+0.05) = 231.0
    MAT002 来自 FIN001：110 × 3 × (1+0.0) = 330.0
    MAT001 来自 FIN002：50 × 4 × (1+0.0) = 200.0
    MAT003 来自 FIN002：50 × 1 × (1+0.2) = 60.0

  合并 MAT001：231.0 + 200.0 = 431.0
  MAT002：330.0
  MAT003：60.0

库存（用于缺口计算）：
  MAT001：stock=400, safety=50  → 可用=350；缺口=431-350=81.0
  MAT002：stock=500, safety=0   → 可用=500；缺口=0（充足）
  MAT003：stock=20,  safety=5   → 可用=15+在途30=45；缺口=60-45=15.0

在途（PO）：
  MAT003：ordered=40, received=10 → 在途=30
"""
import pytest
from zhuopin_platform.shared_tools.models import (
    BomRow, InventoryRow, PurchaseOrder, ProductionPlan,
)
from o2_kit_shortage.kit_engine import explode_bom, calc_shortage
from o2_kit_shortage.agent import run_kit_alert


# ── fixture 定义 ──────────────────────────────────────────────────────────────

GOLDEN_BOM = [
    BomRow("FIN001", "SUB001", "中间件",   level=1, qty_per_unit=1.0, loss_rate=0.10, unit="PCS"),
    BomRow("SUB001", "MAT001", "电容 A",   level=2, qty_per_unit=2.0, loss_rate=0.05, unit="PCS"),
    BomRow("SUB001", "MAT002", "电阻 B",   level=2, qty_per_unit=3.0, loss_rate=0.00, unit="PCS"),
    BomRow("FIN002", "MAT001", "电容 A",   level=1, qty_per_unit=4.0, loss_rate=0.00, unit="PCS"),
    BomRow("FIN002", "MAT003", "芯片 C",   level=1, qty_per_unit=1.0, loss_rate=0.20, unit="PCS"),
]

GOLDEN_PLANS = [
    ProductionPlan("P001", "FIN001", "成品 A", planned_qty=100, planned_date="2026-07-01"),
    ProductionPlan("P002", "FIN002", "成品 B", planned_qty=50,  planned_date="2026-07-01"),
]

GOLDEN_INVENTORY = [
    InventoryRow("MAT001", "电容 A", current_stock=400, safety_stock=50,  unit="PCS", last_updated="2026-07-01"),
    InventoryRow("MAT002", "电阻 B", current_stock=500, safety_stock=0,   unit="PCS", last_updated="2026-07-01"),
    InventoryRow("MAT003", "芯片 C", current_stock=20,  safety_stock=5,   unit="PCS", last_updated="2026-07-01"),
]

GOLDEN_POS = [
    PurchaseOrder("PO001", "MAT003", qty_ordered=40, qty_received=10,
                  expected_date="2026-07-10", supplier_confirmed_date="2026-07-10",
                  supplier_id="S01", status="in_transit"),
]

# 手工预算真值
EXPECTED_GROSS = {
    "MAT001": 431.0,   # 231.0(来自FIN001) + 200.0(来自FIN002)
    "MAT002": 330.0,
    "MAT003": 60.0,
}
EXPECTED_SHORTAGES = {
    "MAT001": 81.0,    # 431 - (400-50) = 81
    "MAT003": 15.0,    # 60 - (20-5+30) = 15
    # MAT002: 可用500 >= 330，无缺口
}


# ── 测试 ──────────────────────────────────────────────────────────────────────

class TestGoldenKitAnalysis:

    def test_gross_demand_matches_manual_calculation(self):
        """毛需求与手工预算偏差 < 1%。"""
        gross = explode_bom(GOLDEN_BOM, GOLDEN_PLANS)
        for mat_id, expected in EXPECTED_GROSS.items():
            actual = gross.get(mat_id, 0.0)
            rel_err = abs(actual - expected) / expected
            assert rel_err < 0.01, (
                f"{mat_id}: 实际={actual:.4f}, 手工={expected:.4f}, 偏差={rel_err:.4%}"
            )

    def test_shortage_matches_manual_calculation(self):
        """缺口与手工预算偏差 < 1%，充足物料不出现在结果中。"""
        gross = explode_bom(GOLDEN_BOM, GOLDEN_PLANS)
        shortages, _missing = calc_shortage(gross, GOLDEN_INVENTORY, GOLDEN_POS)

        # 验证有缺口的物料
        for mat_id, expected in EXPECTED_SHORTAGES.items():
            actual = shortages.get(mat_id, 0.0)
            rel_err = abs(actual - expected) / expected
            assert rel_err < 0.01, (
                f"{mat_id}: 实际缺口={actual:.4f}, 手工={expected:.4f}, 偏差={rel_err:.4%}"
            )

        # 验证充足物料不在缺口结果中
        assert "MAT002" not in shortages, "MAT002 库存充足，不应出现缺口"

    def test_run_kit_alert_golden_end_to_end(self):
        """run_kit_alert 端到端黄金对照：shortages 与手工值偏差 < 1%。"""
        result = run_kit_alert(GOLDEN_BOM, GOLDEN_PLANS, GOLDEN_INVENTORY, GOLDEN_POS)
        assert result.shortage_count == len(EXPECTED_SHORTAGES)
        for mat_id, expected in EXPECTED_SHORTAGES.items():
            actual = result.shortages.get(mat_id, 0.0)
            rel_err = abs(actual - expected) / expected
            assert rel_err < 0.01, (
                f"{mat_id}: 实际={actual:.4f}, 手工={expected:.4f}, 偏差={rel_err:.4%}"
            )
        assert "MAT002" not in result.shortages
        assert set(result.products) == {"FIN001", "FIN002"}
