#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""针对指定批次/泳道的第三道闸「归属判定」独立回放（队列 §一 `#611` 归属判法销号判据⑷）。

`工具-main-leak回放.py` 只判白名单（`--extra` 也只加白名单候选），不判归属——归属需要
该泳道当时的分支/worktree 名（从批次目录的 `.opener.txt`／`.log` 现取），且需要活的
git 历史（分支若已被 `工具-泳道分支合入.ps1` ff 入 master，merge-base 会与分支尖端重合，
须改查它留的 `backup/<short>-pre-rebase` 备份 ref）——这些都不是静态补丁文件本身能提供
的信息，因此**不并进** `工具-main-leak回放.py`，另立本文件（`#611` 派单件④要求）。

白名单判据仍现取自 `工具-opener批处理执行v2.ps1`（import 该判据的姊妹文件，不留第二份
硬编码），归属判据严格复刻该脚本 `#611` 段落的算法：分支相对 fork 点新增的文件 ∪
worktree（若还在）当下的 `git status --porcelain`。

用法：
  python 0-学习与工具/工具-泄漏归属判定回放.py --batch 20260919-075655 --lane q2-A1
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import re
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
LEAK_REPLAY_SCRIPT = REPO_ROOT / "0-学习与工具" / "工具-main-leak回放.py"


def _load_leak_replay_module():
    spec = importlib.util.spec_from_file_location("_leak_replay_for_attribution", LEAK_REPLAY_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repo_root: pathlib.Path, *args: str) -> tuple[int, str]:
    p = subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout.strip()


#: 批次日志首行形如：
#: [lane:q2] A1 worktree 已建：C:\...\.claude\worktrees\op0919b-q2-redline-ppt（分支 claude/op0919b-q2-redline-ppt，新建自 master）
LOG_WT_RE = re.compile(r"worktree 已建：(.+?)（分支\s+(claude/\S+?)[，,)]", re.M)


def resolve_branch_and_worktree(batch_dir: pathlib.Path, lane_id: str) -> tuple[str | None, pathlib.Path | None]:
    log_path = batch_dir / f"{lane_id}.log"
    if not log_path.is_file():
        raise SystemExit(f"✗ 找不到 {log_path}，无法从中现取分支/worktree 名。")
    text = log_path.read_text(encoding="utf-8-sig", errors="replace")
    m = LOG_WT_RE.search(text)
    if not m:
        return None, None
    wt_path = pathlib.Path(m.group(1).strip())
    branch = m.group(2).strip()
    return branch, wt_path


