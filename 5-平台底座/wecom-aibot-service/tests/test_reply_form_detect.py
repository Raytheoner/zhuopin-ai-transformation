"""`aibot_service.reply_form_detect` 单测。

每条用例都对应队列 `#446` 里点名的一次真实误判，防止同族缺陷复发：
- 采购部#18：9 个复选框实际勾了 3 个，曾被读成全空
- 采购部#19：勾选写在段落里（不在表格内），只扫表格的读法整个漏掉
- 财务部#14/#15、质量部同族：0 批注 0 修订 0 勾选、答复全靠正文高亮段
- 巡逻章程 §二 硬约束 2：✏️ 列非空 ≠ 改判，必须核对 ✅/❌ 列的实际字符
"""
from __future__ import annotations

from aibot_service.reply_form_detect import detect_reply_form

from docx_fixtures import (
    build_docx,
    checkbox_cell_xml,
    checkbox_xml,
    comment_anchor_paragraph_xml,
    comment_entry_xml,
    del_xml,
    highlighted_run_xml,
    ins_xml,
    paragraph_xml,
    plain_run_xml,
    table_row_xml,
    table_xml,
    text_cell_xml,
)


def _wrap_run_paragraph(*runs: str) -> str:
    return "<w:p>" + "".join(runs) + "</w:p>"


# ---------------------------------------------------------------------------
# 复选框：段落内（不在表格里）
# ---------------------------------------------------------------------------


def test_checkbox_in_paragraph_not_in_table_is_detected(tmp_path):
    """回归采购部#19：勾选写在段落文字里，只扫表格的读法会把它整个漏掉。"""
    body = paragraph_xml("第 5 件事：") + checkbox_xml(1, checked=True)
    docx_path = build_docx(tmp_path / "reply.docx", body)

    report = detect_reply_form(docx_path)

    assert len(report.checkboxes) == 1
    assert report.checkboxes[0].checked is True
    assert report.checkboxes[0].in_table is False
    assert report.checked_count == 1


def test_checkboxes_in_table_and_paragraph_are_both_counted(tmp_path):
    """表格内外的勾选必须合并读出，不能只认其中一种来源。"""
    table = table_xml(
        [
            table_row_xml([checkbox_cell_xml(1, checked=False), checkbox_cell_xml(2, checked=False)]),
        ]
    )
    body = table + paragraph_xml("段落内追加两项：") + checkbox_xml(3, True) + checkbox_xml(4, True)
    docx_path = build_docx(tmp_path / "reply.docx", body)

    report = detect_reply_form(docx_path)

    assert len(report.checkboxes) == 4
    assert report.checked_count == 2
    in_table_flags = [c.in_table for c in report.checkboxes]
    assert in_table_flags == [True, True, False, False]


def test_nine_checkboxes_three_checked_not_all_empty(tmp_path):
    """回归采购部#18 真实事故：9 格实际勾了 3 个，此前被读成全空。"""
    checked_pattern = [False, True, False, True, False, False, False, False, True]
    rows = []
    idx = 1
    for r in range(3):
        cells = []
        for c in range(3):
            cells.append(checkbox_cell_xml(idx, checked=checked_pattern[idx - 1]))
            idx += 1
        rows.append(table_row_xml(cells))
    body = table_xml(rows)
    docx_path = build_docx(tmp_path / "reply.docx", body)

    report = detect_reply_form(docx_path)

    assert len(report.checkboxes) == 9
    assert report.checked_count == 3, "9 格里应读出 3 个勾选，绝不能读成全空"
    assert report.unchecked_count == 6


# ---------------------------------------------------------------------------
# 高亮叙事型回件（0 批注 0 修订 0 勾选，靠正文高亮作答）
# ---------------------------------------------------------------------------


def test_highlight_only_reply_classified_as_highlight_form(tmp_path):
    """回归财务部#14/#15、质量部同族：无勾选/批注/修订时不得判定为"她什么都没答"。"""
    body = _wrap_run_paragraph(
        plain_run_xml("唐燕萍回复："),
        highlighted_run_xml("李姣龙会继续每天照原节奏放"),
    )
    docx_path = build_docx(tmp_path / "reply.docx", body)

    report = detect_reply_form(docx_path)

    assert report.checkboxes == []
    assert report.comments == []
    assert report.revisions == []
    assert len(report.highlights) == 1
    assert report.highlights[0].text == "李姣龙会继续每天照原节奏放"
    assert report.forms_present == ["highlight"]


