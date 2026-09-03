"""切分与定类层的行为（骨架期唯一有真实产出的一层）。"""
from __future__ import annotations

from pathlib import Path

import pytest

from sc4_contract.clause_extract import segment, summarize_coverage
from sc4_contract.clause_lexicon import MOCK_LEXICON, ClauseLexicon
from sc4_contract.models import ClauseType, ContractDocument
from sc4_contract.text_source import PlainTextSource

MOCK_DIR = Path(__file__).parent / "mock_data"


@pytest.fixture
def sample_doc() -> ContractDocument:
    return PlainTextSource(MOCK_DIR).load("sample_contract.md")


def test_四类条款各命中一段(sample_doc):
    result = segment(sample_doc, MOCK_LEXICON)
    for t in (ClauseType.PRICE, ClauseType.DELIVERY, ClauseType.WARRANTY, ClauseType.PENALTY):
        assert len(result.by_type(t)) == 1, f"{t.value} 未命中或命中多段"


def test_切不出类别的段落如实落未归类而非丢弃(sample_doc):
    result = segment(sample_doc, MOCK_LEXICON)
    others = result.by_type(ClauseType.OTHER)
    assert [s.heading for s in others] == ["其他约定"]


def test_标题行之前的抬头不成span(sample_doc):
    result = segment(sample_doc, MOCK_LEXICON)
    assert result.spans[0].heading == "价格与结算"
    assert "乙方：样例供应商" not in result.spans[0].text


def test_span区间连续且可回指原文(sample_doc):
    result = segment(sample_doc, MOCK_LEXICON)
    for s in result.spans:
        assert sample_doc.text[s.start:s.end].strip() == s.text
    for a, b in zip(result.spans, result.spans[1:]):
        assert a.end == b.start


def test_无标题行时返回空结果而不是整篇塞成一段():
    doc = ContractDocument(doc_id="D0", title="无结构", text="这是一段没有任何条款标题的文字。")
    result = segment(doc, MOCK_LEXICON)
    assert result.spans == []


def test_多类命中时不猜退回未归类():
    lex = ClauseLexicon(
        lexicon_id="test-ambiguous",
        keywords={ClauseType.PRICE: ("价格",), ClauseType.DELIVERY: ("交付",)},
    )
    doc = ContractDocument(doc_id="D1", title="T", text="第一条 交付价格调整\n正文。")
    result = segment(doc, lex)
    assert result.spans[0].clause_type is ClauseType.OTHER


def test_概览只陈述命中不给缺失字段(sample_doc):
    cov = summarize_coverage(segment(sample_doc, MOCK_LEXICON))
    assert "missing_types" not in cov
    assert cov["covered_types"] == ["交付", "价格", "质保", "违约责任"]
    assert cov["lexicon_id"] == "mock-v0"
