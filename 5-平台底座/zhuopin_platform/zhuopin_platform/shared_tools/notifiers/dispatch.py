"""通知派发器 —— L2 人工门禁 + 审计留痕（合规红线）。

职责：把满足 NotificationMessage Protocol 的消息经通道（默认企微）外发，但在外发前
执行 **L2 人工门禁**：高风险通报（推客户 / 标记 requires_confirmation / severity=critical）
必须有人工确认（confirmed_by）才放行，否则只保留草稿、绝不自动外发。

审计：每次外发/拦截动作经注入的 AuditLogger 留痕（动作类型 / 渠道 / 人工确认状态），
满足 IATF 可追溯。
"""
from __future__ import annotations

from typing import Callable

from ...audit import AuditEvent, AuditLogger
from ..crm_notifier.contracts import NotificationMessage
from . import wecom


class Notifier:
    """通知派发器（带 L2 门禁与审计）。

    Args:
        send_fn:     底层发送函数 (webhook_url, content) -> None。默认企微 send_markdown。
        webhook_url: 通道地址（从环境变量注入，不硬编码）。
        audit:       AuditLogger，记录通知动作（None 则不留痕）。
        scenario:    审计归属场景标识（如 "SC8"）。
        channel:     渠道名（审计用），默认 "wecom"。
    """

    def __init__(
        self,
        send_fn: Callable[[str, str], None] | None = None,
        webhook_url: str = "",
        audit: AuditLogger | None = None,
        scenario: str = "NOTIFY",
        channel: str = "wecom",
    ):
        self._send_fn = send_fn or wecom.send_markdown
        self._webhook_url = webhook_url
        self._audit = audit
        self._scenario = scenario
        self._channel = channel

    @staticmethod
    def _is_high_risk(message: NotificationMessage) -> bool:
        """高风险判定：显式要求确认，或严重度为 critical。"""
        if getattr(message, "requires_confirmation", False):
            return True
        return getattr(message, "severity", "") == "critical"

    def send(self, message: NotificationMessage, confirmed_by: str = "") -> bool:
        """外发一条通知。高风险且未确认 → 拦截（不外发），返回 False。

        Returns:
            True  外发成功；False 被 L2 门禁拦截（仅留草稿）。
        """
        high_risk = self._is_high_risk(message)
        blocked = high_risk and not confirmed_by

        if blocked:
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
                "severity": getattr(message, "severity", ""),
                "requires_confirmation": getattr(message, "requires_confirmation", False),
                "confirmed_by": confirmed_by,
                "sent": sent,
            },
        ))
