"""数据接入层（design D1/D6/D10/D11，spec: fi2-feed-source）—— 三单四表统一接口：mock / csv 应急桥接 / u9c 直读。

v3 口径修正（2026-07-09）：核对对象改 AP 单 vs INV，PO/GR 保留加载（PO 作 AP-PO 单价前置
参照，GR 本次匹配数学暂不消费，供未来 FI2-1 完整性校验用）。发票挂载 `ap_no`（U9C 应付单
附件语义），按 `ap_no` 关联 AP↔Invoice；`(po_no, line_no)` 仍用于 AP↔PO 单价前置参照关联。
切源不改匹配引擎/分类逻辑：
  · mock：贴口径备稿字段的夹具（单测/回归）。
  · csv ：应急桥接（同字段约定，接口先搭，真实路径待 9 月数据闸接通）。
  · u9c ：U9C 财务接口直读（design D15，队列 #60，2026-07-20 起 PO/GR/AP 三单可用）——
    注入 `u9c_connector`+`ap_doc_nos` 时按 AP 单号驱动真实查询（AP→去重 SrcPONo/SrcRcvNo
    →PO/GR）；未注入连接器时维持 fail-loud（不静默回退 mock/csv）。发票（Invoice）默认仍
    fail-loud（Attachment/OCR 未就绪，队列 #59），但 design D19（队列 #214/§四#43，
    2026-08-03）新增例外：显式提供 `invoice_sample_dir`（人工誊录小样目录）时改读该目录，
    未提供则行为不变。付款（Payment）u9c 源下始终 fail-loud，不受本次改动影响。
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional as _Opt

from pydantic import BaseModel, field_validator

from zhuopin_platform.shared_tools.connector_errors import RealEndpointNotReadyError

from . import config as _config
from .models import APLine, GRNLine, InvoiceLine, POLine, PaymentRecord


def _read_csv(path: Path | str) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# ── Pydantic 边界校验（脏数据挡在接入层）─────────────────────────────────────

class _POLineRow(BaseModel):
    po_no: str
    line_no: str
    item_code: str
    qty: float
    unit_price: float
    tax_rate: float
    amount: float
    supplier: _Opt[str] = ""
    po_date: _Opt[str] = ""

    @field_validator("po_no", "line_no", "item_code", mode="before")
    @classmethod
    def _require(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("必填字段不能为空")
        return str(v).strip()

    @field_validator("qty", "unit_price", "tax_rate", "amount", mode="before")
    @classmethod
    def _coerce(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("数值字段不能为空")
        return float(v)


class _GRNRow(BaseModel):
    grn_no: str
    po_no: str
    line_no: str
    item_code: str
    recv_qty: float
    recv_date: _Opt[str] = ""

    @field_validator("grn_no", "po_no", "line_no", "item_code", mode="before")
    @classmethod
    def _require(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("必填字段不能为空")
        return str(v).strip()

    @field_validator("recv_qty", mode="before")
    @classmethod
    def _coerce(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("recv_qty 不能为空")
        return float(v)


class _APLineRow(BaseModel):
    """应付单明细行边界校验（v3 新增）。"""
    ap_no: str
    po_no: str
    line_no: str
    item_code: str
    qty: float
    unit_price: float
    untaxed_amount: float
    tax_amount: float
    ap_date: _Opt[str] = ""

    @field_validator("ap_no", "po_no", "line_no", "item_code", mode="before")
    @classmethod
    def _require(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("必填字段不能为空")
        return str(v).strip()

    @field_validator("qty", "unit_price", "untaxed_amount", "tax_amount", mode="before")
    @classmethod
    def _coerce(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("数值字段不能为空")
        return float(v)


class _InvoiceRow(BaseModel):
    """发票明细行边界校验（v3 修正4 字段：挂载 ap_no，字段贴 INV 票面）。"""
    inv_no: str
    ap_no: str
    item_code: str
    unit: _Opt[str] = ""
    unit_price: float
    inv_qty: float
    untaxed_amount: float
    tax_rate: float
    tax_amount: float
    inv_date: _Opt[str] = ""

    @field_validator("inv_no", "ap_no", "item_code", mode="before")
    @classmethod
    def _require(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("必填字段不能为空")
        return str(v).strip()

    @field_validator("unit_price", "inv_qty", "untaxed_amount", "tax_rate", "tax_amount", mode="before")
    @classmethod
    def _coerce(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("数值字段不能为空")
        return float(v)


class _PaymentRow(BaseModel):
    pay_no: str
    inv_no: str
    pay_amount: float
    pay_date: _Opt[str] = ""

    @field_validator("pay_no", "inv_no", mode="before")
    @classmethod
    def _require(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("必填字段不能为空")
        return str(v).strip()

    @field_validator("pay_amount", mode="before")
    @classmethod
    def _coerce(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("pay_amount 不能为空")
        return float(v)


def parse_po_lines(rows: list[dict]) -> list[POLine]:
    out: list[POLine] = []
    for raw in rows:
        try:
            r = _POLineRow.model_validate(raw)
        except Exception as e:
            raise ValueError(f"FI2 PO明细行校验失败: {e}") from None
        out.append(POLine(r.po_no, r.line_no, r.item_code, r.qty, r.unit_price,
                           r.tax_rate, r.amount, r.supplier or "", r.po_date or ""))
    return out


def parse_grn(rows: list[dict]) -> list[GRNLine]:
    out: list[GRNLine] = []
    for raw in rows:
        try:
            r = _GRNRow.model_validate(raw)
        except Exception as e:
            raise ValueError(f"FI2 入库单校验失败: {e}") from None
        out.append(GRNLine(r.grn_no, r.po_no, r.line_no, r.item_code, r.recv_qty, r.recv_date or ""))
    return out


def parse_ap_lines(rows: list[dict]) -> list[APLine]:
    """解析应付单明细行（v3 新增，design D10）。"""
    out: list[APLine] = []
    for raw in rows:
        try:
            r = _APLineRow.model_validate(raw)
        except Exception as e:
            raise ValueError(f"FI2 应付单明细行校验失败: {e}") from None
        out.append(APLine(r.ap_no, r.po_no, r.line_no, r.item_code, r.qty, r.unit_price,
                           r.untaxed_amount, r.tax_amount, r.ap_date or ""))
    return out


def parse_invoice(rows: list[dict]) -> list[InvoiceLine]:
    out: list[InvoiceLine] = []
    for raw in rows:
        try:
            r = _InvoiceRow.model_validate(raw)
        except Exception as e:
            raise ValueError(f"FI2 发票行校验失败: {e}") from None
        out.append(InvoiceLine(r.inv_no, r.ap_no, r.item_code, r.unit or "", r.unit_price,
                                r.inv_qty, r.untaxed_amount, r.tax_rate, r.tax_amount, r.inv_date or ""))
    return out


def parse_payment(rows: list[dict]) -> list[PaymentRecord]:
    out: list[PaymentRecord] = []
    for raw in rows:
        try:
            r = _PaymentRow.model_validate(raw)
        except Exception as e:
            raise ValueError(f"FI2 付款凭证校验失败: {e}") from None
        out.append(PaymentRecord(r.pay_no, r.inv_no, r.pay_amount, r.pay_date or ""))
    return out


def partition_invoices(
    ap_lines: list[APLine], invoice_rows: list[InvoiceLine]
) -> tuple[list[InvoiceLine], list[InvoiceLine]]:
    """按 `ap_no` 是否存在对应 AP 单，切分发票为 (可匹配, 孤立) 两组（v3：锚点从 PO 行改 AP 单号）。

    孤立发票（挂载的 ap_no 在 AP 明细行里完全找不到，数据完整性异常——正常流程下发票是
    配票生成的 AP 单附件，理论不应出现）不得进入料品汇总归集当作正常匹配对象——由调用方
    另行标记待处理。
    """
    ap_nos = {a.ap_no for a in ap_lines}
    linked: list[InvoiceLine] = []
    orphaned: list[InvoiceLine] = []
    for inv in invoice_rows:
        (linked if inv.ap_no in ap_nos else orphaned).append(inv)
    return linked, orphaned


def _u9c_str(v) -> str:
    """真实 API 字段可能是 int（如 DocLineNo=10）或 str（如 SrcPOLineNo="240"），统一转 str。"""
    return "" if v is None else str(v)


def _u9c_date(v) -> str:
    """真实 API 日期形如 "2025-12-26T00:00:00"，取日期部分；空值原样返回空串。"""
    return (v or "")[:10]


def _map_u9c_po_row(row: dict) -> dict:
    """`Purchase/Query` 原始行 → `_POLineRow` 字段（design D15-b）。

    `FinalPriceTC` 已实测确认为含税单价（`ConfirmQty×FinalPriceTC=TotalMnyTC`），
    与 AP `TaxPrice` 同基准，R7 单价比对可直接用（design D15-a②）。
    """
    return {
        "po_no": row.get("DocNo"), "line_no": _u9c_str(row.get("DocLineNo")),
        "item_code": row.get("ItemCode"), "qty": row.get("ConfirmQty"),
        "unit_price": row.get("FinalPriceTC"), "tax_rate": row.get("TaxRate"),
        "amount": row.get("NetMnyTC"), "supplier": row.get("SupplierName") or "",
        "po_date": _u9c_date(row.get("BusinessDate")),
    }


def _map_u9c_gr_row(row: dict) -> dict:
    """`GR/Query` 原始行 → `_GRNRow` 字段（design D15-b）。`SrcDocNo`/`SrcDocLineNo`
    = 来源 PO 单号/行号（GR 本次匹配数学暂不消费，见 design D10）。"""
    return {
        "grn_no": row.get("RcvDocNo"), "po_no": row.get("SrcDocNo"),
        "line_no": _u9c_str(row.get("SrcDocLineNo")), "item_code": row.get("ItemCode"),
        "recv_qty": row.get("RcvQtyTU"), "recv_date": _u9c_date(row.get("BusinessDate")),
    }


def _map_u9c_ap_row(row: dict) -> dict:
    """`AP/Query` 原始行 → `_APLineRow` 字段（design D15-b）。`TaxPrice` 已实测确认
    为含税单价（`APQtyTU×TaxPrice=TotalAmtTC`），与 PO `FinalPriceTC` 同基准。"""
    return {
        "ap_no": row.get("DocNo"), "po_no": row.get("SrcPONo"),
        "line_no": _u9c_str(row.get("SrcPOLineNo")), "item_code": row.get("ItemCode"),
        "qty": row.get("APQtyTU"), "unit_price": row.get("TaxPrice"),
        "untaxed_amount": row.get("NonTaxAmtTC"), "tax_amount": row.get("TaxAmtTC"),
        "ap_date": "",  # AP/Query 未提供独立单据日期字段，非匹配引擎消费字段
    }


class FeedSource:
    """三单四表统一加载器（v3：PO/GR/AP/Invoice/Payment）。

    Args:
        data_source: "mock" | "csv" | "u9c"（None → config.DATA_SOURCE_DEFAULT）。
        mock_dir:    mock 夹具目录（含 po_lines.csv/grn.csv/ap_lines.csv/invoice.csv/payment.csv）。
        csv_dir:     应急桥接目录（同字段约定，真实路径待接通）。
        audit:       ConnectorAudit（连接器访问留痕，占位）。
        u9c_connector: `u9c` 源下驱动真实查询的连接器（如 `ZpConnector`，需暴露
            `get_purchase_lines`/`get_gr_lines`/`get_ap_lines(doc_no)` 三方法，design D15；
            批量模式另需 `get_ap_lines_by_supplier(supplier_code)`，design D16）。
            `None`（默认）→ `u9c` 源五个 loader 保持 fail-loud（现状行为不变）。
        ap_supplier_codes: `u9c` 源下按供应商批量取数（design D16，队列 #61 追加）——
            自动分页拉取这些供应商名下**全部** AP 明细行，取代逐单号手工清单。
            与 `ap_doc_nos` 二选一（同时注入时优先批量模式，见 `_fetch_u9c_ap_rows`）。
            `AP/Query` 的 `supplierCode` 过滤此前有服务器端 SQL bug（design D15-a①），
            2026-07-21 已由 IT 修复（队列 #61），本参数才具备可用性。
        ap_doc_nos:  `u9c` 源下待对账的 AP 单号清单（显式给单号的原始 MVP 形态，
            design D15-a①）——`ap_supplier_codes` 未注入时的手工兜底路径，仍受支持
            （如财务专员只想追一批具体单号，不想拉某供应商全量）。
        invoice_sample_dir: `u9c` 源下人工誊录发票小样目录（design D19，队列 #214/
            §四#43）——提供时 `load_invoice()` 改读该目录 `invoice.csv`（同既有
            `parse_invoice`/`_InvoiceRow` 边界校验），不再 fail-loud；`None`（默认）→
            `load_invoice()` 维持现状 fail-loud（Attachment/OCR 未就绪，队列 #59），
            行为与本参数引入前完全一致。仅影响 `load_invoice()`，不影响
            `load_po_lines`/`load_grn`/`load_ap_lines`/`load_payment`。
    """

    def __init__(self, data_source: str | None = None, *, mock_dir: Path | str | None = None,
                 csv_dir: Path | str | None = None, audit=None, cfg=_config,
                 u9c_connector=None, ap_doc_nos: list[str] | None = None,
                 ap_supplier_codes: list[str] | None = None,
                 invoice_sample_dir: Path | str | None = None):
        self.data_source = (data_source or cfg.DATA_SOURCE_DEFAULT).strip().lower()
        self.mock_dir = Path(mock_dir) if mock_dir else None
        self.csv_dir = Path(csv_dir) if csv_dir else None
        self.audit = audit
        self.cfg = cfg
        self.u9c_connector = u9c_connector
        self.ap_doc_nos = list(ap_doc_nos) if ap_doc_nos else None
        self.ap_supplier_codes = list(ap_supplier_codes) if ap_supplier_codes else None
        self.invoice_sample_dir = Path(invoice_sample_dir) if invoice_sample_dir else None
        self._u9c_ap_rows_cache: list[dict] | None = None

    def _dir(self) -> Path:
        if self.data_source == "mock":
            return self.mock_dir
        if self.data_source == "csv":
            return self.csv_dir
        raise ValueError(f"未知 data_source: {self.data_source}")

    def _fetch_u9c_ap_rows(self) -> list[dict]:
        """拉取待对账的 AP 明细行（design D16，队列 #61 追加），同次 FeedSource 实例
        内缓存复用（`load_ap_lines`/`load_po_lines`/`load_grn` 三方共享，避免重复
        网络调用）。两种驱动模式二选一，`ap_supplier_codes` 优先：
          · 批量模式（`ap_supplier_codes`）：按供应商自动分页拉取全部 AP 明细行，
            取代原"手工给单号清单"的 MVP 限制（该限制源于 `AP/Query` 服务器端过滤
            参数 bug，design D15-a①，2026-07-21 已由 IT 修复，见队列 #61）。
          · 手工模式（`ap_doc_nos`）：逐单号精确拉取，D15-a① 原始 MVP 形态，仍受
            支持（财务专员只想追一批具体单号时更直接）。
        """
        if self._u9c_ap_rows_cache is None:
            if self.ap_supplier_codes:
                rows: list[dict] = []
                for code in self.ap_supplier_codes:
                    rows.extend(self.u9c_connector.get_ap_lines_by_supplier(code))
                self._u9c_ap_rows_cache = rows
            elif self.ap_doc_nos:
                rows = []
                for ap_no in self.ap_doc_nos:
                    rows.extend(self.u9c_connector.get_ap_lines(ap_no))
                self._u9c_ap_rows_cache = rows
            else:
                raise ValueError(
                    "u9c 源 + 已注入 u9c_connector 时，FeedSource 需同时注入 "
                    "ap_supplier_codes（批量，按供应商）或 ap_doc_nos（手工，按单号）之一"
                )
        return self._u9c_ap_rows_cache

    def load_po_lines(self) -> list[POLine]:
        if self.data_source == "u9c":
            if self.u9c_connector is None:
                raise RealEndpointNotReadyError("load_po_lines", self.cfg.U9C_FI_NOT_READY)
            po_nos = sorted({r.get("SrcPONo") for r in self._fetch_u9c_ap_rows() if r.get("SrcPONo")})
            rows: list[dict] = []
            for po_no in po_nos:
                rows.extend(self.u9c_connector.get_purchase_lines(po_no))
            return parse_po_lines([_map_u9c_po_row(r) for r in rows])
        return parse_po_lines(_read_csv(self._dir() / "po_lines.csv"))

    def load_grn(self) -> list[GRNLine]:
        if self.data_source == "u9c":
            if self.u9c_connector is None:
                raise RealEndpointNotReadyError("load_grn", self.cfg.U9C_FI_NOT_READY)
            rcv_nos = sorted({r.get("SrcRcvNo") for r in self._fetch_u9c_ap_rows() if r.get("SrcRcvNo")})
            rows: list[dict] = []
            for rcv_no in rcv_nos:
                rows.extend(self.u9c_connector.get_gr_lines(rcv_no))
            return parse_grn([_map_u9c_gr_row(r) for r in rows])
        return parse_grn(_read_csv(self._dir() / "grn.csv"))

    def load_ap_lines(self) -> list[APLine]:
        if self.data_source == "u9c":
            if self.u9c_connector is None:
                raise RealEndpointNotReadyError("load_ap_lines", self.cfg.U9C_FI_NOT_READY)
            return parse_ap_lines([_map_u9c_ap_row(r) for r in self._fetch_u9c_ap_rows()])
        return parse_ap_lines(_read_csv(self._dir() / "ap_lines.csv"))

    def load_invoice(self) -> list[InvoiceLine]:
        if self.data_source == "u9c":
            # design D19（队列 #214/§四#43）：显式提供人工誊录小样目录时读取该目录，
            # 不再 fail-loud——但这不是"发票源已解决"，只是把已知的人工誊录小样接进来；
            # 未提供该参数（默认）时，Attachment/OCR 未就绪（队列 #59）的 fail-loud 行为
            # 与本次改动前完全一致，不静默变化。
            if self.invoice_sample_dir is not None:
                return parse_invoice(_read_csv(self.invoice_sample_dir / "invoice.csv"))
            raise RealEndpointNotReadyError("load_invoice", self.cfg.U9C_FI_NOT_READY)
        return parse_invoice(_read_csv(self._dir() / "invoice.csv"))

    def load_payment(self) -> list[PaymentRecord]:
        if self.data_source == "u9c":
            raise RealEndpointNotReadyError("load_payment", self.cfg.U9C_FI_NOT_READY)
        return parse_payment(_read_csv(self._dir() / "payment.csv"))
