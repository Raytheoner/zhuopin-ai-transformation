"""队列 #382⑴bis 单测：桥一落信号后直接起无头 CC 拆件的起活机制本身。

真实 `Popen`／`tasklist` 一律不在单测里调用——`popen`/`pid_alive` 均可
注入替身。真实、非模拟的子进程起活验证见收工报告里登记的手工实测记录
（单测不能替代"真的起了一个 claude 进程"这件事，同派单件 §验收「只跑通
单测不算」）。
"""
from __future__ import annotations

import itertools
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from aibot_service import patrol_dispatch as pd
from aibot_service import patrol_signal
from aibot_service.repo_paths import (
    resolve_patrol_charter_path,
    resolve_patrol_dispatch_failure_state_path,
    resolve_patrol_dispatch_lock_path,
    resolve_patrol_dispatch_log_dir,
)

@pytest.fixture(autouse=True)
def isolated_codex_policy(tmp_path, monkeypatch):
    # 每个旧状态机用例仍走注入的FakeProc；仅配置新provider接缝。
    monkeypatch.delenv('ZHUOPIN_CODEX_RUNTIME', raising=False)
    config=tmp_path/'.codex'
    config.mkdir(exist_ok=True)
    (config/'runtime.local.json').write_text(json.dumps({'python':sys.executable}),encoding='utf-8')
    (config/'consumers.local.json').write_text(json.dumps({'patrol':{'enabled':True}}),encoding='utf-8')
    provider=tmp_path/'0-学习与工具/codex-handoff/model_provider.py'
    provider.parent.mkdir(parents=True,exist_ok=True)
    provider.write_text('# FakeProc only',encoding='utf-8')


NOW = datetime(2026, 9, 4, 15, 0, 0, tzinfo=timezone.utc)


class FakeAudit:
    def __init__(self):
        self.events = []

    def record(self, event):
        self.events.append(event)

    def actions(self):
        return [e.action for e in self.events]


class FakeStdin:
    def __init__(self, raise_on_write=False):
        self.written = ""
        self.closed = False
        self._raise = raise_on_write

    def write(self, text):
        if self._raise:
            raise RuntimeError("stdin 挂了")
        self.written += text

    def close(self):
        self.closed = True


class FakeProc:
    def __init__(self, pid=4242, stdin_raises=False):
        self.pid = pid
        self.stdin = FakeStdin(raise_on_write=stdin_raises)

    def wait(self):
        """默认代表"进程立即退出"——`_spawn_watcher` 里 `proc.wait()` 的替身。"""
        return 0


