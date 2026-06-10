"""
SC3 在途跟踪引擎（收割自 supplychain/src/agents/supplier_tracking.py）。
纯算法，不含审计/通知胶水——引擎与场景胶水分离，便于未来搬移复用。

import 全走 zhuopin_platform，零 supplychain 运行时依赖。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from zhuopin_platform.shared_tools.models import (
    BomRow,
    InventoryRow,
    ProductionPlan,
)


# ---------------------------------------------------------------------------
# compute_dos（D2=A：SC3 场景本地）
# 当第 2 个消费方出现时，提升到 zhuopin_platform/shared_tools/supply_metrics.py。
# ---------------------------------------------------------------------------

def compute_dos(
    inventory: list[InventoryRow],
    bom: list[BomRow],
    plans: list[ProductionPlan],
    planning_days: int = 14,
) -> dict[str, float]:
    """
    计算各物料的可用天数（DOS）。
    只展开 level=1 的直接组件（不递归），与生产计划简单对应。
    DOS = (current_stock - safety_stock) / 日均需求；无需求物料返回 inf。
    """
    gross_req: dict[str, float] = {}
    for row in bom:
        if row.level != 1:
            continue
        for plan in plans:
            if plan.product_id == row.product_id:
                gross_req[row.component_id] = (
                    gross_req.get(row.component_id, 0.0)
                    + plan.planned_qty * row.qty_per_unit
                )

    result: dict[str, float] = {}
    for inv in inventory:
        mid = inv.material_id
        available = max(inv.current_stock - inv.safety_stock, 0)
        demand = gross_req.get(mid, 0.0)
        if demand == 0:
            result[mid] = float("inf")
        else:
            daily = demand / planning_days
            result[mid] = round(available / daily, 2)

    return result


# ---------------------------------------------------------------------------
# 风险结果类型
# ---------------------------------------------------------------------------

@dataclass
class SupplierRisk:
    po_id: str
    material_id: str
    material_name: str
    days_remaining: int
    dos_days: float
    risk_level: str                      # "high" | "medium" | "low"
    risk_reasons: list[str] = field(default_factory=list)
    qty_remaining: float = 0
    supplier_confirmed_date: str = ""


# ---------------------------------------------------------------------------
# 风险分级（纯函数，便于单元测试直接调用）
# ---------------------------------------------------------------------------

def _classify_risk(days_remaining: int, dos_days: float) -> SupplierRisk:
    """根据剩余天数和 DOS 判定风险等级，返回只含 risk_level/risk_reasons 的临时对象。"""
    stub = SupplierRisk("", "", "", days_remaining, dos_days, "")
    reasons: list[str] = []

    if days_remaining <= 3:
        reasons.append(
            f"承诺交期{'已过' if days_remaining < 0 else '仅剩' + str(days_remaining) + '天'}"
        )
    if dos_days < 5:
        reasons.append(f"库存DOS仅 {dos_days:.1f} 天（低于5天警戒）")

    if reasons:
        stub.risk_level = "high"
        stub.risk_reasons = reasons
        return stub

    reasons = []
    if days_remaining <= 7:
        reasons.append(f"承诺交期仅剩 {days_remaining} 天")
    if dos_days < 10:
        reasons.append(f"库存DOS仅 {dos_days:.1f} 天（低于10天提醒）")

    if reasons:
        stub.risk_level = "medium"
        stub.risk_reasons = reasons
        return stub

    stub.risk_level = "low"
    return stub


_RISK_ORDER = {"high": 0, "medium": 1, "low": 2}


# ---------------------------------------------------------------------------
# 主分析函数
# ---------------------------------------------------------------------------

def analyze(
    connector,
    today: date,
    planning_days: int = 14,
    srm_dates: dict[str, str] | None = None,
    srm_only: bool = False,
) -> list[SupplierRisk]:
    """
    读取在途采购订单，计算每笔订单的延期风险。
    跳过 status == "received" 的订单。
    返回结果按风险等级排序（high → medium → low）。

    Args:
        srm_dates: 可选，{po_id: confirmed_date_str} 来自携客云 SRM。
                   有值时覆盖 connector 里的 supplier_confirmed_date；
                   未覆盖的 PO 或 None 时回退到 connector 原始数据。
        srm_only:  True 时只处理有 SRM 承诺交期的 PO，跳过无答交记录的订单。
    """
    orders    = connector.get_purchase_orders()
    inventory = connector.get_inventory()
    bom       = connector.get_bom()
    plans     = connector.get_production_plan()

    inv_name = {r.material_id: r.material_name for r in inventory}
    dos_map  = compute_dos(inventory, bom, plans, planning_days=planning_days)

    results: list[SupplierRisk] = []
    for po in orders:
        if po.status == "received":
            continue

        srm_date = (srm_dates or {}).get(po.po_id)

        if srm_only and srm_dates is not None and not srm_date:
            continue

        confirmed_str  = srm_date or po.supplier_confirmed_date
        confirmed      = date.fromisoformat(confirmed_str)
        days_remaining = (confirmed - today).days
        dos            = dos_map.get(po.material_id, float("inf"))

        classified = _classify_risk(days_remaining, dos)
        results.append(SupplierRisk(
            po_id=po.po_id,
            material_id=po.material_id,
            material_name=inv_name.get(po.material_id, po.material_id),
            days_remaining=days_remaining,
            dos_days=dos,
            risk_level=classified.risk_level,
            risk_reasons=classified.risk_reasons,
            qty_remaining=po.qty_ordered - po.qty_received,
            supplier_confirmed_date=confirmed_str,
        ))

    results.sort(key=lambda r: _RISK_ORDER[r.risk_level])
    return results
