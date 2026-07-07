"""数据接入层单测（spec: fi2-feed-source）。"""
from __future__ import annotations

import pytest

from zhuopin_platform.shared_tools.connector_errors import RealEndpointNotReadyError

from fi2.feed_source import (
    FeedSource,
    parse_grn,
    parse_invoice,
    parse_payment,
    parse_po_lines,
    partition_invoices,
)
from fi2.models import InvoiceLine, POLine


def test_mock_loads_all_four_tables(mock_dir):
    fs = FeedSource("mock", mock_dir=mock_dir)
    po_lines = fs.load_po_lines()
    grn = fs.load_grn()
    invoice = fs.load_invoice()
    payment = fs.load_payment()
    assert len(po_lines) == 10
    assert len(grn) == 9  # PO-5000/10 无 GRN
    assert len(invoice) == 11  # 含 1 张孤立发票 PO-9999
    assert len(payment) == 2


def test_anchors_link_po_grn_invoice(mock_dir):
    fs = FeedSource("mock", mock_dir=mock_dir)
    po_lines = fs.load_po_lines()
    invoice = fs.load_invoice()
    po_keys = {(p.po_no, p.line_no) for p in po_lines}
    inv_keys = {(i.po_no, i.line_no) for i in invoice}
    assert ("PO-1000", "10") in po_keys
    assert ("PO-1000", "10") in inv_keys


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


def test_dirty_invoice_rejected():
    with pytest.raises(ValueError):
        parse_invoice([{"inv_no": "", "po_no": "P1", "line_no": "10", "item_code": "A",
                        "inv_qty": 1, "inv_unit_price": 1, "inv_amount": 1.13, "tax_rate": 0.13}])


def test_dirty_payment_rejected():
    with pytest.raises(ValueError):
        parse_payment([{"pay_no": "PAY1", "inv_no": "", "pay_amount": 100}])


def test_orphan_invoice_partitioned_not_matched():
    po_lines = [POLine("PO-1", "10", "A001", 10, 10, 0.13, 113)]
    invoices = [
        InvoiceLine("INV-1", "PO-1", "10", "A001", 10, 10, 113, 0.13),
        InvoiceLine("INV-2", "PO-9999", "10", "X001", 1, 1, 1.13, 0.13),
    ]
    linked, orphaned = partition_invoices(po_lines, invoices)
    assert [i.inv_no for i in linked] == ["INV-1"]
    assert [i.inv_no for i in orphaned] == ["INV-2"]
