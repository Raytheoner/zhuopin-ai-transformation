"""PMC 确认门禁 —— SC11 唯一一条**现在就必须落地**的红线。

## 门禁原文（采购专线 2026-07-06 定，全景规划 §2.1.2 SC11 块后加固注）

> 调拨清单落 ERP ＋ 外发邮件**须 PMC 经理人工确认后执行，AI 不自动落库、不自动外发**；
> 调拨决策写平台 `audit`（根 `CLAUDE.md` §7 L2 门禁）。

前置总表 SC11 行备注也点名「PMC 确认门禁写入 openspec」。⇒ 这条**不依赖任何前置**，
是本骨架期能交付的实心内容，故先于路径算法落地。

## 两条实现立场

**⑴ 确认状态的唯一判据是拟稿自身的 `approved_by`。** 执行侧函数不接受任何形如
`force=True` / `already_confirmed=True` 的旁路参数 —— 一个能被参数关掉的门禁，
在下一次赶工时就会被关掉。

**⑵ 即便已确认，骨架期两个执行侧动作仍然抛。** 真实 ERP 写入与邮件外发都还没接，
而"确认过了"和"能执行了"是两件事。此处若为了让流程"看起来通"而静默 no-op，
就会产出一条 audit 说落库成功、而 ERP 里什么都没有。
"""
from __future__ import annotations

from datetime import datetime, timezone

from .models import TransferPlanDraft


class PmcApprovalRequired(RuntimeError):
    """未经 PMC 经理确认即试图落库或外发。"""


class NotWiredYet(RuntimeError):
    """已确认，但该执行通道尚未接入（骨架期恒抛）。"""


def approve(draft: TransferPlanDraft, pmc_manager: str) -> TransferPlanDraft:
    """记录 PMC 经理的人工确认。

    `pmc_manager` 是实名 —— L2 门禁要的是可归责人，不是一个布尔值（IATF 16949）。
    """
    if not pmc_manager.strip():
        raise ValueError("PMC 确认须实名：门禁要的是可归责人，不是一个布尔值")
    draft.approved_by = pmc_manager.strip()
    draft.approved_at = datetime.now(tz=timezone.utc).isoformat()
    return draft


def _require_approved(draft: TransferPlanDraft, action: str) -> None:
    if not draft.is_approved:
        raise PmcApprovalRequired(
            f"{action} 须 PMC 经理人工确认后执行，AI 不自动执行。\n"
            f"  门禁来源：采购专线 2026-07-06；全景规划 §2.1.2 SC11 门禁加固注；根 CLAUDE.md §7-4\n"
            f"  ⇒ 先调 gate.approve(draft, pmc_manager='<实名>')。"
        )


def commit_to_erp(draft: TransferPlanDraft) -> None:
    """把调拨清单落 ERP 库存模块。骨架期：确认闸在前，通道未接在后，两道都不跳过。"""
    _require_approved(draft, "调拨清单落 ERP")
    raise NotWiredYet(
        "ERP 库存模块写入通道尚未接入（前置：生产计划数据通路 / U9C 写权限，本机 off-LAN 亦无法验证）。"
        " 刻意不静默 no-op —— 否则会产出一条『落库成功』的 audit 而 ERP 里什么都没有。"
    )


def notify_outsourced_warehouse(draft: TransferPlanDraft) -> None:
    """邮件通知委外仓收货人。骨架期：同上两道闸。"""
    _require_approved(draft, "外发邮件通知委外仓收货人")
    raise NotWiredYet(
        "外发邮件通道尚未接入。🔴 对外真实消息属最高档动作，接入后仍须逐次走对外发送纪律，"
        " 不因 PMC 已确认调拨内容而自动获得发信授权（两件事、两道授权）。"
    )
