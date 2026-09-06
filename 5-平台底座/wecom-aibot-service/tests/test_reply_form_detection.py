"""队列 #446：回件形态识别 —— 单测用合成 docx 片段，不嵌入任何真实回件。

真实回件全部落在本机 gitignore 的 `7-外部文档/`（外部专员往来，不入库，
worktree 之间也不互带），故这里的固件（fixture）全部是本文件手写的最小
合法 OOXML 片段，覆盖四类信号各自的关键分支——不是"看起来像"，是按
`python-docx`/Word 实际写出的 XML 结构手工还原（`w14:checkbox` 结构与
`0-学习与工具/md转Word工具/md2word.py::add_checkbox()` 生成的产物逐字同构）。

对**真实**回件的离线回归（8～9 封已归档样本，逐封列"机器读出的形态 vs
人当时最终结论"）不适合放在这份入库单测里——见 `queue-446-offline-
regression-2026-09-05.md`（本次派单件产出，供总线/下一位领取方复核）。
"""
from __future__ import annotations

import io
import zipfile

import pytest

from aibot_service import reply_form_detection as rfd

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
W14 = 'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"'


def _wrap_document(body_xml: str) -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:document {W} {W14}><w:body>{body_xml}</w:body></w:document>"
    )


def _checkbox_sdt(checked: bool, display_char: str = None) -> str:
    val = "1" if checked else "0"
    char = display_char or ("☒" if checked else "☐")
    return (
        "<w:sdt><w:sdtPr>"
        '<w:id w:val="100000001"/>'
        f'<w14:checkbox><w14:checked w14:val="{val}"/>'
        '<w14:checkedState w14:val="2612" w14:font="MS Gothic"/>'
        '<w14:uncheckedState w14:val="2610" w14:font="MS Gothic"/>'
        "</w14:checkbox>"
        "</w:sdtPr><w:sdtEndPr/>"
        f"<w:sdtContent><w:r><w:t>{char}</w:t></w:r></w:sdtContent>"
        "</w:sdt>"
    )


