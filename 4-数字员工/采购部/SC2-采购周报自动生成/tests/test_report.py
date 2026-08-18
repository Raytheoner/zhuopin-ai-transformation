"""组装层单测（spec: sc2-weekly-report）。对应 tasks 5.1-5.6。"""
from __future__ import annotations

import json
from datetime import date

import pytest

from sc2 import config
from sc2.report import (
    build_report,
    load_snapshot,
    render_text,
    save_snapshot,
    snapshot_to_report,
)
from sc2.sources import MockFeed
from sc2.windows import build_windows

BASE = date(2026, 8, 19)


@pytest.fixture(autouse=True)
def _isolated_reports(tmp_path, monkeypatch):
    """把生成物重定向到 tmp，避免污染场景 reports/。"""
    monkeypatch.setenv("SC2_REPORTS_DIR", str(tmp_path))
    yield


@pytest.fixture()
def report():
    ws = build_windows(BASE)
    return build_report(MockFeed().fetch(ws), ws)


# ── 5.1/5.2 三窗口并列 ──────────────────────────────────────────────────────

def test_每个指标同时给出本周值与周环比与月同比(report):
    assert report.metrics
    for m in report.metrics:
        assert hasattr(m, "current") and hasattr(m, "previous") and hasattr(m, "month_ago")


def test_三窗口在同一份周报内而非拆成多份(report):
    text = render_text(report)
    assert "上周" in text and "上月同期" in text


def test_历史窗口缺失时明示无可比基准而非省略该列():
    """spec 场景：不得省略该列使读者以为不存在此对比维度。"""
    ws = build_windows(BASE)
    ds = MockFeed().fetch(ws)
    # 造一个只有本周数据的集合
    only_current = type(ds)(
        order_lines=tuple(l for l in ds.order_lines if ws.current.contains(l.order_date)),
        receipts=tuple(r for r in ds.receipts
                       if ws.current.contains(r.receipt_date)),
        mode=ds.mode, fetched_at=ds.fetched_at,
        range_start=ds.range_start, range_end=ds.range_end)
    text = render_text(build_report(only_current, ws))
    assert "无可比基准" in text


def test_无数据指标显示为无数据而非零():
    ws = build_windows(BASE)
    ds = MockFeed().fetch(ws)
    empty = type(ds)(order_lines=(), receipts=(), mode="mock",
                     fetched_at=ds.fetched_at)
    text = render_text(build_report(empty, ws))
    assert "无数据" in text
    assert "0.0%" not in text or "无数据" in text


# ── 5.3 可追溯标注 ──────────────────────────────────────────────────────────

def test_周报标明基准日期与三窗口起止与取数时刻(report):
    text = render_text(report)
    assert report.base_date.isoformat() in text
    assert report.window_text["current"] in text
    assert report.window_text["previous"] in text
    assert report.window_text["month_ago"] in text
    assert report.fetched_at in text


def test_周报标明数据源(report):
    text = render_text(report)
    assert "数据源" in text
    for note in report.source_notes.values():
        assert note[:10] in text


def test_期次为ISO周标签(report):
    assert report.period == "2026-W34"


# ── 5.4/5.5 快照 ────────────────────────────────────────────────────────────

def test_快照含指标值与口径假设与阈值与基准日期(report):
    path = save_snapshot(report)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["period"] == "2026-W34"
    assert data["base_date"] == BASE.isoformat()
    assert data["thresholds"]
    assert data["metrics"]
    assert any(m["current"]["caveat"] for m in data["metrics"])


def test_依快照重渲染与原期一致(report):
    save_snapshot(report)
    restored = snapshot_to_report(load_snapshot(report.period))
    assert render_text(restored) == render_text(report)


def test_快照落在reports目录下(report, tmp_path):
    path = save_snapshot(report)
    assert path.parent == tmp_path
    assert path.name == "sc2_weekly_2026-W34.json"


def test_口径变更后历史期不被追溯改写(report):
    """spec 场景：历史期按其快照记录的当期口径呈现。"""
    save_snapshot(report)
    original = render_text(snapshot_to_report(load_snapshot(report.period)))

    # 模拟口径定版后重新生成——新一期用 caliber_confirmed=True，标注消失
    ws = build_windows(BASE)
    new_report = build_report(MockFeed().fetch(ws), ws, caliber_confirmed=True)
    assert "口径待确认" not in render_text(new_report)

    # 但历史快照重渲染仍带当期口径标注，未被追改
    assert render_text(snapshot_to_report(load_snapshot(report.period))) == original
    assert "口径待确认" in original


def test_快照不存在时读取报错而非静默返回空():
    with pytest.raises(FileNotFoundError):
        load_snapshot("2019-W01")


# ── 5.6 生成物一律落 reports/ ───────────────────────────────────────────────

def test_三类生成物路径均在reports下(tmp_path):
    for p in (config.snapshot_path("2026-W34"), config.publish_state_path(),
              config.audit_path()):
        assert p.parent == tmp_path, f"{p} 未落在 reports/ 下"


def test_reports目录被gitignore覆盖():
    """伴生文件覆盖核实（队列 #328②）——用真实 git check-ignore，不靠推断。"""
    import subprocess

    rel = ("4-数字员工/采购部/SC2-采购周报自动生成/reports/"
           "sc2_weekly_2026-W34.json")
    repo_root = config.SCENE_ROOT.parent.parent.parent
    r = subprocess.run(["git", "check-ignore", "-v", rel],
                       cwd=repo_root, capture_output=True, text=True)
    assert r.returncode == 0, f"生成物未被 gitignore 覆盖：{r.stdout}{r.stderr}"
    assert "**/reports/" in r.stdout


def test_异常项可从周报直接取出(report):
    assert isinstance(report.anomalies, tuple)
    for m in report.anomalies:
        assert m.anomaly


# —— 本周窗口未走完的显式声明（2026-08-18 首次部署实测发现）——


def test_周中生成时显式声明本周窗口未走完():
    """🔴 基准日落在周中时，本周只过了 N/7 天而上周/上月同期都是完整 7 天，
    「量」类指标的环比同比会系统性偏低——首次部署当天 21 个指标里 16 个因此
    被打 🔴。那是结构性假象，任何阈值调整都修不掉，故必须显式声明。"""
    from datetime import date

    from sc2.report import build_report, render_text
    from sc2.sources import build_feed
    from sc2.windows import build_windows

    base = date(2026, 8, 18)          # 周二 ⇒ 2/7 天
    windows = build_windows(base)
    text = render_text(build_report(build_feed("mock").fetch(windows), windows))
    assert "本周窗口尚未走完" in text
    assert "2/7 天" in text


def test_完整周生成时不出现该声明():
    """周报按正常节奏（周日/周一出完整周）运行时本行不出现，不构成日常噪音。"""
    from datetime import date

    from sc2.report import build_report, render_text
    from sc2.sources import build_feed
    from sc2.windows import build_windows

    base = date(2026, 8, 23)          # 周日 ⇒ 7/7 天，窗口已走完
    windows = build_windows(base)
    text = render_text(build_report(build_feed("mock").fetch(windows), windows))
    assert "本周窗口尚未走完" not in text
