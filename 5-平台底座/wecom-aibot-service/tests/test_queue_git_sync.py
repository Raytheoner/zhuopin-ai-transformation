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

import pytest

from zhuopin_platform.audit import AuditLogger

from aibot_service.queue_appender import append_pending_task
from aibot_service.queue_edit_lock import QueueLockBusy
from aibot_service.queue_git_sync import (
    UNSYNCED_MARKER,
    _clear_unsynced_markers,
    _is_non_fast_forward,
    _mark_row_unsynced,
    append_task_and_sync_to_git,
    flush_pending_git_sync_appends,
    sync_after_archive,
)
from aibot_service.repo_paths import REPO_ROOT_OVERRIDE_ENV

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


# ── 队列 #126：跨 checkout 失效修复 ──────────────────────────────────────


def test_append_task_and_sync_to_git_recovers_from_cross_worktree_repo_root(tmp_path: Path):
    """核心回归场景：调用方传入的 `repo_root` 是队列文件所在 worktree 的
    "邻居" worktree（服务常驻 `ops/wecom-service-home`、队列文件固定指向
    主工作区的真实故障模式简化版）。修复前 `_relative_to_repo` 会直接抛
    ValueError（queue.md 不在 wrong_repo_root 的 subpath 下）；修复后应
    动态解析出 queue_path 真正所属的仓库根，正常推送成功。"""
    origin, clone_a, _clone_b = _init_bare_origin_with_clones(tmp_path)
    wrong_repo_root = tmp_path / "clone_a_sibling_worktree"
    _git(clone_a, "worktree", "add", "-q", "-b", "sibling", str(wrong_repo_root))

    outcome = append_task_and_sync_to_git(
        wrong_repo_root, clone_a / "queue.md", **_sample_kwargs("跨worktree场景")
    )

    assert outcome.pushed is True, f"应动态解析出 clone_a 自身的根，实际 last_error={outcome.last_error!r}"
    pushed_content = _show_origin_file(origin, "master", "queue.md")
    assert "跨worktree场景" in pushed_content


def test_append_task_and_sync_to_git_recovers_from_unrelated_repo_root(tmp_path: Path):
    """跨 repo 形态：传入的 `repo_root` 是与队列文件毫不相干的另一个仓库
    （如未来 Mac 独立 clone 场景）——同样应以队列文件自身所属仓库为准。"""
    origin, clone_a, _clone_b = _init_bare_origin_with_clones(tmp_path)
    unrelated_repo = tmp_path / "unrelated_repo"
    _git(tmp_path, "init", "-q", "-b", "master", str(unrelated_repo))
    _git(unrelated_repo, "config", "user.email", "x@example.com")
    _git(unrelated_repo, "config", "user.name", "X")

    outcome = append_task_and_sync_to_git(
        unrelated_repo, clone_a / "queue.md", **_sample_kwargs("跨repo场景")
    )

    assert outcome.pushed is True
    pushed_content = _show_origin_file(origin, "master", "queue.md")
    assert "跨repo场景" in pushed_content


def test_append_task_and_sync_to_git_env_override_takes_precedence(tmp_path: Path):
    """`WECOM_AIBOT_REPO_ROOT` 显式覆盖——绕开动态 git 解析，直接在 override
    指定的目录上执行 git 操作。"""
    origin, clone_a, _clone_b = _init_bare_origin_with_clones(tmp_path)

    outcome = append_task_and_sync_to_git(
        tmp_path / "never_used", clone_a / "queue.md",
        env={REPO_ROOT_OVERRIDE_ENV: str(clone_a)},
        **_sample_kwargs("override场景"),
    )

    assert outcome.pushed is True
    pushed_content = _show_origin_file(origin, "master", "queue.md")
    assert "override场景" in pushed_content


