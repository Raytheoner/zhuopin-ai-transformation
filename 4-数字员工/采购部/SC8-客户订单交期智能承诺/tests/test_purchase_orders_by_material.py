"""PO 在途数据接入（sources.load_purchase_orders_by_material，功能批1，2026-07-23）。

按料号汇总在途未清量（status=in_transit/partial 的 qty_ordered−qty_received），
供 #12 子件供给状态 / #14 需求日可齐套数量共享使用。全 mock，不触网。
"""
from __future__ import annotations

from zhuopin_platform.shared_tools.models import PurchaseOrder

from sc8 import config
from sc8.sources import PO_LINE_STATUS_CLOSED, load_purchase_orders_by_material


def _po(material, qty_ordered, qty_received, status, po_id="PO1", line_no=""):
    return PurchaseOrder(po_id=po_id, material_id=material, qty_ordered=qty_ordered,
                         qty_received=qty_received, expected_date="2026-08-01",
                         supplier_confirmed_date="2026-08-01", supplier_id="V1", status=status,
                         line_no=line_no)


class _FakeZpConnector:
    def __init__(self, orders, line_status=None):
        self._orders = orders
        self._line_status = line_status   # {(po_id, line_no): LineStatus}，None=不实现该方法

    def get_purchase_orders(self, days=60):
        return self._orders

    def get_purchase_line_status(self, item_codes):
        if self._line_status is None:
            raise AttributeError("此测试连接器未实现 get_purchase_line_status")
        return dict(self._line_status)


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


# ── 行级关闭状态过滤（队列 #173，#139④ 根治，2026-08-03）───────────────────────

def test_line_status_closed_excludes_line_despite_quantity_heuristic():
    """真实场景：短缺关闭（LineStatus=4）的行 qty_received 永远追不上 qty_ordered，
    纯数量启发式会一直误判 partial——行级关闭状态应优先剔除。"""
    po = _po("A", 5000, 0, "partial", po_id="ZPCG1", line_no="210")
    conn = _FakeZpConnector([po], line_status={("ZPCG1", "210"): 4})
    result = load_purchase_orders_by_material({"A"}, connector=conn)
    assert result == {}


def test_line_status_open_still_counted():
    """LineStatus=2（已审核未交清，真实在途）不受影响，仍计入未清量。"""
    po = _po("A", 100, 30, "in_transit", po_id="ZPCG1", line_no="10")
    conn = _FakeZpConnector([po], line_status={("ZPCG1", "10"): 2})
    result = load_purchase_orders_by_material({"A"}, connector=conn)
    assert result == {"A": 70.0}


def test_line_status_lookup_failure_degrades_to_quantity_only():
    """get_purchase_line_status 查询失败（fail-soft）：不影响既有纯数量口径行为。"""
    po = _po("A", 100, 30, "in_transit", po_id="ZPCG1", line_no="10")
    conn = _FakeZpConnector([po])   # line_status=None → 调用即抛 AttributeError
    result = load_purchase_orders_by_material({"A"}, connector=conn)
    assert result == {"A": 70.0}   # 与改造前完全一致，未被静默吞掉


def test_line_status_not_queried_without_materials_filter():
    """materials 为 None（不收窄）时跳过行级状态查询，行为与改造前完全一致。"""
    po = _po("A", 100, 30, "in_transit", po_id="ZPCG1", line_no="10")
    conn = _FakeZpConnector([po], line_status={("ZPCG1", "10"): 4})  # 即便有数据也不查
    result = load_purchase_orders_by_material(connector=conn)  # materials=None
    assert result == {"A": 70.0}


def test_po_line_status_closed_constants_match_it_semantics():
    """IT 陈承 2026-07-30 回件：3=自然关闭/4=短缺关闭/5=超额关闭。"""
    assert PO_LINE_STATUS_CLOSED == frozenset({3, 4, 5})


def test_real_open_po_beyond_60_days_now_counted():
    """真实案例复现（姚祖怡 07-28 判例回件 #18-c）：266 天前下单、仍未清的 PO 在新默认
    窗口下应被计入在途未清量（旧 60 天窗口会漏掉）。"""
    old_po = _po("R01D.0006", 3000, 0, "in_transit", po_id="ZPCG20251105008")
    conn = _FakeZpConnector([old_po])   # 忽略 days 值，直接返回全部（模拟真实无服务端日期过滤）
    result = load_purchase_orders_by_material(connector=conn)
    assert result == {"R01D.0006": 3000.0}
