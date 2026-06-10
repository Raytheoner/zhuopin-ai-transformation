"""
齐套分析核心算法（收割自 supplychain/src/agents/kit_analysis.py）。
- explode_bom: 递归展开BOM，计算各物料毛需求（含损耗率）
- calc_shortage: 计算可用量与缺口，输出缺料清单
import 已改为底座 models，算法原样保留。
"""
from zhuopin_platform.shared_tools.models import BomRow, InventoryRow, PurchaseOrder, ProductionPlan


def explode_bom(
    bom: list[BomRow],
    plans: list[ProductionPlan],
) -> dict[str, float]:
    """
    递归展开BOM，返回 {material_id: 合计毛需求}。
    子件（如SUB001）继续向下展开至叶节点，自身不计入结果。
    毛需求 = 生产计划量 × BOM用量 × (1 + 损耗率)，逐层累乘。
    """
    # 构建 product_id → [BomRow] 的索引，方便递归查找
    bom_index: dict[str, list[BomRow]] = {}
    for row in bom:
        bom_index.setdefault(row.product_id, []).append(row)

    # 所有出现在 product_id 列的ID（既是父件，也可能是子件/中间件）
    sub_assemblies = set(bom_index.keys())

    gross: dict[str, float] = {}

    def _expand(product_id: str, qty: float, visited: set[str]) -> None:
        """递归展开一个产品/子件，qty 是该层的净需求数量（已含父层损耗）。"""
        if product_id in visited:
            return  # 防止循环引用
        visited = visited | {product_id}

        for row in bom_index.get(product_id, []):
            # 本层实际需求 = 上层传入数量 × 本层用量 × (1 + 损耗率)
            child_qty = qty * row.qty_per_unit * (1 + row.loss_rate)

            if row.component_id in sub_assemblies:
                # 中间件：继续向下递归，自身不加入毛需求
                _expand(row.component_id, child_qty, visited)
            else:
                # 叶节点物料：累加到毛需求
                gross[row.component_id] = gross.get(row.component_id, 0.0) + child_qty

    for plan in plans:
        _expand(plan.product_id, plan.planned_qty, set())

    return gross


def calc_shortage(
    gross: dict[str, float],
    inventory: list[InventoryRow],
    purchase_orders: list[PurchaseOrder],
) -> dict[str, float]:
    """
    计算每种物料的缺口，返回 {material_id: 缺口数量}（只含缺口>0的物料）。
    可用量 = 当前库存 - 安全库存 + 在途未到货（qty_ordered - qty_received）
    缺口 = max(毛需求 - 可用量, 0)
    """
    # 汇总在途未到货
    in_transit: dict[str, int] = {}
    for po in purchase_orders:
        in_transit[po.material_id] = (
            in_transit.get(po.material_id, 0) + po.qty_ordered - po.qty_received
        )

    inv_index = {row.material_id: row for row in inventory}

    shortages: dict[str, float] = {}
    for material_id, need in gross.items():
        inv = inv_index.get(material_id)
        available = 0.0
        if inv:
            available = inv.current_stock - inv.safety_stock + in_transit.get(material_id, 0)
        gap = need - available
        if gap > 0:
            shortages[material_id] = gap

    return shortages
