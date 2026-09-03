"""SC10 场景入口 —— 骨架期跑「BOM 展开 → 主数据对齐 → 数据完备度体检 → 留痕」。

自动化等级 L2（全景规划 §2.1.2 SC10：AI 评估，采购经理确认）。
骨架期产不出"评估"（口径与外部数据均未到位），故入口输出的是**事实与数据完备度**，
audit 里如实标 `review_status="待前置到位"`。

🔴 红线（规划原文）：涉物料库/BOM 数据走平台 `audit`；采购物料数据**不适用** OEM 隔离
（根 `CLAUDE.md` §4 / `5-平台底座/CLAUDE.md` OEM 隔离边界）—— 故本入口**不**调
`data_isolation_layer`，这是刻意的，不是漏了。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from zhuopin_platform.audit import AuditEvent, AuditLogger
from zhuopin_platform.shared_tools.models import BomRow, ProductionPlan

from .models import BomReviewFacts, MaterialRecord
from .review import collect_facts

SCENARIO = "SC10"
ACTION = "bom_review_facts"


def _content_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def run_review_facts(
    bom: list[BomRow],
    plans: list[ProductionPlan],
    materials: Iterable[MaterialRecord],
    *,
    evaluator: str,
    audit: AuditLogger | None = None,
) -> BomReviewFacts:
    if not evaluator.strip():
        raise ValueError("evaluator 不可为空：L2 场景须留可归责人（IATF 16949）")

    facts = collect_facts(bom, plans, materials)
    readiness = facts.data_readiness

    if audit is not None:
        audit.record(
            AuditEvent(
                scenario=SCENARIO,
                action=ACTION,
                evaluator=evaluator,
                automation_level="L2",
                decision={
                    **readiness,
                    "shared_materials": sum(1 for u in facts.usages if u.is_shared),
                    "review_status": "待前置到位",
                    "blocked_by": [
                        "external_price_api",
                        "material_attribute_data",
                        "selection_ranking_criteria",
                    ],
                },
                data_sources={"bom": "mock:in-memory", "master": "mock:in-memory"},
                content_hash=_content_hash(readiness),
            )
        )
    return facts
