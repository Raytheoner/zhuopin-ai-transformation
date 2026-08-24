"""队列 #387 ⑹：`pending_queue_appends.jsonl` 补录侧的幂等判据。

**真实事故（2026-08-24 15:30:53）**：`queue_sync_degraded` 把一行推进了
`reports/pending_queue_appends.jsonl`（机器人当时发了「队列同步失败 1 次，
一行待人工核对合并」告警）。人工核对结果是：**该行对应的队列行已经存在**
（就是 §一 `#389`）⇒ 那条 pending 是重复，若被自动 flush 会产生第二条同
内容、不同编号的行。

**为什么会这样**：`queue_sync_degraded` 的常见根因是 `.git/index.lock` 被
并发 git 进程占着（本机常态——sweep／巡检／CC 会话随时在跑 git），而**加锁
失败发生在「行已写进磁盘文件」之后**。于是同一条来件同时以两种形态存在。

本文件把那次人工核对固化成机器判据。
"""
import asyncio
import json

import pytest

from zhuopin_platform.audit import AuditLogger

from aibot_service.queue_git_sync import (
    flush_pending_git_sync_appends,
    input_pointer_already_in_queue,
)

QUEUE_MECHANISM_REL = "1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md"
QUEUE_BUSINESS_REL = "1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md"

POINTER = "7-外部文档/IT/IT-2023458-回复-2026-08-24-文本反馈-m1.md"


def _write_queue(repo_root, rel, extra_row=""):
    path = repo_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# 队列（测试骨架）\n\n> 编号高水位线：#100\n\n"
        "## 一、任务看板\n\n"
        "| 编号 | 任务 | 领取方 | 输入指针 | 预期产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| 100 | 既有行 | Paul | `x` | y | [S:done] |  | 2026-08-01 |\n"
        + extra_row
        + "\n## 二、待 commit 批次\n\n",
        encoding="utf-8",
    )
    return path


def _row_with_pointer():
    return (
        f"| 101 | 企微反馈自动归档：2023458 发来文本反馈 | 业务总线 | "
        f"`{POINTER}` | 核实内容 | [S:open] |  | 2026-08-24 |\n"
    )


# ── 判据函数本身 ────────────────────────────────────────────────────────


def test_pointer_found_in_mechanism_queue(tmp_path):
    queue_path = _write_queue(tmp_path, QUEUE_MECHANISM_REL, _row_with_pointer())
    _write_queue(tmp_path, QUEUE_BUSINESS_REL)

    assert input_pointer_already_in_queue(tmp_path, queue_path, f"`{POINTER}`") is True


def test_pointer_found_in_the_other_queue_file(tmp_path):
    """🔴 扫全部物理队列文件，不只扫写入侧那一份。

    `#315` 拆成两份之后，一条行可能被人工挪进另一份；只扫写入侧会把「已挪走
    的行」误判为不存在，于是补出第二条——正是「一份拆成两份、下游只跟了一
    份」那个家族的又一个入口。
    """
    queue_path = _write_queue(tmp_path, QUEUE_MECHANISM_REL)
    _write_queue(tmp_path, QUEUE_BUSINESS_REL, _row_with_pointer())

    assert input_pointer_already_in_queue(tmp_path, queue_path, f"`{POINTER}`") is True


def test_pointer_absent_returns_false(tmp_path):
    queue_path = _write_queue(tmp_path, QUEUE_MECHANISM_REL)
    _write_queue(tmp_path, QUEUE_BUSINESS_REL)

    assert input_pointer_already_in_queue(tmp_path, queue_path, f"`{POINTER}`") is False


def test_backticks_are_stripped_before_matching(tmp_path):
    """`input_pointer` 在 append_kwargs 里带反引号包裹，队列行里也带——
    两侧都归一化后再比，免得因为一层反引号判成"没找到"。"""
    queue_path = _write_queue(tmp_path, QUEUE_MECHANISM_REL, _row_with_pointer())
    _write_queue(tmp_path, QUEUE_BUSINESS_REL)

    assert input_pointer_already_in_queue(tmp_path, queue_path, POINTER) is True


