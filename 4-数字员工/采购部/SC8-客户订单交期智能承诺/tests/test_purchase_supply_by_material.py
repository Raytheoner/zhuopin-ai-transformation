"""未交 PO 的供应商/制单人汇总（sources.load_purchase_supply_by_material，队列 #334）。

物料看板「供应商名称」列的取数源（design D4-a）。过滤口径必须与既有
`load_purchase_orders_by_material` 逐条一致——两列出现在同一行上，口径不同即自相矛盾。
全 mock，不触网。
"""
from __future__ import annotations

import pytest
from zhuopin_platform.shared_tools.models import PurchaseOrder

from sc8.sources import load_purchase_supply_by_material


def _po(material, *, status="in_transit", ordered=100, received=0, supplier="",
        buyer="", po_id="PO1", line_no=""):
    return PurchaseOrder(po_id=po_id, material_id=material, qty_ordered=ordered,
                         qty_received=received, expected_date="2026-08-01",
                         supplier_confirmed_date="2026-08-01", supplier_id="V1",
                         status=status, line_no=line_no,
                         supplier_name=supplier, buyer=buyer)


class _FakeZpConnector:
    def __init__(self, orders, line_status=None):
        self._orders = orders
        self._line_status = line_status

    def get_purchase_orders(self, days=60):
        return self._orders

    def get_purchase_line_status(self, item_codes):
        if self._line_status is None:
            raise AttributeError("此测试连接器未实现 get_purchase_line_status")
        return dict(self._line_status)


def test_dedupes_and_sorts_multiple_suppliers_for_same_material():
    conn = _FakeZpConnector([
        _po("A", supplier="厦门信和达电子有限公司", buyer="尤胤栋", po_id="P1"),
        _po("A", supplier="厦门信和达电子有限公司", buyer="沈潇敏", po_id="P2"),
        _po("A", supplier="上海森和创电气有限公司", buyer="尤胤栋", po_id="P3"),
    ])
    assert load_purchase_supply_by_material(connector=conn) == {
        "A": {"suppliers": ["上海森和创电气有限公司", "厦门信和达电子有限公司"],
              "buyers": ["尤胤栋", "沈潇敏"]},
    }


def test_material_without_outstanding_po_is_absent():
    conn = _FakeZpConnector([
        _po("A", status="received", ordered=100, received=100, supplier="S1"),
        _po("B", ordered=100, received=100, supplier="S2"),   # 在途但已收清 → 未清量 0
    ])
    assert load_purchase_supply_by_material(connector=conn) == {}


def test_partial_status_counts_and_narrowing_by_materials():
    conn = _FakeZpConnector([_po("A", status="partial", received=90, supplier="S1"),
                             _po("B", supplier="S2")])
    assert load_purchase_supply_by_material({"A"}, connector=conn) == {
        "A": {"suppliers": ["S1"], "buyers": []},
    }


def test_line_closed_rows_are_excluded_same_as_qty_loader():
    """行级关闭三态（3/4/5）不算在途——与 load_purchase_orders_by_material 同口径。"""
    conn = _FakeZpConnector([_po("A", supplier="S1", po_id="P1", line_no="1")],
                            line_status={("P1", "1"): 4})
    assert load_purchase_supply_by_material({"A"}, connector=conn) == {}


def test_line_status_query_failure_is_fail_soft():
    """行级关闭查询失败只放弃这一步修正，不连累既有数量口径下本可得的结果。"""
    conn = _FakeZpConnector([_po("A", supplier="S1", po_id="P1", line_no="1")],
                            line_status=None)   # get_purchase_line_status 抛异常
    assert load_purchase_supply_by_material({"A"}, connector=conn) == {
        "A": {"suppliers": ["S1"], "buyers": []},
    }


def test_blank_supplier_or_buyer_is_not_recorded_as_empty_string():
    conn = _FakeZpConnector([_po("A", supplier="  ", buyer="")])
    assert load_purchase_supply_by_material(connector=conn) == {
        "A": {"suppliers": [], "buyers": []},
    }


def test_connector_error_propagates_caller_decides_degradation():
    """本函数与 load_purchase_orders_by_material 同为 real fail-loud：异常原样上抛，
    由 compute_snapshot 决定降级（见 test_baoguan_service 里的 fail-soft 用例）。"""
    class _Boom:
        def get_purchase_orders(self, days=60):
            raise RuntimeError("ERP unreachable")

    with pytest.raises(RuntimeError):
        load_purchase_supply_by_material(connector=_Boom())


def test_caller_supplied_line_status_is_used_and_not_refetched():
    """调用方传了 line_status 就不再自取（compute_snapshot 靠这个避免把 ERP 查询翻倍）。"""
    class _NoRefetch(_FakeZpConnector):
        def get_purchase_line_status(self, item_codes):
            raise AssertionError("不应再自取：调用方已传入 line_status")

    conn = _NoRefetch([_po("A", supplier="S1", po_id="P1", line_no="1"),
                       _po("B", supplier="S2", po_id="P2", line_no="1")])
    out = load_purchase_supply_by_material({"A", "B"}, connector=conn,
                                           line_status={("P1", "1"): 4})
    assert out == {"B": {"suppliers": ["S2"], "buyers": []}}   # A 的唯一一行已关闭


def test_empty_dict_line_status_means_no_filtering_not_refetch():
    """`{}` 是「预取失败/无从收窄」的合法值，语义＝不做关闭行剔除，**不是**「去自取」。"""
    class _NoRefetch(_FakeZpConnector):
        def get_purchase_line_status(self, item_codes):
            raise AssertionError("不应自取")

    conn = _NoRefetch([_po("A", supplier="S1", po_id="P1", line_no="1")])
    assert load_purchase_supply_by_material({"A"}, connector=conn, line_status={}) == {
        "A": {"suppliers": ["S1"], "buyers": []},
    }
