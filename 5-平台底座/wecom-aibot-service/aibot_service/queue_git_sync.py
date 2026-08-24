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

**队列 #287 修复（2026-08-06，openspec `aibot-queue-sync-checkout-guard`，
Shao Peishen 批准候选 A）**：上方"reset --mixed 只移动分支指针+索引，不动
工作区；随后单独 checkout 这一个文件，确保不误伤工作区里其他未提交内容"
这句"设计要求"此前从未被真正校验过——`_commit` 的 `git add` 会把磁盘上
当次的**全部**内容（含协议〇.7/〇.8 允许存在的"人类会话已 release 编辑锁
但尚未 commit"这一合法状态，可持续数分钟到数小时）一并暂存进本地 commit，
一旦推送因非快进被拒（日常高频场景），后续 `reset`/`checkout` 会把这个
混合了人类成果的本地 commit 连根拔起——人类的内容既不在工作区、也不在
任何可达的 git 历史里。真实事故与代码路径复现见队列 #287。**修法**：新增
`_diff_exceeds_expected`，在执行 `reset`/`checkout` 前校验刚提交的这个
本地 commit 相对其父提交的实际改动是否超出"仅本次追加"的预期规模（插入
≤2 行、删除 ≤1 行，只用行数量级判断，不解析表格语义）；超出即判定磁盘上
混入了外来内容，**放弃销毁性 reset/checkout**，改为 `reset --soft
HEAD~1` 撤销本地 commit（不动工作区），人类内容与机器人本次算出的行都
原样保留在工作区、交人工/sweep 后续处理；`GitSyncOutcome` 新增
`foreign_content_detected` 字段，`sync_after_archive` 据此使用与网络/
冲突类失败明确区分的 audit reason 与告警文案（不得让人误判为可通过
重试解决）。护栏未命中时（磁盘只有本次追加自身差异）行为与护栏引入前
完全一致。
"""
from __future__ import annotations

import asyncio
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger
from zhuopin_platform.shared_tools.queue_table import iter_queue_paths

from . import pending_jsonl
from .queue_appender import append_pending_task
from .queue_edit_lock import QueueLockBusy
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


def _diff_exceeds_expected(
    repo_root: Path, relative_path: str, *, max_insertions: int = 2, max_deletions: int = 1,
) -> bool:
    """队列 #287 护栏（openspec `aibot-queue-sync-checkout-guard` 决策点1/3，
    Shao Peishen 2026-08-06 批准候选 A）：刚完成的本地 commit（`HEAD`，相对
    `HEAD~1`）对 `relative_path` 的实际改动是否超出"本次追加预期产生的差异"
    （新增一行任务 ＋ 至多一行高水位线自增，即插入 ≤2 行、删除 ≤1 行）。

    超出即判定磁盘上原本存在与本次追加无关的外来未提交内容（该内容已被
    `git add` 一并暂存进这个 commit 里，见 `_commit`）——协议〇.7/〇.8 允许
    "人类已 release 编辑锁但内容尚未提交"这一合法状态持续数分钟到数小时，
    此时若恰好撞上非快进冲突，后续的 `reset`/`checkout` 会把这份混合内容
    连根拔起（队列 #287 真实事故，已用 `test_conflict_recompute_destroys_
    uninvolved_uncommitted_edits` 复现坐实）。

    只用行数量级判断，不解析队列表格语义——见 design.md 决策点3：语义
    解析引入的新失败面（表格格式漂移）比行数判断更大，量级判断对"本次
    只是自己的一行 vs 混入了一整个编辑锁窗口的改动"这一区分已经足够。

    无法判断时（如首次提交没有 `HEAD~1`、diff 输出为空）保守放行——返回
    `False`，沿用护栏加入前的既有行为，不引入新的失败面。"""
    result = _run_git(repo_root, "diff", "--numstat", "HEAD~1", "HEAD", "--", relative_path)
    if result.returncode != 0 or not result.stdout.strip():
        return False
    line = result.stdout.strip().splitlines()[0]
    parts = line.split("\t")
    if len(parts) < 2:
        return False
    try:
        insertions = int(parts[0])
        deletions = int(parts[1])
    except ValueError:
        return False
    return insertions > max_insertions or deletions > max_deletions


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
    # 队列 #286：失败时实际写入了哪个暂存文件（`pending_queue_appends.jsonl`
    # 或锁忙专用暂存文件），None 表示未写入任何文件（未提供暂存路径，或
    # 推送成功无需暂存）。供 `flush_pending_git_sync_appends` 判断一条记录
    # 是否已在补录过程中"迁移"到另一个暂存文件，避免同时留在两处。
    pending_recorded_at: Optional[Path] = None
    # 队列 #287：`_diff_exceeds_expected` 护栏是否拦截了一次销毁性重算——
    # True 时磁盘上的外来内容已被保留（未执行 reset/checkout），供
    # `sync_after_archive` 选用差异化的 audit reason/告警文案，不与网络/
    # 冲突类失败共用同一套"可通过重试解决"的措辞。
    foreign_content_detected: bool = False


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
    guard_triggered = False

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

        # 队列 #287 护栏（openspec aibot-queue-sync-checkout-guard，Shao
        # Peishen 2026-08-06 批准候选 A）：在执行会覆盖工作区文件内容的
        # reset/checkout 之前，先校验刚提交的这个本地 commit 对该文件的
        # 实际改动是否超出"本次追加"应有的规模——超出即说明磁盘上原本
        # 存在与本次追加无关的外来未提交内容（如协议〇.7/〇.8 允许的
        # "人类已 release 编辑锁但内容尚未提交"合法状态），此时绝不能继续
        # 执行销毁性 reset/checkout（队列 #287 真实事故的根因）。
        if _diff_exceeds_expected(resolved_repo_root, relative_path):
            guard_triggered = True
            last_error = (
                "护栏拦截（foreign_dirty_content_detected）：磁盘上存在与本次"
                f"追加无关的外来未提交内容，已放弃销毁性 reset/checkout；"
                f"原始推送错误：{last_error}"
            )
            break

        # origin 已前进——对齐到最新版本后重新计算插入点/编号（而非重放）。
        # reset --mixed 只移动分支指针+索引，不动工作区；随后单独 checkout
        # 这一个文件，确保不误伤工作区里其他未提交内容（设计要求；上方
        # 护栏是这条"设计要求"此前从未被真正校验过的补强）。
        _run_git(resolved_repo_root, "fetch", remote)
        _run_git(resolved_repo_root, "reset", "--mixed", f"{remote}/{branch}")
        _run_git(resolved_repo_root, "checkout", "--", relative_path)
        _sleep(backoff_seconds)

    if guard_triggered:
        # 护栏命中：不执行任何销毁性操作。撤销本地这个（可能混入外来内容
        # 的）commit（--soft，不动工作区），工作区随之恢复为"外来内容 ＋
        # 本次追加已插入的这一行"混合的未提交状态——与进入本函数之前相比
        # 只多了这一行（这一行本就该留在磁盘上，交人工/sweep 后续处理）。
        _run_git(resolved_repo_root, "reset", "--soft", "HEAD~1")
    elif exhausted_conflict:
        # 重试耗尽：丢弃本地这个基于过期基线算出、编号可能已不准确的 commit，
        # 仓库恢复到与远端一致的干净状态，不挡住后续自动化写入。
        _run_git(resolved_repo_root, "fetch", remote)
        _run_git(resolved_repo_root, "reset", "--hard", f"{remote}/{branch}")

    return GitSyncOutcome(
        row=row, pushed=False, attempts=attempt, last_error=last_error,
        foreign_content_detected=guard_triggered,
    )


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
    record = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "error": error,
        **append_kwargs,
    }
    pending_jsonl.append_record(pending_path, record)


def _extract_append_kwargs_from_flat_record(record: dict) -> dict:
    """`_append_pending_record` 把 `recorded_at`/`error` 与 append_kwargs
    摊平写在同一层（历史 schema，`pending_queue_appends.jsonl` 专用，见该
    函数与既有测试对其形状的既有断言）——补录时反向剥离出纯 append_kwargs。"""
    return {k: v for k, v in record.items() if k not in ("recorded_at", "error")}


def input_pointer_already_in_queue(
    repo_root: Path, queue_path: Path, input_pointer: str
) -> bool:
    """队列 #387 ⑹：这条待补录记录对应的队列行，是不是**已经存在**了？

    **为什么需要这道判据**：`queue_sync_degraded` 的根因通常是 `.git/index.lock`
    被并发 git 进程占着（本机是常态——sweep/巡检/CC 会话随时在跑 git），而
    **加锁失败发生在「行已写进磁盘文件」之后**。于是同一条来件会同时以两种
    形态存在：磁盘队列里的一行 ＋ `pending_queue_appends.jsonl` 里的一条待
    补录记录。这条 pending 若被 flush，就会**再追加一条同内容、不同编号的
    行**。2026-08-24 15:30:53 真实发生过一次（对应行即 §一 `#389`），当时靠
    人工 `grep` 发现并处置——本函数把那次人工核对固化成机器判据。

    **判据 ＝ `input_pointer` 在任一份队列文件里出现过**。`input_pointer` 是
    归档文件的仓库相对路径（含 msgid 消歧后缀，见 `intake._build_filename`），
    **在本项目里对每一条来件唯一**，比按描述文本或编号匹配都稳。

    🔴 **扫全部物理队列文件、不只扫 `queue_path`**（`iter_queue_paths()`，与
    `open_pool_reminder.build_pool_items_from_repo` 同一入口）：`#315` 拆分成
    两份之后，一条行可能被人工挪进另一份；只扫写入侧那一份，会把"已挪走的
    行"误判为不存在，于是补出第二条——**这正是「一份拆成两份、下游只跟了
    一份」那个家族的又一个入口**。

    读取失败/文件不存在时按「没找到」处理并继续扫其余文件——**这一侧的
    fail-open 是刻意的**：本函数只是一道去重网，读不到文件就退回改动前的
    行为（照常补录），不能因为一个读不到的文件把整条补录链路卡死。
    """
    if not input_pointer:
        return False
    needle = input_pointer.strip().strip("`")
    if not needle:
        return False

    candidates: list[Path] = []
    for queue_rel in iter_queue_paths():
        candidates.append(repo_root / queue_rel)
    if queue_path not in candidates:
        candidates.append(queue_path)

    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if needle in text:
            return True
    return False


def _route_pending_failure(
    *,
    is_lock_busy: bool,
    append_kwargs: dict,
    error: str,
    pending_path: Optional[Path],
    lock_pending_path: Optional[Path],
) -> Optional[Path]:
    """队列 #286 根因：锁忙与真实 git 失败此前混用同一个暂存文件/同一套
    "不知道该找谁补录"的处境——锁忙应当被 `queue_lock_pending.flush_
    pending_queue_appends` 的既有补录逻辑重试（它深知"锁忙就该等下一条
    消息到达再试"，且已在生产环境验证过），真实 git 失败（网络/非快进
    重试耗尽）此前根本没有 flush 通道（见本模块新增的 `flush_pending_git_
    sync_appends`）。混在一起会导致"同一种失败从两个不同层抛出，只有一层
    的暂存会被补录"（队列 #286 原文）。

    `is_lock_busy=True` 且提供了 `lock_pending_path` 时，写入锁忙暂存文件
    （与 `queue_lock_pending.record_deferred_append` 同一 schema，供其既有
    flush 逻辑直接消费，不需要它感知"这条记录其实是从 git 同步层转过来
    的"）；否则（含锁忙但未提供 `lock_pending_path` 的旧调用方场景，向后
    兼容）落回 `pending_path`（`_append_pending_record` 既有扁平 schema）。
    两者都未提供时返回 `None`，不写入任何文件（未提供暂存路径的调用方，
    如既有部分单测——不引入新的失败模式）。"""
    if is_lock_busy and lock_pending_path is not None:
        pending_jsonl.append_record(lock_pending_path, {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "sender": "",
            "append_kwargs": append_kwargs,
        })
        return lock_pending_path
    if pending_path is not None:
        _append_pending_record(pending_path, append_kwargs, error)
        return pending_path
    return None


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


def _location_hint(pending_recorded_at: Optional[Path], append_kwargs: dict) -> str:
    """队列 #286：告警文案带上暂存文件路径与该条 `input_pointer`，使人工
    承接有明确落点——此前文案只说"一行待人工核对合并"，没人知道该去哪个
    文件捞哪一行。"""
    pointer = append_kwargs.get("input_pointer", "")
    parts = []
    if pending_recorded_at is not None:
        parts.append(f"已暂存于 {pending_recorded_at}")
    if pointer:
        parts.append(f"指针 {pointer}")
    return f"（{'，'.join(parts)}）" if parts else ""


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
    lock_pending_path: Optional[Path] = None,
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
    #168）——非快进冲突重算时用于保护本地写入不被人类编辑窗口覆盖。

    `lock_pending_path`（队列 #286）：失败原因是 `QueueLockBusy`（冲突重算
    时人类恰好持锁）时，记录改落这个文件而非 `pending_path`——与
    `queue_lock_pending.record_deferred_append` 同一 schema，供其既有
    `flush_pending_queue_appends` 直接补录，不需要新造一套"锁忙从 git 层
    抛出"的处理逻辑。未提供时（向后兼容旧调用方）回落 `pending_path`。"""
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
        written_to = _route_pending_failure(
            is_lock_busy=isinstance(exc, QueueLockBusy),
            append_kwargs=append_kwargs, error=str(exc),
            pending_path=pending_path, lock_pending_path=lock_pending_path,
        )
        _mark_row_unsynced_safely(queue_path, already_appended_row)
        if connector is not None and recipient:
            await _send_degraded_alert(
                connector, audit,
                f"队列同步异常：{exc}{_location_hint(written_to, append_kwargs)}", recipient,
                fallback_send=fallback_send, evaluator=evaluator,
            )
        return GitSyncOutcome(
            row=already_appended_row or "", pushed=False, attempts=0, last_error=str(exc),
            pending_recorded_at=written_to,
        )

    if outcome.pushed:
        audit.record(AuditEvent(
            scenario="wecom-aibot", action="queue_sync_pushed", evaluator=evaluator,
            automation_level="L1", decision={"attempts": outcome.attempts}, data_sources={},
        ))
        return outcome

    audit.record(AuditEvent(
        scenario="wecom-aibot", action="queue_sync_degraded", evaluator=evaluator,
        automation_level="L1",
        decision={
            "attempts": outcome.attempts,
            "reason": "foreign_dirty_content_detected" if outcome.foreign_content_detected else "",
        },
        data_sources={}, error=outcome.last_error,
    ))
    # 非快进重试耗尽/网络类失败/护栏拦截均由 append_task_and_sync_to_git
    # 内部处理，从不以 QueueLockBusy 形式反映在 outcome.last_error 里——
    # 恒定路由到 pending_path（真实 git 失败暂存文件，队列 #287 护栏命中
    # 也复用这一个通道，见 design.md 决策点2：不新增第三个暂存文件），
    # 不涉及锁忙分流。
    written_to = _route_pending_failure(
        is_lock_busy=False, append_kwargs=append_kwargs, error=outcome.last_error,
        pending_path=pending_path, lock_pending_path=lock_pending_path,
    )
    outcome.pending_recorded_at = written_to
    _mark_row_unsynced_safely(queue_path, outcome.row or already_appended_row)
    if connector is not None and recipient:
        desc = append_kwargs.get("description", "")
        if outcome.foreign_content_detected:
            # 队列 #287：文案须与"网络/冲突类失败"明确区分——那类失败
            # 靠重试就可能自愈，本情形重试无意义（磁盘上的外来内容不会
            # 因为再试一次而消失），必须显式说明"已跳过、未做任何覆盖"，
            # 避免人工误判成可以再等一等的暂时性故障。
            alert_text = (
                f"队列同步护栏拦截：磁盘上存在其它未提交内容（并非本次追加），"
                f"已跳过自动同步、未执行任何覆盖性操作，需人工核实后处理："
                f"{desc}{_location_hint(written_to, append_kwargs)}"
            )
        else:
            alert_text = (
                f"队列同步失败 {outcome.attempts} 次，一行待人工核对合并："
                f"{desc}{_location_hint(written_to, append_kwargs)}"
            )
        await _send_degraded_alert(
            connector, audit, alert_text, recipient,
            fallback_send=fallback_send, evaluator=evaluator,
        )
    return outcome


