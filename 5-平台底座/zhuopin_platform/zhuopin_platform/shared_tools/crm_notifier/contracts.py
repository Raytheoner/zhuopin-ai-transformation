"""通知输入契约（D3：用 Protocol 解耦，平台通知能力被多场景复用）。

两个 Protocol：
  · NotificationMessage —— 通用通知消息（收件人/标题/正文/严重度），通知通道与 L2 门禁只读这些字段。
  · DelayNoticeInput   —— CRM 延期通报草稿生成器的专用输入（客户/订单/原交期/新交期/原因列表）。

通知器/草稿器只依赖这些字段，不依赖任一场景的具体业务类（如 SC8 的 DelayCase）——
任意满足字段的对象（含 SC8 的 DelayCase 适配体）均可直接消费。
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class NotificationMessage(Protocol):
    """通用通知消息契约。通知通道（wecom 等）+ L2 门禁 + 审计只读这些字段。

    `requires_confirmation` 为**强约束字段**（合规红线，Blocker1）：必须由上层显式声明。
    L2 门禁采用 FAIL-CLOSED 语义——该字段缺失/未知时一律按"高风险·需人工确认·不外发"处理。
    """

    recipient: str               # 收件人/通报对象（客户名 / 内部群名）
    title: str                   # 标题/主题
    body: str                    # 正文
    severity: str                # 严重度：info / warning / critical
    requires_confirmation: bool  # 是否需 L2 人工确认（推客户等高风险必须为 True）


@runtime_checkable
class DelayNoticeInput(Protocol):
    """CRM 延期通报草稿生成器的输入契约（不耦合 DelayCase）。"""

    customer_name: str   # 客户
    so_id: str           # 订单号
    product_id: str      # 产品料号
    target_date: str     # 原承诺交期
    new_date: str        # 新预计交期
    delay_days: int      # 延期天数
    reasons: list        # 延期原因列表（list[str]）
