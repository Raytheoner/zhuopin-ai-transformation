"""跟进信 README 的 markdown 表格读写（仅供 delivery.py 场景①使用）。

只处理"现有跟进信清单"这一张表——按管道符 `|` 切分/拼接，不支持单元格内含
转义 `|`（该 README 目前全是中文自然语言内容，无代码块/管道符，够用）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


class ReadmeTableError(LookupError):
    pass


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


def locate_row(text: str, match: Callable[[list[str]], bool]) -> RowLocation:
    """定位表格中"发送状态"列所在、且满足 `match(cells)` 的第一行。

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

    for i in range(header_idx + 2, len(lines)):
        line = lines[i]
        if not line.strip().startswith("|"):
            break
        cells = _split_row(line)
        if len(cells) <= status_col_index:
            continue
        if match(cells):
            return RowLocation(
                line_index=i,
                cells=cells,
                status_col_index=status_col_index,
                header_cells=header_cells,
            )

    raise ReadmeTableError("未找到匹配的跟进信行")


def write_status(text: str, loc: RowLocation, new_status: str) -> str:
    """把 `loc` 定位到的行的状态列原子替换为 `new_status`，返回新文本。"""
    lines = text.splitlines()
    cells = loc.cells.copy()
    cells[loc.status_col_index] = new_status
    lines[loc.line_index] = _join_row(cells)
    newline = "\n" if text.endswith("\n") else ""
    return "\n".join(lines) + newline
