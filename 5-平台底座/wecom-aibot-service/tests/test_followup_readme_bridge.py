"""S4 桥一单测（队列 #366 M1）：回件到达即在跟进信 README 打第九态。

文件名与状态串**全部取自真实归档件与真实 README 行**（2026-08-21 实测）。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from aibot_service import followup_readme_bridge as bridge
from aibot_service.queue_edit_lock import QueueLockBusy
from zhuopin_platform.shared_tools import followup_gate as fg

README_HEADER = (
    "## 现有跟进信清单\n\n"
    "| 编号 | 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |\n"
    "|--------|------|--------|---------|---------|---------|\n"
)
LETTER_FILE = "采购部-姚祖怡-跟进-2026-08-20-SC2采购周报口径判例批改.md"
ARCHIVED = (
    "采购部-YaoZuYi-回复-2026-08-21-采购部-姚祖怡-跟进-2026-08-20-"
    "SC2采购周报口径判例批改-0d6acc8a6238e6155c6e91f874246213.docx"
)
TEXT_FEEDBACK = "采购部-YaoZuYi-回复-2026-08-19-文本反馈-19662402efb7e15f1fe4993c9ea51772.md"
NOW = datetime(2026, 8, 21, 13, 15, 30, tzinfo=timezone.utc)


class FakeAudit:
    def __init__(self):
        self.events = []

    def record(self, event):
        self.events.append(event)

    def actions(self):
        return [e.action for e in self.events]


class FakeLock:
    """记录 acquire/release 次序；`busy_times` 次之内的 acquire 抛忙。"""

    def __init__(self, busy_times=0, on_acquire=None):
        self.busy_times = busy_times
        self.attempts = 0
        self.acquired = 0
        self.released = 0
        self._on_acquire = on_acquire

    def try_acquire(self):
        self.attempts += 1
        if self.attempts <= self.busy_times:
            raise QueueLockBusy("队列文件编辑锁占用中")
        self.acquired += 1
        if self._on_acquire is not None:
            self._on_acquire()

    def release(self):
        self.released += 1


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / bridge.FOLLOWUP_README_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    return tmp_path


def write_readme(repo_root: Path, status: str, number: str = "采购部#17",
                 target: str = LETTER_FILE) -> Path:
    path = repo_root / bridge.FOLLOWUP_README_REL
    path.write_text(
        README_HEADER
        + f"| {number} | 2026-08-20 | 采购部 · 姚祖怡 | SC2 判例批改 → "
          f"目标文件：`{target}` | 尽快 | {status} |\n",
        encoding="utf-8",
    )
    return path


def run(repo_root, *, filename=ARCHIVED, lock=None, audit=None, logs=None, **kwargs):
    lock = lock or FakeLock()
    return bridge.mark_reply_arrived(
        archived_filename=filename,
        repo_root=repo_root,
        audit=audit if audit is not None else FakeAudit(),
        lock_factory=lambda: lock,
        now=NOW,
        sleep=lambda _s: None,
        log=(logs.append if logs is not None else (lambda _m: None)),
        **kwargs,
    ), lock


class TestHappyPath:
    def test_在途信被标为第九态且原状态原样保留(self, repo):
        path = write_readme(repo, "✅ 已推送 2026-08-20 12:20 UTC")
        result, lock = run(repo)
        assert result.action == bridge.ACTION_MARKED
        assert result.letter_number == "采购部#17"
        text = path.read_text(encoding="utf-8")
        assert fg.REPLY_ARRIVED_STATUS in text
        assert "2026-08-21T13:15:30Z" in text, "UTC 且显式带 Z（根 CLAUDE.md §5 硬规则）"
        assert "✅ 已推送 2026-08-20 12:20 UTC" in text, (
            "原状态不得被覆盖丢失——「这封信何时推送」这一格没有任何别处的副本"
        )
        assert lock.acquired == 1 and lock.released == 1

    def test_标完之后闸仍锁(self, repo):
        path = write_readme(repo, "✅ 已推送 2026-08-20 12:20 UTC")
        run(repo)
        status_line = [l for l in path.read_text(encoding="utf-8").splitlines()
                       if l.startswith("| 采购部#17")][0]
        status = status_line.rstrip("|").rsplit("|", 1)[-1].strip()
        assert not fg.is_closed_status(status), "第九态是「回件到了」，不是「回灌完了」"
        assert fg.classify_status(status) == "reply_arrived"

    def test_写入必须走编辑锁(self, repo):
        write_readme(repo, "✅ 已推送 2026-08-20 12:20 UTC")
        _, lock = run(repo)
        assert lock.acquired == 1, "不得绕开协议〇.7 直接写文件"

    def test_留痕含审计事件与一行可见输出(self, repo):
        write_readme(repo, "✅ 已推送 2026-08-20 12:20 UTC")
        audit, logs = FakeAudit(), []
        run(repo, audit=audit, logs=logs)
        assert audit.actions() == ["followup_readme_bridge_marked"]
        assert len(logs) == 1 and "跟进信README桥" in logs[0]


class TestNoMatch:
    def test_匹配不上时README一字不改且打印WARN(self, repo):
        """反例单测⑶（派单件 §六.3）——「匹配不上时不要猜」。"""
        path = write_readme(repo, "✅ 已推送 2026-08-20 12:20 UTC")
        before = path.read_text(encoding="utf-8")
        audit, logs = FakeAudit(), []
        result, lock = run(repo, filename=TEXT_FEEDBACK, audit=audit, logs=logs)
        assert result.action == bridge.ACTION_UNMATCHED
        assert path.read_text(encoding="utf-8") == before, "README 必须一字未动"
        assert lock.attempts == 0, "配不上就不该去抢锁"
        assert logs and logs[0].startswith("⚠"), f"必须 fail-loud，实得：{logs}"
        assert audit.actions() == ["followup_readme_bridge_unmatched"]

    def test_README行没有目标文件标注时同样不猜(self, repo):
        path = repo / bridge.FOLLOWUP_README_REL
        path.write_text(
            README_HEADER
            + "| 采购部#3 | 2026-07-15 | 采购部 · 姚祖怡 | 没有标注目标文件 | 尽快 | ✅ 已推送 |\n",
            encoding="utf-8",
        )
        before = path.read_text(encoding="utf-8")
        result, _ = run(repo)
        assert result.action == bridge.ACTION_UNMATCHED
        assert path.read_text(encoding="utf-8") == before

    def test_README不存在时不抛只留痕(self, tmp_path):
        audit = FakeAudit()
        result, _ = run(tmp_path, audit=audit)
        assert result.action == bridge.ACTION_NO_README
        assert audit.actions() == ["followup_readme_bridge_no_readme"]


class TestIdempotence:
    @pytest.mark.parametrize("status", [
        "📥 已回件并回灌（2026-08-21 拆件巡逻）",
        "✅ **无需回复**（发出即闭环）",
        "**❌ 已作废 · 9 月重写**",
    ])
    def test_已闭环的信不被推回第九态(self, repo, status):
        path = write_readme(repo, status)
        before = path.read_text(encoding="utf-8")
        result, lock = run(repo)
        assert result.action == bridge.ACTION_ALREADY
        assert path.read_text(encoding="utf-8") == before
        assert lock.attempts == 0

    def test_同一条回件重投不会叠加第九态(self, repo):
        path = write_readme(repo, "✅ 已推送 2026-08-20 12:20 UTC")
        run(repo)
        once = path.read_text(encoding="utf-8")
        result, _ = run(repo)
        assert result.action == bridge.ACTION_ALREADY
        assert path.read_text(encoding="utf-8") == once


class TestLockContention:
    def test_锁忙时重试指数退避(self, repo):
        write_readme(repo, "✅ 已推送 2026-08-20 12:20 UTC")
        lock = FakeLock(busy_times=2)
        result, _ = run(repo, lock=lock)
        assert result.action == bridge.ACTION_MARKED
        assert lock.attempts == 3

    def test_重试用尽后告警且绝不静默(self, repo):
        path = write_readme(repo, "✅ 已推送 2026-08-20 12:20 UTC")
        before = path.read_text(encoding="utf-8")
        lock = FakeLock(busy_times=99)
        alerts, logs, audit = [], [], FakeAudit()
        result, _ = run(repo, lock=lock, audit=audit, logs=logs,
                        alert_send=alerts.append)
        assert result.action == bridge.ACTION_LOCK_BUSY
        assert lock.attempts == bridge.DEFAULT_MAX_ATTEMPTS
        assert path.read_text(encoding="utf-8") == before
        assert alerts, "放弃时必须告警"
        assert logs and logs[0].startswith("⚠")
        assert audit.actions() == ["followup_readme_bridge_lock_busy"]

    def test_告警通道自身抛异常也不得让本函数抛(self, repo):
        write_readme(repo, "✅ 已推送 2026-08-20 12:20 UTC")

        def boom(_msg):
            raise RuntimeError("告警通道挂了")

        result, _ = run(repo, lock=FakeLock(busy_times=99), alert_send=boom)
        assert result.action == bridge.ACTION_LOCK_BUSY


class TestReReadUnderLock:
    def test_持锁后重读发现别人已转态则不覆盖(self, repo):
        """锁外读到的行位置在持锁那一刻可能已经过期——直接按行号写回等于
        把别人的改动覆盖掉。这正是编辑锁存在的理由。"""
        path = write_readme(repo, "✅ 已推送 2026-08-20 12:20 UTC")

        def someone_else_closes_it():
            write_readme(repo, "📥 已回件并回灌（2026-08-21 拆件巡逻抢先转态）")

        result, _ = run(repo, lock=FakeLock(on_acquire=someone_else_closes_it))
        assert result.action == bridge.ACTION_ALREADY
        assert "📥 已回件并回灌" in path.read_text(encoding="utf-8")
        assert fg.REPLY_ARRIVED_STATUS not in path.read_text(encoding="utf-8")


class TestStatusComposition:
    def test_前缀在最前旧状态接在后面(self):
        built = bridge.build_reply_arrived_status(
            "✅ 已推送 2026-08-20 12:20 UTC", ARCHIVED, NOW)
        assert built.startswith(fg.REPLY_ARRIVED_STATUS)
        assert built.endswith("✅ 已推送 2026-08-20 12:20 UTC")
        assert ARCHIVED in built, "须写明溯源，便于反查是哪一件回件触发的"

    def test_锁目标是仓库相对正斜杠路径(self):
        # 传绝对路径能锁住文件，但 `cmd_release` 里那套 README 校验会按
        # `args.file == FOLLOWUP_README_TARGET` 逐字比对 ⇒ 静默不跑。
        assert str(bridge.LOCK_TARGET) == bridge.FOLLOWUP_README_REL
        assert "\\" not in str(bridge.LOCK_TARGET)
