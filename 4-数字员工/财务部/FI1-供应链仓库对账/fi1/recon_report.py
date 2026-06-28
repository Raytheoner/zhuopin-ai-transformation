"""对账聚合 + L2 门禁 + 审计（design D6/D7）。

逐料号对账差异报告（理论/标准损耗/实际/总差异/差异率/分类/状态）；
L2 门禁：needs_review / bom_incomplete → 标"需人工确认"/"待人工核"，**不自动结案**；
每笔判定写平台 AuditLogger（scenario=FI1，数量为主，金额不落 AI 侧）。
报告标注"AI 对账建议，结案在财务+供应链经理"（非终局）。
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict

from zhuopin_platform.audit import AuditEvent

from . import config as _config
from .models import ComponentReconcile

DISCLAIMER = "AI 对账建议，结案在财务+供应链经理（非终局，超阈值不自动结案）"


def _status(c: ComponentReconcile) -> str:
    if c.bom_incomplete:
        return "待人工核"
    if c.needs_review:
        return "需人工确认"
    return "AI建议通过"


def _decision_payload(c: ComponentReconcile, rule_version: str) -> dict:
    """审计/报告决策载荷 —— **数量为主，无金额/单价**（财务红色数据脱敏，红线 D7）。"""
    return {
        "component_id": c.component_id,
        "theoretical_net": c.theoretical_net,
        "standard_loss": c.standard_loss,
        "actual_feed": c.actual_feed,
        "total_variance": c.total_variance,
        "variance_pct": c.variance_pct,
        "classification": c.classification,
        "severity": c.severity,
        "needs_review": c.needs_review,
        "bom_incomplete": c.bom_incomplete,
        "rule_id": c.rule_id,
        "rule_version": rule_version,
    }


def build_report(
    components: list[ComponentReconcile],
    incomplete_products: list[str],
    *,
    data_sources: dict[str, str],
    rule_version: str | None = None,
    bom_source: str = "",
    evaluator: str = "",
    period: str = "",
    audit=None,
    cfg=_config,
) -> dict:
    """聚合对账报告 + 过 L2 门禁 + 写审计。

    Args:
        components: 已分类的对账结果（先经 variance_classify.classify_all）。
        incomplete_products: BOM 拉取失败的成品（待人工核）。
        data_sources: 各输入来源标记（如 {"bom":"u9c","output":"csv","feed":"csv"}）。
        audit: 平台 AuditLogger（None 则不留痕；生产必传）。
    """
    rv = rule_version or cfg.RULE_VERSION
    items: list[dict] = []
    for c in components:
        row = _decision_payload(c, rv)
        row["component_name"] = c.component_name
        row["status"] = _status(c)
        items.append(row)

    auto_pass = [it for it in items if it["status"] == "AI建议通过"]
    needs_review = [it for it in items if it["status"] == "需人工确认"]
    manual_check = [it for it in items if it["status"] == "待人工核"]
    by_class = dict(Counter(it["classification"] for it in items))

    report = {
        "scenario": "FI1",
        "period": period,
        "disclaimer": DISCLAIMER,
        "automation_level": "L2",
        "rule_version": rv,
        "bom_source": bom_source,
        "data_sources": data_sources,
        "items": items,
        "needs_review": needs_review,
        "manual_check": manual_check,
        "incomplete_products": list(incomplete_products),
        "summary": {
            "total": len(items),
            "auto_suggest_pass": len(auto_pass),
            "needs_review": len(needs_review),
            "manual_check": len(manual_check),
            "incomplete_products": len(incomplete_products),
            "by_classification": by_class,
        },
    }

    # 全链审计：每笔对账判定 + 分类 append-only 留痕（数量为主，金额不落）
    if audit is not None:
        for c in components:
            decision = _decision_payload(c, rv)
            content_hash = hashlib.sha256(
                json.dumps(decision, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()
            audit.record(AuditEvent(
                scenario="FI1",
                action="warehouse_reconcile",
                evaluator=evaluator,
                automation_level="L2",
                decision=decision,
                data_sources=data_sources,
                content_hash=content_hash,
            ))

    return report
