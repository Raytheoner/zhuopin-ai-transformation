import asyncio

import pytest

from zhuopin_platform.audit import AuditLogger

from aibot_service.queue_lock_pending import (
    record_deferred_append,
    read_deferred_appends,
    flush_pending_queue_appends,
)
import aibot_service.queue_lock_pending as queue_lock_pending_mod

from fakes import FakeQueueEditLock

QUEUE_TEXT = """\
## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 1 | 既有任务 | CC | p | e | 待领 | — | 07-09 |
"""


def _append_kwargs(desc="d"):
    return dict(description=desc, owner="o", input_pointer="i", expected_output="e", date_str="2026-07-30")


def test_read_deferred_appends_missing_file_returns_empty(tmp_path):
    assert read_deferred_appends(tmp_path / "no_such.jsonl") == []


def test_record_and_read_deferred_appends_round_trip(tmp_path):
    pending_path = tmp_path / "pending.jsonl"
    record_deferred_append(pending_path, {"recorded_at": "t1", "append_kwargs": _append_kwargs("第一条")})
    record_deferred_append(pending_path, {"recorded_at": "t2", "append_kwargs": _append_kwargs("第二条")})

    records = read_deferred_appends(pending_path)
    assert len(records) == 2
    assert records[0]["append_kwargs"]["description"] == "第一条"
    assert records[1]["append_kwargs"]["description"] == "第二条"


def test_flush_with_no_pending_records_is_noop(tmp_path):
    queue_path = tmp_path / "queue.md"
    queue_path.write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")

    flushed = asyncio.run(
        flush_pending_queue_appends(
            pending_path=tmp_path / "pending.jsonl",
            queue_path=queue_path,
            repo_root=tmp_path,
            audit=audit,
            lock_factory=lambda: FakeQueueEditLock(busy=False),
        )
    )
    assert flushed == 0


def test_flush_appends_pending_record_when_lock_free_and_clears_pending_file(tmp_path, monkeypatch):
    """锁空闲时——暂存记录应被正确补录（不重复追加），并从暂存文件移除，
    同时按正常路径继续走一遍 git 同步（此处用 monkeypatch 隔离 git 层，
    只验证 flush 自身的编排逻辑；真实 git 同步的端到端覆盖见
    test_connection.py 的真实仓库集成测试）。"""
    queue_path = tmp_path / "queue.md"
    queue_path.write_text(QUEUE_TEXT, encoding="utf-8")
    pending_path = tmp_path / "pending.jsonl"
    record_deferred_append(pending_path, {"recorded_at": "t1", "sender": "姚祖怡", "append_kwargs": _append_kwargs("补录测试")})
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")

    sync_calls = []

    async def _fake_sync_after_archive(**kwargs):
        sync_calls.append(kwargs)

    monkeypatch.setattr(queue_lock_pending_mod, "sync_after_archive", _fake_sync_after_archive)

    flushed = asyncio.run(
        flush_pending_queue_appends(
            pending_path=pending_path,
            queue_path=queue_path,
            repo_root=tmp_path,
            audit=audit,
            lock_factory=lambda: FakeQueueEditLock(busy=False),
        )
    )

    assert flushed == 1
    assert "补录测试" in queue_path.read_text(encoding="utf-8")
    assert read_deferred_appends(pending_path) == []  # 不重复追加：暂存已清空
    assert len(sync_calls) == 1
    assert sync_calls[0]["already_appended_row"].strip().startswith("|")

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "queue_append_pending_flushed" in actions


def test_flush_stops_and_preserves_order_when_lock_still_busy(tmp_path, monkeypatch):
    """锁仍被占用（人类可能仍在编辑）——本条及后续条目都保留在暂存文件里，
    不跳过尝试后面的、也不因为"试过一次"就丢弃。"""
    queue_path = tmp_path / "queue.md"
    queue_path.write_text(QUEUE_TEXT, encoding="utf-8")
    pending_path = tmp_path / "pending.jsonl"
    record_deferred_append(pending_path, {"recorded_at": "t1", "append_kwargs": _append_kwargs("第一条待补")})
    record_deferred_append(pending_path, {"recorded_at": "t2", "append_kwargs": _append_kwargs("第二条待补")})
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")

    async def _fake_sync_after_archive(**kwargs):
        raise AssertionError("锁忙时不应走到 git 同步这一步")

    monkeypatch.setattr(queue_lock_pending_mod, "sync_after_archive", _fake_sync_after_archive)

    flushed = asyncio.run(
        flush_pending_queue_appends(
            pending_path=pending_path,
            queue_path=queue_path,
            repo_root=tmp_path,
            audit=audit,
            lock_factory=lambda: FakeQueueEditLock(busy=True),
        )
    )

    assert flushed == 0
    assert "第一条待补" not in queue_path.read_text(encoding="utf-8")
    remaining = read_deferred_appends(pending_path)
    assert len(remaining) == 2  # 两条都还在，顺序不变
    assert remaining[0]["append_kwargs"]["description"] == "第一条待补"
    assert remaining[1]["append_kwargs"]["description"] == "第二条待补"


def test_flush_partial_success_preserves_remaining_order(tmp_path, monkeypatch):
    """第一条在补录中途变为可拿锁（成功），第二条锁忙——第一条应从暂存移
    除，第二条应保留，不因第一条成功而被误清空。"""
    queue_path = tmp_path / "queue.md"
    queue_path.write_text(QUEUE_TEXT, encoding="utf-8")
    pending_path = tmp_path / "pending.jsonl"
    record_deferred_append(pending_path, {"recorded_at": "t1", "append_kwargs": _append_kwargs("可补录")})
    record_deferred_append(pending_path, {"recorded_at": "t2", "append_kwargs": _append_kwargs("仍锁忙")})
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")

    async def _fake_sync_after_archive(**kwargs):
        pass

    monkeypatch.setattr(queue_lock_pending_mod, "sync_after_archive", _fake_sync_after_archive)

    locks = [FakeQueueEditLock(busy=False), FakeQueueEditLock(busy=True)]
    lock_iter = iter(locks)

    flushed = asyncio.run(
        flush_pending_queue_appends(
            pending_path=pending_path,
            queue_path=queue_path,
            repo_root=tmp_path,
            audit=audit,
            lock_factory=lambda: next(lock_iter),
        )
    )

    assert flushed == 1
    assert "可补录" in queue_path.read_text(encoding="utf-8")
    remaining = read_deferred_appends(pending_path)
    assert len(remaining) == 1
    assert remaining[0]["append_kwargs"]["description"] == "仍锁忙"
