import pytest

from aibot_service.readme_table import (
    DraftNotPendingReviewError,
    ReadmeTableError,
    assert_draft_pending_review,
    build_target_file_annotation,
    column_index,
    extract_target_filename,
    iter_rows,
    locate_row,
    split_department_and_name,
    write_status,
)

SAMPLE = """\
## 现有跟进信清单

| 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |
|------|--------|---------|---------|---------|
| 2026-07-04 | 质量部 · 陈忱 | 产品类样本 | 尽量 7/15 前 | ✅ 已发 |
| 2026-07-06 | 质量部 · 陈忱 | 8D 预填校准会议程 | 校准会 7 月内 | 🆕 待发 |
| 2026-07-09 | 采购部 · 姚祖怡 | 整合信 | 8月初 | 🆕 待发 |

## 下一节
"""


def test_locate_row_finds_status_column():
    loc = locate_row(SAMPLE, lambda cells: "8D 预填校准会议程" in cells[2])
    assert loc.status_col_index == 4
    assert loc.cells[0] == "2026-07-06"
    assert loc.cells[4] == "🆕 待发"


def test_locate_row_raises_when_no_match():
    with pytest.raises(ReadmeTableError):
        locate_row(SAMPLE, lambda cells: "不存在的事项" in cells[2])


def test_locate_row_disambiguates_multiple_pending_rows():
    loc = locate_row(SAMPLE, lambda cells: "姚祖怡" in cells[1] and "整合信" in cells[2])
    assert loc.cells[0] == "2026-07-09"


def test_write_status_replaces_only_target_row():
    loc = locate_row(SAMPLE, lambda cells: "8D 预填校准会议程" in cells[2])
    new_text = write_status(SAMPLE, loc, "✅ 已推送 2026-07-11 10:00 UTC")

    lines = new_text.splitlines()
    assert "✅ 已推送 2026-07-11 10:00 UTC" in lines[loc.line_index]
    # 其他行不受影响
    assert "✅ 已发" in new_text
    assert "🆕 待发" in new_text  # 姚祖怡那行仍是待发
    reparsed = locate_row(new_text, lambda cells: "姚祖怡" in cells[1])
    assert reparsed.cells[4] == "🆕 待发"


def test_write_status_preserves_trailing_content():
    loc = locate_row(SAMPLE, lambda cells: "整合信" in cells[2])
    new_text = write_status(SAMPLE, loc, "✅ 已推送 X")
    assert "## 下一节" in new_text


def test_iter_rows_returns_all_data_rows_in_order():
    rows = iter_rows(SAMPLE)
    assert [r.cells[0] for r in rows] == ["2026-07-04", "2026-07-06", "2026-07-09"]
    assert all(r.status_col_index == 4 for r in rows)


def test_iter_rows_raises_when_no_status_column():
    with pytest.raises(ReadmeTableError):
        iter_rows("| 日期 | 收信人 |\n|---|---|\n| 2026-07-04 | 陈忱 |\n")


def test_assert_draft_pending_review_accepts_draft_status():
    assert_draft_pending_review("⏳ 待你审")  # 不抛异常即通过


def test_assert_draft_pending_review_rejects_other_values():
    for bad_value in ("🆕 待发", "✅ 已发", "", "⏳待你审"):
        with pytest.raises(DraftNotPendingReviewError):
            assert_draft_pending_review(bad_value)


def test_column_index_finds_containing_header():
    assert column_index(["日期", "收信人", "主要事项"], "收信人") == 1


def test_column_index_returns_none_when_absent():
    assert column_index(["日期", "收信人"], "交期要点") is None


def test_split_department_and_name_extracts_department_and_bare_name():
    assert split_department_and_name("质量部 · 陈忱（可分担朱映桦）") == ("质量部", "陈忱")


def test_split_department_and_name_returns_none_pair_without_separator():
    assert split_department_and_name("未知格式的收信人") == (None, None)


# 队列 #241：dispatch 的行→文件匹配判据只用「收信人＋日期」，同日多封
# 必然歧义。修法⑴——README 行携带目标文件名，dispatch 直接读、不再猜。


def test_extract_target_filename_reads_canonical_annotation():
    topic = "批 2 引擎最后一项口径判例包" + build_target_file_annotation("采购部-姚祖怡-跟进-2026-07-29-x.md")
    assert extract_target_filename(topic) == "采购部-姚祖怡-跟进-2026-07-29-x.md"


def test_extract_target_filename_reads_historical_verbose_annotation():
    # 队列 #150 那行的真实措辞（值周巡检人工消歧时手写，非本函数生成），
    # 用词比 build_target_file_annotation 的固定格式更啰嗦——本函数须兼容，
    # 不要求回改历史行。
    topic = (
        "请批\"上月未齐套项目的物料\"这 1 项　→ **目标文件（2026-08-04 值周"
        "巡检消歧）**：`采购部-姚祖怡-跟进-2026-07-29-批2上月未齐套跨月占用"
        "判例批改.md`（同日另两封…不是本行…）"
    )
    assert extract_target_filename(topic) == (
        "采购部-姚祖怡-跟进-2026-07-29-批2上月未齐套跨月占用判例批改.md"
    )


def test_extract_target_filename_returns_none_when_absent():
    assert extract_target_filename("普通主题，未标注目标文件") is None


def test_build_target_file_annotation_round_trips():
    annotation = build_target_file_annotation("部门-姓名-跟进-2026-08-05-事项.md")
    assert extract_target_filename(annotation) == "部门-姓名-跟进-2026-08-05-事项.md"
