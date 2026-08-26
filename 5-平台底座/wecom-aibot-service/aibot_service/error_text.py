"""异常 → 审计 `error` 字段文案（队列 #416 ⑵，2026-08-26）。

🔴 **本模块存在的唯一理由**：`str(exc)` 对**无参异常**返回空串。
`asyncio.TimeoutError()` 是本服务最常见的失败形态之一（media 下载/上传
走 WS ack 等待，超时即抛无参 `TimeoutError`），它的 `str()` 就是 `""`
⇒ 审计里 `error` 全空，**「失败了」和「失败原因」同时消失**。

2026-08-26 唐燕萍附件未入档的排查里，三条失败事件（`message_dispatch_
failed` / `forward_dispatch_failed` / `pending_*_dispatch_failed`）的
`error` 全是空串，光"确认它是一次超时"就多花三步——而这一步之所以难，
正是因为**记录者把「异常对象」当成了「异常描述」**。类型名是无参异常
仅剩的信息，丢掉它等于什么都没记。

判据（写在这里因为它是通用的）：**留痕一个异常时，类型名必须出现在
文案里**——消息可以为空，类型名永远不为空。
"""
from __future__ import annotations


def describe_exception(exc: BaseException) -> str:
    """`f"{类型名}: {消息}"`，消息为空时只留类型名（不留一个尾随的 ": "）。

    >>> describe_exception(TimeoutError())
    'TimeoutError'
    >>> describe_exception(ValueError("文件消息缺 file_url"))
    'ValueError: 文件消息缺 file_url'
    """
    name = type(exc).__name__
    text = str(exc)
    return f"{name}: {text}" if text else name
