# -*- coding: utf-8 -*-
"""无头棒收工探针单测。

🔴 **本套的重点是「它真的会响」，不是「它不报错」**——本探针的失败模式
是**静默漏报**（正是它要消灭的那 90 分钟空转）。所以每条「应报」用例都
配一条**变异检验**：把判读逻辑打掉后，断言用例真的转红；恒真的测试比没
有测试更糟（同队列 §一 `#398`「用来发现问题的东西自己坏了」）。
"""

from __future__ import annotations

import datetime as _dt
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location(
    "_probe_under_test", _HERE / "工具-无头棒收工探针.py"
)
probe = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = probe
_SPEC.loader.exec_module(probe)


NOW = _dt.datetime(2026, 9, 10, 18, 0, 0)


def _mkbatch(root: Path, name: str, *, summary: str | None = None,
             log_age_min: int = 1) -> Path:
    d = root / "reports" / "opener-batch" / name
    d.mkdir(parents=True, exist_ok=True)
    log = d / "lane-A1.log"
    log.write_text("[lane:x] start\n", encoding="utf-8")
    ts = (NOW - _dt.timedelta(minutes=log_age_min)).timestamp()
    import os
    os.utime(log, (ts, ts))
    if summary is not None:
        s = d / "summary.txt"
        s.write_text(summary, encoding="utf-8")
        os.utime(s, (ts, ts))
    return d


SUMMARY_OK = """
Lane                 Id Status Minutes
----                 -- ------ -------
549-550-opener-infra A1 OK        12.30
"""

SUMMARY_MIXED = """
Lane                 Id Status      Minutes
----                 -- ------      -------
507-sweep-apply      A1 NO-SENTINEL   43.20
k2-externalize       A1 PARTIAL       13.20
"""


