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
    UNSYNCED_MARKER,
    _is_non_fast_forward,
    append_task_and_sync_to_git,
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
