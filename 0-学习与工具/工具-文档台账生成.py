"""
文档台账生成器（R2，见《文档治理规范与规整执行清单-2026-07-07》）。

扫描治理范围内目录的 md frontmatter，按七层分组产出台账，写入
1-转型规划/0-全景路线图/文档台账-自动生成.md。

用法：python 0-学习与工具/工具-文档台账生成.py
纪律：CC 每次收工重新生成一次（一行命令，见上）。

队列 #306：§一 列数校验（QUEUE_EXPECTED_COLUMNS）改从
zhuopin_platform.shared_tools.queue_table 读取权威值，不再本地硬编码。
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# 队列 #306：仅当目录真实存在时才尝试 import，缺失时（隔离环境）用本地
# 兜底桩，与 工具-共享文档编辑锁.py/工具-落库sweep.py 既有引导同一原则。
_PLATFORM_PATH = REPO_ROOT / "5-平台底座" / "zhuopin_platform"
if _PLATFORM_PATH.is_dir():
    if str(_PLATFORM_PATH) not in sys.path:
        sys.path.insert(0, str(_PLATFORM_PATH))
    from zhuopin_platform.shared_tools import queue_table  # noqa: E402
else:
    class queue_table:  # type: ignore[no-redef]
        """隔离环境兜底桩——取值须与 zhuopin_platform.shared_tools.queue_table
        保持一致，见该模块。"""

        SECTION_COLUMN_COUNTS = {"一": 8, "二": 4, "四": 4}
        QUEUE_PATH_REL = "1-转型规划/0-全景路线图/跨桌任务队列.md"

OUTPUT_PATH = REPO_ROOT / "1-转型规划" / "0-全景路线图" / "文档台账-自动生成.md"
QUEUE_PATH = REPO_ROOT / queue_table.QUEUE_PATH_REL  # 队列 #313：收拢自本地字面量
QUEUE_SECTION_ONE_HEADING = "## 一、任务看板"
QUEUE_EXPECTED_COLUMNS = queue_table.SECTION_COLUMN_COUNTS["一"]

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


# 前导装饰（**、✅、空白、破折号等）匹配前先剥离，避免 `**已生效**` 类漏判
_DECO_PREFIX = re.compile(r"^[\s*✅✓☑🟢🔵🟡🔴>#—-]+")

# 常见非枚举写法 → 六枚举（前缀匹配，避免"待…定稿"被误判成"定稿=生效"）
_STATUS_SYNONYM: list[tuple[str, str]] = [
    ("已定稿", "生效"), ("已生效", "生效"), ("规则定稿", "生效"), ("定稿", "生效"),
    ("已确认", "生效"), ("确认通过", "生效"), ("已启用", "生效"),
    ("跟进信", "生效"), ("常设机制", "生效"),
    ("已重排", "已执行归档"), ("已回复", "已执行归档"), ("已执行", "已执行归档"),
    ("已发", "已执行归档"), ("已归档", "已执行归档"), ("收口成果", "已执行归档"),
    ("待执行", "在办"), ("滚动更新", "在办"),
    ("待 VP", "在办"), ("待 CC", "在办"), ("待 Paul", "在办"),
    ("校准会", "在办"), ("CC 引用", "在办"), ("收口", "在办"),
    ("草案", "在办"), ("就绪", "在办"), ("设计稿", "在办"), ("规划稿", "在办"),
    ("评审", "在办"), ("工作", "在办"), ("备料", "在办"), ("映射", "在办"),
    ("答复", "在办"), ("建议", "在办"), ("需求", "在办"), ("模板", "在办"),
    ("分析", "在办"), ("候选", "在办"), ("审核", "在办"), ("派工", "在办"),
    ("单一入口", "在办"), ("上线收口", "在办"), ("交接", "在办"),
    ("启用稿", "在办"), ("MVP", "在办"),
    ("作废", "已作废"), ("废弃", "已作废"),
    ("快照", "历史快照"), ("历史", "历史快照"),
]


def status_bucket(status_raw: str) -> str:
    if not status_raw:
        return "（缺状态头，待补）"
    s = _DECO_PREFIX.sub("", status_raw)
    for e in STATUS_ORDER:
        if s.startswith(e):
            return e
    for kw, e in _STATUS_SYNONYM:
        if s.startswith(kw):
            return e
    return "（状态头非标准枚举，待补）"


def check_queue_row_column_counts(queue_text: str) -> list[tuple[str, int]]:
    """队列 §一「任务看板」逐行列数自检（队列 #164，2026-07-30 状态页取数时实测发现）。

    队列 #313/#314（openspec 变更包 `queue-table-backtick-aware-split`，
    commit `6d7871d`）：切列改为委托权威模块
    `queue_table.parse_section_rows`（反引号感知——CommonMark code span
    跨度内的竖线不再被误当列分隔符）。本函数此前自行实现"按 `|` 切分数
    一遍"的朴素解析，会把反引号包裹的代码示例（如 shell 命令片段）里的
    竖线误判为额外列分隔符，产生假阳性（#313 行实测命中）；委托权威模块
    后与 `工具-共享文档编辑锁.py`／`工具-队列查询.py`／`工具-队列结构
    lint.py`／`工具-落库sweep.py` 其余四处消费者判据一致，不再独立实现。

    只扫 §一 到下一个 `## ` 标题之间的表格行；跳过表头行与分隔行（`|---|...`）。

    返回 (行首 `#` 编号, 实际列数) 列表，仅含列数 ≠ 8 的行；无异常返回空列表。
    """
    start = queue_text.find(QUEUE_SECTION_ONE_HEADING)
    if start == -1:
        return []
    rest = queue_text[start + len(QUEUE_SECTION_ONE_HEADING):]
    next_heading = rest.find("\n## ")
    section = rest if next_heading == -1 else rest[:next_heading]

    anomalies: list[tuple[str, int]] = []
    for _, cells, ok in queue_table.parse_section_rows(section, "一"):
        if not ok:
            anomalies.append((cells[0] if cells else "", len(cells)))
    return anomalies


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
            if path.name == OUTPUT_PATH.name:  # 跳过脚本自身输出（每跑必覆盖，无需状态头）
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

    queue_anomalies: list[tuple[str, int]] = []
    if QUEUE_PATH.exists():
        queue_anomalies = check_queue_row_column_counts(
            QUEUE_PATH.read_text(encoding="utf-8", errors="ignore")
        )
    if queue_anomalies:
        lines.append(f"## 队列 §一 行列数自检（{len(queue_anomalies)} 处异常，队列 #164）")
        lines.append("")
        lines.append(
            f"> 标准列数 {QUEUE_EXPECTED_COLUMNS}；以下行实际列数不符，多为正文误写裸竖线"
            "（改用全角 `／`）——按列下标解析的工具会读错该行，见协议〇.8。"
        )
        lines.append("")
        for row_id, count in queue_anomalies:
            lines.append(f"- `#{row_id}`：实际 {count} 列")
        lines.append("")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"台账已生成：{OUTPUT_PATH.relative_to(REPO_ROOT)}（{total} 份，{len(missing_status)} 份待补状态头）")
    if queue_anomalies:
        print(f"⚠ 队列 §一 发现 {len(queue_anomalies)} 处行列数异常：{queue_anomalies}")


if __name__ == "__main__":
    main()
