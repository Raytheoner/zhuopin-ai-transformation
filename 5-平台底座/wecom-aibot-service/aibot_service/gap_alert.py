"""开发端监听中断告知（Paul 2026-07-16 要求）。

企微 aibot 协议没有离线消息补推能力——监听断线期间发来的消息永久丢失，
无法找回。本模块不试图"重传"（技术上不可能），只做**如实告知**：调用方在
建连*前*用 `last_event_timestamp` 读一次审计日志最后一条事件的时间戳
（建连本身会写新的审计事件，若建连*后*才读会读到刚写入的"连接成功"事件
本身，间隔恒为 0），建连成功后用 `format_alert` 判断间隔是否超阈值、生成
私信文案发给 Paul。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

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