def _build_docx(document_body_xml: str, extra_parts: dict = None) -> bytes:
    """拼一份最小合法 docx——本模块只读 `word/document.xml` 与
    `word/comments*.xml`，其余部件（`[Content_Types].xml`／`_rels`）真实
    Word 文档必有，但**本模块的 zipfile 直读逻辑不依赖它们**，测试固件
    因此可以只放被测部件，验证的正是"不经 python-docx 高层封装也能读"。
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", _wrap_document(document_body_xml))
        for name, content in (extra_parts or {}).items():
            z.writestr(name, content)
    return buf.getvalue()


def _write_docx(tmp_path, name: str, document_body_xml: str, extra_parts: dict = None):
    path = tmp_path / name
    path.write_bytes(_build_docx(document_body_xml, extra_parts))
    return path


# ---------------------------------------------------------------- ① 部件清单

def test_list_part_names_direct_zip_read(tmp_path):
    """直读部件清单——不经 python-docx；`word/comments.xml` 在不在，只看
    `namelist()`，不看某个对象有没有 `.comments` 属性。"""
    path = _write_docx(tmp_path, "a.docx", "<w:p/>", extra_parts={"word/comments.xml": "<w:comments/>"})
    names = rfd.list_part_names(path)
    assert "word/document.xml" in names
    assert "word/comments.xml" in names


# ---------------------------------------------------------------- ② 复选框

def test_checkbox_checked_and_unchecked_counted_and_which_ones(tmp_path):
    """数勾了几个哪几个——不是只数"有没有勾"，是逐格给出 checked 布尔值。"""
    body = (
        "<w:p>" + _checkbox_sdt(True) + "</w:p>"
        + "<w:p>" + _checkbox_sdt(False) + "</w:p>"
        + "<w:p>" + _checkbox_sdt(False) + "</w:p>"
    )
    path = _write_docx(tmp_path, "checked.docx", body)
    sig = rfd.analyze_docx(path)
    assert sig.checkbox_checked_count == 1
    assert sig.checkbox_unchecked_count == 2
    assert [c.checked for c in sig.checkboxes] == [True, False, False]
    assert sig.summary_line() == "w14:checkbox ☒1/☐2"


def test_checkbox_row_context_pulls_sibling_table_cells(tmp_path):
    """队列 #446 point ⑶ 的根因所在排版：控件独占一个单元格，
    label／题干在同一行的**别的**单元格——本模块须把它们拼出来，不能只
    报告一个孤零零的 ☒/☐（那正是当年"读成全空"的成因）。"""
    row = (
        "<w:tr>"
        "<w:tc><w:p><w:r><w:t>料号 A：缺口三个月合计 406,953</w:t></w:r></w:p></w:tc>"
        f"<w:tc><w:p>{_checkbox_sdt(True)}</w:p></w:tc>"
        f"<w:tc><w:p>{_checkbox_sdt(False)}</w:p></w:tc>"
        "</w:tr>"
    )
    body = f"<w:tbl>{row}</w:tbl>"
    path = _write_docx(tmp_path, "row.docx", body)
    sig = rfd.analyze_docx(path)
    checked = [c for c in sig.checkboxes if c.checked][0]
    assert "料号 A" in checked.row_context
    assert "406,953" in checked.row_context
    # 自己所在那一格（"☒"）按元素身份排除，不会在 row_context 里出现；
    # 隔壁那个未勾格子的 "☐" 属于同一行**别的**单元格，应正常出现。
    assert "☐" in checked.row_context


def test_checkbox_context_is_own_paragraph_only_when_not_in_table(tmp_path):
    """不在表格内的独立复选框——`row_context` 应为空串，不得凭空捏造。"""
    body = "<w:p><w:r><w:t>是笔误：</w:t></w:r>" + _checkbox_sdt(True) + "</w:p>"
    path = _write_docx(tmp_path, "no_table.docx", body)
    sig = rfd.analyze_docx(path)
    assert sig.checkboxes[0].row_context == ""
    assert "是笔误" in sig.checkboxes[0].context


def test_no_prechecked_boxes_regression_guard(tmp_path):
    """质量部#9 黄金基准（README 已用 XML 取证核对）：14 个复选框、
    ☒6/☐8、**无预勾选**。本用例只钉"检测器认得出 checked=False 就是
    unchecked，不会把默认态误判成任何一种预设"——用真实文件的比例复现，
    不嵌入真实文件内容本身。"""
    boxes = "".join(_checkbox_sdt(i < 6) for i in range(14))
    body = f"<w:p>{boxes}</w:p>"
    path = _write_docx(tmp_path, "q9.docx", body)
    sig = rfd.analyze_docx(path)
    assert sig.checkbox_checked_count == 6
    assert sig.checkbox_unchecked_count == 8
    assert sig.summary_line() == "w14:checkbox ☒6/☐8"


# ---------------------------------------------------------------- ② 裸勾选字符（控件外）

def test_loose_checkbox_char_outside_any_control_is_flagged_separately(tmp_path):
    """人直接在正文里敲一个 ☒，没有走内容控件——不得并入 `checkbox_total`
    （没有 checked/unchecked 这个布尔状态可读），但也不能对它视而不见
    （那正是"以为勾了、机器看不到"的另一种真实形态）。"""
    body = (
        "<w:p><w:r><w:t>你上封勾的是「☒ 认可」，我们收到了。</w:t></w:r></w:p>"
    )
    path = _write_docx(tmp_path, "loose.docx", body)
    sig = rfd.analyze_docx(path)
    assert sig.checkboxes == []
    assert len(sig.loose_checkbox_chars) == 1
    assert sig.loose_checkbox_chars[0].char == "☒"
    assert "认可" in sig.loose_checkbox_chars[0].context


def test_checkbox_control_display_char_not_double_counted_as_loose(tmp_path):
    """结构化控件自身用来显示 ☒/☐ 的那个 `w:t`，不该被裸字符探测器
    又报一次——否则每个正常控件都会被误报"控件外还有一个裸字符"。"""
    body = "<w:p>" + _checkbox_sdt(True) + "</w:p>"
    path = _write_docx(tmp_path, "not_double.docx", body)
    sig = rfd.analyze_docx(path)
    assert len(sig.checkboxes) == 1
    assert sig.loose_checkbox_chars == []


# ---------------------------------------------------------------- ② 高亮

def test_highlight_adjacent_same_color_runs_merge_into_one_span(tmp_path):
    """陈述 财务部#14/#15 的真实形态：整段用高亮作答，若不合并相邻同色
    run，会把一句连续的话拆成几十个碎片，"高亮段全文"就无法直接读。"""
    body = (
        "<w:p>"
        '<w:r><w:rPr><w:highlight w:val="yellow"/></w:rPr><w:t>唐燕萍回复：</w:t></w:r>'
        '<w:r><w:rPr><w:highlight w:val="yellow"/></w:rPr><w:t>选 (b) 更合适。</w:t></w:r>'
        "<w:r><w:t>（此句无高亮）</w:t></w:r>"
        "</w:p>"
    )
    path = _write_docx(tmp_path, "hl.docx", body)
    sig = rfd.analyze_docx(path)
    assert len(sig.highlights) == 1
    assert sig.highlights[0].text == "唐燕萍回复：选 (b) 更合适。"
    assert sig.highlights[0].color == "yellow"


def test_highlight_color_change_breaks_the_span(tmp_path):
    """颜色变了就该是两段，不能因为紧挨着就强行合并成一段。"""
    body = (
        "<w:p>"
        '<w:r><w:rPr><w:highlight w:val="yellow"/></w:rPr><w:t>第一段黄色。</w:t></w:r>'
        '<w:r><w:rPr><w:highlight w:val="cyan"/></w:rPr><w:t>第二段青色。</w:t></w:r>'
        "</w:p>"
    )
    path = _write_docx(tmp_path, "hl2.docx", body)
    sig = rfd.analyze_docx(path)
    assert [h.color for h in sig.highlights] == ["yellow", "cyan"]
    assert sig.highlights[0].text == "第一段黄色。"
    assert sig.highlights[1].text == "第二段青色。"


def test_highlight_run_count_total_matches_unmerged_readme_convention(tmp_path):
    """README 记的历史口径（"财务部#14 55~78 处高亮"）按**未合并** run 数
    数；本模块合并后的 `highlights` 段数是另一个数字，两者都要能对得上——
    这条钉住 `highlight_run_count_total` 不是段数、是原始 run 数之和。"""
    body = (
        "<w:p>"
        '<w:r><w:rPr><w:highlight w:val="yellow"/></w:rPr><w:t>一</w:t></w:r>'
        '<w:r><w:rPr><w:highlight w:val="yellow"/></w:rPr><w:t>二</w:t></w:r>'
        '<w:r><w:rPr><w:highlight w:val="yellow"/></w:rPr><w:t>三</w:t></w:r>'
        "</w:p>"
    )
    path = _write_docx(tmp_path, "runs.docx", body)
    sig = rfd.analyze_docx(path)
    assert len(sig.highlights) == 1          # 合并后只有一段
    assert sig.highlights[0].run_count == 3  # 但原始是 3 个 run
    assert sig.highlight_run_count_total == 3


def test_no_highlight_at_all_reports_zero_not_error(tmp_path):
    path = _write_docx(tmp_path, "plain.docx", "<w:p><w:r><w:t>纯文字回复，无任何标记。</w:t></w:r></w:p>")
    sig = rfd.analyze_docx(path)
    assert sig.highlights == []
    assert not sig.has_any_signal


# ---------------------------------------------------------------- ② 批注

def test_comment_text_and_anchor_extracted(tmp_path):
    body = (
        "<w:p>"
        '<w:commentRangeStart w:id="0"/>'
        "<w:r><w:t>这一段是被批注圈住的原文</w:t></w:r>"
        '<w:commentRangeEnd w:id="0"/>'
        '<w:r><w:commentReference w:id="0"/></w:r>'
        "</w:p>"
    )
    comments_xml = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:comments {W}>'
        '<w:comment w:id="0" w:author="陈忱" w:date="2026-08-25T00:00:00Z">'
        "<w:p><w:r><w:t>这里的判据需要再确认一下</w:t></w:r></w:p>"
        "</w:comment></w:comments>"
    )
    path = _write_docx(tmp_path, "cm.docx", body, extra_parts={"word/comments.xml": comments_xml})
    sig = rfd.analyze_docx(path)
    assert len(sig.comments) == 1
    c = sig.comments[0]
    assert c.author == "陈忱"
    assert c.text == "这里的判据需要再确认一下"
    assert c.anchor_text == "这一段是被批注圈住的原文"
    assert sig.has_comments_part is True


def test_no_comments_part_returns_empty_not_error(tmp_path):
    path = _write_docx(tmp_path, "no_cm.docx", "<w:p><w:r><w:t>无批注</w:t></w:r></w:p>")
    sig = rfd.analyze_docx(path)
    assert sig.comments == []
    assert sig.has_comments_part is False


# ---------------------------------------------------------------- ② 修订标记

def test_tracked_insertions_and_deletions_extracted_with_correct_text_field(tmp_path):
    """插入文字在 `w:t`，删除文字在 `w:delText`——两者取字段路径不同，
    这条用例专门钉住"没把两套字段搞反"。"""
    body = (
        "<w:p>"
        '<w:ins w:id="1" w:author="姚祖怡" w:date="2026-08-28T00:00:00Z">'
        "<w:r><w:t>新增的这句话</w:t></w:r></w:ins>"
        '<w:del w:id="2" w:author="姚祖怡" w:date="2026-08-28T00:00:00Z">'
        "<w:r><w:delText>被删掉的这句话</w:delText></w:r></w:del>"
        "</w:p>"
    )
    path = _write_docx(tmp_path, "trk.docx", body)
    sig = rfd.analyze_docx(path)
    ins = [t for t in sig.tracked_changes if t.kind == "ins"]
    dele = [t for t in sig.tracked_changes if t.kind == "del"]
    assert ins[0].text == "新增的这句话"
    assert ins[0].author == "姚祖怡"
    assert dele[0].text == "被删掉的这句话"


# ---------------------------------------------------------------- ③ 结构化产出 / summary_line

def test_summary_line_never_silently_reports_no_answer():
    """🔴 队列 #446 的核心红线：四类信号全为零时，`summary_line()` 必须
    如实说"机器没读到信号"，绝不能措辞成"对方未作答"一类会被当作结论
    直接回灌权威载体的句子——这正是本模块要根治的错误结论本身。"""
    empty = rfd.FormSignals(docx_path="x.docx")
    line = empty.summary_line()
    # 允许提及"未作答"字样本身（作为「不得判定为…」的反面示例转述），
    # 但绝不能是一句可以被直接当结论回灌的裸断言——必须带着"不得/需人工"
    # 这类否定-转人工的框架词一并出现。
    assert "均未命中" in line
    assert "人工" in line
    assert not line.strip().startswith(("对方未作答", "没有回复", "空", "全空"))


def test_summary_line_combines_multiple_signal_families(tmp_path):
    """真实回件常常混用多种形态（如 采购部#19 复选框＋高亮同现）——
    summary_line 须把命中的都列出来，不能只报第一个命中的类别。"""
    body = (
        "<w:p>" + _checkbox_sdt(True) + "</w:p>"
        "<w:p>"
        '<w:r><w:rPr><w:highlight w:val="yellow"/></w:rPr><w:t>同一份回件里还有高亮。</w:t></w:r>'
        "</w:p>"
    )
    path = _write_docx(tmp_path, "mix.docx", body)
    sig = rfd.analyze_docx(path)
    line = sig.summary_line()
    assert "checkbox" in line
    assert "高亮段" in line


def test_analyze_docx_raises_on_missing_document_part(tmp_path):
    """`word/document.xml` 缺失＝非合法 Word 文档，须显式抛错，不得静默
    回落成"零信号"——那会和"读到了、只是恰好没有信号"混为一谈。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("readme.txt", "not a docx")
    path = tmp_path / "broken.docx"
    path.write_bytes(buf.getvalue())
    with pytest.raises(ValueError):
        rfd.analyze_docx(path)
