"""S4 桥一（队列 #366 M1）：回件到达即在跟进信 README 打中间态。

## 它补的是哪一格

**串行闸永远不会自己开。** 闸的判据源是 `README-跟进机制与命名约定.md` 的
「发送状态」列，而机器只写队列：回件到达时本服务自动追 §一 入信行（做到
了）、拆件回灌由人写队列行（做到了）、**唯独没有任何东西去改 README 那一
格**。2026-08-21 当天两次真实咬人——采购部#17 的回件 13:13:24 落盘、队列
13:15 就自动追了行，而 README 状态列一动没动，闸对姚祖怡仍锁着。

本模块让「回件物理到达」这件事**在权威源上立刻可见**：把该信的状态改写为
第九态 `📨 回件已到，待拆件 <UTC>`。

🔴 **第九态仍属在途、闸仍锁**——它不是「闭环」的弱化版，而是「已推送」与
「已回件并回灌」之间那段此前完全不可见的空白。真正开闸仍须人拆件回灌后
转闭环四态（由 S4 桥二在 `release` 上强制，见 `工具-共享文档编辑锁.py::
_validate_followup_reply_state_sync`）。

## 三条硬约束

1. **匹配不上就不动 README**（派单件 §二 原文「匹配不上时不要猜」）。
   配对只走 `followup_gate.reply_matches_letter`（归一化后 stem 逐字相等）。
   纯文本反馈类回件天然配不上——**这是设计取舍，不是缺陷**：一条文本回件
   无法确定地指向哪一封信，硬配会造出比漏配更难发现的错误。
   未匹配时 **fail-loud**：记审计事件 ＋ 打印 WARN，不静默跳过。
2. **必须走编辑锁**，不得直接写文件绕开协议〇.7。复用既有
   `SubprocessQueueEditLock`（与队列写入同一把协议实现，不分叉）。
3. **`acquire` 拿不到锁必须重试**（指数退避，默认 3 次）；**放弃时必须
   打日志并告警**，不得静默。锁忙不是"没事发生"，是"这条回件的可见性这次
   丢了"。

## 为什么不做「拿不到锁就暂存、下次补录」

队列侧那条路径（`queue_lock_pending.py`）之所以成立，是因为**队列行丢了
等于这条回件在调度视野里从未发生**，代价极高。README 这一格不同：即使
本次没打上，**桥二仍会在拆件 release 时把人拦下来**——两座桥是冗余而非串
联，缺一座不会漏。故此处只做有限重试 ＋ 告警，不新增第三个暂存文件。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable, Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger
from zhuopin_platform.shared_tools import followup_gate

from .queue_edit_lock import QueueLockBusy
from .readme_table import ReadmeTableError, iter_rows, extract_target_filename, write_status

# 🔴 必须是**仓库相对、正斜杠**的字面量：`工具-共享文档编辑锁.py::cmd_release`
# 按 `args.file == FOLLOWUP_README_TARGET` 逐字比对来决定跑不跑 README 那套
# release 校验。传绝对路径能锁住文件，但那道校验会**静默不跑**（同
# CLAUDE.md §5「工具静默回退」）；传 `Path("a/b")` 在 Windows 上 `str()` 出来
# 是反斜杠，同样比不中。`PurePosixPath` 的 `str()` 在任何平台都是正斜杠。
FOLLOWUP_README_REL = "6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md"
LOCK_TARGET = PurePosixPath(FOLLOWUP_README_REL)

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_SECONDS = 2.0

ACTION_MARKED = "marked"
ACTION_UNMATCHED = "unmatched"
ACTION_ALREADY = "already_beyond"
ACTION_LOCK_BUSY = "lock_busy"
ACTION_NO_README = "no_readme"


@dataclass
class BridgeResult:
    action: str
    letter_number: Optional[str] = None
    detail: str = ""


def _utc_stamp(now: Optional[datetime] = None) -> str:
    """UTC，且**显式带 `Z`**——根 CLAUDE.md §5 硬规则：引用任何时刻前先答
    一句「这是 UTC 还是本地」，并在输出里标基准。本服务其余留痕（审计
    JSONL、告警文案）同样是真 UTC，此处保持一致。"""
    moment = now or datetime.now(tz=timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_reply_arrived_status(previous_status: str, archived_filename: str,
                               now: Optional[datetime] = None) -> str:
    """新状态值 ＝ 第九态前缀 ＋ UTC 戳 ＋ 溯源，**原状态原样接在后面**。

    前缀在最前，是因为闭环判据一律按前缀比对；旧状态不删，是因为「这封信
    是什么时候推送的」是后续转闭环态时要引用的事实——**覆盖式写入会把它
    弄丢，而这一格没有任何别处的副本**。
    """
    stamp = _utc_stamp(now)
    return (
        f"{followup_gate.REPLY_ARRIVED_STATUS} {stamp}"
        f"（企微机器人自动标记，入信归档 `{archived_filename}`；"
        f"**仍属在途、串行闸仍锁**，拆件回灌后须转闭环四态之一）"
        f"　━━━　原状态 ━━━　{previous_status}"
    )


def _locate_letter(readme_text: str, archived_filename: str):
    """按目标文件标注找到这封回件对应的 README 行；找不到返回 None。"""
    for row in iter_rows(readme_text):
        topic_cell = row.cells[3] if len(row.cells) > 3 else ""
        target = extract_target_filename(topic_cell)
        if not target:
            continue
        if followup_gate.reply_matches_letter(archived_filename, target):
            return row
    return None


def _row_number(row) -> str:
    return row.cells[0] if row.cells else "?"


def mark_reply_arrived(
    *,
    archived_filename: str,
    repo_root: Path,
    audit: AuditLogger,
    lock_factory: Callable[[], object],
    evaluator: str = "system",
    now: Optional[datetime] = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    alert_send: Optional[Callable[[str], None]] = None,
    log: Callable[[str], None] = print,
) -> BridgeResult:
    """把 `archived_filename` 对应的那封信在 README 上标为第九态。

    **本函数绝不向上抛**——它是归档主流程的旁路增强，任何失败都不得让一条
    已经成功归档的回件反过来算作处理失败（同 `sync_after_archive` 的既有
    契约）。失败一律走审计 ＋ 告警。
    """
    readme_path = repo_root / FOLLOWUP_README_REL
    try:
        readme_text = readme_path.read_text(encoding="utf-8")
    except OSError as exc:
        return _record(audit, evaluator, BridgeResult(
            ACTION_NO_README, detail=f"README 读取失败：{readme_path}（{exc}）"
        ), log=log)

    try:
        row = _locate_letter(readme_text, archived_filename)
    except ReadmeTableError as exc:
        return _record(audit, evaluator, BridgeResult(
            ACTION_NO_README, detail=f"README 表格解析失败：{exc}"
        ), log=log)

    if row is None:
        return _record(audit, evaluator, BridgeResult(
            ACTION_UNMATCHED,
            detail=(
                f"入信归档件 `{archived_filename}` 未能确定地对应 README 任何一行"
                "（纯文本反馈、或该行未带队列 #241 的 `目标文件：` 标注）"
                "——按「匹配不上时不要猜」未改 README，只追了队列行。"
            ),
        ), log=log)

    current_status = row.cells[row.status_col_index]
    if (followup_gate.is_closed_status(current_status)
            or followup_gate.is_reply_arrived_status(current_status)):
        # 幂等：同一条回件重投、或人已抢先转态，都不该把状态往回推。
        return _record(audit, evaluator, BridgeResult(
            ACTION_ALREADY, letter_number=_row_number(row),
            detail=f"README「{_row_number(row)}」已处于「"
                   f"{followup_gate.normalize_status(current_status)[:30]}」，不覆盖。",
        ), log=log)

    lock = lock_factory()
    last_error = ""
    for attempt in range(1, max_attempts + 1):
        try:
            lock.try_acquire()
        except QueueLockBusy as exc:
            last_error = str(exc)
            if attempt < max_attempts:
                sleep(backoff_seconds * (2 ** (attempt - 1)))
                continue
            break
        try:
            # 🔴 持锁后**重读重定位**：从上面那次读到现在，别的会话可能已经
            # 改过这一格（这正是编辑锁存在的理由）。用锁外读到的
            # `RowLocation` 直接写回，等于把别人的改动按行号覆盖掉。
            fresh_text = readme_path.read_text(encoding="utf-8")
            fresh_row = _locate_letter(fresh_text, archived_filename)
            if fresh_row is None:
                return _record(audit, evaluator, BridgeResult(
                    ACTION_UNMATCHED,
                    detail=f"持锁后重定位失败（README 在此期间被改动？）：{archived_filename}",
                ), log=log)
            fresh_status = fresh_row.cells[fresh_row.status_col_index]
            if (followup_gate.is_closed_status(fresh_status)
                    or followup_gate.is_reply_arrived_status(fresh_status)):
                return _record(audit, evaluator, BridgeResult(
                    ACTION_ALREADY, letter_number=_row_number(fresh_row),
                    detail="持锁后重读发现已被转态，不覆盖。",
                ), log=log)
            readme_path.write_text(
                write_status(
                    fresh_text, fresh_row,
                    build_reply_arrived_status(fresh_status, archived_filename, now),
                ),
                encoding="utf-8",
            )
            return _record(audit, evaluator, BridgeResult(
                ACTION_MARKED, letter_number=_row_number(fresh_row),
                detail=f"README「{_row_number(fresh_row)}」已标为"
                       f"「{followup_gate.REPLY_ARRIVED_STATUS}」。",
            ), log=log)
        finally:
            lock.release()

    result = BridgeResult(
        ACTION_LOCK_BUSY, letter_number=_row_number(row),
        detail=(
            f"README 编辑锁 {max_attempts} 次重试后仍占用，"
            f"「{_row_number(row)}」本次未标第九态（回件已正常归档、队列行已追）"
            f"——桥二会在拆件 release 时兜住，不会漏。最后一次：{last_error}"
        ),
    )
    if alert_send is not None:
        try:
            alert_send(result.detail)
        except Exception:  # noqa: BLE001 —— 告警自身失败不得反过来破坏本函数"不抛"的契约
            pass
    return _record(audit, evaluator, result, log=log)


def _record(audit: AuditLogger, evaluator: str, result: BridgeResult,
            *, log: Callable[[str], None]) -> BridgeResult:
    """统一留痕：审计事件 ＋ 一行可见输出。**每一条分支都经过这里**，
    包括"没做事"的那几条——静默跳过正是本模块要消灭的东西。"""
    prefix = {
        ACTION_MARKED: "✓", ACTION_ALREADY: "·",
        ACTION_UNMATCHED: "⚠", ACTION_LOCK_BUSY: "⚠", ACTION_NO_README: "⚠",
    }.get(result.action, "·")
    try:
        log(f"{prefix} [跟进信README桥] {result.detail}")
    except Exception:  # noqa: BLE001
        pass
    try:
        audit.record(AuditEvent(
            scenario="wecom-aibot",
            action=f"followup_readme_bridge_{result.action}",
            evaluator=evaluator,
            automation_level="L1",
            decision={"letter_number": result.letter_number or ""},
            data_sources={"detail": result.detail},
        ))
    except Exception:  # noqa: BLE001 —— 留痕失败不得反过来破坏"不抛"的契约
        pass
    return result
