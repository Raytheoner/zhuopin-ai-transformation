"""对账聚合 + L3 门禁 + R5 门禁 + 审计（design D4/D7/D12/D14，spec: fi2-recon-report，
v3 口径修正 2026-07-09 + R1/R5/R7 真值落地 2026-07-10）。

按料品（ap_no, item_code）聚合匹配结果为报告；四类非完全匹配（金额微差/明细错位/数量金额
不符/无发票支撑）标 `needs_review`（强制转人工）；完全匹配类标 `l3_suggested_pass`（AI 建议
通过，**未过账**，仅供抽查）。**AP-PO 单价超差（价格校验，design D12）独立于五类判定**——
即便某料品四维判定为"完全匹配"，只要其价格超差，本层 MUST 将其状态强制改写为
`needs_review`（分类结果本身不变，仅路由状态被覆盖，保持判定语义真实可查）。

**R5 门禁（design D14 新增）**：仅对"金额微差"类生效——同一 AP 单下"金额微差"料品的未税
金额差异总额，相对整单（PO 行）合计未税金额，在门禁线内（¥1 或 0.5%，两者取宽松者）→
状态改 `l2_self_resolved`（AP 自行消化，不转人工）；超线维持 `needs_review`。价格超差
（price_check）优先级高于本门禁——价格超差 MUST 强制转人工，不因 R5 门禁而放行。"无发票
支撑"/"明细错位"/"数量金额不符"三类不在本门禁范围内（结构性问题不因总额小而降级，CC 从紧
解读，待唐燕萍团队批改，见场景 CLAUDE.md）。

每行写平台 AuditLogger（scenario=FI2，金额脱敏——只记差异比例，不落原始 AP/发票单价/
未税金额/税额绝对值）。孤立发票（挂载的 ap_no 找不到对应 AP 单）单列，不计入五类分类。
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter

from zhuopin_platform.audit import AuditEvent

from . import config as _config
from .models import APLine, InvoiceLine, ItemMatch, POLine, PriceCheckResult
from .price_check import failed_item_keys

DISCLAIMER = "AI 建议通过/预警，未过账；结案与过账在财务人员（L3 阶段不实现自动过账，达标后另行晋级 L4）"

# R5 门禁仅对"金额微差"类生效（design D14，见模块 docstring 的从紧解读）
_L2_ELIGIBLE_CLASS = "金额微差"


def _price_diff_pct_by_item(price_results: list[PriceCheckResult]) -> dict[tuple[str, str], float]:
    """同一料品可能对应多条 AP 行价格校验结果，取偏离幅度最大者作报告代表值（脱敏，只留比例）。"""
    out: dict[tuple[str, str], float] = {}
    for r in price_results:
        if r.price_diff_pct is None:
            continue
        key = (r.ap_no, r.item_code)
        if key not in out or abs(r.price_diff_pct) > abs(out[key]):
            out[key] = r.price_diff_pct
    return out


def _po_untaxed_by_ap(ap_lines: list[APLine], po_lines: list[POLine]) -> dict[str, float]:
    """R5 门禁分母——整单（PO 行）合计未税金额：按该 ap_no 下 AP 明细行关联的
    `(po_no, line_no)` 精确匹配对应 PO 行未税金额（qty×unit_price）求和，同一 PO 行
    在同一 ap_no 下去重只计一次。找不到对应 PO 行按 0 计（不阻断门禁计算，仅影响分母
    精度，真实数据接入后可校准）。
    """
    po_untaxed = {(p.po_no, p.line_no): p.qty * p.unit_price for p in po_lines}
    totals: dict[str, float] = {}
    seen: dict[str, set] = {}
    for a in ap_lines:
        key = (a.po_no, a.line_no)
        s = seen.setdefault(a.ap_no, set())
        if key in s:
            continue
        s.add(key)
        totals[a.ap_no] = totals.get(a.ap_no, 0.0) + po_untaxed.get(key, 0.0)
    return totals


def _l2_gated_ap_docs(
    items: list[ItemMatch], ap_lines: list[APLine], po_lines: list[POLine], *, cfg
) -> set[str]:
    """R5 门禁：返回其"金额微差"类料品应降级为 L2 自行消化的 ap_no 集合。"""
    if not ap_lines or not po_lines:
        return set()

    by_ap: dict[str, list[ItemMatch]] = {}
    for it in items:
        if it.classification == _L2_ELIGIBLE_CLASS:
            by_ap.setdefault(it.ap_no, []).append(it)
    if not by_ap:
        return set()

    po_totals = _po_untaxed_by_ap(ap_lines, po_lines)
    gated: set[str] = set()
    for ap_no, its in by_ap.items():
        diff_total = sum(it.untaxed_amount_diff for it in its if it.untaxed_amount_diff is not None)
        po_total = po_totals.get(ap_no, 0.0)
        within_abs = abs(diff_total) <= cfg.L2_GATE_ABS_THRESHOLD
        within_pct = bool(po_total) and abs(diff_total / po_total) <= cfg.UNTAXED_AMOUNT_TOLERANCE_PCT
        if within_abs or within_pct:
            gated.add(ap_no)
    return gated


def _decision_payload(
    item: ItemMatch, *, price_failed: bool, price_diff_pct: float | None, l2_gated: bool
) -> dict:
    """审计/报告决策载荷 —— **差异比例为主，不含原始金额绝对值**（财务红色数据脱敏，红线 D7）。

    优先级：价格超差（price_failed）> R5 门禁（l2_gated）> 原始分类路由（item.status）。
    """
    if price_failed:
        effective_status = "needs_review"
    elif l2_gated:
        effective_status = "l2_self_resolved"
    else:
        effective_status = item.status
    effective_needs_review = effective_status == "needs_review"
    return {
        "ap_no": item.ap_no,
        "item_code": item.item_code,
        "has_invoice": item.has_invoice,
        "qty_diff_pct": item.qty_diff_pct,
        "untaxed_amount_diff_pct": item.untaxed_amount_diff_pct,
        "tax_amount_diff_pct": item.tax_amount_diff_pct,
        "classification": item.classification,
        "price_check_failed": price_failed,
        "price_diff_pct": price_diff_pct,
        "status": effective_status,
        "needs_review": effective_needs_review,
        "rule_version": item.rule_version,
    }


def build_report(
    items: list[ItemMatch],
    orphaned_invoices: list[InvoiceLine],
    price_results: list[PriceCheckResult] | None = None,
    *,
    ap_lines: list[APLine] | None = None,
    po_lines: list[POLine] | None = None,
    data_sources: dict[str, str],
    evaluator: str = "",
    period: str = "",
    audit=None,
    cfg=_config,
) -> dict:
    """聚合匹配报告 + 过 L3/R5 门禁（含价格校验强制路由）+ 写审计。

    Args:
        items: 已分类的 `ItemMatch`（先经 result_classify.classify_all）。
        orphaned_invoices: 挂载的 ap_no 找不到对应 AP 单的孤立发票（不计入五类分类，单列待处理）。
        price_results: AP-PO 单价校验结果（design D12，None 则视为无价格超差项）。
        ap_lines/po_lines: R5 门禁分母计算用（design D14）；缺省则不计算 R5 门禁
            （所有"金额微差"维持 needs_review，向后兼容不传该二参的调用方）。
        data_sources: 各输入来源标记（如 {"po":"mock","ap":"mock","invoice":"mock"}）。
        audit: 平台 AuditLogger（None 则不留痕；生产必传）。
    """
    price_results = price_results or []
    failed_keys = failed_item_keys(price_results)
    diff_pct_by_key = _price_diff_pct_by_item(price_results)
    l2_gated_docs = _l2_gated_ap_docs(items, ap_lines or [], po_lines or [], cfg=cfg)

    payloads = [
        _decision_payload(
            item,
            price_failed=(item.ap_no, item.item_code) in failed_keys,
            price_diff_pct=diff_pct_by_key.get((item.ap_no, item.item_code)),
            l2_gated=(item.classification == _L2_ELIGIBLE_CLASS and item.ap_no in l2_gated_docs),
        )
        for item in items
    ]

    l3_suggested_pass = [p for p in payloads if p["status"] == "l3_suggested_pass"]
    needs_review = [p for p in payloads if p["status"] == "needs_review"]
    l2_self_resolved = [p for p in payloads if p["status"] == "l2_self_resolved"]
    by_class = dict(Counter(p["classification"] for p in payloads))
    price_check_alerts = [p for p in payloads if p["price_check_failed"]]

    orphaned = [
        {"inv_no": inv.inv_no, "ap_no": inv.ap_no, "item_code": inv.item_code}
        for inv in orphaned_invoices
    ]

    report = {
        "scenario": "FI2",
        "period": period,
        "disclaimer": DISCLAIMER,
        "automation_level": "L3",
        "rule_version": cfg.RULE_VERSION,
        "data_sources": data_sources,
        "items": payloads,
        "needs_review": needs_review,
        "l3_suggested_pass": l3_suggested_pass,
        "l2_self_resolved": l2_self_resolved,
        "orphaned_invoices": orphaned,
        "price_check_alerts": price_check_alerts,
        "summary": {
            "total": len(payloads),
            "l3_suggested_pass": len(l3_suggested_pass),
            "l2_self_resolved": len(l2_self_resolved),
            "needs_review": len(needs_review),
            "orphaned_invoices": len(orphaned),
            "price_check_alerts": len(price_check_alerts),
            "by_classification": by_class,
        },
    }

    # 全链审计：每料品匹配判定 append-only 留痕（差异比例为主，金额绝对值不落）
    if audit is not None:
        for payload in payloads:
            content_hash = hashlib.sha256(
                json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()
            audit.record(AuditEvent(
                scenario="FI2",
                action="item_match",
                evaluator=evaluator,
                automation_level="L3",
                decision=payload,
                data_sources=data_sources,
                content_hash=content_hash,
            ))

    return report
