"""队列本地追加成功后，自动同步到 GitHub master（design.md D1）。

`queue_appender.append_pending_task()` 本身不改——本模块新增独立的 git 层
乐观并发重试：推送被拒绝（origin 已前进）时，**不**做 `git pull --rebase`
式的重放（那只会重放"插入这一行"的动作，不会重新计算编号该是多少），而是
fetch 最新内容、把队列文件对齐到 origin 的最新版本，再**重新调用**
`append_pending_task()` 对最新内容重新计算插入点与编号——历史事故（队列
#69/#70、07-23 两次撞号）的真实模式是"两个写手各自基于稍旧的内容算出同一个
编号"，而非文本行冲突，必须重算而非重放才能保证编号不撞车。

失败语义分两类：
- **非快进（origin 已前进）**：可恢复——fetch+对齐+重算后重试，重试上限
  `max_retries` 次；重试全部因非快进耗尽后，把仓库 `reset --hard` 回远端
  最新版本（丢弃本地那个基于过期基线算出、编号可能已不准确的 commit），
  真正待补录的是**原始参数**（不是那个可能已过期的行文本），交调用方写入
  暂存文件，供人工/CC 后续按当时最新内容重新计算编号补录。
- **其他失败（网络/鉴权等）**：不可恢复重试无意义，直接放弃——但本地这个
  commit 内容仍然正确（基于当时最新基线算出），**不**丢弃，留在本地分支
  上，下次调用（下一条消息）会在其基础上继续追加+尝试推送，相当于自然的
  "延后重试"。

**队列 #126 两处修复**：
① **跨 checkout 失效**——本模块此前直接信任调用方传入的 `repo_root`，
   2026-07-28 真实命中：服务常驻 `ops/wecom-service-home` worktree、队列
   文件固定指向主工作区，两根不同致 `_relative_to_repo` 抛 subpath 错误。
   现改为调用方每次都动态解析 `queue_path` 实际所属的 repo 根（见
   `repo_paths.resolve_repo_root`），传入的 `repo_root` 只作解析失败时的
   回落值，不再被无条件信任。
② **已落盘但同步失败时的可见性**——此前失败只留 audit 事件+私信告警，
   队列文件本身看不出这一行尚未确认同步；现改为在文件里给该行追加显式
   "⏳未同步"标记（`_mark_row_unsynced`），使只看文件的读取方也能察觉。

**队列 #180 修复（2026-07-31）**：上述②的标记此前"只加不清"——`_mark_row_
unsynced` 打标记后，任何后续一次成功的 git 同步都会把**当时文件的完整
内容**（含这个陈旧标记）一并推送上去，但从未有代码去清除它；标记文案自己
写着"核实已同步后请手动删除本标记"，却没有人/机制真的去做，实测 #149/
#175 两行早已同步成功、标记仍挂着，堆积成过时假警报。**修法**：①
`append_task_and_sync_to_git` 每次即将提交（意味着文件当前完整内容即将
被推送）前，先调用 `_clear_unsynced_markers` 清掉文件里此刻残留的**全部**
标记——不局限于本次追加的这一行，因为"即将发生的这次推送"会让文件里
当下所有内容（含任何更早失败遗留的标记）一并确认同步；②标记插入位置从
"紧跟编号列之后"（挤占任务描述开头，扫读第一眼看到的是"未同步"而非
"这是什么任务"）改为行**末尾**（登记列之后、闭合竖线之前），不再顶偏
正文。
"""
from __future__ import annotations

import asyncio
import json
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger

from .queue_appender import append_pending_task
from .repo_paths import resolve_repo_root

DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = 3.0

UNSYNCED_MARKER = (
    "⏳未同步（队列 git 同步失败，本行目前只落本地磁盘/服务自身 checkout，"
    "尚未确认已推送 GitHub，见 audit `queue_sync_degraded`；下次任意一次队列同步"
    "成功推送后会自动清除本标记，无需手动删除，见队列 #180）"
)

_ROW_ID_RE = re.compile(r"^\|\s*(\d+)\s*\|")
_NON_FAST_FORWARD_MARKERS = (
    "non-fast-forward",
    "fetch first",
    "[rejected]",
    "Updates were rejected",
)


def _run_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True, encoding="utf-8"
    )


