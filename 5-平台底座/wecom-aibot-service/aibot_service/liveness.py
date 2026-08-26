"""存活戳：与业务消息量无关的"服务确实还活着"信号（队列 #147）。

`gap_alert.py` 此前唯一能拿到的时间基准是审计 JSONL 最后一条**事件**的
时间戳——但审计是"有事才写"，不是"活着就写"：周末无人发消息、服务全程
健康，审计文件照样几十小时不增长，下次重启就会被误判成"中断数千分钟"
（2026-07-29 15:38 那次"中断约 79 分钟"误报即是此类假象）。真断线与
长时间空闲在审计日志里长得一模一样，看多了必然被当噪音忽略，等真断线
时反而漏判——这正是本模块要堵的缺口。

做法：连接存活期间每 `DEFAULT_LIVENESS_INTERVAL_SECONDS`（5 分钟）覆写一次
独立的存活戳文件（单文件覆写，非追加——体积恒定、无清理负担；进程被杀时
最后一次写入天然就是"最后确认活着"的时刻，语义正确）。**刻意不写进审计
JSONL**：审计有 hash 防篡改链（队列 #126 统一并重算过），每天 288 条心跳
会稀释可追溯性、拖慢 `verify_chain()`，且心跳是运行状态、不是"AI 决策"，
本不该按 IATF 口径进审计——存活戳与审计是两回事，物理隔离开。
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger

from .error_text import describe_exception

DEFAULT_LIVENESS_INTERVAL_SECONDS = 300  # 5 分钟


def write_liveness(path: Path, now: datetime) -> None:
    """覆写存活戳文件；父目录不存在时先建好。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"alive_at": now.isoformat()}, ensure_ascii=False),
        encoding="utf-8",
    )


def read_liveness(path: Path) -> Optional[datetime]:
    """读存活戳；文件不存在/内容损坏/字段缺失/时间格式非法一律返回 None
    （视同"无存活戳可比对"，回落 `gap_alert` 的"首次运行"文案，不抛异常
    ——存活戳读取失败不应影响服务正常连接/告警流程）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(text)
        return datetime.fromisoformat(data["alive_at"])
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return None


async def run_liveness_heartbeat(
    path: Path,
    *,
    interval_seconds: float = DEFAULT_LIVENESS_INTERVAL_SECONDS,
    audit: Optional[AuditLogger] = None,
    evaluator: str = "system",
    _sleep: Callable[[float], "asyncio.Future"] = asyncio.sleep,
) -> None:
    """常驻后台任务：立即写一次存活戳（新进程启动即确立"此刻活着"的基准，
    不必等满一个周期），随后每 `interval_seconds` 覆写一次，直至被取消
    （调用方在服务退出时 `task.cancel()`，见 `run_aibot_service.py`）。

    写入失败（磁盘满/权限）不向上抛出、不中断长连接——本函数是纯粹的后台
    维护任务，不该因为一次写入失败就影响服务主流程；提供 `audit` 时留痕
    一条 `liveness_heartbeat_write_failed`（心跳本身不进审计链，见模块
    docstring，但"心跳写失败"是一次异常状态、值得留痕，两者不矛盾）。"""
    while True:
        try:
            write_liveness(path, datetime.now(timezone.utc))
        except OSError as exc:
            if audit is not None:
                audit.record(AuditEvent(
                    scenario="wecom-aibot", action="liveness_heartbeat_write_failed",
                    evaluator=evaluator, automation_level="L1",
                    decision={}, data_sources={"path": str(path)}, error=describe_exception(exc),
                ))
        await _sleep(interval_seconds)
