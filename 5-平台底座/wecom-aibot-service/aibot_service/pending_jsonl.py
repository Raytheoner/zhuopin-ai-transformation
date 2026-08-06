"""通用的推迟暂存 JSONL 读写工具（队列 #286）。

`queue_lock_pending.py`（编辑锁占用暂存）与 `queue_git_sync.py`（git 推送
失败暂存）此前各自独立实现了一套几乎相同的"追加一行/整体读出/剩余重写"
逻辑，物理上是两个不同 schema 的文件——本模块只抽出与 schema 无关的纯
文件级操作，供两处复用，不改变任何一方的记录 schema 或既有调用方行为。
`queue_git_sync.py` 需要复用（而不是从 `queue_lock_pending.py` 导入）是因为
后者本身 `from .queue_git_sync import sync_after_archive`——两者互相导入
会成环，故都改为依赖这个不引用任何一方的中立模块。
"""
from __future__ import annotations

import json
from pathlib import Path


def append_record(path: Path, record: dict) -> None:
    """把一条记录追加进 `path`（append-only，一行一条 JSON）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_records(path: Path) -> list[dict]:
    """按写入顺序（FIFO）读出全部记录；文件不存在/为空返回空列表。"""
    if not path.exists():
        return []
    records: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records


def rewrite_records(path: Path, remaining: list[dict]) -> None:
    """用剩余记录整体重写文件；剩余为空时直接删除该文件（体积恒定，不留
    一个永远的空文件）。"""
    if not remaining:
        if path.exists():
            path.unlink()
        return
    text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in remaining)
    path.write_text(text, encoding="utf-8")
