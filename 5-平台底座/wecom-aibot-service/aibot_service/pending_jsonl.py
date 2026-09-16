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

import contextlib
import json
import os
from pathlib import Path


def _claim_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".flushing")


def try_claim_flush(path: Path) -> bool:
    """互斥声明"本进程正在 flush 这份暂存文件"（队列 #586 ⑸）。

    用同目录下一个 `<path>.flushing` 哨兵文件、`O_CREAT|O_EXCL` 原子创建
    实现——两个进程（如常驻监听的 `on_message` 与 `decision_reminder_
    check.py` 的"第二道载体"）几乎同时各自 `read_records()` 到同一批未
    处理记录、各自成功写出一份队列行 ⇒ 同一条来信被写成两行（真实事故：
    `#588`＝`#590`、`#589`＝`#591`）。`read → 处理 → rewrite` 这段临界区
    此前没有任何互斥，本函数把它补上。**声明失败即视为"另一进程正在
    flush"，调用方应放弃本轮、直接返回 0**（下次消息到达/下次巡逻自然
    会重试，不会真的漏 flush，只是多等一轮）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    claim = _claim_path(path)
    try:
        fd = os.open(str(claim), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    os.close(fd)
    return True


def release_flush_claim(path: Path) -> None:
    """释放 `try_claim_flush` 的声明；文件不存在（如从未成功声明过）静默忽略。"""
    with contextlib.suppress(FileNotFoundError):
        _claim_path(path).unlink()


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
