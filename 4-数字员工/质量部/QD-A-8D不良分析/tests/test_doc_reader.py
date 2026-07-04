"""doc_reader 单测 — 段落解析与文本提取。"""
from qda_prefill.doc_reader import _parse_sections, DocumentSections


def test_parse_d_sections_from_text():
    text = (
        "8D报告 - 案例编号: 8D-2026-001\n"
        "D2: 某产品在高温下异常重启，客户反馈。\n"
        "具体现象：偶发，频率约3次/百小时。\n"
        "D3: 紧急隔离现场库存。\n"
        "D4: 根本原因：电容降额不足。\n"
    )
    doc = _parse_sections(text, "test.docx")
    assert "D2" in doc.sections
    assert "电容降额不足" in doc.sections.get("D4", "")
    assert doc.full_text == text


def test_parse_returns_header_text():
    text = "X" * 600
    doc = _parse_sections(text, "test.docx")
    assert len(doc.header_text) == 500


def test_parse_no_sections_returns_empty_sections():
    text = "没有任何段落标头的普通文本内容。"
    doc = _parse_sections(text, "test.docx")
    assert doc.sections == {}
    assert doc.full_text == text


def test_read_docx_extracts_sections(synthetic_docx):
    from qda_prefill.doc_reader import read
    doc = read(synthetic_docx)
    assert isinstance(doc, DocumentSections)
    assert "D2" in doc.sections
    assert "D4" in doc.sections
    assert "D7" in doc.sections
    assert "D8" in doc.sections
