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


class _FakeU9cConnector:
    """假连接器（design D15-b）——真实字段形状的样例行，验证映射/缓存/AP 单号驱动。"""

    def __init__(self):
        self.ap_calls: list[str] = []
        self.po_calls: list[str] = []
        self.gr_calls: list[str] = []
        self.supplier_calls: list[str] = []

    _AP_ROWS_BY_DOC = {
        "AP-REAL-1": [
            {"DocNo": "AP-REAL-1", "SrcPONo": "PO-REAL-1", "SrcPOLineNo": "10",
             "ItemCode": "R01A.0175", "APQtyTU": 5000.0, "TaxPrice": 0.42,
             "NonTaxAmtTC": 1858.41, "TaxAmtTC": 241.59,
             "SrcRcvNo": "RCV-REAL-1", "SrcRcvLineNo": "10"},
            {"DocNo": "AP-REAL-1", "SrcPONo": "PO-REAL-1", "SrcPOLineNo": "20",
             "ItemCode": "R01A.0176", "APQtyTU": 100.0, "TaxPrice": 1.0,
             "NonTaxAmtTC": 88.5, "TaxAmtTC": 11.5,
             "SrcRcvNo": "RCV-REAL-1", "SrcRcvLineNo": "20"},
        ],
    }

    def get_ap_lines(self, doc_no):
        self.ap_calls.append(doc_no)
        return self._AP_ROWS_BY_DOC[doc_no]

    def get_ap_lines_by_supplier(self, supplier_code):
        """design D16：批量按供应商——测试用返回值与单号模式的 AP-REAL-1 一致，
        验证下游 PO/GR 派生与字段映射走的是同一条路径。"""
        self.supplier_calls.append(supplier_code)
        return {"ZA0066": self._AP_ROWS_BY_DOC["AP-REAL-1"]}[supplier_code]

    def get_purchase_lines(self, doc_no):
        self.po_calls.append(doc_no)
        assert doc_no == "PO-REAL-1"
        return [
            {"DocNo": "PO-REAL-1", "DocLineNo": 10, "ItemCode": "R01A.0175",
             "ConfirmQty": 5000.0, "FinalPriceTC": 0.42, "TaxRate": 0.13,
             "NetMnyTC": 1858.41, "SupplierName": "厦门信和达电子有限公司",
             "BusinessDate": "2025-12-21T00:00:00"},
            {"DocNo": "PO-REAL-1", "DocLineNo": 20, "ItemCode": "R01A.0176",
             "ConfirmQty": 100.0, "FinalPriceTC": 1.0, "TaxRate": 0.13,
             "NetMnyTC": 88.5, "SupplierName": "厦门信和达电子有限公司",
             "BusinessDate": "2025-12-21T00:00:00"},
        ]

    def get_gr_lines(self, doc_no):
        self.gr_calls.append(doc_no)
        assert doc_no == "RCV-REAL-1"
        return [
            {"RcvDocNo": "RCV-REAL-1", "DocLineNo": 10, "SrcDocNo": "PO-REAL-1",
             "SrcDocLineNo": "10", "ItemCode": "R01A.0175", "RcvQtyTU": 5000.0,
             "BusinessDate": "2026-01-05T00:00:00"},
        ]


def test_u9c_real_connector_ap_driven_three_step_fetch():
    """design D15-b：注入连接器 + ap_doc_nos 后，AP→去重 SrcPONo/SrcRcvNo→PO/GR 三步拉取，
    字段正确映射，AP 行只拉一次（跨 load_ap_lines/load_po_lines/load_grn 缓存复用）。"""
    conn = _FakeU9cConnector()
    fs = FeedSource("u9c", u9c_connector=conn, ap_doc_nos=["AP-REAL-1"])

    ap_lines = fs.load_ap_lines()
    assert len(ap_lines) == 2
    assert ap_lines[0].ap_no == "AP-REAL-1"
    assert ap_lines[0].po_no == "PO-REAL-1" and ap_lines[0].line_no == "10"
    assert ap_lines[0].unit_price == 0.42          # TaxPrice（含税）
    assert ap_lines[0].untaxed_amount == 1858.41
    assert ap_lines[0].tax_amount == 241.59

    po_lines = fs.load_po_lines()
    assert {p.po_no for p in po_lines} == {"PO-REAL-1"}
    assert {p.line_no for p in po_lines} == {"10", "20"}
    first = next(p for p in po_lines if p.line_no == "10")
    assert first.unit_price == 0.42                # FinalPriceTC（含税，同 AP TaxPrice 基准）
    assert first.po_date == "2025-12-21"            # BusinessDate 截断到日期

    grn = fs.load_grn()
    assert len(grn) == 1
    assert grn[0].grn_no == "RCV-REAL-1" and grn[0].po_no == "PO-REAL-1"

    assert conn.ap_calls == ["AP-REAL-1"]           # 三次 load 只拉一次 AP（实例内缓存）
    assert conn.po_calls == ["PO-REAL-1"]           # 去重后只拉一个 PO 单号
    assert conn.gr_calls == ["RCV-REAL-1"]


