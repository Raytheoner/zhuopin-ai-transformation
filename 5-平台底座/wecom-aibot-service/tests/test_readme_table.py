import pytest

from aibot_service.readme_table import (
    DRAFT_PENDING_REVIEW_STATUS,
    PAUSED_STATUS,
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


# 队列 #294 修法⑴：两态语义扩为三态，新增 `⏸ 暂缓`（批准后又主动暂缓发送）。


def test_paused_status_is_distinct_marker():
    from aibot_service.gates import FINALIZED_STATUS_MARKER

    assert PAUSED_STATUS == "⏸ 暂缓"
    assert PAUSED_STATUS != DRAFT_PENDING_REVIEW_STATUS
    assert PAUSED_STATUS != FINALIZED_STATUS_MARKER


def test_write_status_can_move_row_to_paused_and_back():
    loc = locate_row(SAMPLE, lambda cells: "8D 预填校准会议程" in cells[2])
    paused_text = write_status(SAMPLE, loc, PAUSED_STATUS)
    reparsed = locate_row(paused_text, lambda cells: "8D 预填校准会议程" in cells[2])
    assert reparsed.cells[4] == PAUSED_STATUS

    resumed_text = write_status(paused_text, reparsed, "🆕 待发")
    reparsed_again = locate_row(resumed_text, lambda cells: "8D 预填校准会议程" in cells[2])
    assert reparsed_again.cells[4] == "🆕 待发"


# ---------------------------------------------------------------------------
# 闭环形态标注（队列 #353；openspec `followup-closure-form-survives-backfill`）
# ---------------------------------------------------------------------------

from aibot_service.readme_table import (  # noqa: E402
    ClosureFormAnnotationError,
    build_closure_form_annotation,
    build_closure_form_snapshot,
    extract_closure_form,
)


def test_闭环形态标注写完能被解析回来():
    ann = build_closure_form_annotation("✅ 无需回复", "正文三要素表明写「不用回」")
    parsed = extract_closure_form(f"某封信的主要事项{ann}")
    assert parsed.form.form == "✅ 无需回复"
    assert parsed.form.basis == "正文三要素表明写「不用回」"


def test_越界取值在写入侧就被拒绝():
    # 写入侧与解析侧同一条约束——判据都从 followup_gate 取，不各写一份。
    with pytest.raises(ClosureFormAnnotationError):
        build_closure_form_annotation("✅ 大概不用回", "随便写的")


def test_空依据在写入侧就被拒绝():
    with pytest.raises(ClosureFormAnnotationError):
        build_closure_form_annotation("✅ 无需回复", "   ")


def test_依据含右括号被拒绝以免解析在错误位置截断():
    with pytest.raises(ClosureFormAnnotationError):
        build_closure_form_annotation("✅ 无需回复", "见（附件）说明")


def test_追加闭环形态标注后列数不变且能正常定位():
    """🔴 队列 #241 已确立的手法：只在既有单元格内追加文本、不新增列 ⇒
    编辑锁的列数/身份校验不受影响。本条是那句话的可执行版本。"""
    before = iter_rows(SAMPLE)
    row = next(r for r in before if "8D 预填校准会议程" in r.cells[2])
    widths_before = [len(r.cells) for r in before]

    lines = SAMPLE.splitlines()
    cells = row.cells.copy()
    cells[2] += build_closure_form_annotation("✅ 无需回复", "正文写明不用回")
    lines[row.line_index] = "| " + " | ".join(cells) + " |"
    after_text = "\n".join(lines) + "\n"

    after = iter_rows(after_text)
    assert [len(r.cells) for r in after] == widths_before
    assert after[1].status_col_index == row.status_col_index
    assert extract_closure_form(after[1].cells[2]).form.form == "✅ 无需回复"


def test_目标文件标注与闭环形态标注可以并存互不干扰():
    topic = (
        "**C01–C10 已落地**"
        + build_target_file_annotation("质量部-陈忱-跟进-2026-08-18-x.md")
        + build_closure_form_annotation("✅ 无需回复", "正文写明不用回")
    )
    assert extract_target_filename(topic) == "质量部-陈忱-跟进-2026-08-18-x.md"
    assert extract_closure_form(topic).form.form == "✅ 无需回复"


def test_快照段不自带分段符由调用方拼接():
    # 分段符只在拼接那一处出现一次——不新造第二种分段范式。
    snap = build_closure_form_snapshot("✅ 无需回复", "正文写明不用回")
    assert not snap.startswith("　")
    assert snap.startswith("闭环形态（发出时快照）")


def test_未标注的主要事项列返回无标注且不报违规():
    parsed = extract_closure_form("**C01–C10 已落地并部署，先认一个错**")
    assert parsed.form is None
    assert parsed.violation is None
