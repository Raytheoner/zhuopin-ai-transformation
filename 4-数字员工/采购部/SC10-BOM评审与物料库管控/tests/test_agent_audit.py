"""入口层：L2 可归责人必填、audit 如实标注三项前置、不走 OEM 隔离。"""
from __future__ import annotations

import pytest
from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.models import BomRow, ProductionPlan

from sc10_bom_review.agent import ACTION, SCENARIO, run_review_facts
from sc10_bom_review.models import LifecycleStatus, MaterialRecord

BOM = [
    BomRow("F01", "M-A", "电阻A", 1, 2.0, 0.0, "PCS"),
    BomRow("F02", "M-A", "电阻A", 1, 3.0, 0.0, "PCS"),
]
PLANS = [
    ProductionPlan("P1", "F01", "成品一", 10, "2026-09-10"),
    ProductionPlan("P2", "F02", "成品二", 20, "2026-09-11"),
]
MATERIALS = [MaterialRecord("M-A", "电阻A", lifecycle=LifecycleStatus.ACTIVE, unit_price=0.1)]


def test_evaluator为空即拒():
    with pytest.raises(ValueError, match="可归责人"):
        run_review_facts(BOM, PLANS, MATERIALS, evaluator="")


def test_审计留痕标注待前置到位并点名三项(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    run_review_facts(BOM, PLANS, MATERIALS, evaluator="姚祖怡", audit=audit)

    records = audit.query_by(scenario=SCENARIO, action=ACTION)
    assert len(records) == 1
    decision = records[0]["decision"]
    assert decision["review_status"] == "待前置到位"
    assert sorted(decision["blocked_by"]) == [
        "external_price_api",
        "material_attribute_data",
        "selection_ranking_criteria",
    ]
    assert decision["shared_materials"] == 1
    assert records[0]["automation_level"] == "L2"


def test_采购物料数据不走OEM隔离故oem_context留空(tmp_path):
    # 规划原文与底座 OEM 隔离边界均写明：采购物料数据不适用 OEM 隔离。
    # 这里断言的是"刻意没做"，避免后来者以为是漏了而顺手补上路由。
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    run_review_facts(BOM, PLANS, MATERIALS, evaluator="姚祖怡", audit=audit)
    assert audit.query_by(scenario=SCENARIO)[0].get("oem_context", "") == ""
