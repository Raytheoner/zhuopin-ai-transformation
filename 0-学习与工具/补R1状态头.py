"""
R1 状态头一次性回填器（配合《文档治理规范》R1 + 台账 R2）。

对治理范围内 .md：
  A. 无 frontmatter  → 顶部补 `---\nstatus: <建议>\ntitle: "<H1或文件名>"\n---`
  B. 有 frontmatter 无 status → 在开头 `---` 后插一行 `status: <建议>`
已有 status（含被台账同义词吸收的非枚举写法）一律不动——幂等。

建议状态为启发式初判（六枚举），保守默认"在办"（可逆、不误退役/误激活）；
回填后请人工/各专线在 R3 生命周期里按实精修（尤其归档件→历史快照、已执行 prompt→已执行归档）。

用法：
  预览： python 0-学习与工具/补R1状态头.py
  执行： python 0-学习与工具/补R1状态头.py --apply
执行后重跑台账：python 0-学习与工具/工具-文档台账生成.py
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ["0-学习与工具", "1-转型规划", "2-试点项目", "3-治理与合规", "6-人才与组织"]
SELF_OUTPUT = "文档台账-自动生成.md"

# 队列 #98 并入项（2026-08-17）：构建/缓存产物排除口径**从台账生成器 import**，
# 不在这里抄第二份——本脚本是台账「待补状态头」清单的执行端，两边判据一旦漂移，
# 这里就会往 `.pytest_cache/README.md` 之类的产物里真的写入 frontmatter
# （台账只是数错，本脚本是改文件，后果更重）。同一判据多份独立实现正是
# 队列 #306/#307 要收敛的形态，故此处刻意 import 而非复制。
_LEDGER_PATH = Path(__file__).resolve().with_name("工具-文档台账生成.py")
_spec = importlib.util.spec_from_file_location("_doc_ledger", _LEDGER_PATH)
_ledger = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ledger)
is_build_artifact = _ledger.is_build_artifact


def has_frontmatter(text: str) -> bool:
    return text.startswith("---") and text.find("\n---", 3) != -1


def has_status(text: str) -> bool:
    if not has_frontmatter(text):
        return False
    end = text.find("\n---", 3)
    for line in text[3:end].splitlines():
        if re.match(r"^\s*status\s*:", line):
            return True
    return False


def suggest(rel: str) -> str:
    n = Path(rel).name
    if n.startswith("session接力"):
        return "在办"
    if re.search(r"复盘|差距分析|评审结果|体检", n):
        return "历史快照"
    if re.search(r"报告|审计", n):
        return "历史快照"
    if re.search(r"实施计划|规划|规范|蓝图|架构|路径|协作架构", n):
        return "生效"
    if re.search(r"确认单|成果汇报", n):
        return "生效"
    if re.search(r"通知|正文|需求-给|需求通知|派工说明|FO视图|今日同步", n):
        return "已执行归档"
    if re.search(r"待办追踪|待决策|检查清单|就绪检查|评审清单|要点", n):
        return "在办"
    return "在办"


def first_h1(text: str, stem: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip().replace('"', "'")
    return stem


def main() -> None:
    apply = "--apply" in sys.argv
    a_add, b_add, skipped = [], [], 0
    for d in SCAN_DIRS:
        base = REPO_ROOT / d
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.md")):
            rel_path = p.relative_to(REPO_ROOT)
            if is_build_artifact(rel_path) or p.name == SELF_OUTPUT:
                continue
            rel = str(rel_path).replace("\\", "/")
            text = p.read_text(encoding="utf-8", errors="ignore")
            if text.startswith("﻿"):  # 去 BOM，防 BOM 挡住 --- 被误判为无 frontmatter 而双加头
                text = text[1:]
            if has_status(text):
                skipped += 1
                continue
            s = suggest(rel)
            if not has_frontmatter(text):
                title = first_h1(text, p.stem)
                new = f'---\nstatus: {s}\ntitle: "{title}"\n---\n\n' + text
                a_add.append((rel, s))
            else:
                idx = text.index("\n") + 1  # 开头 --- 行之后
                new = text[:idx] + f"status: {s}\n" + text[idx:]
                b_add.append((rel, s))
            if apply:
                p.write_text(new, encoding="utf-8")

    mode = "已写入" if apply else "预览（未写；加 --apply 执行）"
    print(f"[{mode}] A补整头={len(a_add)}  B插status={len(b_add)}  合计={len(a_add)+len(b_add)}  已有status跳过={skipped}")
    for rel, s in a_add:
        print(f"  A [{s}] {rel}")
    for rel, s in b_add:
        print(f"  B [{s}] {rel}")


if __name__ == "__main__":
    main()
