"""queue_table.py 单测（队列 #306+#307）。"""
from __future__ import annotations

from zhuopin_platform.shared_tools.queue_table import (
    SECTION_COLUMN_COUNTS,
    column_count_ok,
    escape_bare_pipe,
    has_bare_pipe,
)


def test_section_column_counts_matches_known_sections():
    assert SECTION_COLUMN_COUNTS == {"一": 8, "二": 4, "四": 4}


def test_has_bare_pipe_detects_pipe():
    assert has_bare_pipe("a|b") is True


def test_has_bare_pipe_no_pipe():
    assert has_bare_pipe("正常文本") is False


def test_has_bare_pipe_backtick_wrapped_still_detected():
    # 反引号不豁免——本项目现有表格解析对反引号无感知，见函数文档。
    assert has_bare_pipe("`a|b`") is True


def test_escape_bare_pipe_replaces_with_fullwidth_slash():
    assert escape_bare_pipe("a|b|c") == "a／b／c"


def test_escape_bare_pipe_no_pipe_unchanged():
    assert escape_bare_pipe("正常文本") == "正常文本"


def test_column_count_ok_section_one_exact():
    cells = ["1", "任务", "领取方", "输入", "产出", "状态", "触碰区", "登记"]
    assert column_count_ok("一", cells) is True


def test_column_count_ok_section_one_short_by_bare_pipe():
    # 裸竖线致列偏移的情形——实际列数少于标准列数。
    cells = ["1", "任务", "领取方", "输入", "产出", "状态"]
    assert column_count_ok("一", cells) is False


def test_column_count_ok_section_two():
    cells = ["B-0101", "文件清单", "说明", "待处理"]
    assert column_count_ok("二", cells) is True


def test_column_count_ok_section_four():
    cells = ["1", "事项", "等谁", "截止"]
    assert column_count_ok("四", cells) is True


def test_column_count_ok_unknown_section_returns_true():
    assert column_count_ok("五", ["a", "b"]) is True
