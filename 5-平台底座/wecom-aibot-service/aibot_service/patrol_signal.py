"""队列 #382⑴：拆件巡逻「桥一打标即开班」的信号文件读写。

## 它补的是哪一格

拆件巡逻此前靠工作日固定双班扫队列——回件到手到有人拆件之间天然隔着
半个班次。派单件要求把开班方式从「定时」改成「桥一（`followup_readme_
bridge.mark_reply_arrived`）打标即开班」，但拆件巡逻本身是跑在
`C:\\Users\\Paul Shao\\Claude\\Scheduled\\huijian-chaijian-patrol\\SKILL.md`
的 Claude 侧 scheduled task——**这份 prompt 在仓库外，本仓库任何代码都
无法从内部直接触达或触发它**（同 `draft_gap_check.py` 文首「分工边界」
已记录的同一条边界；`mcp__scheduled-tasks__list_scheduled_tasks` 从本
worktree 能看到的只是另一个互不相干的任务库）。故本模块不做「触发」，
只做「留一个证据」：桥一打标成功的同一把编辑锁内，把这次到达写进一个
小文件；巡逻侧改高频轻量探测（`scripts/check_patrol_signal.py`）读它，
比每次都扫 2 MB 队列真身便宜到近乎零成本。真正把探测脚本接进 SKILL.md
与调高频率，需 Cowork 在其自己能触达该 store 的会话里用
`update_scheduled_task` 完成——见 `check_patrol_signal.py` 文首说明。

## 三条设计取舍

1. **fail-open，不 fail-closed**（读侧）：信号文件读不懂（损坏/格式错）
   时按「有信号」处理，绝不因为状态文件自己坏了就让一条真实回件被静默
   吞掉——同根 CLAUDE.md OP-0819-F「探针通了 ≠ 机制通了」一族，这里是
   反面：**机制原本是通的，不能因为一个新加的旁路信号坏了而被拖着一起
   哑掉**。
2. **累积列表，不覆盖单值**：一个班次运行期间可能有新回件到达；清空时
   只挪走「本次开班已知悉」的那些（按 `--before` 时间戳），期间新落的
   条目原样保留到下一次探测——同 `outbox_relay.py` 的乐观并发校验思路，
   避免「扫描期间又来一条，收工时被整份清空」的丢失窗口。
3. **本模块任何异常绝不上抛**：调用方 `mark_reply_arrived` 自身有「绝不
   向上抛」的既有契约，写信号失败只应记一行日志，不得反过来让一次已经
   成功的 README 标记被上层误判为失败。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from .repo_paths import resolve_patrol_signal_path

PENDING_KEY = "pending"


def _utc_stamp(now: Optional[datetime] = None) -> str:
    """UTC 且显式带 `Z`——与 `followup_readme_bridge._utc_stamp` 同口径
    （根 CLAUDE.md §5 硬规则：引用任何时刻前先答一句「这是 UTC 还是本地」）。
    """
    moment = now or datetime.now(tz=timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class SignalSnapshot:
    present: bool
    pending: list = field(default_factory=list)
    corrupted: bool = False


def raise_signal(
    repo_root: Path,
    *,
    letter_number: Optional[str],
    archived_filename: str,
    now: Optional[datetime] = None,
    log: Callable[[str], None] = print,
) -> None:
    """记一条「有回件到达」的信号。绝不向上抛——见文首取舍 3。"""
    path = resolve_patrol_signal_path(repo_root)
    entry = {
        "letter_number": letter_number or "",
        "archived_filename": archived_filename,
        "at": _utc_stamp(now),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        pending = []
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                pending = list(data.get(PENDING_KEY, []))
            except (json.JSONDecodeError, OSError):
                # 已损坏读不回——不阻塞新信号，从这一条重新起数。旧内容
                # 丢的只是「更早那几条的明细」，不是「有活」这个事实本身
                # （新条目仍会被写入）。
                pending = []
        pending.append(entry)
        path.write_text(
            json.dumps({PENDING_KEY: pending}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        try:
            log(f"⚠ [巡逻信号] 写入失败，本次回件到达不会提前触发开班（{path}）：{exc}")
        except Exception:  # noqa: BLE001 —— 日志本身失败不得反过来抛出
            pass


def read_signal(repo_root: Path) -> SignalSnapshot:
    """只读。文件不存在＝无信号；存在但读不懂＝ fail-open 按有信号处理。"""
    path = resolve_patrol_signal_path(repo_root)
    if not path.exists():
        return SignalSnapshot(present=False, pending=[])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        pending = list(data.get(PENDING_KEY, []))
        return SignalSnapshot(present=bool(pending), pending=pending)
    except (json.JSONDecodeError, OSError):
        return SignalSnapshot(present=True, pending=[], corrupted=True)


def clear_signal(repo_root: Path, *, before: Optional[str] = None) -> int:
    """消费信号。

    `before`＝本次开班已知悉的截止时间戳（`read_signal` 报的「最新」那条
    的 `at`）：只移除 `at <= before` 的条目，期间新落的原样保留——见文首
    取舍 2。不传 `before` 时整份清空（供手工重置/测试用）。

    返回值＝实际移除的条目数；文件本不存在时返回 0；文件损坏时无法做
    「哪些该留」的判断，直接整份清空并返回 0（读不懂就不敢做减法，留一份
    读不懂的文件没有意义）。
    """
    path = resolve_patrol_signal_path(repo_root)
    if not path.exists():
        return 0
    if before is None:
        removed = 0
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            removed = len(data.get(PENDING_KEY, []))
        except (json.JSONDecodeError, OSError):
            pass
        path.unlink()
        return removed
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        current = list(data.get(PENDING_KEY, []))
    except (json.JSONDecodeError, OSError):
        path.unlink()
        return 0
    remaining = [item for item in current if str(item.get("at", "")) > before]
    removed = len(current) - len(remaining)
    if remaining:
        path.write_text(
            json.dumps({PENDING_KEY: remaining}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        path.unlink()
    return removed
