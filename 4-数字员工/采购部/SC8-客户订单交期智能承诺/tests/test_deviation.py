"""承诺交期偏差监控（C1 / SOP §4.3 · 先写测试）。

覆盖：偏差≤阈值不告警；>阈值告警+留痕+触发重算；恰好=阈值不告警（严格大于）；
最新无法预测(None)视为重大偏差；audit/on_breach 缺省不报错。
"""
from __future__ import annotations

from datetime import date

from sc8.deviation import ACTION_DEVIATION_ALERT, monitor_deviation


def test_within_threshold_no_alert(audit):
    """偏差 ≤ 3 天 → 不告警、不留痕、不触发重算。"""
    calls = []
    res = monitor_deviation(
        date(2026, 7, 10), date(2026, 7, 12),   # 偏差 2 天
        so_id="SO1", customer_name="比亚迪", audit=audit,
        on_breach=lambda r: calls.append(r),
    )
    assert res.breached is False
    assert res.deviation_days == 2
    assert calls == []
    assert audit.query_by(scenario="SC8", action=ACTION_DEVIATION_ALERT) == []


def test_exactly_threshold_no_alert(audit):
    """恰好 = 3 天 → 不告警（严格大于）。"""
    res = monitor_deviation(date(2026, 7, 10), date(2026, 7, 13),
                            so_id="SO1", audit=audit)
    assert res.deviation_days == 3
    assert res.breached is False


def test_over_threshold_alerts_audits_and_recomputes(audit):
    """偏差 > 3 天 → breached、写 delivery_deviation_alert、调 on_breach。"""
    calls = []
    res = monitor_deviation(
        date(2026, 7, 10), date(2026, 7, 16),    # 偏差 6 天
        so_id="SO2", customer_name="理想", audit=audit,
        on_breach=lambda r: calls.append(r.so_id),
    )
    assert res.breached is True and res.requires_recompute is True
    assert res.deviation_days == 6
    assert calls == ["SO2"]                       # 触发重算回调
    recs = audit.query_by(scenario="SC8", action=ACTION_DEVIATION_ALERT)
    assert len(recs) == 1
    assert recs[0]["decision"]["deviation_days"] == 6
    assert recs[0]["decision"]["so_id"] == "SO2"


def test_earlier_than_committed_also_breaches(audit):
    """提前交付偏差也按 abs 计：早 5 天 → 超阈值告警。"""
    res = monitor_deviation(date(2026, 7, 10), date(2026, 7, 5),
                            so_id="SO3", audit=audit)
    assert res.deviation_days == 5
    assert res.breached is True


def test_unpredictable_is_major_deviation(audit):
    """最新无法预测交付日（actual_date=None）→ 视为重大偏差（C1-b）。"""
    res = monitor_deviation(date(2026, 7, 10), None, so_id="SO4", audit=audit)
    assert res.breached is True and res.requires_recompute is True
    assert res.deviation_days is None
    recs = audit.query_by(scenario="SC8", action=ACTION_DEVIATION_ALERT)
    assert recs[0]["decision"]["reason"] == "无法预测交付日"


def test_no_audit_no_callback_does_not_raise():
    """audit=None 且 on_breach=None 且超阈值 → 仅返回结果，不报错。"""
    res = monitor_deviation(date(2026, 7, 10), date(2026, 7, 20), so_id="SO5")
    assert res.breached is True
