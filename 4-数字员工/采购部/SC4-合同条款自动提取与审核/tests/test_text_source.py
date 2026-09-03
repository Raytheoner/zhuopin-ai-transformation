"""取文层：真实 PDF/Word 未接入前，宁可当场报错也不静默读成乱码。"""
from __future__ import annotations

from pathlib import Path

import pytest

from sc4_contract.text_source import PlainTextSource

MOCK_DIR = Path(__file__).parent / "mock_data"


def test_纯文本可取文并带来源标识():
    doc = PlainTextSource(MOCK_DIR).load("sample_contract.md")
    assert doc.doc_id == "sample_contract"
    assert doc.source == "mock:plaintext:sample_contract.md"
    assert "第一条" in doc.text


@pytest.mark.parametrize("ref", ["某合同.pdf", "某合同.docx"])
def test_二进制后缀直接拒绝并指向底座doc_parser(ref):
    with pytest.raises(ValueError, match="doc_parser"):
        PlainTextSource(MOCK_DIR).load(ref)


def test_doc_id不可为空():
    from sc4_contract.models import ContractDocument

    with pytest.raises(ValueError, match="doc_id"):
        ContractDocument(doc_id="", title="T", text="x")