def test_already_appended_row_is_committed_without_duplicate_append(tmp_path: Path):
    """`intake.py` 已经用 `append_pending_task` 独立落盘一行——本函数首次
    尝试须直接提交这一行，不得再内部调用 `append_pending_task` 二次追加
    同一内容（修复前的隐藏 bug：`sync_after_archive` 接入生产前从未被
    端到端测试覆盖，一旦 checkout 校验通过，intake.py 的落盘行会和本函数
    内部重新算出的一行同时存在，造成同一条消息在队列里出现两行）。"""
    origin, clone_a, _clone_b = _init_bare_origin_with_clones(tmp_path)
    pre_appended_row = append_pending_task(clone_a / "queue.md", **_sample_kwargs("已由intake落盘"))

    outcome = append_task_and_sync_to_git(
        clone_a, clone_a / "queue.md",
        already_appended_row=pre_appended_row,
        **_sample_kwargs("已由intake落盘"),
    )

    assert outcome.pushed is True
    assert outcome.attempts == 1
    assert outcome.row == pre_appended_row
    pushed_content = _show_origin_file(origin, "master", "queue.md")
    assert pushed_content.count("已由intake落盘") == 1, (
        f"应只出现一行，实际出现 {pushed_content.count('已由intake落盘')} 次：\n{pushed_content}"
    )


def test_already_appended_row_recomputed_on_conflict_not_duplicated(tmp_path: Path):
    """已落盘的行如果在推送时撞上非快进冲突，仍应走"对齐后重算"路径（而非
    盲目重放已经算错的编号），且最终也只留一行。"""
    origin, clone_a, clone_b = _init_bare_origin_with_clones(tmp_path)
    other_row = _push_other_writer_row(clone_b, "另一写手先手推送")
    other_id = _row_id(other_row)

    pre_appended_row = append_pending_task(clone_a / "queue.md", **_sample_kwargs("已落盘遇冲突"))

    outcome = append_task_and_sync_to_git(
        clone_a, clone_a / "queue.md",
        already_appended_row=pre_appended_row,
        **_sample_kwargs("已落盘遇冲突"),
    )

    assert outcome.pushed is True
    assert outcome.attempts == 2
    assert _row_id(outcome.row) > other_id
    pushed_content = _show_origin_file(origin, "master", "queue.md")
    assert pushed_content.count("已落盘遇冲突") == 1


# ── 队列 #126：未同步显式标记 ────────────────────────────────────────────


def test_sync_after_archive_marks_row_unsynced_when_degraded(tmp_path: Path):
    """已落盘但 git 同步最终失败——队列文件里该行应被追加"⏳未同步"标记，
    使只看文件的读取方也能察觉（此前只有 audit 事件+私信告警）。"""
    origin, clone_a, _clone_b = _init_bare_origin_with_clones(tmp_path)
    pre_appended_row = append_pending_task(clone_a / "queue.md", **_sample_kwargs("网络故障场景"))
    task_id = _row_id(pre_appended_row)
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")

    outcome = asyncio.run(sync_after_archive(
        repo_root=clone_a, queue_path=clone_a / "queue.md",
        append_kwargs=_sample_kwargs("网络故障场景"),
        already_appended_row=pre_appended_row,
        audit=audit, connector=None, recipient="",
        remote="nonexistent-remote",
    ))

    assert outcome.pushed is False
    on_disk = (clone_a / "queue.md").read_text(encoding="utf-8")
    marked_line = next(l for l in on_disk.splitlines() if l.strip().startswith(f"| {task_id} |"))
    assert UNSYNCED_MARKER in marked_line