def write_charter(repo_root: Path, text: str = "章程正文") -> Path:
    path = resolve_patrol_charter_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class TestStarted:
    def test_无陈旧锁时正常起活(self, tmp_path):
        write_charter(tmp_path)
        calls = []

        def popen(argv, **kwargs):
            calls.append({"argv": argv, "kwargs": kwargs})
            return FakeProc(pid=1234)

        result = pd.dispatch_headless_patrol(
            tmp_path, now=NOW, popen=popen, pid_alive=lambda pid: False,
        )
        assert result.action == pd.ACTION_STARTED
        assert result.pid == 1234
        assert len(calls) == 1
        argv = calls[0]["argv"]
        assert argv[0] == sys.executable
        assert "model_provider.py" in argv[2]
        assert not any("dangerously" in arg for arg in argv)
        assert argv[argv.index("--sandbox") + 1] == "workspace-write"
        assert calls[0]["kwargs"]["cwd"] == str(tmp_path)

    def test_起活带model参数取自模块常量(self, tmp_path):
        # 队列 #581 ⑵：无头巡逻默认走最便宜的模型，argv 里的值须取自 PATROL_MODEL 常量，不得硬编码字符串。
        write_charter(tmp_path)
        calls = []

        def popen(argv, **kwargs):
            calls.append({"argv": argv, "kwargs": kwargs})
            return FakeProc(pid=1234)

        pd.dispatch_headless_patrol(tmp_path, now=NOW, popen=popen, pid_alive=lambda pid: False)
        argv = calls[0]["argv"]
        assert "--model" not in argv  # 继承已验证的Codex配置，禁止sonnet/opus透传

    def test_prompt含章程原文且未改一字(self, tmp_path):
        charter_text = "第一行\n第二行\n"
        write_charter(tmp_path, charter_text)
        captured = {}

        def popen(argv, **kwargs):
            proc = FakeProc()
            return proc

        # 直接测 _build_prompt，避免依赖能否从 FakeProc.stdin 反查写入内容
        prompt = pd._build_prompt(charter_text)
        assert prompt.endswith(charter_text)
        assert charter_text in prompt

    def test_起活成功后写并发守卫锁文件(self, tmp_path):
        write_charter(tmp_path)
        pd.dispatch_headless_patrol(
            tmp_path, now=NOW, popen=lambda *a, **k: FakeProc(pid=555),
            pid_alive=lambda pid: False,
        )
        lock_path = resolve_patrol_dispatch_lock_path(tmp_path)
        data = json.loads(lock_path.read_text(encoding="utf-8"))
        assert data["pid"] == 555
        assert data["started_at"] == "2026-09-04T15:00:00Z"

    def test_起活写日志目录与文件(self, tmp_path):
        write_charter(tmp_path)
        result = pd.dispatch_headless_patrol(
            tmp_path, now=NOW, popen=lambda *a, **k: FakeProc(),
            pid_alive=lambda pid: False,
        )
        log_dir = resolve_patrol_dispatch_log_dir(tmp_path)
        assert log_dir.is_dir()
        assert Path(result.log_path).parent == log_dir

    def test_stdin写入失败不影响已起活的判定(self, tmp_path):
        """子进程已经真实起了——stdin 写失败只影响它读不读得到 prompt，
        不代表"没起活"，不得因此报 failed（见文首取舍 4 附近的非阻塞说明；
        进程既已 `Popen` 成功，起活这件事已是既成事实）。"""
        write_charter(tmp_path)
        result = pd.dispatch_headless_patrol(
            tmp_path, now=NOW,
            popen=lambda *a, **k: FakeProc(stdin_raises=True),
            pid_alive=lambda pid: False,
        )
        assert result.action == pd.ACTION_STARTED

    def test_审计记录一条started事件(self, tmp_path):
        write_charter(tmp_path)
        audit = FakeAudit()
        pd.dispatch_headless_patrol(
            tmp_path, now=NOW, audit=audit,
            popen=lambda *a, **k: FakeProc(pid=99),
            pid_alive=lambda pid: False,
        )
        assert audit.actions() == ["patrol_headless_dispatch_started"]
        assert audit.events[0].decision["pid"] == 99


