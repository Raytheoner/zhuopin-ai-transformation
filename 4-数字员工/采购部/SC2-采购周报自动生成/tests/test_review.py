"""确认层单测（spec: sc2-anomaly-review）。对应 tasks 6.1-6.5。

这道门是 SC2 保持 **L3**（AI 生成、人确认后发布）而非 L4 全自动的唯一结构性保证。
下面每条测试都在守它的一个缺口。
"""
from __future__ import annotations

import json
from datetime import date

import pytest

from sc2 import config
from sc2.models import Metric, MetricValue, WeeklyReport
from sc2.report import build_report
from sc2.review import (
    PublishState,
    ReviewStore,
    UnconfirmedError,
    confirm,
    ensure_publishable,
    status_of,
)
from sc2.sources import MockFeed
from sc2.windows import build_windows

BASE = date(2026, 8, 19)


@pytest.fixture(autouse=True)
def _isolated_reports(tmp_path, monkeypatch):
    monkeypatch.setenv("SC2_REPORTS_DIR", str(tmp_path))
    yield


@pytest.fixture()
def report():
    ws = build_windows(BASE)
    return build_report(MockFeed().fetch(ws), ws)


@pytest.fixture()
def store():
    return ReviewStore()


# ── 6.1 未确认不得推送 ──────────────────────────────────────────────────────

def test_生成后默认待确认(report, store):
    store.register(report)
    assert status_of(store, report.period) == PublishState.PENDING


def test_未确认时推送前置检查拒绝(report, store):
    store.register(report)
    with pytest.raises(UnconfirmedError):
        ensure_publishable(store, report.period)


def test_确认后方可推送(report, store):
    store.register(report)
    confirm(store, report.period, confirmed_by="姚祖怡", snapshot_id="snap-1")
    ensure_publishable(store, report.period)      # 不抛即通过
    assert status_of(store, report.period) == PublishState.CONFIRMED


def test_未注册的期次不得推送(store):
    with pytest.raises(UnconfirmedError):
        ensure_publishable(store, "2026-W99")


# ── 6.2 超时不得自动确认 ────────────────────────────────────────────────────

def test_确认接口不含任何超时自动确认路径():
    """spec：MUST NOT 自动转为已确认。

    以签名反证——`confirm` 强制要求 `confirmed_by`，且 `ReviewStore` 上不存在
    任何 auto/expire 类方法。没有那条路径，就没有「放着放着就发出去了」。
    """
    import inspect

    sig = inspect.signature(confirm)
    assert sig.parameters["confirmed_by"].default is inspect.Parameter.empty

    names = [n for n in dir(ReviewStore) if not n.startswith("_")]
    for banned in ("auto_confirm", "expire", "confirm_if_stale", "tick"):
        assert banned not in names


def test_确认人不得为空(report, store):
    store.register(report)
    with pytest.raises(ValueError):
        confirm(store, report.period, confirmed_by="   ", snapshot_id="s")


# ── 6.3 异常不阻断确认，但判断须被记录 ──────────────────────────────────────

def test_带异常仍可确认且异常列表被记录(report, store):
    anomalous = WeeklyReport(
        period=report.period, base_date=report.base_date,
        metrics=(Metric(key="k1", name="下单行数", group="下单",
                        current=MetricValue(10.0), previous=MetricValue(1.0),
                        month_ago=MetricValue(1.0), anomaly=True),),
        window_text=report.window_text, mode=report.mode,
        fetched_at=report.fetched_at, thresholds=report.thresholds)
    store.register(anomalous)
    rec = confirm(store, anomalous.period, confirmed_by="姚祖怡", snapshot_id="s1")
    assert rec["anomalies"] == ["k1"]
    ensure_publishable(store, anomalous.period)


def test_无异常正常确认(report, store):
    store.register(report)
    rec = confirm(store, report.period, confirmed_by="姚祖怡", snapshot_id="s1")
    assert isinstance(rec["anomalies"], list)


# ── 6.4 确认写审计 ──────────────────────────────────────────────────────────

def test_确认留痕五项齐全(report, store):
    store.register(report)
    confirm(store, report.period, confirmed_by="姚祖怡", snapshot_id="snap-1")
    events = [json.loads(l) for l in
              config.audit_path().read_text(encoding="utf-8").splitlines() if l.strip()]
    assert events
    ev = events[-1]
    assert ev["scenario"] == "SC2"
    assert ev["action"] == "weekly_report_publish_confirm"
    assert ev["evaluator"] == "姚祖怡"                 # ① 确认人
    assert ev["timestamp"]                              # ② 确认时刻
    assert ev["decision"]["period"] == report.period    # ③ 期次
    assert ev["decision"]["snapshot_id"] == "snap-1"    # ④ 快照标识
    assert "anomalies" in ev["decision"]                # ⑤ 异常列表