def test_u9c_real_connector_batch_by_supplier_drives_same_pipeline():
    """design D16（队列 #61 追加）：`ap_supplier_codes` 批量模式走连接器
    `get_ap_lines_by_supplier`，下游 PO/GR 派生与字段映射与手工单号模式完全一致
    （复用同一条 `_fetch_u9c_ap_rows` → 三步拉取管线，只是 AP 行的来源不同）。"""
    conn = _FakeU9cConnector()
    fs = FeedSource("u9c", u9c_connector=conn, ap_supplier_codes=["ZA0066"])

    ap_lines = fs.load_ap_lines()
    assert len(ap_lines) == 2
    assert {a.ap_no for a in ap_lines} == {"AP-REAL-1"}

    po_lines = fs.load_po_lines()
    assert {p.po_no for p in po_lines} == {"PO-REAL-1"}

    grn = fs.load_grn()
    assert len(grn) == 1

    assert conn.supplier_calls == ["ZA0066"]        # 三次 load 只拉一次（缓存复用）
    assert conn.ap_calls == []                       # 批量模式不走单号逐个查询路径


def test_u9c_real_connector_ap_supplier_codes_takes_priority_over_doc_nos():
    """同时注入两种驱动参数时，批量模式优先（design D16）。"""
    conn = _FakeU9cConnector()
    fs = FeedSource("u9c", u9c_connector=conn,
                     ap_supplier_codes=["ZA0066"], ap_doc_nos=["AP-REAL-1"])
    fs.load_ap_lines()
    assert conn.supplier_calls == ["ZA0066"]
    assert conn.ap_calls == []


def test_u9c_real_connector_requires_ap_doc_nos_or_supplier_codes():
    fs = FeedSource("u9c", u9c_connector=_FakeU9cConnector())  # 两者均未传
    with pytest.raises(ValueError):
        fs.load_ap_lines()


def test_u9c_real_connector_invoice_payment_still_failloud():
    """Attachment/OCR 未就绪（队列 #59），u9c 源 Invoice/Payment 无条件 fail-loud，
    不因注入连接器而改变（design D15-b）。未提供 invoice_sample_dir 时，design D19
    引入的例外路径不生效，行为与本次改动前完全一致。"""
    fs = FeedSource("u9c", u9c_connector=_FakeU9cConnector(), ap_doc_nos=["AP-REAL-1"])
    with pytest.raises(RealEndpointNotReadyError):
        fs.load_invoice()
    with pytest.raises(RealEndpointNotReadyError):
        fs.load_payment()


def test_u9c_invoice_sample_dir_overrides_failloud(tmp_path):
    """design D19（队列 #214/§四#43）：u9c 源下显式提供人工誊录发票小样目录时，
    `load_invoice()` 改读该目录，不再 fail-loud；`load_payment()` 不受影响、仍
    fail-loud（本次改动范围明确不含 Payment）。"""
    (tmp_path / "invoice.csv").write_text(
        "inv_no,ap_no,item_code,unit,unit_price,inv_qty,untaxed_amount,tax_rate,tax_amount,inv_date\n"
        "INV-REAL-1,AP-REAL-1,R01A.0175,个,0.371682,5000,1858.41,0.13,241.59,2026-06-01\n",
        encoding="utf-8",
    )
    fs = FeedSource("u9c", u9c_connector=_FakeU9cConnector(), ap_doc_nos=["AP-REAL-1"],
                     invoice_sample_dir=tmp_path)
    invoices = fs.load_invoice()
    assert len(invoices) == 1
    assert invoices[0].inv_no == "INV-REAL-1"
    assert invoices[0].ap_no == "AP-REAL-1"
    assert invoices[0].untaxed_amount == 1858.41

    with pytest.raises(RealEndpointNotReadyError):
        fs.load_payment()


