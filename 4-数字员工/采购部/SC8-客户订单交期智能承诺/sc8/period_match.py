"""周期累计供需匹配（B2，shortage-baoguan-criteria-v3，2026-07-10 会议定稿）。

Paul 现场答复的核心逻辑（非简单的"数量双判"）：
  1. 周期窗口 = [上一次期望交付日 次日, 本次期望交付日 D]（例：D=7/20 → 窗口 6/21~7/20；
     无"上一次"时兜底＝D 减 1 个自然月）。
  2. 窗口内该物料的 SRM 承诺（调用方已按 PO+供应商配对好、取当前确认状态，本函数
     只管累计计算）按承诺日期升序累加。
  3. 累计满足需求量 → 判定"可满足"；不满足 → 输出需求日当天可满足量 + 逐日累计
     曲线（每天一个值，含无新到货的平台期），直到累计满足或已知承诺耗尽为止。
  4. 跨周期结转：`carry_in_balance` 由调用方传入上一周期的剩余供应量，本周期优先
     使用；本周期算完的剩余（`carry_forward`）供调用方结转给下一周期。

范围提醒：本模块只做"单一需求"的周期累计匹配。多个需求同时竞争同一物料时的
PMC 优先级排序不在此实现（沿用 `sc8.priority_hook` 的框架桩，见 B4）。跨运行的
"上一周期期望交付日 / 结转余额"持久化账本本次未做，由调用方显式传入
（`previous_demand_date`/`carry_in_balance`），持久化落点是独立后续任务。
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta


def _minus_one_month(d: date) -> date:
    """d 减 1 个自然月，遇到目标月无该日（如 3/31→2 月）时安全裁到月末。"""
    year, month = d.year, d.month - 1
    if month == 0:
        month, year = 12, year - 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


@dataclass
class PeriodMatchResult:
    """单一需求的周期累计供需匹配结果。"""
    material_id:              str
    demand_qty:                float
    demand_date:               date
    window_start:              date
    satisfied:                 bool                 # 需求日当天是否已累计满足
    available_at_demand_date:  float                # 需求日当天累计可满足数量
    satisfied_date:            date | None          # 累计满足需求量的日期；已知承诺耗尽仍不够→None
    daily_curve:               dict[str, float] = field(default_factory=dict)  # {日期: 累计可满足量}，需求日之后逐日
    carry_forward:             float = 0.0          # 结转给下一周期的剩余供应量（仅 satisfied 时非零）


def match_period_cumulative_supply(
    material_id: str,
    demand_qty: float,
    demand_date: date,
    commitments: list[tuple[date, float]],
    *,
    previous_demand_date: date | None = None,
    carry_in_balance: float = 0.0,
) -> PeriodMatchResult:
    """周期累计供需匹配（见模块 docstring）。

    Args:
        commitments: [(承诺到货日, 数量), ...]，调用方已按 PO+供应商配对取当前
            确认状态（不含历史修改版本）；可包含窗口前/需求日后的记录，本函数
            自行按窗口起点过滤、按日期升序处理。
    """
    window_start = (
        previous_demand_date + timedelta(days=1) if previous_demand_date is not None
        else _minus_one_month(demand_date) + timedelta(days=1)
    )
    relevant = sorted((d, q) for d, q in commitments if d >= window_start)

    cumulative = carry_in_balance
    idx = 0
    n = len(relevant)
    while idx < n and relevant[idx][0] <= demand_date:
        cumulative += relevant[idx][1]
        idx += 1
    available_at_demand_date = cumulative
    satisfied = available_at_demand_date >= demand_qty

    if satisfied:
        return PeriodMatchResult(
            material_id=material_id, demand_qty=demand_qty, demand_date=demand_date,
            window_start=window_start, satisfied=True,
            available_at_demand_date=available_at_demand_date,
            satisfied_date=demand_date, daily_curve={},
            carry_forward=available_at_demand_date - demand_qty,
        )

    # 未满足：把需求日之后的承诺按日期分组，逐日推进累计曲线
    future_by_date: dict[date, float] = {}
    for d, q in relevant[idx:]:
        future_by_date[d] = future_by_date.get(d, 0.0) + q

    curve: dict[str, float] = {}
    satisfied_date: date | None = None
    if future_by_date:
        last_commit_date = max(future_by_date)
        cursor = demand_date
        running = cumulative
        while running < demand_qty and cursor < last_commit_date:
            cursor += timedelta(days=1)
            running += future_by_date.get(cursor, 0.0)
            curve[cursor.isoformat()] = running
        if running >= demand_qty:
            satisfied_date = cursor

    return PeriodMatchResult(
        material_id=material_id, demand_qty=demand_qty, demand_date=demand_date,
        window_start=window_start, satisfied=False,
        available_at_demand_date=available_at_demand_date,
        satisfied_date=satisfied_date, daily_curve=curve, carry_forward=0.0,
    )
