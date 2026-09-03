"""评审层 —— 事实可算，建议留步。

`collect_facts` 是本场景骨架期唯一真跑的函数；三个 `suggest_*` 全在前置闸后。
"""
from __future__ import annotations

from typing import Any, Iterable

from zhuopin_platform.agents.kit_engine import explode_bom
from zhuopin_platform.shared_tools.models import BomRow, ProductionPlan

from . import pending
from .models import BomReviewFacts, BomUsage, LifecycleStatus, MaterialRecord


def _product_index(bom: list[BomRow], plans: list[ProductionPlan]) -> dict[str, set[str]]:
    """{物料 → 用到它的成品集合}，用于识别跨机型共用料。

    刻意逐个成品单独展开再合并，而不是一次性展开全部计划：`explode_bom` 返回的是合计
    毛需求、丢掉了"这份需求来自哪个成品"，而共用料判定要的正是这条来源信息。
    """
    index: dict[str, set[str]] = {}
    by_product: dict[str, ProductionPlan] = {}
    for p in plans:
        by_product.setdefault(p.product_id, p)
    for product_id, plan in by_product.items():
        for material_id in explode_bom(bom, [plan]):
            index.setdefault(material_id, set()).add(product_id)
    return index


def collect_facts(
    bom: list[BomRow],
    plans: list[ProductionPlan],
    materials: Iterable[MaterialRecord],
) -> BomReviewFacts:
    """把 BOM 展开结果与物料主数据对齐，产出事实层与数据完备度体检。

    复用底座 `kit_engine.explode_bom`（O2/SC7/SC8 共用），**不重写展开逻辑**。
    """
    gross = explode_bom(bom, plans)
    index = _product_index(bom, plans)
    master = {m.material_id: m for m in materials}

    facts = BomReviewFacts()
    for material_id in sorted(gross):
        facts.usages.append(
            BomUsage(
                material_id=material_id,
                gross_qty=gross[material_id],
                product_ids=tuple(sorted(index.get(material_id, ()))),
            )
        )
        record = master.get(material_id)
        if record is None:
            facts.not_in_master.append(material_id)
            continue
        if record.lifecycle is LifecycleStatus.UNKNOWN:
            facts.unknown_lifecycle.append(material_id)
        if record.unit_price is None:
            facts.missing_price.append(material_id)
    return facts


def suggest_bom_review(facts: BomReviewFacts) -> list[dict[str, Any]]:
    """BOM 评审建议。前置＝外部行情源（无它就没有可比的价格/参数/封装）。"""
    pending.require("external_price_api")
    raise AssertionError("unreachable")  # pragma: no cover - require() 恒抛


def suggest_selection_level(facts: BomReviewFacts) -> list[dict[str, Any]]:
    """物料优先选用级别建议。前置＝选用级别口径（知识型，判据源未单列）。"""
    pending.require("selection_ranking_criteria")
    raise AssertionError("unreachable")  # pragma: no cover - require() 恒抛


def suggest_obsolescence(facts: BomReviewFacts) -> list[dict[str, Any]]:
    """物料库优先选用与淘汰建议。前置＝物料属性数据 ＋ 选用口径，缺一不可。"""
    pending.require("material_attribute_data")
    raise AssertionError("unreachable")  # pragma: no cover - require() 恒抛
