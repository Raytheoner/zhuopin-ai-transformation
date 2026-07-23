"""PO 在途数据接入（sources.load_purchase_orders_by_material，功能批1，2026-07-23）。

按料号汇总在途未清量（status=in_transit/partial 的 qty_ordered−qty_received），
供 #12 子件供给状态 / #14 需求日可齐套数量共享使用。全 mock，不触网。
"""
from __future__ import annotations

from zhuopin_platform.shared_tools.models import PurchaseOrder

from sc8 import config
from sc8.sources import load_purchase_orders_by_material


def _po(material, qty_ordered, qty_received, status, po_id="PO1"):
    return PurchaseOrder(po_id=po_id, material_id=material, qty_ordered=qty_ordered,
                         qty_received=qty_received, expected_date="2026-08-01",
                         supplier_confirmed_date="2026-08-01", supplier_id="V1", status=status)


class _FakeZpConnector:
    def __init__(self, orders):
        self._orders = orders

    def get_purchase_orders(self, days=60):
        return self._orders


def test_aggregates_outstanding_qty_for_in_transit():
    conn = _FakeZpConnector([_po("A", 100, 30, "in_transit")])
    result = load_purchase_orders_by_material(connector=conn)
    assert result == {"A": 70.0}


def test_aggregates_partial_status_too():
    conn = _FakeZpConnector([_po("A", 100, 90, "partial")])
    result = load_purchase_orders_by_material(connector=conn)
    assert result == {"A": 10.0}


def test_received_status_excluded():
    conn = _FakeZpConnector([_po("A", 100, 100, "received")])
    result = load_purchase_orders_by_material(connector=conn)
    assert result == {}


def test_sums_multiple_pos_for_same_material():
    conn = _FakeZpConnector([
        _po("A", 100, 0, "in_transit", po_id="PO1"),
        _po("A", 50, 20, "partial", po_id="PO2"),
    ])
    result = load_purchase_orders_by_material(connector=conn)
    assert result == {"A": 130.0}   # 100 + 30


def test_materials_filter_bounds_result():
    conn = _FakeZpConnector([_po("A", 100, 0, "in_transit"), _po("B", 50, 0, "in_transit")])
    result = load_purchase_orders_by_material({"A"}, connector=conn)
    assert list(result.keys()) == ["A"]


def test_zero_outstanding_not_included():
    """qty_received >= qty_ordered 但 status 仍标 in_transit（数据边缘情况）：不产生 0 记录。"""
    conn = _FakeZpConnector([_po("A", 100, 100, "in_transit")])
    result = load_purchase_orders_by_material(connector=conn)
    assert result == {}


def test_empty_orders_returns_empty_dict():
    conn = _FakeZpConnector([])
    assert load_purchase_orders_by_material(connector=conn) == {}


# ── config.po_transit_enabled() ─────────────────────────────────────────────

def test_po_transit_defaults_on(monkeypatch):
    monkeypatch.delenv("SC8_PO_TRANSIT", raising=False)
    assert config.po_transit_enabled() is True


def test_po_transit_explicit_off(monkeypatch):
    monkeypatch.setenv("SC8_PO_TRANSIT", "off")
    assert config.po_transit_enabled() is False


def test_po_transit_explicit_on(monkeypatch):
    monkeypatch.setenv("SC8_PO_TRANSIT", "on")
    assert config.po_transit_enabled() is True
