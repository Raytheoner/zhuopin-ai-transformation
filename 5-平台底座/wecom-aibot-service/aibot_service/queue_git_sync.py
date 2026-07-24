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
from typing import Callable, Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger

from .queue_appender import append_pending_task

DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = 3.0

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
) -> GitSyncOutcome:
    """本地追加（含重算）+ git 层乐观并发重试推送。同步阻塞函数——调用方
    （异步场景）请自行 `asyncio.to_thread` 包裹，参照 `group_notify.py` 惯例。
    """
    relative_path = _relative_to_repo(repo_root, queue_path)
    row = ""
    last_error = ""
    attempt = 0
    exhausted_conflict = False

    for attempt in range(1, max_retries + 1):
        row = append_pending_task(
            queue_path,
            description=description,
            owner=owner,
            input_pointer=input_pointer,
            expected_output=expected_output,
            date_str=date_str,
            touch_zone=touch_zone,
        )

        err = _commit(repo_root, relative_path, row)
        if err:
            last_error = err
            break

        push = _run_git(repo_root, "push", remote, branch)
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
        _run_git(repo_root, "fetch", remote)
        _run_git(repo_root, "reset", "--mixed", f"{remote}/{branch}")
        _run_git(repo_root, "checkout", "--", relative_path)
        _sleep(backoff_seconds)

    if exhausted_conflict:
        # 重试耗尽：丢弃本地这个基于过期基线算出、编号可能已不准确的 commit，
        # 仓库恢复到与远端一致的干净状态，不挡住后续自动化写入。
        _run_git(repo_root, "fetch", remote)
        _run_git(repo_root, "reset", "--hard", f"{remote}/{branch}")

    return GitSyncOutcome(row=row, pushed=False, attempts=attempt, last_error=last_error)


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
) -> GitSyncOutcome:
    """`archive_inbound_message` 本地追加成功后的独立后续步骤（不阻塞归档
    主流程——本函数本身不向上抛出任何异常，失败只降级+告警）。"""
    try:
        outcome = await asyncio.to_thread(
            append_task_and_sync_to_git,
            repo_root,
            queue_path,
            remote=remote,
            branch=branch,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
            **append_kwargs,
        )
    except Exception as exc:  # noqa: BLE001 —— git 子进程意外异常也不得向上抛
        audit.record(AuditEvent(
            scenario="wecom-aibot", action="queue_sync_degraded", evaluator=evaluator,
            automation_level="L1", decision={"attempts": 0}, data_sources={}, error=str(exc),
        ))
        if pending_path is not None:
            _append_pending_record(pending_path, append_kwargs, str(exc))
        if connector is not None and recipient:
            await _send_degraded_alert(
                connector, audit, f"队列同步异常：{exc}", recipient,
                fallback_send=fallback_send, evaluator=evaluator,
            )
        return GitSyncOutcome(row="", pushed=False, attempts=0, last_error=str(exc))

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
    if connector is not None and recipient:
        desc = append_kwargs.get("description", "")
        alert_text = f"队列同步失败 {outcome.attempts} 次，一行待人工核对合并：{desc}"
        await _send_degraded_alert(
            connector, audit, alert_text, recipient,
            fallback_send=fallback_send, evaluator=evaluator,
        )
    return outcome
