"""queue_git_sync.py 单测（design.md D1）。

真实本地 git 仓库黑盒验证（bare origin + 两个 clone 模拟"Mac 与另一写手
几乎同时都在改队列文件"）——覆盖 tasks.md 2.5 要求的四种场景：推送成功 /
冲突后重算（而非重放）/ 重试耗尽降级 / 降级不阻塞归档主流程。
"""
from __future__ import annotations

import asyncio
import json
import re
import subprocess
from pathlib import Path

from zhuopin_platform.audit import AuditLogger

from aibot_service.queue_appender import append_pending_task
from aibot_service.queue_git_sync import (
    _is_non_fast_forward,
    append_task_and_sync_to_git,
    sync_after_archive,
)

SAMPLE_QUEUE = """\
## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 1 | 任务一 | CC | 指针1 | 产出1 | 待领 | — | 07-09 |

## 二、占位小节

后续内容不动。
"""

_ROW_ID_RE = re.compile(r"^\|\s*(\d+)\s*\|")


def _row_id(row: str) -> int:
    m = _ROW_ID_RE.match(row.strip())
    assert m, row
    return int(m.group(1))


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8"
    )


def _show_origin_file(origin: Path, ref: str, rel_path: str) -> str:
    result = subprocess.run(
        ["git", "--git-dir", str(origin), "show", f"{ref}:{rel_path}"],
        check=True, capture_output=True, text=True, encoding="utf-8",
    )
    return result.stdout


def _init_bare_origin_with_clones(tmp_path: Path) -> tuple[Path, Path, Path]:
    origin = tmp_path / "origin.git"
    origin.mkdir()
    _git(origin, "init", "--bare", "-q", "-b", "master")

    seed = tmp_path / "_seed"
    seed.mkdir()
    _git(seed, "init", "-q", "-b", "master")
    _git(seed, "config", "user.email", "seed@example.com")
    _git(seed, "config", "user.name", "Seed")
    (seed / "queue.md").write_text(SAMPLE_QUEUE, encoding="utf-8")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-q", "-m", "init")
    _git(seed, "remote", "add", "origin", str(origin))
    _git(seed, "push", "-q", "origin", "master")

    clone_a = tmp_path / "clone_a"
    clone_b = tmp_path / "clone_b"
    for clone in (clone_a, clone_b):
        _git(tmp_path, "clone", "-q", str(origin), str(clone))
        _git(clone, "config", "user.email", "bot@example.com")
        _git(clone, "config", "user.name", "Test Bot")

    return origin, clone_a, clone_b


def _sample_kwargs(description: str = "测试任务") -> dict:
    return dict(
        description=description, owner="CC", input_pointer="指针X",
        expected_output="产出X", date_str="07-24", touch_zone="",
    )


def _push_other_writer_row(clone_b: Path, description: str = "另一写手的任务") -> str:
    """模拟另一台机器已经追加并成功推送了一行。"""
    row = append_pending_task(clone_b / "queue.md", **_sample_kwargs(description))
    _git(clone_b, "add", "queue.md")
    _git(clone_b, "commit", "-q", "-m", f"other writer #{_row_id(row)}")
    _git(clone_b, "push", "-q", "origin", "master")
    return row


class _FakeConnector:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[tuple[str, str]] = []

    async def send_markdown(self, recipient: str, text: str) -> None:
        self.calls.append((recipient, text))
        if self.should_fail:
            raise RuntimeError("WebSocket not connected, unable to send data")


def _actions(audit: AuditLogger) -> list[str]:
    return [r["action"] for r in audit.query_by(scenario="wecom-aibot")]


def test_is_non_fast_forward_detects_standard_git_rejection_text():
    stderr = (
        "To /tmp/origin.git\n"
        " ! [rejected]        master -> master (fetch first)\n"
        "error: failed to push some refs to '/tmp/origin.git'\n"
        "hint: Updates were rejected because the remote contains work that you do\n"
    )
    assert _is_non_fast_forward(stderr)


def test_is_non_fast_forward_false_for_unrelated_errors():
    assert not _is_non_fast_forward("fatal: 'nonexistent-remote' does not appear to be a git repository")


