"""queue_table.py 单测（队列 #306+#307+#314）。"""
from __future__ import annotations

from zhuopin_platform.shared_tools.queue_table import (
    SECTION_COLUMN_COUNTS,
    column_count_ok,
    escape_bare_pipe,
    has_bare_pipe,
    parse_section_rows,
    split_row_cells,
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


# ---------------------------------------------------------------------------
# split_row_cells（队列 #314，openspec 变更包 queue-table-backtick-aware-split）
# ---------------------------------------------------------------------------


def test_split_row_cells_pipe_inside_backtick_not_a_delimiter():
    cells = split_row_cells("| 1 | 说明 `a|b` | 状态 |")
    assert cells == ["1", "说明 `a|b`", "状态"]


def test_split_row_cells_multiple_pipes_inside_one_backtick_span():
    cells = split_row_cells("| 1 | `a|b|c` | 状态 |")
    assert cells == ["1", "`a|b|c`", "状态"]


def test_split_row_cells_two_separate_backtick_spans_each_with_pipe():
    cells = split_row_cells("| 1 | `a|b` 与 `c|d` | 状态 |")
    assert cells == ["1", "`a|b` 与 `c|d`", "状态"]


def test_split_row_cells_unclosed_backtick_pipe_still_splits():
    # 落单反引号不构成跨度（design.md 决策点 1：与 Markdown 渲染器"不生成
    # code span"的处理一致，是期望行为，不用状态机额外处理）。
    cells = split_row_cells("| 1 | `未闭合|仍会被切开 | 状态 |")
    assert cells == ["1", "`未闭合", "仍会被切开", "状态"]


def test_split_row_cells_entire_row_wrapped_in_single_backtick_span():
    cells = split_row_cells("| 1 | `整段|都在反引号里|不切` |")
    assert cells == ["1", "`整段|都在反引号里|不切`"]


def test_split_row_cells_no_leading_pipe_returns_none():
    assert split_row_cells("普通段落文字") is None


def test_split_row_cells_not_ending_in_pipe_still_returns_cells():
    """队列 #314①/#313 真实事故：结尾被外部工具截断的行，仍应切出单元格
    交调用方发现列数异常，不得在切分这一步静默丢弃（同 `_table_data_rows`
    docstring 的既有教训，见 `工具-共享文档编辑锁.py`）。"""
    cells = split_row_cells("| 313 | 任务 | ...到此为止没有收尾")
    assert cells is not None
    assert cells[0] == "313"
    assert len(cells) < SECTION_COLUMN_COUNTS["一"]


def test_split_row_cells_real_313_incident_shape():
    """真实历史事故复现——#313 行在 `git show 298c152` 起的状态列正文里
    出现 `git grep` 的正则交替符（一个反引号包裹、内含竖线的代码片段），
    未受保护时会把该单元格撑成两段。反引号感知切列后，该片段应仍是同一
    个单元格。"""
    row = (
        "| 313 | 任务 | CC | 指针 | 产出 | "
        "系统性核查：`git grep` 全库 `from zhuopin_platform|import zhuopin_platform` "
        "| 触碰区 | 2026-08-09 |"
    )
    cells = split_row_cells(row)
    assert len(cells) == 8
    assert "from zhuopin_platform|import zhuopin_platform" in cells[5]


def test_split_row_cells_double_backtick_escaping_single_backtick():
    """apply 阶段真实数据踩坑复现（队列 #314，非纸面推演）：对当前生产
    队列文件跑任务 3.2 的新旧切列 diff 时，真实命中 §二 批次
    `B-0809_312可Open池立行与接力收工` 的"文件清单"列从 4 列被错误合并
    成 3 列——该列正文用 CommonMark 标准写法（双反引号游程）包裹"内容
    本身含单个反引号"的文本，如 ` `` \\`f1c9e29 `` `（描述"反引号被吃掉"
    这件事本身）。最初实现用单反引号正则 `` `[^`]*` `` 配对，会把双反引号
    游程里的每个反引号都当独立配对边界，导致游程配对全部错位、后续竖线
    保护范围漂移，错误吞掉真正的列分隔符。改用按 CommonMark 反引号游程
    长度配对的扫描算法（`_mask_backtick_spans`）后修复。"""
    row = (
        "| B-TEST | 描述：`` `f1c9e29 `` 被吃成换页符 | "
        "`docs(test): 示例提交信息` | ✅ 已完成 |"
    )
    cells = split_row_cells(row)
    assert len(cells) == 4
    assert cells[0] == "B-TEST"
    assert "`` `f1c9e29 ``" in cells[1]
    assert cells[2] == "`docs(test): 示例提交信息`"
    assert cells[3] == "✅ 已完成"


# ---------------------------------------------------------------------------
# parse_section_rows
# ---------------------------------------------------------------------------

_SECTION_ONE_SAMPLE = """
| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 1 | 正常行 | CC | 指针 | 产出 | 状态 | 触碰区 | 2026-08-01 |
| 2 | 反引号外裸竖线致 9 列 a|b | CC | 指针 | 产出 | 状态 | 触碰区 | 2026-08-01 |
"""


def test_parse_section_rows_classifies_mixed_valid_and_invalid_rows():
    rows = parse_section_rows(_SECTION_ONE_SAMPLE, "一")
    assert len(rows) == 2
    _, cells1, ok1 = rows[0]
    assert cells1[0] == "1"
    assert ok1 is True
    _, cells2, ok2 = rows[1]
    assert cells2[0] == "2"
    assert ok2 is False  # 反引号外的裸竖线撑出第 9 列，真列偏移


def test_parse_section_rows_backtick_pipe_no_longer_misjudged_as_offset():
    section = (
        "| # | 任务 | 领取方 | 输入 | 产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| 313 | 任务 | CC | 指针 | 产出 | "
        "`from zhuopin_platform|import zhuopin_platform` | 触碰区 | 2026-08-09 |\n"
    )
    rows = parse_section_rows(section, "一")
    assert len(rows) == 1
    _, cells, ok = rows[0]
    assert len(cells) == 8
    assert ok is True


def test_parse_section_rows_skips_header_and_separator():
    rows = parse_section_rows(_SECTION_ONE_SAMPLE, "一")
    ids = [cells[0] for _, cells, _ in rows]
    assert "#" not in ids
    assert not any(set(i) <= {"-"} for i in ids)
