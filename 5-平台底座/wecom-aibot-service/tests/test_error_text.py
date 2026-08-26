"""队列 #416 ⑵ 的反例测试：对旧实现（`str(exc)`）必须变红。"""
from __future__ import annotations

import asyncio

from aibot_service.error_text import describe_exception


def test_no_arg_exception_keeps_type_name():
    """🔴 本条就是元缺陷本身：`str(asyncio.TimeoutError())` 是空串。"""
    assert str(asyncio.TimeoutError()) == ""          # 旧实现写进审计的东西
    assert describe_exception(asyncio.TimeoutError()) == "TimeoutError"


def test_message_bearing_exception_keeps_both():
    assert describe_exception(ValueError("文件消息缺 file_url")) == (
        "ValueError: 文件消息缺 file_url"
    )


def test_no_trailing_separator_when_message_empty():
    assert describe_exception(RuntimeError("")) == "RuntimeError"


def test_custom_exception_type_name_survives():
    class QueueLockBusyLike(RuntimeError):
        pass

    assert describe_exception(QueueLockBusyLike()) == "QueueLockBusyLike"
