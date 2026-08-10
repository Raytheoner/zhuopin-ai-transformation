"""税务导出 Excel 摄取测试（队列 #295，design：fi2-tax-export-ingest）——全程假连接器，不触网。"""
from __future__ import annotations

import csv
import json

import openpyxl
import pytest

from fi2.tax_export_ingest import (
    discover_new_files,
    ingest_directory,
    is_processed,
    load_ledger,
    mark_processed,
    parse_export_workbook,
    resolve_ap_no,
    resolve_item_code,
    save_ledger,
    write_invoice_csv,
)

_HEADER = [
    "序号", "发票代码", "发票号码", "数电发票号码", "销方识别号", "销方名称",
    "购方识别号", "购买方名称", "开票日期", "税收分类编码", "特定业务类型",
    "货物或应税劳务名称", "规格型号", "单位", "数量", "单价", "金额", "税率",
    "税额", "价税合计", "发票来源", "发票票种", "发票状态", "是否正数发票",
    "发票风险等级", "开票人", "备注",
]


def _make_export_xlsx(path, rows, *, header=_HEADER, sheet_name="信息汇总表"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.append(header)
    for r in rows:
        ws.append(r)
    wb.save(path)


def _row(digital_no="26327000000742719331", name="*半导体*场效应管", spec="NVMJS2D5N06CLTWG",
         unit="个", qty=100, unit_price=25.0, amount=None, tax_rate="13%", tax_amount=None,
         date="2026-07-10 11:33:22"):
    amount = amount if amount is not None else round(qty * unit_price, 2)
    tax_amount = tax_amount if tax_amount is not None else round(amount * 0.13, 2)
    return ["1", "", "", digital_no, "SELLER-TAX-ID", "卖方公司", "BUYER-TAX-ID", "买方公司",
            date, "1060105010000000000", "", name, spec, unit, qty, unit_price, amount,
            tax_rate, tax_amount, round(amount + tax_amount, 2), "电子发票服务平台",
            "数电发票（增值税专用发票）", "正常", "是", "正常", "张三", "ZPCG20260101001"]


# ── Excel 解析（3.1）──────────────────────────────────────────────────────

def test_parse_export_workbook_reads_rows(tmp_path):
    p = tmp_path / "sample.xlsx"
    _make_export_xlsx(p, [_row(), _row(digital_no="26327000000742719332")])
    rows = parse_export_workbook(p)
    assert len(rows) == 2
    assert rows[0]["数电发票号码"] == "26327000000742719331"
    assert rows[1]["数电发票号码"] == "26327000000742719332"


def test_parse_export_workbook_accepts_suffixed_sheet_name(tmp_path):
    """队列 #82 真实数据核验：真实批量导出文件的 sheet 名是「信息汇总表1」（带后缀），
    与 round-1 验证样本的精确「信息汇总表」不同，须前缀匹配兼容、不得判为 parse_error。"""
    p = tmp_path / "sample.xlsx"
    _make_export_xlsx(p, [_row()], sheet_name="信息汇总表1")
    rows = parse_export_workbook(p)
    assert len(rows) == 1
    assert rows[0]["数电发票号码"] == "26327000000742719331"


def test_parse_export_workbook_missing_sheet_raises(tmp_path):
    p = tmp_path / "bad.xlsx"
    wb = openpyxl.Workbook()
    wb.active.title = "别的表"
    wb.save(p)
    with pytest.raises(ValueError, match="信息汇总表"):
        parse_export_workbook(p)


def test_parse_export_workbook_missing_field_raises(tmp_path):
    p = tmp_path / "bad_field.xlsx"
    header = [h for h in _HEADER if h != "数电发票号码"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "信息汇总表"
    ws.append(header)
    wb.save(p)
    with pytest.raises(ValueError, match="数电发票号码"):
        parse_export_workbook(p)


def test_parse_export_workbook_skips_blank_rows(tmp_path):
    p = tmp_path / "sample.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "信息汇总表"
    ws.append(_HEADER)
    ws.append(_row())
    ws.append([None] * len(_HEADER))
    wb.save(p)
    rows = parse_export_workbook(p)
    assert len(rows) == 1


# ── 已处理清单（3.2）──────────────────────────────────────────────────────

def test_ledger_roundtrip_and_idempotency(tmp_path):
    ledger_path = tmp_path / "ledger.json"
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    f1 = export_dir / "a.xlsx"
    _make_export_xlsx(f1, [_row()])

    ledger = load_ledger(ledger_path)
    assert ledger == {}

    new_files = discover_new_files(export_dir, ledger)
    assert len(new_files) == 1
    path, file_hash = new_files[0]
    mark_processed(ledger, file_hash, path.name, row_count=1, processed_at="2026-08-07T00:00:00Z")
    save_ledger(ledger_path, ledger)

    # 重跑：同内容文件应被跳过
    ledger2 = load_ledger(ledger_path)
    assert is_processed(ledger2, file_hash)
    assert discover_new_files(export_dir, ledger2) == []


def test_same_filename_different_content_is_new(tmp_path):
    ledger_path = tmp_path / "ledger.json"
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    f1 = export_dir / "a.xlsx"
    _make_export_xlsx(f1, [_row()])
    ledger = load_ledger(ledger_path)
    _, h1 = discover_new_files(export_dir, ledger)[0]
    mark_processed(ledger, h1, "a.xlsx", row_count=1, processed_at="t1")
    save_ledger(ledger_path, ledger)

    # 同名文件内容变化（追加一行）→ 哈希变化 → 应被视为新文件
    _make_export_xlsx(f1, [_row(), _row(digital_no="26327000000742719999")])
    ledger2 = load_ledger(ledger_path)
    new_files = discover_new_files(export_dir, ledger2)
    assert len(new_files) == 1
    assert new_files[0][1] != h1


# ── ap_no 反查（3.3）──────────────────────────────────────────────────────

class _FakeApByInvoiceConnector:
    """模拟服务端 CONTAINS 语义：返回集合可能包含非真实候选（InvoiceNo 恰好含查询串
    但并非真正匹配），resolve_ap_no 必须靠客户端 suffix 校验滤掉噪声。"""

    def __init__(self, rows_by_query: dict[str, list[dict]]):
        self._rows_by_query = rows_by_query

    def get_ap_lines_by_invoice_no(self, invoice_no):
        return self._rows_by_query.get(invoice_no, [])


def test_resolve_ap_no_unique_hit_full_string_stored():
    digital_no = "26322000005633189671"
    conn = _FakeApByInvoiceConnector({
        digital_no[-8:]: [
            {"DocNo": "AP-2026070071", "InvoiceNo": digital_no},
            {"DocNo": "AP-2026070071", "InvoiceNo": digital_no},
        ],
    })
    ap_no, reason, detail = resolve_ap_no(conn, digital_no)
    assert ap_no == "AP-2026070071"
    assert reason == ""


def test_resolve_ap_no_unique_hit_suffix_only_stored():
    digital_no = "26327000000742719331"
    conn = _FakeApByInvoiceConnector({
        digital_no[-8:]: [{"DocNo": "AP-2026070036", "InvoiceNo": digital_no[-8:]}],
    })
    ap_no, reason, detail = resolve_ap_no(conn, digital_no)
    assert ap_no == "AP-2026070036"
    assert reason == ""


def test_resolve_ap_no_filters_out_contains_noise():
    """服务端 CONTAINS 噪声：候选行的 InvoiceNo 恰好含查询子串但不是右侧子串关系，
    客户端 suffix 校验必须把它滤掉，不得误采信。"""
    digital_no = "26322000005633189671"
    suffix = digital_no[-8:]
    conn = _FakeApByInvoiceConnector({
        suffix: [
            {"DocNo": "AP-REAL", "InvoiceNo": digital_no},              # 真正匹配
            {"DocNo": "AP-NOISE", "InvoiceNo": "9" + suffix + "9"},     # 噪声：非右侧子串
        ],
    })
    ap_no, reason, detail = resolve_ap_no(conn, digital_no)
    assert ap_no == "AP-REAL"
    assert reason == ""


def test_resolve_ap_no_zero_match():
    conn = _FakeApByInvoiceConnector({})
    ap_no, reason, detail = resolve_ap_no(conn, "26322000005633189671")
    assert ap_no is None
    assert reason == "ap_no_zero_match"


def test_resolve_ap_no_ambiguous_multiple_ap_docs():
    digital_no = "26322000005633189671"
    suffix = digital_no[-8:]
    conn = _FakeApByInvoiceConnector({
        suffix: [
            {"DocNo": "AP-A", "InvoiceNo": digital_no},
            {"DocNo": "AP-B", "InvoiceNo": suffix},
        ],
    })
    ap_no, reason, detail = resolve_ap_no(conn, digital_no)
    assert ap_no is None
    assert reason == "ap_no_ambiguous"
    assert "AP-A" in detail and "AP-B" in detail


# ── item_code 反查（3.4）──────────────────────────────────────────────────

def test_resolve_item_code_unique_match():
    ap_lines = [
        {"ItemCode": "R02E.0217", "APQtyTU": 183.0, "TaxPrice": 28.6},
        {"ItemCode": "R02E.0217", "APQtyTU": 157.0, "TaxPrice": 28.6},
        {"ItemCode": "R02E.0208", "APQtyTU": 250.0, "TaxPrice": 17.0},
    ]
    # 未税单价 25.3097345132743 * 1.13 ≈ 28.6
    item_code, reason, detail = resolve_item_code(ap_lines, qty=183.0, untaxed_unit_price=25.3097345132743, tax_rate=0.13)
    assert item_code == "R02E.0217"
    assert reason == ""


def test_resolve_item_code_zero_match_when_qty_not_in_ap_lines():
    """真实场景：发票把 AP 的多笔批次合并成一行（33+67=100），单笔 qty=100 在 AP
    明细中找不到匹配——必须如实标记未解析，不得猜测归到最接近的一行。"""
    ap_lines = [
        {"ItemCode": "R02E.0217", "APQtyTU": 33.0, "TaxPrice": 28.6},
        {"ItemCode": "R02E.0217", "APQtyTU": 67.0, "TaxPrice": 28.6},
    ]
    item_code, reason, detail = resolve_item_code(ap_lines, qty=100.0, untaxed_unit_price=25.3097345132743, tax_rate=0.13)
    assert item_code is None
    assert reason == "item_code_zero_match"


def test_resolve_item_code_ambiguous_same_qty_price_different_items():
    ap_lines = [
        {"ItemCode": "X001", "APQtyTU": 10.0, "TaxPrice": 5.0},
        {"ItemCode": "X002", "APQtyTU": 10.0, "TaxPrice": 5.0},
    ]
    item_code, reason, detail = resolve_item_code(ap_lines, qty=10.0, untaxed_unit_price=5.0 / 1.13, tax_rate=0.13)
    assert item_code is None
    assert reason == "item_code_ambiguous"
    assert "X001" in detail and "X002" in detail


# ── 端到端编排（3.5）──────────────────────────────────────────────────────

class _FakeFullConnector:
    def __init__(self, invoice_rows, ap_lines_by_ap_no):
        self._invoice_rows = invoice_rows
        self._ap_lines_by_ap_no = ap_lines_by_ap_no

    def get_ap_lines_by_invoice_no(self, invoice_no):
        return self._invoice_rows.get(invoice_no, [])

    def get_ap_lines(self, ap_no):
        return self._ap_lines_by_ap_no.get(ap_no, [])


def test_ingest_directory_end_to_end_produces_invoice_csv(tmp_path):
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    digital_no = "26327000000742719331"
    _make_export_xlsx(export_dir / "one.xlsx", [
        _row(digital_no=digital_no, qty=10, unit_price=100.0, tax_rate="13%"),
    ])

    conn = _FakeFullConnector(
        invoice_rows={digital_no[-8:]: [{"DocNo": "AP-1", "InvoiceNo": digital_no}]},
        ap_lines_by_ap_no={"AP-1": [{"ItemCode": "X001", "APQtyTU": 10.0, "TaxPrice": 113.0}]},
    )

    ledger_path = tmp_path / "ledger.json"
    result = ingest_directory(export_dir, ledger_path, conn, now="2026-08-07T00:00:00Z")

    assert result.files_processed == ["one.xlsx"]
    assert result.files_skipped == []
    assert len(result.resolved_rows) == 1
    row = result.resolved_rows[0]
    assert row["ap_no"] == "AP-1"
    assert row["item_code"] == "X001"
    assert row["inv_no"] == digital_no
    assert row["inv_qty"] == 10
    assert result.diagnostics == []

    out_csv = tmp_path / "out" / "invoice.csv"
    write_invoice_csv(result.resolved_rows, out_csv)
    with open(out_csv, encoding="utf-8-sig") as f:
        written = list(csv.DictReader(f))
    assert len(written) == 1
    assert written[0]["ap_no"] == "AP-1"
    assert written[0]["item_code"] == "X001"

    # 幂等：同一目录再摄取一次，文件已在清单中，不重复产出
    result2 = ingest_directory(export_dir, ledger_path, conn, now="2026-08-07T01:00:00Z")
    assert result2.files_processed == []
    assert result2.files_skipped == ["one.xlsx"]
    assert result2.resolved_rows == []


def test_ingest_directory_unresolved_rows_are_diagnosed_not_dropped_silently(tmp_path):
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    digital_no = "26327000000742719331"
    _make_export_xlsx(export_dir / "one.xlsx", [_row(digital_no=digital_no)])

    conn = _FakeFullConnector(invoice_rows={}, ap_lines_by_ap_no={})   # 零命中
    ledger_path = tmp_path / "ledger.json"
    result = ingest_directory(export_dir, ledger_path, conn, now="2026-08-07T00:00:00Z")

    assert result.resolved_rows == []
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].reason == "ap_no_zero_match"
    assert result.diagnostics[0].digital_invoice_no == digital_no
    # 文件仍应计入已处理（该发票已被诊断过，不会每次重跑都重新报告同一未解析行）
    assert result.files_processed == ["one.xlsx"]


def test_ingest_directory_parse_error_file_produces_file_level_diagnostic(tmp_path):
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    wb = openpyxl.Workbook()
    wb.active.title = "别的表"
    wb.save(export_dir / "bad.xlsx")

    conn = _FakeFullConnector(invoice_rows={}, ap_lines_by_ap_no={})
    ledger_path = tmp_path / "ledger.json"
    result = ingest_directory(export_dir, ledger_path, conn, now="2026-08-07T00:00:00Z")

    assert result.resolved_rows == []
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].reason == "parse_error"
    assert result.diagnostics[0].row_index is None


def test_write_invoice_csv_appends_to_existing_file(tmp_path):
    out_csv = tmp_path / "invoice.csv"
    write_invoice_csv([{
        "inv_no": "INV-1", "ap_no": "AP-1", "item_code": "X001", "unit": "个",
        "unit_price": 1.0, "inv_qty": 10, "untaxed_amount": 8.85, "tax_rate": 0.13,
        "tax_amount": 1.15, "inv_date": "2026-01-01",
    }], out_csv)
    write_invoice_csv([{
        "inv_no": "INV-2", "ap_no": "AP-2", "item_code": "X002", "unit": "个",
        "unit_price": 2.0, "inv_qty": 5, "untaxed_amount": 8.85, "tax_rate": 0.13,
        "tax_amount": 1.15, "inv_date": "2026-01-02",
    }], out_csv)
    with open(out_csv, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert [r["inv_no"] for r in rows] == ["INV-1", "INV-2"]
