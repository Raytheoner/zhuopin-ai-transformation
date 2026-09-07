"""doc_parser —— docx 解析的**判据正本**（队列 `#481`，design 审 2026-09-07）。

场景侧 import 的唯一正门：
    from zhuopin_platform.shared_tools.doc_parser import read_checkboxes
    reading = read_checkboxes(path)
    if reading.is_failure: ...        # 读不了，绝不当「一条都没勾」
    elif not reading.has_carriers: ...# 读得动，但没有勾选载体
    else: reading.control_checked_count, reading.char_checked_count

🔴 **`CheckboxReading` 不可作真假判断**（`if not reading:` 会抛 TypeError）——
「读取失败」「无载体」「有载体零勾」是三件不同的事，用一个 falsy 判断混同它们
正是队列 `#133` ⑴ 那条事故的形状。

三个子模块：
  - `checkbox` : 勾选读取三态入口（控件 ＋ 段落内勾 ＋ 表格格内勾，一次覆盖）
  - `signals`  : 四类回件形态信号（复选框/高亮/批注/修订），判据自 `#446` 迁入
  - `text`     : 取文（覆盖表格与内容控件，不再丢 26%–71% 正文）

纯 stdlib（`zipfile` ＋ `xml.etree.ElementTree`），不引入 python-docx——
`zhuopin_platform` 的依赖清单因此零新增。
"""
from ._xml import DOCUMENT_PART, DocxReadError
from .checkbox import (
    CHECKBOX_LIKE_CHARS,
    CHECKED_CHARS,
    SOURCE_CHAR,
    SOURCE_CONTROL,
    CheckboxCarrier,
    CheckboxReading,
    ReadingStatus,
    TextViewDiagnostic,
    detect_char_carriers,
    detect_control_carriers,
    read_checkboxes,
)
from .signals import (
    CheckboxItem,
    CommentItem,
    FormSignals,
    HighlightSpan,
    LooseCheckboxChar,
    TrackedChange,
    analyze_docx,
    detect_checkboxes,
    detect_comments,
    detect_highlights,
    detect_loose_checkbox_chars,
    detect_tracked_changes,
    list_part_names,
)
from .text import extract_text, extract_text_lines

__all__ = [
    "DOCUMENT_PART",
    "DocxReadError",
    # —— 勾选读取（三态）
    "read_checkboxes",
    "CheckboxReading",
    "CheckboxCarrier",
    "ReadingStatus",
    "TextViewDiagnostic",
    "SOURCE_CONTROL",
    "SOURCE_CHAR",
    "CHECKBOX_LIKE_CHARS",
    "CHECKED_CHARS",
    "detect_control_carriers",
    "detect_char_carriers",
    # —— 四类形态信号
    "analyze_docx",
    "FormSignals",
    "CheckboxItem",
    "LooseCheckboxChar",
    "HighlightSpan",
    "CommentItem",
    "TrackedChange",
    "list_part_names",
    "detect_checkboxes",
    "detect_loose_checkbox_chars",
    "detect_highlights",
    "detect_comments",
    "detect_tracked_changes",
    # —— 取文
    "extract_text",
    "extract_text_lines",
]
