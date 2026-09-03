"""SC10 前置未到位项的统一 fail-loud 闸。

## 前置状态（2026-09-03 由 `OP-0903-B2` 泳道逐行实读，未做推断）

判据源＝`1-转型规划/0-全景路线图/跨场景前置数据与知识库任务总表.md` §一 `SC10` 行：
前置＝「原厂/第三方贸易网站 API 选型 ＋ 我司价格库/物料属性数据整备」，Owner 姚祖怡 ＋ IT，
整理启动 **2027-01**（数据型前 6 周＋缓冲）／完成截止 **2027-02**，状态格 ⚪「新增行」。

⇒ 与 SC4 不同，SC10 的前置**不是已滑，而是窗口本来就还没到**。这个区别要写在代码里：
「未开工」和「已逾期」对承接方意味着完全不同的动作（前者等窗口，后者要追责）。

## 本模块挡住的第三样东西（前置总表没写、但同样不能默认）

「**物料优先选用级别**」与「淘汰建议」的口径 —— 它决定一个物料是被推荐、被限用还是被淘汰，
是采购经理的判断，当前只在人脑里。前置总表把它含在「物料属性数据整备」里一并交给
姚祖怡 ＋ IT，但**数据整备产出的是属性值，不是排序规则**：Active/NRND/New Product/Obsolete
这四个属性到手之后，「NRND 的物料能不能进新 BOM」仍然没有答案。

故本模块把它单列一项 `selection_ranking_criteria`，**不与数据型前置混记** ——
混记会让"属性数据到位"被误读成"SC10 可以全量开工"。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Prerequisite:
    key: str
    title: str
    owner: str
    kind: str            # "数据型" / "知识型"，决定按 6 周还是 8 周倒排
    source: str
    status_note: str


BLOCKED: dict[str, Prerequisite] = {
    "external_price_api": Prerequisite(
        key="external_price_api",
        title="原厂/第三方贸易网站 API 选型与接入（价格/参数/封装）",
        owner="姚祖怡 + IT",
        kind="数据型",
        source="跨场景前置数据与知识库任务总表.md §一 `SC10 BOM 评审及物料库管控` 行",
        status_note="⚪ 新增行；整理启动 2027-01（数据型前 6 周+缓冲）／完成截止 2027-02 —— 窗口未到，非逾期",
    ),
    "material_attribute_data": Prerequisite(
        key="material_attribute_data",
        title="我司价格库 / 物料属性（Active·NRND·New Product·Obsolete）数据整备",
        owner="姚祖怡 + IT",
        kind="数据型",
        source="跨场景前置数据与知识库任务总表.md §一 `SC10 BOM 评审及物料库管控` 行",
        status_note="⚪ 新增行；同上窗口 —— 窗口未到，非逾期",
    ),
    "selection_ranking_criteria": Prerequisite(
        key="selection_ranking_criteria",
        title="物料优先选用级别口径与淘汰建议判据",
        owner="采购经理（待点名；前置总表未单列，本场景据实拆出）",
        kind="知识型",
        source="全景规划 §2.1.2 SC10 块「物料优先选用级别建议 / 优先选用与淘汰建议」；前置总表未单列",
        status_note="🔴 判据源本身无此行 —— 属性数据到位 ≠ 排序规则到位，见本模块 docstring",
    ),
}


class PendingPrerequisiteError(RuntimeError):
    """判据/口径/外部数据源类能力在其前置到位前被调用。"""


def require(key: str) -> None:
    p = BLOCKED.get(key)
    if p is None:
        raise KeyError(f"未登记的前置键：{key!r}；已登记：{sorted(BLOCKED)}")
    raise PendingPrerequisiteError(
        f"SC10 前置未到位，本能力不提供默认口径：{p.title}\n"
        f"  Owner ：{p.owner}（{p.kind}前置）\n"
        f"  判据源：{p.source}\n"
        f"  实读状态：{p.status_note}\n"
        f"  ⇒ 骨架期只提供 BOM 展开与物料台账结构，选用级别/淘汰建议须待前置到位后另行 openspec。"
    )
