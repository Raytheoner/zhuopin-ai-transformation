"""通知派发器 —— L2 人工门禁 + 审计留痕（合规红线）。

职责：把满足 NotificationMessage Protocol 的消息经通道（默认企微）外发，但在外发前
执行 **L2 人工门禁**：高风险通报（推客户 / requires_confirmation / severity=critical）
必须有人工确认（confirmed_by）才放行，否则只保留草稿、绝不自动外发。

门禁语义为 **FAIL-CLOSED**（Blocker1）：通知对象缺 `requires_confirmation` 字段或严重度
未知时，一律按"高风险·需确认·不外发"处理，绝不默认放行自动发。

持久化钩子（Blocker2 接口预留）：L2 拦截的草稿经 `pending_sink` 交给上层持久化"待审批队列"。
本批仅暴露接口（`PendingApprovalSink` Protocol），SC8 接实际队列 + 审批流。

审计：每次外发/拦截动作经注入的 AuditLogger 留痕（动作类型 / 渠道 / 人工确认状态），
满足 IATF 可追溯。
"""
from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable

from ...audit import AuditEvent, AuditLogger
from ..crm_notifier.contracts import NotificationMessage
from . import wecom


@runtime_checkable
class PendingApprovalSink(Protocol):
    """L2 待审批队列持久化钩子（Blocker2 接口预留）。

    平台只定义接口；SC8 实现实际持久化（文件/DB 状态机），让 L2 责任人可检索、
    编辑、二次放行（再以 confirmed_by 调 Notifier.send）。
    """

    def enqueue(self, message: NotificationMessage, reason: str = "") -> None:
        """把被拦截的高风险草稿入队（持久化），等待人工审批。"""
        ...


class Notifier:
    """通知派发器（带 L2 门禁与审计）。

    Args:
        send_fn:      底层发送函数 (webhook_url, content) -> None。默认企微 send_markdown。
        webhook_url:  通道地址（从环境变量注入，不硬编码）。
        audit:        AuditLogger，记录通知动作（None 则不留痕）。
        scenario:     审计归属场景标识（如 "SC8"）。
        channel:      渠道名（审计用），默认 "wecom"。
        pending_sink: 待审批队列持久化钩子（Blocker2 预留接口）。拦截时把草稿入队；
                      None 时仅审计 blocked（草稿不持久化——上线前 SC8 必须接实际队列）。
    """

    def __init__(
        self,
        send_fn: Callable[[str, str], None] | None = None,
        webhook_url: str = "",
        audit: AuditLogger | None = None,
        scenario: str = "NOTIFY",
        channel: str = "wecom",
        pending_sink: PendingApprovalSink | None = None,
    ):
        self._send_fn = send_fn or wecom.send_markdown
        self._webhook_url = webhook_url
        self._audit = audit
        self._scenario = scenario
        self._channel = channel
        self._pending_sink = pending_sink

    @staticmethod
    def _is_high_risk(message: NotificationMessage) -> bool:
        """高风险判定（FAIL-CLOSED：未知即拦截）。

        判为高风险（需人工确认）当且仅当满足任一：
          · requires_confirmation 缺失/为 None（**未知即拦截**——绝不默认放行）；
          · requires_confirmation 为真；
          · severity 缺失/为 None（严重度未知，保守拦截）；
          · severity == "critical"。
        仅当 requires_confirmation 显式为 False 且 severity 为已知非 critical 时，才判低风险放行。
        """
        rc = getattr(message, "requires_confirmation", None)
        if rc is None:        # 字段未定义 → 未知即拦截
            return True
        if rc:                # 显式要求确认
            return True
        severity = getattr(message, "severity", None)
        if severity is None:  # 严重度未知 → 保守拦截
            return True
        return severity == "critical"

    def send(self, message: NotificationMessage, confirmed_by: str = "") -> bool:
        """外发一条通知。高风险且未确认 → 拦截（不外发，入待审批队列），返回 False。

        Returns:
            True  外发成功；False 被 L2 门禁拦截（仅留草稿 / 入队待审批）。
        """
        high_risk = self._is_high_risk(message)
        blocked = high_risk and not confirmed_by

        if blocked:
            # Blocker2：拦截的草稿交持久化钩子入队（接口预留，SC8 接实际队列）
            if self._pending_sink is not None:
                self._pending_sink.enqueue(message, reason="awaiting_L2_confirmation")
            self._record("notification_send_blocked", message, confirmed_by, sent=False)
            return False

        self._send_fn(self._webhook_url, message.body)
        self._record("notification_send", message, confirmed_by, sent=True)
        return True

    def _record(self, action: str, message: NotificationMessage,
                confirmed_by: str, sent: bool) -> None:
        if self._audit is None:
            return
        self._audit.record(AuditEvent(
            scenario=self._scenario,
            action=action,
            evaluator=confirmed_by,         # L2 责任人（拦截时为空）
            automation_level="L2",
            decision={
                "channel": self._channel,
                "recipient": getattr(message, "recipient", ""),
                "severity": getattr(message, "severity", None),
                # 审计如实记录原始值（缺失记为 None，便于追溯 fail-closed 触发）
                "requires_confirmation": getattr(message, "requires_confirmation", None),
                "confirmed_by": confirmed_by,
                "sent": sent,
                "queued_for_approval": (not sent) and self._pending_sink is not None,
            },
        ))
