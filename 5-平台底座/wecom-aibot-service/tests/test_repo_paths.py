"""repo_paths.py 单测（队列 #126）：覆盖"同 worktree / 跨 worktree / 跨
repo"三种拓扑形态下 `resolve_repo_root` 的解析行为，以及 `resolve_audit_path`
的落点计算。"""
from __future__ import annotations

import subprocess
from pathlib import Path

from aibot_service.repo_paths import (
    AUDIT_RELATIVE_PATH,
    PENDING_QUEUE_APPENDS_RELATIVE_PATH,
    PENDING_QUEUE_LOCK_APPENDS_RELATIVE_PATH,
    REPO_ROOT_OVERRIDE_ENV,
    resolve_audit_path,
    resolve_pending_queue_appends_path,
    resolve_pending_queue_lock_appends_path,
    resolve_repo_root,
)


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8"
    )


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", "master")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")
    (path / "seed.txt").write_text("seed", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "init")
    return path


def test_resolve_repo_root_same_checkout(tmp_path: Path):
    """同 worktree 形态：锚点与传入的 fallback 本就是同一个 checkout——
    解析结果应等于该 checkout 自身根（即修复前的既有行为，零回归）。"""
    repo = _init_repo(tmp_path / "repo")
    unrelated_fallback = tmp_path / "never_used"

    resolved = resolve_repo_root(repo / "seed.txt", fallback=unrelated_fallback, env={})

    assert resolved.resolve() == repo.resolve()


def test_resolve_repo_root_cross_worktree(tmp_path: Path):
    """跨 worktree 形态（队列 #126 核心场景）：锚点文件实际落在链接
    worktree B 里，调用方却传入了 worktree A 的根作为 `fallback`——解析
    必须以锚点所在的 worktree B 为准，而不是盲目信任 fallback。"""
    main_repo = _init_repo(tmp_path / "main_repo")
    worktree_b = tmp_path / "worktree_b"
    _git(main_repo, "worktree", "add", "-q", "-b", "feature", str(worktree_b))

    anchor = worktree_b / "seed.txt"  # 每个 worktree 都有自己的工作区副本
    assert anchor.exists()

    resolved = resolve_repo_root(anchor, fallback=main_repo, env={})

    assert resolved.resolve() == worktree_b.resolve()
    assert resolved.resolve() != main_repo.resolve()


def test_resolve_repo_root_cross_repo(tmp_path: Path):
    """跨 repo 形态（如未来 Mac 独立 clone）：锚点所在仓库与传入的
    `fallback` 是两个完全无关的仓库——解析仍应以锚点自身所属仓库为准。"""
    repo_a = _init_repo(tmp_path / "repo_a")
    repo_b = _init_repo(tmp_path / "repo_b")

    resolved = resolve_repo_root(repo_b / "seed.txt", fallback=repo_a, env={})

    assert resolved.resolve() == repo_b.resolve()


def test_resolve_repo_root_falls_back_when_anchor_not_in_any_repo(tmp_path: Path):
    """锚点根本不在任何 git 工作树里（如极端环境异常）——"解析失败才回落
    现状"，返回调用方提供的 `fallback`，不引入新的失败模式。"""
    not_a_repo = tmp_path / "plain_dir"
    not_a_repo.mkdir()
    (not_a_repo / "file.md").write_text("x", encoding="utf-8")
    fallback = tmp_path / "fallback_root"

    resolved = resolve_repo_root(not_a_repo / "file.md", fallback=fallback, env={})

    assert resolved == fallback


def test_resolve_repo_root_env_override_wins_over_git_resolution(tmp_path: Path):
    """`WECOM_AIBOT_REPO_ROOT` 显式覆盖——即便锚点能被 git 正常解析到另一
    个仓库根，override 优先级最高，直接采用。"""
    repo = _init_repo(tmp_path / "repo")
    override_root = tmp_path / "explicit_override"

    resolved = resolve_repo_root(
        repo / "seed.txt", fallback=tmp_path / "unused",
        env={REPO_ROOT_OVERRIDE_ENV: str(override_root)},
    )

    assert resolved == override_root


def test_resolve_repo_root_defaults_to_os_environ_when_env_not_passed(tmp_path: Path, monkeypatch):
    """`env` 未显式传入时读取真实进程环境变量（生产用法）。"""
    override_root = tmp_path / "explicit_override_via_os_environ"
    monkeypatch.setenv(REPO_ROOT_OVERRIDE_ENV, str(override_root))

    resolved = resolve_repo_root(tmp_path / "whatever.md", fallback=tmp_path / "unused")

    assert resolved == override_root


def test_resolve_audit_path_anchors_under_repo_root(tmp_path: Path):
    resolved = resolve_audit_path(tmp_path)

    assert resolved == tmp_path / AUDIT_RELATIVE_PATH
    assert resolved.as_posix().endswith(
        "5-平台底座/wecom-aibot-service/reports/wecom_aibot_audit.jsonl"
    )


# ── 队列 #192-C：两个 pending 暂存文件路径与 resolve_audit_path 同源 ───────

def test_resolve_pending_queue_appends_path_anchors_under_repo_root(tmp_path: Path):
    resolved = resolve_pending_queue_appends_path(tmp_path)

    assert resolved == tmp_path / PENDING_QUEUE_APPENDS_RELATIVE_PATH
    assert resolved.parent == resolve_audit_path(tmp_path).parent  # 与 audit 同一目录


def test_resolve_pending_queue_lock_appends_path_anchors_under_repo_root(tmp_path: Path):
    resolved = resolve_pending_queue_lock_appends_path(tmp_path)

    assert resolved == tmp_path / PENDING_QUEUE_LOCK_APPENDS_RELATIVE_PATH
    assert resolved.parent == resolve_audit_path(tmp_path).parent
    assert resolved != resolve_pending_queue_appends_path(tmp_path)  # 两个暂存文件物理分开