def _relative_to_repo(repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _extract_task_id(row: str) -> str:
    m = _ROW_ID_RE.match(row.strip())
    return m.group(1) if m else "?"


def _is_non_fast_forward(stderr: str) -> bool:
    return any(marker in stderr for marker in _NON_FAST_FORWARD_MARKERS)


def _commit(repo_root: Path, relative_path: str, row: str) -> str:
    """git add + commit。返回空串=成功，否则错误信息。"""
    add = _run_git(repo_root, "add", relative_path)
    if add.returncode != 0:
        return add.stderr.strip()
    commit = _run_git(
        repo_root, "commit", "-m", f"bot(队列): 自动追行 #{_extract_task_id(row)}"
    )
    if commit.returncode != 0:
        return commit.stderr.strip()
    return ""


@dataclass
class GitSyncOutcome:
    row: str
    pushed: bool
    attempts: int
    last_error: str = ""


def append_task_and_sync_to_git(
    repo_root: Path,
    queue_path: Path,
    *,
    description: str,
    owner: str,
    input_pointer: str,
    expected_output: str,
    date_str: str,
    touch_zone: str = "",
    remote: str = "origin",
    branch: str = "master",
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
    _sleep: Callable[[float], None] = time.sleep,
    already_appended_row: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    lock_factory: Optional[Callable[[], object]] = None,
) -> GitSyncOutcome:
    """本地追加（含重算）+ git 层乐观并发重试推送。同步阻塞函数——调用方
    （异步场景）请自行 `asyncio.to_thread` 包裹，参照 `group_notify.py` 惯例。

    `repo_root` 不再被直接信任——每次调用都用 `queue_path` 动态解析其真正
    所属的 repo 根（队列 #126），`repo_root` 只作解析失败时的回落值。

    `already_appended_row`：调用方（`intake.py::archive_inbound_message`）
    在本函数之外已经用 `append_pending_task` 把行落了盘（本地文件读改写，
    不含 git 操作）——首次尝试直接提交这一行，不再重新调用
    `append_pending_task` 二次追加同一内容（此前会造成同一条消息在队列里
    出现两行、编号各不相同的重复，队列 #126 修复本 checkout-mismatch 缺陷
    时一并发现并修复，此前从未被端到端集成测试覆盖过）。仅在非快进冲突需
    要重新计算编号时（attempt > 1），才改回调用 `append_pending_task` 对
    齐后的最新内容重算插入点。未传时（如既有直接单测）行为与此前完全一致。

    `lock_factory`（队列 #168）：非快进冲突触发的重算（attempt > 1）同样是
    对队列文件的本地读改写，同样可能与人类会话的编辑窗口重叠——提供时，
    每次重算调用 `append_pending_task` 前都用它构造一把新锁（不复用同一把
    跨多次尝试）。占用中会抛 `QueueLockBusy`，本函数不捕获、原样上抛给
    调用方 `sync_after_archive`（它已有通用 `except Exception` 兜底：记
    `queue_sync_degraded`+暂存+告警，这条双重竞态——git 冲突与人类锁占用
    同时发生——本就该走人工核对，不必在这里再造一套专门处理）。未传时
    （默认，既有调用方/测试）完全不涉及锁，行为与加这个参数前完全一致。
    """
    resolved_repo_root = resolve_repo_root(queue_path, fallback=repo_root, env=env)
    relative_path = _relative_to_repo(resolved_repo_root, queue_path)
    row = ""
    last_error = ""
    attempt = 0
    exhausted_conflict = False

    for attempt in range(1, max_retries + 1):
        if attempt == 1 and already_appended_row is not None:
            row = already_appended_row
        else:
            row = append_pending_task(
                queue_path,
                description=description,
                owner=owner,
                input_pointer=input_pointer,
                expected_output=expected_output,
                date_str=date_str,
                touch_zone=touch_zone,
                lock=lock_factory() if lock_factory is not None else None,
            )

        # 队列 #180：即将提交=即将把文件当前完整内容推送出去，顺带清掉此刻
        # 残留的任何陈旧"⏳未同步"标记（不局限于本次追加的这一行）。
        _clear_unsynced_markers(queue_path)

        err = _commit(resolved_repo_root, relative_path, row)
        if err:
            last_error = err
            break

        push = _run_git(resolved_repo_root, "push", remote, branch)
        if push.returncode == 0:
            return GitSyncOutcome(row=row, pushed=True, attempts=attempt)

        last_error = push.stderr.strip()
        if not _is_non_fast_forward(last_error):
            break  # 网络/鉴权类失败：本地 commit 保留，交下次调用自然重试

        if attempt == max_retries:
            exhausted_conflict = True
            break

        # origin 已前进——对齐到最新版本后重新计算插入点/编号（而非重放）。
        # reset --mixed 只移动分支指针+索引，不动工作区；随后单独 checkout
        # 这一个文件，确保不误伤工作区里其他未提交内容（设计要求）。
        _run_git(resolved_repo_root, "fetch", remote)
        _run_git(resolved_repo_root, "reset", "--mixed", f"{remote}/{branch}")
        _run_git(resolved_repo_root, "checkout", "--", relative_path)
        _sleep(backoff_seconds)

    if exhausted_conflict:
        # 重试耗尽：丢弃本地这个基于过期基线算出、编号可能已不准确的 commit，
        # 仓库恢复到与远端一致的干净状态，不挡住后续自动化写入。
        _run_git(resolved_repo_root, "fetch", remote)
        _run_git(resolved_repo_root, "reset", "--hard", f"{remote}/{branch}")

    return GitSyncOutcome(row=row, pushed=False, attempts=attempt, last_error=last_error)


def _mark_row_unsynced(queue_path: Path, task_id: str) -> bool:
    """在队列文件里为 `task_id` 对应的行追加"⏳未同步"标记，使只看文件的
    读取方也能察觉该行尚未确认同步（队列 #126 缺陷①的可见性补强——此前只
    有 audit 事件+私信告警，文件本身看不出异常，当日两轮撞号正是因为看
    不见这些行才发生）。行已不在文件里时（如重试耗尽后 `reset --hard` 丢
    弃）返回 False——那种情形改靠 `pending_path` 暂存文件兜底，不是本函数
    职责。

    插入位置＝行**末尾**、闭合竖线之前（队列 #180，2026-07-31 改）——此前
    插在编号列之后会把任务描述整体挤后，扫读第一眼看到的是"未同步"而不是
    "这是什么任务"；非标准表格行（不以 `|` 收尾）不强行处理，宁可不标记
    也不写坏格式，返回 False。
    """
    if not task_id or task_id == "?":
        return False
    text = queue_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = _ROW_ID_RE.match(line)
        if m and m.group(1) == task_id and UNSYNCED_MARKER not in line:
            stripped = line.rstrip()
            if not stripped.endswith("|"):
                return False
            last_pipe = len(stripped) - 1
            lines[i] = f"{stripped[:last_pipe]}{UNSYNCED_MARKER} |{line[len(stripped):]}"
            newline = "\n" if text.endswith("\n") else ""
            queue_path.write_text("\n".join(lines) + newline, encoding="utf-8")
            return True
    return False


def _clear_unsynced_markers(queue_path: Path) -> int:
    """清除队列文件里所有 `_mark_row_unsynced` 曾打上的"⏳未同步"标记
    （队列 #180，2026-07-31）。

    标记语义是"本行尚未确认已推送"——凡走到这里（即将进行一次真实的
    git commit+push）都意味着文件当前的完整内容即将被推送，任何仍残留
    在文件里的旧标记（可能来自更早、与本次追加无关的某次失败）此刻也
    会随之推送成功，理应一并清除，否则标记只增不减、永久堆积成过时的
    假警报（实证：#149/#175 两行早已同步成功，标记却仍挂着）。

    只做全文字符串替换（标记文本本身足够独特，不需要逐行按 #id 匹配）；
    兼容当前"行末尾、前置一个空格"与历史遗留的"编号列后、后置一个空格"
    两种插入形态，统一按"标记+相邻一个空格"整体清除，不残留多余空白。
    文件不存在或无标记时返回 0，安全空转。
    """
    if not queue_path.exists():
        return 0
    text = queue_path.read_text(encoding="utf-8")
    count = text.count(UNSYNCED_MARKER)
    if count == 0:
        return 0
    text = text.replace(UNSYNCED_MARKER + " ", "")
    text = text.replace(" " + UNSYNCED_MARKER, "")
    text = text.replace(UNSYNCED_MARKER, "")
    queue_path.write_text(text, encoding="utf-8")
    return count


def _mark_row_unsynced_safely(queue_path: Path, row: Optional[str]) -> None:
    if not row:
        return
    try:
        _mark_row_unsynced(queue_path, _extract_task_id(row))
    except Exception:  # noqa: BLE001 —— 标记失败不应影响告警/降级路径本身
        pass


def _append_pending_record(pending_path: Path, append_kwargs: dict, error: str) -> None:
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "error": error,
        **append_kwargs,
    }
    with pending_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


