"""跟进信 README 只读 digest CLI（队列 §一 #382⑵，2026-09-02）。

## 它解决的问题

巡逻章程 `huijian-chaijian-patrol.SKILL.md` §一.3「待发信盘点」此前要求每班
读跟进信 README **全文**（206 KB 级）去数三态分布 ＋ 核对交叉红标——同 §一.0
「扫全池不通读真身」对队列文件已经解决的问题，README 这边一直没有对应
的 digest 通道。本工具补的就是这一个：结构性逐行扫描「现有跟进信清单」表，
不读整份文件的其余 200 KB 散文。

## 状态列 digest 算法（区别于队列 `--digest` 的字符宽度截断）

队列 `--digest`（`工具-队列查询.py`）对"任务"列做**字符宽度**截断（默认
40 字），这在 2026-09-02 当天已实测致错一次（队列 §一 `#439` 追记：截断
落在关键词之外，导致并入审核关键词搜索结构性漏检）。

README 的「发送状态」列不适合套用同一算法：这一列的**语义**完全由一个
固定的前缀词表决定（`followup_gate.CLOSED_STATUS_PREFIXES` /
`IN_FLIGHT_STATUS_PREFIXES` / `REPLY_ARRIVED_STATUS`，全项目状态判据的
唯一权威源），本工具因此按**前缀匹配**取状态 digest——命中已知前缀即取
**完整前缀本身**（不截断，前缀最长不过 9 个字符，六个示例状态
`📥`/`🆕`/`⏳`/`⏸`/`✅`/`📨` 均在此列），只在前缀之后的自由文本延续段落
才做有界截断（`STATUS_CONTINUATION_WIDTH`）。未命中任何已知前缀时才回落
字符宽度截断，并计入 `malformed_status_rows`（非静默降级，同队列 #308）。
⇒ 状态语义本身**不会**重演 `#439` 那类"关键判断信息被截断算法误伤"的
缺陷——它根本不经过任意宽度的截断。

## 范围边界（刻意不做的事）

只覆盖「现有跟进信清单」主表——`aibot_service.readme_table.
MAIN_TABLE_SECTION`。**不覆盖「补件登记」表**：该表首列语义不同
（"承接编号"不占号）、终态语义也不同（直接从空态到 `✅ 无需回复`/
`✅ 已推送`，不经三态 ⏳/🆕/⏸），并入会把两种不同粒度的状态机混进
同一份 digest。需要补件表数据的调用方应另行处理，不应假设本工具
覆盖了它。

## 用法

    python 0-学习与工具/工具-跟进信README查询.py --digest
    python 0-学习与工具/工具-跟进信README查询.py --digest --digest-width 30
    python 0-学习与工具/工具-跟进信README查询.py --digest --json

`--json` 供 sweep 等下游程序消费（队列 #382⑵：待发信盘点下放 sweep 的
delta 告警）；人读格式与 `--json` 共用同一份行数据，不是两套逻辑
（同 `工具-跟进闸查询.py` 既有的"两条渲染路径共用一份数据"惯例）。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# 队列 #306 式引导：本脚本自身所在的 worktree 本地路径找
# `zhuopin_platform`/`wecom-aibot-service`（同 `工具-跟进闸查询.py`/
# `工具-队列查询.py` 既有引导，仅当目录真实存在时才尝试 import）。
_TOOLS_DIR = Path(__file__).resolve().parent
_REPO_GUESS = _TOOLS_DIR.parent


def _resolve_repo_root() -> Path:
    """同 `工具-队列查询.py::_resolve_repo_root`——按 `git rev-parse` 取
    主工作区根，取不到时退回本文件所在 worktree 的父目录。刻意本地
    独立实现一份而不跨 import 兄弟 CLI 脚本（同目录既定惯例，见
    `工具-队列查询.py` 文首"本文件按需继续本地实现"一段）。"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=_TOOLS_DIR, capture_output=True, text=True, check=True,
        )
        return Path(result.stdout.strip()).parent
    except (subprocess.CalledProcessError, OSError, FileNotFoundError):
        return _REPO_GUESS


REPO_ROOT = _resolve_repo_root()
README_REL = "6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md"

_PLATFORM_PATH = _REPO_GUESS / "5-平台底座" / "zhuopin_platform"
if not _PLATFORM_PATH.is_dir():
    _PLATFORM_PATH = REPO_ROOT / "5-平台底座" / "zhuopin_platform"
if _PLATFORM_PATH.is_dir() and str(_PLATFORM_PATH) not in sys.path:
    sys.path.insert(0, str(_PLATFORM_PATH))
from zhuopin_platform.shared_tools import followup_gate  # noqa: E402

_AIBOT_PATH = _REPO_GUESS / "5-平台底座" / "wecom-aibot-service"
if not _AIBOT_PATH.is_dir():
    _AIBOT_PATH = REPO_ROOT / "5-平台底座" / "wecom-aibot-service"
