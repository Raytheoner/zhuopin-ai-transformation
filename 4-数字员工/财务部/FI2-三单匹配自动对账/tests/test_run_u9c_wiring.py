"""`run()`/CLI 对 u9c 真实源的接线（design D18-c，队列 #78）——此前 `run()` 完全没有
`u9c_connector`/`ap_doc_nos`/`ap_supplier_codes` 参数，`FeedSource` 早已支持但从未被
接线。本文件只测"透传是否正确接到 `FeedSource`"，不重复 `test_feed_source.py` 已覆盖
的字段映射/分页/派生管线细节。
"""
from __future__ import annotations

import pytest

from fi2.run import _split_csv_arg, run


class _FakeU9cConnector:
    """最小假连接器：验证 PO/GR/AP 三表能通，Invoice 仍无条件 fail-loud。"""

    def __init__(self):
        self.ap_calls: list[str] = []
        self.supplier_calls: list[str] = []

    _AP_ROWS = [
        {"DocNo": "AP-W1", "SrcPONo": "PO-W1", "SrcPOLineNo": "10",
         "ItemCode": "X001", "APQtyTU": 10.0, "TaxPrice": 1.0,
         "NonTaxAmtTC": 8.85, "TaxAmtTC": 1.15,
         "SrcRcvNo": "RCV-W1", "SrcRcvLineNo": "10"},
    ]

    def get_ap_lines(self, doc_no):
        self.ap_calls.append(doc_no)
        return self._AP_ROWS

    def get_ap_lines_by_supplier(self, supplier_code, **kw):
        self.supplier_calls.append(supplier_code)
        return self._AP_ROWS

    def get_purchase_lines(self, doc_no):
        assert doc_no == "PO-W1"
        return [{"DocNo": "PO-W1", "DocLineNo": 10, "ItemCode": "X001",
                  "ConfirmQty": 10.0, "FinalPriceTC": 1.0, "TaxRate": 0.13,
                  "NetMnyTC": 8.85, "SupplierName": "测试供应商",
                  "BusinessDate": "2026-01-01T00:00:00"}]

    def get_gr_lines(self, doc_no):
        assert doc_no == "RCV-W1"
        return [{"RcvDocNo": "RCV-W1", "SrcDocNo": "PO-W1", "SrcDocLineNo": "10",
                  "ItemCode": "X001", "RcvQtyTU": 10.0, "BusinessDate": "2026-01-01T00:00:00"}]


def test_run_wires_ap_doc_nos_to_feed_source():
    """`run(data_source="u9c", u9c_connector=..., ap_doc_nos=[...])` 应能拉到真实
    PO/AP（此前 `run()` 无此参数，无法测试到这一步；Invoice 仍 fail-loud，符合 D15-b）。"""
    conn = _FakeU9cConnector()
    from zhuopin_platform.shared_tools.connector_errors import RealEndpointNotReadyError
    with pytest.raises(RealEndpointNotReadyError):
        run("u9c", u9c_connector=conn, ap_doc_nos=["AP-W1"])
    assert conn.ap_calls == ["AP-W1"]   # 证明确实驱动到了真实 AP 拉取，只是卡在 Invoice


def test_run_wires_ap_supplier_codes_to_feed_source():
    conn = _FakeU9cConnector()
    from zhuopin_platform.shared_tools.connector_errors import RealEndpointNotReadyError
    with pytest.raises(RealEndpointNotReadyError):
        run("u9c", u9c_connector=conn, ap_supplier_codes=["ZA0066"])
    assert conn.supplier_calls == ["ZA0066"]


def test_run_u9c_without_connector_still_failloud():
    """未传 `u9c_connector`（现状默认）时行为不变——零回归。"""
    from zhuopin_platform.shared_tools.connector_errors import RealEndpointNotReadyError
    with pytest.raises(RealEndpointNotReadyError):
        run("u9c")


@pytest.mark.parametrize("raw,expected", [
    (None, None),
    ("", None),
    ("AP-1", ["AP-1"]),
    ("AP-1,AP-2", ["AP-1", "AP-2"]),
    ("AP-1, AP-2 ,AP-3", ["AP-1", "AP-2", "AP-3"]),
])
def test_split_csv_arg(raw, expected):
    assert _split_csv_arg(raw) == expected
