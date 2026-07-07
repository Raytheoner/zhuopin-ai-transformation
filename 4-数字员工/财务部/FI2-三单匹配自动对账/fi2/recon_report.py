"""对账聚合 + L3 门禁 + 审计（design D4/D7，spec: fi2-recon-report）。

逐 PO 行匹配结果聚合为报告；四类非完全匹配（金额微差/明细错位/数量金额不符/无GR支撑）标
`needs_review`（强制转人工）；完全匹配类标 `l3_suggested_pass`（AI 建议通过，**未过账**，
仅供抽查）。每行写平台 AuditLogger（scenario=FI2，金额脱敏——只记差异比例，不落原始
发票单价/含税金额绝对值）。孤立发票（无对应 PO 行）单列，不计入五类分类。
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter

from zhuopin_platform.audit import AuditEvent

from . import config as _config
from .models import InvoiceLine, LineMatch

DISCLAIMER = "AI 建议通过/预警，未过账；结案与过账在财务人员（L3 阶段不实现自动过账，达标后另行晋级 L4）"


def _decision_payload(line: LineMatch) -> dict:
    """审计/报告决策载荷 —— **差异比例为主，不含原始金额绝对值**（财务红色数据脱敏，红线 D7）。"""
    return {
        "po_no": line.po_no,
        "line_no": line.line_no,
        "item_code": line.item_code,
        "has_grn": line.has_grn,
        "item_code_match": line.item_code_match,
        "qty_diff_pct": line.qty_diff_pct,
        "amount_diff_pct": line.amount_diff_pct,
        "tax_rate_match": line.tax_rate_match,
        "classification": line.classification,
        "status": line.status,
        "needs_review": line.needs_review,
        "rule_version": line.rule_version,
    }


def build_report(
    lines: list[LineMatch],
    orphaned_invoices: list[InvoiceLine],
    *,
    data_sources: dict[str, str],
    evaluator: str = "",
    period: str = "",
    audit=None,
    cfg=_config,
) -> dict:
    """聚合匹配报告 + 过 L3 门禁 + 写审计。

    Args:
        lines: 已分类的 `LineMatch`（先经 result_classify.classify_all）。
        orphaned_invoices: 找不到对应 PO 行的孤立发票（不计入五类分类，单列待处理）。
        data_sources: 各输入来源标记（如 {"po":"mock","grn":"mock","invoice":"mock"}）。
        audit: 平台 AuditLogger（None 则不留痕；生产必传）。
    """
    items = [_decision_payload(line) for line in lines]

    l3_suggested_pass = [it for it in items if it["status"] == "l3_suggested_pass"]
    needs_review = [it for it in items if it["status"] == "needs_review"]
    by_class = dict(Counter(it["classification"] for it in items))

    orphaned = [
        {"inv_no": inv.inv_no, "po_no": inv.po_no, "line_no": inv.line_no, "item_code": inv.item_code}
        for inv in orphaned_invoices
    ]

    report = {
        "scenario": "FI2",
        "period": period,
        "disclaimer": DISCLAIMER,
        "automation_level": "L3",
        "rule_version": cfg.RULE_VERSION,
        "data_sources": data_sources,
        "items": items,
        "needs_review": needs_review,
        "l3_suggested_pass": l3_suggested_pass,
        "orphaned_invoices": orphaned,
        "summary": {
            "total": len(items),
            "l3_suggested_pass": len(l3_suggested_pass),
            "needs_review": len(needs_review),
            "orphaned_invoices": len(orphaned),
            "by_classification": by_class,
        },
    }

    # 全链审计：每行匹配判定 append-only 留痕（差异比例为主，金额绝对值不落）
    if audit is not None:
        for line in lines:
            decision = _decision_payload(line)
            content_hash = hashlib.sha256(
                json.dumps(decision, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()
            audit.record(AuditEvent(
                scenario="FI2",
                action="line_match",
                evaluator=evaluator,
                automation_level="L3",
                decision=decision,
                data_sources=data_sources,
                content_hash=content_hash,
            ))

    return report
