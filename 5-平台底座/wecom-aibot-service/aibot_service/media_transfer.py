"""media 通道（下载/上传/发送）的重试 + 可配超时（队列 #416 ⑴，2026-08-26）。

**事故**：2026-08-26 13:19 唐燕萍同时发来文本＋文件，文本 13:19:38 归档成功，
文件 13:19:50 `message_dispatch_failed` ＋ 13:20:01 `forward_dispatch_failed`，
`7-外部文档` 下没有那份 .docx。真因＝media 通道下载超时（SDK 侧 `Reply ack
timeout (5.0s) for reqId: aibot_upload_media_chunk_*`），恰撞在一段反复断线
重连的窗口内（13:18:39–13:21:11 共 4 次 disconnected/reconnecting）。同一形态
在迁移之前（08:16 姚祖怡）就已出现过，只是那次归档成功、仅转发失败，没人察觉。

🔴 **不做静默跳过**。本模块只提供三件事：
⑴ **重试**——一次 ack 超时并不代表这份文件下不下来，尤其在重连窗口内；
⑵ **超时可配**——SDK 的 5.0s ack 等待对一份 40KB 的 docx 分片而言偏紧，
   本层再包一道**可配**的整体超时，环境变量见 `connection.py`；
⑶ **失败可辨识**——耗尽重试后抛 `MediaTransferError`，它带着**每一次**
   尝试的类型名与消息（见 `error_text.describe_exception`：无参异常的
   `str()` 是空的，只记 `str(exc)` 等于什么都没记）。

⚠️ **重试次数与超时的取值不由本模块拍板**：默认值是保守的工程默认
（3 次 / 20 秒），**不是判据**。真实值需要 Shao Peishen 按「专员等多久算
可接受」定，未定之前不要把默认值当成已裁定的口径。
"""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger

from .error_text import describe_exception

# 保守工程默认，非判据——见模块 docstring 的黄字。
DEFAULT_MEDIA_MAX_ATTEMPTS = 3
DEFAULT_MEDIA_TIMEOUT_SECONDS = 20.0
DEFAULT_MEDIA_BACKOFF_SECONDS = 1.0


class MediaTransferError(RuntimeError):
    """media 通道重试耗尽。**刻意是独立异常类型**——调用方据此判断"这一次
    该请发件人重发"，而不是靠字符串匹配去猜异常是不是超时。"""

    def __init__(self, stage: str, attempts: int, errors: list[str]) -> None:
        self.stage = stage
        self.attempts = attempts
        self.errors = errors
        super().__init__(
            f"media {stage} 重试 {attempts} 次仍失败：" + "；".join(errors)
        )


async def with_media_retry(
    operation: Callable[[], Awaitable[Any]],
    *,
    stage: str,
    audit: Optional[AuditLogger] = None,
    evaluator: str = "system",
    max_attempts: int = DEFAULT_MEDIA_MAX_ATTEMPTS,
    timeout_seconds: float = DEFAULT_MEDIA_TIMEOUT_SECONDS,
    backoff_seconds: float = DEFAULT_MEDIA_BACKOFF_SECONDS,
    context: Optional[dict] = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> Any:
    """跑 `operation()`，超时即重试，指数退避；耗尽抛 `MediaTransferError`。

    `timeout_seconds <= 0` 时不加本层超时（只依赖 SDK 自身的 ack 超时）——
    留这个口子是为了在排查时能把本层完全摘掉，看清底层到底等了多久。

    **每一次失败都单独留痕**（`media_transfer_retry`），不只记最后一次：
    「第 1 次超时、第 2 次连接断、第 3 次超时」与「三次都超时」是两种不同
    的故障，合并成一条就分不出来了。
    """
    errors: list[str] = []
    for attempt in range(1, max_attempts + 1):
        try:
            if timeout_seconds and timeout_seconds > 0:
                return await asyncio.wait_for(operation(), timeout=timeout_seconds)
            return await operation()
        except asyncio.CancelledError:
            # 🔴 取消不是失败，不吞、不重试——吞掉它会让服务关不掉。
            raise
        except Exception as exc:  # noqa: BLE001 —— 本层的职责就是把它变成"再试一次"
            detail = describe_exception(exc)
            errors.append(f"第{attempt}次 {detail}")
            if audit is not None:
                audit.record(AuditEvent(
                    scenario="wecom-aibot",
                    action="media_transfer_retry",
                    evaluator=evaluator,
                    automation_level="L1",
                    decision={
                        "stage": stage,
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "timeout_seconds": timeout_seconds,
                        "will_retry": attempt < max_attempts,
                    },
                    data_sources=dict(context or {}),
                    error=detail,
                ))
            if attempt >= max_attempts:
                break
            if backoff_seconds > 0:
                await sleep(backoff_seconds * (2 ** (attempt - 1)))
    raise MediaTransferError(stage, max_attempts, errors)


def build_resend_notice(sender: str, error: BaseException) -> str:
    """请发件人重发的提示文案（🔴 **不静默**——队列 #416 ⑴ 点名要的就是这条）。

    只说"没收到、请重发"，**不解释内部异常细节**：专员既不需要也看不懂
    `TimeoutError`，而完整细节已经在审计里。
    """
    reason = "网络超时" if isinstance(error, MediaTransferError) else "传输异常"
    return (
        f"⚠️ {sender} 你好，刚才那份**附件没能收到**（{reason}），"
        "机器人已重试仍未成功，**这份文件没有入档**。\n"
        "麻烦**重新发一次**；若连续失败请直接告知邵培深。\n"
        "（同时发来的文字内容不受影响，已正常归档。）"
    )
