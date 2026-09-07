"""回件形态识别 —— **薄壳委托**，判据正本已迁至平台底座（队列 `#481`）。

## 本文件为什么只剩一层壳
判据原先整份住在这里。但这里是**企微机器人服务包**，`4-数字员工/` 各场景
`import` 不到它——场景要读 docx 勾选，除了自己再写一份别无选择。队列 `#481`
实测：仓库里因此长出了三份各有盲区的 docx 读取实现（`md2word.read_checkboxes`
对纯裸 ☑ 的回件返回「勾 0」、`qda_prefill._read_docx` 丢 26%–71% 正文、本模块
判据最全却场景 import 不到）。**落点选错，做完之后第四份还会长出来**——这才是
重复实现并存的结构性成因。

design 决策点① (a)（Shao Peishen 2026-09-07 审过）：判据迁到
`zhuopin_platform.shared_tools.doc_parser`，即场景侧 import 的唯一正门。
本服务的 `pyproject.toml` 首条依赖本来就是 `zhuopin_platform[aibot]`，
**零依赖成本**。

## 对外契约不变
`analyze_docx()`／`list_part_names()`／`FormSignals` 及其 `summary_line()`
的字段与措辞逐字不变，`scripts/check_reply_form_signals.py` 的命令行输出
因此不因这次重构改变（迁移前后逐字 diff 已实测，见变更包 `tasks.md` 3.2）。
四类信号的探测范围仍是 `word/document.xml`，与 `#446` 一致。

## 新增能力在哪里取
需要「读取失败 / 无勾选载体 / 有 N 个载体勾 M 个」三态区分的调用方，请直接用
`doc_parser.read_checkboxes()`（或读 `FormSignals.checkbox_reading`）——它的
返回类型**禁用 falsy 判断**，从类型上堵死把"读不了"读成"一条都没勾"这条路。
"""
from __future__ import annotations

from zhuopin_platform.shared_tools.doc_parser import (  # noqa: F401
    CHECKBOX_LIKE_CHARS,
    CHECKED_CHARS,
    DOCUMENT_PART,
    CheckboxItem,
    CheckboxReading,
    CommentItem,
    DocxReadError,
    FormSignals,
    HighlightSpan,
    LooseCheckboxChar,
    ReadingStatus,
    TrackedChange,
    analyze_docx,
    detect_checkboxes,
    detect_comments,
    detect_highlights,
    detect_loose_checkbox_chars,
    detect_tracked_changes,
    list_part_names,
    read_checkboxes,
)
from zhuopin_platform.shared_tools.doc_parser._xml import (  # noqa: F401
    COMMENTS_PART_PREFIX,
    W14_NS,
    W_NS,
)

__all__ = [
    "analyze_docx",
    "list_part_names",
    "read_checkboxes",
    "FormSignals",
    "CheckboxItem",
    "LooseCheckboxChar",
    "HighlightSpan",
    "CommentItem",
    "TrackedChange",
    "CheckboxReading",
    "ReadingStatus",
    "DocxReadError",
    "detect_checkboxes",
    "detect_loose_checkbox_chars",
    "detect_highlights",
    "detect_comments",
    "detect_tracked_changes",
    "CHECKBOX_LIKE_CHARS",
    "CHECKED_CHARS",
    "COMMENTS_PART_PREFIX",
    "DOCUMENT_PART",
    "W_NS",
    "W14_NS",
]
