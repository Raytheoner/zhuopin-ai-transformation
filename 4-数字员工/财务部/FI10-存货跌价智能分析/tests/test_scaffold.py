"""FI10 骨架冒烟测试。

不测跌价逻辑（引擎未实现，design 审未过）。守七件事：
  ⑴ 路径引导可用；
  ⑵ 🔴 芯片价格 API 前置未满足 —— 且 `chip_price_drop` 类预警在此之前不得产生，
     该缺口**未被并进判据注册表**（`G-2 = (a)`：靠上游前置落地解除、不靠签认解除）；
  ⑶ 🔴 L9 呆滞口径 —— `EE-4` 已裁「FI10 先定、SC7 后对齐」，口径**归属**定了，
     但判据本身仍未签认（`G-3` 已把它登记进注册表，**登记 ≠ 填值**）；
  ⑷ 🔴 四项未签认判据保持未签认（2026-09-03 起由底座注册表承接，行为不变）；
  ⑸ 🔴 OEM 隔离：`OemProjectPhase.oem_customer` 必填、无默认值；
  ⑹ 计提建议 `disclaimer` 必填、`confirmed_by` 空即不得入账；
  ⑺ 🔴 G-5 反向依赖：写审计的 `decision` 恒带当时生效的 `RULE_VERSION`。
"""
from __future__ import annotations

import dataclasses

import pytest

from zhuopin_platform.criteria_signoff import CriterionNotSignedOffError

from fi10_inventory_writedown import config, models


def test_platform_bootstrap_importable():
    from zhuopin_platform import bootstrap  # noqa: F401
    from zhuopin_platform.audit import AuditLogger  # noqa: F401
    from zhuopin_platform.data_isolation_layer import OEMRouter  # noqa: F401


def test_chip_price_api_blocked():
    """🔴 芯片价格 API 前置未满足（队列 #475 独立立行）。

    并且：该前置的**标的本身尚待判定**（「芯片供货 API」与「芯片市场价格 API」是否同一项
    未定）。本场景**不代下结论**，如实沿用「未定」。
    """
    assert config.CHIP_PRICE_API is None
    assert "#475" in config.CHIP_PRICE_API_BLOCKED
    assert "是否同一项未定" in config.CHIP_PRICE_API_BLOCKED


def test_chip_price_alert_type_not_producible_yet():
    """🔴 依赖芯片价格 API 的预警类型在前置满足前不得产生。

    这条用例守的是"停下登记"这个动作本身：`chip_price_drop` 这个类型名可以存在于契约里
    （否则后续接上时又要改模型），但只要 `CHIP_PRICE_API` 还是空，就不该有任何代码路径
    去生成它。骨架期没有引擎，故此处只锁住前置状态与类型名的对应关系。
    """
    assert config.CHIP_PRICE_API is None
    alert = models.WritedownAlert(material_id="MAT-001", alert_type="chip_price_drop")
    # 契约允许构造，但前置未满足 ⇒ 引擎侧不得有生成路径（引擎实现时补对应用例）
    assert alert.alert_type == "chip_price_drop"
    assert "停下登记" in config.CHIP_PRICE_API_BLOCKED


def test_l9_slow_moving_registered_but_unsigned():
    """🔴 L9 呆滞口径：`G-3` 已把它**登记进注册表**，但它**仍未签认**。

    两件事必须同时成立，缺一即错：
      · 登记了 —— 否则这条判据从此不在任何查缺视野里（`require_all_signed` 看不到它）；
      · 仍未签认 —— `EE-4`「FI10 先定、SC7 后对齐」定的是**口径归属**，不是口径本身。
        「先定」被读成「现在就填」是本条最可能的误读，故此处读一次、必须炸。

    原两条 `L9_SOURCE_ABSENT` 文本断言保留：它记的是 `#474`／`EE-4` 的来龙去脉
    ——「这条判据为什么一度无源可取、又是被哪条裁决改变了性质」。
    """
    assert "SLOW_MOVING_CRITERIA" in config.CRITERIA
    assert config.CRITERIA.is_signed("SLOW_MOVING_CRITERIA") is False
    with pytest.raises(CriterionNotSignedOffError):
        config.CRITERIA.value_of("SLOW_MOVING_CRITERIA")
    assert "尚未落地" in config.L9_SOURCE_ABSENT
    assert "另立一套" in config.L9_SOURCE_ABSENT
    # `EE-4` 的改判须与上段原文并存 —— 只留结论会丢掉成因，只留原文会留下已被推翻的结论。
    assert "EE-4" in config.L9_OWNERSHIP_RULED
    assert "口径归属" in config.L9_OWNERSHIP_RULED


