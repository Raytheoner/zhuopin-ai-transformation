"""
文档台账生成器（R2，见《文档治理规范与规整执行清单-2026-07-07》）。

扫描治理范围内目录的 md frontmatter，按七层分组产出台账，写入
1-转型规划/0-全景路线图/文档台账-自动生成.md。

用法：python 0-学习与工具/工具-文档台账生成.py
纪律：CC 每次收工重新生成一次（一行命令，见上）。
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "1-转型规划" / "0-全景路线图" / "文档台账-自动生成.md"

# 治理范围目录（见文档治理规范 §二 目录职能确认）。
# 4-数字员工/5-平台底座/openspec 有各自 Hermes L2 场景级约定，不入本台账；
# 7-外部文档 gitignore、内容因机而异，不入本台账（避免台账不可复现）。
SCAN_DIRS = [
    "0-学习与工具",
    "1-转型规划",
    "2-试点项目",
    "3-治理与合规",
    "6-人才与组织",
]

STATUS_ORDER = ["生效", "在办", "待发", "已执行归档", "已作废", "历史快照"]

# 七层分类：按文件名关键词粗分（best-effort，找不到规律的落"未分类"人工复核）。
LAYER_RULES: list[tuple[str, "re.Pattern[str]"]] = [
    ("权威", re.compile(r"全景规划|实施计划|标准编排|^CLAUDE\.md$|场景描述")),
    ("机制纪律", re.compile(r"规范|机制|纪律|治理|门禁|变更日志")),
    ("接力", re.compile(r"^session接力")),
    ("交接prompt", re.compile(r"^开场prompt")),
    ("跟进通信", re.compile(r"跟进|企微|邮件")),
    ("就绪与口径", re.compile(r"就绪|口径|批改单|局部定稿|小抄|任务书|待办追踪|需求")),
    ("报告快照/归档", re.compile(r"报告|审计|体检|复盘")),
]
DEFAULT_LAYER = "未分类（待人工归层）"
LAYER_ORDER = ["权威", "机制纪律", "接力", "交接prompt", "跟进通信", "就绪与口径", "报告快照/归档", DEFAULT_LAYER]

_FRONTMATTER_KV = re.compile(r"^([\w一-鿿]+):\s*(.*)$")


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    meta: dict[str, str] = {}
    for line in text[3:end].splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _FRONTMATTER_KV.match(line)
        if m and m.group(1) not in meta:  # 首次出现为准
            meta[m.group(1)] = m.group(2).strip().strip('"')
    return meta


def classify_layer(rel_path: Path) -> str:
    if "z-已执行归档" in rel_path.parts:
        return "报告快照/归档"
    for layer, pattern in LAYER_RULES:
        if pattern.search(rel_path.name):
            return layer
    return DEFAULT_LAYER


def status_bucket(status_raw: str) -> str:
    if not status_raw:
        return "（缺状态头，待补）"
    for s in STATUS_ORDER:
        if status_raw.startswith(s):
            return s
    return "（状态头非标准枚举，待补）"


def main() -> None:
    entries: dict[str, list[tuple[str, str, str]]] = {}
    missing_status: list[str] = []

    for dirname in SCAN_DIRS:
        base = REPO_ROOT / dirname
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.md")):
            if "__pycache__" in path.parts:
                continue
            rel = path.relative_to(REPO_ROOT)
            text = path.read_text(encoding="utf-8", errors="ignore")
            meta = parse_frontmatter(text)
            title = meta.get("title", path.stem).strip('"')
            status_raw = meta.get("status", "")
            layer = classify_layer(rel)
            bucket = status_bucket(status_raw)
            if bucket.startswith("（"):
                missing_status.append(str(rel).replace("\\", "/"))
            entries.setdefault(layer, []).append((bucket, title, str(rel).replace("\\", "/")))

    total = sum(len(v) for v in entries.values())

    lines: list[str] = []
    lines.append("# 文档台账（自动生成，勿手工编辑——改动请改脚本 `0-学习与工具/工具-文档台账生成.py` 后重跑）")
    lines.append("")
    lines.append(
        f"> 生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}｜"
        f"扫描范围：{'、'.join(SCAN_DIRS)}"
        "（4-数字员工/5-平台底座/openspec 有各自 Hermes L2 场景级约定，"
        "7-外部文档 gitignore 因机而异，均不入本台账）"
    )
    lines.append(f"> 找文档先查本表，不翻目录。共 {total} 份 md，{len(missing_status)} 份待补状态头。")
    lines.append("")

    for layer in LAYER_ORDER:
        items = entries.get(layer)
        if not items:
            continue
        lines.append(f"## {layer}（{len(items)}）")
        lines.append("")
        lines.append("| 状态 | 标题 | 路径 |")
        lines.append("|------|------|------|")

        def sort_key(item: tuple[str, str, str]) -> tuple[int, str]:
            bucket, _title, rel = item
            try:
                idx = STATUS_ORDER.index(bucket)
            except ValueError:
                idx = len(STATUS_ORDER)
            return (idx, rel)

        for bucket, title, rel in sorted(items, key=sort_key):
            lines.append(f"| {bucket} | {title} | `{rel}` |")
        lines.append("")

    if missing_status:
        lines.append(f"## 待补状态头清单（{len(missing_status)}）")
        lines.append("")
        lines.append("> R1：新文档缺状态头不得交付；存量由本清单驱动补齐。")
        lines.append("")
        for rel in missing_status:
            lines.append(f"- `{rel}`")
        lines.append("")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"台账已生成：{OUTPUT_PATH.relative_to(REPO_ROOT)}（{total} 份，{len(missing_status)} 份待补状态头）")


if __name__ == "__main__":
    main()
