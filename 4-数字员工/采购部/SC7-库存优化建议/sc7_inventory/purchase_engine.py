"""
采购建议引擎（收割自 supplychain/src/agents/purchase_recommendation.py，
2026-07-06 v2.3 重排随 SC5 采购推荐引擎一并迁入 SC7 库存优化建议场景）。
import 全走 zhuopin_platform，零 supplychain 运行时依赖。
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from zhuopin_platform.agents.kit_engine import explode_bom
from zhuopin_platform.shared_tools.models import BomRow, ProductionPlan, Supplier

from sc7_inventory.business_rules import BusinessRulePolicy

_SAFETY_DAYS = 3


def calc_purchase_qty(shortage: float, mpq: int, moq: int) -> int:
    """建议采购量 = max(ceil(缺口 / MPQ) × MPQ, MOQ)"""
    rounded_up = math.ceil(shortage / mpq) * mpq
    return max(rounded_up, moq)


def select_supplier(material_id: str, suppliers: list[Supplier]) -> Supplier | None:
    """已认证供应商中选单价最低者；无认证供应商返回 None。"""
    candidates = [s for s in suppliers if s.material_id == material_id and s.is_approved]
    if not candidates:
        return None
    return min(candidates, key=lambda s: s.unit_price)


def calc_order_date(planned_date: date, lead_time_days: int) -> date:
    """最迟下单日 = 计划生产日 - 供应商交期 - 安全提前期"""
    return planned_date - timedelta(days=lead_time_days + _SAFETY_DAYS)


def calc_material_earliest_dates(
    bom: list[BomRow],
    plans: list[ProductionPlan],
    shortages: dict[str, float],
) -> dict[str, date]:
    """为每个缺料物料找最早的生产计划日期。"""
    result: dict[str, date] = {}
    for plan in plans:
        plan_gross = explode_bom(bom, [plan])
        plan_date = date.fromisoformat(plan.planned_date)
        for mid in plan_gross:
            if mid in shortages:
                if mid not in result or plan_date < result[mid]:
                    result[mid] = plan_date
    return result


def build_recommendations(
    shortages: dict[str, float],
    suppliers: list[Supplier],
    material_earliest_date: dict[str, date],
    policy: BusinessRulePolicy | None = None,
) -> list[dict]:
    """将缺料字典转为完整采购建议列表。无认证供应商物料不静默跳过。"""
    if policy is None:
        policy = BusinessRulePolicy()

    recs = []
    for material_id, shortage in shortages.items():
        supplier = select_supplier(material_id, suppliers)
        plan_date = material_earliest_date.get(material_id)

        if supplier is not None:
            purchase_qty = calc_purchase_qty(shortage, supplier.mpq, supplier.moq)
            unit_price = supplier.unit_price
            supplier_id = supplier.supplier_id
            latest_order_date = (
                calc_order_date(plan_date, supplier.lead_time_days) if plan_date else None
            )
        else:
            purchase_qty = 0
            unit_price = 0.0
            supplier_id = None
            latest_order_date = None

        decision = policy.evaluate(purchase_qty, unit_price, supplier_id)
        estimated_cost = purchase_qty * unit_price

        recs.append({
            "material_id": material_id,
            "shortage": shortage,
            "purchase_qty": purchase_qty,
            "supplier_id": supplier_id,
            "unit_price": unit_price,
            "estimated_cost": estimated_cost,
            "latest_order_date": latest_order_date,
            "review_status": decision.status,
            "triggered_rules": decision.triggered_rules,
            "review_reason": decision.reason,
        })

    return recs


def calc_cost_summary(recommendations: list[dict]) -> dict:
    """汇总自动下单和人工审核的采购金额。"""
    auto_total = sum(
        r["estimated_cost"] for r in recommendations if r["review_status"] == "可自动下单"
    )
    review_total = sum(
        r["estimated_cost"] for r in recommendations if r["review_status"] == "待人工审核"
    )
    return {
        "auto_total": auto_total,
        "review_total": review_total,
        "grand_total": auto_total + review_total,
    }
