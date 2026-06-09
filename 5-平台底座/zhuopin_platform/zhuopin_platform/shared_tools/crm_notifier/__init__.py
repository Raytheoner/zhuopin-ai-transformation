"""CRM 延期通报草稿（supplychain 收割，D3 解耦：只读 Protocol，不依赖 DelayCase）。"""
from .contracts import NotificationMessage, DelayNoticeInput
from .draft import (
    NotificationDraft,
    DEFAULT_MODEL,
    build_prompt,
    template_draft,
    generate_draft,
)

__all__ = [
    "NotificationMessage",
    "DelayNoticeInput",
    "NotificationDraft",
    "DEFAULT_MODEL",
    "build_prompt",
    "template_draft",
    "generate_draft",
]
