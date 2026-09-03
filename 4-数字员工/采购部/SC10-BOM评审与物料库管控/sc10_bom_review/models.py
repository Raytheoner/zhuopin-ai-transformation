"""SC10 结构模型 —— 承载"物料库里有什么"，不承载"它该不该被选用"。

四个物料生命周期属性逐字取自全景规划 §2.1.2 SC10 块的
「物料属性 Active/NRND/New Product/Obsolete」一句，不是本工程自拟的分级。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class LifecycleStatus(Enum):
    """原厂物料生命周期状态（业界通用，规划原文点名的四个）。

    🔴 **枚举顺序不携带优先级语义**。看起来"显然" Active 优于 NRND 优于 Obsolete，
    但「NRND 的物料能不能进新 BOM」「已在产机型上的 Obsolete 料何时必须替换」这类问题
    的答案是采购经理的口径，不是枚举定义顺序。任何依赖成员顺序做排序的代码都是在偷偷
    造判据 —— 排序须走 `pending.require("selection_ranking_criteria")`。

    🔴 **刻意不混入 `str`**（本仓库其余枚举多为 `(str, Enum)`）：带 `str` 混入时
    `ACTIVE < NRND` 会**静默成立**并按字母序给出答案 —— 一个看起来能用、实际毫无业务
    含义的排序，正是上一段要挡的那个入口。序列化改为显式取 `.value`，多一个字符，
    换掉一整类静默错误。
    """

    ACTIVE = "Active"
    NRND = "NRND"                 # Not Recommended for New Designs
    NEW_PRODUCT = "New Product"
    OBSOLETE = "Obsolete"
    UNKNOWN = "未知"              # 属性数据未整备时的如实取值，不猜成 Active


@dataclass(frozen=True)
class MaterialRecord:
    """公司物料库中的一条物料主数据（骨架期只取 ERP 已有字段）。

    `lifecycle` 缺省 `UNKNOWN` 是刻意的：物料属性数据整备是 2027-01 才启动的前置，
    现在库里根本没有这个字段。默认成 `ACTIVE` 会让"我们还没有这份数据"这件事消失。
    """

    material_id: str
    material_name: str
    category: str = ""
    lifecycle: LifecycleStatus = LifecycleStatus.UNKNOWN
    package: str = ""             # 封装，待外部 API 接入后回填
    unit_price: float | None = None   # 我司价格库；None ＝ 无价，非 0

    def __post_init__(self) -> None:
        if not self.material_id:
            raise ValueError("material_id 不可为空")
        if self.unit_price is not None and self.unit_price < 0:
            raise ValueError(f"单价不可为负：{self.unit_price}")


@dataclass
class BomUsage:
    """一个物料在一份 BOM 展开结果中的用量事实。"""

    material_id: str
    gross_qty: float
    product_ids: tuple[str, ...] = ()

    @property
    def is_shared(self) -> bool:
        """跨机型共用料。**只陈述事实**，不代表"因此应优先选用"。"""
        return len(self.product_ids) > 1


@dataclass
class BomReviewFacts:
    """一次 BOM 评审的**事实层**产出：能从现有数据算出来的全部内容。

    刻意命名为 `Facts` 而不是 `Result`/`Report` —— 全景规划要的三项产出
    （BOM 评审建议 / 物料优先选用级别建议 / 物料库优先选用与淘汰建议）**全是建议**，
    而建议需要口径。骨架期交付的是建议所依赖的事实，不是建议本身。
    """

    usages: list[BomUsage] = field(default_factory=list)
    unknown_lifecycle: list[str] = field(default_factory=list)
    missing_price: list[str] = field(default_factory=list)
    not_in_master: list[str] = field(default_factory=list)

    @property
    def data_readiness(self) -> dict[str, int]:
        """数据完备度体检 —— 骨架期最有用的一张表：还差多少数据才谈得上评审。"""
        return {
            "materials_in_bom": len(self.usages),
            "lifecycle_unknown": len(self.unknown_lifecycle),
            "price_missing": len(self.missing_price),
            "not_in_master": len(self.not_in_master),
        }
