"""队列文件写入前占用协议〇.7 共享编辑锁的生产实现（队列 #168）。

复用既有 CLI 工具 `0-学习与工具/工具-共享文档编辑锁.py`（当作外部子进程
调用，与 `queue_git_sync.py` 对 `git` 子进程的复用同构）——不在这里重新
实现锁协议本身，避免协议分叉成两份互不知情的实现（人类会话与机器人各
认一套"什么算占用""陈旧锁多久可接管"，只会制造新的绕锁缺陷）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

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
        self, repo_root: Path, target: Path, *, who: str = AIBOT_LOCK_WHO, note: str = ""
    ) -> None:
        self._repo_root = repo_root
        self._target = target
        self._who = who
        self._note = note

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
        subprocess.run(
            [
                sys.executable, str(tool), "--file", str(self._target),
                "release", "--who", self._who,
            ],
            capture_output=True, text=True, encoding="utf-8",
        )
