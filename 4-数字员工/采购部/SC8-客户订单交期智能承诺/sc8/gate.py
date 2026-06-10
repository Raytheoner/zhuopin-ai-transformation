"""L2 对客门禁判定（design 门禁红线 + spec delivery-commitment-gate）。

判定一条交付预期对客通报是否**必须人工确认、不自动外发**。强制确认情形（任一命中）：
  · 低置信（confidence == 低）；
  · 关键路径物料无反馈（无反馈物料非空 → 已并入低置信，这里再显式列原因）；
  · 预期交付晚于客户目标日（delay_days > 0 或 无法预测）；
  · 首次给某客户做交付承诺（查 audit 历史无成功外发记录）。

fail-closed 由平台 Notifier 保证（缺 requires_confirmation 字段默认拦截）；本模块负责
把以上业务规则落成 requires_confirmation=True，并给出可审计的拦截原因。
"""
from __future__ import annotations

from zhuopin_platform.audit import AuditLogger

from .models import CONFIDENCE_LOW, DeliveryForecast

ACTION_SEND = "notification_send"


def is_first_commitment(audit: AuditLogger | None, customer_name: str) -> bool:
    """该客户此前是否从未成功外发过交付承诺（首次 = 需 L2 确认）。

    无审计器 → 保守视为首次（fail-closed 偏保守，符合门禁）。
    """
    if audit is None:
        return True
    prior = audit.query_by(scenario="SC8", action=ACTION_SEND)
    for r in prior:
        decision = r.get("decision", {}) or {}
        if decision.get("recipient") == customer_name and decision.get("sent") is True:
            return False
    return True


def evaluate(fc: DeliveryForecast, *, first_commitment: bool) -> tuple[bool, list[str], str]:
    """对一条交付预期做门禁判定。

    Returns:
        (requires_confirmation, reasons, severity)
        requires_confirmation: True → 必须 L2 人工确认，不自动外发
        reasons: 触发原因（写入审计/草稿，可追溯）
        severity: info / warning / critical（晚于目标日或无法预测 → critical）
    """
    reasons: list[str] = []

    if fc.confidence == CONFIDENCE_LOW:
        reasons.append(f"低置信（{fc.confidence_reason}）")

    late = (fc.delay_days is not None and fc.delay_days > 0) or fc.forecast_date is None
    if late:
        if fc.forecast_date is None:
            reasons.append("无法预测交付日（物料未齐套）")
        else:
            reasons.append(f"预期交付晚于客户目标日 {fc.delay_days} 天")

    if first_commitment:
        reasons.append("首次给该客户做交付承诺")

    requires_confirmation = bool(reasons)
    severity = "critical" if late else ("warning" if requires_confirmation else "info")
    return requires_confirmation, reasons, severity
