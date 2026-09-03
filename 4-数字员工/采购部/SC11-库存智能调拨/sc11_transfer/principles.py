"""四条调拨原则的**显式建模** —— 原则正文可转录，冲突裁决不可自拟。

## 这个模块和 `pending.py` 的分工

全景规划 §2.1.2 SC11 逐字写明四条原则：

> 原则：跨仓调拨尽量少、优先物料仓→委外仓、共用料按上线时间顺序、委外仓间就近优先

⇒ **每一条单独拿出来，语义是清楚的**，把它写成一个可度量的函数属于转录。
⇒ **四条同时适用而互相矛盾时听谁的，规划原文没有回答** —— 例如"委外仓 A 有现货但离得远"
   与"物料仓有货但优先级更高"，第 2 条和第 4 条会指向不同的源仓。这属「调拨原则口径」
   （知识型前置，姚祖怡批改会），故 `rank_candidates` 要求**显式传入优先级顺序**，
   没有默认值。

🔑 **为什么不干脆把整个模块也放到闸后**：那样会丢掉本骨架期唯一能交付的东西 ——
四条原则各自的**可度量定义**（"尽量少"少的是什么、"就近"近的是什么）。这些定义本身
就需要被姚祖怡在批改会上过目一遍；把它们写出来，批改会才有可批改的东西，
而不是从一张白纸开始。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from . import pending
from .models import TransferCandidate, Warehouse, WarehouseKind

#: 一条原则 ＝ 给候选路径打一个"越小越好"的分。返回 None ＝ 该原则对本候选无从判断
#: （缺数据），**不折算成 0** —— 缺数据被当成满分是本项目记过多次的静默失效形态。
PrincipleScore = Callable[[TransferCandidate], float | None]


@dataclass(frozen=True)
class Principle:
    key: str
    text: str            # 规划原文，逐字转录，便于批改会比对
    score: PrincipleScore


def _fewest_cross_warehouse(c: TransferCandidate) -> float:
    """原则一「跨仓调拨尽量少」的可度量定义：一条候选的调拨段数。

    直达 ＝ 1 段。段数越少越好，故直接返回 `hops`。
    """
    return float(c.hops)


def _prefer_material_warehouse(
    warehouses: Mapping[str, Warehouse]
) -> PrincipleScore:
    """原则二「优先物料仓→委外仓」：源仓是物料仓记 0，是委外仓记 1。

    源仓不在仓库表里时返回 `None`（无从判断），不猜。
    """

    def score(c: TransferCandidate) -> float | None:
        wh = warehouses.get(c.from_warehouse)
        if wh is None:
            return None
        return 0.0 if wh.kind is WarehouseKind.MATERIAL else 1.0

    return score


def _shared_material_by_line_date(c: TransferCandidate) -> float | None:
    """原则三「共用料按上线时间顺序」：以需求的上线日期排序。

    上线日期缺失时返回 `None` —— 缺日期的需求不该被排到最前面，也不该被排到最后，
    它该被人看见。
    """
    if not c.demand.needed_by:
        return None
    return float(c.demand.needed_by.replace("-", ""))


def _nearest_between_outsourced(
    distances: Mapping[tuple[str, str], float]
) -> PrincipleScore:
    """原则四「委外仓间就近优先」：查距离矩阵。

    🔴 **距离矩阵必须由调用方传入**，本模块不内置任何数字 ——
    「就近」按公里/车程/班次算会得出不同路径，本身即口径（见 `pending.py`）。
    查不到即 `None`。
    """

    def score(c: TransferCandidate) -> float | None:
        return distances.get((c.from_warehouse, c.demand.to_warehouse))

    return score


def build_principles(
    warehouses: Mapping[str, Warehouse],
    distances: Mapping[tuple[str, str], float],
) -> dict[str, Principle]:
    """按规划原文构造四条原则；文本逐字转录，供批改会比对。"""
    return {
        "fewest_cross_warehouse": Principle(
            "fewest_cross_warehouse", "跨仓调拨尽量少", _fewest_cross_warehouse
        ),
        "prefer_material_warehouse": Principle(
            "prefer_material_warehouse", "优先物料仓→委外仓", _prefer_material_warehouse(warehouses)
        ),
        "shared_material_by_line_date": Principle(
            "shared_material_by_line_date", "共用料按上线时间顺序", _shared_material_by_line_date
        ),
        "nearest_between_outsourced": Principle(
            "nearest_between_outsourced", "委外仓间就近优先", _nearest_between_outsourced(distances)
        ),
    }


def rank_candidates(
    candidates: Sequence[TransferCandidate],
    principles: Mapping[str, Principle],
    priority: Sequence[str],
) -> list[TransferCandidate]:
    """按给定优先级顺序对候选排序。

    🔴 `priority` **无默认值，且必须四条齐全** —— 少给一条就等于替 PMC 决定了"那一条
    不重要"。顺序本身属「调拨原则口径」，未经姚祖怡批改会签认前不得写死在代码里；
    调用方传的是**试算用**的假设顺序，须一路带进 audit。
    """
    if set(priority) != set(principles):
        pending.require("transfer_principle_priority")

    def key(c: TransferCandidate) -> tuple:
        out: list[tuple[int, float]] = []
        for name in priority:
            s = principles[name].score(c)
            # (1, 0.0) 排在 (0, x) 之后 ⇒ 无从判断的候选一律靠后、不冒充最优
            out.append((1, 0.0) if s is None else (0, s))
        return tuple(out)

    return sorted(candidates, key=key)
