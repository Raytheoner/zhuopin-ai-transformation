"""O2 数字员工入口：run_kit_alert 薄包装 + 审计接入。"""
from __future__ import annotations

import datetime
from dataclasses import dataclass

from zhuopin_platform.shared_tools.models import (
    BomRow, InventoryRow, PurchaseOrder, ProductionPlan,
)
from zhuopin_platform.audit import AuditLogger, AuditEvent

from .kit_engine import explode_bom, calc_shortage


@dataclass
class KitAlertResult:
    products: list[str]
    gross_demand: dict[str, float]
    shortages: dict[str, float]
    shortage_count: int
    analyzed_at: str


def run_kit_alert(
    bom: list[BomRow],
    plans: list[ProductionPlan],
    inventory: list[InventoryRow],
    purchase_orders: list[PurchaseOrder],
    audit_logger: AuditLogger | None = None,
) -> KitAlertResult:
    """齐套预警入口：展开BOM → 计算缺口 → 写审计 → 返回结果。"""
    gross = explode_bom(bom, plans)
    shortages = calc_shortage(gross, inventory, purchase_orders)

    products = sorted({plan.product_id for plan in plans})
    analyzed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    result = KitAlertResult(
        products=products,
        gross_demand=gross,
        shortages=shortages,
        shortage_count=len(shortages),
        analyzed_at=analyzed_at,
    )

    if audit_logger is not None:
        audit_logger.record(AuditEvent(
            scenario="O2",
            action="kit_shortage_analysis",
            evaluator="auto",
            automation_level="L1",
            decision={
                "products": products,
                "shortage_count": result.shortage_count,
                "shortage_materials": list(shortages.keys()),
                "analyzed_at": analyzed_at,
            },
            data_sources={"bom": "mock", "inventory": "mock", "purchase_orders": "mock"},
        ))

    return result
