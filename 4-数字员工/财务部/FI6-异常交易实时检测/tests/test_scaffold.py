"""FI6 骨架冒烟测试。

不测业务逻辑（检测器未实现，design 审未过）。守五件事：
  ⑴ 路径引导可用；
  ⑵ 🔴 四项未签认判据没被人悄悄签掉（2026-09-03 起由底座注册表承接，行为不变）；
  ⑶ 🔴 `PartyProfile` 上没有被人加出一个"是否关联方"的布尔字段
     —— 关联口径尚未定义，多出这个字段就等于口径被默默造了出来；
  ⑷ L2 默认侧（需人工）与案例库判例的实名要求；
  ⑸ 🔴 G-5 反向依赖：写审计的 `decision` 恒带当时生效的 `RULE_VERSION`。
"""
from __future__ import annotations

import dataclasses

import pytest

from zhuopin_platform.criteria_signoff import CriterionNotSignedOffError

from fi6_anomaly_detect import config, models


def test_platform_bootstrap_importable():
    from zhuopin_platform import bootstrap  # noqa: F401
    from zhuopin_platform.audit import AuditLogger  # noqa: F401


# 本场景的四项待签认判据（顺序即注册表声明顺序）。
CRITERIA_KEYS = (
    "AMOUNT_SURGE_CRITERIA",
    "FREQUENCY_ANOMALY_CRITERIA",
    "RELATED_PARTY_CRITERIA",
    "L2_ESCALATION_CRITERIA",
)


def test_criteria_registry_declares_exactly_these():
    """🔴 四项判据一条不多、一条不少地登记在注册表里（少一条即从此无人守）。"""
    assert config.CRITERIA.keys() == CRITERIA_KEYS


@pytest.mark.parametrize("key", CRITERIA_KEYS)
def test_criteria_registry_all_unsigned(key):
    """🔴 四项判据须财务侧签认，未签认前**读了就炸**。

    异常检测最容易被「先随便设个 3 倍标准差」蒙混过去——那个数一旦落地就会静默决定
    谁被推给财务主管、谁被放过，且永远不会报错。
    """
    assert config.CRITERIA.is_signed(key) is False, (
        f"{key} 已被签认，但本场景尚无财务侧签认落档"
    )
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
        scenario="FI6", action="anomaly_detect", evaluator="示例财务主管",
        automation_level="L2",
        decision=config.audit_decision(txn_id="TX-0001", patterns=[]),
    )
    assert event.decision["rule_version"] == config.RULE_VERSION
    assert "unsigned" in event.decision["rule_version"]


def test_party_profile_has_no_related_flag():
    """🔴 `PartyProfile` 不得出现「是否关联方」类字段。

    关联口径（股权？亲属？主数据比对？）至今未定义。留一个 `is_related` 字段会诱使
    实现方先填上再说——判据就是这样被默默造出来的。要加这个字段，先把口径签认下来。
    """
    field_names = {f.name for f in dataclasses.fields(models.PartyProfile)}
    forbidden = {"is_related", "is_related_party", "related", "related_party"}
    assert not (field_names & forbidden), (
        f"PartyProfile 出现关联方标志字段 {field_names & forbidden}，"
        f"但 RELATED_PARTY_CRITERIA 在注册表里仍未签认"
    )


def test_finding_defaults_to_manual_review():
    """🔴 L2 默认侧：未经判据证成一律 needs_manual_review=True、escalated=False。"""
    finding = models.AnomalyFinding(txn_id="TX-0001")
    assert finding.needs_manual_review is True
    assert finding.escalated is False


def test_case_record_requires_named_confirmer():
    """判例的价值全在「谁认的」——`confirmed_by` 是必填位置参数，不给默认值。"""
    sig_defaults = {
        f.name: f.default
        for f in dataclasses.fields(models.CaseRecord)
        if f.default is not dataclasses.MISSING
    }
    assert "confirmed_by" not in sig_defaults


def test_absence_notes_present():
    """两处「本项目内不存在」的事实须留在代码里，防止后来者假设它们存在。"""
    assert "无既有载体" in config.CASE_LIBRARY_ABSENT
    assert "FI3" in config.FI3_NO_ENTITY