def test_contiguous_highlighted_runs_are_merged_into_one_span(tmp_path):
    body = _wrap_run_paragraph(
        highlighted_run_xml("第一段"),
        highlighted_run_xml("第二段"),
        plain_run_xml("（未高亮的补充说明）"),
        highlighted_run_xml("第三段"),
    )
    docx_path = build_docx(tmp_path / "reply.docx", body)

    report = detect_reply_form(docx_path)

    assert [h.text for h in report.highlights] == ["第一段第二段", "第三段"]


def test_raw_highlight_element_count_includes_paragraph_mark_highlights(tmp_path):
    """回归财务部#14/#15 真实数字对不上事故：历史"N 处高亮"是 `<w:highlight>`
    元素的原始计数（含段落标记 `w:pPr/w:rPr/w:highlight`），不是合并后的
    可读段落数——两个数字都要留，不能只留合并后的那个更小的数。"""
    body = (
        "<w:p>"
        '<w:pPr><w:rPr><w:highlight w:val="yellow"/></w:rPr></w:pPr>'
        + highlighted_run_xml("被高亮的正文")
        + "</w:p>"
    )
    docx_path = build_docx(tmp_path / "reply.docx", body)

    report = detect_reply_form(docx_path)

    # 合并后的可读高亮段仍然只有 1 段（run 级）；
    assert len(report.highlights) == 1
    # 但原始 <w:highlight> 元素计数须把段落标记那一处也算进去 ⇒ 2。
    assert report.raw_highlight_element_count == 2


def test_zero_highlights_when_no_highlight_property_present(tmp_path):
    body = paragraph_xml("普通正文，没有任何高亮")
    docx_path = build_docx(tmp_path / "reply.docx", body)

    report = detect_reply_form(docx_path)

    assert report.highlights == []
    assert report.forms_present == ["plain_narrative"]


# ---------------------------------------------------------------------------
# 批注（word/comments.xml + commentRangeStart/End 锚定原文）
# ---------------------------------------------------------------------------


def test_comment_extraction_pairs_comment_text_with_anchor_text(tmp_path):
    body = comment_anchor_paragraph_xml(comment_id=0, anchored_text="三个月窗口口径")
    comments_xml = comment_entry_xml(
        comment_id=0, author="唐燕萍", date="2026-08-22T00:00:00Z", text="这条我同意方案 (c)"
    )
    docx_path = build_docx(tmp_path / "reply.docx", body, comments_xml=comments_xml)

    report = detect_reply_form(docx_path)

    assert report.comment_part_names == ["word/comments.xml"]
    assert len(report.comments) == 1
    c = report.comments[0]
    assert c.author == "唐燕萍"
    assert c.anchor_text == "三个月窗口口径"
    assert c.comment_text == "这条我同意方案 (c)"
    assert report.forms_present == ["comment"]


def test_no_comments_part_means_empty_comments_list(tmp_path):
    body = paragraph_xml("没有任何批注的正文")
    docx_path = build_docx(tmp_path / "reply.docx", body)

    report = detect_reply_form(docx_path)

    assert report.comments == []
    assert report.comment_part_names == []


# ---------------------------------------------------------------------------
# 修订（w:ins / w:del）
# ---------------------------------------------------------------------------


def test_insert_and_delete_revisions_are_extracted_separately(tmp_path):
    body = _wrap_run_paragraph(
        plain_run_xml("原判定："),
    ) + f"<w:p>{ins_xml(1, '陈忱', '2026-08-25T00:00:00Z', '新增判例2改判')}</w:p>" + (
        f"<w:p>{del_xml(2, '陈忱', '2026-08-25T00:00:00Z', '删除的旧判据')}</w:p>"
    )
    docx_path = build_docx(tmp_path / "reply.docx", body)

    report = detect_reply_form(docx_path)

    assert report.insert_count == 1
    assert report.delete_count == 1
    ins_items = [r for r in report.revisions if r.kind == "ins"]
    del_items = [r for r in report.revisions if r.kind == "del"]
    assert ins_items[0].text == "新增判例2改判"
    assert ins_items[0].author == "陈忱"
    assert del_items[0].text == "删除的旧判据"
    assert report.forms_present == ["revision"]


