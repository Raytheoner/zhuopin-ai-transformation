"""五类判定结果编排（design D11/D12，spec: fi2-result-classify，v3 口径修正 2026-07-09）。

编排 match_engine 的料品汇总比对 + 判定优先级 + 明细错位检测，产出带分类/状态/规则版本的
`ItemMatch` 列表。容差量级 MUST 从 config 读取，唐燕萍规则定稿后只替换 config.py + 本文件
的规则版本号，不改判定顺序/算法结构（match_engine.py 不变）。

价格超差（price_check）的合并不在本模块——本模块只产出五类判定，与 AP-PO 单价校验的
合并在 recon_report 层完成（design D12：两者独立、聚合层才汇总）。
"""
from __future__ import annotations

from . import config as _config
from .match_engine import assign_category, build_item_matches, detect_misaligned_items
from .models import APLine, InvoiceLine, ItemMatch

# 四类非完全匹配强制转人工（design D4，Paul 拍板；v3：无GR支撑→无发票支撑改名）；
# 完全匹配类标"建议通过"不强制逐笔人工
_NEEDS_REVIEW_CLASSES = {"金额微差", "明细错位", "数量金额不符", "无发票支撑"}


def _status(classification: str) -> str:
    if classification in _NEEDS_REVIEW_CLASSES:
        return "needs_review"
    return "l3_suggested_pass"


def classify_all(
    ap_lines: list[APLine],
    invoice_rows: list[InvoiceLine],
    *,
    cfg=_config,
) -> list[ItemMatch]:
    """编排料品汇总比对 + 明细错位检测 + 判定优先级，返回已分类的 `ItemMatch` 列表。

    invoice_rows MUST 已用 feed_source.partition_invoices 过滤孤立发票（挂载的 ap_no
    在 ap_lines 中找不到）。
    """
    items = build_item_matches(ap_lines, invoice_rows)
    misaligned = detect_misaligned_items(items, cfg=cfg)

    for item in items:
        classification = assign_category(
            item, is_misaligned=(item.ap_no, item.item_code) in misaligned, cfg=cfg
        )
        item.classification = classification
        item.status = _status(classification)
        item.needs_review = item.status == "needs_review"
        item.rule_version = cfg.RULE_VERSION
    return items


def rule_version(cfg=_config) -> str:
    return cfg.RULE_VERSION
