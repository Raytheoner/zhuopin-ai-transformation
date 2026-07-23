"""真实 u9c 快照落盘工具测试（design D18-b，队列 #78）——假连接器，不触网。"""
from __future__ import annotations

import csv

from fi2.dump_u9c_snapshot import dump_snapshot


class _FakeU9cConnector:
    _AP_ROWS = [
        {"DocNo": "AP-S1", "SrcPONo": "PO-S1", "SrcPOLineNo": "10",
         "ItemCode": "X001", "APQtyTU": 10.0, "TaxPrice": 1.0,
         "NonTaxAmtTC": 8.85, "TaxAmtTC": 1.15,
         "SrcRcvNo": "RCV-S1", "SrcRcvLineNo": "10"},
    ]

    def get_ap_lines(self, doc_no):
        return self._AP_ROWS

    def get_purchase_lines(self, doc_no):
        return [{"DocNo": "PO-S1", "DocLineNo": 10, "ItemCode": "X001",
                  "ConfirmQty": 10.0, "FinalPriceTC": 1.0, "TaxRate": 0.13,
                  "NetMnyTC": 8.85, "SupplierName": "测试供应商",
                  "BusinessDate": "2026-01-01T00:00:00"}]

    def get_gr_lines(self, doc_no):
        return [{"RcvDocNo": "RCV-S1", "SrcDocNo": "PO-S1", "SrcDocLineNo": "10",
                  "ItemCode": "X001", "RcvQtyTU": 10.0, "BusinessDate": "2026-01-01T00:00:00"}]


def test_dump_snapshot_writes_five_csvs(tmp_path):
    conn = _FakeU9cConnector()
    counts = dump_snapshot(conn, tmp_path, ap_doc_nos=["AP-S1"])
    assert counts == {"po_lines": 1, "ap_lines": 1, "grn": 1}

    for name in ("po_lines.csv", "ap_lines.csv", "grn.csv", "payment.csv", "invoice.csv"):
        assert (tmp_path / name).exists()

    with open(tmp_path / "ap_lines.csv", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["ap_no"] == "AP-S1"
    assert rows[0]["po_no"] == "PO-S1"
    assert rows[0]["item_code"] == "X001"

    with open(tmp_path / "invoice.csv", encoding="utf-8-sig") as f:
        assert list(csv.DictReader(f)) == []   # 未人工誊录前为空占位表

    with open(tmp_path / "payment.csv", encoding="utf-8-sig") as f:
        assert list(csv.DictReader(f)) == []


def test_dump_snapshot_does_not_overwrite_existing_invoice(tmp_path):
    """重跑快照工具（如补拉一批新 AP）不应覆盖已人工誊录好的 invoice.csv。"""
    conn = _FakeU9cConnector()
    (tmp_path / "invoice.csv").write_text(
        "inv_no,ap_no,item_code,unit,unit_price,inv_qty,untaxed_amount,tax_rate,tax_amount,inv_date\n"
        "INV-1,AP-S1,X001,个,1.0,10,8.85,0.13,1.15,2026-01-01\n",
        encoding="utf-8-sig",
    )
    dump_snapshot(conn, tmp_path, ap_doc_nos=["AP-S1"])
    with open(tmp_path / "invoice.csv", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1 and rows[0]["inv_no"] == "INV-1"