def _state(root: Path) -> dict:
    return json.loads((root / probe.STATE_REL).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 基线化：装上去那一刻不许把历史批喷一遍
# ---------------------------------------------------------------------------

def test_首跑基线化不推送(tmp_path):
    _mkbatch(tmp_path, "20260910-140000", summary=SUMMARY_OK)
    _mkbatch(tmp_path, "20260910-150000", summary=SUMMARY_MIXED)
    r = probe.scan(tmp_path, now=NOW)
    assert r["verdict"] == "BASELINE"
    assert len(r["baseline"]) == 2
    assert r["done"] == [] and r["stalled"] == []


def test_基线化不许埋掉当时正在跑的批(tmp_path):
    """🔴 首版实撞：基线化对所有批一律写 done_notified，**把当时正在跑的
    `OP-0910-R` 当场埋掉**——它收工时永远不会被报出。这正是本探针要消灭
    的那个失败模式，却由本探针自己的安装动作制造。"""
    _mkbatch(tmp_path, "20260910-140000", summary=SUMMARY_OK)      # 已收工
    _mkbatch(tmp_path, "20260910-170523", summary=None, log_age_min=3)  # 在跑
    probe._commit(tmp_path, probe.scan(tmp_path, now=NOW))         # 装探针
    st = _state(tmp_path)["batches"]
    assert "done_notified" in st["20260910-140000"]
    assert "done_notified" not in st["20260910-170523"], "在跑的批被基线埋掉了"
    # 它随后收工 ⇒ 必须报
    _mkbatch(tmp_path, "20260910-170523", summary=SUMMARY_OK, log_age_min=1)
    r = probe.scan(tmp_path, now=NOW)
    assert r["verdict"] == "SIGNAL"
    assert [b["batch"] for b in r["done"]] == ["20260910-170523"]


def test_基线化后同一批不再报(tmp_path):
    _mkbatch(tmp_path, "20260910-140000", summary=SUMMARY_OK)
    r1 = probe.scan(tmp_path, now=NOW)
    probe._commit(tmp_path, r1)
    r2 = probe.scan(tmp_path, now=NOW)
    assert r2["verdict"] == "NO-SIGNAL"


# ---------------------------------------------------------------------------
# 收工：新出的 summary 必须报（这一条是本探针存在的理由）
# ---------------------------------------------------------------------------

def test_新收工批必报_SIGNAL(tmp_path):
    _mkbatch(tmp_path, "20260910-140000", summary=SUMMARY_OK)
    probe._commit(tmp_path, probe.scan(tmp_path, now=NOW))     # 基线化
    _mkbatch(tmp_path, "20260910-170523", summary=SUMMARY_MIXED)  # 新批收工
    r = probe.scan(tmp_path, now=NOW)
    assert r["verdict"] == "SIGNAL"
    assert [b["batch"] for b in r["done"]] == ["20260910-170523"]
    lanes = dict(r["done"][0]["lanes"])
    assert lanes["507-sweep-apply"] == "NO-SENTINEL"
    assert lanes["k2-externalize"] == "PARTIAL"


def test_报过一次就不再重复报(tmp_path):
    probe._commit(tmp_path, probe.scan(tmp_path, now=NOW))
    _mkbatch(tmp_path, "20260910-170523", summary=SUMMARY_OK)
    r1 = probe.scan(tmp_path, now=NOW)
    assert r1["verdict"] == "SIGNAL"
    probe._commit(tmp_path, r1)
    assert probe.scan(tmp_path, now=NOW)["verdict"] == "NO-SIGNAL"


def test_变异_摘掉summary判读则新收工批漏报(tmp_path, monkeypatch):
    """🔴 变异检验：把 `_parse_summary` 之前的 `summary.exists()` 判读
    短路掉（模拟「探针看不见 summary」），断言上面的用例真的会转红——
    防止 `test_新收工批必报_SIGNAL` 是恒真的。"""
    probe._commit(tmp_path, probe.scan(tmp_path, now=NOW))
    _mkbatch(tmp_path, "20260910-170523", summary=SUMMARY_OK)
    real_exists = Path.exists

    def blind(self):
        if self.name == "summary.txt":
            return False
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", blind)
    r = probe.scan(tmp_path, now=NOW)
    assert r["verdict"] != "SIGNAL" or not r["done"], "变异未生效，原用例可能恒真"


# ---------------------------------------------------------------------------
# 停滞：无 summary 且长时间静默 —— 比「收工没人知道」更坏的一种
# ---------------------------------------------------------------------------

def test_长时间静默无summary报停滞(tmp_path):
    probe._commit(tmp_path, probe.scan(tmp_path, now=NOW))
    _mkbatch(tmp_path, "20260910-150000", summary=None, log_age_min=120)
    r = probe.scan(tmp_path, now=NOW, stall_minutes=90)
    assert r["verdict"] == "SIGNAL"
    assert r["stalled"][0]["batch"] == "20260910-150000"


def test_在跑中不报停滞(tmp_path):
    probe._commit(tmp_path, probe.scan(tmp_path, now=NOW))
    _mkbatch(tmp_path, "20260910-175500", summary=None, log_age_min=5)
    r = probe.scan(tmp_path, now=NOW, stall_minutes=90)
    assert r["verdict"] == "NO-SIGNAL"
    assert r["running"][0]["batch"] == "20260910-175500"


def test_变异_停滞阈值调到极大则不再报(tmp_path):
    probe._commit(tmp_path, probe.scan(tmp_path, now=NOW))
    _mkbatch(tmp_path, "20260910-150000", summary=None, log_age_min=120)
    assert probe.scan(tmp_path, now=NOW, stall_minutes=10_000)["verdict"] == "NO-SIGNAL"


# ---------------------------------------------------------------------------
# 边界
# ---------------------------------------------------------------------------

def test_超出回看窗口的老批不吵(tmp_path):
    probe._commit(tmp_path, probe.scan(tmp_path, now=NOW))
    _mkbatch(tmp_path, "20260901-090000", summary=SUMMARY_OK, log_age_min=5)
    assert probe.scan(tmp_path, now=NOW, lookback_hours=24)["verdict"] == "NO-SIGNAL"


def test_非时间戳目录名跳过(tmp_path):
    probe._commit(tmp_path, probe.scan(tmp_path, now=NOW))
    d = tmp_path / "reports" / "opener-batch" / "临时手工目录"
    d.mkdir(parents=True)
    (d / "summary.txt").write_text(SUMMARY_OK, encoding="utf-8")
    assert probe.scan(tmp_path, now=NOW)["verdict"] == "NO-SIGNAL"


def test_状态文件损坏时退回基线化而非静默(tmp_path):
    _mkbatch(tmp_path, "20260910-140000", summary=SUMMARY_OK)
    p = tmp_path / probe.STATE_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{ 这不是 JSON", encoding="utf-8")
    r = probe.scan(tmp_path, now=NOW)
    assert r["verdict"] == "BASELINE"   # 退回基线化，不是当作「已通知过」


def test_summary列宽变化仍能解析(tmp_path):
    """列宽随泳道名长度变化——不得按硬编码列位解析（同 #535）。"""
    wide = """
Lane                                              Id Status Minutes
----                                              -- ------ -------
a-very-long-lane-name-that-shifts-every-column    A1 OK        1.00
"""
    rows = probe._parse_summary(wide)
    assert rows == [("a-very-long-lane-name-that-shifts-every-column", "OK")]


def test_消息正文不含自动触发类措辞(tmp_path):
    """🔴 `UPS5:7` 自身的形态守：本探针推的正文必须**明确交回**，
    不得出现「我盯着」「自动接着做」之类——它推的正是那条纪律。"""
    r = {
        "now": "2026-09-10 18:00:00",
        "done": [{"batch": "20260910-170523", "dir": "reports/opener-batch/20260910-170523",
                  "lanes": [("x", "OK")], "finished_at": "2026-09-10 17:50:00"}],
        "stalled": [],
    }
    msg = probe.format_message(r)
    for bad in ("我盯着", "自动起", "自动接着", "一出来就"):
        assert bad not in msg
    assert "棒已完工" in msg


def test_落款不得写死成定时任务():
    """🔴 2026-09-10 17:36 实撞：自检消息由**手工**跑脚本推出，正文却硬写
    「本条由定时任务 poll-opener-batch 推送」——刚写就已过期的假落款。
    缺省必须是「手工」，反了的代价大得多（会让人以为机器守在跑）。"""
    r = {"now": "t", "done": [{"batch": "b", "dir": "d", "lanes": [("x", "OK")],
                               "finished_at": "t"}], "stalled": []}
    assert "手工运行" in probe.format_message(r)
    assert "定时任务" not in probe.format_message(r)
    assert "定时任务" in probe.format_message(r, probe.INVOKER_SCHEDULED)


def test_主流程默认落款为手工(tmp_path, capsys):
    probe._commit(tmp_path, probe.scan(tmp_path, now=NOW))
    _mkbatch(tmp_path, "20260910-170523", summary=SUMMARY_OK)
    probe.main(["--repo-root", str(tmp_path), "--no-notify"])
    out = capsys.readouterr().out
    assert "手工运行" in out and "定时任务" not in out


def test_主流程带旗标时落款为定时任务(tmp_path, capsys):
    probe._commit(tmp_path, probe.scan(tmp_path, now=NOW))
    _mkbatch(tmp_path, "20260910-170523", summary=SUMMARY_OK)
    probe.main(["--repo-root", str(tmp_path), "--no-notify", "--via-scheduled-task"])
    assert "定时任务" in capsys.readouterr().out


def test_peek是dry_run的别名_不写状态不推送(tmp_path):
    """🔴 2026-09-10 23:17 实撞：本方手工核查带 `--no-notify`，它**照样写状态** ⇒
    波 1 收工那条推送永远不会发。能力其实早就有（`--dry-run`），**错在名字看不出
    「会不会吃掉信号」**，于是选错了开关。`--peek` 就是给这件事一个说得出口的名字。"""
    probe._commit(tmp_path, probe.scan(tmp_path, now=NOW))
    _mkbatch(tmp_path, "20260910-170523", summary=SUMMARY_OK)
    before = (tmp_path / probe.STATE_REL).read_text(encoding="utf-8")
    assert probe.main(["--repo-root", str(tmp_path), "--peek"]) == 0
    assert (tmp_path / probe.STATE_REL).read_text(encoding="utf-8") == before, "peek 写了状态"
    # 状态没被吃掉 ⇒ 下一次照常报得出来
    assert probe.scan(tmp_path, now=NOW)["verdict"] == "SIGNAL"


def test_no_notify必须喊出自己吃掉了信号(tmp_path, capsys):
    """🔴 一个「安静地少做一件事」的开关，必须自己喊出来它少做了什么。"""
    probe._commit(tmp_path, probe.scan(tmp_path, now=NOW))
    _mkbatch(tmp_path, "20260910-170523", summary=SUMMARY_OK)
    probe.main(["--repo-root", str(tmp_path), "--no-notify"])
    err = capsys.readouterr().err
    assert "--no-notify" in err and "未推企微" in err and "1 条信号" in err
    assert "--peek" in err, "警告里必须给出正确的替代开关"


def test_主流程dry_run不写状态(tmp_path):
    _mkbatch(tmp_path, "20260910-140000", summary=SUMMARY_OK)
    rc = probe.main(["--repo-root", str(tmp_path), "--dry-run"])
    assert rc == 0
    assert not (tmp_path / probe.STATE_REL).exists()


def test_主流程写状态且不推送(tmp_path, capsys):
    probe._commit(tmp_path, probe.scan(tmp_path, now=NOW))
    _mkbatch(tmp_path, "20260910-170523", summary=SUMMARY_OK)
    rc = probe.main(["--repo-root", str(tmp_path), "--no-notify"])
    assert rc == 0
    assert "[SIGNAL]" in capsys.readouterr().out
    assert "done_notified" in _state(tmp_path)["batches"]["20260910-170523"]


def test_探针自身异常按SIGNAL报出不静默(tmp_path, monkeypatch, capsys):
    """🔴 fail-open：探针坏了必须可见。"""
    def boom(*a, **k):
        raise RuntimeError("模拟探针内部炸了")
    monkeypatch.setattr(probe, "scan", boom)
    rc = probe.main(["--repo-root", str(tmp_path)])
    assert rc == 0
    assert "[SIGNAL] 探针自身异常" in capsys.readouterr().out


def test_不出现WECOM键名字面量():
    """键名只许在 `工具-泳道看护状态机.py` 里有一份（#492）。"""
    src = (_HERE / "工具-无头棒收工探针.py").read_text(encoding="utf-8")
    assert "WECOM_WEBHOOK_URL" + "_OPS" not in src.replace("WECOM_WEBHOOK_URL_OPS`", "")