class TestConcurrencyGuard:
    def test_已有存活进程时不重复起活(self, tmp_path):
        write_charter(tmp_path)
        lock_path = resolve_patrol_dispatch_lock_path(tmp_path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(
            json.dumps({"pid": 777, "started_at": "2026-09-04T14:00:00Z"}),
            encoding="utf-8",
        )
        calls = []
        result = pd.dispatch_headless_patrol(
            tmp_path, now=NOW,
            popen=lambda *a, **k: calls.append(1) or FakeProc(),
            pid_alive=lambda pid: pid == 777,
        )
        assert result.action == pd.ACTION_SKIPPED_BUSY
        assert result.pid == 777
        assert calls == [], "存活时绝不能再起一个"

    def test_陈旧锁pid已不存活则照常起活(self, tmp_path):
        write_charter(tmp_path)
        lock_path = resolve_patrol_dispatch_lock_path(tmp_path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(
            json.dumps({"pid": 777, "started_at": "2026-09-04T02:00:00Z"}),
            encoding="utf-8",
        )
        result = pd.dispatch_headless_patrol(
            tmp_path, now=NOW, popen=lambda *a, **k: FakeProc(pid=888),
            pid_alive=lambda pid: False,
        )
        assert result.action == pd.ACTION_STARTED
        assert result.pid == 888

    def test_锁文件损坏按陈旧锁处理照常起活(self, tmp_path):
        write_charter(tmp_path)
        lock_path = resolve_patrol_dispatch_lock_path(tmp_path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("这不是合法json{{{", encoding="utf-8")
        result = pd.dispatch_headless_patrol(
            tmp_path, now=NOW, popen=lambda *a, **k: FakeProc(pid=42),
            pid_alive=lambda pid: True,  # 就算传真会说"活着"，坏锁也不该采信
        )
        assert result.action == pd.ACTION_STARTED

    def test_跳过时也记一条审计(self, tmp_path):
        write_charter(tmp_path)
        lock_path = resolve_patrol_dispatch_lock_path(tmp_path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(json.dumps({"pid": 1}), encoding="utf-8")
        audit = FakeAudit()
        pd.dispatch_headless_patrol(
            tmp_path, now=NOW, audit=audit,
            popen=lambda *a, **k: FakeProc(),
            pid_alive=lambda pid: True,
        )
        assert audit.actions() == ["patrol_headless_dispatch_skipped_busy"]


class TestFailOpen:
    """起活失败绝不能吞掉——每条都必须落审计＋日志，且不得抛出。"""

    def test_章程文件缺失起活失败(self, tmp_path):
        # 故意不写章程文件
        logs = []
        result = pd.dispatch_headless_patrol(
            tmp_path, now=NOW, log=logs.append,
            popen=lambda *a, **k: FakeProc(), pid_alive=lambda pid: False,
        )
        assert result.action == pd.ACTION_FAILED
        assert "章程" in result.detail
        assert logs and logs[0].startswith("⚠")

    def test_Popen自身抛异常起活失败(self, tmp_path):
        write_charter(tmp_path)

        def boom(*a, **k):
            raise OSError("claude 不在 PATH")

        audit = FakeAudit()
        result = pd.dispatch_headless_patrol(
            tmp_path, now=NOW, audit=audit, popen=boom,
            pid_alive=lambda pid: False,
        )
        assert result.action == pd.ACTION_FAILED
        assert "claude" in result.detail or "PATH" in result.detail
        assert audit.actions() == ["patrol_headless_dispatch_failed"]

    def test_起活流程内未预期异常也不向上抛(self, tmp_path):
        write_charter(tmp_path)

        def boom_pid_alive(pid):
            raise RuntimeError("判活逻辑本身挂了")

        lock_path = resolve_patrol_dispatch_lock_path(tmp_path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(json.dumps({"pid": 1}), encoding="utf-8")

        result = pd.dispatch_headless_patrol(
            tmp_path, now=NOW, popen=lambda *a, **k: FakeProc(),
            pid_alive=boom_pid_alive,
        )
        assert result.action == pd.ACTION_FAILED, "绝不向上抛，只能落成 failed"

    def test_信号文件本身不被本模块触碰(self, tmp_path):
        """起活失败不代表信号被消费——本模块从不读写 patrol_signal.json，
        信号消费只发生在无头 CC 自己按章程 §〇ter 走完流程之后。"""
        result = pd.dispatch_headless_patrol(
            tmp_path, now=NOW, popen=lambda *a, **k: FakeProc(),
            pid_alive=lambda pid: False,
        )
        assert result.action == pd.ACTION_FAILED  # 章程缺失
        from aibot_service.repo_paths import PATROL_SIGNAL_RELATIVE_PATH
        assert not (tmp_path / PATROL_SIGNAL_RELATIVE_PATH).exists()


class TestPidAlive:
    def test_tasklist输出含该pid判定为存活(self, monkeypatch):
        class FakeCompleted:
            stdout = 'Image Name  PID  ...\r\nclaude.exe  1234  ...\r\n'

        def fake_run(argv, **kwargs):
            assert "1234" in argv[-1]
            return FakeCompleted()

        monkeypatch.setattr(pd.subprocess, "run", fake_run)
        assert pd._pid_alive(1234) is True

    def test_tasklist输出不含该pid判定为不存活(self, monkeypatch):
        class FakeCompleted:
            stdout = "INFO: No tasks are running which match the specified criteria."

        monkeypatch.setattr(pd.subprocess, "run", lambda *a, **k: FakeCompleted())
        assert pd._pid_alive(9999) is False

    def test_tasklist本身异常时判定为不存活(self, monkeypatch):
        """查询失败宁可判"不存活"（可能多起一个、被章程编辑锁兜住），也不
        可判"存活"（会让信号原地卡死）——见 `_pid_alive` 文首取舍。"""
        def boom(*a, **k):
            raise FileNotFoundError("tasklist 不存在")

        monkeypatch.setattr(pd.subprocess, "run", boom)
        assert pd._pid_alive(1) is False


class TestPrompt:
    def test_事件驱动前言不改写章程原文(self, tmp_path):
        charter_text = write_charter(tmp_path, "§〇ter 一字不改\n§一 也不改\n").read_text(
            encoding="utf-8"
        )
        prompt = pd._build_prompt(charter_text)
        # 前言只应"追加在前面"，章程原文本身必须逐字原样出现在结尾
        assert prompt.rsplit(charter_text, 1)[-1] == "" or prompt.endswith(charter_text)
        assert charter_text in prompt
        assert prompt.index(charter_text) > 0, "章程原文前必须有事件驱动说明，不能是纯拼接"

    def test_前言不再要求无头CC自己回到一再走一轮(self, tmp_path):
        # 队列 #599 P6：这条指令已迁移给调度层（_spawn_watcher），
        # 前言里不应再出现让无头 CC 自己判断"要不要再走一轮"的旧版措辞。
        assert "回到 §一 再走一轮" not in pd._EVENT_DRIVEN_PREAMBLE
        assert "不必回到" in pd._EVENT_DRIVEN_PREAMBLE
        assert "调度层" in pd._EVENT_DRIVEN_PREAMBLE


class TestWatcherChaining:
    """队列 #599 P6：调度层在子进程退出后复查信号，链式起下一轮。"""

    def test_锁占用期间到达的信号不丢失(self, tmp_path):
        write_charter(tmp_path)
        calls = []

        class Round1Proc(FakeProc):
            def wait(self):
                # 模拟：第一轮无头 CC 正跑着的时候，又有一条新回件到达——
                # 本模块从不读写 patrol_signal.json（文首取舍 3），这里只是
                # 在测试里代替"外部世界在它运行期间发生的事"。
                patrol_signal.raise_signal(
                    tmp_path, letter_number="采购部#1",
                    archived_filename="x.md", now=NOW,
                )
                return 0

        class Round2Proc(FakeProc):
            def wait(self):
                # 模拟：第二轮无头 CC 按章程走完流程、自行消费了信号——
                # 信号消费只发生在无头 CC 自己那一侧，不是本模块的职责。
                patrol_signal.clear_signal(tmp_path)
                return 0

        def popen(argv, **kwargs):
            proc = (Round1Proc if not calls else Round2Proc)(pid=100 + len(calls))
            calls.append(proc)
            return proc

        pd.dispatch_headless_patrol(
            tmp_path, now=NOW, popen=popen, pid_alive=lambda pid: False,
            run_in_thread=lambda fn: fn(),
            # 队列 #416 ⑸bis①判据＝存活 < 60s 且信号未消费才算夭折；本测试
            # 模拟的是两轮都"跑完了一整套章程"的正常链式，需要 monotonic
            # 每次调用都前进 ≥60s，否则会被新判据误判成夭折。
            monotonic=itertools.count(0, 100).__next__,
        )
        assert len(calls) == 2, "第一轮退出时信号仍在，必须链式再起第二轮，不能丢"

    def test_单次退出无新信号不重复起会话(self, tmp_path):
        write_charter(tmp_path)
        calls = []

        def popen(argv, **kwargs):
            proc = FakeProc(pid=100 + len(calls))
            calls.append(proc)
            return proc

        pd.dispatch_headless_patrol(
            tmp_path, now=NOW, popen=popen, pid_alive=lambda pid: False,
            run_in_thread=lambda fn: fn(),
        )
        assert len(calls) == 1, "退出时信号已空，不应再起第二轮"

    def test_watcher读信号失败按无信号处理不误起(self, tmp_path, monkeypatch):
        write_charter(tmp_path)
        calls = []

        def popen(argv, **kwargs):
            proc = FakeProc(pid=100 + len(calls))
            calls.append(proc)
            return proc

        def boom_read_signal(repo_root):
            raise RuntimeError("信号文件读取本身挂了")

        monkeypatch.setattr(patrol_signal, "read_signal", boom_read_signal)
        pd.dispatch_headless_patrol(
            tmp_path, now=NOW, popen=popen, pid_alive=lambda pid: False,
            run_in_thread=lambda fn: fn(),
        )
        assert len(calls) == 1, "复查信号本身异常不得误判为有信号、误起第二轮"

    def test_watcher挂起失败不影响已起活的判定(self, tmp_path):
        write_charter(tmp_path)

        def boom_thread(fn):
            raise RuntimeError("挂后台线程失败")

        result = pd.dispatch_headless_patrol(
            tmp_path, now=NOW, popen=lambda *a, **k: FakeProc(pid=1),
            pid_alive=lambda pid: False, run_in_thread=boom_thread,
        )
        assert result.action == pd.ACTION_STARTED

    def test_退出码非零判夭折且不重试因无信号(self, tmp_path):
        write_charter(tmp_path)

        class FailProc(FakeProc):
            def wait(self):
                return 1  # 非零退出码

        audit = FakeAudit()
        pd.dispatch_headless_patrol(
            tmp_path, now=NOW, audit=audit,
            popen=lambda *a, **k: FailProc(pid=1), pid_alive=lambda pid: False,
            run_in_thread=lambda fn: fn(),
        )
        assert "patrol_headless_dispatch_child_failed" in audit.actions()
        state = pd.load_failure_state(resolve_patrol_dispatch_failure_state_path(tmp_path))
        assert state["consecutive_failures"] == 1

    def test_秒退且信号未消费判夭折并按退避重试(self, tmp_path, monkeypatch):
        write_charter(tmp_path)
        calls = []
        slept = []

        def popen(argv, **kwargs):
            proc = FakeProc(pid=100 + len(calls))
            calls.append(proc)
            return proc

        # 每次 monotonic() 只前进 1 秒——远小于 60s 阈值，模拟"秒退"；
        # 信号在 dispatch 之前就已挂着且从未被任何一轮消费，天然满足
        # "存活 <60s 且信号未消费"。
        pd.patrol_signal.raise_signal(tmp_path, letter_number="财务部#1", archived_filename="x.md", now=NOW)
        pd.dispatch_headless_patrol(
            tmp_path, now=NOW, popen=popen, pid_alive=lambda pid: False,
            run_in_thread=lambda fn: fn(),
            monotonic=itertools.count(0, 1).__next__,
            sleep=lambda seconds: slept.append(seconds),
        )
        assert len(calls) == pd.FAILURE_ALERT_THRESHOLD, "连续夭折应按阈值重试，触顶即停"
        assert slept == [60.0, 120.0], "退避秒数应为 60*2**(n-1)，第 3 次触顶不再重试、不再退避"

    def test_连续夭折达阈值即停止链式并告警(self, tmp_path):
        write_charter(tmp_path)
        pd.patrol_signal.raise_signal(tmp_path, letter_number="财务部#1", archived_filename="x.md", now=NOW)
        audit = FakeAudit()
        alerts = []

        def popen(argv, **kwargs):
            return FakeProc(pid=1)

        pd.dispatch_headless_patrol(
            tmp_path, now=NOW, audit=audit, popen=popen, pid_alive=lambda pid: False,
            run_in_thread=lambda fn: fn(),
            monotonic=itertools.count(0, 1).__next__,
            sleep=lambda seconds: None,
            alert_send=alerts.append,
        )
        assert audit.actions().count("patrol_headless_dispatch_chain_halted") == 1
        assert len(alerts) == 1
        assert "连续 3 次夭折" in alerts[0]
        # 停摆后信号必须原样留着——不得被本模块消费。
        snapshot = pd.patrol_signal.read_signal(tmp_path)
        assert snapshot.present

    def test_失败计数在成功一轮后清零(self, tmp_path):
        write_charter(tmp_path)
        from aibot_service.repo_paths import resolve_patrol_dispatch_failure_state_path

        state_path = resolve_patrol_dispatch_failure_state_path(tmp_path)
        pd.save_failure_state(state_path, {"consecutive_failures": 2})

        result = pd.dispatch_headless_patrol(
            tmp_path, now=NOW, popen=lambda *a, **k: FakeProc(pid=1),
            pid_alive=lambda pid: False, run_in_thread=lambda fn: fn(),
            monotonic=itertools.count(0, 100).__next__,  # 模拟跑完一整套章程
        )
        assert result.action == pd.ACTION_STARTED
        assert pd.load_failure_state(state_path).get("consecutive_failures", 0) == 0

    def test_失败计数跨进程重启持久化(self, tmp_path):
        """队列 #416 ⑸bis③：不能只存内存——本函数每次调用都重新从磁盘
        读状态，模拟服务重启后计数不清零。"""
        write_charter(tmp_path)
        from aibot_service.repo_paths import resolve_patrol_dispatch_failure_state_path

        state_path = resolve_patrol_dispatch_failure_state_path(tmp_path)
        pd.save_failure_state(state_path, {"consecutive_failures": 2})
        pd.patrol_signal.raise_signal(tmp_path, letter_number="财务部#1", archived_filename="x.md", now=NOW)

        class FailProc(FakeProc):
            def wait(self):
                return 1

        alerts = []
        pd.dispatch_headless_patrol(
            tmp_path, now=NOW, popen=lambda *a, **k: FailProc(pid=1),
            pid_alive=lambda pid: False, run_in_thread=lambda fn: fn(),
            sleep=lambda seconds: None, alert_send=alerts.append,
        )
        # 已有 2 次历史失败，本次是第 3 次 —— 应直接触顶停摆，不再重试。
        assert len(alerts) == 1
        assert pd.load_failure_state(state_path)["consecutive_failures"] == 3

    def test_默认watcher走真实后台线程不阻塞主流程(self, tmp_path):
        write_charter(tmp_path)
        import time

        class SlowWaitProc(FakeProc):
            def wait(self):
                time.sleep(0.3)
                return 0

        start = time.monotonic()
        result = pd.dispatch_headless_patrol(
            tmp_path, now=NOW, popen=lambda *a, **k: SlowWaitProc(pid=321),
            pid_alive=lambda pid: False,
        )
        elapsed = time.monotonic() - start
        assert result.action == pd.ACTION_STARTED
        assert elapsed < 0.2, "默认 run_in_thread 必须是真实后台线程，不得阻塞主调用"
