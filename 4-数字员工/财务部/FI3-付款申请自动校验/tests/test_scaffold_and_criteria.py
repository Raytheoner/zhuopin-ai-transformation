"""骨架与判据守卫：R1–R8 已签认且一条不多不少、PENDING 两项未签认读即抛、L3 恒定、审计带版本、日历口径。"""
from __future__ import annotations

from datetime import date

import pytest

from zhuopin_platform.criteria_signoff import CriterionNotSignedOffError

from fi3_payment_validation import config
from fi3_payment_validation.holiday_calendar import CalendarOutOfRangeError, HolidayCalendar
from fi3_payment_validation.models import mask_account

R_KEYS = ("R1_SEVERITY_MAP", "R2_ACCOUNT_RULES", "R3_DUPLICATE_PARAMS", "R4_CONTRACT_CAP",
          "R5_PREPAY_TIERS", "R6_TERM_CLAUSES", "R7_URGENT_CHANNEL", "R8_L4_PROMOTION_GATE")


def test_platform_bootstrap_importable():
    from zhuopin_platform import bootstrap  # noqa: F401
    from zhuopin_platform.audit import AuditLogger  # noqa: F401


def test_r1_to_r8_declared_and_all_signed_by_name():
    assert config.CRITERIA.keys() == R_KEYS
    assert config.CRITERIA.fully_signed
    for k in R_KEYS:
        c = config.CRITERIA.criterion(k)
        assert c.signoff.signed_by == "唐燕萍"
        assert "FI3-付款校验-就绪清单与MVP细化" in c.signoff.evidence
        assert c.signoff.rule_version == config.RULE_VERSION
    assert config.CRITERIA.criterion("R1_SEVERITY_MAP").signoff.signed_on == "2026-07-14"
    assert "unsigned" not in config.RULE_VERSION


def test_r4_provisional_lines_are_tangyanping_not_strawman():
    r4 = config.CRITERIA.value_of("R4_CONTRACT_CAP")
    assert (r4["provisional_warn_pct"], r4["provisional_block_pct"]) == (0.30, 0.50)


def test_r5_tiers_cover_zero_to_infinity_and_include_1m_tier():
    tiers = config.CRITERIA.value_of("R5_PREPAY_TIERS")["tiers"]
    assert tiers[0][0] == 0 and tiers[-1][1] is None
    assert all(tiers[i][1] == tiers[i + 1][0] for i in range(len(tiers) - 1))
    assert tiers[-1] == (1_000_000, None, "有合同", "总经理")


@pytest.mark.parametrize("key", ("PREPAY_AGEING_WARN_DAYS", "L4_PROMOTION_COSIGN"))
def test_pending_criteria_unsigned_read_raises(key):
    assert config.PENDING.is_signed(key) is False
    with pytest.raises(CriterionNotSignedOffError):
        config.PENDING.value_of(key)
    assert "unsigned" in config.PENDING_VERSION


def test_automation_level_is_l3_until_cosign():
    """🔴 停在档 1：L4 只能经 PENDING.L4_PROMOTION_COSIGN 签认后升。"""
    assert config.AUTOMATION_LEVEL == "L3"
    assert config.audit_decision(x=1) == {"x": 1, "rule_version": config.RULE_VERSION, "automation_level": "L3"}


def test_audit_decision_carries_rule_version_into_real_event():
    from zhuopin_platform.audit import AuditEvent
    ev = AuditEvent(scenario="FI3", action="payment_request_validate", evaluator="示例复核人",
                    automation_level="L3", decision=config.audit_decision(req_no="REQ-X"))
    assert ev.decision["rule_version"] == config.RULE_VERSION


def test_mask_account_keeps_last_4_only():
    assert mask_account("6222000000001111") == "************1111"
    assert mask_account("123") == "***"


# ── 节假日日历（就绪包 §二.2 三条口径）──

def test_calendar_is_the_745_row_table(calendar: HolidayCalendar):
    assert len(calendar) == 745
    assert (calendar.first, calendar.last) == (date(2026, 1, 1), date(2028, 1, 15))


def test_workday_read_from_column_not_derived(calendar: HolidayCalendar):
    assert calendar.is_workday(date(2026, 10, 10)) is True     # 调休上班（周六）——旧 33 天表会错顺延
    assert calendar.is_workday(date(2026, 10, 1)) is False     # 国庆
    assert calendar.is_workday(date(2026, 10, 11)) is False    # 周末
    assert calendar.roll_to_workday(date(2026, 10, 1)) == date(2026, 10, 8)
    assert calendar.roll_to_workday(date(2026, 10, 10)) == date(2026, 10, 10)


def test_calendar_out_of_range_fails_loud(calendar: HolidayCalendar):
    with pytest.raises(CalendarOutOfRangeError):
        calendar.is_workday(date(2028, 1, 16))
    with pytest.raises(CalendarOutOfRangeError):
        calendar.roll_to_workday(date(2028, 1, 16))
    with pytest.raises(CalendarOutOfRangeError):
        calendar.add_workdays(date(2028, 1, 10), 10)


def test_calendar_rejects_empty_or_dirty_flags(tmp_path):
    p = tmp_path / "cal.csv"
    p.write_text("日期,星期,节假日名称,日期类型,是否工作日\n2026-01-01,周四,元旦,节假日,maybe\n", encoding="utf-8")
    with pytest.raises(ValueError):
        HolidayCalendar.load(p)
    with pytest.raises(ValueError):
        HolidayCalendar({})
