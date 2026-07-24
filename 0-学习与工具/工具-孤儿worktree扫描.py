"""孤儿 worktree / 陈旧分支扫描（队列 #68④，值周巡检兜底项）。

背景：《构建自动化workflow设计-2026-07-21.md》§五"卫生前置"："值周巡检兜底：每周扫
ahead=0 孤儿 worktree/陈旧分支，生成清理任务交 CC（巡检只读不删）。"——协议〇.5
"收工自删 worktree"管的是单个任务自己收工时的自我清理；本脚本管的是漏网的（会话
异常退出、句柄占用删不掉、Paul 忘记确认等）留在台面上的空壳，作为值周巡检的
兜底扫描项。

**只读，不做任何删除**——`git worktree remove` / `git branch -d` 一律留给 CC 或
Paul 看了报告后手动执行（design 文档原文"巡检只读不删"，本脚本严格遵守）。

判据：ahead=0 = `git rev-list --count origin/master..<branch>` 为 0，即该分支/
worktree 的所有提交都已包含在 origin/master 里——删除不会丢失任何独有内容。
ahead=0 但工作区仍有未提交改动的 worktree，不视为"安全"候选，只作为观察项
单独列出，交人工确认那些改动是否无价值。

用法：
  python 0-学习与工具/工具-孤儿worktree扫描.py
  python 0-学习与工具/工具-孤儿worktree扫描.py --repo-root <path>   # 仅测试用
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def _run_git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", *args], cwd=cwd, capture_output=True,
        text=True, encoding="utf-8", check=check,
    )


def _resolve_repo_root(override: str | None) -> Path:
    if override is not None:
        return Path(override).resolve()
    result = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--show-toplevel"],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return Path(result.stdout.strip())


def _parse_worktree_porcelain(text: str) -> list[dict]:
    entries: list[dict] = []
    current: dict = {}
    for line in text.splitlines():
        if not line.strip():
            if current:
                entries.append(current)
                current = {}
            continue
        if line.startswith("worktree "):
            current = {"path": line[len("worktree "):].strip(), "branch": None, "detached": False}
        elif line.startswith("branch "):
            current["branch"] = line[len("branch "):].strip().removeprefix("refs/heads/")
        elif line == "detached":
            current["detached"] = True
        elif line.startswith("HEAD "):
            current["head"] = line[len("HEAD "):].strip()
    if current:
        entries.append(current)
    return entries


def _ahead_count(repo_root: Path, ref: str) -> int | None:
    """ref 相对 origin/master 的独有提交数；无法计算（如 origin/master 不存在）返回 None。"""
    result = _run_git(["rev-list", "--count", f"origin/master..{ref}"], repo_root, check=False)
    if result.returncode != 0:
        return None
    try:
        return int(result.stdout.strip())
    except ValueError:
        return None


def _is_dirty(repo_root: Path, worktree_path: str) -> bool:
    result = _run_git(["status", "--porcelain=v1"], Path(worktree_path), check=False)
    return bool(result.stdout.strip()) if result.returncode == 0 else True  # 查不出时保守当"脏"


def scan(repo_root: Path) -> dict:
    _run_git(["fetch", "origin", "master", "--quiet"], repo_root, check=False)  # 尽力而为，失败不致命

    porcelain = _run_git(["worktree", "list", "--porcelain"], repo_root).stdout
    worktrees = _parse_worktree_porcelain(porcelain)
    main_worktree = worktrees[0] if worktrees else None  # git 保证第一条恒为主工作区

    orphan_worktrees = []
    dirty_but_merged = []
    for wt in worktrees[1:] if worktrees else []:
        ref = wt.get("branch") or wt.get("head")
        if not ref:
            continue
        ahead = _ahead_count(repo_root, ref)
        if ahead != 0:
            continue
        if _is_dirty(repo_root, wt["path"]):
            dirty_but_merged.append({**wt, "ahead": ahead})
        else:
            orphan_worktrees.append({**wt, "ahead": ahead})

    worktree_branches = {wt["branch"] for wt in worktrees if wt.get("branch")}
    all_branches = [
        line.strip().removeprefix("* ").strip()
        for line in _run_git(["branch", "--list"], repo_root).stdout.splitlines()
        if line.strip()
    ]
    orphan_branches = []
    for branch in all_branches:
        if branch in worktree_branches or branch == "master":
            continue
        ahead = _ahead_count(repo_root, branch)
        if ahead == 0:
            orphan_branches.append({"branch": branch, "ahead": ahead})

    return {
        "main_worktree": main_worktree,
        "orphan_worktrees": orphan_worktrees,
        "dirty_but_merged_worktrees": dirty_but_merged,
        "orphan_branches": orphan_branches,
    }


def format_report(findings: dict) -> str:
    lines = ["=== 孤儿 worktree / 陈旧分支扫描（只读，未做任何删除） ==="]

    ow = findings["orphan_worktrees"]
    lines.append(f"\n① 孤儿 worktree 候选（ahead=0 且工作区干净，{len(ow)} 个）：")
    if not ow:
        lines.append("  （无）")
    for wt in ow:
        lines.append(f"  - {wt['path']}（分支 {wt.get('branch') or wt.get('head')}）"
                     f" → git worktree remove \"{wt['path']}\"")

    dm = findings["dirty_but_merged_worktrees"]
    lines.append(f"\n② 观察项：ahead=0 但工作区有未提交改动（{len(dm)} 个，需人工确认改动是否无价值）：")
    if not dm:
        lines.append("  （无）")
    for wt in dm:
        lines.append(f"  - {wt['path']}（分支 {wt.get('branch') or wt.get('head')}）——不建议直接删")

    ob = findings["orphan_branches"]
    lines.append(f"\n③ 孤儿分支候选（无 worktree 关联，ahead=0，{len(ob)} 个）：")
    if not ob:
        lines.append("  （无）")
    for b in ob:
        lines.append(f"  - {b['branch']} → git branch -d {b['branch']}")

    if ow or ob:
        lines.append("\n建议：以上候选交 CC 逐条执行清理（本脚本本身不删任何东西）；"
                      "若登记进队列，走协议〇.7 编辑锁后追加待领行。")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", default=None, help="仅测试用：覆盖仓库根路径")
    args = parser.parse_args()

    repo_root = _resolve_repo_root(args.repo_root)
    findings = scan(repo_root)
    print(format_report(findings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
