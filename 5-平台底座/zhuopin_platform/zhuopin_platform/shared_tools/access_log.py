"""轻量访问日志采集框架（队列 #112）。

背景：`.51` 上四个内网服务（保供看板8091/命令中心8092/QD-B8093/FI2 8094）此前均无法
回答"部门成员是否真在用"——发布即收口纪律的四关只管到"部署+灰度开闸"，用不用无人知道。
本模块只解决"采集能力先就位"这一层（Shao Peishen 2026-07-29 拍板收窄范围）：记录
时间+来源IP+动作，**不采集个人身份**（无登录系统，本就无个人身份可采）。

**本次不做**：周汇总报送、连续零使用告警——这些是"正式统计动作"，待各场景"统计起算日"
到达后再建（见《价值度量指标口径表-2026-07-27.md》§〇bis）。本模块只负责把数据攒起来。

与既有 `connector_audit.py::AccessTrace`（连接器对外部数据源的访问痕迹）语义不同——
那个记的是"本服务调用了谁"，这个记的是"谁调用了本服务"，两者物理分离，互不混写。

排除 `/api/ping`（监控/程序化探活噪声，不代表真实使用），同 `simple_gate.py` 的
`exempt_paths` 惯例。
"""
from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class AccessLogEntry:
    """一次 HTTP 请求的轻量访问痕迹（不含个人身份，仅供使用率统计）。"""

    service: str
    method: str
    path: str
    status: int
    source_ip: str
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(tz=timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AccessLogger:
    """append-only JSONL 访问日志记录器（同一进程内按文件路径共享一把锁，串行化写入）。"""

    _locks: dict[str, threading.Lock] = {}
    _locks_guard = threading.Lock()

    def __init__(self, path: Path | str):
        self.path = Path(path)
        key = str(self.path.resolve())
        with AccessLogger._locks_guard:
            self._lock = AccessLogger._locks.setdefault(key, threading.Lock())

    def record(self, *, service: str, method: str, path: str, status: int, source_ip: str) -> None:
        entry = AccessLogEntry(service=service, method=method, path=path,
                               status=status, source_ip=source_ip)
        line = json.dumps(entry.to_dict(), ensure_ascii=False) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line)


# ── Flask 集成（SC8/QD-B/FI2 三个 Flask 场景共用；命令中心零依赖自包含一份等价逻辑） ──

def install_flask_access_log(app, *, service_name: str, log_path: Path | str | None,
                              exempt_paths: tuple[str, ...] = ("/api/ping",)):
    """给一个 Flask app 装上轻量访问日志中间件。

    `log_path` 为 None 时**不装**、原样返回 app——既有测试套件与未显式配置落盘路径的
    调用点零回归；只有启动脚本显式传入真实路径，采集才生效（同 cache_dir/ops_webhook_url
    等既有可选参数的"缺省关闭"惯例）。
    """
    if log_path is None:
        return app

    from flask import request

    logger = AccessLogger(log_path)
    exempt = set(exempt_paths)

    @app.after_request
    def _zp_access_log(response):  # noqa: ANN202
        if request.path not in exempt:
            logger.record(
                service=service_name,
                method=request.method,
                path=request.path,
                status=response.status_code,
                source_ip=request.remote_addr or "",
            )
        return response

    return app
