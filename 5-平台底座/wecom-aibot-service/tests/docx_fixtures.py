"""为 `test_reply_form_detect.py` 手搭最小合法 `.docx`。

刻意不经 `python-docx`——`python-docx` 的高层对象模型没有批注/高亮的构造
接口，而本测试恰恰要精确控制这些底层 XML 结构（同被测模块 `reply_form_detect.py`
一样直读裸 OOXML），手写骨架比迁就一个覆盖不了目标结构的库更直接可靠。
"""
from __future__ import annotations

import zipfile
from pathlib import Path

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  {comments_override}
</Types>"""

_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

_DOCUMENT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {comments_rel}
</Relationships>"""

_DOCUMENT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml">
  <w:body>
{body}
  </w:body>
</w:document>"""

_COMMENTS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
{comments}
</w:comments>"""


def build_docx(path: str | Path, body_xml: str, comments_xml: str | None = None) -> Path:
    """写一份最小合法 `.docx`；`body_xml` 是 `<w:body>` 内部片段。

    `comments_xml` 非空时同步登记 `[Content_Types].xml` 的 Override 与
    `word/_rels/document.xml.rels` 的关系条目——三者任一缺失，Word/`python-docx`
    会视为损坏文件，但本模块自己的 `zipfile` 直读不依赖这些关系解析
    （批注按 `w:id` 而非 `r:id` 关联），刻意把它们凑齐只为让测试夹具本身是
    一份"正常"的 docx，不是为了被测代码需要它们。
    """
    path = Path(path)
    has_comments = comments_xml is not None
    content_types = _CONTENT_TYPES.format(
        comments_override=(
            '<Override PartName="/word/comments.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"/>'
            if has_comments
            else ""
        )
    )
    document_rels = _DOCUMENT_RELS.format(
        comments_rel=(
            '<Relationship Id="rId100" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" '
            'Target="comments.xml"/>'
            if has_comments
            else ""
        )
    )
    document_xml = _DOCUMENT_XML.format(body=body_xml)

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", _ROOT_RELS)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/_rels/document.xml.rels", document_rels)
        if has_comments:
            zf.writestr("word/comments.xml", _COMMENTS_XML.format(comments=comments_xml))
    return path


def checkbox_xml(id_val: int, checked: bool) -> str:
    """一枚独立成段的真 `w14:checkbox` 内容控件（同 `md2word.py::add_checkbox` 同构）。"""
    checked_val = "1" if checked else "0"
    char = "☒" if checked else "☐"  # ☒ / ☐
    return f"""
      <w:p>
        <w:sdt>
          <w:sdtPr>
            <w:id w:val="{id_val}"/>
            <w14:checkbox>
              <w14:checked w14:val="{checked_val}"/>
              <w14:checkedState w14:val="2612" w14:font="MS Gothic"/>
              <w14:uncheckedState w14:val="2610" w14:font="MS Gothic"/>
            </w14:checkbox>
          </w:sdtPr>
          <w:sdtEndPr/>
          <w:sdtContent>
            <w:r><w:t>{char}</w:t></w:r>
          </w:sdtContent>
        </w:sdt>
      </w:p>"""


def checkbox_cell_xml(id_val: int, checked: bool) -> str:
    """同一枚勾选控件，但连 `<w:tc>` 单元格外壳都给好，供拼表格用。"""
    checked_val = "1" if checked else "0"
    char = "☒" if checked else "☐"
    return f"""
        <w:tc>
          <w:p>
            <w:sdt>
              <w:sdtPr>
                <w:id w:val="{id_val}"/>
                <w14:checkbox>
                  <w14:checked w14:val="{checked_val}"/>
                  <w14:checkedState w14:val="2612" w14:font="MS Gothic"/>
                  <w14:uncheckedState w14:val="2610" w14:font="MS Gothic"/>
                </w14:checkbox>
              </w:sdtPr>
              <w:sdtEndPr/>
              <w:sdtContent>
                <w:r><w:t>{char}</w:t></w:r>
              </w:sdtContent>
            </w:sdt>
          </w:p>
        </w:tc>"""


def text_cell_xml(text: str) -> str:
    return f"""
        <w:tc>
          <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
        </w:tc>"""


def table_row_xml(cells_xml: list[str]) -> str:
    return "\n      <w:tr>" + "".join(cells_xml) + "\n      </w:tr>"


def table_xml(rows_xml: list[str]) -> str:
    return "\n    <w:tbl>" + "".join(rows_xml) + "\n    </w:tbl>"


def paragraph_xml(text: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def highlighted_run_xml(text: str, color: str = "yellow") -> str:
    return (
        f'<w:r><w:rPr><w:highlight w:val="{color}"/></w:rPr>'
        f"<w:t>{text}</w:t></w:r>"
    )


def plain_run_xml(text: str) -> str:
    return f"<w:r><w:t>{text}</w:t></w:r>"


def ins_xml(id_val: int, author: str, date: str, text: str) -> str:
    return (
        f'<w:ins w:id="{id_val}" w:author="{author}" w:date="{date}">'
        f"<w:r><w:t>{text}</w:t></w:r></w:ins>"
    )


def del_xml(id_val: int, author: str, date: str, text: str) -> str:
    return (
        f'<w:del w:id="{id_val}" w:author="{author}" w:date="{date}">'
        f"<w:r><w:delText>{text}</w:delText></w:r></w:del>"
    )


def comment_anchor_paragraph_xml(comment_id: int, anchored_text: str) -> str:
    return f"""
      <w:p>
        <w:commentRangeStart w:id="{comment_id}"/>
        <w:r><w:t>{anchored_text}</w:t></w:r>
        <w:commentRangeEnd w:id="{comment_id}"/>
        <w:r><w:commentReference w:id="{comment_id}"/></w:r>
      </w:p>"""


def comment_entry_xml(comment_id: int, author: str, date: str, text: str) -> str:
    return f"""
  <w:comment w:id="{comment_id}" w:author="{author}" w:date="{date}">
    <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
  </w:comment>"""
