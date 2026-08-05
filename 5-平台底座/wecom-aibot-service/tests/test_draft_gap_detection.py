"""队列 #245：跟进信"该起草而没起草"检测——比对逻辑单测。

`find_missing_drafts`（侧 A/侧 B 交叉比对，纯数据）与
`find_recent_scenario_commits`（git log 扫描，真实临时仓库，同
`test_repo_paths.py`/`test_queue_git_sync.py` 既有测试风格）分开覆盖。
"""
from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

from aibot_service.draft_gap_detection import (
    SCENARIO_RECIPIENTS,
    ScenarioCommitEvent,
    build_gap_report,
    find_missing_drafts,
    find_recent_scenario_commits,
)

HEADER = (
    "| 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |\n"
    "|------|--------|---------|---------|---------|\n"
)


def _readme(rows: str) -> str:
    return "## 现有跟进信清单\n\n" + HEADER + rows


SC8_PREFIX = "4-数字员工/采购部/SC8-客户订单交期智能承诺/"


# ── find_missing_drafts（纯数据，不涉及 git） ──────────────────────────


def test_no_events_means_no_gaps():
    assert find_missing_drafts(_readme(""), [], date(2026, 8, 5)) == []


def test_event_without_any_drafted_row_is_a_gap():
    events = [
        ScenarioCommitEvent(
            recipient="姚祖怡", scenario_prefix=SC8_PREFIX,
            commit_date=date(2026, 8, 1), commit_sha="abc123", subject="发布收口",
        )
    ]
    gaps = find_missing_drafts(_readme(""), events, date(2026, 8, 5))
    assert len(gaps) == 1
    assert gaps[0].recipient == "姚祖怡"
    assert gaps[0].scenario_prefix == SC8_PREFIX
    assert gaps[0].event_date == date(2026, 8, 1)
    assert gaps[0].commit_sha == "abc123"


def test_drafted_row_on_or_after_event_date_closes_the_gap():
    rows = "| 2026-08-03 | 采购部 · 姚祖怡 | 上线请试用 | 不急 | ⏳ 待你审 |\n"
    events = [
        ScenarioCommitEvent(
            recipient="姚祖怡", scenario_prefix=SC8_PREFIX,
            commit_date=date(2026, 8, 1), commit_sha="abc123", subject="发布收口",
        )
    ]
    assert find_missing_drafts(_readme(rows), events, date(2026, 8, 5)) == []


def test_drafted_row_before_event_date_does_not_close_the_gap():
    # 起草发生在这次发布收口之前——不能证明"这次"发布已经起草过跟进信。
    rows = "| 2026-07-20 | 采购部 · 姚祖怡 | 旧的一封信 | 不急 | ✅ 已发 |\n"
    events = [
        ScenarioCommitEvent(
            recipient="姚祖怡", scenario_prefix=SC8_PREFIX,
            commit_date=date(2026, 8, 1), commit_sha="abc123", subject="发布收口",
        )
    ]
    gaps = find_missing_drafts(_readme(rows), events, date(2026, 8, 5))
    assert len(gaps) == 1


def test_drafted_row_for_different_recipient_does_not_close_the_gap():
    rows = "| 2026-08-03 | 质量部 · 陈忱 | 不相关的信 | 不急 | ⏳ 待你审 |\n"
    events = [
        ScenarioCommitEvent(
            recipient="姚祖怡", scenario_prefix=SC8_PREFIX,
            commit_date=date(2026, 8, 1), commit_sha="abc123", subject="发布收口",
        )
    ]
    gaps = find_missing_drafts(_readme(rows), events, date(2026, 8, 5))
    assert len(gaps) == 1