async def _send_degraded_alert(
    connector,
    audit: AuditLogger,
    alert_text: str,
    recipient: str,
    *,
    fallback_send: Optional[Callable[[str], None]] = None,
    evaluator: str = "system",
) -> None:
    """队列同步降级告警——形状仿 `gap_alert.send_gap_alert`（主通道失败时走
    独立 webhook 兜底），但用本模块自己的审计 action 名，不与 gap_alert 的
    审计事件混淆。"""
    try:
        await connector.send_markdown(recipient, f"⚠️ {alert_text}")
    except Exception:  # noqa: BLE001 —— 告警失败不应影响服务继续运行
        audit.record(AuditEvent(
            scenario="wecom-aibot", action="queue_sync_alert_failed", evaluator=evaluator,
            automation_level="L1", decision={"sent": False}, data_sources={},
        ))
        if fallback_send is None:
            return
        try:
            await asyncio.to_thread(fallback_send, alert_text)
        except Exception:  # noqa: BLE001
            audit.record(AuditEvent(
                scenario="wecom-aibot", action="queue_sync_alert_fallback_failed",
                evaluator=evaluator, automation_level="L1",
                decision={"sent": False}, data_sources={},
            ))
        else:
            audit.record(AuditEvent(
                scenario="wecom-aibot", action="queue_sync_alert_fallback_sent",
                evaluator=evaluator, automation_level="L1",
                decision={"sent": True, "channel": "webhook"}, data_sources={},
            ))
        return
    audit.record(AuditEvent(
        scenario="wecom-aibot", action="queue_sync_alert_sent", evaluator=evaluator,
        automation_level="L1", decision={"sent": True, "recipient": recipient}, data_sources={},
    ))


