"""队列本地追加因编辑锁占用被推迟时的暂存与补录（队列 #168）。

机器人归档一条消息后，若队列文件当前被人类会话持锁编辑，
`queue_appender.append_pending_task` 会抛 `QueueLockBusy`——此时消息本体
已经归档成功（`intake.py::archive_inbound_message` 落盘发生在追加队列行
之前），只是"这一行还没登记进队列、对应的 git 提交也还没做"这一步需要
推迟，**不是消息丢了**。本模块把推迟的追加参数原样存成 JSONL，下一条
消息到达时（见 `connection.py::on_message` 开头调用 `flush_pending_queue_
appends`）优先尝试补录：成功即从暂存移除，并继续走一遍完整的
`queue_git_sync.sync_after_archive`（本地追加+git 同步），与消息刚到达时
走的路径完全一致，复用它既有的降级/告警机制，不重复实现一套。
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger

from . import pending_jsonl
from .queue_appender import append_pending_task
from .queue_edit_lock import QueueLockBusy
from .queue_git_sync import sync_after_archive


def record_deferred_append(pending_path: Path, record: dict) -> None:
    """把本次因锁占用被推迟的追加参数原样追加进暂存 JSONL（一行一条，
    append-only，与 `queue_git_sync._append_pending_record` 同构但物理文件
    独立——两者代表不同的失败模式，混在一起会让人工排查时分不清"这行是
    锁占用暂存的，还是 git 推送失败暂存的"）。队列 #286：读写细节已抽到
    中立的 `pending_jsonl` 模块，供 `queue_git_sync.py` 一并复用（`_append_
    pending_record` 那类 git 推送失败也会被识别为锁占用时改用本函数落到
    同一个暂存文件，见该模块 `_route_queue_lock_busy_to_lock_pending`）。"""
    pending_jsonl.append_record(pending_path, record)


def read_deferred_appends(pending_path: Path) -> list[dict]:
    """按 FIFO 顺序读出暂存记录；文件不存在/为空返回空列表。"""
    return pending_jsonl.read_records(pending_path)


def _rewrite_deferred_appends(pending_path: Path, remaining: list[dict]) -> None:
    """用剩余记录整体重写暂存文件；剩余为空时直接删除该文件（体积恒定，
    不留一个永远的空文件）。"""
    pending_jsonl.rewrite_records(pending_path, remaining)


async def flush_pending_queue_appends(
    *,
    pending_path: Path,
    queue_path: Path,
    repo_root: Path,
    audit: AuditLogger,
    lock_factory: Callable[[], object],
    connector=None,
    recipient: str = "",
    fallback_send: Optional[Callable[[str], None]] = None,
    evaluator: str = "system",
    remote: str = "origin",
    branch: str = "master",
    git_sync_pending_path: Optional[Path] = None,
) -> int:
    """按 FIFO 顺序尝试补录此前因编辑锁占用被推迟的队列行。

    逐条处理，**保序**：本条仍锁忙（人类可能仍在编辑）就立即停止，不跳过
    它去尝试后面的（否则补录顺序会乱，且下次还得重新判断"哪些真的还没
    补"）；本条成功则从暂存移除、继续尝试下一条，并顺带走一遍
    `queue_git_sync.sync_after_archive`（与正常路径一致，同样享有它的
    降级/告警机制，不必在这里重新实现一套失败处理）。

    `lock_factory`：每条记录都调用一次，构造一把全新的锁——不复用同一把
    锁跨多条记录，保持"每次追加各自独立 acquire/release"的语义，与正常
    消息到达时的行为一致。

    返回本次成功补录的行数（供调用方按需审计/日志，不强制）。
    """
    records = read_deferred_appends(pending_path)
    if not records:
        return 0

    flushed = 0
    remaining = list(records)
    for record in records:
        lock = lock_factory()
        try:
            row = append_pending_task(
                queue_path, audit=audit, lock=lock, **record["append_kwargs"]
            )
        except QueueLockBusy:
            break

        remaining.pop(0)
        flushed += 1
        audit.record(AuditEvent(
            scenario="wecom-aibot", action="queue_append_pending_flushed", evaluator=evaluator,
            automation_level="L1",
            decision={"recorded_at": record.get("recorded_at", "")},
            data_sources={"sender": record.get("sender", "")},
        ))
        await sync_after_archive(
            repo_root=repo_root,
            queue_path=queue_path,
            append_kwargs=record["append_kwargs"],
            already_appended_row=row,
            audit=audit,
            connector=connector,
            recipient=recipient,
            fallback_send=fallback_send,
            pending_path=git_sync_pending_path,
            # 注意：故意不传 `lock_pending_path=pending_path`——本函数仍在
            # 迭代 `pending_path` 并会在循环结束后用 `_rewrite_deferred_
            # appends` 整体重写该文件；若这里再次锁忙并直接 append 回同一
            # 文件，会被随后的整体重写覆盖丢失。若这次重算恰好再次撞上
            # 锁忙，改落 `git_sync_pending_path`（由 `flush_pending_git_
            # sync_appends` 在下一条消息到达时接手补录），只是多一轮
            # 延迟，不会丢。
            evaluator=evaluator,
            remote=remote,
            branch=branch,
            lock_factory=lock_factory,
        )

    _rewrite_deferred_appends(pending_path, remaining)
    return flushed
