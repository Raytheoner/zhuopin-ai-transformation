"""FI9 骨架冒烟测试。

不测归集逻辑（引擎未实现，design 审未过）。守八件事：
  ⑴ 路径引导可用；
  ⑵ 🔴 三项未签认判据保持未签认（2026-09-03 起由底座注册表承接，行为不变）；
  ⑶ 🔴 **工时系统存在性保持"未核实"**——它不是"还没接"，是"不知道有没有"，
     且**未被并进判据注册表**（`G-2 = (a)`：靠去问一个人解除、不靠签认解除）；
  ⑷ 🔴 对外材料红线：`is_external_ready` 恒假、辅助账 `disclaimer` 必填；
  ⑸ 项目的高新口径归属不预设（`is_high_tech_scope` 默认 `None` 而非 `False`）；
  ⑹ 发票号 join 纪律留在代码里；
  ⑺ 🔴 G-5 反向依赖：写审计的 `decision` 恒带当时生效的 `RULE_VERSION`；
  ⑻ 🔴 **EE-3 待 design 审的状态留在代码里**——本场景会带出 OEM 项目标识，
     不可被后来者按其余财务场景的「不隔离」结论顺手归并。
"""
from __future__ import annotations

import dataclasses

import pytest

from zhuopin_platform.criteria_signoff import CriterionNotSignedOffError

from fi9_rd_cost import config, models


def test_platform_bootstrap_importable():
    from zhuopin_platform import bootstrap  # noqa: F401
    from zhuopin_platform.audit import AuditLogger  # noqa: F401


# 本场景的三项待签认判据（顺序即注册表声明顺序）。
CRITERIA_KEYS = ("CAPITALIZATION_CRITERIA", "HIGH_TECH_POLICY_LIBRARY", "RD_RATIO_DEFINITION")


def test_criteria_registry_declares_exactly_these():
    """🔴 三项判据一条不多、一条不少 —— 「多一条」几乎必然是 `TIMESHEET_SYSTEM_EXISTS` 被并了进来。"""
    assert config.CRITERIA.keys() == CRITERIA_KEYS


@pytest.mark.parametrize("key", CRITERIA_KEYS)
def test_criteria_registry_all_unsigned(key):
    """🔴 三项判据须财务侧签认，未签认前**读了就炸**。

    本场景的代价比其余财务场景高一个量级：编出来的资本化判据不会报错，
    但会写进报给政府的申报材料里。
    """
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
        scenario="FI9", action="rd_cost_collect", evaluator="示例研发总监",
        automation_level="L2",
        decision=config.audit_decision(project_id="RD-2026-001", verdict="待定"),
    )
    assert event.decision["rule_version"] == config.RULE_VERSION
    assert "unsigned" in event.decision["rule_version"]


def test_timesheet_system_existence_unverified():
    """🔴 工时系统的存在性未核实——不是"还没接"，是"不知道有没有"。

    承接方开工第一件事应是核实它是否存在，而不是假设它存在（已独立立行 `#477`）。
    """
    assert config.TIMESHEET_SYSTEM_EXISTS is None
    assert "三问皆未核实" in config.TIMESHEET_SYSTEM_UNVERIFIED
    assert "不得以任何分摊估算代替" in config.TIMESHEET_SYSTEM_UNVERIFIED


def test_timesheet_existence_is_not_a_criterion():
    """🔴 `G-2 = (a)`：存在性未核实**不得**被并进判据注册表。

    它靠**去问一个人**（`#477`）解除，判据靠**签认落档**解除。并成一条之后，
    「这条空值该找谁去解」就没了——而三类缺口里，那正是唯一各不相同的部分。
    """
    assert "TIMESHEET_SYSTEM_EXISTS" not in config.CRITERIA
    assert "#477" in config.TIMESHEET_SYSTEM_UNVERIFIED


def test_oem_isolation_decision_is_stated():
    """🔴 EE-3：本场景**会**带出 OEM 项目标识，五条定夺项已裁，状态须留在代码里。

    留这条的理由与 FI9 其余「本项目内不存在」注记同族，但方向相反：那些防的是
    「后来者假设某东西存在」，这条防的是**后来者假设本场景不涉 OEM 隔离**
    ——五个财务场景里另四个确实不涉，顺手归并是最省事、也最容易犯的一步。
    """
    text = config.OEM_ISOLATION_DECISION
    assert "EE-3" in text
    assert "data_isolation_layer" in text
    assert "已裁" in text


def test_external_filing_gate_stated():
    """🔴 对外材料红线须留在代码里（根 CLAUDE.md §7-4）。"""
    assert "AI 不得自动出具对外文件" in config.EXTERNAL_FILING_GATE


def test_verdict_never_external_ready_by_default():
    """🔴 判定默认需人工，且对外就绪恒假。

    `is_external_ready` 没有设为 True 的合法路径——对外可用与否由人决定，
    不由数据结构声明。
    """
    v = models.CapitalizationVerdict(project_id="RD-2026-001", entry_id="CE-0001")
    assert v.needs_manual_review is True
    assert v.is_external_ready is False


def test_aux_ledger_disclaimer_is_required():
    """🔴 辅助账每行必须显式带免责标注——给默认值就等于允许有人忘了写。"""
    defaults = {
        f.name
        for f in dataclasses.fields(models.AuxLedgerRow)
        if f.default is not dataclasses.MISSING
    }
    assert "disclaimer" not in defaults


def test_high_tech_scope_not_presumed():
    """项目是否纳入高新口径须按签认政策库判定，默认 `None`（未判）而非 `False`（判了不纳入）。"""
    p = models.RdProject("RD-X", "示例", "2026-01-01")
    assert p.is_high_tech_scope is None


def test_labor_record_source_synthetic(synthetic_labor):
    """骨架期工时只允许合成来源。"""
    assert all(r.source == "synthetic" for r in synthetic_labor)


def test_labor_rate_unsigned(synthetic_labor):
    """工时单价口径属判据，未签认前为 None，不得预填。"""
    assert all(r.rate is None for r in synthetic_labor)


def test_invoice_join_discipline_documented():
    """发票号 join 纪律须留在模块 docstring 里（本项目已实测证伪过字面 join 一次）。"""
    doc = models.__doc__ or ""
    assert "字面 join" in doc
    assert "不得直接沿用 FI2 的后 8 位方案" in doc
