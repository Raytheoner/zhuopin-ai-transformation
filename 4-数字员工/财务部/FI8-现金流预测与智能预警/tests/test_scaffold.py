"""FI8 骨架冒烟测试。

不测预测逻辑（引擎未实现，design 审未过）。守五件事：
  ⑴ 路径引导可用；
  ⑵ 🔴 三项未签认判据保持为空；
  ⑶ 🔴 **银行账户余额的取数授权保持为空**——这一条与判据不同，它是权限缺口，
     骨架期期初余额只允许 `synthetic`；
  ⑷ what-if 结果恒被标为假设，不得与基线预测混同；
  ⑸ 链 D L8 的 O2 缺口口径**引自既有实现**，未被本场景另立一套。
"""
from __future__ import annotations

import pytest

from fi8_cashflow_forecast import config, models


def test_platform_bootstrap_importable():
    from zhuopin_platform import bootstrap  # noqa: F401
    from zhuopin_platform.audit import AuditLogger  # noqa: F401


@pytest.mark.parametrize(
    "name",
    ["CASH_GAP_THRESHOLD", "COLLECTION_ESCALATION_CRITERIA", "PAYMENT_CYCLE_SAMPLING"],
)
def test_unsigned_criteria_stay_none(name):
    """🔴 三项判据须财务侧签认，未签认前一律 None。"""
    assert getattr(config, name) is None


def test_bank_balance_access_not_granted():
    """🔴 银行账户余额取数授权未取得——这不是"还没定个数"，是**能不能取都还没人批**。

    它涉资金安全（同 FI3 的 L4 晋级须 CFO 会签口径），须财务侧 ＋ CFO 办公室明确。
    谁把它填上，请连同 CFO 办公室的授权落档一并提交。
    """
    assert config.BANK_BALANCE_ACCESS is None, (
        "BANK_BALANCE_ACCESS 已被填值，但银行余额取数授权尚无 CFO 办公室落档记录"
    )
    assert "不得默认可得" in config.BANK_BALANCE_NOT_AUTHORIZED


def test_opening_balance_is_synthetic(synthetic_opening):
    """骨架期期初余额只允许合成来源。"""
    assert synthetic_opening.source == "synthetic"


def test_whatif_is_always_hypothetical():
    """🔴 what-if 结果恒为假设，不得与基线预测混在一起对外呈现。"""
    sc = models.WhatIfScenario(scenario_id="WI-001", description="某客户延迟付款 30 天")
    assert sc.is_hypothetical is True


def test_gap_window_not_cfo_confirmed_by_default():
    """🔴 L2 默认侧：资金调度是 CFO 的决策，AI 不自行发起。"""
    gap = models.GapWindow(start_week="2026-10-05", end_week="2026-10-19", min_balance=-320000.0)
    assert gap.confirmed_by_cfo is False


def test_o2_shortage_semantics_quotes_existing_impl():
    """🔗 链 D L8：O2 缺口口径引自既有实现，本场景不另立一套。

    `#472` 明写「`O2` 已有工程实体，承接方可直接读其口径、不必从零定义」。
    这条用例守住那句"引自"——口径描述里必须点到权威实现的名字，
    否则下一个人就会照着自己的理解重写一版。
    """
    text = config.O2_SHORTAGE_SEMANTICS
    assert "calc_shortage" in text
    assert "missing_snapshot" in text


def test_forecast_horizons_are_4_8_12():
    """4/8/12 周是场景定义（#472 标的原文），不是待签认判据，故可写死。"""
    assert config.FORECAST_HORIZONS_WEEKS == (4, 8, 12)


def test_payment_history_delay_days_is_pure_derivation(simple_history):
    """回款延迟天数是纯派生量，不含判据，骨架期即可测。"""
    assert simple_history[0].delay_days == 8
    assert simple_history[1].delay_days == 5
    assert simple_history[2].delay_days == 35


def test_payment_history_delay_days_handles_bad_dates():
    """日期不可解析时返回 None，**不返回 0** —— 0 会被下游当成"按期回款"。"""
    bad = models.PaymentHistory("CUS-X", "AR-X", "", "2026-07-25", 1.0)
    assert bad.delay_days is None
