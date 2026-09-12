"""审计存储后端 —— 写入路径与存储解耦。"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .events import AuditEvent

if os.name == "nt":
    import msvcrt
else:
    import fcntl


class AuditSink(Protocol):
    """所有存储后端实现此接口；业务代码只依赖接口。"""

    def write(self, event: AuditEvent) -> None: ...

    def read_all(self) -> list[dict]: ...


@dataclass
class ChainVerifyResult:
    """hash-chain 校验结果。

    `broken_at`/`error` 是**首个**断点的镜像字段（向后兼容旧调用方，如
    `backfill_orphan_audit_chain.py` 只读这两个字段打印 WARN）；`breaks` 是本次
    校验发现的**全部**断点（`#564`：正本此前遇第一个断点就 `return`，跨进程
    并发写导致的 206 处后续分叉全部被遮住）。`duplicate_prev_hash_pairs` 是
    与哈希重算完全无关的旁证判据——单纯比较相邻两行 JSON 里 `prev_hash` 字段
    的字面值，同一个值出现在相邻两行即说明两个写入方都以为自己接在同一行
    之后，是跨进程分叉的独立佐证（哈希链本身算错也不影响这条判据）。
    """
    ok: bool
    total: int
    broken_at: int | None = None   # 首个断链行号（1-based），None 表示链完整
    error: str = ""
    breaks: list[dict] = field(default_factory=list)
    duplicate_prev_hash_pairs: list[tuple[int, int]] = field(default_factory=list)


class _CrossProcessFileLock:
    """跨进程文件级互斥锁（`#564`）。

    锁的对象是审计 JSONL 旁边的一个独立 `.lock` 哨兵文件，不是审计文件本身
    ——避免与 `ab` 追加写句柄互相干扰。平台适配：Windows 用 `msvcrt.locking`，
    POSIX 用 `fcntl.flock`，两者都是阻塞式独占锁，覆盖同机多进程（含至少 5 个
    独立 OS 进程：常驻 listener ＋ 若干计划任务）并发写同一文件的场景。

    `threading.Lock`（进程内）无法解决这个问题——它只在同一个 Python 进程的
    多个线程之间生效，不同进程各自持有互不相干的 `threading.Lock` 实例。
    """

    def __init__(self, target_path: Path):
        self._lock_path = target_path.with_name(target_path.name + ".lock")
        self._fh = None

    def __enter__(self) -> "_CrossProcessFileLock":
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self._lock_path, "a+b")
        if os.name == "nt":
            self._fh.seek(0)
            # LK_LOCK 内部每 1 秒重试一次、10 次后抛 OSError；外层再包一层
            # 重试，覆盖写入被长时间占用（如磁盘慢/杀毒软件扫描）的边界情况。
            while True:
                try:
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
        else:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if os.name == "nt":
                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None


class JsonlSink:
    """JSON Lines append-only 后端（当前默认，SC1/SC8 在用）。

    线程安全（High4）：写操作先加进程内 `threading.Lock`（同进程多线程排队），
    再加跨进程文件锁 `_CrossProcessFileLock`（`#564`：同机多进程排队）。

    P2 hash-chain：每条记录写入时嵌入 `prev_hash`（上一条落盘行原始字节的 SHA-256）。
    🔴 **`prev_hash` 游标不再有任何进程内存缓存**（`#564` 修复前的 `_last_hashes`
    类级字典只在单进程内共享，而本文件被至少 5 个独立 OS 进程并发写，缓存值对
    其它进程的写入一无所知，是分叉的根因）——每次写入都在跨进程锁**内**现读磁盘
    末行重算 `prev_hash`，内存缓存不得再充当链尾真相。`verify_chain()` 逐行对
    原始字节重算哈希，不依赖 canonical 重排序。
    """

    # 同一进程内对同一文件路径共享一把线程锁（跨进程互斥见 _CrossProcessFileLock）
    _locks: dict[str, threading.Lock] = {}
    _locks_guard = threading.Lock()

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
        """（锁内调用）现读磁盘末行重算上一条哈希——不读任何进程内缓存。

        `#564`：此前的实现优先信任类级内存缓存 `_last_hashes`，只在缓存未命中
        时才回落磁盘；但缓存只在**当前进程**内有效，另一个进程刚写完的新行，
        本进程的缓存对此一无所知，于是两个进程各自拿着自己那份"过期但看起来
        合法"的 prev_hash 各写一条，形成分叉。修复后每次写入都现读磁盘，
        跨进程文件锁（`_CrossProcessFileLock`）保证"现读—写入"这段操作本身
        对同一文件全机唯一，读到的必是全局最新的末行。
        """
        last_line = self._read_last_line_bytes()
        if last_line is None:
            return ""   # genesis
        return self._sha256_bytes(last_line)

    def write(self, event: AuditEvent) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        # 两层锁：先进程内 threading.Lock（同进程多线程排队，避免线程间
        # 在跨进程锁上无谓争抢），再跨进程文件锁（同机多进程排队）。
        with self._lock, _CrossProcessFileLock(self.log_path):
            prev_hash = self._get_prev_hash()
            d = event.to_dict()
            d["prev_hash"] = prev_hash
            line_str = json.dumps(d, ensure_ascii=False)
            line_bytes = (line_str + "\n").encode("utf-8")
            with open(self.log_path, "ab") as f:
                f.write(line_bytes)

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

    def find_prev_hash_forks(self) -> list[tuple[int, int]]:
        """与哈希重算完全无关的旁证判据（`#564` ③）。

        只逐行读 JSON 记录本身携带的 `prev_hash` **字段值**，比较相邻两行是否
        相同——全程不重算任何 SHA-256，不依赖 `verify_chain()` 的字节哈希比对
        路径，是真正独立的第二条判据（哈希计算逻辑本身如果有 bug，这条判据
        依然成立）。两个独立写入方各自读到同一条"上一行"、各自算出同一个
        `prev_hash` 后先后落盘，就会在文件里留下相邻两行同一个 `prev_hash`
        的痕迹——这正是跨进程并发写分叉的指纹。

        行号口径与 `verify_chain()` 一致：按**非空行**计数、1-based（跳过空行
        不计入序号），返回值为 `[(行号a, 行号b), ...]`，`b == a + 1`。
        """
        if not self.log_path.exists():
            return []

        records: list[dict | None] = []   # None 占位：该行 JSON 解析失败
        with open(self.log_path, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    records.append(None)

        pairs: list[tuple[int, int]] = []
        for i in range(1, len(records)):
            prev_rec, cur_rec = records[i - 1], records[i]
            if prev_rec is None or cur_rec is None:
                continue
            prev_val = prev_rec.get("prev_hash")
            cur_val = cur_rec.get("prev_hash")
            if prev_val is not None and cur_val is not None and prev_val == cur_val:
                pairs.append((i, i + 1))   # 1-based，与 verify_chain 行号口径一致
        return pairs

    def verify_chain(self) -> ChainVerifyResult:
        """逐行对磁盘原始字节重算哈希，检测任意行被删改或跨进程分叉。

        无 `prev_hash` 字段的 genesis 豁免**仅对第 1 行生效**（向前兼容旧文件）。
        第 2 行起任何缺 `prev_hash` 字段的行判为断链——堵住"删光全文件 prev_hash
        字段重写即整链通过"的防篡改绕过（A3 / 审计报告 §2.2 P0）。

        🔴 `#564`：本方法**报出全部断点**，不在第一个断点处停手就 `return`——
        正本此前的实现一撞见 `broken_at` 就返回，2026-07-28 那次已知的历史
        迁移断点把后面 206 处跨进程并发写导致的新断点全部遮住了。断点之后的
        哈希游标改用"当前行原始字节的真实哈希"续接（而非"本应匹配的哈希"），
        这样一处断点不会连锁触发后面每一行都被误判为断点。
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

        breaks: list[dict] = []
        prev_hash = ""
        for idx, raw_line in enumerate(raw_lines, start=1):
            try:
                record = json.loads(raw_line.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                breaks.append({"line": idx, "error": f"JSON 解析失败: {e}"})
                # 解析失败拿不到 stored_prev，但原始字节仍可哈希——用它续接
                # 游标，避免这一行的解析失败级联触发后面每一行都被误判断链。
                prev_hash = self._sha256_bytes(raw_line)
                continue

            stored_prev = record.get("prev_hash")

            if stored_prev is None:
                # 无 prev_hash 字段：仅第 1 行可豁免（旧文件兼容）；其后缺字段 = 篡改
                if idx == 1:
                    prev_hash = self._sha256_bytes(raw_line)
                    continue
                breaks.append({
                    "line": idx,
                    "error": f"第 {idx} 行缺 prev_hash 字段（疑似篡改）",
                })
                prev_hash = self._sha256_bytes(raw_line)
                continue

            if stored_prev != prev_hash:
                breaks.append({
                    "line": idx,
                    "error": f"第 {idx} 行 prev_hash 不匹配",
                })

            prev_hash = self._sha256_bytes(raw_line)

        duplicate_pairs = self.find_prev_hash_forks()
        first_break = breaks[0] if breaks else None

        return ChainVerifyResult(
            ok=not breaks and not duplicate_pairs,
            total=len(raw_lines),
            broken_at=first_break["line"] if first_break else None,
            error=first_break["error"] if first_break else "",
            breaks=breaks,
            duplicate_prev_hash_pairs=duplicate_pairs,
        )


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