def test_sync_after_archive_marks_row_unsynced_when_repo_root_unresolvable(tmp_path: Path):
    """队列 #126 原始故障模式复现：`repo_root` 与队列文件所在 checkout
    完全不相干（甚至不在任何 git 仓库里），已落盘的行仍应被标记。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    plain_dir = tmp_path / "not_a_repo"
    plain_dir.mkdir()
    (plain_dir / "queue.md").write_text(SAMPLE_QUEUE, encoding="utf-8")
    pre_appended_row = append_pending_task(plain_dir / "queue.md", **_sample_kwargs("非仓库场景"))
    task_id = _row_id(pre_appended_row)

    outcome = asyncio.run(sync_after_archive(
        repo_root=plain_dir, queue_path=plain_dir / "queue.md",
        append_kwargs=_sample_kwargs("非仓库场景"),
        already_appended_row=pre_appended_row,
        audit=audit, connector=None, recipient="",
    ))

    assert outcome.pushed is False
    on_disk = (plain_dir / "queue.md").read_text(encoding="utf-8")
    marked_line = next(l for l in on_disk.splitlines() if l.strip().startswith(f"| {task_id} |"))
    assert UNSYNCED_MARKER in marked_line


def test_sync_after_archive_does_not_mark_row_when_pushed_successfully(tmp_path: Path):
    origin, clone_a, _clone_b = _init_bare_origin_with_clones(tmp_path)
    pre_appended_row = append_pending_task(clone_a / "queue.md", **_sample_kwargs("正常成功场景"))
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")

    outcome = asyncio.run(sync_after_archive(
        repo_root=clone_a, queue_path=clone_a / "queue.md",
        append_kwargs=_sample_kwargs("正常成功场景"),
        already_appended_row=pre_appended_row,
        audit=audit, connector=None, recipient="",
    ))

    assert outcome.pushed is True
    on_disk = (clone_a / "queue.md").read_text(encoding="utf-8")
    assert UNSYNCED_MARKER not in on_disk


# ── 队列 #180：未同步标记自动清除 ────────────────────────────────────────


def test_mark_row_unsynced_appends_at_row_end_not_after_id_column(tmp_path: Path):
    """标记位置改为行末尾（闭合竖线之前），不再顶偏任务描述开头。"""
    queue_path = tmp_path / "queue.md"
    queue_path.write_text(SAMPLE_QUEUE, encoding="utf-8")

    assert _mark_row_unsynced(queue_path, "1") is True

    line = next(
        l for l in queue_path.read_text(encoding="utf-8").splitlines()
        if l.strip().startswith("| 1 |")
    )
    assert line.strip().startswith("| 1 | 任务一 |"), "任务描述不应被标记顶偏到后面"
    assert line.rstrip().endswith(UNSYNCED_MARKER + " |"), "标记应在行末尾、闭合竖线之前"


def test_clear_unsynced_markers_restores_original_content(tmp_path: Path):
    queue_path = tmp_path / "queue.md"
    queue_path.write_text(SAMPLE_QUEUE, encoding="utf-8")
    original = queue_path.read_text(encoding="utf-8")

    assert _mark_row_unsynced(queue_path, "1") is True
    assert queue_path.read_text(encoding="utf-8") != original

    cleared = _clear_unsynced_markers(queue_path)
    assert cleared == 1
    assert queue_path.read_text(encoding="utf-8") == original, "清除后应与标记前内容逐字节一致"


def test_clear_unsynced_markers_no_markers_is_noop(tmp_path: Path):
    queue_path = tmp_path / "queue.md"
    queue_path.write_text(SAMPLE_QUEUE, encoding="utf-8")

    assert _clear_unsynced_markers(queue_path) == 0
    assert queue_path.read_text(encoding="utf-8") == SAMPLE_QUEUE


def test_clear_unsynced_markers_handles_legacy_leading_space_format(tmp_path: Path):
    """兼容历史（#126 时期）插入格式——标记当时紧跟在编号列之后而非行末尾；
    即便插入位置的写法不同，同样应被完整清除、不残留多余空白（队列 #180
    实证：#149/#175 两行正是这一历史格式）。"""
    header = (
        "## 一、任务看板\n\n"
        "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|------|--------|-------------|----------|------|--------|------|\n"
    )
    original_line = "| 1 | 任务一 | CC | 指针1 | 产出1 | 待领 | — | 07-09 |\n"
    legacy_marked_line = f"| 1 | {UNSYNCED_MARKER} 任务一 | CC | 指针1 | 产出1 | 待领 | — | 07-09 |\n"
    queue_path = tmp_path / "queue.md"
    queue_path.write_text(header + legacy_marked_line, encoding="utf-8")

    cleared = _clear_unsynced_markers(queue_path)
    assert cleared == 1
    assert queue_path.read_text(encoding="utf-8") == header + original_line


