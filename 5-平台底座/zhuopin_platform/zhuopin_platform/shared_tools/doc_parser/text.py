"""docx 取文 —— 覆盖表格单元格与内容控件，不再只取段落的直接 `w:r` 子节点。

## 这个件在治什么（队列 `#481` 1.5 实测）
`4-数字员工/质量部/QD-A-8D不良分析/qda_prefill/doc_reader.py::_read_docx()`
用 `doc.paragraphs` 取文——那是 python-docx 的**高层文本视图**，看不见表格
单元格、也看不见内容控件里的 run。实测：

| 回件 | `doc.paragraphs` 取到 | XML 全量 | 丢失 |
|---|---|---|---|
| `采购部` 08-26 | 3872 字，☒0 ☑0 ☐0 | 5216 字，☒3 ☐6 | 1344 字 ＝ **26%** |
| `质量部#11` | 543 字，☑3 | 1897 字，☑22 | 1354 字 ＝ **71%** |

⇒ 不是"少了几个符号"，是**丢掉四分之一到七成的正文**。

## 取文顺序
按 XML 文档序遍历 `w:body` 下的块级元素：段落逐段一行；表格逐行 `" | "` 拼格。
段落文字用 XML 视图（`p.iter(w:t)`，递归），故 `w:sdt/w:sdtContent` 内的 run、
超链接与修订包裹里的 run 都在其中。

## 边界
本模块只取文字，不做任何分段/语义解析（那是各场景自己的事）；不缓存内容；
被涉 OEM 技术数据的场景调用时，OEM 隔离责任在调用方。
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator, List, Union
from xml.etree import ElementTree as ET

from . import _xml
from ._xml import DOCUMENT_PART, DocxReadError, w


def _table_row_lines(tbl: ET.Element) -> Iterator[str]:
    for tr in tbl.findall(w("tr")):
        cells = []
        for tc in tr.findall(w("tc")):
            cells.append("".join(t.text or "" for t in tc.iter(w("t"))).strip())
        line = " | ".join(c for c in cells if c)
        if line:
            yield line


def _block_lines(container: ET.Element) -> Iterator[str]:
    """按文档序产出块级元素的文字行（段落 / 表格，表格可嵌套）。"""
    for child in container:
        if child.tag == w("p"):
            text = _xml.full_paragraph_text(child).strip()
            if text:
                yield text
        elif child.tag == w("tbl"):
            yield from _table_row_lines(child)
        elif child.tag in (w("sdt"), w("sdtContent")):
            # 块级内容控件：其 `w:sdtContent` 里装的仍是段落/表格，递归下去
            yield from _block_lines(child)


def extract_text_lines(
    docx_path: Union[str, Path], include_extra_parts: bool = False
) -> List[str]:
    """按文档序返回非空文字行。`include_extra_parts` 为真时追加页眉/页脚/脚注。"""
    _, roots = _xml.read_parts(docx_path, include_extra_parts=include_extra_parts)
    lines: List[str] = []
    for part, root in roots:
        body = root.find(w("body")) if part == DOCUMENT_PART else root
        container = body if body is not None else root
        lines.extend(_block_lines(container))
    return lines


def extract_text(
    docx_path: Union[str, Path], include_extra_parts: bool = False
) -> str:
    """全文（行间以 `\\n` 相连）。读不了即抛 `DocxReadError`，**绝不返回空串**
    ——「读不了」与「这份文档确实没字」不是同一件事。"""
    return "\n".join(extract_text_lines(docx_path, include_extra_parts=include_extra_parts))


__all__ = ["extract_text", "extract_text_lines", "DocxReadError"]
