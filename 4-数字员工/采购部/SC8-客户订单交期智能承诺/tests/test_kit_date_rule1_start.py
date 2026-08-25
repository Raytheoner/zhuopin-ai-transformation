"""无答交启发式起算点「规则 1」（队列 §一 #401 ／ §四 #111 拍板 (a)）。

判据＝姚祖怡 2026-08-18 书面签认：
  · **规则 1**（出货日**不在**三个月内）：无答交按出货日往前推 3 个月的 **20 日**起、
    再往后推 90 天。他确认的例子逐字为「出货日是 12 月 5 日，往前推 3 个月是 9 月，
    起算点就是 9 月 20 日」。
  · **规则 2**（出货日**在**三个月内）：无答交按此时此刻起往后推 90 天。
  · **规则 3**（既有答交又有无答交）：取两者中更晚的作齐套日期。

本文件是**反例单测**：每个用例都写成「如果哪一处写错，这条会红」的形态，而不是把实现
再抄一遍。重点覆盖 ① 跨年 ② 月末 ③ 与规则 2／3 分支互斥 ④ 开关 OFF 时逐字节零漂移。
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from sc8 import config
from sc8.baoguan import assess_supply_risk
from sc8.forecast import (
    _shift_months,
    estimate_material_arrivals,
    no_feedback_start_date,
    ship_within_horizon,
)
from sc8.models import SalesOrder

P = config.default_params()


@pytest.fixture
def rule1_on(monkeypatch):
    monkeypatch.setenv("SC8_KIT_DATE_RULE1", "on")


@pytest.fixture
def rule1_off(monkeypatch):
    monkeypatch.setenv("SC8_KIT_DATE_RULE1", "off")


# ── 1. 起算点本身（规则 1 分支）────────────────────────────────────────────────

def test_yao_own_example_dec5_to_sep20():
    """他 08-18 亲口确认的那个例子，逐字复现：12/5 ⇒ 9/20。

    这条一旦红，说明「20 日」被读成了别的东西（月初/月末/相对天数）——而那正是
    采购部#15 专门发一封信去确认的那个歧义点。
    """
    assert no_feedback_start_date(date(2026, 12, 5), date(2026, 8, 25), P) == date(2026, 9, 20)


def test_start_day_is_natural_month_20th_not_relative_offset():
    """反例：同一个自然月里出货日不同，起算点必须**完全相同**（都是那个月的 20 号）。

    若实现写成「出货日减 90 天」之类的相对偏移，本条必红。
    """
    today = date(2026, 8, 25)
    starts = {no_feedback_start_date(date(2026, 12, d), today, P) for d in (1, 5, 19, 20, 21, 31)}
    assert starts == {date(2026, 9, 20)}


@pytest.mark.parametrize("ship,expected", [
    (date(2027, 1, 15), date(2026, 10, 20)),   # 跨年：1 月 → 上一年 10 月
    (date(2027, 2, 10), date(2026, 11, 20)),   # 跨年：2 月 → 上一年 11 月
    (date(2027, 3, 5),  date(2026, 12, 20)),   # 跨年：3 月 → 上一年 12 月
    (date(2027, 4, 1),  date(2027, 1, 20)),    # 同年首月，不跨年（边界的另一侧）
])
def test_cross_year_month_arithmetic(ship, expected):
    """跨年月份回绕：1/2/3 月前推 3 个月必须落到**上一年**的 10/11/12 月。

    反例价值：`month - 3` 直接算会得到 -2/-1/0 月，`date()` 当场抛 ValueError 或算错年份。
    """
    assert no_feedback_start_date(ship, date(2026, 8, 25), P) == expected


def test_month_end_ship_date_does_not_shift_the_anchor_month():
    """月末出货日（31 号）不得因「目标月没有 31 号」而把锚月挪走。

    实现先把出货日归到当月 1 号再推月，故 3-31 前推 3 个月是 **12 月**（不是 11 月）。
    若实现直接对 3-31 做月加减并收敛到月末，会得到 12-31 再改日为 20 ⇒ 结果碰巧相同；
    但 5-31 前推 3 个月的那一步会落到 2-28/2-29 ⇒ 锚月仍是 2 月，结果也相同。本条锁的是
    **锚月的选取与出货日的「日」无关**这条不变式。
    """
    today = date(2026, 8, 25)
    assert no_feedback_start_date(date(2027, 3, 31), today, P) == date(2026, 12, 20)
    assert no_feedback_start_date(date(2027, 5, 31), today, P) == date(2027, 2, 20)
    assert no_feedback_start_date(date(2027, 5, 1), today, P) == date(2027, 2, 20)


def test_rule1_start_may_precede_today_and_is_not_clamped():
    """起算点允许早于今天，**刻意不向今天钳制**（否则规则 1 在边界附近静默失效）。

    今天 08-25、出货 11-30（刚出三个月窗口）⇒ 起算 08-20，比今天早 5 天。
    若有人「顺手」加一句 `max(start, today)`，本条立刻红。
    """
    today, ship = date(2026, 8, 25), date(2026, 11, 30)
    start = no_feedback_start_date(ship, today, P)
    assert start == date(2026, 8, 20)
    assert start < today
    # 但估算到货日仍在未来 —— 不钳制不会造出「到货日在过去」这种荒谬结论
    assert start + timedelta(days=P.no_feedback_lead_days) > today


# ── 2. 规则 1 ／ 规则 2 分支互斥 ──────────────────────────────────────────────

def test_horizon_boundary_is_inclusive_and_exclusive_by_one_day():
    """三个月边界：当天算「在三个月内」（走规则 2），次日起走规则 1。

    这条同时是**互斥性**的锚点：同一 (today, ship) 只可能落进一支。
    """
    today = date(2026, 8, 25)
    assert ship_within_horizon(today, date(2026, 11, 25), P) is True
    assert ship_within_horizon(today, date(2026, 11, 26), P) is False
    # 边界当天 → 规则 2（起算＝出货日本身，因其晚于今天）
    assert no_feedback_start_date(date(2026, 11, 25), today, P) == date(2026, 11, 25)
    # 次日 → 规则 1（起算＝8 月 20 日）
    assert no_feedback_start_date(date(2026, 11, 26), today, P) == date(2026, 8, 20)


def test_horizon_month_end_clamping():
    """今天落在月末时，三个月边界收敛到目标月最后一天，不得抛 ValueError。

    8-31 + 3 个自然月 = 11-30（11 月没有 31 号）；11-30 仍判「在三个月内」。
    """
    assert _shift_months(date(2026, 8, 31), 3) == date(2026, 11, 30)
    assert _shift_months(date(2026, 11, 30), 3) == date(2027, 2, 28)
    assert _shift_months(date(2027, 11, 30), 3) == date(2028, 2, 29)   # 闰年
    assert ship_within_horizon(date(2026, 8, 31), date(2026, 11, 30), P) is True
    assert ship_within_horizon(date(2026, 8, 31), date(2026, 12, 1), P) is False


@pytest.mark.parametrize("ship", [date(2026, 6, 1), date(2026, 8, 24), date(2026, 8, 25)])
def test_past_due_ship_dates_stay_on_rule2(ship):
    """已过期／今天的出货日恒判「在三个月内」⇒ 起算＝今天，与规则 2 逐字一致。

    #344 实测的那 38 行就在这一支，本次**必须不动它们**。
    """
    today = date(2026, 8, 25)
    assert ship_within_horizon(today, ship, P) is True
    assert no_feedback_start_date(ship, today, P) == today


@pytest.mark.parametrize("ship", [date(2026, 9, 1), date(2026, 10, 15), date(2026, 11, 25)])
def test_future_within_horizon_keeps_current_conservative_reading(ship):
    """未来但在三个月内的行：**本次刻意不改**，仍是「出货日 +90」而非「今天 +90」。

    实测 24 行落在这一支，现行比规则 2 逐字更晚、偏保守。§四 #111 拍板 (a) 的标的是
    规则 1；顺手一起改会让一次上线带两个自变量。本条把「不改」钉成显式契约——将来若要
    改规则 2，改的人会先在这里被拦一下，并被迫回头看这段理由。
    """
    today = date(2026, 8, 25)
    assert no_feedback_start_date(ship, today, P) == ship
    assert no_feedback_start_date(ship, today, P) != today


# ── 3. 与规则 3（有答交／无答交取更晚）互不干扰 ────────────────────────────────

def _bom(product: str, *components: str):
    from zhuopin_platform.shared_tools.models import BomRow
    return [BomRow(product_id=product, component_id=c, component_name=c, level=1,
                   qty_per_unit=1.0, loss_rate=0.0, unit="PCS") for c in components]


def _so(ship: str) -> SalesOrder:
    return SalesOrder(so_id="FO-1", customer_id="", customer_name="某客户",
                      item_code="F01", qty=10, required_date=ship,
                      doc_type="预测订单", item_name="成品")


def test_rule3_still_takes_the_later_of_answered_and_unanswered(rule1_on):
    """规则 1 把无答交子件的估算日往前挪之后，规则 3 仍然成立：齐料日＝两者更晚。

    构造：A 有答交 2027-03-10（晚），B 无答交（规则 1 起算 2026-09-20 +90 = 2026-12-19）。
    齐料日必须是 A 的 2027-03-10 —— 若实现让规则 1 覆盖了整行而不是只改无答交那一支，
    本条会红。
    """
    from zhuopin_platform.shared_tools.models import SrmDeliveryOrder
    bom = _bom("F01", "A", "B")
    srm = [SrmDeliveryOrder(delivery_id="D1", demand_id="N1", supplier_id="ZA.0001",
                            material_id="A", qty_committed=10,
                            committed_date="2027-03-10", status="confirmed")]
    mat = estimate_material_arrivals(
        "F01", bom, srm, demand_date=date(2026, 12, 20), params=P,
        heuristic_base_date=no_feedback_start_date(date(2026, 12, 20), date(2026, 8, 25), P))
    assert mat.arrivals["A"] == date(2027, 3, 10)
    assert mat.arrivals["B"] == date(2026, 9, 20) + timedelta(days=90)
    assert max(mat.arrivals.values()) == date(2027, 3, 10)      # 规则 3：取更晚
    assert mat.bottleneck_material == "A"
    assert mat.no_feedback_materials == ["B"]


def test_rule1_moves_the_unanswered_leg_earlier_not_later(rule1_on):
    """方向性反例：规则 1 只会把无答交子件的估算日**前移**，绝不后移。

    #111 实测「现行一律比规则 1 晚 89~92 天」，方向搞反会让看板更红而不是更绿。
    """
    today, ship = date(2026, 8, 25), date(2027, 1, 15)
    before = max(ship, today) + timedelta(days=P.no_feedback_lead_days)
    after = no_feedback_start_date(ship, today, P) + timedelta(days=P.no_feedback_lead_days)
    assert after < before
    assert (before - after).days == (ship - date(2026, 10, 20)).days


# ── 4. 开关 OFF ⇒ 零漂移（结构性，不靠「跑了测试没发现」）────────────────────────

def test_default_is_off(monkeypatch):
    """**未设置环境变量**时必须是 OFF —— 与 `net_inventory_enabled` 同级：翻 ON 会改四色。

    用 `delenv` 而不是读环境现值：本条锁的是**代码里的默认值**，不是这台机器当下的
    环境；后者会让「把开关调到 ON 跑一遍全量」这种正当动作把本条弄红。
    """
    monkeypatch.delenv("SC8_KIT_DATE_RULE1", raising=False)
    assert config.kit_date_rule1_enabled() is False


def test_estimate_without_base_date_is_byte_identical(rule1_on):
    """不传 `heuristic_base_date` ⇒ 与改造前逐字节一致，即使开关是 ON。

    这条锁的是 `sc8/pipeline.py` 与 `data/golden/` 的结构性零漂移：它们不传本参数，
    所以**走不进**新分支——零漂移由调用图保证，而不是由「测试碰巧没覆盖到」保证。
    """
    bom = _bom("F01", "B")
    demand = date(2027, 1, 15)
    mat = estimate_material_arrivals("F01", bom, [], demand_date=demand, params=P)
    assert mat.arrivals["B"] == demand + timedelta(days=P.no_feedback_lead_days)


def test_assess_supply_risk_zero_drift_when_switch_off(rule1_off):
    """开关 OFF 时 `assess_supply_risk` 的齐料日 ＝ 改造前口径（max(出货日,今天)+90）。"""
    so = _so("2027-01-15")
    bom = _bom("F01", "B")
    row = assess_supply_risk(so, bom, [], today=date(2026, 8, 25), params=P)
    assert row.kit_date == date(2027, 1, 15) + timedelta(days=P.no_feedback_lead_days)


def test_assess_supply_risk_applies_rule1_when_switch_on(rule1_on):
    """开关 ON 时同一份输入的齐料日前移到规则 1 的结论，且差值 ＝ 出货日与 10/20 之差。"""
    so = _so("2027-01-15")
    bom = _bom("F01", "B")
    row = assess_supply_risk(so, bom, [], today=date(2026, 8, 25), params=P)
    assert row.kit_date == date(2026, 10, 20) + timedelta(days=P.no_feedback_lead_days)


def test_param_version_carries_the_branch(monkeypatch):
    """审计可追溯：开关 ON 时参数版本串自带 `+rule1` 标记。

    否则同一个 `sc8-params-v1` 会对应两套齐料日算法，事后无法还原当时按哪一支算的。
    """
    monkeypatch.setenv("SC8_KIT_DATE_RULE1", "off")
    assert config.default_params().param_version == config.PARAM_VERSION
    monkeypatch.setenv("SC8_KIT_DATE_RULE1", "on")
    assert config.default_params().param_version == config.PARAM_VERSION + "+rule1"
