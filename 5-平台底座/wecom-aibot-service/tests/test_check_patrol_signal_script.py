"""队列 #382⑴：探针脚本 CLI 层单测——只测 stdout 文本前缀与 --clear 效果，
`patrol_signal` 自身的读写/累积/fail-open 逻辑已在 test_patrol_signal.py
覆盖，这里只验证 CLI 这一层没有接错。"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import check_patrol_signal as cli  # noqa: E402
from aibot_service import patrol_signal  # noqa: E402


@pytest.fixture()
def repo_root(tmp_path, monkeypatch):
    monkeypatch.setenv("WECOM_AIBOT_REPO_ROOT", str(tmp_path))
    return tmp_path


def _run(monkeypatch, capsys, argv):
    monkeypatch.setattr(sys, "argv", ["check_patrol_signal.py", *argv])
    code = cli.main()
    return code, capsys.readouterr().out


class TestCheck:
    def test_无信号时输出NO_SIGNAL(self, repo_root, monkeypatch, capsys):
        code, out = _run(monkeypatch, capsys, ["--check"])
        assert code == 0
        assert out.startswith("[NO-SIGNAL]")

    def test_不带参数默认等价于check(self, repo_root, monkeypatch, capsys):
        code, out = _run(monkeypatch, capsys, [])
        assert code == 0
        assert out.startswith("[NO-SIGNAL]")

    def test_有信号时输出SIGNAL与详情(self, repo_root, monkeypatch, capsys):
        patrol_signal.raise_signal(
            repo_root, letter_number="财务部#15", archived_filename="a.docx",
        )
        code, out = _run(monkeypatch, capsys, ["--check"])
        assert code == 0
        assert out.startswith("[SIGNAL]")
        assert "财务部#15" in out
        assert "a.docx" in out
        assert "CHECKPOINT=" in out

    def test_信号文件损坏时按有信号处理(self, repo_root, monkeypatch, capsys):
        from aibot_service.repo_paths import resolve_patrol_signal_path

        path = resolve_patrol_signal_path(repo_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("坏掉的 JSON {{{", encoding="utf-8")

        code, out = _run(monkeypatch, capsys, ["--check"])
        assert code == 0
        assert out.startswith("[SIGNAL]")
        assert "fail-open" in out


class TestClear:
    def test_clear消费全部信号(self, repo_root, monkeypatch, capsys):
        patrol_signal.raise_signal(
            repo_root, letter_number="财务部#15", archived_filename="a.docx",
        )
        code, out = _run(monkeypatch, capsys, ["--clear"])
        assert code == 0
        assert out.startswith("[CLEARED] 已消费 1 条信号")
        assert patrol_signal.read_signal(repo_root).present is False

    def test_按checkpoint清空保留扫描期间新到的信号(self, repo_root, monkeypatch, capsys):
        # 🔴 显式给两次到达注入相隔较远的时间戳——信号「at」只精确到秒，
        # 若像生产那样都用真实 wall-clock，两次调用落在同一秒内会让
        # checkpoint 比较（`at > before`）把两条都判为"未晚于"而一并清空，
        # 这正是 checkpoint 机制本身要分辨的场景，测试不能靠运气避开它。
        patrol_signal.raise_signal(
            repo_root, letter_number="财务部#15", archived_filename="a.docx",
            now=datetime(2026, 9, 1, 2, 0, 0, tzinfo=timezone.utc),
        )
        _, check_out = _run(monkeypatch, capsys, ["--check"])
        checkpoint = next(
            line.split("=", 1)[1] for line in check_out.splitlines()
            if line.startswith("CHECKPOINT=")
        )

        # 模拟"探测之后、收工之前"又有一条新回件到达。
        patrol_signal.raise_signal(
            repo_root, letter_number="采购部#19", archived_filename="b.docx",
            now=datetime(2026, 9, 1, 5, 30, 0, tzinfo=timezone.utc),
        )
        code, out = _run(monkeypatch, capsys, ["--clear", "--before", checkpoint])
        assert code == 0
        assert "又有 1 条新到" in out

        remaining = patrol_signal.read_signal(repo_root)
        assert remaining.present is True
        assert remaining.pending[0]["letter_number"] == "采购部#19"

    def test_清空空文件不报错(self, repo_root, monkeypatch, capsys):
        code, out = _run(monkeypatch, capsys, ["--clear"])
        assert code == 0
        assert out.startswith("[CLEARED] 已消费 0 条信号")
