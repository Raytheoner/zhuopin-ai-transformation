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

第三个桶（队列 #267，2026-08-08 加）：ahead=0 且 tracked 干净，但工作区内存在
`.gitignore` 命中的非空内容（如 `reports/`、`.env`、`real_frozen/`、`*.db`）——
这类内容不会被 `git status --porcelain`（不带 `--ignored`）识别，此前会被误判为
"安全可删"落进第①桶，而 `git worktree remove` 实际会把这些文件一并永久清空。
**真实事故（非假想）**：队列 #262/#263 两份签字审计报告落在某 worktree 的
`reports/`（gitignore 命中），该 worktree 被判定为"ahead=0 且干净"后
`git worktree remove`，两份文件随之真实丢失，事后靠重新独立核验补救——详见
队列 #267。本桶只做标注、逐个列出具体路径，不做任何删除，红线与前两桶一致。
**边界（如实登记，不得假装闭合，Shao Peishen 2026-08-07 明示要求）**：它只覆盖
『经工具走』的路径，直接手敲 `git worktree remove` 仍无拦截——本次事故本身
正是手敲触发，要覆盖需在 `remove` 前加包装器，经评估判断不值得（多一层包装即
多一个可绕过物），故未做，如实登记为未覆盖缺口。

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


# ============================================================
# 队列 §一 #338 子项 B（2026-08-23，OP-0823-G）：落后列
# ============================================================
# 报告新增一列「落后 master N 个提交（其中触碰 CLAUDE.md M 个）」。
# **纯增列**：不改任何删除判定、不新增桶、不新增删除能力（#338 原文约束）。
#
# 立这一列的实测理由（memory 体系审核 2026-08-16 报告 F5）：13 份 worktree
# 内的 `CLAUDE.md` 副本在 89,908–132,100 B 之间各版本并存 ⇒ **在陈旧
# worktree 里开的 CC session，载入的是旧版规则，而它不会报任何错**。
#
# 🔴 落后一律用 **git 提交计数**，不用 mtime（#338 预授权④，A9 教训），
# 也不用 `git log -L`／`blame`——队列行号随上方增删漂移，那两者会静默给出
# 另一行的历史。
CLAUDE_MD_REL = "CLAUDE.md"


def _behind_base(repo_root: Path) -> str | None:
    """落后的比较基准：优先本地 `master`（ff 对齐的目标就是它），退
    `origin/master`。**返回值会被打进报告标题**——两个工具若用了不同基准，
    数字会对不上，而对不上的数字没有标注就是又一个静默陷阱。"""
    for ref in ("master", "origin/master"):
        result = _run_git(["rev-parse", "--verify", "--quiet", ref], repo_root, check=False)
        if result.returncode == 0 and result.stdout.strip():
            return ref
    return None


def _behind_counts(repo_root: Path, wt: dict, base: str | None) -> tuple[int | None, int | None]:
    """返回 `(HEAD 落后 base 的提交数, 其中触碰 CLAUDE.md 的提交数)`。

    取不到时返回 `(None, None)`，调用方一律渲染成「未取到」——
    🔴 **绝不渲染成 0**：0 的含义是「已对齐」，与「查不出来」是两件事，
    把后者显示成前者，一个该清的空壳就会长得跟一个健康的 worktree 一样。

    🔴 判 worktree 身份**只认两件事**：该目录内 `.git` 条目存在 ＋ 它在
    `git worktree list --porcelain` 注册项内（本函数的入参就来自该注册项）。
    **不看 `git -C <目录>` 的输出**——#98 实测：对非注册目录跑 `git -C`，
    git 会静默向上找到主工作区的 `.git` 并返回**主工作区**的状态（当时返回
    「分支=master／落后 0／脏 0」，照抄就会把一个该清的空壳记成「干净、
    无需处理」）。
    """
    if base is None:
        return None, None
    head = wt.get("head")
    if not head or set(head) == {"0"}:      # 物理空壳：HEAD 全零
        return None, None
    if not (Path(wt["path"]) / ".git").exists():
        return None, None
    rev_range = f"{head}..{base}"
    counts = []
    for pathspec in ([], ["--", CLAUDE_MD_REL]):
        result = _run_git(["rev-list", "--count", rev_range, *pathspec], repo_root, check=False)
        text = result.stdout.strip()
        counts.append(int(text) if result.returncode == 0 and text.isdigit() else None)
    return counts[0], counts[1]