# 本场景的四项待签认判据（顺序即注册表声明顺序；第四项由 `G-3` 归入）。
CRITERIA_KEYS = (
    "NRV_ESTIMATION_BASIS",
    "AGING_ALERT_THRESHOLD",
    "TERMINATED_PROJECT_ALERT_CRITERIA",
    "SLOW_MOVING_CRITERIA",
)


def test_criteria_registry_declares_exactly_these():
    """🔴 四项判据一条不多、一条不少 —— 「多一条」几乎必然是 `CHIP_PRICE_API` 被并了进来。"""
    assert config.CRITERIA.keys() == CRITERIA_KEYS


@pytest.mark.parametrize("key", CRITERIA_KEYS)
def test_criteria_registry_all_unsigned(key):
    """🔴 四项判据须财务侧签认，未签认前**读了就炸**。"""
    assert config.CRITERIA.is_signed(key) is False
    with pytest.raises(CriterionNotSignedOffError):
        config.CRITERIA.value_of(key)


def test_rule_version_consistent_with_signoff_state():
    """版本号须自陈「未签认」；本用例同时守 `config.py` 里那行导入期校验别被删掉。"""
    config.CRITERIA.assert_rule_version(config.RULE_VERSION)
    assert "unsigned" in config.RULE_VERSION


def test_chip_price_api_is_not_a_criterion():
    """🔴 `G-2 = (a)`：前置未满足**不得**被并进判据注册表。

    它靠**上游 `#475` 落地**解除，判据靠签认解除；且它的标的本身尚待判定
    （「供货 API」与「市场价格 API」是否同一项未定）——一条连标的都没定的东西
    被登记成「待财务侧签认的判据」，会把它派给一个根本解不了它的人。
    """
    assert "CHIP_PRICE_API" not in config.CRITERIA
    assert "不并入" in config.CHIP_PRICE_API_BLOCKED


def test_audit_decision_carries_rule_version():
    """🔴 G-5 反向依赖：审计日志指向判据版本，不是判据模块去写日志。"""
    from zhuopin_platform.audit import AuditEvent

    event = AuditEvent(
        scenario="FI10", action="writedown_test", evaluator="示例供应链经理",
        automation_level="L2",
        decision=config.audit_decision(material_id="MAT-001", writedown_amount=None),
        oem_context="占位客户A",
    )
    assert event.decision["rule_version"] == config.RULE_VERSION
    assert "unsigned" in event.decision["rule_version"]


def test_oem_customer_is_required():
    """🔴 OEM 隔离：不知属谁的 OEM 项目数据在隔离体系里无处安放。

    让 `oem_customer` 可以留空，就是给混库开了个口子（根 CLAUDE.md §7-3）。
    """
    defaults = {
        f.name
        for f in dataclasses.fields(models.OemProjectPhase)
        if f.default is not dataclasses.MISSING
        or f.default_factory is not dataclasses.MISSING  # type: ignore[misc]
    }
    assert "oem_customer" not in defaults
    assert "禁跨库" in config.OEM_ISOLATION_REQUIRED


def test_provision_advice_disclaimer_required():
    """🔴 计提建议影响财务报表 ⇒ `disclaimer` 必填、无默认值。"""
    defaults = {
        f.name
        for f in dataclasses.fields(models.ProvisionAdvice)
        if f.default is not dataclasses.MISSING
    }
    assert "disclaimer" not in defaults


def test_writedown_test_defaults():
    """🔴 L2 默认侧：需人工确认；NRV 未签认口径时为 None（不是 0）。"""
    t = models.WritedownTest(material_id="MAT-001", batch_no="B2025-11", book_cost=46200.0)
    assert t.needs_manual_review is True
    assert t.nrv is None
    assert t.writedown_amount is None


def test_pure_derivations(simple_aging, simple_in_transit):
    """账面成本与在途量是纯派生量，不含判据，骨架期即可测。

    在途量口径与 `kit_engine.calc_shortage` 一致（已订 − 已收），刻意对齐，
    免得同一个概念在两个场景里算出两个数。
    """
    assert simple_aging[0].book_cost == pytest.approx(46200.0)
    assert simple_in_transit[0].qty_in_transit == pytest.approx(1500.0)
    assert simple_in_transit[1].qty_in_transit == pytest.approx(1000.0)
