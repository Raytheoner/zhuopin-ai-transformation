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

## 整格原文只读模式 `--row`（队列 §一 #501⑴，2026-09-08）

`--digest` 解决的是「扫全表不通读真身」，它按设计**必然**只给每格的首段；
`--digest-width` 也救不了状态列——已识别前缀之后的延续文本走的是
`STATUS_CONTINUATION_WIDTH` 这个**独立常量**，`--digest-width` 对它无效
（`#501` 立行前实测传 3000 无变化，见该行成因段）。

于是出现了一个**读侧取证链的断口**：README 有读侧禁通读钩子
（`hooks-pretooluse-queue-read-guard.ps1`，立法理由见 openspec
`followup-readme-phase2` D4）挡住 `Read`/`Grep`/`cat`，唯一写入口
`工具-跟进信README登记.py set-status` 又是**整格替换**——想改写一格长状态，
改写者手里没有任何合法途径看到那一格的全文。`#501` 的原始形态就是这个断口
的一次真实命中：`质量部#7` 的状态格里嵌着一句在机器眼里仍有效的
`串行豁免：` 口令，上一棒看护者**当场停手未改**，判据是「看不见全文就改
＝用重建文本覆盖一段从未看过的叙述」。

`--row <编号>` 补的正是这一格：**单行、逐字、零截断**地输出该行各格原文，
并对每格附字符数／UTF-8 字节数／sha256（供改写前后逐字对照留档）。

🔴 **它刻意不是「放宽 `--digest-width`」，也不是「开一个通读后门」**：
一次只出**一行**，且**必须**给出确切编号——读侧禁通读的立法目的（一次
`Read` 就把 178 KB 主表灌进上下文）因此不被绕过，被放开的只有「改写者看得见
自己要改的那一格」这一件事。

🔴 **行匹配判据与 `set-status` 的关系**：`set-status` 的匹配是「编号格字面
相等 **或** `parse_letter_number` 解析值相等，取第一个命中」。本模式**不复刻**
那条判据（复刻即多一份会漂移的实现，正是 `#482` 在修的毛病），而是走一条
**更严**的路：先做字面相等匹配，无命中才回落解析值相等，且**任一趟命中多行
即报错**（`set-status` 会静默取第一行）。字面相等是两侧必然一致的子集 ⇒
输出里显式回印「编号格字面值」，改写者把该字面值原样喂给 `set-status
--number`，走的就是两侧逐字相同的那条分支。

⚠️ **「逐字」的确切边界**：markdown 表格按 `|` 切分，`readme_table._split_row`
会 `strip()` 掉每格与管道符之间的空白——本模式输出的是**该 strip 之后**的格
内容。这不是有损：写侧 `_join_row` 回写时同样按 `| ` + ` | ` 拼装，故
「读出来的格 → 原样喂回 set-status」是逐字往返的。格**内部**的任何空白、
换行转义、装饰星号一律不动（不走 `normalize_status`）。

## 用法

    python 0-学习与工具/工具-跟进信README查询.py --digest
    python 0-学习与工具/工具-跟进信README查询.py --digest --digest-width 30
    python 0-学习与工具/工具-跟进信README查询.py --digest --json
    python 0-学习与工具/工具-跟进信README查询.py --row 质量部#7
    python 0-学习与工具/工具-跟进信README查询.py --row 质量部#7 --field 发送状态
    python 0-学习与工具/工具-跟进信README查询.py --row 质量部#7 --json