def _behind_label(wt: dict) -> str:
    """渲染成报告里那一列。取不到一律写「未取到」，不写 0。"""
    total = wt.get("behind")
    if total is None:
        return "落后未取到"
    claude = wt.get("behind_claude")
    claude_shown = "未取到" if claude is None else str(claude)
    return f"落后 {total} 个提交（其中触碰 {CLAUDE_MD_REL} 的 {claude_shown} 个）"


def _is_dirty(repo_root: Path, worktree_path: str) -> bool:
    result = _run_git(["status", "--porcelain=v1"], Path(worktree_path), check=False)
    return bool(result.stdout.strip()) if result.returncode == 0 else True  # 查不出时保守当"脏"


def _has_any_file(path: Path) -> bool:
    """path 自身是文件，或是包含至少一个文件（递归）的目录——用于排除"目录存在
    但完全为空"的假阳性：git 对显式匹配 ignore 规则的目录，即便其内容为空，
    `--ignored=matching` 仍会原样报告该目录（已实测坐实，非文档推测），必须
    再查一次文件系统才能兑现"非空内容"这个判据。"""
    if path.is_file():
        return True
    if path.is_dir():
        return any(p.is_file() for p in path.rglob("*"))
    return False  # 路径已不存在


def _ignored_content_paths(worktree_path: str) -> list[str]:
    """worktree 内命中 `.gitignore` 规则的非空内容路径。

    `--ignored=matching` 对显式匹配某条 ignore 规则的目录只报告目录本身一行
    （不展开成员文件——已实测坐实，`traditional`/`matching` 两模式的差异只体现
    在"目录本身不匹配、但内容全被忽略"这一更细分场景，本项目 `.gitignore` 里
    `**/reports/` 这类目录级规则不落在那个场景）；对单独匹配的文件（如 `.env`）
    则逐个列出。查不出时（如路径已不存在）返回空列表——本函数是"锦上添花"的
    第三桶，缺失信息不应生成误导性阻塞项，这与 `_is_dirty` 遇错误时保守判"脏"
    的策略刻意不同：那里判断的是"能不能安全删"，本函数只是在"已判定安全"之后
    再加一层如实标注。
    """
    result = _run_git(
        ["status", "--porcelain=v1", "--ignored=matching"], Path(worktree_path), check=False,
    )
    if result.returncode != 0:
        return []
    wt_path = Path(worktree_path)
    candidates = [line[3:].strip() for line in result.stdout.splitlines() if line.startswith("!! ")]
    return [p for p in candidates if _has_any_file(wt_path / p)]


def scan(repo_root: Path) -> dict:
    _run_git(["fetch", "origin", "master", "--quiet"], repo_root, check=False)  # 尽力而为，失败不致命

    porcelain = _run_git(["worktree", "list", "--porcelain"], repo_root).stdout
    worktrees = _parse_worktree_porcelain(porcelain)
    main_worktree = worktrees[0] if worktrees else None  # git 保证第一条恒为主工作区

    # #338 子项 B：先给**每个**注册 worktree 算落后列。刻意放在归桶之前、
    # 且遍历的是全部注册项——归桶只覆盖 ahead=0 的那些，而「载入了旧版规则」
    # 这件事跟 ahead 是不是 0 毫无关系。
    behind_base = _behind_base(repo_root)
    for wt in worktrees[1:] if worktrees else []:
        wt["behind"], wt["behind_claude"] = _behind_counts(repo_root, wt, behind_base)

    orphan_worktrees = []
    dirty_but_merged = []
    ignored_content_worktrees = []
    for wt in worktrees[1:] if worktrees else []:
        ref = wt.get("branch") or wt.get("head")
        if not ref:
            continue
        ahead = _ahead_count(repo_root, ref)
        if ahead != 0:
            continue
        if _is_dirty(repo_root, wt["path"]):
            dirty_but_merged.append({**wt, "ahead": ahead})
            continue
        ignored_paths = _ignored_content_paths(wt["path"])
        if ignored_paths:
            ignored_content_worktrees.append({**wt, "ahead": ahead, "ignored_paths": ignored_paths})
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
        "ignored_content_worktrees": ignored_content_worktrees,
        "orphan_branches": orphan_branches,
        # #338 子项 B：全部注册 worktree（不含主工作区）及其落后列。
        "all_worktrees": worktrees[1:] if worktrees else [],
        "behind_base": behind_base,
    }


