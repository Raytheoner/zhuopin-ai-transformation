"""FI5 数据模型 —— 报销审核的输入/输出记录（骨架期只定形，不含引擎逻辑）。

输入：
  · `ExpenseClaim`   报销单头（申请人／部门／期间／合计金额／类型）。
  · `ExpenseLine`    报销明细行（费用科目／金额／发票号／场合与人数）。
  · `BudgetBalance`  预算余额快照（部门 × 科目 × 期间）。
输出：
  · `AuditFinding`   逐行审核结论（命中规则／风险等级／是否需人工／理由）。

🔴 `invoice_no` 的 join 纪律（本项目已实测证伪过一次，勿再默认字面一致）：
FI2 变更包 `fi2-tax-export-ingest`（归档 2026-08-07）真实探测**推翻了「发票号字面 join」
假设**，改用后 8 位 ＋ 客户端 suffix 校验，8/8 真实样本唯一命中。⇒ 本场景凡涉发票号
对碰，**必须先做一次字面一致性实测**（位数／前导零／空格／全半角／代码前缀），实测结论
落档后再定 join 键；**不得直接沿用 FI2 的后 8 位方案**（税务导出与报销发票是两套来源，
FI2 的结论只证明「不能想当然」，没有证明「后 8 位对本场景也成立」）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExpenseClaim:
    """报销单头。"""
    claim_id: str
    claimant: str
    department: str
    period: str                    # 归属期间，如 "2026-09"
    claim_type: str                # 差旅 / 招待 / 办公 / 其他
    total_amount: float
    submitted_at: str = ""


@dataclass
class ExpenseLine:
    """报销明细行。"""
    claim_id: str
    line_no: int
    account: str                   # 费用科目
    amount: float
    invoice_no: Optional[str] = None   # 🔴 join 纪律见模块 docstring
    occasion: str = ""             # 招待场合类型（招待类必填）
    headcount: Optional[int] = None    # 招待人数（人均限额判定用）
    travel_grade: str = ""         # 申请人职级（差旅标准判定用）
    nights: Optional[int] = None       # 住宿夜数


@dataclass
class BudgetBalance:
    """预算余额快照（部门 × 科目 × 期间）。"""
    department: str
    account: str
    period: str
    budget_amount: float
    used_amount: float

    @property
    def remaining(self) -> float:
        return self.budget_amount - self.used_amount


@dataclass
class AuditFinding:
    """逐行审核结论。

    引擎填：`rule_ids` / `risk_grade` / `needs_manual_review` / `reason`。
    🔴 `needs_manual_review=True` 时一律不自动结案（L2 门禁，根 CLAUDE.md §7-4）。
    """
    claim_id: str
    line_no: int
    rule_ids: list[str] = field(default_factory=list)
    risk_grade: str = ""           # 由 config.RISK_GRADE_BOUNDARIES 判定；未签认前引擎须 fail-loud
    needs_manual_review: bool = True   # 🔴 默认需人工——放行才是须被判据显式证成的那一侧
    reason: str = ""
    rule_version: str = ""
