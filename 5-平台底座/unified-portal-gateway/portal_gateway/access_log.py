"""网关访问日志（spec portal-access-log）——复用平台 `zhuopin_platform.audit`。

复用 `AuditLogger` 而非另建一套日志格式：① 免费获得 append-only hash-chain
防篡改（IATF 可追溯）；② 与队列 #112 使用率埋点合并落地——`decision` 字段里
的 path/domain/tier/allowed 已是 #112 需要的统计维度，无需二次埋点。

只记录"谁在何时访问了什么资源"这一元信息，**不记录**被判定为敏感的字段
具体取值（本模块的函数签名从结构上就不接受任何页面内容/字段值参数，
不存在"手滑传进去"的可能）。
"""
from __future__ import annotations

from datetime import date

from zhuopin_platform.audit import AuditEvent, AuditLogger

from portal_gateway.permissions import PermissionTier

SCENARIO = "portal-gateway"
ACTION = "portal_access"
DEV_PERIOD_LABEL = "开发期"
OFFICIAL_PERIOD_LABEL = "正式统计"

UNAUTHENTICATED = "unauthenticated"
INSUFFICIENT_TIER = "insufficient_tier"
AUTHORIZED = "authorized"


def is_development_period(domain: str, start_dates: dict[str, str] | None, *, today: date | None = None) -> bool:
    """按《价值度量指标口径表》§〇bis 起算日规则判定。

    未配置该 domain 的起算日 —— 视为仍在开发期（保守默认：不确定就不计入
    正式统计，而不是反过来默认已起算）。
    """
    start_dates = start_dates or {}
    start_str = start_dates.get(domain)
    if not start_str:
        return True
    start = date.fromisoformat(start_str)
    current = today if today is not None else date.today()
    return current < start


def build_access_event(*, userid: str | None, domain: str, path: str,
                        tier_required: PermissionTier, tier_resolved: PermissionTier | None,
                        allowed: bool, auth_result: str,
                        start_dates: dict[str, str] | None = None,
                        today: date | None = None) -> AuditEvent:
    period = DEV_PERIOD_LABEL if is_development_period(domain, start_dates, today=today) else OFFICIAL_PERIOD_LABEL
    return AuditEvent(
        scenario=SCENARIO,
        action=ACTION,
        evaluator=userid or "(未登录)",
        automation_level="L1",
        decision={
            "path": path,
            "domain": domain,
            "tier_required": tier_required.name,
            "tier_resolved": tier_resolved.name if tier_resolved is not None else None,
            "allowed": allowed,
            "auth_result": auth_result,
            "period": period,
        },
    )


def record_access(logger: AuditLogger, **kwargs) -> None:
    logger.record(build_access_event(**kwargs))