async def flush_pending_git_sync_appends(
    *,
    pending_path: Path,
    repo_root: Path,
    queue_path: Path,
    audit: AuditLogger,
    connector=None,
    recipient: str = "",
    fallback_send: Optional[Callable[[str], None]] = None,
    evaluator: str = "system",
    remote: str = "origin",
    branch: str = "master",
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
    lock_factory: Optional[Callable[[], object]] = None,
    lock_pending_path: Optional[Path] = None,
) -> int:
    """队列 #286：补录此前因非快进重试耗尽/网络等真实 git 失败被暂存进
    `pending_queue_appends.jsonl` 的记录——该文件此前没有任何自动 flush
    通道（`queue_lock_pending.flush_pending_queue_appends` 只认另一个
    schema 不同的锁忙专用暂存文件），记录只会永久躺在磁盘上直到人工翻
    日志才会发现，是队列 #286 三条真实丢失行的直接成因。

    与锁忙补录的一处关键差异：这里**不**假设原始那一行仍在磁盘上——记录
    被写入这个文件时，磁盘上的队列文件几乎总已经被 `append_task_and_
    sync_to_git` 的冲突重算或重试耗尽清空过（`reset --mixed`/`reset
    --hard`），原始那次算出的行号/位置可能已经过期，必须让
    `sync_after_archive` 内部重新调用 `append_pending_task` 对最新内容
    重算（`already_appended_row` 留空），而不是重放一个可能已经撞号的
    旧结果。

    也不像锁忙补录那样"一条失败就整体停止"——那是因为锁被同一个人类
    会话占用大概率会持续一段时间，continue 尝试后面的记录没有意义；这里
    的失败通常是相互独立的网络抖动/编号冲突，continue 反而更可能多挽回
    几条。若某条重试后又变成锁忙（`outcome.pending_recorded_at ==
    lock_pending_path`），它已经被 `sync_after_archive` 转移到锁忙暂存
    文件、交由那条既有链路补录，本函数不重复保留它，避免同一条记录同时
    躺在两个文件里。

    返回本次成功补录（真正推送成功）的行数。"""
    records = pending_jsonl.read_records(pending_path)
    if not records:
        return 0

    flushed = 0
    remaining: list[dict] = []
    for record in records:
        append_kwargs = _extract_append_kwargs_from_flat_record(record)

        # 队列 #387 ⑹：补录前先问一句「这一行是不是已经在了」。`queue_sync_
        # degraded` 的常见根因（`.git/index.lock` 被并发 git 进程占着）发生在
        # 行已落盘之后 ⇒ 磁盘上有行、pending 里也有记录，直接补录会产生第二
        # 条同内容行。丢弃该记录并留痕，不再往下走。
        if input_pointer_already_in_queue(
            repo_root, queue_path, str(append_kwargs.get("input_pointer", ""))
        ):
            audit.record(AuditEvent(
                scenario="wecom-aibot", action="queue_sync_pending_skipped_duplicate",
                evaluator=evaluator, automation_level="L1",
                decision={"recorded_at": record.get("recorded_at", ""), "reason": "row_already_present"},
                data_sources={"input_pointer": append_kwargs.get("input_pointer", "")},
            ))
            continue

        outcome = await sync_after_archive(
            repo_root=repo_root,
            queue_path=queue_path,
            append_kwargs=append_kwargs,
            audit=audit,
            connector=connector,
            recipient=recipient,
            fallback_send=fallback_send,
            pending_path=None,
            lock_pending_path=lock_pending_path,
            evaluator=evaluator,
            remote=remote,
            branch=branch,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
            lock_factory=lock_factory,
        )
        if outcome.pushed:
            flushed += 1
            audit.record(AuditEvent(
                scenario="wecom-aibot", action="queue_sync_pending_flushed", evaluator=evaluator,
                automation_level="L1",
                decision={"recorded_at": record.get("recorded_at", "")},
                data_sources={"input_pointer": append_kwargs.get("input_pointer", "")},
            ))
        elif outcome.pending_recorded_at != lock_pending_path or lock_pending_path is None:
            remaining.append(record)
        # else：已被转移进锁忙暂存文件，不在本文件里重复保留。

    pending_jsonl.rewrite_records(pending_path, remaining)
    return flushed
