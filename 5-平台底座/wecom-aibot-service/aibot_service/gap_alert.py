"""开发端监听中断告知（Paul 2026-07-16 要求）。

企微 aibot 协议没有离线消息补推能力——监听断线期间发来的消息永久丢失，
无法找回。本模块不试图"重传"（技术上不可能），只做**如实告知**。

2026-07-19 真实事故：`send_gap_alert` 发送提醒时，恰好是企微连接本身仍在
故障恢复的窗口期（网络反复抖动），发送本身也失败——此前没有重试/兜底，
Paul 完全收不到"已恢复"通知（审计留了 `gap_alert_send_failed`，但无人看
得到）。修复：主通道（同一条企微连接）失败时，若调用方提供
`fallback_send`（走独立的群 webhook 通道，不依赖同一条故障连接），尝试
兜底发送一次；全程失败也不抛出（告警本身不应影响服务继续运行）。

队列 #147（2026-07-29 "中断约 79 分钟"误报事故后修复）：`format_alert`/
`build_reconnect_notice` 判据此前用"距上次**审计事件**的时长"当"中断
时长"——但审计是"有事才写"，不是"活着就写"：周末无人发消息、服务全程
健康，下次重启仍会被误判成"中断数千分钟"。真断线与长时间空闲在审计
日志里长得一模一样，看多了必然被当噪音忽略，等真断线时反而漏判。

**修复**：判据改为"距上次**确认存活**"——调用方在建连*前*改用
`aibot_service.liveness.read_liveness` 读一个独立的存活戳文件（`liveness.py`
每 5 分钟覆写一次，与业务消息量无关），把这个时间戳传给 `format_alert`/
`build_reconnect_notice`（两者的第一个参数语义从此变为"上次确认存活"，
不再是"上次审计事件"）；原来基于审计事件的 `last_event_timestamp` 仍然
保留，改传给 `build_reconnect_notice` 的新参数 `last_event_at`，只用于
**非告警分支的纯信息展示**（"距上次有人发消息约 X"），不再影响是否触发
"消息可能丢失"这条警示——两个数回答的是不同问题，不应混为一谈。
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
    """`last_ts` 为 None（首次启动，无历史可比对）或间隔未超阈值时返回 None。

    `last_ts` 语义（队列 #147）：调用方应传"上次确认存活"的时间戳（见
    `liveness.read_liveness`），而非"上次审计事件"——本函数只负责按给定
    时间戳格式化文案，不关心其来源，但生产路径的正确用法是前者，否则
    空闲期会被误判成中断（见模块 docstring）。
    """
    if last_ts is None:
        return None
    gap_seconds = (now - last_ts).total_seconds()
    if gap_seconds <= threshold_seconds:
        return None
    gap_minutes = int(gap_seconds // 60)
    window = f"{last_ts.strftime('%H:%M')}–{now.strftime('%H:%M UTC')}"
    return (
        f"监听已恢复。真实断线约 {gap_minutes} 分钟（{window}）。"
        f"企微没有离线消息补推能力，这段时间的来件不会补推，如有请让对方重发。"
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


def _format_duration(seconds: float) -> str:
    """把秒数格式化成人可读的粗粒度时长（用于非告警分支的"距上次有人发
    消息"信息展示，不追求精确到秒——那是纯背景信息，不是判据）。"""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds} 秒"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} 分钟"
    return f"{minutes // 60} 小时"


def build_reconnect_notice(
    last_alive_at: Optional[datetime],
    now: datetime,
    threshold_seconds: int = DEFAULT_THRESHOLD_SECONDS,
    *,
    last_event_at: Optional[datetime] = None,
) -> str:
    """每次(重)连接都生成一条通报文案（Paul 2026-07-19 要求：不管中断长短，
    每次都要收到确认消息，而不是只在超阈值时收到警示）。`format_alert`
    仍保留"None=无需警示"的原语义不变；本函数在其返回 None 时补一句轻量
    的"已恢复/已启动"文案，两者内容不同——超阈值那句带"消息可能丢失"的
    警示措辞，轻量那句不带（短间隔不存在消息丢失风险）。

    `last_alive_at`（队列 #147 起）：**上次确认存活**的时间戳（来自
    `liveness.read_liveness`），决定是否触发"真实断线"警示——这是唯一
    影响告警与否的输入。

    `last_event_at`：上次审计事件（业务消息）的时间戳，**纯信息展示**，
    只出现在"未超阈值"分支里作为背景说明（"距上次有人发消息约 X，属正常
    空闲"），不参与、也不影响是否触发警示——空闲多久都不该被当成中断。
    """
    warning = format_alert(last_alive_at, now, threshold_seconds)
    if warning is not None:
        return warning
    if last_alive_at is None:
        return "监听已启动（首次运行，无存活戳可比对）。"
    gap_seconds = int((now - last_alive_at).total_seconds())
    idle_note = ""
    if last_event_at is not None:
        idle_note = (
            f"（距上次有人发消息约 {_format_duration((now - last_event_at).total_seconds())}"
            f"，属正常空闲。）"
        )
    return f"监听已恢复，断线约 {gap_seconds} 秒。期间无消息丢失风险。{idle_note}"


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
