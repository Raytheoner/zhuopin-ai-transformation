"""开发端监听中断告知（Paul 2026-07-16 要求）。

企微 aibot 协议没有离线消息补推能力——监听断线期间发来的消息永久丢失，
无法找回。本模块不试图"重传"（技术上不可能），只做**如实告知**：调用方在
建连*前*用 `last_event_timestamp` 读一次审计日志最后一条事件的时间戳
（建连本身会写新的审计事件，若建连*后*才读会读到刚写入的"连接成功"事件
本身，间隔恒为 0），建连成功后用 `format_alert` 判断间隔是否超阈值、生成
私信文案发给 Paul。

2026-07-19 真实事故：`send_gap_alert` 发送提醒时，恰好是企微连接本身仍在
故障恢复的窗口期（网络反复抖动），发送本身也失败——此前没有重试/兜底，
Paul 完全收不到"已恢复"通知（审计留了 `gap_alert_send_failed`，但无人看
得到）。修复：主通道（同一条企微连接）失败时，若调用方提供
`fallback_send`（走独立的群 webhook 通道，不依赖同一条故障连接），尝试
兜底发送一次；全程失败也不抛出（告警本身不应影响服务继续运行）。
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger

DEFAULT_THRESHOLD_SECONDS = 180  # 3 分钟——短于此判定为正常重连抖动，不告警


def last_event_timestamp(audit_path: Path) -> Optional[datetime]:
    """审计日志最后一条事件的时间戳；文件不存在/为空/格式异常均返回 None。"""
    if not audit_path.exists():
        return None
    last_line: Optional[str] = None
    with audit_path.open(encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                last_line = stripped
    if last_line is None:
        return None
    try:
        record = json.loads(last_line)
    except json.JSONDecodeError:
        return None
    ts = record.get("timestamp")
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def format_alert(
    last_ts: Optional[datetime],
    now: datetime,
    threshold_seconds: int = DEFAULT_THRESHOLD_SECONDS,
) -> Optional[str]:
    """`last_ts` 为 None（首次启动，无历史可比对）或间隔未超阈值时返回 None。"""
    if last_ts is None:
        return None
    gap_seconds = (now - last_ts).total_seconds()
    if gap_seconds <= threshold_seconds:
        return None
    gap_minutes = int(gap_seconds // 60)
    return (
        f"监听已恢复。上次活动时间：{last_ts.strftime('%Y-%m-%d %H:%M UTC')}，"
        f"中断约 {gap_minutes} 分钟。企微没有离线消息补推能力，这段时间如果有人发过消息，"
        f"机器人不会收到——如需要，请让对方确认一下、必要时重发。"
    )


def check_gap_and_format_alert(
    audit_path: Path,
    now: datetime,
    threshold_seconds: int = DEFAULT_THRESHOLD_SECONDS,
) -> Optional[str]:
    """便捷组合：文件未变动（如离线诊断/测试场景）时可一次性用。
    服务主流程请分开调用 `last_event_timestamp`（建连前）+ `format_alert`（建连后）。
    """
    return format_alert(last_event_timestamp(audit_path), now, threshold_seconds)


def build_reconnect_notice(
    last_ts: Optional[datetime],
    now: datetime,
    threshold_seconds: int = DEFAULT_THRESHOLD_SECONDS,
) -> str:
    """每次(重)连接都生成一条通报文案（Paul 2026-07-19 要求：不管中断长短，
    每次都要收到确认消息，而不是只在超阈值时收到警示）。`format_alert`
    仍保留"None=无需警示"的原语义不变；本函数在其返回 None 时补一句轻量
    的"已恢复/已启动"文案，两者内容不同——超阈值那句带"消息可能丢失"的
    警示措辞，轻量那句不带（短间隔不存在消息丢失风险）。
    """
    warning = format_alert(last_ts, now, threshold_seconds)
    if warning is not None:
        return warning
    if last_ts is None:
        return "监听已启动（首次运行，无历史活动记录可比对）。"
    gap_seconds = int((now - last_ts).total_seconds())
    return f"监听已恢复，距上次活动约 {gap_seconds} 秒，无明显中断。"


async def send_gap_alert(
    connector,
    audit: AuditLogger,
    alert_text: str,
    recipient: str,
    *,
    fallback_send: Optional[Callable[[str], None]] = None,
    last_event_at: str = "",
) -> None:
    """发送"监听已恢复"提醒。主通道（企微智能机器人私信，走 `connector`）
    失败时，若提供 `fallback_send`（同步函数，走独立的群 webhook 通道），
    在线程池里调用一次兜底；`fallback_send` 本身失败也不向上抛出。
    `last_event_at`：审计留痕用，断线前最后一条事件的时间戳（ISO 格式）。
    """
    try:
        await connector.send_markdown(recipient, f"ℹ️ {alert_text}")
    except Exception:  # noqa: BLE001 — 告警失败不应阻塞服务本身运行
        audit.record(AuditEvent(
            scenario="wecom-aibot", action="gap_alert_send_failed", evaluator="system",
            automation_level="L1", decision={"sent": False},
            data_sources={"last_event_at": last_event_at},
        ))
        if fallback_send is None:
            return
        try:
            await asyncio.to_thread(fallback_send, alert_text)
        except Exception:  # noqa: BLE001
            audit.record(AuditEvent(
                scenario="wecom-aibot", action="gap_alert_fallback_failed", evaluator="system",
                automation_level="L1", decision={"sent": False}, data_sources={},
            ))
        else:
            audit.record(AuditEvent(
                scenario="wecom-aibot", action="gap_alert_fallback_sent", evaluator="system",
                automation_level="L1", decision={"sent": True, "channel": "webhook"}, data_sources={},
            ))
        return
    audit.record(AuditEvent(
        scenario="wecom-aibot", action="gap_alert_sent", evaluator="system",
        automation_level="L1", decision={"sent": True, "recipient": recipient},
        data_sources={"last_event_at": last_event_at},
    ))