def format_report(findings: dict) -> str:
    lines = ["=== 孤儿 worktree / 陈旧分支扫描（只读，未做任何删除） ==="]

    ow = findings["orphan_worktrees"]
    lines.append(f"\n① 孤儿 worktree 候选（ahead=0 且工作区干净，{len(ow)} 个）：")
    if not ow:
        lines.append("  （无）")
    for wt in ow:
        lines.append(f"  - {wt['path']}（分支 {wt.get('branch') or wt.get('head')}"
                     f"｜{_behind_label(wt)}）"
                     f" → git worktree remove \"{wt['path']}\"")

    dm = findings["dirty_but_merged_worktrees"]
    lines.append(f"\n② 观察项：ahead=0 但工作区有未提交改动（{len(dm)} 个，需人工确认改动是否无价值）：")
    if not dm:
        lines.append("  （无）")
    for wt in dm:
        lines.append(f"  - {wt['path']}（分支 {wt.get('branch') or wt.get('head')}"
                     f"｜{_behind_label(wt)}）——不建议直接删")

    ic = findings["ignored_content_worktrees"]
    lines.append(
        f"\n③ 观察项：ahead=0 且 tracked 干净，但存在 .gitignore 命中的非空内容（{len(ic)} 个）——"
        "删除将永久销毁以下不在 git 里的文件（队列 #267，真实事故：#262/#263 两份签字审计报告"
        "曾因此被 `git worktree remove` 一并清空）。**边界（如实登记，不得假装闭合）**："
        "它只覆盖『经工具走』的路径，直接手敲 `git worktree remove` 仍无拦截："
    )
    if not ic:
        lines.append("  （无）")
    for wt in ic:
        lines.append(f"  - {wt['path']}（分支 {wt.get('branch') or wt.get('head')}"
                     f"｜{_behind_label(wt)}）"
                     "——不在 git 里、删除即永久丢失：")
        for p in wt["ignored_paths"]:
            lines.append(f"      · {p}")

    ob = findings["orphan_branches"]
    lines.append(f"\n④ 孤儿分支候选（无 worktree 关联，ahead=0，{len(ob)} 个）：")
    if not ob:
        lines.append("  （无）")
    for b in ob:
        lines.append(f"  - {b['branch']} → git branch -d {b['branch']}")

    # #338 子项 B：全部注册 worktree 的落后一览。①②③ 只覆盖 ahead=0 的
    # 那些，而「在陈旧 worktree 里开的 session 载入旧版规则」与 ahead 无关，
    # 故本节单列，**只报告、不产生任何清理建议**。
    aw = findings.get("all_worktrees") or []
    base = findings.get("behind_base") or "（基准未取到）"
    lines.append(f"\n⑤ 全部注册 worktree 的落后一览（基准 {base}，只读不建议清理，"
                 f"{len(aw)} 个）——在陈旧 worktree 里开的 session 载入的是旧版规则，"
                 "且不会报任何错：")
    if not aw:
        lines.append("  （无）")
    for wt in sorted(aw, key=lambda w: -(w.get("behind") if w.get("behind") is not None else -1)):
        lines.append(f"  - {Path(wt['path']).name}（分支 {wt.get('branch') or wt.get('head')}）"
                     f"｜{_behind_label(wt)}")

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
