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

from zhuopin_platform.audit import AuditEvent, AuditLogger
from zhuopin_platform.shared_tools.notifiers.dispatch import Notifier

from . import gate, notify
from .models import DeliveryForecast
from .pending_queue import FilePendingQueue

SCENARIO = "SC8"


def build_notifier(
    queue: FilePendingQueue,
    audit: AuditLogger | None = None,
    send_fn=None,
    webhook_url: str = "",
) -> Notifier:
    """构造接好待审批队列与审计的 SC8 Notifier（pending_sink = 文件队列）。"""
    return Notifier(
        send_fn=send_fn,
        webhook_url=webhook_url,
        audit=audit,
        scenario=SCENARIO,
        channel="wecom",
        pending_sink=queue,
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
    """提交一条对客交付承诺（首道：未确认必拦入队，不外发）。"""
    first = gate.is_first_commitment(audit, fc.customer_name)
    requires, reasons, severity = gate.evaluate(fc, first_commitment=first)

    draft = notify.build_customer_draft(
        fc, requires_confirmation=requires, severity=severity,
        extra_reasons=reasons, api_key=api_key,
    )
    # Notifier 执行 fail-closed 门禁：requires 且无 confirmed_by → 拦截 + 入队（pending_sink）
    sent = notifier.send(draft)
    return CommitmentResult(
        sent=sent, requires_confirmation=requires,
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