`--json` 供 sweep 等下游程序消费（队列 #382⑵：待发信盘点下放 sweep 的
delta 告警）；人读格式与 `--json` 共用同一份行数据，不是两套逻辑
（同 `工具-跟进闸查询.py` 既有的"两条渲染路径共用一份数据"惯例）。
"""
from __future__ import annotations

import argparse
import hashlib
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


# ---------------------------------------------------------------------------
# 整格原文只读模式（`--row`，队列 §一 #501⑴）
# ---------------------------------------------------------------------------

# `--field` 的「全部列」取值。刻意用英文字面量而非"全部"——它是命令行 token，
# 与列名（一律中文）不可能撞车，同队列 `工具-队列查询.py --field all` 既有约定。
RAW_FIELD_ALL = "all"

# sha256 全长 64 位十六进制，人读输出里取前 16 位即可区分改写前后（碰撞概率
# 与本用途完全不相干）；`--json` 里给全长，供机器逐字对照。
RAW_HUMAN_HASH_PREFIX = 16


class RawRowNotFound(LookupError):
    """`--row` 给的编号在主表里定位不到，或定位到多行（歧义）。

    与 `ReadmeTableError`（表结构坏了）分开成两类：前者是"你给的编号不对"，
    后者是"这份文件不再是那张表了"，两者的处置完全不同——混成一类会让
    调用方把"编号打错"当成"README 被人改坏了"。
    """


def _cell_fingerprint(value: str) -> dict:
    """一格原文的可核指纹。字符数与字节数分列——CJK 一字三字节，只给其中
    一个数字会让「改写前后长度对得上吗」这个核对动作在两种口径间打滑。"""
    raw = value.encode("utf-8")
    return {
        "chars": len(value),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def build_raw_row(readme_text: str, number: str, section: str = MAIN_TABLE_SECTION) -> dict:
    """按编号取**单行**各格原文，零截断。

    匹配两趟（判据见模块 docstring「行匹配判据与 `set-status` 的关系」）：
    ⑴ 编号格**字面相等**；⑵ 无命中才回落 `parse_letter_number` **解析值相等**。
    任一趟命中多行 ⇒ `raise RawRowNotFound`，**MUST NOT 静默取第一行**——
    改写者据本函数的输出去改一格，取错行的代价是把改写写到别人那行上。
    """
    rows = iter_rows(readme_text, section=section)
    if not rows:
        raise RawRowNotFound(f"「{section}」表内无数据行，无法定位编号「{number}」")
    header = rows[0].header_cells
    number_col = column_index(header, "编号")
    if number_col is None:
        raise ReadmeTableError(
            f"「{section}」表头缺少「编号」列——表结构可能已变，本工具需要同步更新列名。"
        )

    def _cell_of(row, col):
        return row.cells[col] if len(row.cells) > col else ""

    literal = [r for r in rows if _cell_of(r, number_col) == number]
    matched, how = (literal, "字面相等") if literal else ([], "")
    if not matched:
        target_parsed = followup_gate.parse_letter_number(number)
        if target_parsed is not None:
            matched = [
                r for r in rows
                if followup_gate.parse_letter_number(_cell_of(r, number_col)) == target_parsed
            ]
            how = "编号解析值相等"

    if not matched:
        raise RawRowNotFound(
            f"编号「{number}」在「{section}」主表中定位不到。"
            "（本模式只读主表活行；已归档的行请用 `--file` 指向对应 "
            "`README-归档-YYYYMM.md` 再查。）"
        )
    if len(matched) > 1:
        literals = "、".join(f"`{_cell_of(r, number_col)}`" for r in matched)
        raise RawRowNotFound(
            f"编号「{number}」按「{how}」命中 {len(matched)} 行（{literals}）——歧义，"
            "本模式拒绝猜哪一行。请改传上列某个**编号格字面值**（字面相等只会命中一行）。"
        )

    row = matched[0]
    cells = []
    for i, col_name in enumerate(header):
        value = _cell_of(row, i)
        cells.append({
            "column": col_name,
            "index": i,
            "is_status_column": i == row.status_col_index,
            "value": value,
            **_cell_fingerprint(value),
        })
    return {
        "section": section,
        "queried_number": number,
        # 🔴 回印字面值：改写者把**这一个**值喂给 `set-status --number`，
        # 走的是两侧逐字相同的字面相等分支（模块 docstring 已述）。
        "number_cell_literal": _cell_of(row, number_col),
        "matched_by": how,
        # markdown 文件里的 0-based 行号（与 `RowLocation.line_index` 同一口径）；
        # +1 即编辑器行号。给出它是为了让"我读的和我改的是同一行"可被第三方复核。
        "line_index": row.line_index,
        "status_column_index": row.status_col_index,
        "cells": cells,
    }


def _select_raw_cells(raw_row: dict, field: str) -> list[dict]:
    """`--field` 选列：`all` 全出；否则按**列名含该子串**选（同 `column_index`
    既有的包含匹配口径——表头实际写作「发送状态（2026-07-06）」，要求全等
    会逼调用方去抄那个括注）。选不中即抛，不静默返回空。"""
    if field == RAW_FIELD_ALL:
        return raw_row["cells"]
    hits = [c for c in raw_row["cells"] if field in c["column"]]
    if not hits:
        names = "、".join(c["column"] for c in raw_row["cells"])
        raise RawRowNotFound(f"列名不含「{field}」的列——本表列为：{names}")
    return hits


def _run_raw_row(args: argparse.Namespace) -> int:
    readme_rel = args.file or README_REL
    readme_path = REPO_ROOT / readme_rel
    try:
        text = readme_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"✗ 读取 README 失败：{readme_path}（{exc}）")
        return 1

    try:
        raw_row = build_raw_row(text, args.row)
        cells = _select_raw_cells(raw_row, args.field)
    except (ReadmeTableError, RawRowNotFound) as exc:
        print(f"✗ {exc}")
        return 1

    if args.json:
        payload = dict(raw_row)
        payload["readme"] = readme_rel
        payload["field"] = args.field
        payload["cells"] = cells
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"【整格原文 · {raw_row['section']} · {raw_row['number_cell_literal']}】")
    print(f"文件：{readme_rel} ｜ markdown 行号 {raw_row['line_index'] + 1} "
          f"｜ 匹配方式：{raw_row['matched_by']} ｜ 选列：{args.field}")
    print("🔴 逐字原文、零截断；改写请用 "
          f"`工具-跟进信README登记.py set-status --number {raw_row['number_cell_literal']}`"
          "（整格替换）。")
    for c in cells:
        marker = "（发送状态列）" if c["is_status_column"] else ""
        print(f"\n──── [{c['index']}] {c['column']}{marker} ｜ {c['chars']} 字 ／ "
              f"{c['bytes']} 字节 ／ sha256:{c['sha256'][:RAW_HUMAN_HASH_PREFIX]} ────")
        print(c["value"])
    return 0


def _run_digest(args: argparse.Namespace) -> int:
    if args.digest_width < 1:
        print("✗ --digest-width 须为正整数。")
        return 1

    readme_rel = args.file or README_REL
    readme_path = REPO_ROOT / readme_rel
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
            "readme": readme_rel,
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
        description="跟进信 README 只读查询：`--digest` 结构性扫描「现有跟进信清单」"
                     "主表，供待发信盘点/交叉红标等下游程序或人工快速核查用，"
                     "不必读全文（队列 §一 #382⑵）；`--row <编号>` 单行整格原文、"
                     "逐字零截断，供改写长状态格前取证（队列 §一 #501⑴）。",
    )
    parser.add_argument(
        "--digest", action="store_true",
        help="输出主表全部行 digest（编号｜收信人｜发送状态首段｜交期要点首段）。"
             "与 `--row` 二选一，必传其一。",
    )
    parser.add_argument(
        "--row", default=None, metavar="编号",
        help="整格原文只读模式（#501⑴）：按编号取**单行**各格原文，逐字、零截断，"
             "每格附字符数／字节数／sha256。改写长状态格前的取证入口——"
             "读侧禁通读钩子挡住直读、`set-status` 又是整格替换时，这是唯一"
             "能看见全文的合法途径。与 `--digest` 二选一。",
    )
    parser.add_argument("--json", action="store_true", help="机器消费用；与人读格式共用同一份数据")
    parser.add_argument(
        "--field", default=RAW_FIELD_ALL, metavar="列名",
        help=f"仅 `--row` 模式生效：选列（默认 `{RAW_FIELD_ALL}` ＝全部列）。"
             "按列名**含该子串**匹配（表头实际写作「发送状态（2026-07-06）」，"
             "传 `发送状态` 即可）；选不中即报错，不静默返回空。",
    )
    parser.add_argument(
        "--digest-width", type=int, default=DEFAULT_DIGEST_WIDTH,
        help=f"「交期要点」列与未识别状态前缀兜底的截断宽度（默认 {DEFAULT_DIGEST_WIDTH}）；"
             "已识别的状态前缀本身永不受此宽度截断。",
    )
    parser.add_argument(
        "--file", default=None,
        help=f"目标文件相对仓库根路径（默认 {README_REL}）；`followup-readme-phase2` "
             "归档能力落地后，可指向某份 `README-归档-YYYYMM.md` 归档件人工核对历史"
             "（同队列 `工具-队列查询.py --file` 既有用法）。归档件章节标题/表头与"
             "主表一致，按同一套解析逻辑读取，行为逐字相同。",
    )
    args = parser.parse_args(argv)
    # 🔴 两模式互斥且必传其一——不设默认模式：`--row` 是「看一格」，`--digest`
    # 是「扫全表」，猜错方向的代价一边是白跑、另一边是把 45 行灌进上下文。
    if args.digest and args.row is not None:
        print("✗ `--digest` 与 `--row` 互斥，一次只能选一个模式。")
        return 1
    if not args.digest and args.row is None:
        print("✗ 须指定模式：`--digest`（扫全表 digest）或 `--row <编号>`（单行整格原文）。")
        return 1
    if args.row is not None:
        return _run_raw_row(args)
    return _run_digest(args)


if __name__ == "__main__":
    raise SystemExit(main())
