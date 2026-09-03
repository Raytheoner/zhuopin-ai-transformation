"""FI6 骨架冒烟测试。

不测业务逻辑（检测器未实现，design 审未过）。守四件事：
  ⑴ 路径引导可用；
  ⑵ 🔴 四项未签认判据没被人悄悄填上默认数；
  ⑶ 🔴 `PartyProfile` 上没有被人加出一个"是否关联方"的布尔字段
     —— 关联口径尚未定义，多出这个字段就等于口径被默默造了出来；
  ⑷ L2 默认侧（需人工）与案例库判例的实名要求。
"""
from __future__ import annotations

import dataclasses

import pytest

from fi6_anomaly_detect import config, models


def test_platform_bootstrap_importable():
    from zhuopin_platform import bootstrap  # noqa: F401
    from zhuopin_platform.audit import AuditLogger  # noqa: F401


@pytest.mark.parametrize(
    "name",
    [
        "AMOUNT_SURGE_CRITERIA",
        "FREQUENCY_ANOMALY_CRITERIA",
        "RELATED_PARTY_CRITERIA",
        "L2_ESCALATION_CRITERIA",
    ],
)
def test_unsigned_criteria_stay_none(name):
    """🔴 四项判据须财务侧签认，未签认前一律 None。

    异常检测最容易被「先随便设个 3 倍标准差」蒙混过去——那个数一旦落地就会静默决定
    谁被推给财务主管、谁被放过，且永远不会报错。
    """
    assert getattr(config, name) is None, (
        f"{name} 已被填值，但本场景判据尚无财务侧签认记录"
    )


def test_rule_version_marked_unsigned():
    assert "unsigned" in config.RULE_VERSION


def test_party_profile_has_no_related_flag():
    """🔴 `PartyProfile` 不得出现「是否关联方」类字段。

    关联口径（股权？亲属？主数据比对？）至今未定义。留一个 `is_related` 字段会诱使
    实现方先填上再说——判据就是这样被默默造出来的。要加这个字段，先把口径签认下来。
    """
    field_names = {f.name for f in dataclasses.fields(models.PartyProfile)}
    forbidden = {"is_related", "is_related_party", "related", "related_party"}
    assert not (field_names & forbidden), (
        f"PartyProfile 出现关联方标志字段 {field_names & forbidden}，"
        f"但 config.RELATED_PARTY_CRITERIA 仍为 None"
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
