"""审计存储后端 —— 写入路径与存储解耦。"""
from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .events import AuditEvent


class AuditSink(Protocol):
    """所有存储后端实现此接口；业务代码只依赖接口。"""

    def write(self, event: AuditEvent) -> None: ...

    def read_all(self) -> list[dict]: ...


@dataclass
class ChainVerifyResult:
    """hash-chain 校验结果。"""
    ok: bool
    total: int
    broken_at: int | None = None   # 首个断链行号（1-based），None 表示链完整
    error: str = ""


class JsonlSink:
    """JSON Lines append-only 后端（当前默认，SC1/SC8 在用）。

    线程安全（High4）：写操作加进程内互斥锁，避免并发追加导致行穿插。

    P2 hash-chain：每条记录写入时嵌入 `prev_hash`（上一条落盘行原始字节的 SHA-256）。
    `_last_hashes` 为类级路径字典（与 `_locks` 同构），两个指向同一文件的实例共享
    同一 hash 游标，双实例交替写不断链。`verify_chain()` 逐行对原始字节重算哈希，
    不依赖 canonical 重排序。
    """

    # 同一进程内对同一文件路径共享一把锁
    _locks: dict[str, threading.Lock] = {}
    _locks_guard = threading.Lock()

    # 同一进程内对同一文件路径共享上一条哈希（类级，与 _locks 同构）
    _last_hashes: dict[str, str] = {}
    _hashes_guard = threading.Lock()

    def __init__(self, log_path: Path | str):
        self.log_path = Path(log_path)
        key = str(self.log_path.resolve())
        with JsonlSink._locks_guard:
            self._lock = JsonlSink._locks.setdefault(key, threading.Lock())
        self._path_key = key

    @staticmethod
    def _sha256_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _read_last_line_bytes(self) -> bytes | None:
        """从文件末尾读最后一行的原始字节（含 \\n）；文件不存在或空返回 None。"""
        if not self.log_path.exists():
            return None
        with open(self.log_path, "rb") as f:
            f.seek(0, 2)  # 跳到末尾
            size = f.tell()
            if size == 0:
                return None
            # 从末尾向前找最后一个 \n（前一行的结尾）
            pos = size - 1
            # 跳过末尾空行 / \n
            f.seek(pos)
            while pos > 0 and f.read(1) == b"\n":
                pos -= 1
                f.seek(pos)
            # 向前找这行的起始
            end = pos + 1
            while pos > 0:
                f.seek(pos - 1)
                if f.read(1) == b"\n":
                    break
                pos -= 1
            f.seek(pos)
            line = f.read(end - pos + 1)   # +1 补回末尾 \n
            return line if line else None

    def _get_prev_hash(self) -> str:
        """（锁内调用）取当前上一条哈希；_last_hashes 无记录时从磁盘末行重算。"""
        cached = JsonlSink._last_hashes.get(self._path_key)
        if cached is not None:
            return cached
        # 初次写：尝试从文件末行读取哈希
        last_line = self._read_last_line_bytes()
        if last_line is None:
            return ""   # genesis
        return self._sha256_bytes(last_line)

    def write(self, event: AuditEvent) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            prev_hash = self._get_prev_hash()
            d = event.to_dict()
            d["prev_hash"] = prev_hash
            line_str = json.dumps(d, ensure_ascii=False)
            line_bytes = (line_str + "\n").encode("utf-8")
            with open(self.log_path, "ab") as f:
                f.write(line_bytes)
            # 更新类级缓存
            with JsonlSink._hashes_guard:
                JsonlSink._last_hashes[self._path_key] = self._sha256_bytes(line_bytes)

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
                    continue
        return records

    def verify_chain(self) -> ChainVerifyResult:
        """逐行对磁盘原始字节重算哈希，检测任意行被删改。

        首条无 `prev_hash` 字段的记录视为合法 genesis（向前兼容旧文件）。
        """
        if not self.log_path.exists():
            return ChainVerifyResult(ok=True, total=0)

        raw_lines: list[bytes] = []
        with open(self.log_path, "rb") as f:
            for line in f:
                stripped = line.rstrip(b"\n")
                if stripped:
                    raw_lines.append(line if line.endswith(b"\n") else line + b"\n")

        if not raw_lines:
            return ChainVerifyResult(ok=True, total=0)

        prev_hash = ""
        for idx, raw_line in enumerate(raw_lines, start=1):
            try:
                record = json.loads(raw_line.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                return ChainVerifyResult(ok=False, total=len(raw_lines),
                                         broken_at=idx, error=f"JSON 解析失败: {e}")

            stored_prev = record.get("prev_hash")

            if stored_prev is None:
                # 无 prev_hash 字段 → 视为合法 genesis（旧文件兼容）
                prev_hash = self._sha256_bytes(raw_line)
                continue

            if stored_prev != prev_hash:
                return ChainVerifyResult(ok=False, total=len(raw_lines),
                                         broken_at=idx,
                                         error=f"第 {idx} 行 prev_hash 不匹配")

            prev_hash = self._sha256_bytes(raw_line)

        return ChainVerifyResult(ok=True, total=len(raw_lines))


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
