"""四维匹配引擎（design D1/D3，spec: fi2-match-engine）。

沿 (po_no, line_no) 比对 PO 行 vs GRN(收货) vs Invoice(开票)：
物料编码一致性 + 数量(GRN 收货 vs Invoice 开票) + 金额(Invoice 含税金额 vs 应付=收货量×PO单价×(1+税率))
+ 税率(Invoice vs PO)。同一 PO 行多批到货/多张发票按 (po_no, line_no) 求和聚合（FIFO 明细配对为
二期细化，MVP 在聚合总量层面比对即可覆盖分批场景）。

判定优先级（design D3，命中即停）：① 无 GR 支撑 → ② 明细错位 → ③ 数量/金额不符 → ④ 金额微差 → ⑤ 完全匹配。
容差量级从 config 读取（唐燕萍定稿后只换配置，不改本文件判定顺序/算法结构）。

调用方 MUST 先用 feed_source.partition_invoices 过滤掉孤立发票（无对应 PO 行），
本模块假设传入的 invoice_rows 均可在 po_lines 中找到锚点。
"""
from __future__ import annotations

from typing import Optional

from . import config as _config
from .models import GRNLine, InvoiceLine, LineMatch, POLine

_ROUND = 6


def _qty_in_tolerance(diff: float, diff_pct: Optional[float], cfg) -> bool:
    """数量容差：±pct 或 ±N 个，两者取宽松者（任一满足即算容差内）。"""
    within_abs = abs(diff) <= cfg.QTY_TOLERANCE_ABS
    within_pct = diff_pct is not None and abs(diff_pct) <= cfg.QTY_TOLERANCE_PCT
    return within_abs or within_pct


def build_line_matches(
    po_lines: list[POLine],
    grn_rows: list[GRNLine],
    invoice_rows: list[InvoiceLine],
) -> list[LineMatch]:
    """按 (po_no, line_no) 分组聚合 GRN/Invoice，逐行算原始四维差异（不含容差判定/分类）。

    invoice_rows 中每个 (po_no, line_no) MUST 能在 po_lines 找到对应行
    （调用方需先用 feed_source.partition_invoices 过滤孤立发票）。
    """
    po_by_key = {(p.po_no, p.line_no): p for p in po_lines}

    grn_qty: dict[tuple[str, str], float] = {}
    for g in grn_rows:
        key = (g.po_no, g.line_no)
        grn_qty[key] = grn_qty.get(key, 0.0) + float(g.recv_qty)

    inv_qty: dict[tuple[str, str], float] = {}
    inv_amount: dict[tuple[str, str], float] = {}
    inv_tax_rate: dict[tuple[str, str], float] = {}
    inv_item_code: dict[tuple[str, str], str] = {}
    for i in invoice_rows:
        key = (i.po_no, i.line_no)
        inv_qty[key] = inv_qty.get(key, 0.0) + float(i.inv_qty)
        inv_amount[key] = inv_amount.get(key, 0.0) + float(i.inv_amount)
        inv_tax_rate.setdefault(key, float(i.tax_rate))
        inv_item_code.setdefault(key, i.item_code)

    results: list[LineMatch] = []
    for key in sorted(inv_qty):
        po_no, line_no = key
        po_line = po_by_key.get(key)
        if po_line is None:
            raise ValueError(
                f"发票行 {key} 无对应 PO 行——调用方须先用 feed_source.partition_invoices 过滤孤立发票"
            )
        item_code = inv_item_code.get(key, "")
        item_code_match = po_line.item_code == item_code
        has_grn = key in grn_qty

        if not has_grn:
            results.append(LineMatch(
                po_no=po_no, line_no=line_no, item_code=item_code,
                has_grn=False, has_invoice=True,
                item_code_match=item_code_match,
                qty_diff=None, qty_diff_pct=None,
                amount_diff=None, amount_diff_pct=None,
                tax_rate_match=inv_tax_rate.get(key) == po_line.tax_rate,
            ))
            continue

        recv_qty = round(grn_qty[key], _ROUND)
        qty_diff = round(inv_qty[key] - recv_qty, _ROUND)
        qty_diff_pct = round(qty_diff / recv_qty, _ROUND) if recv_qty else None
        expected_amount = round(recv_qty * po_line.unit_price * (1 + po_line.tax_rate), _ROUND)
        amount_diff = round(inv_amount[key] - expected_amount, _ROUND)
        amount_diff_pct = round(amount_diff / expected_amount, _ROUND) if expected_amount else None
        tax_rate_match = inv_tax_rate.get(key) == po_line.tax_rate

        results.append(LineMatch(
            po_no=po_no, line_no=line_no, item_code=item_code,
            has_grn=True, has_invoice=True,
            item_code_match=item_code_match,
            qty_diff=qty_diff, qty_diff_pct=qty_diff_pct,
            amount_diff=amount_diff, amount_diff_pct=amount_diff_pct,
            tax_rate_match=tax_rate_match,
        ))
    return results


def detect_misaligned_lines(lines: list[LineMatch], *, cfg=_config) -> set[tuple[str, str]]:
    """"明细错位"跨行检测（design D3 核心算法）。

    同一 po_no 下，若存在 ≥2 行金额差异同时超出尾差容差、且方向相反（一多一少），
    且该 po_no 下所有行金额差异总和在 PO 级容差内 —— 判定这些行为"明细错位"。
    单行超容差、或找不到方向相反的配对行时，MUST NOT 判为明细错位（避免假阳性）。
    """
    misaligned: set[tuple[str, str]] = set()
    by_po: dict[str, list[LineMatch]] = {}
    for line in lines:
        by_po.setdefault(line.po_no, []).append(line)

    for po_no, po_lines_group in by_po.items():
        over_tolerance = [
            l for l in po_lines_group
            if l.has_grn and l.amount_diff is not None
            and abs(l.amount_diff) > cfg.AMOUNT_TAIL_TOLERANCE
        ]
        positives = [l for l in over_tolerance if l.amount_diff > 0]
        negatives = [l for l in over_tolerance if l.amount_diff < 0]
        if not positives or not negatives:
            continue  # 无方向相反的配对行，不判错位（避免单行超容差被误判）

        po_total_diff = sum(
            l.amount_diff for l in po_lines_group if l.amount_diff is not None
        )
        if abs(po_total_diff) <= cfg.PO_LEVEL_AMOUNT_TOLERANCE:
            for l in positives + negatives:
                misaligned.add((l.po_no, l.line_no))
    return misaligned


def assign_category(line: LineMatch, *, is_misaligned: bool, cfg=_config) -> str:
    """判定优先级：无GR支撑 > 明细错位 > 数量/金额不符 > 金额微差 > 完全匹配。"""
    if not line.has_grn:
        return "无GR支撑"
    if is_misaligned:
        return "明细错位"

    qty_ok = line.qty_diff == 0 or _qty_in_tolerance(line.qty_diff, line.qty_diff_pct, cfg)
    dims_ok = qty_ok and line.item_code_match and line.tax_rate_match

    if not dims_ok:
        return "数量金额不符"

    if line.amount_diff == 0:
        return "完全匹配"
    if abs(line.amount_diff) <= cfg.AMOUNT_TAIL_TOLERANCE:
        return "金额微差"
    return "数量金额不符"