if _AIBOT_PATH.is_dir() and str(_AIBOT_PATH) not in sys.path:
    sys.path.insert(0, str(_AIBOT_PATH))
from aibot_service.readme_table import (  # noqa: E402
    MAIN_TABLE_SECTION,
    ReadmeTableError,
    column_index,
    iter_rows,
    split_department_and_name,
)

DIGEST_FIELD_SEP = "｜"  # 全角，避免与表格列分隔符半角 `|` 混淆（同队列 #441）

# 状态前缀之后延续文本的有界截断宽度——只为了让读者多看一点上下文
# （如日期/补记来源），不影响状态判定本身（判定只看前缀是否命中）。
STATUS_CONTINUATION_WIDTH = 24
# 未命中任何已知前缀时的回落截断宽度，以及"交期要点"列的截断宽度——
# 两者均无固定词表可比对，只能按字符宽度截断，故沿用队列 digest 的
# 默认宽度惯例（`工具-队列查询.py::DEFAULT_DIGEST_WIDTH`）。
DEFAULT_DIGEST_WIDTH = 40
DIGEST_MALFORMED_STATUS = "[status:?]"

# 自然断句优先于宽度硬切——命中越早越好；"；" 是"交期要点"列常见的
# 多项分隔符（如"① 8/1 前；② ……"），"。"/"——"/"━━━" 沿用队列 digest
# 既有的 `LEADING_SEGMENT_SEPARATORS` 约定（`工具-队列查询.py`）。
LEADING_SEGMENT_SEPARATORS = ("。", "——", "━━━", "；")
LEADING_STRIP_CHARS = "* \t　"

# `classify_status` 的四类返回值中，只有这三个前缀代表"专员还没看到这封
# 信"（`followup_gate.NOT_YET_SENT_STATUS_PREFIXES`）——待发信盘点的三态
# 计数与交叉红标判据都只关心这三个值，直接复用同一份权威常量，不重写
# 一份新的三态词表。
_ALL_KNOWN_STATUS_PREFIXES = (
    followup_gate.REPLY_ARRIVED_STATUS,
    *followup_gate.CLOSED_STATUS_PREFIXES,
    *followup_gate.IN_FLIGHT_STATUS_PREFIXES,
)


def _leading_segment(text: str, width: int, strip_leading: bool = True) -> str:
    """自然分隔符优先、宽度硬切兜底，硬切时补"…"（同队列 digest 惯例，
    `工具-队列查询.py::_digest_status_field` 的省略号写法）。

    `strip_leading=False`（已识别状态前缀之后的延续文本专用）：保留原文
    本来就有的分隔空格/标点，不做剥离——原文形态两种都真实存在
    （`✅ 已推送 2026-...` 前缀后带空格／`✅ 已发（Paul 手动...` 前缀后
    直接跟括号），剥离前导空格会让前者读起来"已推送2026"字词粘连。"""
    stripped = text.lstrip(LEADING_STRIP_CHARS) if strip_leading else text
    cut = len(stripped)
    hit_separator = False
    for sep in LEADING_SEGMENT_SEPARATORS:
        idx = stripped.find(sep)
        if idx != -1 and idx < cut:
            cut = idx
            hit_separator = True
    if cut > width:
        cut = width
        hit_separator = False
    result = stripped[:cut]
    if not hit_separator and cut < len(stripped):
        result += "…"
    return result


def _digest_status_field(status_cell: str, width: int) -> tuple[str, bool]:
    """返回 (展示用状态 digest, 是否落入"未识别已知前缀"兜底)。

    命中已知前缀 ⇒ 完整前缀本身 + 有界延续文本，前缀永不截断；未命中
    ⇒ 按宽度截断兜底，并把第二项标 True（非静默降级，调用方据此计入
    `malformed_status_rows`，同队列 #308 既有原则）。"""
    normalized = followup_gate.normalize_status(status_cell)
    for prefix in _ALL_KNOWN_STATUS_PREFIXES:
        if normalized.startswith(prefix):
            remainder = normalized[len(prefix):]
            continuation = _leading_segment(remainder, STATUS_CONTINUATION_WIDTH, strip_leading=False)
            return prefix + continuation, False
    fallback = _leading_segment(normalized, width)
    return fallback or DIGEST_MALFORMED_STATUS, True


def _not_yet_sent_prefix(status_cell: str) -> str | None:
    normalized = followup_gate.normalize_status(status_cell)
    for prefix in followup_gate.NOT_YET_SENT_STATUS_PREFIXES:
        if normalized.startswith(prefix):
            return prefix
    return None


