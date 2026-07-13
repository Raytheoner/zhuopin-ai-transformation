"""周期累计供需匹配算法（B2，shortage-baoguan-criteria-v3，2026-07-10 会议定稿）。

Paul 现场给的 worked example：期望交付日 7/20 → 周期窗口 6/21~7/20。
本文件测核心纯函数 match_period_cumulative_supply，不依赖真实 SRM/ERP 连接。

范围说明（design.md 已标注）：本算法只做单一需求维度的周期累计匹配；
"上一周期结转"用 carry_in_balance 参数注入（跨运行持久化账本是本次未做的
后续基础设施，见 design D2 备注），"多需求 PMC 优先级排序"沿用 B4 框架桩。
"""
from __future__ import annotations

from datetime import date

from sc8.period_match import match_period_cumulative_supply


def test_worked_example_window_6_21_to_7_20():
    """Paul worked example：期望交付日 7/20 → 窗口 6/21~7/20；窗口内累计够 → 可满足。"""
    commitments = [
        (date(2026, 6, 25), 30.0),
        (date(2026, 7, 5), 40.0),
        (date(2026, 7, 18), 30.0),
    ]
    result = match_period_cumulative_supply(
        material_id="M1", demand_qty=100.0, demand_date=date(2026, 7, 20),
        commitments=commitments, previous_demand_date=date(2026, 6, 20),
    )
    assert result.satisfied is True
    assert result.available_at_demand_date == 100.0
    assert result.satisfied_date == date(2026, 7, 20)
    assert result.daily_curve == {}


def test_commitment_before_window_start_excluded():
    """窗口起点 = 上次期望交付日+1；窗口前的承诺（已归属上一周期）不计入本周期。"""
    commitments = [
        (date(2026, 6, 15), 999.0),   # 早于窗口起点 6/21，不算
        (date(2026, 6, 25), 30.0),
    ]
    result = match_period_cumulative_supply(
        material_id="M1", demand_qty=30.0, demand_date=date(2026, 7, 20),
        commitments=commitments, previous_demand_date=date(2026, 6, 20),
    )
    assert result.satisfied is True
    assert result.available_at_demand_date == 30.0, "999.0 那条应被窗口排除在外"


def test_insufficient_at_demand_date_outputs_partial_and_curve():
    """需求日当天不够 → 输出部分满足量 + 逐日累计曲线，直到满足为止。"""
    commitments = [
        (date(2026, 6, 25), 30.0),
        (date(2026, 7, 22), 40.0),   # 需求日之后才到
        (date(2026, 7, 25), 30.0),   # 累计到这天才满足 100
    ]
    result = match_period_cumulative_supply(
        material_id="M1", demand_qty=100.0, demand_date=date(2026, 7, 20),
        commitments=commitments, previous_demand_date=date(2026, 6, 20),
    )
    assert result.satisfied is False
    assert result.available_at_demand_date == 30.0
    assert result.satisfied_date == date(2026, 7, 25)
    # 逐日曲线：7/21~7/24 累计仍是 30（无新到货，flat），7/22 到货后变 70，7/25 变 100
    assert result.daily_curve["2026-07-21"] == 30.0
    assert result.daily_curve["2026-07-22"] == 70.0
    assert result.daily_curve["2026-07-24"] == 70.0
    assert result.daily_curve["2026-07-25"] == 100.0


def test_never_satisfied_within_known_commitments():
    """已知承诺范围内累计仍不够 → satisfied_date=None，曲线截止到最后一条已知承诺日。"""
    commitments = [(date(2026, 7, 22), 10.0)]
    result = match_period_cumulative_supply(
        material_id="M1", demand_qty=100.0, demand_date=date(2026, 7, 20),
        commitments=commitments, previous_demand_date=date(2026, 6, 20),
    )
    assert result.satisfied is False
    assert result.satisfied_date is None
    assert result.daily_curve["2026-07-22"] == 10.0
    assert max(result.daily_curve) == "2026-07-22"


def test_carry_in_balance_applied_first():
    """上一周期结转的剩余供应量（carry_in_balance）优先计入本周期可用量。"""
    result = match_period_cumulative_supply(
        material_id="M1", demand_qty=50.0, demand_date=date(2026, 7, 20),
        commitments=[], previous_demand_date=date(2026, 6, 20),
        carry_in_balance=60.0,
    )
    assert result.satisfied is True
    assert result.available_at_demand_date == 60.0
    assert result.carry_forward == 10.0, "60(结转)-50(需求)=10 继续结转给下一周期"


def test_no_previous_demand_date_falls_back_to_minus_one_month():
    """无"上一次"时窗口起点兜底＝需求日减 1 个自然月（MVP 兜底，7/20 → 窗口起点 6/21）。"""
    commitments = [
        (date(2026, 6, 20), 999.0),   # 应被排除（6/21 之前）
        (date(2026, 6, 21), 30.0),    # 应计入（正好是兜底窗口起点当天）
    ]
    result = match_period_cumulative_supply(
        material_id="M1", demand_qty=30.0, demand_date=date(2026, 7, 20),
        commitments=commitments, previous_demand_date=None,
    )
    assert result.satisfied is True
    assert result.available_at_demand_date == 30.0


def test_month_end_edge_case_fallback():
    """兜底减 1 个自然月遇到月末日期不存在时安全处理（如 3/31 减 1 月 → 2 月无 31 日）。"""
    commitments = [(date(2026, 3, 1), 10.0)]
    result = match_period_cumulative_supply(
        material_id="M1", demand_qty=10.0, demand_date=date(2026, 3, 31),
        commitments=commitments, previous_demand_date=None,
    )
    assert result.satisfied is True  # 不应抛异常，2/28 或 2/29 都能覆盖 3/1 之前
