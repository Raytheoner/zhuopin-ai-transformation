"""通用通知通道（supplychain 收割）：企微推送 + L2 门禁派发器。"""
from . import wecom
from .dispatch import Notifier

__all__ = ["wecom", "Notifier"]
