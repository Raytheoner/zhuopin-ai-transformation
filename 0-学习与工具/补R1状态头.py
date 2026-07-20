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

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ["0-学习与工具", "1-转型规划", "2-试点项目", "3-治理与合规", "6-人才与组织"]
SELF_OUTPUT = "文档台账-自动生成.md"


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
            if "__pycache__" in p.parts or p.name == SELF_OUTPUT:
                continue
            rel = str(p.relative_to(REPO_ROOT)).replace("\\", "/")
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
