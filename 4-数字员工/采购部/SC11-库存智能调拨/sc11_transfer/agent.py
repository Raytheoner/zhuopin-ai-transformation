"""SC11 场景入口 —— 骨架期跑「需求分解 → 候选枚举 → 假设顺序试算 → 拟稿 → 留痕」。

自动化等级 L2（全景规划：AI 操作，PMC 经理决策）。入口**只产拟稿**，
落 ERP 与外发一律经 `gate.py`，本模块不提供任何直达执行的路径。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from zhuopin_platform.audit import AuditEvent, AuditLogger

from .models import TransferDemand, TransferPlanDraft, Warehouse
from .principles import build_principles
from .routing import build_draft, warehouse_index

SCENARIO = "SC11"
ACTION = "transfer_plan_draft"


def _content_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def run_draft(
    demands: Sequence[TransferDemand],
    stock_by_warehouse: Mapping[str, Mapping[str, float]],
    warehouses: Sequence[Warehouse],
    distances: Mapping[tuple[str, str], float],
    priority_assumption: Sequence[str],
    *,
    evaluator: str,
    audit: AuditLogger | None = None,
) -> TransferPlanDraft:
    if not evaluator.strip():
        raise ValueError("evaluator 不可为空：L2 场景须留可归责人（IATF 16949）")

    principles = build_principles(warehouse_index(warehouses), distances)
    draft = build_draft(demands, stock_by_warehouse, principles, priority_assumption)

    if audit is not None:
        summary = draft.summary
        audit.record(
            AuditEvent(
                scenario=SCENARIO,
                action=ACTION,
                evaluator=evaluator,
                automation_level="L2",
                decision={
                    **summary,
                    "review_status": "待前置到位",
                    "blocked_by": [
                        "production_plan_feed",
                        "outsourced_stock_visibility",
                        "transfer_principle_priority",
                        "logistics_distance_matrix",
                    ],
                },
                data_sources={"plans": "mock:in-memory", "stock": "mock:in-memory"},
                content_hash=_content_hash(summary),
            )
        )
    return draft