def test_审计自动化档位标为L3(report, store):
    store.register(report)
    confirm(store, report.period, confirmed_by="姚祖怡", snapshot_id="s")
    ev = json.loads(config.audit_path().read_text(encoding="utf-8").splitlines()[-1])
    assert ev["automation_level"] == "L3"


def test_重复确认各自留痕且后者不覆盖前者(report, store):
    store.register(report)
    confirm(store, report.period, confirmed_by="姚祖怡", snapshot_id="s1")
    store.register(report)      # 重新生成同期
    confirm(store, report.period, confirmed_by="孙涛", snapshot_id="s2")
    lines = [l for l in config.audit_path().read_text(encoding="utf-8").splitlines()
             if l.strip()]
    evs = [json.loads(l) for l in lines]
    confirms = [e for e in evs if e["action"] == "weekly_report_publish_confirm"]
    assert len(confirms) == 2
    assert confirms[0]["evaluator"] == "姚祖怡"
    assert confirms[1]["evaluator"] == "孙涛"


def _with_changed_metrics(report: WeeklyReport) -> WeeklyReport:
    """同期次但指标值不同的一份周报（模拟重新取数后数字变了）。"""
    changed = tuple(
        Metric(key=m.key, name=m.name, group=m.group,
               current=MetricValue(999.0, m.current.unit, m.current.caveat),
               previous=m.previous, month_ago=m.month_ago,
               anomaly=m.anomaly, threshold_unconfirmed=m.threshold_unconfirmed)
        for m in report.metrics)
    return WeeklyReport(
        period=report.period, base_date=report.base_date, metrics=changed,
        window_text=report.window_text, mode=report.mode,
        fetched_at=report.fetched_at, thresholds=report.thresholds)


def test_内容变了会把已确认退回待确认(report, store):
    """内容变了，先前那次确认就不再适用于新内容——否则等于用旧签认背书新数字
    （同 #228「通知已送达而生产未更新」那族教训的同构形态）。"""
    store.register(report)
    confirm(store, report.period, confirmed_by="姚祖怡", snapshot_id="s1")
    store.register(_with_changed_metrics(report))
    assert status_of(store, report.period) == PublishState.PENDING
    with pytest.raises(UnconfirmedError):
        ensure_publishable(store, report.period)


def test_同内容重复生成不反复要求确认(report, store):
    """反向：内容没变就不该把人已经签过的字作废，否则确认会变成噪音。"""
    store.register(report)
    confirm(store, report.period, confirmed_by="姚祖怡", snapshot_id="s1")
    store.register(report)
    assert status_of(store, report.period) == PublishState.CONFIRMED
    ensure_publishable(store, report.period)


def test_内容变了也会清掉已推送标记(report, store):
    """否则新数字会因为「已推送过」而永远发不出去。"""
    store.register(report)
    confirm(store, report.period, confirmed_by="姚祖怡", snapshot_id="s1")
    assert store.mark_pushed(report.period) is True
    store.register(_with_changed_metrics(report))
    confirm(store, report.period, confirmed_by="姚祖怡", snapshot_id="s2")
    assert store.mark_pushed(report.period) is True


# ── 6.5 跨进程持久化 ────────────────────────────────────────────────────────

def test_确认状态落盘且重启后保持(report, store):
    store.register(report)
    confirm(store, report.period, confirmed_by="姚祖怡", snapshot_id="s1")
    fresh = ReviewStore()                       # 模拟服务重启：全新实例重新读盘
    assert status_of(fresh, report.period) == PublishState.CONFIRMED
    ensure_publishable(fresh, report.period)


def test_确认状态不仅存于进程内存(report, store):
    store.register(report)
    confirm(store, report.period, confirmed_by="姚祖怡", snapshot_id="s1")
    assert config.publish_state_path().exists()
    data = json.loads(config.publish_state_path().read_text(encoding="utf-8"))
    assert report.period in data


def test_重启后不重复推送(report, store):
    store.register(report)
    confirm(store, report.period, confirmed_by="姚祖怡", snapshot_id="s1")
    assert store.mark_pushed(report.period) is True
    fresh = ReviewStore()
    assert fresh.mark_pushed(report.period) is False, "重启后不得重复推送"


def test_状态文件落在reports目录下(report, store, tmp_path):
    store.register(report)
    confirm(store, report.period, confirmed_by="姚祖怡", snapshot_id="s1")
    assert config.publish_state_path().parent == tmp_path
