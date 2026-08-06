"""通用 append-only JSONL 存储（队列 #110 Feature A/B 共用骨架）。

仿 `pending_queue.py::FilePendingQueue` 的落盘范式（per-file 线程锁 + JSONL append），
去掉幂等/状态翻转部分——反馈按钮与判例包提交都是纯追加、无需改写已写记录。

红线（队列 #110 原文 + 调查结论，见 `case_review.py` 顶部说明）：只采集标注，不自动
改任何判据；不经 `zhuopin_platform.audit`——专员打的标注/判例意见本身不是终局业务
决策，真正的口径变更仍须走判例批改法的显式签认步骤。
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path


class JsonlAppendStore:
    """最小 append-only JSONL 存储：同进程按文件路径共享一把锁，串行化写入。"""

    _locks: dict[str, threading.Lock] = {}
    _locks_guard = threading.Lock()

    def __init__(self, path: Path | str):
        self.path = Path(path)
        key = str(self.path.resolve())
        with JsonlAppendStore._locks_guard:
            self._lock = JsonlAppendStore._locks.setdefault(key, threading.Lock())

    def append(self, record: dict) -> str:
        """追加一条记录，自动补 id/created_at（覆盖调用方同名字段，保证唯一且可信）。"""
        full = dict(record)
        full["id"] = uuid.uuid4().hex
        full["created_at"] = datetime.now(tz=timezone.utc).isoformat()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(full, ensure_ascii=False) + "\n"
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line)
        return full["id"]

    def read_all(self) -> list[dict]:
        """读取全部记录（坏行容错跳过，不炸）。"""
        if not self.path.exists():
            return []
        out: list[dict] = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out
