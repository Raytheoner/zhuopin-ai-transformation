"""FI8 骨架冒烟测试。

不测预测逻辑（引擎未实现，design 审未过）。守六件事：
  ⑴ 路径引导可用；
  ⑵ 🔴 三项未签认判据保持未签认（2026-09-03 起由底座注册表承接，行为不变）；
  ⑶ 🔴 **银行账户余额的取数授权保持为空，且未被并进判据注册表**——它是**权限缺口**，
     解除路径是审批不是签认（`G-2 = (a)`）；骨架期期初余额只允许 `synthetic`；
  ⑷ what-if 结果恒被标为假设，不得与基线预测混同；
  ⑸ 链 D L8 的 O2 缺口口径**引自既有实现**，未被本场景另立一套；
  ⑹ 🔴 G-5 反向依赖：写审计的 `decision` 恒带当时生效的 `RULE_VERSION`。
"""
from __future__ import annotations

import pytest

from zhuopin_platform.criteria_signoff import CriterionNotSignedOffError

from fi8_cashflow_forecast import config, models


def test_platform_bootstrap_importable():
    from zhuopin_platform import bootstrap  # noqa: F401
    from zhuopin_platform.audit import AuditLogger  # noqa: F401


# 本场景的三项待签认判据（顺序即注册表声明顺序）。
CRITERIA_KEYS = ("CASH_GAP_THRESHOLD", "COLLECTION_ESCALATION_CRITERIA", "PAYMENT_CYCLE_SAMPLING")


def test_criteria_registry_declares_exactly_these():
    """🔴 三项判据一条不多、一条不少 —— 「多一条」几乎必然是 `BANK_BALANCE_ACCESS` 被并了进来。"""
    assert config.CRITERIA.keys() == CRITERIA_KEYS


@pytest.mark.parametrize("key", CRITERIA_KEYS)
def test_criteria_registry_all_unsigned(key):
    """🔴 三项判据须财务侧签认，未签认前**读了就炸**。"""
    assert config.CRITERIA.is_signed(key) is False
    with pytest.raises(CriterionNotSignedOffError):
        config.CRITERIA.value_of(key)


def test_rule_version_consistent_with_signoff_state():
    """版本号须自陈「未签认」；本用例同时守 `config.py` 里那行导入期校验别被删掉。"""
    config.CRITERIA.assert_rule_version(config.RULE_VERSION)
    assert "unsigned" in config.RULE_VERSION


def test_audit_decision_carries_rule_version():
    """🔴 G-5 反向依赖：审计日志指向判据版本，不是判据模块去写日志。"""
    from zhuopin_platform.audit import AuditEvent

    event = AuditEvent(
        scenario="FI8", action="cashflow_forecast", evaluator="示例 CFO 办公室复核人",
        automation_level="L2",
        decision=config.audit_decision(horizon_weeks=4, gap_windows=0),
    )
    assert event.decision["rule_version"] == config.RULE_VERSION
    assert "unsigned" in event.decision["rule_version"]


def test_bank_balance_access_not_granted():
    """🔴 银行账户余额取数授权未取得——这不是"还没定个数"，是**能不能取都还没人批**。

    它涉资金安全（同 FI3 的 L4 晋级须 CFO 会签口径），须财务侧 ＋ CFO 办公室明确。
    谁把它填上，请连同 CFO 办公室的授权落档一并提交。

    🔴 **EE-2（Shao Peishen 2026-09-03）：该授权由他本人去推。** 本场景先做不依赖余额的
    部分，**不得绕过**——绕过的形态不止「填个数」，还包括「拿期初余额推算」「拿 0 顶上」，
    那两种都会让整条 12 周曲线看起来完全正常而它是错的。
    """
    assert config.BANK_BALANCE_ACCESS is None, (
        "BANK_BALANCE_ACCESS 已被填值，但银行余额取数授权尚无 CFO 办公室落档记录"
    )
    assert "不得默认可得" in config.BANK_BALANCE_NOT_AUTHORIZED


def test_bank_balance_access_is_not_a_criterion():
    """🔴 `G-2 = (a)`：权限缺口**不得**被并进判据注册表。

    它与判据的机械形状很像（都是个空值、都拦着引擎不许跑），但**解除路径完全不同**：
    判据靠财务侧签认解除，这一条靠 CFO 办公室审批解除。并进去之后，
    「该找谁去解它」这个信息就一起没了——而那恰恰是这条空值唯一有用的部分。
    """
    assert "BANK_BALANCE_ACCESS" not in config.CRITERIA
    assert "不并入" in config.BANK_BALANCE_NOT_AUTHORIZED


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
