"""卓品 zp ERP 连接器测试（第 6 组）。

验证：
  · 解析：物料主数据→InventoryRow、PurOrder→PurchaseOrder（状态推断）、供应商聚合。
  · 回退：生产计划无 zp 端点 → CSV 回退。
  · D2：_zp_post 写轻量访问痕迹（source=zp_ERP）。
  · 全程 mock，不触 testerp 真实端点。
"""
import json
from pathlib import Path

import pytest

from zhuopin_platform.audit.sinks import JsonlSink
from zhuopin_platform.shared_tools import models
from zhuopin_platform.shared_tools.connector_audit import ConnectorAudit
from zhuopin_platform.shared_tools.connector import DataConnector
from zhuopin_platform.shared_tools.erp_connector import ZpConnector
from zhuopin_platform.shared_tools.erp_connector import connector as erp_mod

FIXTURES = Path(__file__).parent / "fixtures"


def _make_conn(tmp_path, audit=None):
    return ZpConnector(
        base_url="https://testerp.example:4445", user_code="u", ent_code="001",
        org_code="Z", client_id="cid", client_secret="sec",
        fallback_dir=FIXTURES, po_cache_file=tmp_path / "po_cache.json", audit=audit,
    )


def test_is_dataconnector(tmp_path):
    assert isinstance(_make_conn(tmp_path), DataConnector)


def test_get_inventory_parsing(tmp_path, monkeypatch):
    conn = _make_conn(tmp_path)
    canned = [{"itemCode": "R01B.0039", "itemName": "电容", "unitName": "PCS",
               "editDate": "2026-05-20"}]
    monkeypatch.setattr(conn, "_zp_post", lambda *a, **k: canned)
    inv = conn.get_inventory()
    assert len(inv) == 1 and isinstance(inv[0], models.InventoryRow)
    assert inv[0].material_id == "R01B.0039"


def test_get_purchase_orders_status(tmp_path, monkeypatch):
    conn = _make_conn(tmp_path)
    canned = [
        {"erpNo": "PO1", "itemCode": "M1", "qty": 100, "rcvQtyTU": 100,
         "makeDate": "2099-01-01", "deliveryDate": "2099-02-01", "supplyCode": "S1"},
        {"erpNo": "PO2", "itemCode": "M2", "qty": 100, "rcvQtyTU": 30,
         "makeDate": "2099-01-01", "deliveryDate": "2099-02-01", "supplyCode": "S2"},
        {"erpNo": "PO3", "itemCode": "M3", "qty": 100, "rcvQtyTU": 0,
         "makeDate": "2099-01-01", "deliveryDate": "2099-02-01", "supplyCode": "S3"},
    ]
    monkeypatch.setattr(conn, "_zp_post", lambda *a, **k: canned)
    pos = conn.get_purchase_orders(days=99999)
    by_id = {p.po_id: p for p in pos}
    assert by_id["PO1"].status == "received"
    assert by_id["PO2"].status == "partial"
    assert by_id["PO3"].status == "in_transit"


def test_get_suppliers_aggregation(tmp_path, monkeypatch):
    conn = _make_conn(tmp_path)
    canned = [{"supplyCode": "S1", "itemCode": "M1", "finallyPriceTC": 12.5}]
    monkeypatch.setattr(conn, "_zp_post", lambda *a, **k: canned)
    sups = conn.get_suppliers()
    assert len(sups) == 1 and isinstance(sups[0], models.Supplier)
    assert sups[0].unit_price == 12.5


def test_production_plan_falls_back_to_csv(tmp_path):
    """生产计划无 zp 端点 → CSV 回退到夹具。"""
    conn = _make_conn(tmp_path)
    plans = conn.get_production_plan()
    assert len(plans) > 0
    assert all(isinstance(p, models.ProductionPlan) for p in plans)


def test_zp_post_writes_lightweight_trace(tmp_path, monkeypatch):
    """D2：一次 zp API 调用写一条轻量痕迹（source=zp_ERP）。"""
    sink = JsonlSink(tmp_path / "access_trace.jsonl")
    conn = _make_conn(tmp_path, audit=ConnectorAudit(sink=sink))
    monkeypatch.setattr(conn, "_get_token", lambda: "tok")

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps({"code": 200, "data": []}).encode("utf-8")
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", lambda *a, **k: _Resp())

    conn.get_inventory()
    records = sink.read_all()
    assert len(records) == 1
    assert records[0]["source"] == "zp_ERP"
    assert "ZpViewItemMaster" in records[0]["action"]
