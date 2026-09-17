"""FI3 数据模型 —— 付款申请校验的输入／输出契约。

输入（全部来自 U9C 侧，档 1 以 mock CSV 承载）：
  · `PaymentRequest`   一张付款申请（旁路校验清单的校验对象，乙方案）。
  · `SupplierAccount`  供应商主数据的收款账户（含变更记录）。
  · `Contract`         采购合同（含补充协议／框架／暂估价标记／账期条款）。
  · `PaidVoucher`      已付款凭证（近 12 个月历史 ＋ 增量）。
  · `Prepayment`       预付款台账一条。
  · `FI2MatchResult`   FI2 三单匹配结果（上游，按发票号消费）。
输出：
  · `CheckFinding`     单个子场景的一条校验发现（等级来自 R1，不在此写死）。
  · `ValidationVerdict` 一张申请跑完全部适用校验后的四态结论（🟢/🟡/🔴/🟣）。

🔴 `ValidationVerdict.needs_manual_review` 默认 `True` 且引擎从不改它：本场景 L3，AI 不碰钱。
🔴 收款账号在任何对外呈现（报告／审计 payload）中只留尾 4 位：`mask_account()`。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


def mask_account(account: str) -> str:
    """财务红色数据脱敏：只留尾 4 位（就绪清单 §三 第四条）。"""
    digits = account.strip()
    if len(digits) <= 4:
        return "*" * len(digits)
    return "*" * (len(digits) - 4) + digits[-4:]


@dataclass
class InvoiceRef:
    """付款申请所附的一张发票（发票级累计需要发票额）。"""
    inv_no: str
    inv_amount: float           # 价税合计


@dataclass
class PaymentRequest:
    """一张付款申请。

    `pay_type` 取 `正式`（对已开票应付的付款）或 `预付`（预付款，走 R5 分级）。
    `support_level` 只对预付有意义，取 R5 `support_rank` 之一（无单据／仅申请／有PO／有合同）。
    三个锚点日期供 FI3-6 按账期条款种类取用；缺锚点时到期日算不出、标提醒（不猜）。
    """
    req_no: str
    supplier_id: str
    supplier_name: str
    amount: float                          # 本次申请金额（含税，R4 口径）
    pay_type: str                          # 正式 | 预付
    submitted_on: str                      # YYYY-MM-DD
    account_name: str
    bank_account: str
    bank_name: str
    contract_no: str = ""
    po_nos: tuple[str, ...] = ()
    invoices: tuple[InvoiceRef, ...] = ()
    support_level: str = ""                # 预付用：无单据 | 仅申请 | 有PO | 有合同
    accept_date: str = ""                  # 验收日
    receipt_date: str = ""                 # 到货日
    invoice_date: str = ""                 # 票到日
    is_urgent: bool = False                # 紧急付款（R7 通道）
    deduct_prepay_no: str = ""             # 本次扣回的预付款编号（FI3-3 预付款扣回）


@dataclass
class SupplierAccount:
    """供应商收款账户主数据（一家供应商可有多条：变更留历史）。"""
    supplier_id: str
    account_name: str
    bank_account: str
    bank_name: str
    effective_from: str                    # YYYY-MM-DD
    status: str = "生效"                   # 生效 | 停用
    first_use_confirmed_by: str = ""       # 新账户首用的财务主管确认人（实名）；空＝未确认


@dataclass
class Contract:
    """采购合同（框架合同的子订单通过 `parent_contract_no` 归到父合同汇总）。"""
    contract_no: str
    supplier_id: str
    cap_amount: float                      # 合同上限（含税）
    term_clause: str = ""                  # 账期条款原文，如「验收后30天」「月结60天」「票到后」
    is_framework: bool = False
    parent_contract_no: str = ""
    is_provisional: bool = False           # 暂估价合同
    status: str = "有效"


@dataclass
class PaidVoucher:
    """已付款凭证。"""
    voucher_no: str
    supplier_id: str
    amount: float
    pay_date: str
    inv_no: str = ""
    po_no: str = ""
    contract_no: str = ""


@dataclass
class Prepayment:
    """预付款台账一条。"""
    prepay_no: str
    supplier_id: str
    amount: float
    paid_on: str
    written_off_amount: float = 0.0
    invoice_received: bool = False
    contract_no: str = ""

    @property
    def outstanding(self) -> float:
        return round(self.amount - self.written_off_amount, 2)


@dataclass
class FI2MatchResult:
    """FI2 三单匹配结果（按发票号消费；类别字面沿用 FI2 五类）。"""
    inv_no: str
    ap_no: str
    match_class: str                       # 完全匹配 | 金额微差 | 明细错位 | 数量金额不符 | 无发票支撑


@dataclass
class CheckFinding:
    """一条校验发现。`level` 取 R1 的字面（拦截／提醒／预警／通过），由引擎从注册表取、不在检查器写死。"""
    check_id: str                          # FI3-1 … FI3-6
    code: str                              # R1_SEVERITY_MAP 的 key
    level: str
    reason: str
    evidence: dict = field(default_factory=dict)


@dataclass
class ValidationVerdict:
    """一张申请的四态结论。

    `outcome`：🟢通过 / 🟡提醒放行 / 🔴拦截 / 🟣特批。
    🔴 `needs_manual_review` 恒 `True`（L3）；`automation_level` 由 config 写入，引擎不得改。
    """
    req_no: str
    outcome: str
    findings: list[CheckFinding] = field(default_factory=list)
    due_date: Optional[str] = None         # FI3-6 算出的付款到期日
    special_approval: dict = field(default_factory=dict)   # 🟣 特批：审批人／补齐期限／跟踪清单
    prepay_ageing: list[dict] = field(default_factory=list)  # FI3-5 账龄度量（无阈值）
    needs_manual_review: bool = True
    automation_level: str = ""
    rule_version: str = ""
