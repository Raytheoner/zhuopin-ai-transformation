"""数据接入层（design D1/D6，spec: fi2-feed-source）—— 三单四表统一接口：mock / csv 应急桥接 / u9c 直读。

四表按 (po_no, line_no) 关联 PO↔GRN↔Invoice、按 inv_no 关联 Invoice↔Payment。
切源不改匹配引擎/分类逻辑：
  · mock：贴口径备稿字段的夹具（单测/回归）。
  · csv ：应急桥接（同字段约定，接口先搭，真实路径待 9 月数据闸接通）。
  · u9c ：U9C 财务接口直读，端点未开放 → fail-loud（不静默回退 mock/csv）。
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional as _Opt

from pydantic import BaseModel, field_validator

from zhuopin_platform.shared_tools.connector_errors import RealEndpointNotReadyError

from . import config as _config
from .models import GRNLine, InvoiceLine, POLine, PaymentRecord


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


class _InvoiceRow(BaseModel):
    inv_no: str
    po_no: str
    line_no: str
    item_code: str
    inv_qty: float
    inv_unit_price: float
    inv_amount: float
    tax_rate: float
    inv_date: _Opt[str] = ""

    @field_validator("inv_no", "po_no", "line_no", "item_code", mode="before")
    @classmethod
    def _require(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("必填字段不能为空")
        return str(v).strip()

    @field_validator("inv_qty", "inv_unit_price", "inv_amount", "tax_rate", mode="before")
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


def parse_invoice(rows: list[dict]) -> list[InvoiceLine]:
    out: list[InvoiceLine] = []
    for raw in rows:
        try:
            r = _InvoiceRow.model_validate(raw)
        except Exception as e:
            raise ValueError(f"FI2 发票行校验失败: {e}") from None
        out.append(InvoiceLine(r.inv_no, r.po_no, r.line_no, r.item_code, r.inv_qty,
                                r.inv_unit_price, r.inv_amount, r.tax_rate, r.inv_date or ""))
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
    po_lines: list[POLine], invoice_rows: list[InvoiceLine]
) -> tuple[list[InvoiceLine], list[InvoiceLine]]:
    """按 (po_no, line_no) 是否存在对应 PO 行，切分发票为 (可匹配, 孤立) 两组。

    孤立发票（找不到 PO 行）不得进入四维比对当正常匹配对象——由调用方另行标记待处理。
    """
    po_keys = {(p.po_no, p.line_no) for p in po_lines}
    linked: list[InvoiceLine] = []
    orphaned: list[InvoiceLine] = []
    for inv in invoice_rows:
        (linked if (inv.po_no, inv.line_no) in po_keys else orphaned).append(inv)
    return linked, orphaned


class FeedSource:
    """三单四表统一加载器。

    Args:
        data_source: "mock" | "csv" | "u9c"（None → config.DATA_SOURCE_DEFAULT）。
        mock_dir:    mock 夹具目录（含 po_lines.csv/grn.csv/invoice.csv/payment.csv）。
        csv_dir:     应急桥接目录（同字段约定，真实路径待接通）。
        audit:       ConnectorAudit（连接器访问留痕，占位）。
    """

    def __init__(self, data_source: str | None = None, *, mock_dir: Path | str | None = None,
                 csv_dir: Path | str | None = None, audit=None, cfg=_config):
        self.data_source = (data_source or cfg.DATA_SOURCE_DEFAULT).strip().lower()
        self.mock_dir = Path(mock_dir) if mock_dir else None
        self.csv_dir = Path(csv_dir) if csv_dir else None
        self.audit = audit
        self.cfg = cfg

    def _dir(self) -> Path:
        if self.data_source == "mock":
            return self.mock_dir
        if self.data_source == "csv":
            return self.csv_dir
        raise ValueError(f"未知 data_source: {self.data_source}")

    def load_po_lines(self) -> list[POLine]:
        if self.data_source == "u9c":
            raise RealEndpointNotReadyError("load_po_lines", self.cfg.U9C_FI_NOT_READY)
        return parse_po_lines(_read_csv(self._dir() / "po_lines.csv"))

    def load_grn(self) -> list[GRNLine]:
        if self.data_source == "u9c":
            raise RealEndpointNotReadyError("load_grn", self.cfg.U9C_FI_NOT_READY)
        return parse_grn(_read_csv(self._dir() / "grn.csv"))

    def load_invoice(self) -> list[InvoiceLine]:
        if self.data_source == "u9c":
            raise RealEndpointNotReadyError("load_invoice", self.cfg.U9C_FI_NOT_READY)
        return parse_invoice(_read_csv(self._dir() / "invoice.csv"))

    def load_payment(self) -> list[PaymentRecord]:
        if self.data_source == "u9c":
            raise RealEndpointNotReadyError("load_payment", self.cfg.U9C_FI_NOT_READY)
        return parse_payment(_read_csv(self._dir() / "payment.csv"))