def test_multiple_commits_same_scenario_report_only_one_gap_using_earliest_date():
    events = [
        ScenarioCommitEvent(
            recipient="姚祖怡", scenario_prefix=SC8_PREFIX,
            commit_date=date(2026, 8, 3), commit_sha="later", subject="又一次改动",
        ),
        ScenarioCommitEvent(
            recipient="姚祖怡", scenario_prefix=SC8_PREFIX,
            commit_date=date(2026, 8, 1), commit_sha="earlier", subject="首次发布收口",
        ),
    ]
    gaps = find_missing_drafts(_readme(""), events, date(2026, 8, 5))
    assert len(gaps) == 1
    assert gaps[0].event_date == date(2026, 8, 1)
    assert gaps[0].commit_sha == "earlier"


# ── build_gap_report ────────────────────────────────────────────────


def test_build_gap_report_no_gaps():
    assert "无缺口" in build_gap_report([], 7)


def test_build_gap_report_lists_each_gap():
    from aibot_service.draft_gap_detection import MissingDraftGap

    gaps = [
        MissingDraftGap(
            recipient="姚祖怡", scenario_prefix=SC8_PREFIX,
            event_date=date(2026, 8, 1), commit_sha="abcdef1234",
        )
    ]
    report = build_gap_report(gaps, 7)
    assert "姚祖怡" in report
    assert SC8_PREFIX in report
    assert "2026-08-01" in report
    assert "abcdef12" in report  # 短 sha


# ── find_recent_scenario_commits（真实临时 git 仓库） ──────────────────


def _git(cwd: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8", env=env,
    )


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", "master")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")
    return path


def _commit_file(repo: Path, rel_path: str, content: str, commit_date_iso: str, message: str) -> str:
    """在指定日期提交一个文件，返回 commit sha。日期通过 GIT_AUTHOR_DATE/
    GIT_COMMITTER_DATE 注入，使测试对"近 N 天"判据可控，不依赖真实系统
    时钟。"""
    import os

    target = repo / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    env = {
        **os.environ,
        "GIT_AUTHOR_DATE": commit_date_iso,
        "GIT_COMMITTER_DATE": commit_date_iso,
    }
    _git(repo, "commit", "-q", "-m", message, env=env)
    result = _git(repo, "rev-parse", "HEAD")
    return result.stdout.strip()


def test_find_recent_scenario_commits_detects_commit_touching_whitelisted_scenario(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    sha = _commit_file(
        repo, f"{SC8_PREFIX}CLAUDE.md", "部署状态：已上线",
        "2026-08-04T10:00:00+08:00", "发布收口 SC8",
    )

    events = find_recent_scenario_commits(repo, today=date(2026, 8, 5), window_days=7)

    assert len(events) == 1
    assert events[0].recipient == "姚祖怡"
    assert events[0].scenario_prefix == SC8_PREFIX
    assert events[0].commit_sha == sha
    assert events[0].commit_date == date(2026, 8, 4)


def test_find_recent_scenario_commits_ignores_commit_outside_window(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(
        repo, f"{SC8_PREFIX}CLAUDE.md", "很久以前的部署",
        "2026-07-01T10:00:00+08:00", "很久以前的发布收口",
    )

    events = find_recent_scenario_commits(repo, today=date(2026, 8, 5), window_days=7)

    assert events == []


def test_find_recent_scenario_commits_ignores_unrelated_file(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(
        repo, "0-学习与工具/无关文件.md", "与已部署场景无关",
        "2026-08-04T10:00:00+08:00", "无关改动",
    )

    events = find_recent_scenario_commits(repo, today=date(2026, 8, 5), window_days=7)

    assert events == []


def test_find_recent_scenario_commits_covers_all_whitelisted_scenarios(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    for prefix, recipient in SCENARIO_RECIPIENTS.items():
        sha = _commit_file(
            repo, f"{prefix}CLAUDE.md", f"{recipient} 场景部署状态",
            "2026-08-04T10:00:00+08:00", f"发布收口 {recipient}",
        )

    events = find_recent_scenario_commits(repo, today=date(2026, 8, 5), window_days=7)

    recipients = {e.recipient for e in events}
    assert recipients == set(SCENARIO_RECIPIENTS.values())