def build_digest_rows(readme_text: str, width: int = DEFAULT_DIGEST_WIDTH) -> list[dict]:
    """结构性扫描「现有跟进信清单」主表，返回逐行 digest 字典列表——
    人读格式与 `--json` 共用本函数的返回值，不是两套逻辑。`width` 只管
    「交期要点」列与未识别状态前缀兜底的截断宽度，已识别的状态前缀本身
    永不受它截断。"""
    rows = iter_rows(readme_text, section=MAIN_TABLE_SECTION)
    if not rows:
        return []
    header = rows[0].header_cells
    number_col = column_index(header, "编号")
    recipient_col = column_index(header, "收信人")
    delivery_col = column_index(header, "交期要点")
    # 🔴 非静默降级：这三列若找不到，说明表结构已变，静默按空字符串
    # 展示会让下游（sweep 拿「编号」当 key 追踪状态）把"每一行都拿到空
    # 编号"这种明显损坏的输出当成正常数据消费——宁可当场报错。
    missing = [name for name, col in (("编号", number_col), ("收信人", recipient_col),
                                       ("交期要点", delivery_col)) if col is None]
    if missing:
        raise ReadmeTableError(
            f"「{MAIN_TABLE_SECTION}」表头缺少必需列：{'、'.join(missing)}"
            "——表结构可能已变，本工具需要同步更新列名。"
        )

    result = []
    for row in rows:
        cells = row.cells
        status_cell = cells[row.status_col_index]
        status_digest, malformed = _digest_status_field(status_cell, width)
        recipient = cells[recipient_col] if len(cells) > recipient_col else ""
        department, name = split_department_and_name(recipient) if recipient else (None, None)
        delivery = _leading_segment(cells[delivery_col], width) if len(cells) > delivery_col else ""
        result.append({
            "number": cells[number_col] if len(cells) > number_col else "",
            "recipient": recipient,
            "department": department,
            # `name`：从"收信人"列拆出的纯姓名（如"姚祖怡"，不含"采购部 · "
            # 前缀）——队列行提及某人时惯用裸姓名而非完整"部门 · 姓名"格式，
            # 交叉红标一类的下游识别需要这个字段单独可用，不必自己再拆一次
            # （`split_department_and_name` 已是权威实现，见 import）。
            "name": name,
            "status_kind": followup_gate.classify_status(status_cell),
            "not_yet_sent_prefix": _not_yet_sent_prefix(status_cell),
            "status_digest": status_digest,
            "status_malformed": malformed,
            "delivery_digest": delivery,
        })
    return result


def _run_digest(args: argparse.Namespace) -> int:
    if args.digest_width < 1:
        print("✗ --digest-width 须为正整数。")
        return 1

    readme_path = REPO_ROOT / README_REL
    try:
        text = readme_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"✗ 读取 README 失败：{readme_path}（{exc}）")
        return 1

    try:
        rows = build_digest_rows(text, width=args.digest_width)
    except ReadmeTableError as exc:
        print(f"✗ {exc}")
        return 1

    malformed = sum(1 for r in rows if r["status_malformed"])

    if args.json:
        print(json.dumps({
            "readme": README_REL,
            "section": MAIN_TABLE_SECTION,
            "total_rows": len(rows),
            "malformed_status_rows": malformed,
            "rows": rows,
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"【digest · {MAIN_TABLE_SECTION} · 合计 {len(rows)} 行】")
    for r in rows:
        print(f"{r['number']}{DIGEST_FIELD_SEP}{r['recipient']}{DIGEST_FIELD_SEP}"
              f"{r['status_digest']}{DIGEST_FIELD_SEP}{r['delivery_digest']}")

    counts = {p: 0 for p in followup_gate.NOT_YET_SENT_STATUS_PREFIXES}
    for r in rows:
        if r["not_yet_sent_prefix"] in counts:
            counts[r["not_yet_sent_prefix"]] += 1
    summary = "／".join(f"{p}×{n}" for p, n in counts.items())
    print(f"\n{summary}（合计 {len(rows)} 行，未识别已知前缀 {malformed} 行）")
    if malformed:
        print(f"⚠ {malformed} 行状态列未识别到已知前缀（已按宽度截断兜底展示，"
              "可能是本工具词表尚未覆盖的新写法，建议人工核实）。")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="跟进信 README 只读 digest——结构性扫描「现有跟进信清单」"
                     "主表，供待发信盘点/交叉红标等下游程序或人工快速核查用，"
                     "不必读全文（队列 §一 #382⑵）。",
    )
    parser.add_argument(
        "--digest", action="store_true", required=True,
        help="输出主表全部行 digest（编号｜收信人｜发送状态首段｜交期要点首段）；"
             "当前唯一支持的模式，显式要求传入以留出未来扩展空间。",
    )
    parser.add_argument("--json", action="store_true", help="机器消费用；与人读格式共用同一份数据")
    parser.add_argument(
        "--digest-width", type=int, default=DEFAULT_DIGEST_WIDTH,
        help=f"「交期要点」列与未识别状态前缀兜底的截断宽度（默认 {DEFAULT_DIGEST_WIDTH}）；"
             "已识别的状态前缀本身永不受此宽度截断。",
    )
    args = parser.parse_args(argv)
    return _run_digest(args)


if __name__ == "__main__":
    raise SystemExit(main())
