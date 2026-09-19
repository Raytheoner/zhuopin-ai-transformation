#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`*-main-leak.patch` 回放器（队列 §一 `#611` 销号判据⑶ 的执行件）。

2026-09-19 `OP-0919-K` 立。**成因是一次真实的 token 浪费**：为了判「这份补丁
还会不会判 FAIL」，当日 `cat` 了一份 `opener-A1-main-leak.patch` —— **单次回显
69.7 KB**，比整个开场（CLAUDE.md ＋ 派单件 ＋ 接力卡 ＋ digest ＝ 约 50 KB）还多
40%。而补丁正文里绝大部分是队列行的完整 diff（一行状态格可达 4 KB × 两侧）。

🔑 **判词：判 FAIL 只需要文件名，不需要 diff 正文。** 第三道闸（`工具-opener批处理
执行v2.ps1` L384–L419）的判据就是「泄漏清单里还剩几个非白名单路径」——清单全写在
补丁的 `----- 未跟踪新文件／已跟踪文件改动：<路径> -----` 表头行上。本工具只读表头。

🔴 **白名单判据不在本文件里，现取自 `工具-opener批处理执行v2.ps1`。** 复制一份到
Python 侧就等于第二份判据，闸改了而回放器没改时，回放会报「全过」而生产照旧 FAIL
——那正是本项目「接缝处各自正确、合起来矛盾」那一族（`#610`／`#611`／`#620` 同源）。
解析不到白名单一律 fail-loud 退出，不退回硬编码默认值。

用法：
  python 0-学习与工具/工具-main-leak回放.py                       # 回放全部补丁，出对照表
  python 0-学习与工具/工具-main-leak回放.py --since 20260919      # 只放某日起的批次
  python 0-学习与工具/工具-main-leak回放.py --extra '1-转型规划/0-全景路线图/跨桌任务队列-*.md' \
                                              --extra '…/合入登记/ff-patrol-*.jsonl'
        # --extra ＝ 候选修法的追加白名单（glob），用来回答「这样改能让几条转绿」
"""
from __future__ import annotations

import argparse
import fnmatch
import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
GATE_SCRIPT = REPO_ROOT / "0-学习与工具" / "工具-opener批处理执行v2.ps1"
PATCH_GLOB = "reports/opener-batch/*/*-main-leak.patch"

#: 补丁里的泄漏清单表头行——**只读这一行**，正文一律不读（见模块 docstring）。
LEAK_HEADER_RE = re.compile(
    r"^----- (?:未跟踪新文件|已跟踪文件改动)：(.+?) -----\s*$", re.M
)
#: 第三道闸白名单所在的 Where-Object 块，从 `$lp` 开始到该块结束。
GATE_WHITELIST_BLOCK_RE = re.compile(r"-not \(\s*\$lp -eq.*?\)\s*\}\)", re.S)
GATE_EQ_RE = re.compile(r"\$lp -eq '([^']+)'")
GATE_LIKE_RE = re.compile(r"\$lp -like '([^']+)'")


def read_gate_whitelist(script: pathlib.Path) -> tuple[list[str], list[str]]:
    """现取第三道闸的白名单，返回 (精确匹配项, glob 项)。解析不到即 fail-loud。"""
    if not script.is_file():
        raise SystemExit(f"✗ 找不到判据正本 {script}——白名单必须现取，不退回硬编码默认值。")
    text = script.read_text(encoding="utf-8", errors="replace")
    block = GATE_WHITELIST_BLOCK_RE.search(text)
    if not block:
        raise SystemExit(
            "✗ 在 `工具-opener批处理执行v2.ps1` 里没解析到第三道闸的白名单块"
            "（`-not ($lp -eq …)`）。闸的写法若已改动，请同步本工具的 "
            "GATE_WHITELIST_BLOCK_RE，**不要**在本文件里补一份硬编码白名单。"
        )
    body = block.group(0)
    return GATE_EQ_RE.findall(body), GATE_LIKE_RE.findall(body)


def make_predicate(exact: list[str], globs: list[str], extra: list[str]):
    pats = list(globs) + list(extra)

    def allowed(path: str) -> bool:
        return path in exact or any(fnmatch.fnmatch(path, g) for g in pats)

    return allowed


def leaks_of(patch: pathlib.Path) -> tuple[list[str], bool]:
    """返回 (泄漏路径清单, 是否老格式)。

    老格式 ＝ 2026-09-16 之前那两份纯 `git diff`、无 `----- 表头 -----` 的补丁。
    它们**不计入分母**并显式标注——把解析不了的补丁默默算成「OK」，就是给自己
    造一个只会报成功的守卫。
    """
    text = patch.read_text(encoding="utf-8", errors="replace")
    hits = LEAK_HEADER_RE.findall(text)
    if hits:
        return hits, False
    return [], text.lstrip().startswith("#") or "diff --git" in text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="第三道闸 main-leak 补丁回放（队列 #611 销号判据⑶）")
    ap.add_argument("--repo-root", default=str(REPO_ROOT))
    ap.add_argument("--since", default=None, help="只放批次目录名 >= 该前缀的（如 20260919）")
    ap.add_argument("--extra", action="append", default=[],
                    help="候选修法的追加白名单（glob，可重复）——用来回答「这样改能让几条转绿」")
    ap.add_argument("--quiet", action="store_true", help="只出汇总一行，不出逐条表")
    args = ap.parse_args(argv)

    root = pathlib.Path(args.repo_root).resolve()
    exact, globs = read_gate_whitelist(root / "0-学习与工具" / "工具-opener批处理执行v2.ps1")
    allowed = make_predicate(exact, globs, args.extra)

    patches = sorted(root.glob(PATCH_GLOB))
    if args.since:
        patches = [p for p in patches if p.parent.name >= args.since]
    if not patches:
        print("（没有匹配到任何 *-main-leak.patch）")
        return 0

    print(f"判据正本：{GATE_SCRIPT.relative_to(REPO_ROOT)}｜白名单现取 "
          f"精确 {len(exact)} 项、glob {len(globs)} 项"
          + (f"｜追加 {len(args.extra)} 项：{'、'.join(args.extra)}" if args.extra else ""))
    fail = ok = skipped = 0
    for p in patches:
        leaks, legacy = leaks_of(p)
        name = f"{p.parent.name} / {p.name.replace('-main-leak.patch', '')}"
        if not leaks:
            skipped += 1
            if not args.quiet:
                print(f"  ⏭ {name}：老格式补丁（无 `----- 表头 -----`），不解析、不计入分母")
            continue
        rest = [x for x in leaks if not allowed(x)]
        if rest:
            fail += 1
            if not args.quiet:
                print(f"  ✗ {name}：仍判 FAIL，剩 {len(rest)} 件 —— "
                      + "；".join(pathlib.PurePosixPath(x).name for x in rest))
        else:
            ok += 1
            if not args.quiet:
                print(f"  ✓ {name}：不再判 FAIL（泄漏 {len(leaks)} 件全部命中白名单）")
    total = fail + ok
    print(f"⇒ 有效分母 {total} 份：转绿 {ok}／仍 FAIL {fail}"
          + (f"；另有 {skipped} 份老格式不计入" if skipped else ""))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
