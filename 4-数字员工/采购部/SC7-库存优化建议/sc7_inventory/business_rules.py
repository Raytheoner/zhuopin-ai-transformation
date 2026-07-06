"""
采购审核业务规则集中管理（收割自 supplychain/src/agents/business_rules.py，
2026-07-06 v2.3 重排随 SC5 采购推荐引擎一并迁入 SC7）。

Phase 2 规则：
    R1_amount_threshold    — 单次采购金额 ≥ 50 万元 → 人工审核
    R2_unapproved_supplier — 无认证供应商           → 人工审核
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ReviewDecision:
    status: str
    triggered_rules: list[str] = field(default_factory=list)
    reason: str = ""


class BusinessRulePolicy:
    AMOUNT_THRESHOLD = 500_000

    def evaluate(self, qty: int, unit_price: float, supplier_id: str | None) -> ReviewDecision:
        triggered: list[str] = []
        reasons: list[str] = []

        amount = qty * unit_price
        if amount >= self.AMOUNT_THRESHOLD:
            triggered.append("R1_amount_threshold")
            reasons.append(f"采购金额 {amount:,.0f} 元 ≥ 50万阈值")

        if supplier_id is None:
            triggered.append("R2_unapproved_supplier")
            reasons.append("无认证供应商，需人工指派")

        if triggered:
            return ReviewDecision(
                status="待人工审核",
                triggered_rules=triggered,
                reason="；".join(reasons),
            )
        return ReviewDecision(
            status="可自动下单",
            triggered_rules=[],
            reason="金额未超阈值且供应商已认证",
        )
