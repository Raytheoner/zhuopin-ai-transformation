"""料品汇总归集匹配引擎（design D10/D11，spec: fi2-match-engine，v3 口径修正 2026-07-09）。

沿 `(ap_no, item_code)` 双向聚合 AP 明细行 vs INV 明细行——AP 侧同料品多行求和
（数量/未税金额/税额），INV 侧同料品多行求和（同）——一次聚合天然吸收 AP↔INV 的
多对一/一对多/多对多，逐行比对不再成立（v1 的逐 PO 行四维比对已废弃，见 design D11）。

迭代方向以 **AP 驱动**（遍历 AP 侧聚合键，核验 INV 侧是否有支撑）——AP 是"即将触发
付款"的一方，是需要被验证有无凭证支撑的对象，对应 v1 D3"以发票为迭代驱动、核验 GRN
是否支撑"的精神（新架构下"付款请求方"从 Invoice 换成 AP，"凭证方"从 GRN 换成 Invoice）。

判定优先级（design D11，命中即停）：① 无发票支撑（原"无 GR 支撑"改名）→ ② 明细错位
→ ③ 数量/未税金额/税额任一维度超容差 → ④ 仅未税金额差在尾差容差内 → ⑤ 完全匹配。
容差量级从 config 读取（唐燕萍 R1-R7 定稿真值，design D14；只换配置，不改本文件判定
顺序/算法结构）。

聚合 key 比对前先对 `item_code` 做归一化预处理（`item_normalize.normalize_item_code`，
design D14）：AP/INV 双方书写差异（空格/全半角/括号/"-"与"/"）视作同一料品，输出仍展示
原始（未归一化）item_code，不影响报告/审计可读性。

调用方 MUST 先用 feed_source.partition_invoices 过滤掉孤立发票（挂载的 ap_no 在 AP
明细行中找不到），本模块假设传入的 invoice_rows 均可在 ap_lines 中找到锚点。
"""
from __future__ import annotations

from typing import Optional

from . import config as _config
from .item_normalize import normalize_item_code
from .models import APLine, InvoiceLine, ItemMatch

_ROUND = 6


def _qty_in_tolerance(diff: float, diff_pct: Optional[float], cfg) -> bool:
    """数量容差：±pct 或 ±N 个，两者取宽松者（R1 真值默认两者均为 0，即精确匹配）。"""
    within_abs = abs(diff) <= cfg.QTY_TOLERANCE_ABS
    within_pct = diff_pct is not None and abs(diff_pct) <= cfg.QTY_TOLERANCE_PCT
    return within_abs or within_pct


def _amount_in_tolerance(diff: float, diff_pct: Optional[float], cfg) -> bool:
    """未税金额容差：±绝对值 或 ±比例，两者取宽松者（R1"比例口径备用：未税 ≤0.5%"）。"""
    within_abs = abs(diff) <= cfg.AMOUNT_TAIL_TOLERANCE
    within_pct = diff_pct is not None and abs(diff_pct) <= cfg.UNTAXED_AMOUNT_TOLERANCE_PCT
    return within_abs or within_pct


