"""需求分解与候选路径枚举 —— 骨架期真跑的一层。

做两件事：
① 把生产计划 ＋ BOM 展开成"某仓在某日之前需要某料多少"（复用底座 `kit_engine`）；
② 对每条需求枚举**所有**有货的源仓，产出候选路径，交 `principles.rank_candidates` 排序。

刻意**不**在这里做择优 —— 择优要的是原则优先级，那是口径。这里只保证"候选一个不漏"。
"""
from __future__ import annotations

from typing import Mapping, Sequence

from zhuopin_platform.agents.kit_engine import explode_bom
from zhuopin_platform.shared_tools.models import BomRow, ProductionPlan

from .models import TransferCandidate, TransferDemand, TransferPlanDraft, Warehouse
from .principles import Principle, rank_candidates


def demands_from_plans(
    bom: list[BomRow],
    plans: Sequence[ProductionPlan],
    plan_warehouse: Mapping[str, str],
) -> list[TransferDemand]:
    """把生产计划逐条展开成调拨需求。

    `plan_warehouse` ＝ {plan_id: 该计划在哪个委外仓上线}。骨架期由调用方给出；
    真实来源是生产计划数据通路（`pending.py::production_plan_feed`）。

    逐个计划单独展开而非一次性展开：`explode_bom` 返回合计毛需求、丢掉了"这份需求属于
    哪条计划、哪个上线日" —— 而"共用料按上线时间顺序"这条原则要的正是上线日。
    """
    demands: list[TransferDemand] = []
    for plan in plans:
        warehouse = plan_warehouse.get(plan.plan_id)
        if warehouse is None:
            raise KeyError(
                f"生产计划 {plan.plan_id} 未给出上线仓；骨架期须由调用方显式提供，"
                f"不默认落到任一委外仓（默认会静默把料调错地方）"
            )
        for material_id, qty in explode_bom(bom, [plan]).items():
            demands.append(
                TransferDemand(
                    material_id=material_id,
                    to_warehouse=warehouse,
                    qty=qty,
                    needed_by=plan.planned_date,
                    product_id=plan.product_id,
                )
            )
    return demands


def enumerate_candidates(
    demand: TransferDemand,
    stock_by_warehouse: Mapping[str, Mapping[str, float]],
) -> list[TransferCandidate]:
    """枚举能满足该需求的全部源仓（有货即为候选，不做择优、不做部分拆分）。

    骨架期只产**整条满足**的候选：部分调拨要按"先满足谁"拆分，那又是口径。
    一条都满足不了时返回空列表，由调用方落进 `unmet` —— 不静默丢弃。
    """
    out: list[TransferCandidate] = []
    for warehouse, stock in stock_by_warehouse.items():
        if warehouse == demand.to_warehouse:
            continue
        if stock.get(demand.material_id, 0.0) >= demand.qty:
            out.append(TransferCandidate(demand=demand, from_warehouse=warehouse, qty=demand.qty))
    return out


def build_draft(
    demands: Sequence[TransferDemand],
    stock_by_warehouse: Mapping[str, Mapping[str, float]],
    principles: Mapping[str, Principle],
    priority_assumption: Sequence[str],
) -> TransferPlanDraft:
    """产出调拨清单**拟稿**（未确认）。

    `priority_assumption` 一路带进 draft 与 audit：任何一份拟稿都要能被认出
    是在哪个假设顺序下排出来的（真口径待批改会签认）。
    """
    draft = TransferPlanDraft(priority_assumption=tuple(priority_assumption))
    for demand in demands:
        candidates = enumerate_candidates(demand, stock_by_warehouse)
        if not candidates:
            draft.unmet.append(demand)
            continue
        draft.lines.append(rank_candidates(candidates, principles, priority_assumption)[0])
    return draft


def warehouse_index(warehouses: Sequence[Warehouse]) -> dict[str, Warehouse]:
    return {w.code: w for w in warehouses}
