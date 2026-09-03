"""FI9 骨架冒烟测试。

不测归集逻辑（引擎未实现，design 审未过）。守六件事：
  ⑴ 路径引导可用；
  ⑵ 🔴 三项未签认判据保持为空；
  ⑶ 🔴 **工时系统存在性保持"未核实"**——它不是"还没接"，是"不知道有没有"；
  ⑷ 🔴 对外材料红线：`is_external_ready` 恒假、辅助账 `disclaimer` 必填；
  ⑸ 项目的高新口径归属不预设（`is_high_tech_scope` 默认 `None` 而非 `False`）；
  ⑹ 发票号 join 纪律留在代码里。
"""
from __future__ import annotations

import dataclasses

import pytest

from fi9_rd_cost import config, models


def test_platform_bootstrap_importable():
    from zhuopin_platform import bootstrap  # noqa: F401
    from zhuopin_platform.audit import AuditLogger  # noqa: F401


@pytest.mark.parametrize(
    "name",
    ["CAPITALIZATION_CRITERIA", "HIGH_TECH_POLICY_LIBRARY", "RD_RATIO_DEFINITION"],
)
def test_unsigned_criteria_stay_none(name):
    """🔴 三项判据须财务侧签认，未签认前一律 None。

    本场景的代价比其余财务场景高一个量级：编出来的资本化判据不会报错，
    但会写进报给政府的申报材料里。
    """
    assert getattr(config, name) is None


def test_timesheet_system_existence_unverified():
    """🔴 工时系统的存在性未核实——不是"还没接"，是"不知道有没有"。

    承接方开工第一件事应是核实它是否存在，而不是假设它存在。
    """
    assert config.TIMESHEET_SYSTEM_EXISTS is None
    assert "三问皆未核实" in config.TIMESHEET_SYSTEM_UNVERIFIED
    assert "不得以任何分摊估算代替" in config.TIMESHEET_SYSTEM_UNVERIFIED


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
