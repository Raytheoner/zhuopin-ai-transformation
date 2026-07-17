"""数据接入层单测（spec: fi2-feed-source，v3 口径修正 2026-07-09）。"""
from __future__ import annotations

import pytest

from zhuopin_platform.shared_tools.connector_errors import RealEndpointNotReadyError

from fi2.feed_source import (
    FeedSource,
    parse_ap_lines,
    parse_grn,
    parse_invoice,
    parse_payment,
    parse_po_lines,
    partition_invoices,
)
from fi2.models import APLine, InvoiceLine, POLine


def test_mock_loads_all_tables(mock_dir):
    fs = FeedSource("mock", mock_dir=mock_dir)
    po_lines = fs.load_po_lines()
    grn = fs.load_grn()
    ap_lines = fs.load_ap_lines()
    invoice = fs.load_invoice()
    payment = fs.load_payment()
    assert len(po_lines) == 10
    assert len(grn) == 5
    assert len(ap_lines) == 11
    assert len(invoice) == 11  # 含 1 张孤立发票（挂载 ap_no=AP-9999 不存在）
    assert len(payment) == 2


def test_anchors_link_ap_invoice(mock_dir):
    fs = FeedSource("mock", mock_dir=mock_dir)
    ap_lines = fs.load_ap_lines()
    invoice = fs.load_invoice()
    ap_nos = {a.ap_no for a in ap_lines}
    inv_ap_nos = {i.ap_no for i in invoice}
    assert "AP-1000" in ap_nos
    assert "AP-1000" in inv_ap_nos


def test_anchors_link_ap_po_price_reference(mock_dir):
    fs = FeedSource("mock", mock_dir=mock_dir)
    po_lines = fs.load_po_lines()
    ap_lines = fs.load_ap_lines()
    po_keys = {(p.po_no, p.line_no) for p in po_lines}
    assert all((a.po_no, a.line_no) in po_keys for a in ap_lines)


def test_anchors_link_invoice_payment(mock_dir):
    fs = FeedSource("mock", mock_dir=mock_dir)
    payment = fs.load_payment()
    invoice = fs.load_invoice()
    inv_nos = {i.inv_no for i in invoice}
    assert all(p.inv_no in inv_nos for p in payment)


def test_csv_bridge_loads_same_shape(tmp_path):
    (tmp_path / "po_lines.csv").write_text(
        "po_no,line_no,item_code,qty,unit_price,tax_rate,amount\n"
        "PO-1,10,X1,10,10,0.13,113\n", encoding="utf-8")
    fs = FeedSource("csv", csv_dir=tmp_path)
    rows = fs.load_po_lines()
    assert rows[0].po_no == "PO-1"
    assert rows[0].amount == 113


def test_u9c_fail_loud_all_loaders():
    fs = FeedSource("u9c")
    with pytest.raises(RealEndpointNotReadyError):
        fs.load_po_lines()
    with pytest.raises(RealEndpointNotReadyError):
        fs.load_grn()
    with pytest.raises(RealEndpointNotReadyError):
        fs.load_ap_lines()
    with pytest.raises(RealEndpointNotReadyError):
        fs.load_invoice()
    with pytest.raises(RealEndpointNotReadyError):
        fs.load_payment()


def test_dirty_po_line_rejected():
    with pytest.raises(ValueError):
        parse_po_lines([{"po_no": "", "line_no": "10", "item_code": "A", "qty": 1,
                          "unit_price": 1, "tax_rate": 0.13, "amount": 1.13}])  # 缺 po_no
    with pytest.raises(ValueError):
        parse_po_lines([{"po_no": "P1", "line_no": "10", "item_code": "A", "qty": "abc",
                          "unit_price": 1, "tax_rate": 0.13, "amount": 1.13}])  # qty 非法


def test_dirty_grn_rejected():
    with pytest.raises(ValueError):
        parse_grn([{"grn_no": "G1", "po_no": "P1", "line_no": "10", "item_code": "A",
                    "recv_qty": ""}])  # 缺数量


def test_dirty_ap_line_rejected():
    with pytest.raises(ValueError):
        parse_ap_lines([{"ap_no": "", "po_no": "P1", "line_no": "10", "item_code": "A",
                          "qty": 1, "unit_price": 1, "untaxed_amount": 1, "tax_amount": 0.13}])  # 缺 ap_no
    with pytest.raises(ValueError):
        parse_ap_lines([{"ap_no": "AP-1", "po_no": "P1", "line_no": "10", "item_code": "A",
                          "qty": "abc", "unit_price": 1, "untaxed_amount": 1, "tax_amount": 0.13}])  # qty 非法


def test_dirty_invoice_rejected():
    with pytest.raises(ValueError):
        parse_invoice([{"inv_no": "", "ap_no": "AP-1", "item_code": "A", "unit": "件",
                        "unit_price": 1, "inv_qty": 1, "untaxed_amount": 1, "tax_rate": 0.13,
                        "tax_amount": 0.13}])  # 缺 inv_no


def test_dirty_payment_rejected():
    with pytest.raises(ValueError):
        parse_payment([{"pay_no": "PAY1", "inv_no": "", "pay_amount": 100}])


def test_orphan_invoice_partitioned_not_matched():
    ap_lines = [APLine("AP-1", "PO-1", "10", "A001", 10, 10, 100, 13)]
    invoices = [
        InvoiceLine("INV-1", "AP-1", "A001", "件", 10, 10, 100, 0.13, 13),
        InvoiceLine("INV-2", "AP-9999", "X001", "件", 1, 1, 1, 0.13, 0.13),
    ]
    linked, orphaned = partition_invoices(ap_lines, invoices)
    assert [i.inv_no for i in linked] == ["INV-1"]
    assert [i.inv_no for i in orphaned] == ["INV-2"]
