"""归档后向跨桌任务队列 §一 追加"待领"行（design.md 对应 spec 场景②）。"""
from __future__ import annotations

import re
from pathlib import Path

TABLE_HEADER_MARKER = "## 一、任务看板"
_ROW_ID_RE = re.compile(r"^\|\s*(\d+)\s*\|")
_SECTION_HEADING_RE = re.compile(r"^##\s")


def _section_bounds(lines: list[str], header_idx: int) -> tuple[int, int]:
    """返回 `header_idx` 所在表格的行范围 [start, end)，以下一个 `## ` 标题
    （或文件末尾）为界——**不得**越界扫到别的表格（2026-07-13 真实生产链路
    联调发现的严重 bug：原实现无边界，把行插进了 §四 的四列表格里，还借用
    了 §四 自己的独立编号序列，两处表格都被写坏）。"""
    end = len(lines)
    for i in range(header_idx + 1, len(lines)):
        if _SECTION_HEADING_RE.match(lines[i].strip()):
            end = i
            break
    return header_idx + 1, end


def _next_task_id(lines: list[str], start: int, end: int) -> int:
    ids = [
        int(m.group(1))
        for line in lines[start:end]
        if (m := _ROW_ID_RE.match(line.strip()))
    ]
    return (max(ids) + 1) if ids else 1


def append_pending_task(
    queue_path: Path,
    *,
    description: str,
    owner: str,
    input_pointer: str,
    expected_output: str,
    date_str: str,
    touch_zone: str = "",
) -> str:
    """在 §一 任务看板表格最后一行数据行之后插入一条新"待领"行，返回该行文本。

    编号与插入位置均严格限定在 §一 自己的表格范围内（不越界到后续其他
    `## ` 小节，即便那些小节也用 `| 数字 | ... |` 格式且有自己独立的编号）。
    """
    text = queue_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    header_idx = next(
        (i for i, l in enumerate(lines) if l.strip() == TABLE_HEADER_MARKER), None
    )
    if header_idx is None:
        raise LookupError(f'未找到队列表格标题行 "{TABLE_HEADER_MARKER}"：{queue_path}')

    start, end = _section_bounds(lines, header_idx)

    insert_at = header_idx
    for i in range(start, end):
        if _ROW_ID_RE.match(lines[i].strip()):
            insert_at = i

    task_id = _next_task_id(lines, start, end)
    row = (
        f"| {task_id} | {description} | {owner} | {input_pointer} | "
        f"{expected_output} | 待领 | {touch_zone} | {date_str} |"
    )
    lines.insert(insert_at + 1, row)

    newline = "\n" if text.endswith("\n") else ""
    queue_path.write_text("\n".join(lines) + newline, encoding="utf-8")
    return row
