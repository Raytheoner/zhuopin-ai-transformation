"""SC11 前置未到位项的统一 fail-loud 闸。

## 前置状态（2026-09-03 由 `OP-0903-B2` 泳道逐行实读，未做推断）

判据源＝`1-转型规划/0-全景路线图/跨场景前置数据与知识库任务总表.md` §一 `SC11` 行：
前置＝「生产计划数据通路 ＋ 3 委外仓库存实时可见 ＋ 调拨原则口径（知识型：姚祖怡批改会）」，
Owner 姚祖怡 ＋ PMC ＋ IT，整理启动 **2027-02**（知识型前 8 周）／完成截止 **2027-03**，
状态格 ⚪「新增行；PMC 确认门禁写入 openspec」⇒ **三项均未开工、窗口未到。**

## 第四项：物流距离

全景规划写「按生产时间顺序＋**物流距离**选最佳调拨路径」，而「1 物料仓 ＋ 3 委外仓」之间
的距离/时长矩阵在本项目全库无既有指针。它不在前置总表 SC11 行的三项里 —— 那三项分别是
数据通路、库存可见性、原则口径，**都不产出距离矩阵**。故本模块据实单列第四项。

⚠️ 距离看似"查一下就有"，但「就近」按公里、按车程、还是按承运商班次算，会得出不同的路径，
**这本身就是口径**。骨架期不替 PMC 选。

## 一处刻意不挡的：四条调拨原则本身

四条原则（跨仓调拨尽量少 / 优先物料仓→委外仓 / 共用料按上线时间顺序 / 委外仓间就近优先）
**逐字见于全景规划 §2.1.2 SC11 块**，是已成文的业务原则，转录进代码不算自拟判据。
被挡住的是它们的**相对优先级与冲突裁决** —— 四条同时适用而互相矛盾时听谁的，
规划原文没有回答，属「调拨原则口径」这项知识型前置（姚祖怡批改会）。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Prerequisite:
    key: str
    title: str
    owner: str
    kind: str
    source: str
    status_note: str


BLOCKED: dict[str, Prerequisite] = {
    "production_plan_feed": Prerequisite(
        key="production_plan_feed",
        title="生产计划数据通路",
        owner="姚祖怡 + PMC + IT",
        kind="数据型",
        source="跨场景前置数据与知识库任务总表.md §一 `SC11 库存智能调拨` 行",
        status_note="⚪ 新增行；整理启动 2027-02／完成截止 2027-03 —— 窗口未到，非逾期",
    ),
    "outsourced_stock_visibility": Prerequisite(
        key="outsourced_stock_visibility",
        title="3 委外仓库存实时可见",
        owner="IT（内网数据通路）",
        kind="数据型",
        source="跨场景前置数据与知识库任务总表.md §一 `SC11 库存智能调拨` 行",
        status_note="⚪ 新增行；属内网通路，本机 off-LAN 期间亦无法自行验证",
    ),
    "transfer_principle_priority": Prerequisite(
        key="transfer_principle_priority",
        title="四条调拨原则的相对优先级与冲突裁决（调拨原则口径）",
        owner="姚祖怡（批改会）+ PMC",
        kind="知识型",
        source="跨场景前置数据与知识库任务总表.md §一 `SC11` 行第 ⑶ 项；原则正文见全景规划 §2.1.2 SC11 块",
        status_note="⚪ 未起；🔴 判据/口径类永不默认生效（原则正文可转录，冲突裁决不可自拟）",
    ),
    "logistics_distance_matrix": Prerequisite(
        key="logistics_distance_matrix",
        title="1 物料仓 + 3 委外仓的物流距离/时长矩阵及其口径",
        owner="PMC（待点名）",
        kind="混合",
        source="全景规划 §2.1.2 SC11 块「按生产时间顺序+物流距离选最佳调拨路径」；前置总表三项均不产出此矩阵",
        status_note="🔴 判据源无此项，本场景据实单列；「就近」按公里/车程/班次算会得出不同路径，本身即口径",
    ),
}


class PendingPrerequisiteError(RuntimeError):
    """判据/口径/数据通路类能力在其前置到位前被调用。"""


def require(key: str) -> None:
    p = BLOCKED.get(key)
    if p is None:
        raise KeyError(f"未登记的前置键：{key!r}；已登记：{sorted(BLOCKED)}")
    raise PendingPrerequisiteError(
        f"SC11 前置未到位，本能力不提供默认口径：{p.title}\n"
        f"  Owner ：{p.owner}（{p.kind}前置）\n"
        f"  判据源：{p.source}\n"
        f"  实读状态：{p.status_note}\n"
        f"  ⇒ 骨架期只提供四条原则的显式建模与 PMC 确认门禁，路径择优须待口径到位后另行 openspec。"
    )
