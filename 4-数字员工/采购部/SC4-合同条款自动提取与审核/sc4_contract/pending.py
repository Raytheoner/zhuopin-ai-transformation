"""SC4 前置未到位项的统一 fail-loud 闸（骨架期核心件）。

## 为什么它先于任何功能代码存在

SC4 的两项前置**都是知识型、且都是法务侧的**：
① 公司标准合同条款库（质量协议/交付/违约）——前置总表 §一 `SC4` 行，Owner 法务＋采购，
   整理启动「8月初」／完成截止「9月底」，**状态格至今零回填**；
② 合同风险条款判据——前置总表 §一.2 知识资产台账，持有人法务、**backup「采购合同岗」
   仍标「待点名」**。

⇒ 「某条款算不算偏离标准」「偏离到什么程度算高风险」「缺哪几类条款算致命」这三件事，
**当前没有任何一份仓库内文件能回答**。骨架期把它们写成默认值（哪怕标着 TODO）会立刻
产生两个后果：⑴ 下游测试会围着这个默认值长出黄金基准，前置到位后改判据 ＝ 改一片测试；
⑵ 演示时它看起来"能跑"，而跑出来的风险等级是本工程自拟的，**法务从未见过**。

故本模块的立场是：**判据缺席时不给默认值、直接抛。** 调用方拿到的错误里带着卡在哪一项
前置、去哪里看它的状态——而不是一个静默成立的数字。

> 同族教训见根 `CLAUDE.md` §5「工具静默回退」：错误不产生信号，比错误本身更贵。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Prerequisite:
    """一项尚未到位的前置，及其在规划文档中的权威落点。"""

    key: str
    title: str
    owner: str
    source: str          # 判据源里的具体行，写到章节级，便于核实而非泛指
    status_note: str     # 实读到的状态原文，不做转述美化


#: 判据源＝`1-转型规划/0-全景路线图/跨场景前置数据与知识库任务总表.md`
#: （2026-09-03 由本泳道逐行实读，未做推断）
BLOCKED: dict[str, Prerequisite] = {
    "standard_clause_library": Prerequisite(
        key="standard_clause_library",
        title="公司标准合同条款库（质量协议/交付/违约）",
        owner="法务 + 采购",
        source="跨场景前置数据与知识库任务总表.md §一 `SC4 合同条款提取` 行",
        status_note="🟡 实施计划已标 8月前置（整理启动 8月初／完成截止 9月底，状态格无完成回填）",
    ),
    "risk_clause_criteria": Prerequisite(
        key="risk_clause_criteria",
        title="合同风险条款判据",
        owner="法务（backup「采购合同岗」待点名）",
        source="跨场景前置数据与知识库任务总表.md §一.2 知识资产台账「合同风险条款判据」行",
        status_note="首轮工作坊「8月初」无开过记录；backup 至今未点名",
    ),
}


class PendingPrerequisiteError(RuntimeError):
    """判据/口径类能力在其前置到位前被调用。

    刻意继承 `RuntimeError` 而非自定义基类：它要的是"谁都别顺手 except 掉"，
    不是一个可被分类处理的业务异常。
    """


def require(key: str) -> None:
    """守在一切依赖法务判据的入口处；前置未解锁即抛。

    解锁方式**不在本模块**——前置总表对应行的状态格回填后，由承接方按 openspec
    变更包正式移除对应 `require()` 并补齐判据实现，**不允许在调用侧 try/except 绕过**。
    """
    p = BLOCKED.get(key)
    if p is None:
        raise KeyError(f"未登记的前置键：{key!r}；已登记：{sorted(BLOCKED)}")
    raise PendingPrerequisiteError(
        f"SC4 前置未到位，本能力不提供默认判据：{p.title}\n"
        f"  Owner ：{p.owner}\n"
        f"  判据源：{p.source}\n"
        f"  实读状态：{p.status_note}\n"
        f"  ⇒ 骨架期只提供解析与条款定位，比对基准与风险分级须待该前置回填后另行 openspec。"
    )
