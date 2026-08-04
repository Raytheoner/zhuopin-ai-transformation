from datetime import datetime, timedelta, timezone

import pytest

from zhuopin_platform.audit import AuditLogger

from aibot_service.approval import (
    ApprovalCooldownError,
    approve_followup_letter,
    check_cooldown,
)
from aibot_service.readme_table import DraftNotPendingReviewError

README_TEXT = """\
## 现有跟进信清单

| 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |
|------|--------|---------|---------|---------|
| 2026-08-05 | 采购部 · 姚祖怡 | 测试批准事项 | 不急 | ⏳ 待你审 |
| 2026-08-04 | 质量部 · 陈忱 | 已发信 | 不急 | ✅ 已发 |
"""

NOW = datetime(2026, 8, 5, 3, 0, tzinfo=timezone.utc)


def _match_test_topic(cells):
    return "测试批准事项" in cells[2]


def _setup(tmp_path, readme_text=README_TEXT):
    readme_path = tmp_path / "README.md"
    readme_path.write_text(readme_text, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    cooldown_state_path = tmp_path / "cooldown_state.json"
    return readme_path, audit, cooldown_state_path


def test_approve_requires_quote(tmp_path):
    readme_path, audit, cooldown_state_path = _setup(tmp_path)
    with pytest.raises(ValueError):
        approve_followup_letter(
            readme_path=readme_path, match=_match_test_topic, quote="   ",
            audit=audit, cooldown_state_path=cooldown_state_path, now=NOW,
        )


def test_approve_rejects_non_draft_row(tmp_path):
    readme_path, audit, cooldown_state_path = _setup(tmp_path)

    def _match_already_sent(cells):
        return "已发信" in cells[2]

    with pytest.raises(DraftNotPendingReviewError):
        approve_followup_letter(
            readme_path=readme_path, match=_match_already_sent, quote="Shao Peishen: 可以发",
            audit=audit, cooldown_state_path=cooldown_state_path, now=NOW,
        )
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "followup_approval_rejected" in actions


def test_approve_first_call_is_rejected_by_cooldown_and_records_first_seen(tmp_path):
    readme_path, audit, cooldown_state_path = _setup(tmp_path)

    with pytest.raises(ApprovalCooldownError):
        approve_followup_letter(
            readme_path=readme_path, match=_match_test_topic, quote="Shao Peishen: 可以发",
            audit=audit, cooldown_state_path=cooldown_state_path, now=NOW,
        )

    # README 未被改动（批准被冷却窗口拒绝，不应有任何写入发生）
    assert "🆕 待发" not in readme_path.read_text(encoding="utf-8")
    assert cooldown_state_path.exists()
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "followup_approval_rejected" in actions


def test_approve_succeeds_after_cooldown_elapsed(tmp_path):
    readme_path, audit, cooldown_state_path = _setup(tmp_path)

    with pytest.raises(ApprovalCooldownError):
        approve_followup_letter(
            readme_path=readme_path, match=_match_test_topic, quote="Shao Peishen: 可以发",
            audit=audit, cooldown_state_path=cooldown_state_path, now=NOW,
        )

    later = NOW + timedelta(minutes=11)
    result = approve_followup_letter(
        readme_path=readme_path, match=_match_test_topic, quote="Shao Peishen: 可以发",
        audit=audit, cooldown_state_path=cooldown_state_path, now=later,
    )

    assert result.new_status == "🆕 待发"
    new_text = readme_path.read_text(encoding="utf-8")
    assert "🆕 待发" in new_text
    assert "⏳ 待你审" not in new_text
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "followup_approved" in actions
    approved_events = [r for r in audit.query_by(scenario="wecom-aibot") if r["action"] == "followup_approved"]
    assert approved_events[0]["decision"]["quote"] == "Shao Peishen: 可以发"


def test_approve_still_blocked_before_cooldown_elapses(tmp_path):
    readme_path, audit, cooldown_state_path = _setup(tmp_path)

    with pytest.raises(ApprovalCooldownError):
        approve_followup_letter(
            readme_path=readme_path, match=_match_test_topic, quote="Shao Peishen: 可以发",
            audit=audit, cooldown_state_path=cooldown_state_path, now=NOW,
        )

    almost_there = NOW + timedelta(minutes=5)
    with pytest.raises(ApprovalCooldownError):
        approve_followup_letter(
            readme_path=readme_path, match=_match_test_topic, quote="Shao Peishen: 可以发",
            audit=audit, cooldown_state_path=cooldown_state_path, now=almost_there,
        )
    assert "🆕 待发" not in readme_path.read_text(encoding="utf-8")


def test_check_cooldown_custom_minutes(tmp_path):
    state_path = tmp_path / "state.json"
    with pytest.raises(ApprovalCooldownError):
        check_cooldown(state_path, "row-a", now=NOW, cooldown_minutes=1)
    # 1 分钟冷却，40 秒后仍应拒绝
    with pytest.raises(ApprovalCooldownError):
        check_cooldown(state_path, "row-a", now=NOW + timedelta(seconds=40), cooldown_minutes=1)
    # 61 秒后应通过（不抛异常）
    check_cooldown(state_path, "row-a", now=NOW + timedelta(seconds=61), cooldown_minutes=1)


def test_check_cooldown_tracks_rows_independently(tmp_path):
    state_path = tmp_path / "state.json"
    with pytest.raises(ApprovalCooldownError):
        check_cooldown(state_path, "row-a", now=NOW, cooldown_minutes=10)
    # 不同行身份互不影响，row-b 仍是"首次观测"
    with pytest.raises(ApprovalCooldownError):
        check_cooldown(state_path, "row-b", now=NOW + timedelta(minutes=11), cooldown_minutes=10)
    # row-a 已过冷却期，row-b 尚未
    check_cooldown(state_path, "row-a", now=NOW + timedelta(minutes=11), cooldown_minutes=10)
    with pytest.raises(ApprovalCooldownError):
        check_cooldown(state_path, "row-b", now=NOW + timedelta(minutes=15), cooldown_minutes=10)
