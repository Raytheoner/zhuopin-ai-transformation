"""calibrate 单测 — 命中率计算与报告生成。"""
from qda_prefill.calibrate import (RecordComparison, batch_report,
                                    compare_record, load_golden_csv)
from qda_prefill.doc_reader import read
from qda_prefill.field_extractor import extract_fields


def test_compare_case_id_exact(synthetic_docx, golden_csv):
    doc = read(synthetic_docx)
    record = extract_fields(doc)
    golden_rows = load_golden_csv(golden_csv)
    comp = compare_record(record, golden_rows[0], source="test")
    # 案例ID精确匹配
    case_id_hit = next(h for h in comp.hits if h.field == "案例ID")
    assert case_id_hit.hit is True
    assert case_id_hit.method == "exact"


def test_compare_closure_date_exact(synthetic_docx, golden_csv):
    doc = read(synthetic_docx)
    record = extract_fields(doc)
    golden_rows = load_golden_csv(golden_csv)
    comp = compare_record(record, golden_rows[0])
    date_hit = next(h for h in comp.hits if h.field == "结案日期")
    assert date_hit.hit is True


def test_overall_score_positive(synthetic_docx, golden_csv):
    doc = read(synthetic_docx)
    record = extract_fields(doc)
    golden_rows = load_golden_csv(golden_csv)
    comp = compare_record(record, golden_rows[0])
    assert comp.overall_score > 0.3   # 合成夹具至少30%命中


def test_batch_report_contains_table(synthetic_docx, golden_csv):
    doc = read(synthetic_docx)
    record = extract_fields(doc)
    golden_rows = load_golden_csv(golden_csv)
    comp = compare_record(record, golden_rows[0], source="sample_8d.docx")
    report = batch_report([comp])
    assert "## 字段命中率" in report
    assert "案例ID" in report
    assert "结案日期" in report


def test_load_golden_csv(golden_csv):
    rows = load_golden_csv(golden_csv)
    assert len(rows) == 1
    assert rows[0]["案例ID"] == "8D-2026-031"
    assert rows[0]["不良分类"] == "制程"
