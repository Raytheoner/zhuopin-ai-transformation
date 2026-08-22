"""组装层 —— 指标集 → 周报 + 快照读写（spec: sc2-weekly-report）。

**快照为什么必须完整到能脱离原始数据重渲染**：价值指标里那条「口径一致性」
（同一指标在连续 4 期周报中算法定义不变、可复算）的唯一证据就是快照。若快照
只存数值不存口径与阈值，日后口径一改，历史期就再也说不清当时算的是什么。

对应地，**历史期不得被新口径追溯改写**——重渲染历史快照必须还原当期的口径标注。
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from . import config
from .metrics import (
    ANOMALY_LABEL,
    DEFAULT_THRESHOLDS,
    THRESHOLDS_CONFIRMED_BY,
    compute_metrics,
    metric_groups,
)
from .models import FrozenDataset, Metric, MetricValue, WeeklyReport
from .windows import WindowSet, build_windows

#: 无数据 / 无可比基准的统一呈现文案。**不用 0% 代替**（spec sc2-metric-engine）。
NO_DATA_TEXT = "无数据"
NO_BASE_TEXT = "无可比基准"


def build_report(dataset: FrozenDataset, windows: WindowSet, *,
                 thresholds: dict[str, float] | None = None,
                 thresholds_confirmed: bool = True,
                 thresholds_confirmed_by: str = THRESHOLDS_CONFIRMED_BY,
                 caliber_confirmed: bool = False) -> WeeklyReport:
    """组装一期周报。

    🔴 `thresholds_confirmed` 缺省为 **True**（2026-08-22 起）——±400% 已由姚祖怡
    2026-08-21 判例批改回件显式签认。**签认来源随 `thresholds_confirmed_by` 一并
    落进快照**：只翻一个布尔位而不记谁签的，日后说不清这个数是哪来的。
    调用方若传入自定义阈值而未同时给出签认来源，须自行把 `thresholds_confirmed`
    置回 False —— 未经签认的阈值必须带"未经确认"标注（IATF 判据类）。
    """
    th = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        th.update(thresholds)
    metrics = compute_metrics(dataset, windows, thresholds=th,
                              thresholds_confirmed=thresholds_confirmed,
                              caliber_confirmed=caliber_confirmed)
    return WeeklyReport(
        period=windows.current.label(),
        iso_period=windows.current.iso_label(),
        base_date=windows.base or windows.current.start,
        metrics=metrics,
        window_text={
            "current": windows.current.label_text(),
            "previous": windows.previous.label_text(),
            "month_ago": windows.month_ago.label_text(),
        },
        mode=dataset.mode,
        fetched_at=dataset.fetched_at,
        source_notes=dict(dataset.source_notes),
        thresholds=th,
        thresholds_confirmed=thresholds_confirmed,
        thresholds_confirmed_by=thresholds_confirmed_by if thresholds_confirmed else "",
    )


# ── 呈现 ────────────────────────────────────────────────────────────────────

def _fmt_value(v: MetricValue) -> str:
    if not v.has_data:
        return NO_DATA_TEXT
    if v.unit == "%":
        return f"{v.value * 100:.1f}%"
    if abs(v.value - round(v.value)) < 1e-9:
        return f"{int(round(v.value))}{v.unit}"
    return f"{v.value:.2f}{v.unit}"


def _fmt_delta(d: float | None) -> str:
    """环比。**None ＝ 无可比基准，不是 0%**。"""
    if d is None:
        return NO_BASE_TEXT
    return f"{d * 100:+.1f}%"


def _incomplete_week_note(base: date) -> str | None:
    """本周窗口尚未走完时的显式声明。

    🔴 **为什么非说不可**（2026-08-18 首次部署当天实测发现）：三窗口同为一个自然周
    才使量纲可直接比较（D16-R），但**基准日落在周中时，本周只过了 N/7 天，而上周与
    上月同期都是完整 7 天**——所有「量」类指标的环比/同比于是全线巨幅下降，当天
    21 个指标里 16 个被打上 🔴。那不是业务波动，是把半周和整周放在一起比。
    没有任何阈值调整能修掉它，因为它不是阈值问题。

    故照 spec「不可算不呈现」的同一精神**显式声明**：宁可读者看到一句啰嗦的提示，
    也不能让他把结构性假象当成真实的采购塌方。**周报按完整周（周一出上一周）运行时
    本行不出现**，不构成日常噪音。
    """
    elapsed = base.weekday() + 1          # 周一=1 … 周日=7
    if elapsed >= 7:
        return None
    return (f"- 🔴 **本周窗口尚未走完**：仅含 {elapsed}/7 天，而上周与上月同期均为完整 7 天"
            f"⇒ **「量」类指标的周环比/月同比会系统性偏低，不是业务波动**。"
            f"完整周的可比数请在本周结束后重算。")


def render_text(report: WeeklyReport) -> str:
    """纯文本周报——企微推送与快照回归都用它，保证两处呈现同源。"""
    lines: list[str] = [
        f"# 采购周报 {report.period}",
        "",
        f"- 期次口径：**{report.period}（采购口径周序）**"
        + (f"｜ISO 周号对照：{report.iso_period}" if report.iso_period else ""),
        f"- 基准日期：{report.base_date.isoformat()}",
        f"- 本周：{report.window_text['current']}",
        f"- 上周：{report.window_text['previous']}",
        f"- 上月同期：{report.window_text['month_ago']}",
        f"- 取数模式：{report.mode}｜取数时刻：{report.fetched_at}",
    ]
    if report.source_notes:
        lines.append("- 数据源：")
        for k, v in report.source_notes.items():
            lines.append(f"  - {k}：{v}")
    if report.thresholds_confirmed:
        lines.append(
            f"- {ANOMALY_LABEL}阈值：周环比 ±"
            f"{report.thresholds.get('wow_abs_pct', 0) * 100:.0f}%"
            + (f"｜签认：{report.thresholds_confirmed_by}"
               if report.thresholds_confirmed_by else "")
            + "。🔴 **仅作工作量参考，不作异常告警，不触发任何自动推送**")
    else:
        lines.append("- ⚠️ 波动阈值**未经专员确认**（判据类，须显式签认后方可定版）")
    incomplete = _incomplete_week_note(report.base_date)
    if incomplete:
        lines.append(incomplete)
    lines.append("")

    for group, items in metric_groups(report.metrics).items():
        lines.append(f"## {group}")
        lines.append("")
        lines.append("| 指标 | 本周 | 周环比 | 月同比 | 备注 |")
        lines.append("|---|---|---|---|---|")
        for m in items:
            # 🔶 而非 🔴：这是工作量波动参考，不是异常告警（姚祖怡限定用途）。
            flag = "🔶 " if m.anomaly else ""
            note = m.current.caveat or ""
            if m.anomaly:
                note = (note + "；" if note else "") + (
                    "阈值未经确认" if m.threshold_unconfirmed else ANOMALY_LABEL)
            lines.append(
                f"| {flag}{m.name} | {_fmt_value(m.current)} | "
                f"{_fmt_delta(m.week_over_week)} | {_fmt_delta(m.month_over_month)} | "
                f"{note} |")
        lines.append("")
    return "\n".join(lines)


# ── 快照 ────────────────────────────────────────────────────────────────────

def _value_to_dict(v: MetricValue) -> dict[str, Any]:
    return {"value": v.value, "unit": v.unit, "caveat": v.caveat}


def _value_from_dict(d: dict[str, Any]) -> MetricValue:
    return MetricValue(value=d["value"], unit=d.get("unit", ""),
                       caveat=d.get("caveat", ""))


def report_to_dict(report: WeeklyReport) -> dict[str, Any]:
    return {
        "period": report.period,
        "iso_period": report.iso_period,
        "base_date": report.base_date.isoformat(),
        "mode": report.mode,
        "fetched_at": report.fetched_at,
        "window_text": report.window_text,
        "source_notes": report.source_notes,
        "thresholds": report.thresholds,
        "thresholds_confirmed": report.thresholds_confirmed,
        "thresholds_confirmed_by": report.thresholds_confirmed_by,
        "metrics": [
            {
                "key": m.key, "name": m.name, "group": m.group,
                "current": _value_to_dict(m.current),
                "previous": _value_to_dict(m.previous),
                "month_ago": _value_to_dict(m.month_ago),
                "anomaly": m.anomaly,
                "threshold_unconfirmed": m.threshold_unconfirmed,
            }
            for m in report.metrics
        ],
    }


def snapshot_to_report(data: dict[str, Any]) -> WeeklyReport:
    """快照 → 周报。**还原当期口径与阈值**，不套用当下的口径。"""
    return WeeklyReport(
        period=data["period"],
        iso_period=data.get("iso_period", ""),
        base_date=date.fromisoformat(data["base_date"]),
        metrics=tuple(
            Metric(key=m["key"], name=m["name"], group=m["group"],
                   current=_value_from_dict(m["current"]),
                   previous=_value_from_dict(m["previous"]),
                   month_ago=_value_from_dict(m["month_ago"]),
                   anomaly=m.get("anomaly", False),
                   threshold_unconfirmed=m.get("threshold_unconfirmed", False))
            for m in data["metrics"]
        ),
        window_text=data.get("window_text", {}),
        mode=data.get("mode", ""),
        fetched_at=data.get("fetched_at", ""),
        source_notes=data.get("source_notes", {}),
        thresholds=data.get("thresholds", {}),
        thresholds_confirmed=data.get("thresholds_confirmed", False),
        thresholds_confirmed_by=data.get("thresholds_confirmed_by", ""),
    )


def save_snapshot(report: WeeklyReport) -> Path:
    """落一期快照到 `reports/`。"""
    path = config.snapshot_path(report.period)
    path.write_text(
        json.dumps(report_to_dict(report), ensure_ascii=False, indent=2),
        encoding="utf-8")
    return path


def load_snapshot(period: str) -> dict[str, Any]:
    """读一期快照。**不存在即上抛**，不静默返回空——静默会让历史期悄悄变成空报表。"""
    path = config.snapshot_path(period)
    if not path.exists():
        raise FileNotFoundError(f"未找到 {period} 期快照：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def generate(base: date, *, mode: str = "mock", **kw) -> WeeklyReport:
    """取数 → 组装 一步到位（服务入口与 CLI 用）。"""
    from .sources import build_feed

    windows = build_windows(base)
    return build_report(build_feed(mode).fetch(windows), windows, **kw)