def build_item_matches(
    ap_lines: list[APLine],
    invoice_rows: list[InvoiceLine],
) -> list[ItemMatch]:
    """按 `(ap_no, item_code)` 双向聚合 AP/Invoice，算原始三维差异（不含容差判定/分类）。

    invoice_rows 中每个 `ap_no` MUST 能在 ap_lines 找到对应应付单
    （调用方需先用 feed_source.partition_invoices 过滤孤立发票）。
    """
    ap_nos = {a.ap_no for a in ap_lines}

    ap_qty: dict[tuple[str, str], float] = {}
    ap_untaxed: dict[tuple[str, str], float] = {}
    ap_tax: dict[tuple[str, str], float] = {}
    display_code: dict[tuple[str, str], str] = {}
    for a in ap_lines:
        key = (a.ap_no, normalize_item_code(a.item_code))
        display_code.setdefault(key, a.item_code)
        ap_qty[key] = ap_qty.get(key, 0.0) + float(a.qty)
        ap_untaxed[key] = ap_untaxed.get(key, 0.0) + float(a.untaxed_amount)
        ap_tax[key] = ap_tax.get(key, 0.0) + float(a.tax_amount)

    inv_qty: dict[tuple[str, str], float] = {}
    inv_untaxed: dict[tuple[str, str], float] = {}
    inv_tax: dict[tuple[str, str], float] = {}
    for i in invoice_rows:
        if i.ap_no not in ap_nos:
            raise ValueError(
                f"发票 {i.inv_no!r} 挂载的 ap_no={i.ap_no!r} 无对应 AP 单——"
                "调用方须先用 feed_source.partition_invoices 过滤孤立发票"
            )
        key = (i.ap_no, normalize_item_code(i.item_code))
        inv_qty[key] = inv_qty.get(key, 0.0) + float(i.inv_qty)
        inv_untaxed[key] = inv_untaxed.get(key, 0.0) + float(i.untaxed_amount)
        inv_tax[key] = inv_tax.get(key, 0.0) + float(i.tax_amount)

    results: list[ItemMatch] = []
    for key in sorted(ap_qty):
        ap_no, _norm_code = key
        item_code = display_code[key]
        has_invoice = key in inv_qty

        ap_u = round(ap_untaxed[key], _ROUND)
        ap_t = round(ap_tax[key], _ROUND)
        ap_tax_rate = round(ap_t / ap_u, _ROUND) if ap_u else 0.0

        if not has_invoice:
            results.append(ItemMatch(
                ap_no=ap_no, item_code=item_code, has_invoice=False,
                qty_diff=None, qty_diff_pct=None,
                untaxed_amount_diff=None, untaxed_amount_diff_pct=None,
                tax_amount_diff=None, tax_amount_diff_pct=None,
                ap_tax_rate=ap_tax_rate,
            ))
            continue

        ap_q = round(ap_qty[key], _ROUND)

        qty_diff = round(inv_qty[key] - ap_q, _ROUND)
        qty_diff_pct = round(qty_diff / ap_q, _ROUND) if ap_q else None
        untaxed_diff = round(inv_untaxed[key] - ap_u, _ROUND)
        untaxed_diff_pct = round(untaxed_diff / ap_u, _ROUND) if ap_u else None
        tax_diff = round(inv_tax[key] - ap_t, _ROUND)
        tax_diff_pct = round(tax_diff / ap_t, _ROUND) if ap_t else None

        results.append(ItemMatch(
            ap_no=ap_no, item_code=item_code, has_invoice=True,
            qty_diff=qty_diff, qty_diff_pct=qty_diff_pct,
            untaxed_amount_diff=untaxed_diff, untaxed_amount_diff_pct=untaxed_diff_pct,
            tax_amount_diff=tax_diff, tax_amount_diff_pct=tax_diff_pct,
            ap_tax_rate=ap_tax_rate,
        ))
    return results


def detect_misaligned_items(items: list[ItemMatch], *, cfg=_config) -> set[tuple[str, str]]:
    """"明细错位"跨料品检测（design D11 核心算法，v3：粒度从 PO 行改料品）。

    同一 ap_no 下，若存在 ≥2 个料品的未税金额差异同时超出尾差容差、且方向相反
    （一多一少），且该 ap_no 下所有料品未税金额差异总和在 AP 级容差内 —— 判定这些
    料品为"明细错位"。单料品超容差、或找不到方向相反的配对料品时，MUST NOT 判为
    明细错位（避免假阳性）。
    """
    misaligned: set[tuple[str, str]] = set()
    by_ap: dict[str, list[ItemMatch]] = {}
    for item in items:
        by_ap.setdefault(item.ap_no, []).append(item)

    for ap_no, ap_items in by_ap.items():
        over_tolerance = [
            it for it in ap_items
            if it.has_invoice and it.untaxed_amount_diff is not None
            and abs(it.untaxed_amount_diff) > cfg.AMOUNT_TAIL_TOLERANCE
        ]
        positives = [it for it in over_tolerance if it.untaxed_amount_diff > 0]
        negatives = [it for it in over_tolerance if it.untaxed_amount_diff < 0]
        if not positives or not negatives:
            continue  # 无方向相反的配对料品，不判错位（避免单料品超容差被误判）

        ap_total_diff = sum(
            it.untaxed_amount_diff for it in ap_items if it.untaxed_amount_diff is not None
        )
        if abs(ap_total_diff) <= cfg.AP_LEVEL_AMOUNT_TOLERANCE:
            for it in positives + negatives:
                misaligned.add((it.ap_no, it.item_code))
    return misaligned


def assign_category(item: ItemMatch, *, is_misaligned: bool, cfg=_config) -> str:
    """判定优先级：无发票支撑 > 明细错位 > 数量/金额不符 > 金额微差 > 完全匹配。"""
    if not item.has_invoice:
        return "无发票支撑"
    if is_misaligned:
        return "明细错位"

    qty_ok = item.qty_diff == 0 or _qty_in_tolerance(item.qty_diff, item.qty_diff_pct, cfg)
    # R1"税额随税率"：容差不是独立固定值，按该料品 AP 侧有效税率动态换算（design D14）
    tax_tolerance = cfg.AMOUNT_TAIL_TOLERANCE * item.ap_tax_rate
    tax_ok = item.tax_amount_diff == 0 or abs(item.tax_amount_diff) <= tax_tolerance
    dims_ok = qty_ok and tax_ok

    if not dims_ok:
        return "数量金额不符"

    if item.untaxed_amount_diff == 0:
        return "完全匹配"
    if _amount_in_tolerance(item.untaxed_amount_diff, item.untaxed_amount_diff_pct, cfg):
        return "金额微差"
    return "数量金额不符"
