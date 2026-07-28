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


# ── config.bom_max_depth()（姚祖怡 07-26 V6 #9 根因修复，队列 #117）───────────

def test_bom_max_depth_defaults_five(monkeypatch):
    monkeypatch.delenv("SC8_BOM_MAX_DEPTH", raising=False)
    assert config.bom_max_depth() == 5


def test_bom_max_depth_explicit_override(monkeypatch):
    monkeypatch.setenv("SC8_BOM_MAX_DEPTH", "3")
    assert config.bom_max_depth() == 3


def test_bom_max_depth_invalid_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("SC8_BOM_MAX_DEPTH", "not-a-number")
    assert config.bom_max_depth() == 5


def test_bom_max_depth_floor_is_one(monkeypatch):
    monkeypatch.setenv("SC8_BOM_MAX_DEPTH", "0")
    assert config.bom_max_depth() == 1


# ── config.po_transit_lookback_days()（#18-c 根因修复，姚祖怡 07-28 判例回件，队列 #139）──

def test_po_transit_lookback_days_defaults_365(monkeypatch):
    monkeypatch.delenv("SC8_PO_TRANSIT_DAYS", raising=False)
    assert config.po_transit_lookback_days() == 365


def test_po_transit_lookback_days_explicit_override(monkeypatch):
    monkeypatch.setenv("SC8_PO_TRANSIT_DAYS", "180")
    assert config.po_transit_lookback_days() == 180


def test_po_transit_lookback_days_invalid_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("SC8_PO_TRANSIT_DAYS", "not-a-number")
    assert config.po_transit_lookback_days() == 365


def test_po_transit_lookback_days_floor_is_one(monkeypatch):
    monkeypatch.setenv("SC8_PO_TRANSIT_DAYS", "0")
    assert config.po_transit_lookback_days() == 1


# ── load_purchase_orders_by_material 默认回溯窗口（#18-c）───────────────────────

class _DaysCapturingConnector:
    """记录调用方实际传入的 days 值（不关心返回内容本身）。"""
    def __init__(self):
        self.seen_days = None

    def get_purchase_orders(self, days=60):
        self.seen_days = days
        return []


def test_default_days_uses_config_lookback(monkeypatch):
    """未显式传 days → 走 config.po_transit_lookback_days()（默认 365），不再硬编码 60。"""
    monkeypatch.delenv("SC8_PO_TRANSIT_DAYS", raising=False)
    conn = _DaysCapturingConnector()
    load_purchase_orders_by_material(connector=conn)
    assert conn.seen_days == 365


def test_explicit_days_overrides_config_default():
    """显式传 days 时仍尊重调用方指定值（不被 config 默认值覆盖）。"""
    conn = _DaysCapturingConnector()
    load_purchase_orders_by_material(connector=conn, days=90)
    assert conn.seen_days == 90


def test_real_open_po_beyond_60_days_now_counted():
    """真实案例复现（姚祖怡 07-28 判例回件 #18-c）：266 天前下单、仍未清的 PO 在新默认
    窗口下应被计入在途未清量（旧 60 天窗口会漏掉）。"""
    old_po = _po("R01D.0006", 3000, 0, "in_transit", po_id="ZPCG20251105008")
    conn = _FakeZpConnector([old_po])   # 忽略 days 值，直接返回全部（模拟真实无服务端日期过滤）
    result = load_purchase_orders_by_material(connector=conn)
    assert result == {"R01D.0006": 3000.0}
