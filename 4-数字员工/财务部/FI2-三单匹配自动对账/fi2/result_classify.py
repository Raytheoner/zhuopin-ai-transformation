"""五类判定结果编排（design D2/D3/D4，spec: fi2-result-classify）。

编排 match_engine 的四维比对 + 判定优先级 + 明细错位检测，产出带分类/状态/规则版本的
`LineMatch` 列表。容差量级 MUST 从 config 读取，唐燕萍规则定稿后只替换 config.py + 本文件
的规则版本号，不改判定顺序/算法结构（match_engine.py 不变）。
"""
from __future__ import annotations

from . import config as _config
from .match_engine import assign_category, build_line_matches, detect_misaligned_lines
from .models import GRNLine, InvoiceLine, LineMatch, POLine

# 四类非完全匹配强制转人工（design D4，Paul 拍板）；完全匹配类标"建议通过"不强制逐笔人工
_NEEDS_REVIEW_CLASSES = {"金额微差", "明细错位", "数量金额不符", "无GR支撑"}


def _status(classification: str) -> str:
    if classification in _NEEDS_REVIEW_CLASSES:
        return "needs_review"
    return "l3_suggested_pass"


def classify_all(
    po_lines: list[POLine],
    grn_rows: list[GRNLine],
    invoice_rows: list[InvoiceLine],
    *,
    cfg=_config,
) -> list[LineMatch]:
    """编排四维比对 + 明细错位检测 + 判定优先级，返回已分类的 `LineMatch` 列表。

    invoice_rows MUST 已用 feed_source.partition_invoices 过滤孤立发票（无对应 PO 行）。
    """
    lines = build_line_matches(po_lines, grn_rows, invoice_rows)
    misaligned = detect_misaligned_lines(lines, cfg=cfg)

    for line in lines:
        classification = assign_category(
            line, is_misaligned=(line.po_no, line.line_no) in misaligned, cfg=cfg
        )
        line.classification = classification
        line.status = _status(classification)
        line.needs_review = line.status == "needs_review"
        line.rule_version = cfg.RULE_VERSION
    return lines


def rule_version(cfg=_config) -> str:
    return cfg.RULE_VERSION