def test_push_succeeds_without_conflict(tmp_path: Path):
    origin, clone_a, _clone_b = _init_bare_origin_with_clones(tmp_path)

    outcome = append_task_and_sync_to_git(
        clone_a, clone_a / "queue.md", **_sample_kwargs("首次成功场景")
    )

    assert outcome.pushed is True
    assert outcome.attempts == 1
    assert outcome.last_error == ""
    pushed_content = _show_origin_file(origin, "master", "queue.md")
    assert "首次成功场景" in pushed_content
    assert f"| {_row_id(outcome.row)} |" in pushed_content


def test_conflict_recomputes_higher_id_instead_of_replaying(tmp_path: Path):
    """历史事故模式是"两个写手各自算出同一个编号"——本用例验证冲突后是
    重新计算出比对方更大的编号，而不是盲目重放本地那次已经算错的编号。"""
    origin, clone_a, clone_b = _init_bare_origin_with_clones(tmp_path)

    other_row = _push_other_writer_row(clone_b, "另一写手先手推送")
    other_id = _row_id(other_row)

    # clone_a 此时对 clone_b 的推送一无所知，本地队列文件仍是初始内容。
    outcome = append_task_and_sync_to_git(
        clone_a, clone_a / "queue.md", **_sample_kwargs("clone_a 追加")
    )

    assert outcome.pushed is True
    assert outcome.attempts == 2, "第 1 次应因非快进被拒，第 2 次重算后才成功"
    final_id = _row_id(outcome.row)
    assert final_id > other_id, "必须重算出比对方更大的编号，不能重放出撞号"

    final_content = _show_origin_file(origin, "master", "queue.md")
    assert "另一写手先手推送" in final_content, "对方的行不能因本次同步丢失"
    assert "clone_a 追加" in final_content
    ids_in_final = [int(m) for m in re.findall(r"^\|\s*(\d+)\s*\|", final_content, re.M)]
    assert len(ids_in_final) == len(set(ids_in_final)), f"不得出现重复编号：{ids_in_final}"


