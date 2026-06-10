"""calc_shortage 缺口计算测试（先写测试）。"""
import pytest
from zhuopin_platform.shared_tools.models import InventoryRow, PurchaseOrder
from o2_kit_shortage.kit_engine import calc_shortage


def _inv(mat_id: str, stock: int, safety: int) -> InventoryRow:
    return InventoryRow(
        material_id=mat_id, material_name=mat_id,
        current_stock=stock, safety_stock=safety,
        unit="PCS", last_updated="2026-07-01",
    )


def _po(mat_id: str, ordered: int, received: int) -> PurchaseOrder:
    return PurchaseOrder(
        po_id="PO001", material_id=mat_id,
        qty_ordered=ordered, qty_received=received,
        expected_date="2026-07-10", supplier_confirmed_date="2026-07-10",
        supplier_id="S01", status="in_transit",
    )


class TestCalcShortage:

    def test_sufficient_inventory_no_shortage(self):
        """库存充足：可用量 ≥ 毛需求，不在返回结果中。"""
        gross = {"MAT001": 100.0}
        inventory = [_inv("MAT001", stock=200, safety=50)]
        result = calc_shortage(gross, inventory, [])
        # 可用量 = 200 - 50 = 150 >= 100
        assert "MAT001" not in result

    def test_shortage_with_in_transit(self):
        """库存不足但加上在途后仍有缺口。"""
        gross = {"MAT001": 200.0}
        inventory = [_inv("MAT001", stock=100, safety=20)]
        pos = [_po("MAT001", ordered=70, received=20)]
        result = calc_shortage(gross, inventory, pos)
        # 可用量 = 100 - 20 + 50(在途) = 130；缺口 = 200 - 130 = 70
        assert result == {"MAT001": pytest.approx(70.0, rel=1e-6)}

    def test_no_inventory_record_full_shortage(self):
        """无库存记录时可用量视为 0，缺口 = 全额毛需求。"""
        gross = {"MAT999": 150.0}
        result = calc_shortage(gross, [], [])
        assert result == {"MAT999": pytest.approx(150.0, rel=1e-6)}

    def test_multiple_po_aggregated(self):
        """同物料多个 PO 在途数量汇总。"""
        gross = {"MAT002": 500.0}
        inventory = [_inv("MAT002", stock=100, safety=0)]
        pos = [
            _po("MAT002", ordered=200, received=50),   # 在途 150
            _po("MAT002", ordered=100, received=0),    # 在途 100
        ]
        result = calc_shortage(gross, inventory, pos)
        # 可用量 = 100 + 250(在途) = 350；缺口 = 500 - 350 = 150
        assert result == {"MAT002": pytest.approx(150.0, rel=1e-6)}

    def test_zero_shortage_not_in_result(self):
        """恰好够用（缺口 = 0）时不出现在结果中。"""
        gross = {"MAT003": 100.0}
        inventory = [_inv("MAT003", stock=150, safety=50)]
        result = calc_shortage(gross, inventory, [])
        # 可用量 = 150 - 50 = 100 = 毛需求，缺口 0
        assert "MAT003" not in result

    def test_safety_stock_reduces_available(self):
        """安全库存正确从可用量中扣减。"""
        gross = {"MAT004": 80.0}
        inventory = [_inv("MAT004", stock=100, safety=30)]
        result = calc_shortage(gross, inventory, [])
        # 可用量 = 100 - 30 = 70 < 80；缺口 = 10
        assert result == {"MAT004": pytest.approx(10.0, rel=1e-6)}