# ---------------------------------------------------------------------------
# 硬约束 1：通读全部段落（含表格单元格），不能只解析表格
# ---------------------------------------------------------------------------


def test_full_paragraphs_covers_narrative_and_table_cells_in_document_order(tmp_path):
    body = (
        paragraph_xml("段落A：开篇说明")
        + table_xml([table_row_xml([text_cell_xml("表格B：单元格内容")])])
        + paragraph_xml("段落C：推翻整个功能的统一答复")
    )
    docx_path = build_docx(tmp_path / "reply.docx", body)

    report = detect_reply_form(docx_path)

    assert report.full_paragraphs == [
        "段落A：开篇说明",
        "表格B：单元格内容",
        "段落C：推翻整个功能的统一答复",
    ]


# ---------------------------------------------------------------------------
# 硬约束 2：✏️ 列非空 ≠ 改判，必须核对 ✅/❌ 列的实际字符
# ---------------------------------------------------------------------------


def test_tables_expose_raw_cell_characters_not_column_semantics(tmp_path):
    """✏️ 列被打了字符不代表改判——必须去看 ✅/❌ 列实际写的是哪个符号。"""
    header = table_row_xml(
        [text_cell_xml("判例"), text_cell_xml("✅"), text_cell_xml("❌"), text_cell_xml("✏️")]
    )
    # 真实事故形态：✏️ 列非空（写了字），但 ✅ 列才是那个真正的符号；
    # ❌ 列留空。调用方必须逐格读字符，不能因为"✏️ 列有内容"就误判为改判。
    data_row = table_row_xml(
        [
            text_cell_xml("判例1"),
            text_cell_xml("✅"),
            text_cell_xml(""),
            text_cell_xml("笔误，按新口径"),
        ]
    )
    body = table_xml([header, data_row])
    docx_path = build_docx(tmp_path / "reply.docx", body)

    report = detect_reply_form(docx_path)

    assert len(report.tables) == 1
    rows = report.tables[0].rows
    assert rows[0] == ["判例", "✅", "❌", "✏️"]
    assert rows[1] == ["判例1", "✅", "", "笔误，按新口径"]


# ---------------------------------------------------------------------------
# 纯文本回件（.md/.txt）—— 不套用 docx 结构化判据，整份原文即"形态"
# ---------------------------------------------------------------------------


def test_plain_markdown_reply_is_read_as_whole_text(tmp_path):
    md_path = tmp_path / "reply.md"
    md_path.write_text("这是一封纯文本反馈，没有 docx 结构，须整份通读。", encoding="utf-8")

    report = detect_reply_form(md_path)

    assert report.doc_type == "plain_text"
    assert report.forms_present == ["plain_text_reply"]
    assert report.plain_text == "这是一封纯文本反馈，没有 docx 结构，须整份通读。"
    assert report.checkboxes == [] and report.highlights == [] and report.comments == []


def test_unsupported_extension_raises_value_error(tmp_path):
    other = tmp_path / "reply.xlsx"
    other.write_bytes(b"not really an xlsx")

    try:
        detect_reply_form(other)
    except ValueError as exc:
        assert "不认得" in str(exc)
    else:
        raise AssertionError("应对不支持的扩展名抛 ValueError")


# ---------------------------------------------------------------------------
# summary() 冒烟
# ---------------------------------------------------------------------------


def test_summary_reports_all_counts(tmp_path):
    body = paragraph_xml("正文") + checkbox_xml(1, True) + checkbox_xml(2, False)
    docx_path = build_docx(tmp_path / "reply.docx", body)

    report = detect_reply_form(docx_path)
    summary = report.summary()

    assert "2 勾选" in summary
    assert "1 已勾" in summary
    assert "1 未勾" in summary