@pytest.mark.xfail(
    strict=True,
    reason=(
        "队列 #287 根因复现，待 openspec 变更包 aibot-queue-sync-checkout-guard "
        "design 审批通过并 apply 护栏后应转为通过（届时移除本 xfail 标记）"
    ),
)
def test_conflict_recompute_destroys_uninvolved_uncommitted_edits(tmp_path: Path):
    """队列 #287 根因复现（真实代码路径，非 mock）：人类会话经协议〇.7
    编辑锁 acquire→写盘→release 后，改动仍只落在工作区（未 commit，等待
    sweep 按 §二 批次统一提交）——这期间若机器人恰好处理另一条消息、且
    推送撞上非快进冲突（origin 已被第三方推进，属日常高频场景），冲突后的
    `fetch`+`reset --mixed`+`checkout -- relative_path` 会把队列文件的
    工作区内容整体替换成 origin 版本，人类那份从未涉及本次冲突的未提交
    编辑被静默一并抹掉——即 #287 描述的"锁与结构校验都正常工作，只是它们
    保护的那份文件在其之外被另一个进程整体替换"。

    本用例不依赖任何 mock：真实 bare origin + 真实 git 子进程 + 真实调用
    生产函数 `append_task_and_sync_to_git`。"""
    origin, clone_a, clone_b = _init_bare_origin_with_clones(tmp_path)

    # 人类会话：acquire 编辑锁编辑 → 写盘 → release（协议〇.7/〇.8），
    # 改动此刻只在工作区，尚未 commit（等 sweep 处理 §二 批次时才提交）。
    human_marker = "人类会话已release但尚未commit的真实成果——不得被机器人抹掉"
    queue_text = (clone_a / "queue.md").read_text(encoding="utf-8")
    queue_text = queue_text.replace(
        "## 二、占位小节", f"## 二、占位小节\n\n{human_marker}\n"
    )
    (clone_a / "queue.md").write_text(queue_text, encoding="utf-8")
    assert _git(clone_a, "status", "--porcelain").stdout.strip() != "", "前置条件：工作区应处于脏状态"

    # 第三方（另一 CC session/机器人自己处理的另一条消息）先手推送，制造
    # 非快进冲突——这是高频并发仓库里的日常场景，不是刻意构造的极端条件。
    _push_other_writer_row(clone_b, "并发的另一条消息")

    outcome = append_task_and_sync_to_git(
        clone_a, clone_a / "queue.md", **_sample_kwargs("机器人正在处理的这条消息")
    )

    assert outcome.pushed is True, f"重算后应成功推送，last_error={outcome.last_error!r}"
    assert outcome.attempts == 2, "第 1 次应因非快进被拒，第 2 次重算后才成功"

    on_disk = (clone_a / "queue.md").read_text(encoding="utf-8")
    pushed_content = _show_origin_file(origin, "master", "queue.md")
    assert human_marker in on_disk, (
        "根因复现：人类已 release 但未 commit 的改动被 reset/checkout 静默抹掉，"
        "工作区里已找不到，见队列 #287"
    )
    assert human_marker in pushed_content, "人类的改动应随本次同步一并保留并推送，而非彻底消失"


def test_append_task_and_sync_to_git_clears_stale_marker_from_earlier_row_on_success(
    tmp_path: Path,
):
    """队列 #180 核心场景复现：#149/#175 式的陈旧标记——某次更早的失败
    已在别的行留下标记，且带标记的版本早已被提交推送到 origin。本次一次
    全新的成功同步（追加另一行）应把这个陈旧标记一并清掉，而不只是本次
    追加的新行本身不带标记。"""
    origin, clone_a, _clone_b = _init_bare_origin_with_clones(tmp_path)

    assert _mark_row_unsynced(clone_a / "queue.md", "1") is True
    _git(clone_a, "add", "queue.md")
    _git(clone_a, "commit", "-q", "-m", "模拟历史遗留标记（如 #149/#175）")
    _git(clone_a, "push", "-q", "origin", "master")
    assert UNSYNCED_MARKER in _show_origin_file(origin, "master", "queue.md")

    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    outcome = asyncio.run(sync_after_archive(
        repo_root=clone_a, queue_path=clone_a / "queue.md",
        append_kwargs=_sample_kwargs("全新任务"),
        audit=audit, connector=None, recipient="",
    ))

    assert outcome.pushed is True
    on_disk = (clone_a / "queue.md").read_text(encoding="utf-8")
    assert UNSYNCED_MARKER not in on_disk, "本次成功同步应顺带清掉陈旧标记"
    pushed = _show_origin_file(origin, "master", "queue.md")
    assert UNSYNCED_MARKER not in pushed, "陈旧标记也应随本次推送从 origin 上被清除"


# ── 队列 #286：flush 通道覆盖两类暂存文件 ──────────────────────────────


class _AlwaysBusyLock:
    def try_acquire(self) -> None:
        raise QueueLockBusy("模拟：冲突重算时人类恰好持锁")

    def release(self) -> None:
        pass


