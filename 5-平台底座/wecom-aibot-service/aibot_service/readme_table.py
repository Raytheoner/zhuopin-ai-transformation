"""跟进信 README 的 markdown 表格读写（供 delivery.py 场景①、
approval.py 场景③、dispatch.py 场景④共用）。

只处理"现有跟进信清单"这一张表——按管道符 `|` 切分/拼接，不支持单元格内含
转义 `|`（该 README 目前全是中文自然语言内容，无代码块/管道符，够用）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional


class ReadmeTableError(LookupError):
    pass


# design.md D1：两态语义草稿标记——起草唯一合法产物，转终态（gates.py 的
# FINALIZED_STATUS_MARKER = "🆕 待发"）仅能经 approve_followup_letter.py。
DRAFT_PENDING_REVIEW_STATUS = "⏳ 待你审"


class DraftNotPendingReviewError(RuntimeError):
    """批准脚本拒绝：目标行「发送状态」列不是约定的待审草稿标记。"""


def assert_draft_pending_review(status_value: str) -> None:
    if status_value.strip() != DRAFT_PENDING_REVIEW_STATUS:
        raise DraftNotPendingReviewError(
            f'批准被拒绝：当前状态 "{status_value.strip()}" 非约定的待审草稿标记 '
            f'"{DRAFT_PENDING_REVIEW_STATUS}"'
        )


def _split_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _join_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


@dataclass
class RowLocation:
    line_index: int
    cells: list[str]
    status_col_index: int
    header_cells: list[str]


def iter_rows(text: str) -> list[RowLocation]:
    """返回表格全部数据行（供批量扫描场景使用，如 dispatch.py 场景④逐行
    判定是否可发送）——与 `locate_row` 共用同一套表头/分隔行判定逻辑，
    区别只在"取第一个匹配"还是"取全部"。

    表头行：任意以 `|` 开头且含"发送状态"字样的行。表头下一行是
    `|---|---|...` 分隔行，再往下直到第一条非 `|` 开头的行为止都是数据行。
    """
    lines = text.splitlines()
    header_idx = None
    header_cells: list[str] = []
    status_col_index = -1

    for i, line in enumerate(lines):
        if line.strip().startswith("|") and "发送状态" in line:
            header_cells = _split_row(line)
            for j, cell in enumerate(header_cells):
                if cell.startswith("发送状态"):
                    status_col_index = j
                    break
            header_idx = i
            break

    if header_idx is None or status_col_index < 0:
        raise ReadmeTableError('未找到含"发送状态"列的表格')

    rows: list[RowLocation] = []
    for i in range(header_idx + 2, len(lines)):
        line = lines[i]
        if not line.strip().startswith("|"):
            break
        cells = _split_row(line)
        if len(cells) <= status_col_index:
            continue
        rows.append(
            RowLocation(
                line_index=i,
                cells=cells,
                status_col_index=status_col_index,
                header_cells=header_cells,
            )
        )
    return rows


def locate_row(text: str, match: Callable[[list[str]], bool]) -> RowLocation:
    """定位表格中"发送状态"列所在、且满足 `match(cells)` 的第一行。"""
    for row in iter_rows(text):
        if match(row.cells):
            return row
    raise ReadmeTableError("未找到匹配的跟进信行")


def write_status(text: str, loc: RowLocation, new_status: str) -> str:
    """把 `loc` 定位到的行的状态列原子替换为 `new_status`，返回新文本。"""
    lines = text.splitlines()
    cells = loc.cells.copy()
    cells[loc.status_col_index] = new_status
    lines[loc.line_index] = _join_row(cells)
    newline = "\n" if text.endswith("\n") else ""
    return "\n".join(lines) + newline


def column_index(header_cells: list[str], contains: str) -> Optional[int]:
    """按表头单元格是否包含子串定位列序号（供 dispatch.py/draft_gap_detection.py
    共用，避免各自重复实现同一个查找）。"""
    for i, cell in enumerate(header_cells):
        if contains in cell:
            return i
    return None


def split_department_and_name(recipient_cell: str) -> tuple[Optional[str], Optional[str]]:
    """"质量部 · 陈忱（可分担朱映桦）" -> ("质量部", "陈忱")。取不到则返回
    (None, None)，调用方据此判失败，不臆造。原属 dispatch.py，队列 #245
    需要同一套解析（README 已起草行 vs 发布收口场景按收信人交叉比对），
    迁到本共享模块，dispatch.py 改为调用本函数。"""
    if "·" not in recipient_cell:
        return None, None
    department, _, rest = recipient_cell.partition("·")
    department = department.strip()
    name = rest.strip()
    for cut in ("（", "("):
        idx = name.find(cut)
        if idx != -1:
            name = name[:idx]
    name = name.strip()
    if not department or not name:
        return None, None
    return department, name


# 队列 #241 修法⑴：README 行携带目标文件名，dispatch 直接读、不再仅凭
# 「收信人＋日期」猜测（同日多封必然歧义，2026-08-04 首次真实触发命中）。
# 起草时统一由 `build_target_file_annotation` 写入固定格式；历史行（如
# 队列 #150，值周巡检人工消歧写入）措辞略有出入但同样含"目标文件"关键字
# + 反引号围栏的 .md 文件名，本正则对两者兼容，不需要回改历史行内容。
_TARGET_FILE_RE = re.compile(r"目标文件[^`]*`([^`]+\.md)`")


def extract_target_filename(topic_cell: str) -> Optional[str]:
    """从"主要事项"列文本中提取队列 #241 标注的目标文件名，未标注返回 None
    （调用方据此回落旧的「部门＋姓名＋日期」glob 判据，向后兼容未标注的
    历史行）。"""
    m = _TARGET_FILE_RE.search(topic_cell)
    return m.group(1) if m else None


def build_target_file_annotation(filename: str) -> str:
    """起草新行时追加到"主要事项"列末尾的固定格式片段（队列 #241 修法⑴）。
    只在既有单元格内追加文本，不新增列——不改变表格结构，`_validate_
    followup_readme_release`/`_validate_release_structure`（编辑锁工具的
    列数/身份校验）因此不受影响，无需同步修改。"""
    return f" → 目标文件：`{filename}`"
