"""field_extractor 单测 — 12字段提取。"""
from qda_prefill.doc_reader import read
from qda_prefill.field_extractor import Confidence, extract_fields


def test_case_id_extracted(synthetic_docx):
    doc = read(synthetic_docx)
    record = extract_fields(doc)
    assert "8D-2026-031" in record.case_id.value
    assert record.case_id.confidence == Confidence.HIGH


def test_closure_date_extracted(synthetic_docx):
    doc = read(synthetic_docx)
    record = extract_fields(doc)
    assert record.closure_date.value == "2026-06-15"
    assert record.closure_date.confidence == Confidence.HIGH


def test_defect_description_from_d2(synthetic_docx):
    doc = read(synthetic_docx)
    record = extract_fields(doc)
    assert record.defect_description.value.strip() != ""
    assert record.defect_description.confidence in (Confidence.MED, Confidence.HIGH)


def test_root_cause_from_d4(synthetic_docx):
    doc = read(synthetic_docx)
    record = extract_fields(doc)
    rc = record.root_cause.value
    assert "根本原因" in rc or "降额" in rc or "规范" in rc


def test_safety_related_default_low(synthetic_docx):
    doc = read(synthetic_docx)
    record = extract_fields(doc)
    assert record.safety_related.value == "否"
    assert record.safety_related.confidence == Confidence.LOW


def test_safety_related_yes_on_keyword():
    from qda_prefill.doc_reader import _parse_sections
    from qda_prefill.field_extractor import extract_fields
    text = "D2: ECU ASIL-D功能安全相关失效，导致制动系统异常。\nD3: 隔离。\n"
    doc = _parse_sections(text, "test.docx")
    record = extract_fields(doc)
    assert record.safety_related.value == "是"
    assert record.safety_related.confidence == Confidence.HIGH


def test_defect_category_process(synthetic_docx):
    doc = read(synthetic_docx)
    record = extract_fields(doc)
    assert record.defect_category.value == "制程"


def test_root_cause_verified_yes(synthetic_docx):
    doc = read(synthetic_docx)
    record = extract_fields(doc)
    assert record.root_cause_verified.value == "是"


def test_corrective_actions_includes_d5_to_d7(synthetic_docx):
    doc = read(synthetic_docx)
    record = extract_fields(doc)
    ca = record.corrective_actions.value
    assert "[D5]" in ca or "[D6]" in ca or "[D7]" in ca


def test_all_fields_have_confidence(synthetic_docx):
    doc = read(synthetic_docx)
    record = extract_fields(doc)
    for label, data in record.to_dict().items():
        conf = data.get("confidence")
        assert conf in ("HIGH", "MED", "LOW"), f"字段 {label} 缺少有效置信度"


def test_to_dict_has_12_fields(synthetic_docx):
    doc = read(synthetic_docx)
    record = extract_fields(doc)
    d = record.to_dict()
    assert len(d) == 12
