"""三层权限判定（决策件 §五决策3，design.md 决策5，spec portal-permission-model）。

三层：公开只读（PUBLIC_READ）< 域成员（DOMAIN_MEMBER）< 域管理员（DOMAIN_ADMIN），
按手工维护的 `department_mapping.yaml` 判定；未登记 userid 或域不匹配一律
fail-closed 降级为 PUBLIC_READ，不默认授予任何域权限。

起步阶段刻意不做字段级细粒度权限或跨域审批流——本模块只暴露"三层判定"
这一个能力，没有更细的配置项（spec Requirement「起步阶段不做细粒度字段级
权限与跨域审批流」）。
"""
from __future__ import annotations

from enum import IntEnum
from pathlib import Path
from typing import Any

import yaml

WILDCARD_DOMAIN = "*"

_DEFAULT_MAPPING_PATH = Path(__file__).resolve().parent / "department_mapping.yaml"


class PermissionTier(IntEnum):
    """数值越大权限越高，可直接用 >= 比较（design.md 决策5）。"""

    PUBLIC_READ = 0
    DOMAIN_MEMBER = 1
    DOMAIN_ADMIN = 2


_TIER_BY_NAME = {
    "public_read": PermissionTier.PUBLIC_READ,
    "domain_member": PermissionTier.DOMAIN_MEMBER,
    "domain_admin": PermissionTier.DOMAIN_ADMIN,
}


def _parse_tier(raw: str) -> PermissionTier:
    try:
        return _TIER_BY_NAME[raw]
    except KeyError:
        raise ValueError(
            f"department_mapping.yaml 出现未知 tier 取值：{raw!r}（仅接受 "
            f"{sorted(_TIER_BY_NAME)}）"
        ) from None


def load_department_mapping(path: Path | str | None = None) -> dict[str, list[dict[str, Any]]]:
    """加载并规范化部门映射表；`tier` 字段转为 `PermissionTier` 枚举。

    格式见 `department_mapping.yaml`：``{userid: [{domain, tier}, ...]}``。
    空文件/文件不存在时返回空映射（等价于全体用户 fail-closed 到公开只读）。
    """
    target = Path(path) if path is not None else _DEFAULT_MAPPING_PATH
    if not target.exists():
        return {}
    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    mapping: dict[str, list[dict[str, Any]]] = {}
    for userid, entries in raw.items():
        mapping[str(userid)] = [
            {"domain": str(e["domain"]), "tier": _parse_tier(str(e["tier"]))}
            for e in (entries or [])
        ]
    return mapping


def resolve_tier(mapping: dict[str, list[dict[str, Any]]], userid: str | None, domain: str) -> PermissionTier:
    """判定某 userid 在指定 domain 下的权限层级。

    fail-closed：userid 为空/未登记/映射表中无该 domain（且无通配 "*"）条目，
    一律返回 `PUBLIC_READ`，不猜测、不默认授予域权限。
    """
    if not userid:
        return PermissionTier.PUBLIC_READ
    entries = mapping.get(userid)
    if not entries:
        return PermissionTier.PUBLIC_READ
    best = PermissionTier.PUBLIC_READ
    for entry in entries:
        if entry["domain"] in (domain, WILDCARD_DOMAIN):
            if entry["tier"] > best:
                best = entry["tier"]
    return best


def has_access(required: PermissionTier, resolved: PermissionTier) -> bool:
    """resolved 层级是否满足 required 层级的最低要求。"""
    return resolved >= required


def is_sensitive_field_visible(resolved: PermissionTier) -> bool:
    """敏感字段判据的落地开关——仅域管理员及以上可见（决策件 §五决策3 判据）。"""
    return resolved >= PermissionTier.DOMAIN_ADMIN