def test_lock_busy_during_conflict_recompute_routes_to_lock_pending_file(tmp_path: Path):
    """队列 #286 核心场景（真实还原故障链路）：`already_appended_row` 已
    落盘（模拟 intake.py 直接落盘的这一行）→ 第 1 次尝试提交推送，撞上
    非快进冲突（另一写手先手推送）→ `fetch`+`reset`+`checkout` 对齐后进入
    第 2 次尝试，`append_pending_task(..., lock=lock_factory())` 重算时
    恰好撞上人类持锁。此前该记录与"真实 git 失败"混用同一个 `pending_
    path`（`_append_pending_record` 扁平 schema），而唯一有 flush 通道的
    是另一个 schema 不同的锁忙暂存文件，导致这条记录永远等不到补录。
    修复后应改落 `lock_pending_path`，schema 与 `queue_lock_pending.
    record_deferred_append` 一致（`append_kwargs` 嵌套一层）。"""
    origin, clone_a, clone_b = _init_bare_origin_with_clones(tmp_path)
    _push_other_writer_row(clone_b, "先手推送制造非快进冲突")
    pre_appended_row = append_pending_task(
        clone_a / "queue.md", **_sample_kwargs("撞上冲突重算时的锁忙")
    )
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    git_sync_pending = tmp_path / "pending_queue_appends.jsonl"
    lock_pending = tmp_path / "pending_queue_lock_appends.jsonl"

    outcome = asyncio.run(sync_after_archive(
        repo_root=clone_a, queue_path=clone_a / "queue.md",
        append_kwargs=_sample_kwargs("撞上冲突重算时的锁忙"),
        already_appended_row=pre_appended_row,
        audit=audit, connector=None, recipient="",
        pending_path=git_sync_pending, lock_pending_path=lock_pending,
        lock_factory=lambda: _AlwaysBusyLock(),
    ))

    assert outcome.pushed is False
    assert not git_sync_pending.exists(), "锁忙不该落进真实 git 失败暂存文件"
    assert lock_pending.exists(), "锁忙应改落锁忙专用暂存文件，供既有 flush_pending_queue_appends 补录"
    record = json.loads(lock_pending.read_text(encoding="utf-8").strip())
    assert record["append_kwargs"]["description"] == "撞上冲突重算时的锁忙"
    assert outcome.pending_recorded_at == lock_pending


def test_non_lock_busy_failure_still_routes_to_git_sync_pending_file(tmp_path: Path):
    """护栏是"锁忙才转向"，真实网络/编号冲突失败（非 QueueLockBusy）应
    维持现状——落 `pending_path`（扁平 schema，向后兼容既有测试断言）。"""
    origin, clone_a, _clone_b = _init_bare_origin_with_clones(tmp_path)
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    git_sync_pending = tmp_path / "pending_queue_appends.jsonl"
    lock_pending = tmp_path / "pending_queue_lock_appends.jsonl"

    outcome = asyncio.run(sync_after_archive(
        repo_root=clone_a, queue_path=clone_a / "queue.md",
        append_kwargs=_sample_kwargs("网络类失败"),
        audit=audit, connector=None, recipient="",
        pending_path=git_sync_pending, lock_pending_path=lock_pending,
        remote="nonexistent-remote",
    ))

    assert outcome.pushed is False
    assert git_sync_pending.exists()
    assert not lock_pending.exists()
    record = json.loads(git_sync_pending.read_text(encoding="utf-8").strip())
    assert record["description"] == "网络类失败", "既有扁平 schema 不变"
    assert outcome.pending_recorded_at == git_sync_pending


def test_degraded_alert_includes_pending_file_path_and_input_pointer(tmp_path: Path):
    """队列 #286 建议③：告警文案带上暂存文件路径与 input_pointer，使人工
    承接有明确落点，不再只是一句"一行待人工核对合并"。"""
    origin, clone_a, clone_b = _init_bare_origin_with_clones(tmp_path)
    _push_other_writer_row(clone_b, "初始阻挡")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = _FakeConnector()
    git_sync_pending = tmp_path / "pending_queue_appends.jsonl"

    asyncio.run(sync_after_archive(
        repo_root=clone_a, queue_path=clone_a / "queue.md",
        append_kwargs=_sample_kwargs("带落点的降级告警"),
        audit=audit, connector=connector, recipient="ShaoPeiShen",
        pending_path=git_sync_pending, max_retries=1,
    ))

    assert connector.calls, "降级必须私信"
    alert_text = connector.calls[0][1]
    assert str(git_sync_pending) in alert_text, "告警文案应包含暂存文件路径"
    assert "指针X" in alert_text, "告警文案应包含 input_pointer，供人工按图索骥"