def test_u9c_invoice_sample_dir_still_validates_dirty_rows(tmp_path):
    """人工誊录小样仍走既有 Pydantic 边界校验（同 mock/csv 源），不因来自 u9c 源例外
    路径而放松——脏数据（缺 inv_no）应照常拒收，不静默跳过。"""
    (tmp_path / "invoice.csv").write_text(
        "inv_no,ap_no,item_code,unit,unit_price,inv_qty,untaxed_amount,tax_rate,tax_amount,inv_date\n"
        ",AP-REAL-1,R01A.0175,个,0.37,5000,1850,0.13,240.5,2026-06-01\n",
        encoding="utf-8",
    )
    fs = FeedSource("u9c", u9c_connector=_FakeU9cConnector(), ap_doc_nos=["AP-REAL-1"],
                     invoice_sample_dir=tmp_path)
    with pytest.raises(ValueError):
        fs.load_invoice()


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


# ── 「无 PO 关联」应付行：一行不得打挂整批（队列 #390）────────────────────
#
# 实撞样本：2026-08-24 全量跑 `OP-0823-E` §375 时，`AP-2026010125` 全单只有 1 行、
# 且 `SrcPONo`/`SrcPOLineNo` 双空 ⇒ `_APLineRow` 两个必填校验同时失败 ⇒ 整个 640 单
# 的批量加载当场中止、零产出。
#
# 🔴 本组测试只锁「批量跑得完 ＋ 这类行留可查诊断」。**「费用类应付要不要进三单
# 核对」是唐燕萍的账务口径**（队列 #390 ⒜⒝⒞ 待她拍板），故默认模式刻意仍是
# fail-loud，下面第一个测试就是钉住这一点——不默认生效。

def _ap_raw(ap_no="AP-1", po_no="PO-1", line_no="10", item_code="A001"):
    return {"ap_no": ap_no, "po_no": po_no, "line_no": line_no, "item_code": item_code,
            "qty": 10, "unit_price": 1.13, "untaxed_amount": 10.0, "tax_amount": 1.3}


def test_no_po_link_row_still_fail_loud_by_default():
    """🔴 默认口径不变：无 PO 关联行照旧 fail-loud，不静默跳过（静默丢弃＝无声漏单）。"""
    rows = [_ap_raw(ap_no="AP-2026010125", po_no="", line_no="")]
    with pytest.raises(ValueError):
        parse_ap_lines(rows)
    with pytest.raises(ValueError):
        parse_ap_lines(rows, no_po_link="raise")


def test_fail_loud_message_identifies_the_offending_ap_doc():
    """原消息只有 pydantic 原文，640 单批量挂掉后日志里查不出是哪张单——须能定位。"""
    with pytest.raises(ValueError) as ei:
        parse_ap_lines([_ap_raw(), _ap_raw(ap_no="AP-2026010125", po_no="", line_no="")])
    msg = str(ei.value)
    assert "AP-2026010125" in msg
    assert "第 2 行" in msg
    assert "无 PO 关联" in msg      # 顺带指出可用 divert，别让下一个人重新查一遍


def test_divert_lets_the_whole_batch_finish_and_keeps_the_row_traceable():
    """#390 主诉：一行无 PO 关联不得让整批零产出；被分流的行必须留得下、查得到。"""
    diverted = []
    rows = [
        _ap_raw(ap_no="AP-A", item_code="A001"),
        _ap_raw(ap_no="AP-2026010125", po_no="", line_no="", item_code="FEE01"),
        _ap_raw(ap_no="AP-B", item_code="B001"),
    ]
    lines = parse_ap_lines(rows, no_po_link="divert", diverted=diverted)

    # 批量跑得完：其余行照常产出（此前是整批中止、零产出）
    assert [a.ap_no for a in lines] == ["AP-A", "AP-B"]
    # 留可查诊断：不是丢弃
    assert len(diverted) == 1
    assert diverted[0].ap_no == "AP-2026010125"
    assert diverted[0].item_code == "FEE01"
    assert diverted[0].reason == "no_po_link"
    assert diverted[0].index == 1
    assert diverted[0].raw["ap_no"] == "AP-2026010125"   # 原始行原样留存供人工核对


def test_divert_covers_either_field_empty_not_only_both():
    """实撞样本是双空，但单空（只有 SrcPOLineNo 缺）同样过不了必填校验，一并覆盖。"""
    for po_no, line_no in (("", "10"), ("PO-1", ""), ("", "")):
        diverted = []
        lines = parse_ap_lines([_ap_raw(po_no=po_no, line_no=line_no)],
                               no_po_link="divert", diverted=diverted)
        assert lines == []
        assert len(diverted) == 1


