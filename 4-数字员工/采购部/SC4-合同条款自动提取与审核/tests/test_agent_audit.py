"""入口层：L2 可归责人必填、audit 如实标注「审核未开始」。"""
from __future__ import annotations

from pathlib import Path

import pytest
from zhuopin_platform.audit import AuditLogger

from sc4_contract.agent import ACTION, SCENARIO, run_extraction
from sc4_contract.clause_lexicon import MOCK_LEXICON
from sc4_contract.text_source import PlainTextSource

MOCK_DIR = Path(__file__).parent / "mock_data"


@pytest.fixture
def doc():
    return PlainTextSource(MOCK_DIR).load("sample_contract.md")


def test_evaluator为空即拒(doc):
    with pytest.raises(ValueError, match="可归责人"):
        run_extraction(doc, MOCK_LEXICON, evaluator="   ")


def test_审计留痕标注审核未开始并点名两项前置(tmp_path, doc):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    run_extraction(doc, MOCK_LEXICON, evaluator="张采购", audit=audit)

    records = audit.query_by(scenario=SCENARIO, action=ACTION)
    assert len(records) == 1
    decision = records[0]["decision"]
    assert decision["review_status"] == "待前置到位"
    assert sorted(decision["blocked_by"]) == ["risk_clause_criteria", "standard_clause_library"]
    assert records[0]["automation_level"] == "L2"
    assert records[0]["evaluator"] == "张采购"
    # 用了哪份词表必须可追溯：词表升版后旧结论要能被认出是旧词表产的
    assert records[0]["data_sources"]["lexicon"] == "mock-v0"
    assert records[0]["data_sources"]["contract"].startswith("mock:plaintext:")


def test_不传audit时不写盘也不报错(doc):
    result = run_extraction(doc, MOCK_LEXICON, evaluator="张采购")
    assert result.doc_id == "sample_contract"
