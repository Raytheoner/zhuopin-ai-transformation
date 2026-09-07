# -*- coding: utf-8 -*-
"""统一 docx 取文单测（队列 `#481` spec「取文完整度须覆盖表格与内容控件」）。

治的是 `qda_prefill/doc_reader._read_docx()` 那条路：用 python-docx 的
`doc.paragraphs` 取文 ⇒ 表格与内容控件里的字**一个都拿不到**，真实回件实测
丢 26%（`采购部` 08-26）～71%（`质量部#11`）正文。
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from zhuopin_platform.shared_tools.doc_parser import (
    DocxReadError,
    extract_text,
    extract_text_lines,
)

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
W14 = 'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"'


def _write_docx(tmp_path, name: str, body_xml: str, extra_parts: dict = None) -> Path:
    doc = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:document {W} {W14}><w:body>{body_xml}</w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", doc)
        for part_name, content in (extra_parts or {}).items():
            z.writestr(part_name, content)
    path = tmp_path / name
    path.write_bytes(buf.getvalue())
    return path


BODY = (
    "<w:p><w:r><w:t>D2: 问题描述</w:t></w:r></w:p>"
    "<w:tbl><w:tr>"
    "<w:tc><w:p><w:r><w:t>料号</w:t></w:r></w:p></w:tc>"
    "<w:tc><w:p><w:r><w:t>ZK-ECU-088</w:t></w:r></w:p></w:tc>"
    "</w:tr></w:tbl>"
    "<w:p><w:sdt><w:sdtPr/><w:sdtContent>"
    "<w:r><w:t>控件里的正文也要取到</w:t></w:r>"
    "</w:sdtContent></w:sdt></w:p>"
    "<w:p><w:hyperlink><w:r><w:t>超链接里的字</w:t></w:r></w:hyperlink></w:p>"
    "<w:p/>"
)


def test_取文覆盖表格与内容控件(tmp_path):
    path = _write_docx(tmp_path, "full.docx", BODY)
    lines = extract_text_lines(path)
    assert lines == [
        "D2: 问题描述",
        "料号 | ZK-ECU-088",
        "控件里的正文也要取到",
        "超链接里的字",
    ]


def test_与只取直接run的高层视图对照_确实多取到了(tmp_path):
    """反面对照：模拟 python-docx `doc.paragraphs` 的取法会丢掉哪些。"""
    from zhuopin_platform.shared_tools.doc_parser import _xml

    path = _write_docx(tmp_path, "cmp.docx", BODY)
    _, roots = _xml.read_parts(path, include_extra_parts=False)
    body = roots[0][1].find(_xml.w("body"))
    high_level = [
        t for t in (_xml.simulated_paragraph_text(p).strip() for p in body.findall(_xml.w("p")))
        if t
    ]
    # 高层视图只看得见第一段：表格（不是 body 的直接 w:p）、控件内、超链接内全丢
    assert high_level == ["D2: 问题描述"]
    assert len(extract_text_lines(path)) == 4


def test_读不了即抛_绝不返回空串(tmp_path):
    bad = tmp_path / "broken.docx"
    bad.write_bytes(b"not a zip")
    with pytest.raises(DocxReadError, match="不是合法的 zip"):
        extract_text(bad)


def test_可选取页眉页脚(tmp_path):
    header = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:hdr {W} {W14}><w:p><w:r><w:t>页眉文字</w:t></w:r></w:p></w:hdr>"
    )
    path = _write_docx(
        tmp_path, "hdr.docx", "<w:p><w:r><w:t>正文</w:t></w:r></w:p>",
        extra_parts={"word/header1.xml": header},
    )
    assert extract_text(path) == "正文"
    assert extract_text(path, include_extra_parts=True) == "正文\n页眉文字"
