"""S4 桥一单测（队列 #366 M1）：回件到达即在跟进信 README 打第九态。

文件名与状态串**全部取自真实归档件与真实 README 行**（2026-08-21 实测）。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from aibot_service import followup_readme_bridge as bridge
from aibot_service import patrol_signal
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


def write_rows(repo_root: Path, rows: list[str]) -> Path:
    """多行 README——通道②的判定只有在「同一收信人有多封信」时才有内容可测。"""
    path = repo_root / bridge.FOLLOWUP_README_REL
    path.write_text(README_HEADER + "".join(r if r.endswith("\n") else r + "\n"
                                            for r in rows), encoding="utf-8")
    return path


def row(number: str, date: str, status: str, *, recipient: str = "采购部 · 姚祖怡",
        target: str | None = None) -> str:
    topic = "某事项" + (f" → 目标文件：`{target}`" if target else "")
    return f"| {number} | {date} | {recipient} | {topic} | 尽快 | {status} |"


def run(repo_root, *, filename=ARCHIVED, lock=None, audit=None, logs=None,
        department="采购部", **kwargs):
    lock = lock or FakeLock()
    return bridge.mark_reply_arrived(
        archived_filename=filename,
        repo_root=repo_root,
        audit=audit if audit is not None else FakeAudit(),
        lock_factory=lambda: lock,
        department=department,
        now=NOW,
        sleep=lambda _s: None,
        log=(logs.append if logs is not None else (lambda _m: None)),
        **kwargs,
    ), lock


def status_of(path: Path, number: str) -> str:
    line = [l for l in path.read_text(encoding="utf-8").splitlines()
            if l.startswith(f"| {number} ")][0]
    return line.rstrip("|").rsplit("|", 1)[-1].strip()


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
        assert logs and "跟进信README桥" in logs[0]
        assert audit.events[0].decision["channel"] == fg.PAIR_CHANNEL_STEM, (
            "派单件 §3.4：审计须记录命中的是哪条通道，日后复盘误配全靠它"
        )


class TestTwoChannelPairing:
    """`OP-0823-D` §3.1：① stem 优先，② 未命中时配「最新一封已发出的信」。"""

    def test_通道一stem命中即止不进通道二(self, repo):
        """🔴 专防「去掉 stem 造成净回归」：这里通道② 会给出另一封（`#18`
        更新），断言配的仍是 stem 对上的 `#17`。"""
        path = write_rows(repo, [
            row("采购部#17", "2026-08-20", "✅ 已推送 2026-08-20 12:20 UTC",
                target=LETTER_FILE),
            row("采购部#18", "2026-08-22", "✅ 已推送 2026-08-22 09:00 UTC"),
        ])
        result, _ = run(repo, filename=ARCHIVED)
        assert result.action == bridge.ACTION_MARKED
        assert result.letter_number == "采购部#17"
        assert result.channel == fg.PAIR_CHANNEL_STEM
        assert fg.REPLY_ARRIVED_STATUS not in status_of(path, "采购部#18")

    def test_通道二纯文字回件配到最新一封已发出未闭环的信(self, repo):
        """派单件 §五.1：历史上必然配不上的那一类，现在**能**打上第九态。"""
        path = write_rows(repo, [
            row("采购部#16", "2026-08-18", "✅ 已推送 2026-08-18 09:00 UTC"),
            row("采购部#17", "2026-08-20", "✅ 已推送 2026-08-20 12:20 UTC"),
        ])
        audit = FakeAudit()
        result, lock = run(repo, filename=TEXT_FEEDBACK, audit=audit)
        assert result.action == bridge.ACTION_MARKED
        assert result.letter_number == "采购部#17"
        assert result.channel == fg.PAIR_CHANNEL_LATEST
        assert lock.acquired == 1
        assert fg.REPLY_ARRIVED_STATUS in status_of(path, "采购部#17")
        assert fg.REPLY_ARRIVED_STATUS not in status_of(path, "采购部#16")
        assert audit.events[0].decision["channel"] == fg.PAIR_CHANNEL_LATEST

    def test_表内行序不是时间序时仍按日期取最新(self, repo):
        """实测：`采购部#4`（07-21）在真身 README 里排在 `#17`（08-20）**之后**。
        只按表内行序取"最后一行"会配错，且不报任何错。"""
        path = write_rows(repo, [
            row("采购部#17", "2026-08-20", "✅ 已推送 2026-08-20 12:20 UTC"),
            row("采购部#4", "2026-07-21", "✅ 已推送 2026-07-22 04:56 UTC"),
        ])
        result, _ = run(repo, filename=TEXT_FEEDBACK)
        assert result.letter_number == "采购部#17"
        assert fg.REPLY_ARRIVED_STATUS not in status_of(path, "采购部#4")

    def test_部门名带不带部字都要认(self, repo):
        """`department_mapping.yaml` 里陈承那行是 `IT`，README 写的是 `IT部`。"""
        write_rows(repo, [
            row("IT部#9", "2026-08-18", "✅ 已推送 2026-08-18 07:23 UTC",
                recipient="IT部 · 陈承"),
        ])
        result, _ = run(repo, filename="IT-2023458-回复-2026-08-22-文本反馈-abc123.md",
                        department="IT")
        assert result.action == bridge.ACTION_MARKED
        assert result.letter_number == "IT部#9"


class TestSkipNotYetSent:
    """§五.3：`⏳ 待你审`／`🆕 待发`／`⏸ 暂缓` 都还没到专员手里，不能当目标。"""

    @pytest.mark.parametrize("draft_status", ["⏳ 待你审", "🆕 待发", "⏸ 暂缓"])
    def test_最新一封尚未发出时配到次新那封(self, repo, draft_status):
        path = write_rows(repo, [
            row("采购部#17", "2026-08-20", "✅ 已推送 2026-08-20 12:20 UTC"),
            row("采购部#18", "2026-08-22", draft_status),
        ])
        result, _ = run(repo, filename=TEXT_FEEDBACK)
        assert result.letter_number == "采购部#17", (
            f"「{draft_status}」的信专员根本没收到，不可能是这条回件的目标"
        )
        assert status_of(path, "采购部#18") == draft_status


class TestSupplementAfterClosed:
    """§3.3 ＋ §五.6：闭环后到达的补充说明只落档，**不得制造假警报**。"""

    def test_最新一封已闭环则不动README且只低噪(self, repo):
        path = write_rows(repo, [
            row("采购部#17", "2026-08-20", "📥 已回件并回灌（2026-08-21 拆件巡逻）"),
        ])
        before = path.read_text(encoding="utf-8")
        audit, logs, alerts = FakeAudit(), [], []
        result, lock = run(repo, filename=TEXT_FEEDBACK, audit=audit, logs=logs,
                           alert_send=alerts.append)
        assert result.action == bridge.ACTION_SUPPLEMENT
        assert path.read_text(encoding="utf-8") == before, "README 必须一字未动"
        assert lock.attempts == 0, "不改就不该去抢锁"
        assert not alerts, "🔴 每条补充说明都告警＝用误报训练人忽略告警"
        assert logs and logs[0].startswith("·"), (
            f"这是预期内常态，前缀必须是低噪的「·」而非「⚠」，实得：{logs}"
        )
        assert audit.actions()[0] == "followup_readme_bridge_supplement_after_closed"

    def test_闸不因补充而重新锁(self, repo):
        path = write_rows(repo, [
            row("采购部#17", "2026-08-20", "📥 已回件并回灌（2026-08-21 拆件巡逻）"),
        ])
        run(repo, filename=TEXT_FEEDBACK)
        assert fg.is_closed_status(status_of(path, "采购部#17")), "不得重开在途"


class TestNoMatch:
    def test_该收信人无任何已发出的信时WARN且不动(self, repo):
        path = write_rows(repo, [
            row("采购部#18", "2026-08-22", "⏳ 待你审"),
        ])
        before = path.read_text(encoding="utf-8")
        audit, logs = FakeAudit(), []
        result, lock = run(repo, filename=TEXT_FEEDBACK, audit=audit, logs=logs)
        assert result.action == bridge.ACTION_NO_DISPATCHED
        assert path.read_text(encoding="utf-8") == before
        assert lock.attempts == 0
        assert logs and logs[0].startswith("⚠"), f"必须 fail-loud，实得：{logs}"
        assert audit.actions()[0] == "followup_readme_bridge_no_dispatched_letter"

    def test_收信人解析不出时WARN且不猜(self, repo):
        """fail-closed 归「待分拣」的进件——`department` 传 None，通道②不可用。"""
        path = write_rows(repo, [
            row("采购部#17", "2026-08-20", "✅ 已推送 2026-08-20 12:20 UTC"),
        ])
        before = path.read_text(encoding="utf-8")
        audit, logs = FakeAudit(), []
        result, lock = run(repo, filename=TEXT_FEEDBACK, department=None,
                           audit=audit, logs=logs)
        assert result.action == bridge.ACTION_NO_DEPARTMENT
        assert path.read_text(encoding="utf-8") == before, (
            "不知道是谁发来的就绝不动 README——这正是 fail-closed 的意义"
        )
        assert lock.attempts == 0
        assert logs and logs[0].startswith("⚠")
        assert audit.actions()[0] == "followup_readme_bridge_no_department"

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

class TestHealthCheckDoesNotBlock:
    """§3.1bis：「已发出未闭环」这个量只报数，**不参与转态、不阻塞配对**。

    🔴 这一条专防已被推翻的方案 B（唯一在途）借尸还魂——它在生产数据上恒不
    成立（四位收信人各有 7／6／4／4 封历史未闭环信），按它实现机制上线当天
    就是哑的。
    """

    def test_堆了六封历史未闭环信也照样配得上(self, repo):
        path = write_rows(repo, [
            row(f"采购部#{n}", f"2026-07-{10 + n:02d}", "✅ 已推送")
            for n in range(1, 7)
        ] + [row("采购部#17", "2026-08-20", "✅ 已推送 2026-08-20 12:20 UTC")])
        logs = []
        result, _ = run(repo, filename=TEXT_FEEDBACK, logs=logs)
        assert result.action == bridge.ACTION_MARKED, "历史积压不得阻塞配对"
        assert result.letter_number == "采购部#17"
        assert fg.REPLY_ARRIVED_STATUS in status_of(path, "采购部#17")
        for n in range(1, 7):
            assert fg.REPLY_ARRIVED_STATUS not in status_of(path, f"采购部#{n}")
        assert any("健康检查" in m and "7 封" in m for m in logs), (
            f"健康检查须报出这 7 封（6 封历史 ＋ #17），实得：{logs}"
        )


class TestStatusCompositionExtra:
    def test_锁目标是仓库相对正斜杠路径(self):
        # 传绝对路径能锁住文件，但 `cmd_release` 里那套 README 校验会按
        # `args.file == FOLLOWUP_README_TARGET` 逐字比对 ⇒ 静默不跑。
        assert str(bridge.LOCK_TARGET) == bridge.FOLLOWUP_README_REL
        assert "\\" not in str(bridge.LOCK_TARGET)


class TestPatrolSignal:
    """队列 #382⑴：只有「真的标了第九态」（`ACTION_MARKED`）才该给拆件巡逻
    留信号——其余分支（已闭环/未命中/锁忙/幂等重投）README 全都没变，不
    该制造一次多余开班。"""

    def test_真实标记会给巡逻留信号(self, repo):
        write_readme(repo, "✅ 已推送 2026-08-20 12:20 UTC")
        result, _ = run(repo)
        assert result.action == bridge.ACTION_MARKED
        snapshot = patrol_signal.read_signal(repo)
        assert snapshot.present is True
        assert snapshot.pending[0]["letter_number"] == "采购部#17"
        assert snapshot.pending[0]["archived_filename"] == ARCHIVED
        assert snapshot.pending[0]["at"] == "2026-08-21T13:15:30Z"

    def test_幂等重投不重复留信号(self, repo):
        write_readme(repo, "✅ 已推送 2026-08-20 12:20 UTC")
        run(repo)
        patrol_signal.clear_signal(repo)
        result, _ = run(repo)
        assert result.action == bridge.ACTION_ALREADY
        assert patrol_signal.read_signal(repo).present is False, (
            "第二次是 ACTION_ALREADY——README 没有任何变化，不该无中生有一个信号"
        )

    def test_补充说明不留信号(self, repo):
        write_readme(repo, "📥 已回件并回灌（2026-08-21 拆件巡逻）")
        result, _ = run(repo, filename=TEXT_FEEDBACK)
        assert result.action == bridge.ACTION_SUPPLEMENT
        assert patrol_signal.read_signal(repo).present is False

    def test_未命中不留信号(self, repo):
        write_rows(repo, [row("采购部#18", "2026-08-22", "⏳ 待你审")])
        result, _ = run(repo, filename=TEXT_FEEDBACK)
        assert result.action == bridge.ACTION_NO_DISPATCHED
        assert patrol_signal.read_signal(repo).present is False

    def test_锁忙放弃不留信号(self, repo):
        write_readme(repo, "✅ 已推送 2026-08-20 12:20 UTC")
        result, _ = run(repo, lock=FakeLock(busy_times=99))
        assert result.action == bridge.ACTION_LOCK_BUSY
        assert patrol_signal.read_signal(repo).present is False

    def test_信号写入自身失败不影响标记结果(self, repo, monkeypatch):
        """`patrol_signal.raise_signal` 出问题绝不能把一次已经成功的
        README 标记反过来变成失败——见 `_raise_patrol_signal` docstring。"""
        write_readme(repo, "✅ 已推送 2026-08-20 12:20 UTC")
        monkeypatch.setattr(
            patrol_signal, "raise_signal",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("信号模块挂了")),
        )
        result, _ = run(repo)
        assert result.action == bridge.ACTION_MARKED, "旁路信号失败不得拖累主流程"
