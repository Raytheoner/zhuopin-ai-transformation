#!/usr/bin/env python3
"""工具-patchid比对 —— 判「某活是否已做」看**产物在不在 master**，不看分支 SHA 谱系（队列 §一 `#534`，`OP-0910-Y`）。

## 它解决的问题

apply 期常在分支与 master 两条线上各提交一份（sweep 自动落库／总线代 ff 后
分支侧 ⏸ 态无人回写），于是分支图上永远显示「未并入」、行内长期写着「待你
拍板 ff」，**而内容其实早已在 master**——`#455`（三个提交 patch-id 逐对相同，
内容 2026-09-05 即已进 master，行内一直写「待拍板 ff」，白占了 2026-09-07 合审
的一个决策位）、`#341`（2026-09-10 用三点 diff `master...分支` 误判「+1452 行
未合入」，实为 100% 已在 master）、`#452`／`#482`／`#504` 同形态。判据正本＝
`.claude/rules/两桌同步与取证.md` §二「SHA 谱系≠内容已合入」。

## 判据（为什么是 patch-id，不是三点 diff、也不是 blob 比对）

- **三点 diff `master...分支`** ＝ diff(merge-base, 分支)。分支相对 merge-base 当然
  有新增行，master 有没有同样的行它根本不看 ⇒ 内容已合入也报「+N 行」（`#341`
  的误判来源）。
- **blob 逐字节比对**（`git diff master 分支 -- <files>`）：等价提交的文件**后来在
  master 被继续改写是常态**（`#341` 那 7 个文件里 3 个此后又被改过），文件不同
  ≠ 未落地。
- **patch-id**（`git patch-id --stable`）：对每个独有提交的 diff 内容做归一化哈希，
  与 master 侧独有提交逐一比对——**同一份改动无论被 cherry-pick、rebase 还是
  sweep 另行提交，patch-id 都相同**。全部对上 ⇒ 内容已在 master；这正是
  `git cherry` 的内核，本工具把它做成带证据（逐对 patch-id ＋ 命中文件数）、
  可被状态机 `pause` 路径调用的形态。

## 三态结论（`verdict`）

- `in_master`：分支独有提交（不含 merge 提交）**全部**在 master 侧找到 patch-id
  等价提交，或分支本就是 master 祖先（独有提交 0 条）⇒ 无需停等 ff。
- `needs_merge`：至少一个独有提交在 master 侧**没有** patch-id 等价提交 ⇒ 真需
  ff，照旧停等。
- 空 diff 提交（`git log -p` 不产出 patch-id）不算「未合入」——它没有内容可合；
  但会在证据里单列（`empty_commits`），不静默吞掉。

🔴 **本工具只判「内容是否已在 master」，不判「该不该合」**——`needs_merge` 只是
「照旧停等」，不是「可以自动 ff」；🟡 档处置一字不变。

## 用法

    python 0-学习与工具/工具-patchid比对.py --branch claude/op0905n-editrow-guard-455
    python 0-学习与工具/工具-patchid比对.py --branch <ref> --base origin/master --json

退出码：0 ＝ `in_master`；1 ＝ `needs_merge`；2 ＝ 参数／git 错误（ref 不存在等）。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

#: `git patch-id --stable` 每行输出：`<patch-id> <commit-id>`。
_PATCH_ID_LINE_RE = re.compile(r"^([0-9a-f]{40})\s+([0-9a-f]{40})\s*$")

VERDICT_IN_MASTER = "in_master"
VERDICT_NEEDS_MERGE = "needs_merge"


class PatchIdCompareError(RuntimeError):
    """git 调用失败（ref 不存在／不是仓库等）——调用方转成退出码 2，不得被当作
    「真需 ff」或「已在 master」中的任何一种。"""


def _git(repo: Optional[Path], *args: str, input_bytes: Optional[bytes] = None) -> bytes:
    cmd = ["git"]
    if repo is not None:
        cmd += ["-C", str(repo)]
    cmd += list(args)
    proc = subprocess.run(cmd, input=input_bytes, capture_output=True)
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace").strip()
        raise PatchIdCompareError(f"git {' '.join(args[:2])} 失败（rc={proc.returncode}）：{err}")
    return proc.stdout


def _text(b: bytes) -> str:
    return b.decode("utf-8", errors="replace")


def resolve_ref(repo: Optional[Path], ref: str) -> str:
    """把 ref 解析成完整 SHA；解析不出即抛 `PatchIdCompareError`（不猜、不回落）。"""
    try:
        return _text(_git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")).strip()
    except PatchIdCompareError as exc:
        raise PatchIdCompareError(f"ref `{ref}` 解析失败：{exc}") from exc


def list_unique_commits(repo: Optional[Path], base: str, tip: str) -> list[str]:
    """`base..tip` 的非 merge 提交（父在前、子在后，便于按时间读证据）。"""
    out = _text(_git(repo, "rev-list", "--no-merges", "--reverse", f"{base}..{tip}"))
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def count_merge_commits(repo: Optional[Path], base: str, tip: str) -> int:
    out = _text(_git(repo, "rev-list", "--merges", f"{base}..{tip}"))
    return len([ln for ln in out.splitlines() if ln.strip()])


def master_side_revs(repo: Optional[Path], base: str, tip: str) -> list[str]:
    """master 侧参与比对的提交范围（rev 参数列表，交给 `git log`）。

    朴素写法是 `tip..base`（`git cherry` 的口径），但分支若把 master **合进过
    自己**（merge master into branch），master 就成了分支的祖先、`tip..base` 为空，
    master 上那份等价提交明明存在却扫不到 ⇒ 假「真需 ff」。故改为：master 侧＝
    `base` 减去分支独有非 merge 提交的**外部父**（父不在 `base..tip` 里的那些，
    即分叉点）——`base ^fork1 ^fork2 …`。分叉点之前是两边共有的历史，不可能是
    「另行提交的同一份改动」，排除它们只省时间不丢命中；分叉点之后的 master
    提交全在范围内，不管分支后来有没有把 master 合进来。
    独有提交为空（分支已是祖先）时退回 `tip..base`（结果也为空，只为形状一致）。
    """
    out = _text(_git(repo, "rev-list", "--parents", "--no-merges", f"{base}..{tip}"))
    unique_all = set(
        ln.strip() for ln in _text(_git(repo, "rev-list", f"{base}..{tip}")).splitlines() if ln.strip()
    )
    external_parents: list[str] = []
    for line in out.splitlines():
        parts = line.split()
        if not parts:
            continue
        for parent in parts[1:]:
            if parent not in unique_all and parent not in external_parents:
                external_parents.append(parent)
    if not external_parents:
        return [f"{tip}..{base}"]
    return [base] + [f"^{p}" for p in external_parents]


def patch_ids_for_revs(repo: Optional[Path], revs: list[str]) -> dict[str, str]:
    """给定 rev 参数（如 `["base..tip"]` 或 `["base", "^fork"]`）内每个非 merge
    提交的 stable patch-id：`{commit_sha: patch_id}`。

    一次 `git log -p` 喂给一次 `git patch-id --stable`（与 `git cherry` 内核同一
    手法），不逐提交起进程。空 diff 提交不产出行 ⇒ 不在返回的字典里，由调用方
    按「空提交」单列。
    """
    log = _git(
        repo, "log", "-p", "--no-merges", "--no-color", "--format=commit %H", *revs,
    )
    if not log.strip():
        return {}
    out = _text(_git(repo, "patch-id", "--stable", input_bytes=log))
    result: dict[str, str] = {}
    for line in out.splitlines():
        m = _PATCH_ID_LINE_RE.match(line.strip())
        if not m:
            continue
        patch_id, commit = m.group(1), m.group(2)
        result[commit] = patch_id
    return result


def files_of_commit(repo: Optional[Path], sha: str) -> list[str]:
    out = _text(_git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", sha))
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def subject_of_commit(repo: Optional[Path], sha: str) -> str:
    return _text(_git(repo, "log", "-1", "--format=%s", sha)).strip()


def compare(*, branch: str, base: str = "master", repo: Optional[Path] = None) -> dict:
    """核心判定：分支独有提交逐个取 patch-id，与 master 侧独有提交比对。

    返回：
        {
          "branch", "base", "branch_sha", "base_sha",
          "verdict": "in_master" | "needs_merge",
          "all_in_master": bool,
          "unique_commit_count": int,      # 分支独有非 merge 提交数
          "merge_commit_count": int,       # 分支独有 merge 提交数（不参与比对，单列）
          "matched": [ {sha, subject, patch_id, master_sha, files} ... ],
          "missing": [ {sha, subject, patch_id, files} ... ],
          "empty_commits": [ {sha, subject} ... ],
          "hit_file_count": int,           # matched 触碰文件去重数
          "missing_file_count": int,       # missing 触碰文件去重数
        }
    """
    branch_sha = resolve_ref(repo, branch)
    base_sha = resolve_ref(repo, base)

    unique = list_unique_commits(repo, base_sha, branch_sha)
    merges = count_merge_commits(repo, base_sha, branch_sha)
    branch_pids = patch_ids_for_revs(repo, [f"{base_sha}..{branch_sha}"])
    # master 侧：分叉点之后的 master 提交（见 `master_side_revs`，含分支曾把
    # master 合进自己的形态）——分叉点之前两边共有，不可能是「另行提交的同一份
    # 改动」，扫它们只多花时间。
    master_pids = patch_ids_for_revs(repo, master_side_revs(repo, base_sha, branch_sha))
    master_by_pid: dict[str, str] = {}
    for sha, pid in master_pids.items():
        # 同一 patch-id 在 master 上多次出现时记最早的一次（`git log` 子在前，
        # 这里取字典里最后写入的＝最早的父）。
        master_by_pid[pid] = sha

    matched: list[dict] = []
    missing: list[dict] = []
    empty: list[dict] = []
    for sha in unique:
        subject = subject_of_commit(repo, sha)
        pid = branch_pids.get(sha)
        if pid is None:
            empty.append({"sha": sha, "subject": subject})
            continue
        files = files_of_commit(repo, sha)
        master_sha = master_by_pid.get(pid)
        if master_sha is not None:
            matched.append({
                "sha": sha, "subject": subject, "patch_id": pid,
                "master_sha": master_sha, "files": files,
            })
        else:
            missing.append({"sha": sha, "subject": subject, "patch_id": pid, "files": files})

    all_in_master = not missing
    hit_files = {f for m in matched for f in m["files"]}
    missing_files = {f for m in missing for f in m["files"]}
    return {
        "branch": branch,
        "base": base,
        "branch_sha": branch_sha,
        "base_sha": base_sha,
        "verdict": VERDICT_IN_MASTER if all_in_master else VERDICT_NEEDS_MERGE,
        "all_in_master": all_in_master,
        "unique_commit_count": len(unique),
        "merge_commit_count": merges,
        "matched": matched,
        "missing": missing,
        "empty_commits": empty,
        "hit_file_count": len(hit_files),
        "missing_file_count": len(missing_files),
    }


def format_evidence(result: dict) -> str:
    """人读证据：一行结论 ＋ 逐对 patch-id。可直接贴进队列行／等人通知。"""
    short = lambda s: s[:8]  # noqa: E731
    head = (
        f"{result['branch']}@{short(result['branch_sha'])} vs {result['base']}@{short(result['base_sha'])}："
        f"独有提交 {result['unique_commit_count']}"
    )
    if result["merge_commit_count"]:
        head += f"（另 merge 提交 {result['merge_commit_count']} 个不参与比对）"
    if result["all_in_master"]:
        if result["unique_commit_count"] == 0:
            head = "✓ 内容已在 master（分支已是 master 祖先，独有提交 0）：" + head
        else:
            head = (
                f"✓ 内容已在 master：{head}，patch-id 全部对上"
                f"（命中文件 {result['hit_file_count']}）"
            )
    else:
        head = (
            f"✗ 真需 ff：{head}，未在 master {len(result['missing'])} 个"
            f"（触碰文件 {result['missing_file_count']}）"
        )
    lines = [head]
    for m in result["matched"]:
        lines.append(
            f"  = {short(m['sha'])} ≡ master {short(m['master_sha'])}　patch-id {short(m['patch_id'])}"
            f"　{len(m['files'])} 文件　{m['subject']}"
        )
    for m in result["missing"]:
        lines.append(
            f"  + {short(m['sha'])} 无等价　patch-id {short(m['patch_id'])}"
            f"　{len(m['files'])} 文件　{m['subject']}"
        )
    for e in result["empty_commits"]:
        lines.append(f"  · {short(e['sha'])} 空 diff（无内容可合）　{e['subject']}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--branch", required=True, help="待合分支（任意可解析 ref：分支名／SHA／origin/x）")
    p.add_argument("--base", default="master", help="比对基准，默认 master")
    p.add_argument("--repo", default=None, help="仓库路径（默认当前目录；worktree 内亦可，refs 共享）")
    p.add_argument("--json", action="store_true")
    return p


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    repo = Path(args.repo) if args.repo else None
    try:
        result = compare(branch=args.branch, base=args.base, repo=repo)
    except PatchIdCompareError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2
    print(format_evidence(result))
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    return 0 if result["all_in_master"] else 1


if __name__ == "__main__":
    sys.exit(main())
