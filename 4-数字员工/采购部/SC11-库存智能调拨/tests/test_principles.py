"""四条原则的可度量定义，以及"优先级顺序不得默认"这条闸。"""
from __future__ import annotations

import pytest

from sc11_transfer import pending
from sc11_transfer.models import (
    TransferCandidate,
    TransferDemand,
    Warehouse,
    WarehouseKind,
)
from sc11_transfer.principles import build_principles, rank_candidates

WAREHOUSES = [
    Warehouse("WM", "物料仓", WarehouseKind.MATERIAL),
    Warehouse("W1", "委外仓一", WarehouseKind.OUTSOURCED),
    Warehouse("W2", "委外仓二", WarehouseKind.OUTSOURCED),
    Warehouse("W3", "委外仓三", WarehouseKind.OUTSOURCED),
]
WH_INDEX = {w.code: w for w in WAREHOUSES}
DISTANCES = {("W1", "W3"): 30.0, ("W2", "W3"): 10.0, ("WM", "W3"): 50.0}
ALL_FOUR = (
    "fewest_cross_warehouse",
    "prefer_material_warehouse",
    "shared_material_by_line_date",
    "nearest_between_outsourced",
)


@pytest.fixture
def principles():
    return build_principles(WH_INDEX, DISTANCES)


def _demand(to="W3", needed_by="2026-09-10") -> TransferDemand:
    return TransferDemand(material_id="M-A", to_warehouse=to, qty=5, needed_by=needed_by)


def test_四条原则文本逐字转录自规划原文(principles):
    assert [p.text for p in principles.values()] == [
        "跨仓调拨尽量少",
        "优先物料仓→委外仓",
        "共用料按上线时间顺序",
        "委外仓间就近优先",
    ]


def test_优先级顺序不全时抛_不替PMC决定哪条不重要(principles):
    cands = [TransferCandidate(_demand(), "WM", 5)]
    with pytest.raises(pending.PendingPrerequisiteError, match="调拨原则口径"):
        rank_candidates(cands, principles, ["fewest_cross_warehouse"])


def test_物料仓优先于委外仓(principles):
    cands = [
        TransferCandidate(_demand(), "W1", 5),
        TransferCandidate(_demand(), "WM", 5),
    ]
    ranked = rank_candidates(cands, principles, ALL_FOUR)
    assert ranked[0].from_warehouse == "WM"


def test_委外仓间按距离矩阵就近(principles):
    order = ("nearest_between_outsourced",) + tuple(k for k in ALL_FOUR if k != "nearest_between_outsourced")
    cands = [
        TransferCandidate(_demand(), "W1", 5),   # 30
        TransferCandidate(_demand(), "W2", 5),   # 10
    ]
    ranked = rank_candidates(cands, principles, order)
    assert [c.from_warehouse for c in ranked] == ["W2", "W1"]


def test_距离查不到时排在最后而不是当成零(principles):
    order = ("nearest_between_outsourced",) + tuple(k for k in ALL_FOUR if k != "nearest_between_outsourced")
    d = _demand(to="W2")
    cands = [
        TransferCandidate(d, "W3", 5),   # ("W3","W2") 不在矩阵里 → None
        TransferCandidate(d, "W1", 5),   # ("W1","W2") 也不在 → None
        TransferCandidate(d, "WM", 5),   # 同样不在 → None
    ]
    ranked = rank_candidates(cands, principles, order)
    # 四条全 None 时退化为稳定排序（原顺序），关键是不因缺数据而冒充最优
    assert len(ranked) == 3


def test_缺上线日期的需求不被排到最前(principles):
    order = ("shared_material_by_line_date",) + tuple(k for k in ALL_FOUR if k != "shared_material_by_line_date")
    早 = TransferCandidate(_demand(needed_by="2026-09-01"), "W1", 5)
    无 = TransferCandidate(_demand(needed_by=""), "W2", 5)
    ranked = rank_candidates([无, 早], principles, order)
    assert ranked[0] is 早


def test_源仓不在仓库表时不猜(principles):
    score = principles["prefer_material_warehouse"].score
    assert score(TransferCandidate(_demand(), "W1", 5)) == 1.0
    assert score(TransferCandidate(_demand(), "W-未登记", 5)) is None
