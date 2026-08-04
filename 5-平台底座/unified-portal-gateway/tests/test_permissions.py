"""portal_gateway.permissions 单测——覆盖 spec portal-permission-model 全部 Scenario。"""
from __future__ import annotations

import textwrap

import pytest

from portal_gateway.permissions import (
    PermissionTier,
    has_access,
    is_sensitive_field_visible,
    load_department_mapping,
    resolve_tier,
)


@pytest.fixture
def mapping():
    return {
        "YaoZuYi": [{"domain": "procurement", "tier": PermissionTier.DOMAIN_ADMIN}],
        "tangyanping": [{"domain": "finance", "tier": PermissionTier.DOMAIN_ADMIN}],
        "SomeMember": [{"domain": "procurement", "tier": PermissionTier.DOMAIN_MEMBER}],
        "ShaoPeiShen": [{"domain": "*", "tier": PermissionTier.DOMAIN_ADMIN}],
    }


# ── 三层权限判定 ──────────────────────────────────────────────────────


def test_public_read_for_unmapped_userid(mapping):
    tier = resolve_tier(mapping, "SomeRandomEmployee", domain="procurement")
    assert tier == PermissionTier.PUBLIC_READ


def test_public_read_for_none_userid(mapping):
    assert resolve_tier(mapping, None, domain="procurement") == PermissionTier.PUBLIC_READ


def test_domain_member_can_view_own_domain(mapping):
    tier = resolve_tier(mapping, "SomeMember", domain="procurement")
    assert tier == PermissionTier.DOMAIN_MEMBER
    assert has_access(PermissionTier.DOMAIN_MEMBER, tier) is True


def test_domain_admin_can_execute_operations_and_see_sensitive(mapping):
    tier = resolve_tier(mapping, "YaoZuYi", domain="procurement")
    assert tier == PermissionTier.DOMAIN_ADMIN
    assert has_access(PermissionTier.DOMAIN_ADMIN, tier) is True
    assert is_sensitive_field_visible(tier) is True


def test_non_domain_member_rejected_for_other_domain(mapping):
    # SomeMember 只在 procurement 登记，访问 finance 应 fail-closed 降级
    tier = resolve_tier(mapping, "SomeMember", domain="finance")
    assert tier == PermissionTier.PUBLIC_READ
    assert has_access(PermissionTier.DOMAIN_MEMBER, tier) is False


def test_wildcard_domain_admin_applies_to_any_domain(mapping):
    for domain in ("procurement", "finance", "quality", "sales", "anything-new"):
        tier = resolve_tier(mapping, "ShaoPeiShen", domain=domain)
        assert tier == PermissionTier.DOMAIN_ADMIN


def test_sensitive_field_hidden_for_domain_member(mapping):
    tier = resolve_tier(mapping, "SomeMember", domain="procurement")
    assert is_sensitive_field_visible(tier) is False


def test_tier_ordering_is_comparable():
    assert PermissionTier.PUBLIC_READ < PermissionTier.DOMAIN_MEMBER < PermissionTier.DOMAIN_ADMIN


# ── 部门映射表加载（手工文件，不取企微通讯录） ─────────────────────────


def test_load_department_mapping_parses_yaml(tmp_path):
    f = tmp_path / "department_mapping.yaml"
    f.write_text(
        textwrap.dedent(
            """
            YaoZuYi:
              - { domain: procurement, tier: domain_admin }
            SomeMember:
              - { domain: procurement, tier: domain_member }
            """
        ),
        encoding="utf-8",
    )
    mapping = load_department_mapping(f)
    assert mapping["YaoZuYi"] == [{"domain": "procurement", "tier": PermissionTier.DOMAIN_ADMIN}]
    assert mapping["SomeMember"] == [{"domain": "procurement", "tier": PermissionTier.DOMAIN_MEMBER}]


def test_load_department_mapping_missing_file_returns_empty(tmp_path):
    mapping = load_department_mapping(tmp_path / "does-not-exist.yaml")
    assert mapping == {}


def test_load_department_mapping_unknown_tier_raises(tmp_path):
    f = tmp_path / "bad.yaml"
    f.write_text("SomeUser:\n  - { domain: procurement, tier: super_admin }\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_department_mapping(f)


def test_load_default_packaged_mapping_includes_known_seed_users():
    mapping = load_department_mapping()
    assert resolve_tier(mapping, "YaoZuYi", domain="procurement") == PermissionTier.DOMAIN_ADMIN
    assert resolve_tier(mapping, "tangyanping", domain="finance") == PermissionTier.DOMAIN_ADMIN
    assert resolve_tier(mapping, "ChenChen", domain="quality") == PermissionTier.DOMAIN_ADMIN
    assert resolve_tier(mapping, "ShaoPeiShen", domain="procurement") == PermissionTier.DOMAIN_ADMIN
    assert resolve_tier(mapping, "ShaoPeiShen", domain="quality") == PermissionTier.DOMAIN_ADMIN
    # 未登记用户 fail-closed
    assert resolve_tier(mapping, "SomeoneNotListed", domain="procurement") == PermissionTier.PUBLIC_READ