async def sync_after_archive(
    *,
    repo_root: Path,
    queue_path: Path,
    append_kwargs: dict,
    audit: AuditLogger,
    connector=None,
    recipient: str = "",
    fallback_send: Optional[Callable[[str], None]] = None,
    pending_path: Optional[Path] = None,
    evaluator: str = "system",
    remote: str = "origin",
    branch: str = "master",
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
    already_appended_row: Optional[str] = None,
    lock_factory: Optional[Callable[[], object]] = None,
) -> GitSyncOutcome:
    """`archive_inbound_message` 本地追加成功后的独立后续步骤（不阻塞归档
    主流程——本函数本身不向上抛出任何异常，失败只降级+告警）。

    `already_appended_row`：调用方（`intake.py`）已经落盘的那一行原文，
    见 `append_task_and_sync_to_git` 同名参数文档——避免同一条消息被重复
    追加两次。

    `lock_factory`：见 `append_task_and_sync_to_git` 同名参数文档（队列
    #168）——非快进冲突重算时用于保护本地写入不被人类编辑窗口覆盖。"""
    try:
        outcome = await asyncio.to_thread(
            append_task_and_sync_to_git,
            repo_root,
            queue_path,
            remote=remote,
            branch=branch,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
            already_appended_row=already_appended_row,
            lock_factory=lock_factory,
            **append_kwargs,
        )
    except Exception as exc:  # noqa: BLE001 —— git 子进程意外异常也不得向上抛
        audit.record(AuditEvent(
            scenario="wecom-aibot", action="queue_sync_degraded", evaluator=evaluator,
            automation_level="L1", decision={"attempts": 0}, data_sources={}, error=str(exc),
        ))
        if pending_path is not None:
            _append_pending_record(pending_path, append_kwargs, str(exc))
        _mark_row_unsynced_safely(queue_path, already_appended_row)
        if connector is not None and recipient:
            await _send_degraded_alert(
                connector, audit, f"队列同步异常：{exc}", recipient,
                fallback_send=fallback_send, evaluator=evaluator,
            )
        return GitSyncOutcome(row=already_appended_row or "", pushed=False, attempts=0, last_error=str(exc))

    if outcome.pushed:
        audit.record(AuditEvent(
            scenario="wecom-aibot", action="queue_sync_pushed", evaluator=evaluator,
            automation_level="L1", decision={"attempts": outcome.attempts}, data_sources={},
        ))
        return outcome

    audit.record(AuditEvent(
        scenario="wecom-aibot", action="queue_sync_degraded", evaluator=evaluator,
        automation_level="L1", decision={"attempts": outcome.attempts}, data_sources={},
        error=outcome.last_error,
    ))
    if pending_path is not None:
        _append_pending_record(pending_path, append_kwargs, outcome.last_error)
    _mark_row_unsynced_safely(queue_path, outcome.row or already_appended_row)
    if connector is not None and recipient:
        desc = append_kwargs.get("description", "")
        alert_text = f"队列同步失败 {outcome.attempts} 次，一行待人工核对合并：{desc}"
        await _send_degraded_alert(
            connector, audit, alert_text, recipient,
            fallback_send=fallback_send, evaluator=evaluator,
        )
    return outcome
