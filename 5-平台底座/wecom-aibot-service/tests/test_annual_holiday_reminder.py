"""队列 #379：`aibot_service.annual_holiday_reminder` 纯逻辑层单测。

I/O（连接/发送/CLI）在 `scripts/annual_holiday_reminder.py`，不在本文件
覆盖范围内（同 `test_decision_reminder.py` 只测 `decision_reminder.py`
的既有分工）。
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from aibot_service.annual_holiday_reminder import (
    LI_JIAOLONG_USERID,
    AdmissionCheck,
    already_sent_for_year,
    check_admission,
    format_reminder_message,
    is_trigger_day,
    load_state,
    next_target_year,
    save_state,
    should_send,
)


class TestIsTriggerDay:
    def test_true_on_sept_1(self):
        assert is_trigger_day(date(2026, 9, 1)) is True

    def test_false_on_other_days(self):
        assert is_trigger_day(date(2026, 8, 31)) is False
        assert is_trigger_day(date(2026, 9, 2)) is False
        assert is_trigger_day(date(2027, 9, 1)) is True  # 年份不影响判定

    def test_month_day_override(self):
        assert is_trigger_day(date(2026, 3, 15), month=3, day=15) is True


class TestAlreadySentForYear:
    def test_empty_state_is_false(self):
        assert already_sent_for_year({}, date(2026, 9, 1)) is False

    def test_matches_same_year(self):
        assert already_sent_for_year({"last_sent_year": 2026}, date(2026, 9, 1)) is True

    def test_does_not_match_different_year(self):
        assert already_sent_for_year({"last_sent_year": 2025}, date(2026, 9, 1)) is False


class TestShouldSend:
    def test_trigger_day_first_time_sends(self):
        assert should_send(date(2026, 9, 1), {}) is True

    def test_trigger_day_already_sent_does_not_resend(self):
        assert should_send(date(2026, 9, 1), {"last_sent_year": 2026}) is False

    def test_non_trigger_day_does_not_send(self):
        assert should_send(date(2026, 8, 31), {}) is False

    def test_force_overrides_everything(self):
        assert should_send(date(2026, 8, 31), {"last_sent_year": 2026}, force=True) is True

    def test_force_on_already_sent_trigger_day_still_sends(self):
        # 队列 #379 B-1(a)：明天人工执行首触发——须能在"今年已发过"状态下
        # 仍可强制重发（例如首次尝试失败后需重试）。
        assert should_send(date(2026, 9, 1), {"last_sent_year": 2026}, force=True) is True


class TestNextTargetYear:
    def test_returns_year_plus_one(self):
        assert next_target_year(date(2026, 9, 1)) == 2027
        assert next_target_year(date(2026, 8, 31)) == 2027  # 与触发日无关，纯年份+1


class TestFormatReminderMessage:
    def test_default_template_includes_year(self):
        msg = format_reminder_message(2027)
        assert "2027" in msg
        assert "李姣龙" not in msg  # 文案面向她本人发送，不在正文里提及收件人姓名

    def test_custom_template(self):
        assert format_reminder_message(2028, template="要 {next_year} 年的表") == "要 2028 年的表"


class TestCheckAdmission:
    def test_both_pass(self):
        result = check_admission({"某某": LI_JIAOLONG_USERID}, lambda u: True)
        assert result == AdmissionCheck(outbound_ok=True, inbound_ok=True)
        assert result.passed is True

    def test_outbound_missing_blocks(self):
        result = check_admission({}, lambda u: True)
        assert result.outbound_ok is False
        assert result.passed is False

    def test_inbound_missing_blocks(self):
        # 队列 #380 历史真实形态：出站已通、入站仍未放行——回复会被
        # fail-closed 静默挡回，故任一不通都不得发送。
        result = check_admission({"某某": LI_JIAOLONG_USERID}, lambda u: False)
        assert result.inbound_ok is False
        assert result.passed is False

    def test_checks_the_right_userid(self):
        seen = {}

        def spy(userid: str) -> bool:
            seen["userid"] = userid
            return True

        check_admission({"某某": LI_JIAOLONG_USERID}, spy)
        assert seen["userid"] == LI_JIAOLONG_USERID


class TestStateRoundTrip:
    def test_missing_file_returns_empty_dict(self, tmp_path: Path):
        assert load_state(tmp_path / "does-not-exist.json") == {}

    def test_save_then_load_round_trips(self, tmp_path: Path):
        path = tmp_path / "nested" / "state.json"
        save_state(path, {"last_sent_year": 2026, "last_target_year": 2027})
        assert load_state(path) == {"last_sent_year": 2026, "last_target_year": 2027}

    def test_corrupt_file_returns_empty_dict_not_raise(self, tmp_path: Path):
        path = tmp_path / "state.json"
        path.write_text("{not valid json", encoding="utf-8")
        assert load_state(path) == {}
