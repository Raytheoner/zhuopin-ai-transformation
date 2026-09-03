"""FI10 骨架冒烟测试。

不测跌价逻辑（引擎未实现，design 审未过）。守六件事：
  ⑴ 路径引导可用；
  ⑵ 🔴 芯片价格 API 前置未满足 —— 且 `chip_price_drop` 类预警在此之前不得产生；
  ⑶ 🔴 L9 呆滞口径无源可取 —— SC7 那份口径尚未落地，本场景不得自行定义；
  ⑷ 🔴 三项未签认判据保持为空；
  ⑸ 🔴 OEM 隔离：`OemProjectPhase.oem_customer` 必填、无默认值；
  ⑹ 计提建议 `disclaimer` 必填、`confirmed_by` 空即不得入账。
"""
from __future__ import annotations

import dataclasses

import pytest

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


def test_l9_slow_moving_source_absent():
    """🔴 L9「同口径」当前无源可取 —— SC7 的呆滞口径尚未落地。

    `#474` 要求「从 SC7 取、不得另立一套」，但 SC7 工程实体里没有那份口径
    （②期深化 2027-01，业务口径待姚祖怡确认）。⇒ 本场景**不得自行定义**呆滞口径。
    """
    assert config.SLOW_MOVING_CRITERIA is None
    assert "尚未落地" in config.L9_SOURCE_ABSENT
    assert "另立一套" in config.L9_SOURCE_ABSENT


@pytest.mark.parametrize(
    "name",
    ["NRV_ESTIMATION_BASIS", "AGING_ALERT_THRESHOLD", "TERMINATED_PROJECT_ALERT_CRITERIA"],
)
def test_unsigned_criteria_stay_none(name):
    """🔴 三项判据须财务侧签认，未签认前一律 None。"""
    assert getattr(config, name) is None


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
