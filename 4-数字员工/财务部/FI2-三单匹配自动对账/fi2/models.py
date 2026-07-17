"""FI2 数据模型 —— PO/GR/AP/INV + 匹配结果（design D1/D10/D11/D12，v3 口径修正 2026-07-09）。

输入：
  · `POLine` 采购订单明细行（v3：降级为 AP-PO 单价比对的前置参照，不再是逐行匹配主体）。
  · `GRNLine` 入库单（v3：随四表加载保留，本次匹配数学暂不消费，供未来 FI2-1 完整性校验用）。
  · `APLine` 应付单明细行（v3 新增，配票生成，核对锚点——天然带我方料品编码）。
  · `InvoiceLine` 发票明细行（v3：挂载 `ap_no`，U9C 应付单附件语义，字段贴 INV 票面）。
  · `PaymentRecord` 付款凭证（挂发票号，FI3 范畴，本场景仅加载不参与匹配）。
输出：
  · `ItemMatch` 按 `(ap_no, item_code)` 料品级汇总归集的四维比对 + 五类判定结果（v3：替代 v1 逐 PO 行的 `LineMatch`）。
  · `PriceCheckResult` AP-PO 单价强制比对结果（v3 新增，独立于五类判定）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class POLine:
    """采购订单明细行（v3：AP-PO 单价比对的前置参照）。"""
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
    """入库单（收货）。v3：随三表加载保留，匹配数学本次不消费（见 design D10）。"""
    grn_no: str
    po_no: str
    line_no: str
    item_code: str
    recv_qty: float
    recv_date: str = ""


@dataclass
class APLine:
    """应付单明细行（v3 新增，design D10/D11）。

    配票生成，挂 PO 行做单价前置参照；核对锚点——天然带我方料品编码（不同于供应商 INV）。
    """
    ap_no: str
    po_no: str
    line_no: str
    item_code: str
    qty: float
    unit_price: float
    untaxed_amount: float
    tax_amount: float
    ap_date: str = ""


@dataclass
class InvoiceLine:
    """发票明细行（供应商开票，v3 修正4 字段 + 修正1 挂载 AP 单号）。

    v3：`item_code` 为 mock 层代 OCR+《料品↔INV规格型号/项目名称映射表》的输出结果
    （真实场景映射表构建为晋档 2 前置，见 design D11/Non-Goals）。
    """
    inv_no: str
    ap_no: str
    item_code: str
    unit: str
    unit_price: float
    inv_qty: float
    untaxed_amount: float
    tax_rate: float
    tax_amount: float
    inv_date: str = ""


@dataclass
class PaymentRecord:
    """付款凭证（挂发票号，FI3 范畴）。"""
    pay_no: str
    inv_no: str
    pay_amount: float
    pay_date: str = ""


@dataclass
class ItemMatch:
    """AP 单下按料品汇总归集的四维比对 + 分类结果（v3：替代 v1 逐 PO 行 `LineMatch`，design D11）。

    引擎（match_engine）填：has_invoice/qty_diff/qty_diff_pct/untaxed_amount_diff/
    untaxed_amount_diff_pct/tax_amount_diff/tax_amount_diff_pct/ap_tax_rate。
    分类（result_classify）填：classification/status/needs_review/rule_version。
    """
    ap_no: str
    item_code: str
    has_invoice: bool                        # False → 该料品在此 AP 下无发票支撑
    qty_diff: Optional[float]                # inv_qty合计 - ap_qty合计；无发票支撑时 None
    qty_diff_pct: Optional[float]            # 相对 AP 数量合计的比例；AP 数量合计为 0 时 None
    untaxed_amount_diff: Optional[float]     # inv_untaxed合计 - ap_untaxed合计（仅供内部容差判定，不落审计/报告）
    untaxed_amount_diff_pct: Optional[float]  # untaxed_amount_diff / AP 未税金额合计（审计/报告用，金额脱敏）
    tax_amount_diff: Optional[float]         # inv_tax合计 - ap_tax合计（仅供内部容差判定，不落审计/报告）
    tax_amount_diff_pct: Optional[float]     # tax_amount_diff / AP 税额合计（审计/报告用，金额脱敏）
    ap_tax_rate: float                        # AP 侧有效税率（ap_tax合计/ap_untaxed合计），R1"税额随税率"容差换算用；
                                               # ap_untaxed合计为 0（理论异常）时记 0（design D14）
    # ── 分类（result_classify 填）──
    classification: str = ""
    status: str = ""
    needs_review: bool = False
    rule_version: str = ""
    # ── 价格校验合并结果（recon_report 填，design D12）──
    price_check_failed: bool = False


@dataclass
class PriceCheckResult:
    """AP-PO 单价强制比对结果（v3 新增，design D12，R7 容差占位）。"""
    ap_no: str
    po_no: str
    line_no: str
    item_code: str
    has_po: bool               # False → 该 AP 行找不到对应 PO 行（无法比价，视为超差）
    price_diff_pct: Optional[float]   # (ap.unit_price - po.unit_price) / po.unit_price；仅记比例，不落绝对单价
    exceeds_tolerance: bool
