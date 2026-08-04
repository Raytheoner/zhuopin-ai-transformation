"""portal_gateway.access_log 单测——覆盖 spec portal-access-log 全部 Scenario。"""
from __future__ import annotations

from datetime import date

from zhuopin_platform.audit import AuditLogger

from portal_gateway.access_log import (
    AUTHORIZED,
    INSUFFICIENT_TIER,
    UNAUTHENTICATED,
    build_access_event,
    is_development_period,
    record_access,
)
from portal_gateway.permissions import PermissionTier


# ── 通过/拒绝请求均留痕 ──────────────────────────────────────────────


def test_build_access_event_allowed_records_userid_and_path():
    event = build_access_event(
        userid="YaoZuYi", domain="portal", path="/index.html",
        tier_required=PermissionTier.PUBLIC_READ, tier_resolved=PermissionTier.DOMAIN_ADMIN,
        allowed=True, auth_result=AUTHORIZED,
    )
    assert event.scenario == "portal-gateway"
    assert event.action == "portal_access"
    assert event.evaluator == "YaoZuYi"
    assert event.decision["path"] == "/index.html"
    assert event.decision["allowed"] is True
    assert event.decision["auth_result"] == AUTHORIZED


def test_build_access_event_rejected_unauthenticated_still_records():
    event = build_access_event(
        userid=None, domain="portal", path="/index.html",
        tier_required=PermissionTier.PUBLIC_READ, tier_resolved=None,
        allowed=False, auth_result=UNAUTHENTICATED,
    )
    assert event.evaluator == "(未登录)"
    assert event.decision["allowed"] is False
    assert event.decision["auth_result"] == UNAUTHENTICATED


def test_build_access_event_rejected_insufficient_tier():
    event = build_access_event(
        userid="SomeMember", domain="finance", path="/finance/fi2",
        tier_required=PermissionTier.DOMAIN_ADMIN, tier_resolved=PermissionTier.DOMAIN_MEMBER,
        allowed=False, auth_result=INSUFFICIENT_TIER,
    )
    assert event.decision["allowed"] is False
    assert event.decision["tier_required"] == "DOMAIN_ADMIN"
    assert event.decision["tier_resolved"] == "DOMAIN_MEMBER"


# ── 敏感字段不进日志正文 ─────────────────────────────────────────────


def test_build_access_event_signature_has_no_field_value_parameter():
    import inspect

    params = set(inspect.signature(build_access_event).parameters)
    # 结构性保证：不存在任何可传入"页面内容/字段值"的参数名，日志天然
    # 不可能记录敏感字段明文（只能记录 path/domain/tier/allowed 等元信息）。
    forbidden = {"content", "value", "payload", "body", "field_value", "amount", "price"}
    assert not (params & forbidden)


# ── 开发期标记与起算日判定 ───────────────────────────────────────────


def test_is_development_period_true_when_no_start_date_configured():
    assert is_development_period("portal", {}) is True


def test_is_development_period_true_before_start_date():
    assert is_development_period("procurement", {"procurement": "2026-09-01"},
                                  today=date(2026, 8, 4)) is True


def test_is_development_period_false_after_start_date():
    assert is_development_period("procurement", {"procurement": "2026-07-01"},
                                  today=date(2026, 8, 4)) is False


def test_build_access_event_tags_development_period_by_default():
    event = build_access_event(
        userid="YaoZuYi", domain="portal", path="/", tier_required=PermissionTier.PUBLIC_READ,
        tier_resolved=PermissionTier.PUBLIC_READ, allowed=True, auth_result=AUTHORIZED,
    )
    assert event.decision["period"] == "开发期"


def test_build_access_event_tags_official_period_after_start_date():
    event = build_access_event(
        userid="YaoZuYi", domain="procurement", path="/procurement/baoguan",
        tier_required=PermissionTier.PUBLIC_READ, tier_resolved=PermissionTier.DOMAIN_ADMIN,
        allowed=True, auth_result=AUTHORIZED,
        start_dates={"procurement": "2026-07-01"}, today=date(2026, 8, 4),
    )
    assert event.decision["period"] == "正式统计"


# ── 落盘与 audit hash-chain（复用平台能力） ─────────────────────────────


def test_record_access_writes_to_audit_logger(tmp_path):
    logger = AuditLogger.jsonl(tmp_path / "portal_access.jsonl")
    record_access(
        logger, userid="YaoZuYi", domain="portal", path="/", tier_required=PermissionTier.PUBLIC_READ,
        tier_resolved=PermissionTier.PUBLIC_READ, allowed=True, auth_result=AUTHORIZED,
    )
    records = logger.query_by(scenario="portal-gateway")
    assert len(records) == 1
    assert records[0]["evaluator"] == "YaoZuYi"
    verify = logger.verify_chain()
    assert verify.ok is True