def test_flush_pending_git_sync_appends_recomputes_and_pushes(tmp_path: Path):
    """队列 #286 核心修复：`pending_queue_appends.jsonl` 此前没有任何 flush
    通道，记录只会永久躺在磁盘上。补录时不假设原始行仍在磁盘（该文件被
    写入时磁盘几乎总已被 reset 清空过），必须让 `append_pending_task`
    对最新内容重新计算，而非重放。"""
    origin, clone_a, _clone_b = _init_bare_origin_with_clones(tmp_path)
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    pending_path = tmp_path / "pending_queue_appends.jsonl"
    pending_path.write_text(
        json.dumps({
            "recorded_at": "2026-08-06T08:08:12+00:00",
            "error": "此前一次真实 git 失败",
            **_sample_kwargs("此前失败、待补录的任务"),
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    flushed = asyncio.run(flush_pending_git_sync_appends(
        pending_path=pending_path, repo_root=clone_a, queue_path=clone_a / "queue.md",
        audit=audit, connector=None, recipient="",
    ))

    assert flushed == 1
    assert not pending_path.exists(), "补录成功后暂存文件应清空（无剩余记录时直接删除）"
    pushed_content = _show_origin_file(origin, "master", "queue.md")
    assert "此前失败、待补录的任务" in pushed_content


def test_flush_pending_git_sync_appends_keeps_still_failing_records(tmp_path: Path):
    """补录仍然失败（如推送目标依旧不通）时，记录必须留在暂存文件里，
    不能被静默丢弃或错误地标记为已处理。"""
    origin, clone_a, _clone_b = _init_bare_origin_with_clones(tmp_path)
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    pending_path = tmp_path / "pending_queue_appends.jsonl"
    kwargs = _sample_kwargs("依旧失败的任务")
    pending_path.write_text(
        json.dumps({"recorded_at": "2026-08-06T08:08:12+00:00", "error": "上次失败", **kwargs},
                    ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    flushed = asyncio.run(flush_pending_git_sync_appends(
        pending_path=pending_path, repo_root=clone_a, queue_path=clone_a / "queue.md",
        audit=audit, connector=None, recipient="", remote="nonexistent-remote",
    ))

    assert flushed == 0
    assert pending_path.exists(), "仍失败的记录不能凭空消失"
    remaining = [json.loads(l) for l in pending_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(remaining) == 1
    assert remaining[0]["description"] == "依旧失败的任务"


def test_flush_pending_git_sync_appends_migrates_lock_busy_without_duplication(tmp_path: Path):
    """补录过程中若重新撞上锁忙，记录应"迁移"到锁忙暂存文件、并从
    `pending_queue_appends.jsonl` 里彻底移除——不能同时留在两处（否则同一
    条消息未来会被两条独立的 flush 逻辑各补录一次，造成队列里出现重复行）。"""
    origin, clone_a, clone_b = _init_bare_origin_with_clones(tmp_path)
    _push_other_writer_row(clone_b, "制造非快进冲突")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    pending_path = tmp_path / "pending_queue_appends.jsonl"
    lock_pending = tmp_path / "pending_queue_lock_appends.jsonl"
    kwargs = _sample_kwargs("补录时又撞上锁忙")
    pending_path.write_text(
        json.dumps({"recorded_at": "2026-08-06T08:08:12+00:00", "error": "上次失败", **kwargs},
                    ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    flushed = asyncio.run(flush_pending_git_sync_appends(
        pending_path=pending_path, repo_root=clone_a, queue_path=clone_a / "queue.md",
        audit=audit, connector=None, recipient="",
        lock_pending_path=lock_pending, lock_factory=lambda: _AlwaysBusyLock(),
    ))

    assert flushed == 0
    assert not pending_path.exists(), "已迁移的记录不应继续留在原文件"
    assert lock_pending.exists(), "应迁移进锁忙暂存文件"
    migrated = json.loads(lock_pending.read_text(encoding="utf-8").strip())
    assert migrated["append_kwargs"]["description"] == "补录时又撞上锁忙"