def test_divert_does_not_swallow_real_dirty_data():
    """🔴 分流只对「无 PO 关联」成立；其余脏数据在两种模式下一律照旧 fail-loud。"""
    diverted = []
    with pytest.raises(ValueError):     # 缺 ap_no
        parse_ap_lines([_ap_raw(ap_no="")], no_po_link="divert", diverted=diverted)
    with pytest.raises(ValueError):     # 缺 item_code
        parse_ap_lines([_ap_raw(item_code="")], no_po_link="divert", diverted=diverted)
    with pytest.raises(ValueError):     # qty 非法
        bad = _ap_raw(); bad["qty"] = "abc"
        parse_ap_lines([bad], no_po_link="divert", diverted=diverted)


def test_divert_without_a_place_to_record_is_refused():
    """无处留痕的分流＝静默漏单，本函数不允许——宁可抛错也不悄悄吞掉。"""
    with pytest.raises(ValueError, match="diverted"):
        parse_ap_lines([_ap_raw(po_no="", line_no="")], no_po_link="divert")


def test_unknown_no_po_link_mode_is_refused():
    with pytest.raises(ValueError, match="no_po_link"):
        parse_ap_lines([_ap_raw()], no_po_link="skip")


class _FakeU9cConnectorWithFeeLine(_FakeU9cConnector):
    """批量模式返回值里混一行无 PO 关联的费用类应付（`AP-2026010125` 的形状）。"""

    def get_ap_lines_by_supplier(self, supplier_code):
        self.supplier_calls.append(supplier_code)
        return [
            *self._AP_ROWS_BY_DOC["AP-REAL-1"],
            {"DocNo": "AP-2026010125", "SrcPONo": None, "SrcPOLineNo": None,
             "ItemCode": "FEE.0001", "APQtyTU": 1.0, "TaxPrice": 1000.0,
             "NonTaxAmtTC": 884.96, "TaxAmtTC": 115.04,
             "SrcRcvNo": None, "SrcRcvLineNo": None},
        ]


def test_u9c_batch_mode_survives_fee_line_and_keeps_raw_rows_aligned():
    """批量模式（`ap_supplier_codes`，design D16）端到端：一行费用类应付不再打挂整批。

    ⚠️ 同时钉住 `raw_ap_rows()` 与 `load_ap_lines()` 的「按位置一一对应」既有契约——
    被分流的行必须从 `raw_ap_rows()` 一并剔除，否则 webapp 的 `_u9c_ap_real_line_no`
    会因长度不等整批回落，全表 AP 行号显示悄悄退化（一个不报错的错）。
    """
    conn = _FakeU9cConnectorWithFeeLine()
    fs = FeedSource("u9c", u9c_connector=conn, ap_supplier_codes=["ZA0066"],
                    ap_no_po_link="divert")
    lines = fs.load_ap_lines()

    assert [a.ap_no for a in lines] == ["AP-REAL-1", "AP-REAL-1"]
    assert len(fs.ap_no_po_link_rows) == 1
    assert fs.ap_no_po_link_rows[0].ap_no == "AP-2026010125"
    assert fs.ap_no_po_link_rows[0].raw["item_code"] == "FEE.0001"
    assert len(fs.raw_ap_rows()) == len(lines)
    assert [r["DocNo"] for r in fs.raw_ap_rows()] == ["AP-REAL-1", "AP-REAL-1"]


def test_u9c_batch_mode_default_still_fail_loud_on_fee_line():
    """默认模式下这颗哑雷原样还在——口径未定前不默认生效（队列 #390）。"""
    conn = _FakeU9cConnectorWithFeeLine()
    fs = FeedSource("u9c", u9c_connector=conn, ap_supplier_codes=["ZA0066"])
    with pytest.raises(ValueError, match="AP-2026010125"):
        fs.load_ap_lines()


def test_diverted_rows_do_not_accumulate_across_calls():
    conn = _FakeU9cConnectorWithFeeLine()
    fs = FeedSource("u9c", u9c_connector=conn, ap_supplier_codes=["ZA0066"],
                    ap_no_po_link="divert")
    fs.load_ap_lines()
    fs.load_ap_lines()
    assert len(fs.ap_no_po_link_rows) == 1
