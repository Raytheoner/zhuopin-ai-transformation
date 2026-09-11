#!/usr/bin/env python3
"""工具-未并入分支分类 —— 对 `claude/*` 未并入 master 的分支按 `#534` patch-id 口径做只读三分类（队列 §一 `#553` ⑶，`OP-0911-G`）。

## 它解决的问题

`git branch --no-merged master` 命中的 `claude/*` 分支 2026-09-10 现取 134 条，而其中
**64 条内容早已在 master**（sweep 另行提交／总线代 ff／cherry-pick，分支图上却永远显示
「未并入」）。凡按分支图数「未落地」都会把这 64 条假阴性算进去——告警从第一天起就是噪声
（分类清单 §七 的定量）。判「是否已落地」只能比产物，不看 SHA 谱系：判据正本＝
`.claude/rules/两桌同步与取证.md` §二「SHA 谱系≠内容已合入」，工具先例＝`工具-patchid比对.py`。

## 三分类（与 `分支分类清单-未并入master的claude分支patch-id三分类-2026-09-10.md` §六 同一判据）

- **A 内容已在 master**（三层，任一命中即 A）：
  ① 分支独有非 merge 提交的 patch-id **全部**在 master 侧找到等价（`git cherry` 内核）；
  ② 无等价提交触碰的全部文件在 master 尖端逐字节相同（squash／改写后合入）；
  ③ 文件后来在 master 被继续改，但无等价提交**新增的每一非空行**都已在 master 同路径文件中
    （`#482` 行级口径）。
- **C 该删**：不携带任何独有内容——是另一条未并入 `claude/*` 分支的祖先（后继分支取代），
  或未落地的行只剩过程状态文件（队列真身／接力卡／CHANGELOG／队列行日志／reports）。
- **B 真未落地**：以上皆非。🔴 **B 是上界**（§六 两处已知局限都只会让 A 漏判成 B）。

空 diff 提交（`git patch-id` 不产出行）不算「未合入」——没有内容可合（同 `工具-patchid比对.py`）；
纯 merge 提交不参与比对（`--no-merges`，同 `git cherry`）。

## 为什么带 patch-id 缓存

master 侧从最老分叉点起 2026-09-11 现取 2443 个提交，一次性算 patch-id 实测 57 s；逐分支
`git cherry` 则 ≈1.5 s × 134。提交的 patch-id 一经算出永不变（内容寻址）⇒ 按 SHA 缓存到
`reports/`（不入库），每轮只算新提交。缓存只是加速，**删掉它结果不变**。

## 用法

    python 0-学习与工具/工具-未并入分支分类.py --json
    python 0-学习与工具/工具-未并入分支分类.py --repo <path> --base master --cache reports/x.json

🔴 只读：不合并、不删除、不 fetch；`git status` 前后不变（缓存文件在 gitignore 的 `reports/` 下）。
退出码：0 ＝ 分类完成；2 ＝ git 错误（base 解析失败等）。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

CATEGORY_A = "A"
CATEGORY_B = "B"
CATEGORY_C = "C"
CATEGORY_LABELS = {CATEGORY_A: "A 内容已在 master", CATEGORY_B: "B 真未落地", CATEGORY_C: "C 该删"}

#: 候选分支的 ref 前缀（本地 heads ＋ origin 远端）；同名两侧尖端不同时各算一个候选。
CANDIDATE_REF_PREFIXES = ("refs/heads/claude/", "refs/remotes/origin/claude/")

#: 「过程状态文件」——泳道收工回写产生的、后续在 master 上必然被再次重写的文件
#: （判「该删·仅剩陈旧过程态」用；与分类清单 §六 `STATE_PATTERNS` 同一份）。
STATE_PATTERNS = [
    r"^1-转型规划/0-全景路线图/跨桌任务队列(-业务场景|-机制环境)?\.md$",
    r"^1-转型规划/0-全景路线图/跨桌任务队列-归档-\d+\.md$",
    r"^1-转型规划/0-全景路线图/session接力-.*\.md$",
    r"^1-转型规划/0-全景路线图/进度编年-CHANGELOG\.md$",
    r"^1-转型规划/0-全景路线图/队列回写待补/",
    r"^1-转型规划/0-全景路线图/队列行日志/",
    r"^reports/",
    r"^CLAUDE\.md$",
]
_STATE_RE = [re.compile(p) for p in STATE_PATTERNS]

_PATCH_ID_LINE_RE = re.compile(r"^([0-9a-f]{40})\s+([0-9a-f]{40})\s*$")
_DIFF_META_PREFIXES = ("---", "@@", "diff ", "index ", "new file", "deleted file",
                       "similarity", "rename", "Binary", "old mode", "new mode")

PATCH_ID_CACHE_VERSION = 1


class UnmergedTriageError(RuntimeError):
    """git 调用失败——调用方转成退出码 2，不得当作「零候选」。"""


def _git(repo: Optional[Path], *args: str, input_bytes: Optional[bytes] = None) -> bytes:
    cmd = ["git", "-c", "core.quotepath=false"]
    if repo is not None:
        cmd += ["-C", str(repo)]
    cmd += list(args)
    proc = subprocess.run(cmd, input=input_bytes, capture_output=True)
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace").strip()
        raise UnmergedTriageError(f"git {' '.join(args[:2])} 失败（rc={proc.returncode}）：{err[:300]}")
    return proc.stdout


def _text(b: bytes) -> str:
    return b.decode("utf-8", errors="replace")


def _lines(b: bytes) -> list[str]:
    return [ln.strip() for ln in _text(b).splitlines() if ln.strip()]


def is_state_file(path: str) -> bool:
    return any(r.search(path) for r in _STATE_RE)


# ------------------------------------------------------------------ 候选


def list_candidates(repo: Optional[Path], base: str) -> list[dict]:
    """`claude/*` 且未并入 `base` 的分支尖端：`[{name, tip, sides:[local|remote,…]}]`。

    一次 `for-each-ref --no-merged`（等价于逐条 `merge-base --is-ancestor tip base` 取反），
    同名本地／远端尖端相同合为一条，不同则各算一条（分叉的两侧都可能携带独有内容）。
    """
    out = _text(_git(repo, "for-each-ref", "--no-merged", base,
                     "--format=%(refname) %(objectname)", *[p.rstrip("/") for p in CANDIDATE_REF_PREFIXES]))
    by_key: dict[tuple[str, str], dict] = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        ref, sha = parts
        name, side = None, None
        for prefix, side_name in zip(CANDIDATE_REF_PREFIXES, ("local", "remote")):
            if ref.startswith(prefix):
                name = ref[len(prefix) - len("claude/"):]  # 保留 `claude/` 前缀
                side = side_name
                break
        if name is None:
            continue
        entry = by_key.setdefault((name, sha), {"name": name, "tip": sha, "sides": []})
        entry["sides"].append(side)
    return sorted(by_key.values(), key=lambda e: (e["name"], e["tip"]))


# ------------------------------------------------------------------ patch-id（带缓存）


def load_patch_id_cache(path: Optional[Path]) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict) or data.get("version") != PATCH_ID_CACHE_VERSION:
        return {}
    commits = data.get("commits")
    return dict(commits) if isinstance(commits, dict) else {}


def save_patch_id_cache(path: Optional[Path], cache: dict[str, str], keep: set[str]) -> None:
    """只保留本轮用到的 SHA（`keep`），缓存体积随候选集合而非随历史增长。写失败静默——它只是加速。"""
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(
            {"version": PATCH_ID_CACHE_VERSION,
             "commits": {sha: pid for sha, pid in cache.items() if sha in keep}},
            ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def patch_ids_for(repo: Optional[Path], shas: list[str], cache: dict[str, str]) -> dict[str, str]:
    """给定非 merge 提交列表的 stable patch-id：`{sha: pid}`，空 diff 提交 ⇒ `""`。

    未缓存的 SHA 走一次 `git log --no-walk --stdin -p`（不逐提交起进程；`--stdin` 绕开
    Windows 命令行长度上限）喂给一次 `git patch-id --stable`。
    """
    missing = [s for s in shas if s not in cache]
    if missing:
        log = _git(repo, "log", "--no-walk", "--stdin", "-p", "--no-merges", "--no-color",
                   "--format=commit %H", input_bytes=("\n".join(missing) + "\n").encode())
        found: dict[str, str] = {}
        if log.strip():
            for line in _text(_git(repo, "patch-id", "--stable", input_bytes=log)).splitlines():
                m = _PATCH_ID_LINE_RE.match(line.strip())
                if m:
                    found[m.group(2)] = m.group(1)
        for s in missing:
            cache[s] = found.get(s, "")
    return {s: cache[s] for s in shas}


# ------------------------------------------------------------------ 单分支分析


def _added_lines_by_file(repo: Optional[Path], sha: str) -> dict[str, list[str]]:
    """`git show --unified=0` 里该提交新增的非空行（按目标路径分组，strip 后）。"""
    out = _text(_git(repo, "show", "--unified=0", "--format=", "--no-color", sha))
    result: dict[str, list[str]] = {}
    cur: Optional[str] = None
    for ln in out.splitlines():
        if ln.startswith("+++ "):
            target = ln[4:]
            cur = None if target == "/dev/null" else (target[2:] if target.startswith("b/") else target)
            continue
        if ln.startswith(_DIFF_META_PREFIXES):
            continue
        if ln.startswith("+") and cur:
            s = ln[1:].strip()
            if s:
                result.setdefault(cur, []).append(s)
    return result


class _MasterBlobLines:
    """`git show <base>:<path>` 的非空 strip 行集合，按路径缓存（一轮内 master 不变）。"""

    def __init__(self, repo: Optional[Path], base_sha: str):
        self._repo, self._base, self._cache = repo, base_sha, {}

    def get(self, path: str) -> Optional[set[str]]:
        if path not in self._cache:
            proc = subprocess.run(
                ["git", "-c", "core.quotepath=false", *(["-C", str(self._repo)] if self._repo else []),
                 "show", f"{self._base}:{path}"], capture_output=True)
            self._cache[path] = None if proc.returncode != 0 else set(_lines(proc.stdout))
        return self._cache[path]


def analyze_branch(repo: Optional[Path], base_sha: str, cand: dict, cache: dict[str, str],
                   blobs: _MasterBlobLines, candidate_tips: set[str],
                   used_shas: Optional[set[str]] = None) -> dict:
    """三层 A 判 → C 判 → B。返回一条可机读的记录（含分类依据，供告警正文与复核）。"""
    name, tip = cand["name"], cand["tip"]
    unique = _lines(_git(repo, "rev-list", "--no-merges", "--reverse", f"{base_sha}..{tip}"))
    master_side = _lines(_git(repo, "rev-list", "--no-merges", f"{tip}..{base_sha}"))
    if used_shas is not None:
        used_shas.update(unique, master_side)
    branch_pids = patch_ids_for(repo, unique, cache)
    master_pid_set = {pid for pid in patch_ids_for(repo, master_side, cache).values() if pid}
    plus = [s for s in unique if branch_pids[s] and branch_pids[s] not in master_pid_set]
    empty = [s for s in unique if not branch_pids[s]]
    record = {
        "name": name, "tip": tip, "sides": cand["sides"],
        "unique_commits": len(unique), "cherry_plus": len(plus),
        "cherry_minus": len(unique) - len(plus) - len(empty), "empty_commits": len(empty),
        "first_unmerged_commit": None, "first_unmerged_date": None,
        "category": None, "reason": None,
    }
    if plus:
        first = plus[0]
        record["first_unmerged_commit"] = first
        record["first_unmerged_date"] = _text(_git(repo, "log", "-1", "--format=%cI", first)).strip()
    if not plus:
        record["category"], record["reason"] = CATEGORY_A, "全部独有提交 patch-id 在 master 有等价"
        return record

    # 层②：无等价提交触碰的文件在 master 尖端是否逐字节相同
    plus_files: set[str] = set()
    for s in plus:
        plus_files.update(_lines(_git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", s)))
    differ = _lines(_git(repo, "diff", "--name-only", tip, base_sha, "--", *sorted(plus_files))) if plus_files else []
    if not differ:
        record["category"], record["reason"] = (
            CATEGORY_A, "patch-id 未逐对命中，但未等价提交触碰的全部文件在 master 尖端逐字节相同")
        return record

    # 层③：行级——分支新增的每一非空行是否都已在 master 同路径文件中（#482 口径）
    missing_by_file: dict[str, int] = {}
    for s in plus:
        for path, added in _added_lines_by_file(repo, s).items():
            ml = blobs.get(path)
            for line in added:
                if ml is None or line not in ml:
                    missing_by_file[path] = missing_by_file.get(path, 0) + 1
    missing_total = sum(missing_by_file.values())
    record["missing_lines"] = missing_total
    if missing_total == 0:
        record["category"], record["reason"] = (
            CATEGORY_A, "文件后来在 master 被继续改，但分支新增的每一非空行都已在 master 同文件中")
        return record

    # C①：是另一条未并入候选分支的祖先 ⇒ 内容全在后继分支上
    superseded = []
    for line in _text(_git(repo, "for-each-ref", "--contains", tip, "--format=%(refname) %(objectname)",
                           *[p.rstrip("/") for p in CANDIDATE_REF_PREFIXES])).splitlines():
        parts = line.split()
        if len(parts) != 2 or parts[1] == tip or parts[1] not in candidate_tips:
            continue
        other = parts[0]
        for prefix in CANDIDATE_REF_PREFIXES:
            if other.startswith(prefix):
                other = other[len(prefix) - len("claude/"):]
        if other != name:
            superseded.append(f"{other}@{parts[1][:8]}")
    if superseded:
        record["category"] = CATEGORY_C
        record["reason"] = f"是后继分支的祖先（{', '.join(sorted(set(superseded))[:2])}），不携带任何独有内容"
        record["superseded_by"] = sorted(set(superseded))
        return record
    # C②：未落地的行只剩过程状态文件
    if all(is_state_file(p) for p in missing_by_file):
        record["category"] = CATEGORY_C
        record["reason"] = "未落地的行只剩过程状态文件（队列真身／接力卡／CHANGELOG／队列行日志／reports）"
        return record

    record["category"] = CATEGORY_B
    record["reason"] = (f"{len(plus)} 个独有提交无 patch-id 等价；{len(differ)} 个文件与 master 不同；"
                        f"{missing_total} 行新增内容 master 中不存在")
    record["missing_by_file"] = missing_by_file
    return record


# ------------------------------------------------------------------ 入口


def classify(*, repo: Optional[Path] = None, base: str = "master",
             cache_path: Optional[Path] = None) -> dict:
    """全量分类。返回：
        {"base", "base_sha", "generated_utc", "total", "counts": {"A","B","C"},
         "branches": [record…]（按 name 排序）,
         "b_branches": [{name, tip, first_unmerged_date}…]（按 first_unmerged_date 升序，最老在前）}
    """
    base_sha = _text(_git(repo, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")).strip()
    cands = list_candidates(repo, base_sha)
    candidate_tips = {c["tip"] for c in cands}
    cache = load_patch_id_cache(cache_path)
    keep: set[str] = set()  # 本轮两侧 rev-list 出现过的 SHA——缓存只留这些
    blobs = _MasterBlobLines(repo, base_sha)
    records = [analyze_branch(repo, base_sha, cand, cache, blobs, candidate_tips, keep) for cand in cands]
    save_patch_id_cache(cache_path, cache, keep)
    counts = {CATEGORY_A: 0, CATEGORY_B: 0, CATEGORY_C: 0}
    for r in records:
        counts[r["category"]] += 1
    b_branches = sorted(
        ({"name": r["name"], "tip": r["tip"], "first_unmerged_date": r["first_unmerged_date"],
          "sides": r["sides"], "reason": r["reason"]}
         for r in records if r["category"] == CATEGORY_B),
        key=lambda b: (b["first_unmerged_date"] or "", b["name"]),
    )
    return {
        "base": base, "base_sha": base_sha,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "total": len(records), "counts": counts,
        "branches": records, "b_branches": b_branches,
    }


def format_summary(result: dict) -> str:
    c = result["counts"]
    lines = [f"master@{result['base_sha'][:8]}：未并入 claude/* 候选 {result['total']} ＝ "
             f"A {c['A']}（内容已在 master）／B {c['B']}（真未落地）／C {c['C']}（该删）"]
    for b in result["b_branches"]:
        lines.append(f"  B {b['name']}@{b['tip'][:8]}　首个未落地提交 {(b['first_unmerged_date'] or '?')[:10]}　{b['reason']}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo", default=None, help="仓库路径（默认当前目录；worktree 内亦可，refs 共享）")
    p.add_argument("--base", default="master")
    p.add_argument("--cache", default=None, help="patch-id 缓存文件（建议 reports/ 下，不入库）；省略即不缓存")
    p.add_argument("--json", action="store_true", help="只输出 JSON（供 sweep 子进程解析）")
    return p


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    repo = Path(args.repo) if args.repo else None
    try:
        result = classify(repo=repo, base=args.base,
                          cache_path=Path(args.cache) if args.cache else None)
    except UnmergedTriageError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(format_summary(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
