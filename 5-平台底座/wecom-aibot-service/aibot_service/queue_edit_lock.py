"""队列文件写入前占用协议〇.7 共享编辑锁的生产实现（队列 #168）。

复用既有 CLI 工具 `0-学习与工具/工具-共享文档编辑锁.py`（当作外部子进程
调用，与 `queue_git_sync.py` 对 `git` 子进程的复用同构）——不在这里重新
实现锁协议本身，避免协议分叉成两份互不知情的实现（人类会话与机器人各
认一套"什么算占用""陈旧锁多久可接管"，只会制造新的绕锁缺陷）。

队列 #333③（2026-08-12）：`release()` 检查 `returncode` 非 0 时（锁工具
的 release 结构校验拒绝，见 `工具-共享文档编辑锁.py::_validate_release_
structure`）此前只在锁保持占用这一间接后果里体现，没有任何审计留痕/
告警——逼着人靠"锁为什么迟迟不放"倒推原因（#333 真实事故：拒绝原因是
③预留归属校验，机器人从未检查 `returncode`，锁卡满 30 分钟才被陈旧接管，
全程无人知道发生了什么）。新增 `_record_release_rejected`：非 0 时若
提供 `audit` 则记一条 `queue_edit_lock_release_rejected` 审计事件，若
提供 `alert_send` 则发一条告警——`release()` 本身的"释放失败不向上抛出"
契约不变（见下方类文档），本条只是给这个既有的静默失败补上可观测性，
"不抛"不等于"不记录"。两个参数均可选、默认 `None`（不提供时行为与
本次改动前完全一致），失败也绝不向上抛，不得反过来破坏 `release()`
本身"不抛"的契约。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger

TOOL_RELATIVE_PATH = Path("0-学习与工具") / "工具-共享文档编辑锁.py"

# 与人类会话（如 "Cowork-采购专线"/"CC-QD-B"）区分，方便 `status`/审计里
# 一眼看出锁当前是被机器人还是人类持有。
AIBOT_LOCK_WHO = "企微机器人"


class QueueLockBusy(RuntimeError):
    """队列文件当前被其他会话/进程持锁——本次不得写入。

    调用方（`intake.py::archive_inbound_message`）捕获此异常后应转入"推迟
    补录"路径（见 `queue_lock_pending.py`），而不是让消息静默丢失或让异常
    污染 `connection.py::on_message` 的通用 `message_dispatch_failed` 兜底
    （那条兜底不知道"应该记一条待补录记录"这件事）。
    """


class SubprocessQueueEditLock:
    """通过子进程调用共享编辑锁 CLI 工具，实现 `queue_appender.QueueEditLock`
    契约（duck-typed，无需显式继承）。

    `repo_root`：`工具-共享文档编辑锁.py` 所在仓库根——调用方负责解析好后
    传入（生产用法见 `connection.py`，用 `repo_paths.resolve_repo_root` 以
    `queue_path` 为锚点动态解析，覆盖"服务常驻 worktree 与队列文件所在
    checkout 不是同一个"的场景，与 #126 同一思路）。
    """

    def __init__(
        self, repo_root: Path, target: Path, *, who: str = AIBOT_LOCK_WHO, note: str = "",
        audit: Optional[AuditLogger] = None,
        alert_send: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._repo_root = repo_root
        self._target = target
        self._who = who
        self._note = note
        # 队列 #333③：release 被拒绝时的可观测性兜底，均可选、默认 None
        # （不提供时行为与本次改动前完全一致）——见类文档与 `release()`。
        self._audit = audit
        self._alert_send = alert_send

    def _tool_path(self) -> Path:
        return self._repo_root / TOOL_RELATIVE_PATH

    def try_acquire(self) -> None:
        tool = self._tool_path()
        if not tool.exists():
            # 工具本身找不到（仓库结构异常/repo_root 解析出了意料外的目录）
            # ——宁可保守地按"占用"处理、推迟这次追加，也不能悄悄放弃互斥
            # 保护直接写盘（那样就退回了 #168 修复前的行为）。
            raise QueueLockBusy(
                f"编辑锁工具不存在，按占用处理以策安全（不放弃互斥保护）：{tool}"
            )
        result = subprocess.run(
            [
                sys.executable, str(tool), "--file", str(self._target),
                "acquire", "--who", self._who, "--note", self._note,
            ],
            capture_output=True, text=True, encoding="utf-8",
        )
        if result.returncode != 0:
            raise QueueLockBusy(
                f"队列文件编辑锁占用中，机器人本次追加推迟：{result.stdout.strip()}"
            )

    def release(self) -> None:
        tool = self._tool_path()
        if not tool.exists():
            return
        # 释放失败不向上抛出（见 QueueEditLock 契约文档）——陈旧锁有 30
        # 分钟自动接管兜底，不会因这里的失败导致永久死锁。
        result = subprocess.run(
            [
                sys.executable, str(tool), "--file", str(self._target),
                "release", "--who", self._who,
            ],
            capture_output=True, text=True, encoding="utf-8",
        )
        if result.returncode != 0:
            self._record_release_rejected(result)

    def _record_release_rejected(self, result: subprocess.CompletedProcess) -> None:
        """队列 #333③：release 被拒绝（锁保持占用）时的可观测性兜底——见
        类文档。全程自我兜底：`audit.record`/`alert_send` 本身若抛出，也
        不得向上传播，否则本方法就反过来破坏了 `release()` "不抛"的契约
        （本方法存在的唯一目的就是不让这次拒绝继续悄无声息）。"""
        detail = (result.stdout or "").strip() or (result.stderr or "").strip()
        try:
            if self._audit is not None:
                self._audit.record(AuditEvent(
                    scenario="wecom-aibot", action="queue_edit_lock_release_rejected",
                    evaluator="system", automation_level="L1",
                    decision={"returncode": result.returncode, "who": self._who},
                    data_sources={"target": str(self._target), "detail": detail},
                ))
        except Exception:
            pass
        if self._alert_send is not None:
            try:
                self._alert_send(
                    f"队列编辑锁 release 被拒绝（returncode={result.returncode}），"
                    f"锁保持占用，30 分钟内未人工处理将由陈旧锁接管：{detail}"
                )
            except Exception:
                pass
