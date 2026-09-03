"""FI8 数据模型 —— 现金流预测的输入/输出契约（骨架期只定形）。

输入：
  · `ReceivablePlan` / `PayablePlan`  应收/应付计划一条。
  · `PaymentHistory`                  某客户的历史回款记录（回款周期建模输入）。
  · `OpeningBalance`                  期初资金余额。🔴 见下方警告。
输出：
  · `WeeklyCashflow`   逐周现金流预测点。
  · `GapWindow`        资金缺口窗口。
  · `WhatIfScenario`   what-if 情景定义与其影响。

🔴 **`OpeningBalance` 的警告**：本类存在**不代表**银行账户余额已可取。骨架期它承载的是
**合成期初余额**；真实余额的取数授权须财务侧 ＋ CFO 办公室明确（见 `config
.BANK_BALANCE_NOT_AUTHORIZED`）。`source` 字段必填且骨架期只允许 `"synthetic"`。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ReceivablePlan:
    """应收计划一条。"""
    doc_no: str
    customer_id: str
    amount: float
    due_date: str
    period: str = ""
    overdue_days: int = 0
    order_no: str = ""          # 关联在手订单


@dataclass
class PayablePlan:
    """应付计划一条。"""
    doc_no: str
    supplier_id: str
    amount: float
    due_date: str
    period: str = ""
    po_no: str = ""


@dataclass
class PaymentHistory:
    """某客户一笔历史回款（回款周期建模输入）。

    🔴 建模口径（取几个月、中位数还是均值、剔不剔异常单）属判据，在 `config
    .PAYMENT_CYCLE_SAMPLING`，**未签认**。本类只承载事实，不含任何统计口径。
    """
    customer_id: str
    doc_no: str
    due_date: str
    paid_date: str
    amount: float

    @property
    def delay_days(self) -> Optional[int]:
        """逾期天数 ＝ 实付日 − 应付日。纯派生量，不含判据，可在骨架期即用。"""
        from datetime import date

        def _d(s: str) -> Optional[date]:
            try:
                y, m, d = (int(x) for x in s.split("-"))
                return date(y, m, d)
            except (ValueError, AttributeError):
                return None

        due, paid = _d(self.due_date), _d(self.paid_date)
        if due is None or paid is None:
            return None
        return (paid - due).days


@dataclass
class OpeningBalance:
    """期初资金余额。🔴 见模块 docstring 的警告。"""
    as_of_date: str
    amount: float
    source: str                 # 骨架期只允许 "synthetic"；真实取数须 CFO 办公室授权
    currency: str = "CNY"


@dataclass
class WeeklyCashflow:
    """逐周现金流预测点。"""
    week_start: str
    week_index: int             # 相对预测起点的第 N 周（1..12）
    inflow: float = 0.0
    outflow: float = 0.0
    closing_balance: float = 0.0
    horizon: int = 0            # 该点属于哪个预测视界（4/8/12）
    rule_version: str = ""


@dataclass
class GapWindow:
    """资金缺口窗口。

    🔴 `confirmed_by_cfo` 默认 `False`：本场景是 L2（AI 预测预警，**CFO 决策调度**），
    调度动作不由 AI 发起。
    """
    start_week: str
    end_week: str
    min_balance: float
    shortfall: float = 0.0
    confirmed_by_cfo: bool = False
    reason: str = ""
    rule_version: str = ""


@dataclass
class WhatIfScenario:
    """what-if 情景定义与其影响（如「某客户延迟付款 30 天」）。

    🔴 `is_hypothetical` 恒为 `True` 且不可关闭：what-if 结果**不得**与基线预测混在一起
    对外呈现——把假设情景当成预测报出去，是这类工具最典型的误用。
    """
    scenario_id: str
    description: str
    adjustments: dict = field(default_factory=dict)
    baseline_ref: str = ""
    is_hypothetical: bool = True