def test_empty_pointer_never_matches(tmp_path):
    queue_path = _write_queue(tmp_path, QUEUE_MECHANISM_REL, _row_with_pointer())
    _write_queue(tmp_path, QUEUE_BUSINESS_REL)

    assert input_pointer_already_in_queue(tmp_path, queue_path, "") is False
    assert input_pointer_already_in_queue(tmp_path, queue_path, "``") is False


def test_missing_queue_file_fails_open(tmp_path):
    """⚠️ 这一侧的 fail-open 是刻意的：本函数只是一道去重网，读不到文件就
    退回改动前的行为（照常补录），不能因为一个读不到的文件把补录链路卡死。"""
    queue_path = tmp_path / QUEUE_MECHANISM_REL  # 根本不存在

    assert input_pointer_already_in_queue(tmp_path, queue_path, f"`{POINTER}`") is False


# ── 接进 flush 之后的端到端行为 ─────────────────────────────────────────


def _pending(tmp_path, pointer):
    path = tmp_path / "pending_queue_appends.jsonl"
    path.write_text(
        json.dumps(
            {
                "recorded_at": "2026-08-24T07:30:53+00:00",
                "error": "queue_sync_degraded",
                "description": "企微反馈自动归档：2023458 发来文本反馈",
                "owner": "业务总线",
                "input_pointer": f"`{pointer}`",
                "expected_output": "核实内容",
                "date_str": "2026-08-24",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_flush_skips_record_whose_row_already_exists(tmp_path, monkeypatch):
    """🔴 本文件的主张：已存在即丢弃，绝不补出第二条同内容行。"""
    queue_path = _write_queue(tmp_path, QUEUE_MECHANISM_REL, _row_with_pointer())
    _write_queue(tmp_path, QUEUE_BUSINESS_REL)
    pending_path = _pending(tmp_path, POINTER)
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")

    called = []

    async def _never(**kwargs):
        called.append(kwargs)
        raise AssertionError("已存在的行不得再走一次 sync_after_archive")

    monkeypatch.setattr("aibot_service.queue_git_sync.sync_after_archive", _never)

    flushed = asyncio.run(
        flush_pending_git_sync_appends(
            pending_path=pending_path,
            repo_root=tmp_path,
            queue_path=queue_path,
            audit=audit,
        )
    )

    assert flushed == 0
    assert called == []
    # 记录被丢弃：剩余为空 ⇒ 文件被删（`pending_jsonl.rewrite_records` 语义）
    assert not pending_path.exists()

    events = audit.query_by(scenario="wecom-aibot")
    dup = [r for r in events if r["action"] == "queue_sync_pending_skipped_duplicate"]
    assert len(dup) == 1
    assert dup[0]["decision"]["reason"] == "row_already_present"


def test_flush_still_processes_record_whose_row_is_missing(tmp_path, monkeypatch):
    """回归锁：不存在的行照常补录——去重网不得把正常补录一并挡掉。"""
    queue_path = _write_queue(tmp_path, QUEUE_MECHANISM_REL)
    _write_queue(tmp_path, QUEUE_BUSINESS_REL)
    pending_path = _pending(tmp_path, POINTER)
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")

    seen = []

    class _Outcome:
        pushed = True
        pending_recorded_at = None

    async def _fake_sync(**kwargs):
        seen.append(kwargs["append_kwargs"]["input_pointer"])
        return _Outcome()

    monkeypatch.setattr("aibot_service.queue_git_sync.sync_after_archive", _fake_sync)

    flushed = asyncio.run(
        flush_pending_git_sync_appends(
            pending_path=pending_path,
            repo_root=tmp_path,
            queue_path=queue_path,
            audit=audit,
        )
    )

    assert flushed == 1
    assert seen == [f"`{POINTER}`"]
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "queue_sync_pending_flushed" in actions
    assert "queue_sync_pending_skipped_duplicate" not in actions
