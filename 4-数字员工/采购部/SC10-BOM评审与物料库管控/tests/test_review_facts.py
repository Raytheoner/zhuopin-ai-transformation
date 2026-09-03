"""事实层：BOM 展开复用底座、共用料识别、数据完备度体检。"""
from __future__ import annotations

import pytest
from zhuopin_platform.shared_tools.models import BomRow, ProductionPlan

from sc10_bom_review.models import LifecycleStatus, MaterialRecord
from sc10_bom_review.review import collect_facts


@pytest.fixture
def bom() -> list[BomRow]:
    return [
        BomRow("F01", "M-A", "电阻A", 1, 2.0, 0.0, "PCS"),
        BomRow("F01", "M-B", "电容B", 1, 1.0, 0.0, "PCS"),
        BomRow("F02", "M-A", "电阻A", 1, 3.0, 0.0, "PCS"),
        BomRow("F02", "M-C", "芯片C", 1, 1.0, 0.0, "PCS"),
    ]


@pytest.fixture
def plans() -> list[ProductionPlan]:
    return [
        ProductionPlan("P1", "F01", "成品一", 10, "2026-09-10"),
        ProductionPlan("P2", "F02", "成品二", 20, "2026-09-11"),
    ]


@pytest.fixture
def materials() -> list[MaterialRecord]:
    return [
        MaterialRecord("M-A", "电阻A", lifecycle=LifecycleStatus.ACTIVE, unit_price=0.1),
        MaterialRecord("M-B", "电容B"),                       # lifecycle 未知 + 无价
        MaterialRecord("M-C", "芯片C", lifecycle=LifecycleStatus.NRND),  # 无价
    ]


def test_毛需求走底座explode_bom不自算(bom, plans, materials):
    facts = collect_facts(bom, plans, materials)
    got = {u.material_id: u.gross_qty for u in facts.usages}
    assert got == {"M-A": 10 * 2.0 + 20 * 3.0, "M-B": 10 * 1.0, "M-C": 20 * 1.0}


def test_跨机型共用料被识别且只陈述事实(bom, plans, materials):
    facts = collect_facts(bom, plans, materials)
    by_id = {u.material_id: u for u in facts.usages}
    assert by_id["M-A"].product_ids == ("F01", "F02")
    assert by_id["M-A"].is_shared is True
    assert by_id["M-B"].is_shared is False


def test_数据完备度体检如实计数(bom, plans, materials):
    facts = collect_facts(bom, plans, materials)
    assert facts.data_readiness == {
        "materials_in_bom": 3,
        "lifecycle_unknown": 1,      # M-B
        "price_missing": 2,          # M-B / M-C
        "not_in_master": 0,
    }


def test_BOM里有主数据缺失的物料时单列不静默丢弃(bom, plans, materials):
    facts = collect_facts(bom, plans, [m for m in materials if m.material_id != "M-C"])
    assert facts.not_in_master == ["M-C"]
    # 缺主数据的物料不重复计入其他缺口桶，避免同一件事被数两遍
    assert facts.data_readiness["price_missing"] == 1


def test_生命周期缺省是未知而不是Active():
    assert MaterialRecord("M-X", "X").lifecycle is LifecycleStatus.UNKNOWN


def test_单价可为None表示无价而非零():
    m = MaterialRecord("M-Y", "Y")
    assert m.unit_price is None
    with pytest.raises(ValueError, match="单价"):
        MaterialRecord("M-Z", "Z", unit_price=-1.0)
