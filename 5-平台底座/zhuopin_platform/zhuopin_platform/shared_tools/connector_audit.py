"""连接器审计接入层（D2/D5）。

合规设计（Paul 拍板）：
  · D2 粒度：连接器**只写轻量访问痕迹**（数据源/动作/目标/时间），复用平台 audit 的
    JsonlSink 基础设施（不重建），但与场景层合规 AuditEvent **物理分离**——连接器
    每次读数不刷一条合规决策，避免审计噪声。完整 IATF 合规决策（含 decision/evaluator/
    automation_level）由**场景层**用 zhuopin_platform.audit.AuditLogger 写入。
  · D2 红线：请求/响应全文（含供应商敏感字段）绝不进合规 audit；仅在显式开启的
    DebugLog 里落盘，默认关闭、独立文件（*.debug.log，已 gitignore）。
  · D5：审计接入采用依赖注入（sink 可注入临时对象），便于测试、不污染真实日志。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..audit.sinks import AuditSink


@dataclass
class AccessTrace:
    """连接器一次数据访问的轻量痕迹（无任何合规决策字段、无红色数据）。"""

    source: str            # 数据源：SRM / zp_ERP / U9C / CSV
    action: str            # 动作：get_delivery / get_purchase_orders ...
    target: str = ""       # 目标标识：PO 号 / 料号（非敏感）
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(tz=timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConnectorAudit:
    """连接器轻量访问痕迹记录器（D2/D5）。

    复用平台 audit 的 sink 协议（JsonlSink 等），写入与合规 audit 物理分离的
    访问痕迹日志。无 sink 时静默（测试/离线场景不产生副作用）。

    Args:
        sink: 任意实现 AuditSink.write 的对象（如 JsonlSink(独立 access_trace 路径)）。
              None 时不落盘——连接器照常工作，只是不留痕。
    """

    def __init__(self, sink: AuditSink | None = None):
        self._sink = sink

    def trace(self, source: str, action: str, target: str = "") -> None:
        if self._sink is None:
            return
        self._sink.write(AccessTrace(source=source, action=action, target=target))


class DebugLog:
    """连接器可选 req/resp 全文调试日志（D2：默认关闭、与合规 audit 物理分开）。

    仅供 AIOps 排障临时开启。文件名约定 ``*.debug.log``，已被 .gitignore 排除，
    绝不与合规 audit 混写。

    Args:
        path:    debug 文件路径（应以 .debug.log 结尾）。
        enabled: 默认 False —— 关闭时 record() 不产生任何文件。
    """

    def __init__(self, path: Path | str, enabled: bool = False):
        self.path = Path(path)
        self.enabled = enabled

    def record(self, req: Any, resp: Any = None, error: str = "") -> None:
        if not self.enabled:
            return
        entry = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "req": req,
            "resp": resp,
            "error": error,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
