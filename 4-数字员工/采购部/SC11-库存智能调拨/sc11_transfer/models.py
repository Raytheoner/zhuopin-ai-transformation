"""SC11 结构模型 —— 仓、调拨需求、候选路径、调拨清单**拟稿**。

命名上刻意一律带 `Draft`：全景规划写的是「生成调拨清单交仓库、**拟**录 ERP 库存模块、
**拟**邮件通知委外仓收货人」，采购专线 2026-07-06 门禁进一步定死"须 PMC 经理人工确认
后执行"。类型名里带 Draft，是让"这东西还没生效"在每一个调用点都看得见。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class WarehouseKind(Enum):
    """卓品的两类仓（背景见全景规划 §2.1.2 SC11：1 物料仓 + 3 委外仓）。

    同 SC10 的 `LifecycleStatus`：**不混入 `str`**，避免枚举成员之间出现静默可比较性
    被误当成优先级。
    """

    MATERIAL = "物料仓"
    OUTSOURCED = "委外仓"


@dataclass(frozen=True)
class Warehouse:
    code: str
    name: str
    kind: WarehouseKind

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("仓库编码不可为空")


@dataclass(frozen=True)
class TransferDemand:
    """一条"某仓在某日之前需要某料多少"的需求，来自生产计划 BOM 展开。"""

    material_id: str
    to_warehouse: str
    qty: float
    needed_by: str          # 上线日期 YYYY-MM-DD
    product_id: str = ""

    def __post_init__(self) -> None:
        if self.qty <= 0:
            raise ValueError(f"调拨需求数量须为正：{self.qty}")


@dataclass(frozen=True)
class TransferCandidate:
    """一条候选调拨路径：从哪个仓、调多少、给哪条需求。

    `hops` 恒为 1（本模型只表达直达调拨）；保留该字段是为了让「跨仓调拨尽量少」这条原则
    有一个可度量的对象，而不是靠注释描述。多段中转若将来需要，扩的是这个字段的取值。
    """

    demand: TransferDemand
    from_warehouse: str
    qty: float
    hops: int = 1

    def __post_init__(self) -> None:
        if self.from_warehouse == self.demand.to_warehouse:
            raise ValueError("源仓与目标仓相同，不构成调拨")
        if self.qty <= 0:
            raise ValueError(f"调拨数量须为正：{self.qty}")


@dataclass
class TransferPlanDraft:
    """调拨清单**拟稿** —— 未经 PMC 确认前，它不是计划，只是一份建议。

    `approved_by` 为空即代表未确认；`gate.py` 的执行侧函数以此为唯一判据，
    **不接受任何"调用方说它确认过了"的旁路参数**。
    """

    lines: list[TransferCandidate] = field(default_factory=list)
    unmet: list[TransferDemand] = field(default_factory=list)
    #: 本次排序**假设**的原则优先级顺序。它不是口径、是试算参数 ——
    #: 真口径须经姚祖怡批改会签认（`pending.py::transfer_principle_priority`）。
    #: 一路带进 audit，使任何一份拟稿都能被认出是在哪个假设下排出来的。
    priority_assumption: tuple[str, ...] = ()
    approved_by: str = ""
    approved_at: str = ""

    @property
    def is_approved(self) -> bool:
        return bool(self.approved_by.strip())

    @property
    def summary(self) -> dict[str, object]:
        return {
            "line_count": len(self.lines),
            "unmet_count": len(self.unmet),
            "cross_warehouse_moves": len({(c.from_warehouse, c.demand.to_warehouse) for c in self.lines}),
            "priority_assumption": list(self.priority_assumption),
            "approved": self.is_approved,
        }
