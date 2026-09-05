"""队列 §一 #382⑵（2026-09-05，OP-0905-I）：`draft_gap_check.py` 的 `--json`
CLI 层单测——只测这一层没有接错（字段名/退出码/JSON 结构），不重新验证
`find_recent_scenario_commits`/`find_missing_drafts` 的交叉比对逻辑本身
（已在 `test_draft_gap_detection.py` 覆盖）。同 `test_check_patrol_signal_
script.py` 既有的「CLI 层单测」分工。

`--json` 是给 `0-学习与工具/工具-落库sweep.py` 第 11 类常驻告警子进程调用
用的结构化出口；默认文本输出（供人读、供巡逻章程未摘除前继续调用）本次
未改动，此处不重复覆盖。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import draft_gap_check as cli  # noqa: E402


@pytest.fixture()
def repo_root(tmp_path, monkeypatch):
    monkeypatch.setenv("WECOM_AIBOT_REPO_ROOT", str(tmp_path))
    return tmp_path


def _run(monkeypatch, capsys, argv):
    monkeypatch.setattr(sys, "argv", ["draft_gap_check.py", *argv])
    exit_code = 0
    try:
        cli.main()
    except SystemExit as exc:
        exit_code = exc.code or 0
    return exit_code, capsys.readouterr()


def _write_readme(repo_root: Path, rows: str = "") -> None:
    path = repo_root / cli.FOLLOWUP_README_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "## 现有跟进信清单\n\n"
        "| 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |\n"
        "|------|--------|---------|---------|---------|\n"
    )
    path.write_text(header + rows, encoding="utf-8")


class TestJsonMode:
    def test_readme不存在时输出JSON错误且退出码为1(self, repo_root, monkeypatch, capsys):
        code, captured = _run(monkeypatch, capsys, ["--json"])
        assert code == 1
        payload = json.loads(captured.out)
        assert "error" in payload
        # 🔴 --json 分支下 README 不存在也走 stdout JSON，不走 stderr——
        # 与非 --json 分支（[SKIP] 文案打 stderr）刻意区分，见脚本内注释。
        assert captured.err == ""

    def test_零缺口时输出正确结构(self, repo_root, monkeypatch, capsys):
        _write_readme(repo_root)
        code, captured = _run(monkeypatch, capsys, ["--window-days", "14", "--json"])
        assert code == 0
        payload = json.loads(captured.out)
        assert payload == {"window_days": 14, "gaps": []}

    def test_非json模式行为不变(self, repo_root, monkeypatch, capsys):
        """默认文本输出一字未改——本条只做防回归哨兵。"""
        _write_readme(repo_root)
        code, captured = _run(monkeypatch, capsys, ["--window-days", "14"])
        assert code == 0
        assert "待发信盘点（扩展版" in captured.out
        assert not captured.out.strip().startswith("{")
