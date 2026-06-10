"""订单聚合（收割自 supplychain sales_order_intake）。

把多张销售/预测订单按产品（料号）聚合成生产需求：同料号数量求和、交期取最早
（最紧迫需求驱动生产截止日）。平台 ProductionPlan 从底座 import。
"""
from __future__ import annotations

from zhuopin_platform.shared_tools.models import ProductionPlan

from .models import SalesOrder


def aggregate_demand(orders: list[SalesOrder]) -> list[ProductionPlan]:
    """将销售订单列表聚合为生产需求计划（同 item_code 合并）。

    - planned_qty  = 所有行数量之和
    - planned_date = 最早客户要求交货日期（驱动生产截止日）
    - plan_id      = product_id（方便按产品匹配 BOM）
    """
    if not orders:
        return []

    agg: dict[str, list] = {}
    for so in orders:
        item = so.item_code
        if item not in agg:
            agg[item] = [0, so.required_date, getattr(so, "item_name", "")]
        agg[item][0] += so.qty
        if so.required_date < agg[item][1]:          # 字符串 YYYY-MM-DD 可直接比较
            agg[item][1] = so.required_date
        if not agg[item][2]:
            agg[item][2] = getattr(so, "item_name", "")

    return [
        ProductionPlan(
            plan_id=item_code,
            product_id=item_code,
            product_name=name or item_code,
            planned_qty=total_qty,
            planned_date=earliest_date,
        )
        for item_code, (total_qty, earliest_date, name) in sorted(agg.items())
    ]
