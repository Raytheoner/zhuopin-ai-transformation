"""FO 预测订单 API 健康告警（内部运维告警，非对客）。

FO（LAN-only 真实预测订单源）不可达（502 / 超时 / 网络错误）时，除 **fail-loud**
（绝不静默回退 mock）外，本模块负责两件事：
  ① 写平台 audit（action=fo_unreachable, source=FO，IATF 可追溯）；
  ② 经 notifiers/wecom 推**内部**采购/值班群**文本**告警。

合规定位：这是**内部运维告警**（推内部群），**非对客外发**——因此不经对客 Notifier
的两道门禁（与 `config.CUSTOMER_OUTBOUND_ENABLED` 无关），低风险直推。告警动作本身
绝不吞掉原始 FO 异常：`alert_fo_unreachable` 不 re-raise，由调用方在告警后 re-raise，
保持 fail-loud。
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

_CST = timezone(timedelta(hours=8))

# 内部运维告警 webhook 来源（按序取第一个非空环境变量；缺失则只审计不推送）
OPS_WEBHOOK_ENV: tuple[str, ...] = ("SC8_FO_OPS_WEBHOOK_URL", "WECOM_WEBHOOK_URL")
ACTION_FO_UNREACHABLE = "fo_unreachable"


def _resolve_webhook(webhook_url: str | None) -> str:
    if webhook_url:
        return webhook_url
    for key in OPS_WEBHOOK_ENV:
        val = os.environ.get(key)
        if val:
            return val
    return ""


def build_alert_text(error, *, api_base: str = "") -> str:
    """构造内部运维告警文本（企微纯文本，简洁可转发）。"""
    ts = datetime.now(tz=_CST).strftime("%Y-%m-%d %H:%M")
    return (
        "【SC8 运维告警】FO 预测订单 API 不可达\n"
        f"时间：{ts}（CST）\n"
        f"端点：{api_base or '(默认/未指定)'}\n"
        f"错误：{error}\n"
        "影响：真实订单拉取失败、交付承诺无法刷新；已 fail-loud 停止，未回退 mock。\n"
        "请 IT/值班尽快检查 FO 服务（LAN）。"
    )


def alert_fo_unreachable(
    error,
    *,
    api_base: str = "",
    audit=None,
    webhook_url: str | None = None,
    send_fn=None,
) -> dict:
    """FO 不可达 → 审计留痕 + 内部企微告警。

    不吞、不抛原始 FO 异常（调用方负责 re-raise，保持 fail-loud）；告警自身的失败
    （审计/推送异常）被吞掉，绝不掩盖原始 FO 错误。

    Args:
        error:       捕获到的 FO 异常（或其文本）。
        api_base:    FO 端点（告警正文用）。
        audit:       平台 AuditLogger；None 则不留痕。
        webhook_url: 内部群 webhook；None 时按 OPS_WEBHOOK_ENV 取环境变量，仍缺则跳过推送。
        send_fn:     底层发送函数 (webhook, text)->None；None 时用 wecom.send_text（便于测试注入）。

    Returns:
        dict(audited, notified, webhook_configured) —— 供调用方/测试断言。
    """
    audited = False
    notified = False

    # ① 审计留痕（source=FO 不可达）
    if audit is not None:
        try:
            from zhuopin_platform.audit import AuditEvent
            audit.record(AuditEvent(
                scenario="SC8",
                action=ACTION_FO_UNREACHABLE,
                evaluator="",
                automation_level="L2",
                decision={
                    "source": "FO",
                    "reachable": False,
                    "api_base": api_base,
                    "error": str(error),
                },
                data_sources={"fo": "unreachable"},
                error=str(error),
            ))
            audited = True
        except Exception:
            pass  # 审计失败不掩盖原始 FO 错误

    # ② 内部企微运维告警（非对客，低风险直推）
    hook = _resolve_webhook(webhook_url)
    if hook:
        sender = send_fn
        if sender is None:
            from zhuopin_platform.shared_tools.notifiers import wecom
            sender = wecom.send_text
        try:
            sender(hook, build_alert_text(error, api_base=api_base))
            notified = True
        except Exception:
            pass  # 推送失败不掩盖原始 FO 错误（调用方仍会 re-raise）

    return {"audited": audited, "notified": notified, "webhook_configured": bool(hook)}
