"""前置闸：三项建议能力在前置到位前必须抛；生命周期枚举顺序不得被当成优先级。"""
from __future__ import annotations

import pytest

from sc10_bom_review import pending, review
from sc10_bom_review.models import BomReviewFacts, LifecycleStatus
from sc10_bom_review.sources import UnselectedCatalogSource


@pytest.fixture
def facts() -> BomReviewFacts:
    return BomReviewFacts()


@pytest.mark.parametrize(
    "fn, blocked_key",
    [
        (review.suggest_bom_review, "external_price_api"),
        (review.suggest_selection_level, "selection_ranking_criteria"),
        (review.suggest_obsolescence, "material_attribute_data"),
    ],
)
def test_三项建议一律抛且点名卡在哪项前置(fn, blocked_key, facts):
    with pytest.raises(pending.PendingPrerequisiteError) as ei:
        fn(facts)
    assert pending.BLOCKED[blocked_key].title in str(ei.value)


def test_外部行情源占位实现调用即抛():
    with pytest.raises(pending.PendingPrerequisiteError, match="选型"):
        UnselectedCatalogSource().fetch(["M-A"])


def test_前置登记区分数据型与知识型():
    # 这个区分不是装饰：数据型按 6 周倒排、知识型按 8 周，混记会算错启动日
    kinds = {k: p.kind for k, p in pending.BLOCKED.items()}
    assert kinds == {
        "external_price_api": "数据型",
        "material_attribute_data": "数据型",
        "selection_ranking_criteria": "知识型",
    }


def test_选用口径被单列而非并进数据型前置():
    p = pending.BLOCKED["selection_ranking_criteria"]
    assert "前置总表未单列" in p.source


def test_窗口未到与已逾期在状态里被区分开():
    for key in ("external_price_api", "material_attribute_data"):
        assert "窗口未到，非逾期" in pending.BLOCKED[key].status_note


def test_生命周期枚举不可比较大小():
    # 若有人给 LifecycleStatus 混入 str（本仓库其余枚举的惯用写法）或加了 order=True，
    # `ACTIVE < NRND` 会静默按字母序成立 —— 一个看起来能用、实际毫无业务含义的排序。
    # 这正是"靠枚举顺序偷偷造判据"的入口，故在此硬拦。
    with pytest.raises(TypeError):
        _ = LifecycleStatus.ACTIVE < LifecycleStatus.NRND
    with pytest.raises(TypeError):
        sorted([LifecycleStatus.OBSOLETE, LifecycleStatus.ACTIVE])


def test_生命周期序列化取value而非成员本身():
    assert LifecycleStatus.NRND.value == "NRND"
    assert LifecycleStatus.NEW_PRODUCT.value == "New Product"