def test_conflict_exhausted_retries_returns_pushed_false_and_resets_clean(tmp_path: Path):
    """每次重试前对方都再抢先推送一行，导致重试全部耗尽——验证：
    ① 明确返回 pushed=False；② 仓库回到与远端一致的干净状态（不留一个
    基于过期基线算出、编号可能已不准确的本地 commit 挡住后续自动化写入）。"""
    origin, clone_a, clone_b = _init_bare_origin_with_clones(tmp_path)
    _push_other_writer_row(clone_b, "初始阻挡")  # 保证第 1 次尝试就已冲突
    push_count = {"n": 0}

    def _sleep_and_race(_seconds: float) -> None:
        push_count["n"] += 1
        _push_other_writer_row(clone_b, f"竞争第{push_count['n']}轮")

    outcome = append_task_and_sync_to_git(
        clone_a, clone_a / "queue.md", max_retries=2, _sleep=_sleep_and_race,
        **_sample_kwargs("永远追不上"),
    )

    assert outcome.pushed is False
    assert outcome.attempts == 2
    assert push_count["n"] == 1, "重试上限 2 次只应触发 1 次 sleep 钩子（第 2 次已是最后一次，不再 fetch 重试）"

    local_head = _git(clone_a, "rev-parse", "HEAD").stdout.strip()
    origin_head = subprocess.run(
        ["git", "--git-dir", str(origin), "rev-parse", "master"],
        check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout.strip()
    assert local_head == origin_head, "重试耗尽后本地应回到与远端一致的干净状态"
    status = _git(clone_a, "status", "--porcelain").stdout
    assert status.strip() == "", f"工作区应干净无残留改动：{status!r}"


def test_non_conflict_failure_preserves_local_commit(tmp_path: Path):
    """网络/鉴权类失败（非"origin 已前进"）：本地这个 commit 内容仍然正确，
    不该被丢弃——保留在本地分支上，交下一次调用自然重试。"""
    origin, clone_a, _clone_b = _init_bare_origin_with_clones(tmp_path)

    outcome = append_task_and_sync_to_git(
        clone_a, clone_a / "queue.md", remote="nonexistent-remote",
        **_sample_kwargs("推送目标不存在"),
    )

    assert outcome.pushed is False
    assert outcome.attempts == 1, "非快进类失败不应重试"
    assert "推送目标不存在" in (clone_a / "queue.md").read_text(encoding="utf-8")
    last_subject = _git(clone_a, "log", "-1", "--format=%s").stdout
    assert "bot(队列)" in last_subject


def test_sync_after_archive_success_records_pushed_audit(tmp_path: Path):
    origin, clone_a, _clone_b = _init_bare_origin_with_clones(tmp_path)
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = _FakeConnector()

    outcome = asyncio.run(sync_after_archive(
        repo_root=clone_a, queue_path=clone_a / "queue.md",
        append_kwargs=_sample_kwargs("异步包装成功场景"),
        audit=audit, connector=connector, recipient="ShaoPeiShen",
    ))

    assert outcome.pushed is True
    assert _actions(audit) == ["queue_sync_pushed"]
    assert connector.calls == [], "推送成功不应触发告警"


def test_sync_after_archive_degraded_alerts_paul_and_writes_pending_file(tmp_path: Path):
    origin, clone_a, clone_b = _init_bare_origin_with_clones(tmp_path)
    _push_other_writer_row(clone_b, "初始阻挡")  # 保证第 1 次尝试就已冲突
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = _FakeConnector(should_fail=False)
    pending_path = tmp_path / "pending_queue_appends.jsonl"
    push_count = {"n": 0}

    def _sleep_and_race(_seconds: float) -> None:
        push_count["n"] += 1
        _push_other_writer_row(clone_b, f"异步竞争第{push_count['n']}轮")

    kwargs = _sample_kwargs("异步降级场景")
    outcome = asyncio.run(sync_after_archive(
        repo_root=clone_a, queue_path=clone_a / "queue.md",
        append_kwargs=kwargs, audit=audit, connector=connector, recipient="ShaoPeiShen",
        pending_path=pending_path, max_retries=1,
    ))

    assert outcome.pushed is False
    assert _actions(audit) == ["queue_sync_degraded", "queue_sync_alert_sent"]
    assert connector.calls, "降级必须私信 Paul"
    assert "ShaoPeiShen" == connector.calls[0][0]
    assert "异步降级场景" in connector.calls[0][1]

    pending_lines = pending_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(pending_lines) == 1
    record = json.loads(pending_lines[0])
    assert record["description"] == "异步降级场景"
    assert record["owner"] == "CC"


def test_sync_after_archive_degraded_alert_falls_back_to_webhook(tmp_path: Path):
    origin, clone_a, _clone_b = _init_bare_origin_with_clones(tmp_path)
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = _FakeConnector(should_fail=True)
    fallback_calls: list[str] = []

    outcome = asyncio.run(sync_after_archive(
        repo_root=clone_a, queue_path=clone_a / "queue.md",
        append_kwargs=_sample_kwargs("主通道也挂了"),
        audit=audit, connector=connector, recipient="ShaoPeiShen",
        fallback_send=fallback_calls.append,
        remote="nonexistent-remote",
    ))

    assert outcome.pushed is False
    assert _actions(audit) == ["queue_sync_degraded", "queue_sync_alert_failed", "queue_sync_alert_fallback_sent"]
    assert fallback_calls, "主通道失败必须兜底"


def test_sync_after_archive_does_not_raise_when_repo_root_invalid(tmp_path: Path):
    """归档主流程不得被队列同步的任何异常打断——即便 repo_root 压根不是
    git 仓库，本函数也必须吞掉异常、走降级路径，而不是向上抛。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    not_a_repo = tmp_path / "not_a_repo"
    not_a_repo.mkdir()
    (not_a_repo / "queue.md").write_text(SAMPLE_QUEUE, encoding="utf-8")

    outcome = asyncio.run(sync_after_archive(
        repo_root=not_a_repo, queue_path=not_a_repo / "queue.md",
        append_kwargs=_sample_kwargs("不是仓库"),
        audit=audit, connector=None, recipient="",
    ))

    assert outcome.pushed is False
    assert "queue_sync_degraded" in _actions(audit)