def compute_branch_touched(repo_root: pathlib.Path, branch: str, wt_path: pathlib.Path | None) -> tuple[set[str], list[str]]:
    """复刻 v2.ps1 `#611` 段算法：分支相对 fork 点的改动 ∪ worktree 现存 status。

    返回 (归属集合, 取证手段说明列表)。分支若已被 ff 入 master（merge-base==分支尖端），
    改查同名 `backup/<short>-pre-rebase`（`工具-泳道分支合入.ps1` 留的 ff 前快照）。
    """
    touched: set[str] = set()
    evidence: list[str] = []

    code, base_head = _git(repo_root, "rev-parse", "--verify", "--quiet", branch)
    ref_for_diff = branch
    if code != 0:
        evidence.append(f"分支 {branch} 已不存在，尝试 backup ref")
        base_head = None

    if base_head:
        code, mb = _git(repo_root, "merge-base", "master", branch)
        if code == 0 and mb and mb == base_head:
            short = branch.split("/")[-1]
            backup_ref = f"backup/{short}-pre-rebase"
            code2, _ = _git(repo_root, "rev-parse", "--verify", "--quiet", backup_ref)
            if code2 == 0:
                evidence.append(f"分支 {branch} 已 ff 入 master（merge-base==分支尖端 {mb[:8]}），改用 {backup_ref}")
                ref_for_diff = backup_ref
            else:
                evidence.append(f"⚠ 分支 {branch} 已 ff 入 master 且无 {backup_ref} 备份，分支侧归属集合判定不了（留空，不代表「无归属」）")
                ref_for_diff = None
        elif code == 0 and mb:
            evidence.append(f"分支 {branch} 尚未 ff（merge-base {mb[:8]} ≠ 分支尖端 {base_head[:8]}），直接用分支")

    if ref_for_diff:
        code, mb2 = _git(repo_root, "merge-base", "master", ref_for_diff)
        if code == 0 and mb2:
            code3, names = _git(repo_root, "diff", "--name-only", mb2, ref_for_diff)
            if code3 == 0:
                for line in names.splitlines():
                    if line.strip():
                        touched.add(line.strip())
                evidence.append(f"`git diff --name-only {mb2[:8]} {ref_for_diff}` 共 {len(touched)} 个文件")

    if wt_path and wt_path.is_dir():
        code, status = _git(wt_path, "-c", "core.quotepath=false", "status", "--porcelain")
        if code == 0:
            extra = 0
            for line in status.splitlines():
                if not line:
                    continue
                p = line[3:]
                if p.startswith('"') and p.endswith('"'):
                    p = p[1:-1]
                if " -> " in p:
                    p = p.split(" -> ")[-1]
                if p not in touched:
                    extra += 1
                touched.add(p)
            evidence.append(f"worktree {wt_path} 仍在，现存 status 补 {extra} 个新路径")
    else:
        evidence.append(f"worktree {wt_path} 已不在（收工自删），只认分支提交历史")

    return touched, evidence


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="第三道闸归属判定独立回放（队列 #611）")
    ap.add_argument("--repo-root", default=str(REPO_ROOT))
    ap.add_argument("--batch", required=True, help="批次目录名，如 20260919-075655")
    ap.add_argument("--lane", required=True, help="泳道-序号，如 q2-A1")
    args = ap.parse_args(argv)

    repo_root = pathlib.Path(args.repo_root).resolve()
    batch_dir = repo_root / "reports" / "opener-batch" / args.batch
    patch = batch_dir / f"{args.lane}-main-leak.patch"
    if not patch.is_file():
        raise SystemExit(f"✗ 找不到 {patch}")

    leak_mod = _load_leak_replay_module()
    exact, globs = leak_mod.read_gate_whitelist(repo_root / "0-学习与工具" / "工具-opener批处理执行v2.ps1")
    allowed = leak_mod.make_predicate(exact, globs, [])
    leaks, legacy = leak_mod.leaks_of(patch)
    if legacy:
        raise SystemExit(f"✗ {patch} 是老格式补丁（无表头），本工具不解析。")

    branch, wt_path = resolve_branch_and_worktree(batch_dir, args.lane)
    print(f"批次 {args.batch} / 泳道 {args.lane}｜候选泄漏 {len(leaks)} 项｜分支={branch}｜worktree={wt_path}")

    after_whitelist = [p for p in leaks if not allowed(p)]
    print(f"白名单过滤后剩 {len(after_whitelist)} 项：{after_whitelist}")

    if not after_whitelist:
        print("⇒ 判 OK（白名单已全部覆盖，未触及归属判定）")
        return 0

    if not branch:
        raise SystemExit("✗ 现取不到该泳道分支名，无法做归属判定。")

    touched, evidence = compute_branch_touched(repo_root, branch, wt_path)
    for e in evidence:
        print(f"  · {e}")

    attributed = [p for p in after_whitelist if p in touched]
    unattributed = [p for p in after_whitelist if p not in touched]
    print(f"归属本泳道（判 FAIL）：{attributed}")
    print(f"不归属本泳道（判 OK，天然不计）：{unattributed}")

    if attributed:
        print(f"⇒ 判 FAIL：仍有 {len(attributed)} 项归属本泳道")
        return 1
    print("⇒ 判 OK：候选泄漏全部不归属本泳道（白名单外但非本泳道 worktree 实际触碰）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
