"""AP-PO 单价强制比对（design D12，spec: fi2-price-check，v3 新增 2026-07-09）。

堵 ERP 配票环节可手动改 AP 金额、无 PO 强制校验的控制漏洞：AP 单价相对其前置 PO 行
单价的容差比对，**独立于料品汇总五类判定**——即便某料品的五类判定结果是"完全匹配"，
只要其任一 AP 行价格超差，报告聚合层（recon_report）仍 MUST 将该料品状态强制改写为
`needs_review`（见 design D12）。

容差 R7 真值（design D14，2026-07-10 唐燕萍团队定稿）：人民币供应商统一
`config.AP_PO_PRICE_TOLERANCE_PCT`（±2%，方案二）。外币供应商过渡规则（容差内连续 2 次
同向偏移推人工抽查）与"方案一"原始外币单价+下单日汇率升级位，均因缺前置数据（供应商
清单/跨运行历史状态）本次未实现，见 config.py 注释 + design D14 future-work；本函数暂不
做折算步骤，MVP mock 假设同币种。

金额脱敏（D7 红线延伸）：`PriceCheckResult` 只留 `price_diff_pct`，不落 AP/PO 原始
单价绝对值。
"""
from __future__ import annotations

from . import config as _config
from .models import APLine, POLine, PriceCheckResult

_ROUND = 6


def check_ap_po_price(
    ap_lines: list[APLine],
    po_lines: list[POLine],
    *,
    cfg=_config,
) -> list[PriceCheckResult]:
    """逐 AP 行比对其 unit_price 相对前置 PO 行 unit_price 的偏离比例。

    AP 行找不到对应 PO 行（`(po_no, line_no)` 缺失）时，视为无法比价，MUST 判超差
    （数据完整性异常，正常流程下 AP 由配票生成、理论上必有 PO 前置）。
    """
    po_by_key = {(p.po_no, p.line_no): p for p in po_lines}
    results: list[PriceCheckResult] = []

    for ap in ap_lines:
        po = po_by_key.get((ap.po_no, ap.line_no))
        if po is None:
            results.append(PriceCheckResult(
                ap_no=ap.ap_no, po_no=ap.po_no, line_no=ap.line_no, item_code=ap.item_code,
                has_po=False, price_diff_pct=None, exceeds_tolerance=True,
            ))
            continue

        diff_pct = round((ap.unit_price - po.unit_price) / po.unit_price, _ROUND) if po.unit_price else None
        exceeds = diff_pct is not None and abs(diff_pct) > cfg.AP_PO_PRICE_TOLERANCE_PCT
        results.append(PriceCheckResult(
            ap_no=ap.ap_no, po_no=ap.po_no, line_no=ap.line_no, item_code=ap.item_code,
            has_po=True, price_diff_pct=diff_pct, exceeds_tolerance=exceeds,
        ))
    return results


def failed_item_keys(results: list[PriceCheckResult]) -> set[tuple[str, str]]:
    """归并出 `(ap_no, item_code)` 级别的价格超差标记，供 recon_report 与 ItemMatch 合并。"""
    return {(r.ap_no, r.item_code) for r in results if r.exceeds_tolerance}
