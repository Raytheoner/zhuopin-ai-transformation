"""需求分解、候选枚举、拟稿与留痕。"""
from __future__ import annotations

import pytest
from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.models import BomRow, ProductionPlan

from sc11_transfer import pending
from sc11_transfer.agent import ACTION, SCENARIO, run_draft
from sc11_transfer.models import TransferDemand, Warehouse, WarehouseKind
from sc11_transfer.routing import demands_from_plans, enumerate_candidates

WAREHOUSES = [
    Warehouse("WM", "物料仓", WarehouseKind.MATERIAL),
    Warehouse("W1", "委外仓一", WarehouseKind.OUTSOURCED),
    Warehouse("W3", "委外仓三", WarehouseKind.OUTSOURCED),
]
DISTANCES = {("W1", "W3"): 30.0, ("WM", "W3"): 50.0}
ALL_FOUR = (
    "fewest_cross_warehouse",
    "prefer_material_warehouse",
    "shared_material_by_line_date",
    "nearest_between_outsourced",
)
BOM = [BomRow("F01", "M-A", "电阻A", 1, 2.0, 0.0, "PCS")]
PLANS = [ProductionPlan("P1", "F01", "成品一", 10, "2026-09-10")]


def test_需求分解走底座展开并保住上线日():
    demands = demands_from_plans(BOM, PLANS, {"P1": "W3"})
    assert len(demands) == 1
    d = demands[0]
    assert (d.material_id, d.qty, d.to_warehouse, d.needed_by) == ("M-A", 20.0, "W3", "2026-09-10")


def test_计划未给上线仓时抛而不默认落到某个委外仓():
    with pytest.raises(KeyError, match="未给出上线仓"):
        demands_from_plans(BOM, PLANS, {})


def test_候选枚举跳过目标仓自身且只收够货的仓():
    d = TransferDemand("M-A", "W3", 20.0, "2026-09-10")
    stock = {"WM": {"M-A": 100.0}, "W1": {"M-A": 5.0}, "W3": {"M-A": 999.0}}
    cands = enumerate_candidates(d, stock)
    assert [c.from_warehouse for c in cands] == ["WM"]


def test_源仓与目标仓相同不构成调拨():
    from sc11_transfer.models import TransferCandidate

    d = TransferDemand("M-A", "W3", 5, "2026-09-10")
    with pytest.raises(ValueError, match="不构成调拨"):
        TransferCandidate(demand=d, from_warehouse="W3", qty=5)


def test_满足不了的需求落unmet不静默丢弃(tmp_path):
    demands = demands_from_plans(BOM, PLANS, {"P1": "W3"})
    draft = run_draft(
        demands, {"W1": {"M-A": 1.0}}, WAREHOUSES, DISTANCES, ALL_FOUR, evaluator="李PMC"
    )
    assert draft.lines == []
    assert [d.material_id for d in draft.unmet] == ["M-A"]


def test_拟稿默认未确认且带假设顺序(tmp_path):
    demands = demands_from_plans(BOM, PLANS, {"P1": "W3"})
    draft = run_draft(
        demands, {"WM": {"M-A": 100.0}}, WAREHOUSES, DISTANCES, ALL_FOUR, evaluator="李PMC"
    )
    assert draft.is_approved is False
    assert draft.priority_assumption == ALL_FOUR
    assert draft.lines[0].from_warehouse == "WM"


def test_审计留痕带假设顺序与四项前置(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    demands = demands_from_plans(BOM, PLANS, {"P1": "W3"})
    run_draft(
        demands, {"WM": {"M-A": 100.0}}, WAREHOUSES, DISTANCES, ALL_FOUR,
        evaluator="李PMC", audit=audit,
    )
    rec = audit.query_by(scenario=SCENARIO, action=ACTION)[0]
    assert rec["automation_level"] == "L2"
    assert rec["decision"]["approved"] is False
    assert rec["decision"]["review_status"] == "待前置到位"
    assert rec["decision"]["priority_assumption"] == list(ALL_FOUR)
    assert sorted(rec["decision"]["blocked_by"]) == [
        "logistics_distance_matrix",
        "outsourced_stock_visibility",
        "production_plan_feed",
        "transfer_principle_priority",
    ]


def test_evaluator为空即拒():
    with pytest.raises(ValueError, match="可归责人"):
        run_draft([], {}, WAREHOUSES, DISTANCES, ALL_FOUR, evaluator="")


def test_四项前置全部登记且区分类型():
    assert set(pending.BLOCKED) == {
        "production_plan_feed",
        "outsourced_stock_visibility",
        "transfer_principle_priority",
        "logistics_distance_matrix",
    }
    # 距离矩阵是本场景据实拆出的第四项，判据源里没有
    assert "前置总表三项均不产出此矩阵" in pending.BLOCKED["logistics_distance_matrix"].source
