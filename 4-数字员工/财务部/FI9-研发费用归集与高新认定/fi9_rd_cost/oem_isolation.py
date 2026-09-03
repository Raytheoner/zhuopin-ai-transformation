"""FI9 · OEM 隔离层接法 —— `EE-3` 五条定夺项（Shao Peishen 2026-09-03 裁决）的落地代码。

本模块是 `design.md`（局部件）对应的实现，只覆盖"研发项目 OEM 归属"这一段隔离机制：
三态归属字段的判定入口（E2.2）、未判归属的归集-禁汇总隔离（③④）、跨 OEM 汇总的开关
与三道锁（②）。**不包含** `fi9-cost-collection`/`fi9-capitalization-rules`/
`fi9-aux-ledger-and-filing` 三个 capability 的业务逻辑——那是 `tasks.md` §3-§5，design
审未全部通过前不得开工（本模块只解决 §2.4 这一条）。

🔴 五条定夺项裁决索引（原文见 `design.md` 「§定夺项」，裁决人 Shao Peishen，2026-09-03）：
  ① (c) 分层 —— 本模块只处理"项目标识 → OEM 归属"这一层；金额分层留给 §5 辅助账。
  ② (c) 立法定申报豁免款 ＋ 三道锁 —— `cross_oem_filing_gate()`。
  ③ (b) 允许归集、禁止汇总与对外 —— `partition_by_ownership()`。
  ④ (a) 研发侧认定、财务侧使用 —— 本模块只读 `RdProject.oem_customer`，不提供、
     也不允许任何"从项目号/项目名推导"的函数。
  ⑤ (a) 不卡 —— 本模块走 `OEMRouter.resolve()`（关系型取数判定），不碰 Chroma。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger
from zhuopin_platform.data_isolation_layer import OEMRouter

from . import config
from .models import NON_OEM_PROJECT, RdProject


class CrossOemAggregationDisabledError(PermissionError):
    """②(c) 开关 `FI9_CROSS_OEM_AGGREGATION` 为 OFF 时调用跨 OEM 汇总闸即抛。

    🔴 fail-loud：不静默返回空结果，也不静默降级为"仅本 OEM"结果——两者都会让调用方
    误以为汇总已完成。
    """


class CrossOemFilingLockError(ValueError):
    """三道锁的必填留痕字段（申报期间／经办人／审批人）缺失时抛出。"""


def resolve_project_source(project: RdProject, router: OEMRouter) -> Optional[str]:
    """在取数入口对单个研发项目解析一次 OEM 归属（E2.2：调一次，不在每行费用记录上调）。

    🔴 只读 `project.oem_customer`，绝不检视 `project_id` / `project_name`——④(a) 已裁
    "研发侧认定、财务侧使用"，本函数是财务侧的"使用"，没有推导的权限。

    返回：
      · `None`              —— 未判归属（`oem_customer is None`）。调用方须走
        `partition_by_ownership` 的排除逻辑，**不得**当已放行处理。
      · `NON_OEM_PROJECT`    —— 明确非 OEM，无隔离顾虑。
      · `project.oem_customer` 本身（已注册 OEM 的显示名，如 `"比亚迪"`）—— 已经
        `OEMRouter.resolve()` 校验注册有效性（未注册名/拼写变体在此 fail-closed
        并写审计，同规范 §3.1/§3.2）。返回显示名而非内部 collection key，与
        `AuditEvent.oem_context` 的既有填法（`router.py::_record_denied`）保持一致。

    ⚠️ 未调用 `OEMRouter.guard()`：guard() 额外需要一个"调用方所属 OEM"的第二轴，
    但 FI9 没有"某个 OEM 的人来查询"这种调用方身份（不同于 R1-R5 的 RAG 检索场景）——
    这里唯一要判定的是"这个项目自己声明的归属，是不是一个真实注册的 OEM"，
    `resolve()` 已完整覆盖。理由已同步记入 `design.md` E2.2。
    """
    oem = project.oem_customer
    if oem is None:
        return None
    if oem == NON_OEM_PROJECT:
        return NON_OEM_PROJECT
    router.resolve(oem)  # 校验副作用：未注册/拼写变体在此 fail-closed 并写审计
    return oem


@dataclass
class OwnershipPartition:
    """按 OEM 归属把项目一分为二：可汇总 vs 因未判被排除（③(b)＋④(a)）。"""

    eligible: list[RdProject] = field(default_factory=list)
    excluded_unjudged: list[RdProject] = field(default_factory=list)

    @property
    def excluded_project_ids(self) -> tuple[str, ...]:
        """🔴 因归属未判被排除的项目清单——须在报告显要位置展示，不得塞附录（③ 裁决原文）。"""
        return tuple(p.project_id for p in self.excluded_unjudged)


def partition_by_ownership(projects: Iterable[RdProject], router: OEMRouter) -> OwnershipPartition:
    """③(b)＋④(a)：未判归属允许归集明细，但禁止进入任何汇总/对外产物。

    对每个项目调一次 `resolve_project_source`（入口层，E2.2）。已注册 OEM 与
    `NON_OEM_PROJECT` 项目进 `eligible`；`oem_customer is None` 的项目进
    `excluded_unjudged`——**绝不**因项目名/项目号"看起来像"某个 OEM 而改判
    （④ 裁决：禁止从命名规则推导）。
    """
    partition = OwnershipPartition()
    for project in projects:
        resolved = resolve_project_source(project, router)
        if resolved is None:
            partition.excluded_unjudged.append(project)
        else:
            partition.eligible.append(project)
    return partition


@dataclass(frozen=True)
class CrossOemFilingReceipt:
    """跨 OEM 汇总通过三道锁后的留痕回执——下游产物（§5，本批不做）须随身携带它，
    作为"已过闸"的证明；回执本身**不代表已对外提交**，仍须人工签认（`EXTERNAL_FILING_GATE`）。
    """

    filing_period: str
    operator: str
    approver: str
    covered_oems: tuple[str, ...]
    covered_project_ids: tuple[str, ...]
    scope_disclaimer: str = config.EXTERNAL_FILING_GATE  # 🔴 锁①：指认既有红线，不重写文案


def cross_oem_filing_gate(
    *,
    filing_period: str,
    operator: str,
    approver: str,
    partition: OwnershipPartition,
    audit: AuditLogger | None = None,
) -> CrossOemFilingReceipt:
    """②(c) 跨 OEM 汇总的强制闸口——任何跨项目汇总在产出结果前 MUST 先过这里。

    🔴 开关默认 OFF（`config.cross_oem_aggregation_enabled()`）：翻开条件 ＝ ② 的豁免款
    已正式立进《OEM 数据隔离规范》。**裁决已下 ≠ 规范已立**——代码先于规范落地，在
    IATF「单一可信源」审核下站不住，故开关关闭时本函数 fail-loud，不静默放行、
    也不静默返回空结果。

    三道锁：
      ① 限用途 —— 回执携带 `EXTERNAL_FILING_GATE`（指认既有红线，不重写文案）；
      ② 限流向 —— 本函数只返回内存对象，不写入任何库/RAG（落盘打包属 §5，本批不做）；
      ③ 限留痕与人工闸 —— `filing_period`/`operator`/`approver` 三者必填非空，写 audit
        （覆盖项目清单取自已过 `partition_by_ownership` 排除的 `partition.eligible`）；
        回执不代表已对外提交，对外仍须人工签认。

    🔴 本函数不做金额求和/科目归集——那是辅助账/备查资料包的业务逻辑（§5，design 审
    未全部通过前不得开工）。本函数只做"能不能过闸"与"过闸留痕"。

    `partition` 须先经 `partition_by_ownership()` 产出：本函数不重新判定归属，只在
    已排除未判项目的基础上（`partition.eligible`）计算本次覆盖到的 OEM 与项目清单。
    """
    if not config.cross_oem_aggregation_enabled():
        raise CrossOemAggregationDisabledError(
            "跨 OEM 汇总开关为 OFF（环境变量 FI9_CROSS_OEM_AGGREGATION）。"
            "裁决已下 ≠ 规范已立：②(c) 的豁免款须先正式立进《OEM 数据隔离规范》"
            "（3-治理与合规/OEM数据隔离规范.md §2/§3）才可翻开，本函数在此之前"
            "一律拒绝，不静默返回空结果、也不降级为单 OEM 结果。"
        )

    missing = [
        name
        for name, value in (
            ("filing_period", filing_period),
            ("operator", operator),
            ("approver", approver),
        )
        if not (isinstance(value, str) and value.strip())
    ]
    if missing:
        raise CrossOemFilingLockError(
            f"跨 OEM 汇总三道锁缺失必填字段：{'、'.join(missing)}。"
            "申报期间／经办人／审批人三者均不得为空——这份材料报给政府，留痕不可简化。"
        )

    covered_oems = tuple(sorted({p.oem_customer for p in partition.eligible if p.oem_customer != NON_OEM_PROJECT}))
    covered_project_ids = tuple(p.project_id for p in partition.eligible)

    if audit is not None:
        audit.record(
            AuditEvent(
                scenario="FI9",
                action="cross_oem_aggregation",
                evaluator=approver,
                automation_level="L2",
                decision=config.audit_decision(
                    filing_period=filing_period,
                    operator=operator,
                    approver=approver,
                    covered_project_ids=list(covered_project_ids),
                    excluded_unjudged_project_ids=list(partition.excluded_project_ids),
                ),
                # E2.3：已注册 OEM 显示名按字典序去重逗号连接；只覆盖 NON_OEM_PROJECT 时填其本身。
                oem_context=",".join(covered_oems) if covered_oems else NON_OEM_PROJECT,
            )
        )

    return CrossOemFilingReceipt(
        filing_period=filing_period,
        operator=operator,
        approver=approver,
        covered_oems=covered_oems,
        covered_project_ids=covered_project_ids,
    )
