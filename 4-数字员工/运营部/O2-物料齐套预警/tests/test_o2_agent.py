"""O2 数字员工入口测试（先写测试）。"""
import pytest
from pathlib import Path
from zhuopin_platform.shared_tools.models import (
    BomRow, InventoryRow, PurchaseOrder, ProductionPlan,
)
from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.audit.sinks import JsonlSink
from o2_kit_shortage.agent import KitAlertResult, run_kit_alert


def _make_simple_fixtures():
    bom = [
        BomRow("FIN001", "MAT001", "电容 A", 1, qty_per_unit=2.0, loss_rate=0.0, unit="PCS"),
        BomRow("FIN001", "MAT002", "电阻 B", 1, qty_per_unit=3.0, loss_rate=0.0, unit="PCS"),
    ]
    plans = [
        ProductionPlan("P001", "FIN001", "成品 A", planned_qty=100, planned_date="2026-07-01"),
    ]
    inventory = [
        InventoryRow("MAT001", "电容 A", current_stock=300, safety_stock=50, unit="PCS", last_updated="2026-07-01"),
        InventoryRow("MAT002", "电阻 B", current_stock=100, safety_stock=10, unit="PCS", last_updated="2026-07-01"),
    ]
    pos = []
    return bom, plans, inventory, pos


class TestRunKitAlert:

    def test_end_to_end_returns_result(self):
        """mock 数据端到端跑通，返回 KitAlertResult。"""
        bom, plans, inventory, pos = _make_simple_fixtures()
        result = run_kit_alert(bom, plans, inventory, pos)
        assert isinstance(result, KitAlertResult)
        # MAT001: 毛需求200，可用250（300-50），无缺口
        # MAT002: 毛需求300，可用90（100-10），缺口210
        assert "MAT001" not in result.shortages
        assert "MAT002" in result.shortages
        assert result.shortages["MAT002"] == pytest.approx(210.0, rel=1e-6)

    def test_audit_record_written(self, tmp_path):
        """调用后 AuditLogger sink 有一条 kit_shortage_analysis 记录。"""
        bom, plans, inventory, pos = _make_simple_fixtures()
        sink = JsonlSink(tmp_path / "audit.jsonl")
        logger = AuditLogger(sink=sink)

        run_kit_alert(bom, plans, inventory, pos, audit_logger=logger)

        records = sink.read_all()
        assert len(records) == 1
        rec = records[0]
        assert rec["action"] == "kit_shortage_analysis"
        assert rec["scenario"] == "O2"
        assert "products" in rec["decision"]
        assert "shortage_count" in rec["decision"]
        assert "timestamp" in rec

    def test_no_shortage_empty_dict(self):
        """库存全部充足时 shortages 为空 dict，shortage_count == 0。"""
        bom = [BomRow("FIN001", "MAT001", "X", 1, 1.0, 0.0, "PCS")]
        plans = [ProductionPlan("P1", "FIN001", "A", 10, "2026-07-01")]
        inventory = [InventoryRow("MAT001", "X", 1000, 0, "PCS", "2026-07-01")]
        result = run_kit_alert(bom, plans, inventory, [])
        assert result.shortages == {}
        assert result.shortage_count == 0

    def test_result_fields_complete(self):
        """KitAlertResult 所有字段都已填充。"""
        bom, plans, inventory, pos = _make_simple_fixtures()
        result = run_kit_alert(bom, plans, inventory, pos)
        assert result.products
        assert result.gross_demand
        assert result.analyzed_at
        assert isinstance(result.shortage_count, int)

    def test_audit_none_no_error(self):
        """不传 audit_logger 时静默执行，不抛异常。"""
        bom, plans, inventory, pos = _make_simple_fixtures()
        result = run_kit_alert(bom, plans, inventory, pos, audit_logger=None)
        assert isinstance(result, KitAlertResult)
