"""对客交付承诺编排（门禁 → 草稿 → Notifier → 待审批队列 → 审批放行 → 审计）。

把单条交付预期跑完 L2 闭环：
  1. gate.evaluate 判定是否需人工确认（低置信/晚于目标日/首次承诺）；
  2. notify.build_customer_draft 出草稿（门禁字段由 SC8 覆盖）；
  3. 经平台 Notifier 外发——需确认且无 confirmed_by → 拦截入 FilePendingQueue；
  4. 责任人 queue.approve(id, confirmed_by) → 外发 + 原子标记 'sent'（幂等）。
全链审计经平台 audit（预测在 pipeline 记录；外发/拦截/确认由 Notifier 记录）。
"""
from __future__ import annotations

from dataclasses import dataclass

from typing import Callable

from zhuopin_platform.audit import AuditEvent, AuditLogger
from zhuopin_platform.shared_tools.notifiers.dispatch import Notifier

from . import config, gate, notify
from .models import DeliveryForecast
from .pending_queue import FilePendingQueue

SCENARIO = "SC8"


def build_notifier(
    queue: FilePendingQueue,
    audit: AuditLogger | None = None,
    send_fn=None,
    webhook_url: str = "",
    outbound_enabled: bool | Callable[[], bool] | None = None,
) -> Notifier:
    """构造接好待审批队列与审计的 SC8 Notifier（pending_sink = 文件队列）。

    第二道结构性闸门（A2 / 审计报告 P0-A）：`outbound_enabled` 默认接到
    `config.CUSTOMER_OUTBOUND_ENABLED`——总开关关闭时即便人工 approve 也不外发。
    测试可显式传 `outbound_enabled=True` 验证 approve→放行机制本身。
    """
    if outbound_enabled is None:
        outbound_enabled = lambda: config.CUSTOMER_OUTBOUND_ENABLED  # noqa: E731
    return Notifier(
        send_fn=send_fn,
        webhook_url=webhook_url,
        audit=audit,
        scenario=SCENARIO,
        channel="wecom",
        pending_sink=queue,
        outbound_enabled=outbound_enabled,
    )


@dataclass
class CommitmentResult:
    sent:                  bool          # 是否已外发（False=被门禁拦截入队）
    requires_confirmation: bool
    reasons:               list          # 门禁触发原因
    draft_title:           str


def submit_commitment(
    fc: DeliveryForecast,
    notifier: Notifier,
    audit: AuditLogger | None = None,
    api_key: str | None = None,
) -> CommitmentResult:
    """提交一条对客交付承诺（首道：一律入待审批队列，绝不自动外发）。

    A2 / 审计报告 P0-A 修复：删除"高置信+非首次+不晚于目标日 → 低风险自动放行外发"旁路。
    首道提交**一律**入队（draft.requires_confirmation 恒置 True），真正外发只能由 L2
    责任人经 `queue.approve(item_id, confirmed_by)` 二次放行触发。门禁 `evaluate` 给出的
    真实风险（requires/severity/reasons）仍如实写入草稿与 CommitmentResult，供审计/展示。
    """
    first = gate.is_first_commitment(audit, fc.customer_name)
    requires, reasons, severity = gate.evaluate(fc, first_commitment=first)

    # 首道恒入队：草稿 requires_confirmation 置 True，杜绝低风险经 Notifier 直发。
    # severity/reasons 仍取门禁真实值（审计如实留痕，不因 policy 恒入队而掩盖真实风险）。
    draft = notify.build_customer_draft(
        fc, requires_confirmation=True, severity=severity,
        extra_reasons=reasons, api_key=api_key,
    )
    # B3：标注所需审批级别（重点客户/首次承诺 → VP），入队后由 approve 校验确认人级别。
    draft.required_level = config.required_approval_level(
        fc.customer_name, first_commitment=first)
    # Notifier 双闸门：requires_confirmation=True 必被 L2 fail-closed 拦截入队（pending_sink）；
    # 第二道总开关（CUSTOMER_OUTBOUND_ENABLED）关闭时亦拦截，互为冗余。
    sent = notifier.send(draft)
    return CommitmentResult(
        sent=sent, requires_confirmation=requires,   # 保留门禁真实风险判定
        reasons=reasons, draft_title=draft.title,
    )


def record_correction(
    audit: AuditLogger,
    original_so_id: str,
    fc: DeliveryForecast,
    reason: str,
    trigger_signal: str,
    evaluator: str,
) -> None:
    """更正事件写审计（D4 / SOP §1.4）：关联原预测 so_id，原记录不删（append-only）。"""
    audit.record(AuditEvent(
        scenario=SCENARIO,
        action="delivery_forecast_correction",
        evaluator=evaluator,
        automation_level="L2",
        decision={
            "original_so_id": original_so_id,          # 关联原预测记录
            "product_id": fc.product_id,
            "customer_name": fc.customer_name,
            "corrected_forecast_date": fc.forecast_date.isoformat() if fc.forecast_date else None,
            "reason": reason,                           # 更正原因
            "trigger_signal": trigger_signal,          # 触发信号
            "param_version": fc.param_version,
        },
    ))
