"""FI2 数据模型 —— 三单四表 + 匹配结果（design D1）。

输入：
  · `POLine` 采购订单明细行（锚点：po_no + line_no）。
  · `GRNLine` 入库单（收货数量，挂 PO 行）。
  · `InvoiceLine` 发票明细行（开票数量/金额/税率，挂 PO 行）。
  · `PaymentRecord` 付款凭证（挂发票号）。
输出：
  · `LineMatch` 逐 PO 行四维比对 + 五类判定结果。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class POLine:
    """采购订单明细行（三单匹配锚点）。"""
    po_no: str
    line_no: str
    item_code: str
    qty: float
    unit_price: float
    tax_rate: float
    amount: float
    supplier: str = ""
    po_date: str = ""


@dataclass
class GRNLine:
    """入库单（收货）。"""
    grn_no: str
    po_no: str
    line_no: str
    item_code: str
    recv_qty: float
    recv_date: str = ""


@dataclass
class InvoiceLine:
    """发票明细行（开票）。"""
    inv_no: str
    po_no: str
    line_no: str
    item_code: str
    inv_qty: float
    inv_unit_price: float
    inv_amount: float
    tax_rate: float
    inv_date: str = ""


@dataclass
class PaymentRecord:
    """付款凭证（挂发票号）。"""
    pay_no: str
    inv_no: str
    pay_amount: float
    pay_date: str = ""


@dataclass
class LineMatch:
    """单 PO 行四维比对 + 分类结果。

    引擎（match_engine）填：has_grn/item_code_match/qty_diff/qty_diff_pct/amount_diff/tax_rate_match。
    分类（result_classify）填：classification/status/needs_review/rule_version。
    """
    po_no: str
    line_no: str
    item_code: str
    has_grn: bool
    has_invoice: bool
    item_code_match: bool
    qty_diff: Optional[float]         # inv_qty - grn_recv_qty；无 GRN 时 None
    qty_diff_pct: Optional[float]     # 相对 GRN 收货量的比例；无 GRN 或收货量为 0 时 None
    amount_diff: Optional[float]      # inv_amount - 应付(grn_recv_qty × po_unit_price × (1+po_tax_rate))；无 GRN 时 None（仅供内部容差判定，不落审计/报告）
    amount_diff_pct: Optional[float]  # amount_diff / 应付金额；无 GRN 或应付为 0 时 None（审计/报告用，金额脱敏）
    tax_rate_match: bool
    # ── 分类（result_classify 填）──
    classification: str = ""
    status: str = ""
    needs_review: bool = False
    rule_version: str = ""
