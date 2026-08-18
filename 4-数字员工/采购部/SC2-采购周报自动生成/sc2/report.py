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
from .metrics import DEFAULT_THRESHOLDS, compute_metrics, metric_groups
from .models import FrozenDataset, Metric, MetricValue, WeeklyReport
from .windows import WindowSet, build_windows

#: 无数据 / 无可比基准的统一呈现文案。**不用 0% 代替**（spec sc2-metric-engine）。
NO_DATA_TEXT = "无数据"
NO_BASE_TEXT = "无可比基准"


def build_report(dataset: FrozenDataset, windows: WindowSet, *,
                 thresholds: dict[str, float] | None = None,
                 thresholds_confirmed: bool = False,
                 caliber_confirmed: bool = False) -> WeeklyReport:
    """组装一期周报。"""
    th = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        th.update(thresholds)
    metrics = compute_metrics(dataset, windows, thresholds=th,
                              thresholds_confirmed=thresholds_confirmed,
                              caliber_confirmed=caliber_confirmed)
    return WeeklyReport(
        period=windows.current.iso_label(),
        base_date=windows.base or windows.current.start,
        metrics=metrics,
        window_text={
            "current": windows.current.as_text(),
            "previous": windows.previous.as_text(),
            "month_ago": windows.month_ago.as_text(),
        },
        mode=dataset.mode,
        fetched_at=dataset.fetched_at,
        source_notes=dict(dataset.source_notes),
        thresholds=th,
        thresholds_confirmed=thresholds_confirmed,
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


def render_text(report: WeeklyReport) -> str:
    """纯文本周报——企微推送与快照回归都用它，保证两处呈现同源。"""
    lines: list[str] = [
        f"# 采购周报 {report.period}",
        "",
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
    if not report.thresholds_confirmed:
        lines.append("- ⚠️ 异常阈值**未经专员确认**（判据类，须显式签认后方可定版）")
    lines.append("")

    for group, items in metric_groups(report.metrics).items():
        lines.append(f"## {group}")
        lines.append("")
        lines.append("| 指标 | 本周 | 周环比 | 月同比 | 备注 |")
        lines.append("|---|---|---|---|---|")
        for m in items:
            flag = "🔴 " if m.anomaly else ""
            note = m.current.caveat or ""
            if m.anomaly and m.threshold_unconfirmed:
                note = (note + "；" if note else "") + "阈值未经确认"
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
        "base_date": report.base_date.isoformat(),
        "mode": report.mode,
        "fetched_at": report.fetched_at,
        "window_text": report.window_text,
        "source_notes": report.source_notes,
        "thresholds": report.thresholds,
        "thresholds_confirmed": report.thresholds_confirmed,
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
