"""队列 #341：写入目标（业务场景文件）与取号来源（机制环境文件）不是同一
份文件时，git 同步必须把**两份一起**提交（openspec 变更包
`queue-domain-routing` 决策点 2 配套修复）。

🔴 只提交写入目标那一份，高水位线的推进就永远停在工作区、推不出去——
下一个 checkout／下一次清扫读到的仍是旧值，撞号从"本地已避免"退回"跨
checkout 仍会发生"，等于把决策点 2 只做了一半。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from zhuopin_platform.shared_tools.queue_table import (
    QUEUE_BUSINESS_PATH_REL,
    QUEUE_MECHANISM_PATH_REL,
)

from aibot_service.queue_git_sync import append_task_and_sync_to_git

_MECHANISM_WITH_HWM = """\
> **编号高水位线：§一 #500 ｜ §四 #36**

## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 7 | 机制域任务 | CC | p | e | [S:open] 待领 | — | 09-01 |
"""

_BUSINESS_WITHOUT_HWM = """\
## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 300 | 业务域任务 | 采购专线 | p | e | [S:open] 待领 | — | 09-01 |
"""

_MECHANISM_NAME = Path(QUEUE_MECHANISM_PATH_REL).name
_BUSINESS_NAME = Path(QUEUE_BUSINESS_PATH_REL).name


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True,
        text=True, encoding="utf-8",
    )


def _origin_and_clone(tmp_path: Path) -> tuple[Path, Path]:
    origin = tmp_path / "origin.git"
    origin.mkdir()
    _git(origin, "init", "--bare", "-q", "-b", "master")

    clone = tmp_path / "clone"
    clone.mkdir()
    _git(clone, "init", "-q", "-b", "master")
    _git(clone, "config", "user.email", "bot@example.com")
    _git(clone, "config", "user.name", "Test Bot")
    (clone / _MECHANISM_NAME).write_text(_MECHANISM_WITH_HWM, encoding="utf-8")
    (clone / _BUSINESS_NAME).write_text(_BUSINESS_WITHOUT_HWM, encoding="utf-8")
    _git(clone, "add", "-A")
    _git(clone, "commit", "-q", "-m", "init")
    _git(clone, "remote", "add", "origin", str(origin))
    _git(clone, "push", "-q", "origin", "master")
    return origin, clone


def _show(origin: Path, rel_path: str) -> str:
    return subprocess.run(
        ["git", "--git-dir", str(origin), "show", f"master:{rel_path}"],
        check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout


def test_sync_commits_both_write_target_and_high_water_mark_source(tmp_path: Path):
    """新行落业务场景文件、高水位线推进落机制环境文件 —— 推送成功后
    **两份的改动都必须已到 origin**。"""
    origin, clone = _origin_and_clone(tmp_path)

    outcome = append_task_and_sync_to_git(
        repo_root=clone,
        queue_path=clone / _BUSINESS_NAME,
        description="企微反馈自动归档：某专员 发来文本反馈",
        owner="采购专线",
        input_pointer="指针X",
        expected_output="产出X",
        date_str="2026-09-05",
        touch_zone="",
    )

    assert outcome.pushed is True
    assert outcome.row.startswith("| 501 |")
    # 新行进了业务场景文件并推上去
    assert "| 501 |" in _show(origin, _BUSINESS_NAME)
    # 🔴 高水位线的推进也必须在 origin 上，不能只留在工作区
    assert "§一 #501" in _show(origin, _MECHANISM_NAME)
    # 工作区没有残留未提交改动（两份都进了同一个 commit）
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=clone,
        check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout.strip()
    assert status == ""
