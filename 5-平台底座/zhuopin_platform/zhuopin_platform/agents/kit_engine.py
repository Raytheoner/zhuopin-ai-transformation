"""
齐套分析核心算法（提升自 O2 场景本地 kit_engine，触发：SC5 是第 2 消费方）。
- explode_bom: 递归展开 BOM，计算各物料毛需求（含损耗率）
- calc_shortage: 计算可用量与缺口，输出缺料清单

第 3 消费方出现时接口已稳定，直接 import 本模块即可。
"""
from __future__ import annotations

from zhuopin_platform.shared_tools.models import BomRow, InventoryRow, ProductionPlan, PurchaseOrder


def explode_bom(
    bom: list[BomRow],
    plans: list[ProductionPlan],
) -> dict[str, float]:
    """
    递归展开 BOM，返回 {material_id: 合计毛需求}。
    子件（如 SUB001）继续向下展开至叶节点，自身不计入结果。
    毛需求 = 生产计划量 × BOM 用量 × (1 + 损耗率)，逐层累乘。
    """
    bom_index: dict[str, list[BomRow]] = {}
    for row in bom:
        bom_index.setdefault(row.product_id, []).append(row)

    sub_assemblies = set(bom_index.keys())
    gross: dict[str, float] = {}

    def _expand(product_id: str, qty: float, visited: set[str]) -> None:
        if product_id in visited:
            return  # 防止循环引用
        visited = visited | {product_id}

        for row in bom_index.get(product_id, []):
            child_qty = qty * row.qty_per_unit * (1 + row.loss_rate)
            if row.component_id in sub_assemblies:
                _expand(row.component_id, child_qty, visited)
            else:
                gross[row.component_id] = gross.get(row.component_id, 0.0) + child_qty

    for plan in plans:
        _expand(plan.product_id, plan.planned_qty, set())

    return gross


def calc_shortage(
    gross: dict[str, float],
    inventory: list[InventoryRow],
    purchase_orders: list[PurchaseOrder],
) -> tuple[dict[str, float], list[str]]:
    """
    计算每种物料的缺口，返回 (shortages, missing_snapshot)。
    shortages:        {material_id: 缺口数量}（只含缺口 > 0 的物料）
    missing_snapshot: 不在库存快照中的物料告警清单（B6）

    可用量 = 当前库存 - 安全库存 + 在途未到货（qty_ordered - qty_received）
    缺口 = max(毛需求 - 可用量, 0)

    B6（审计报告 §2.5）：物料**不在库存快照**时，在途量仍计入可用量
    （available = 在途），不再被忽略而高估缺口；同时把该物料记入 missing_snapshot
    告警清单。`ZpConnector.get_inventory` 真实切换后恒返回 0 库存项，此路径必踩。
    """
    in_transit: dict[str, int] = {}
    for po in purchase_orders:
        in_transit[po.material_id] = (
            in_transit.get(po.material_id, 0) + po.qty_ordered - po.qty_received
        )

    inv_index = {row.material_id: row for row in inventory}
    shortages: dict[str, float] = {}
    missing_snapshot: list[str] = []

    for material_id, need in gross.items():
        inv = inv_index.get(material_id)
        on_way = in_transit.get(material_id, 0)
        if inv is not None:
            available = inv.current_stock - inv.safety_stock + on_way
        else:
            available = float(on_way)        # 缺快照：在途仍计入（不再忽略）
            missing_snapshot.append(material_id)
        gap = need - available
        if gap > 0:
            shortages[material_id] = gap

    return shortages, missing_snapshot
