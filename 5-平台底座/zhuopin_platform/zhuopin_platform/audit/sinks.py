"""审计存储后端 —— 写入路径与存储解耦。"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Protocol

from .events import AuditEvent


class AuditSink(Protocol):
    """所有存储后端实现此接口；业务代码只依赖接口。"""

    def write(self, event: AuditEvent) -> None: ...

    def read_all(self) -> list[dict]: ...


class JsonlSink:
    """JSON Lines append-only 后端（当前默认，SC1 在用）。

    线程安全（High4）：写操作加进程内互斥锁，避免 ZpConnector BOM 并行查询等多线程
    场景下并发追加导致行穿插、JSONL 损坏。
    """

    # 同一进程内对同一文件路径共享一把锁（不同 JsonlSink 实例可能指向同一文件）
    _locks: dict[str, threading.Lock] = {}
    _locks_guard = threading.Lock()

    def __init__(self, log_path: Path | str):
        self.log_path = Path(log_path)
        key = str(self.log_path.resolve())
        with JsonlSink._locks_guard:
            self._lock = JsonlSink._locks.setdefault(key, threading.Lock())

    def write(self, event: AuditEvent) -> None:
        line = json.dumps(event.to_dict(), ensure_ascii=False) + "\n"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:  # 串行化写，保证多线程下整行原子追加
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line)

    def read_all(self) -> list[dict]:
        if not self.log_path.exists():
            return []
        records = []
        with open(self.log_path, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # 跳过损坏行，verify_integrity 另行统计
        return records


class ClickHouseSink:
    """ClickHouse append-only 后端（9月迁移启用 — 全景规划 4.2）。

    迁移策略：JsonlSink 与本 sink 可双写一段时间，灰度校验一致性后再切换。
    依赖 clickhouse-connect（pyproject 的 [clickhouse] extra）。
    """

    def __init__(self, dsn: str, table: str = "ai_audit_log"):
        self.dsn = dsn
        self.table = table

    def write(self, event: AuditEvent) -> None:  # pragma: no cover - 9月实现
        raise NotImplementedError(
            "ClickHouseSink 计划 2026-09 随 U9C 数据汇聚一并落地；"
            "当前 Phase 1 使用 JsonlSink。"
        )

    def read_all(self) -> list[dict]:  # pragma: no cover - 9月实现
        raise NotImplementedError
