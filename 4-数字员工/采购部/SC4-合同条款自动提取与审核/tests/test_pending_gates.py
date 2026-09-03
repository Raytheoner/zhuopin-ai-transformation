"""前置闸：判据类能力在前置到位前必须抛，不得有默认值。

这一组测试本身就是「本泳道没有自拟法务判据」的可执行证据 —— 若哪天有人给
`compare_with_standard` 补了个默认实现却没走 openspec，这里会立刻红。
"""
from __future__ import annotations

import pytest

from sc4_contract import pending, review
from sc4_contract.models import ExtractionResult


@pytest.fixture
def empty_result() -> ExtractionResult:
    return ExtractionResult(doc_id="D0")


@pytest.mark.parametrize(
    "fn, blocked_key",
    [
        (review.compare_with_standard, "standard_clause_library"),
        (review.grade_risk, "risk_clause_criteria"),
        (review.detect_missing_clauses, "standard_clause_library"),
    ],
)
def test_判据类能力一律抛且点名卡在哪项前置(fn, blocked_key, empty_result):
    with pytest.raises(pending.PendingPrerequisiteError) as ei:
        fn(empty_result)
    msg = str(ei.value)
    assert pending.BLOCKED[blocked_key].title in msg
    assert pending.BLOCKED[blocked_key].source in msg


def test_两项前置均已登记且带判据源行号级指针():
    assert set(pending.BLOCKED) == {"standard_clause_library", "risk_clause_criteria"}
    for p in pending.BLOCKED.values():
        assert "跨场景前置数据与知识库任务总表.md" in p.source
        assert p.owner and p.status_note


def test_未登记的前置键报KeyError而非静默放行():
    with pytest.raises(KeyError):
        pending.require("不存在的前置")
