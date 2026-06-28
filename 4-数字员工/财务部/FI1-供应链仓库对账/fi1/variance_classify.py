"""差异分类（数据驱动规则注册表，design D5）。

把对账差异映射为分类档（损耗溢短/超损/来料短缺/管理差异），并按 L2 阈值标是否需人工。
**规则即数据**：分类档/严重度/触发条件由注册表（Rule 列表）维护，阈值取自 config（单一可信源），
分类引擎只按注册表首条命中判定，不把分类标准写死在分支里。临时口径占位，对接人 7/31 定稿替换。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from . import config as _config
from .models import ComponentReconcile


@dataclass(frozen=True)
class Rule:
    """一条分类规则。matches/needs_review 为对 ComponentReconcile 的纯谓词。"""
    id: str
    classification: str
    severity: str
    matches: Callable[[ComponentReconcile], bool]
    needs_review: Callable[[ComponentReconcile], bool]


def build_registry(cfg=_config) -> list[Rule]:
    """构造规则注册表（顺序敏感，首条命中即判定）。阈值从 cfg 注入。"""
    def _overloss_pct(c: ComponentReconcile) -> float:
        return (c.total_variance - c.standard_loss) / c.theoretical_net if c.theoretical_net else 1.0

    return [
        # 1) 无理论基准 / BOM 残缺 → 管理差异·待核（最高优先级）
        Rule("R-NB", "管理差异·无理论基准待核", "高",
             matches=lambda c: c.bom_incomplete or c.theoretical_net == 0,
             needs_review=lambda c: True),
        # 2) 负向差异（实际 < 理论净）→ 来料短缺
        Rule("R-SHORT", "来料短缺", "高",
             matches=lambda c: c.total_variance < 0,
             needs_review=lambda c: c.variance_pct is not None
                                    and abs(c.variance_pct) > cfg.L2_SHORTAGE_PCT),
        # 3) 正向且在标准损耗内 → 损耗溢短·标准内（正常）
        Rule("R-STDLOSS", "损耗溢短·标准内", "低",
             matches=lambda c: c.total_variance <= c.standard_loss,
             needs_review=lambda c: False),
        # 4) 正向且超出标准损耗 → 超损
        Rule("R-OVER", "超损", "高",
             matches=lambda c: c.total_variance > c.standard_loss,
             needs_review=lambda c: _overloss_pct(c) > cfg.L2_OVERLOSS_PCT),
    ]


def classify(c: ComponentReconcile, cfg=_config) -> ComponentReconcile:
    """按注册表首条命中给 c 填分类字段，返回 c（原地填充）。"""
    for rule in build_registry(cfg):
        if rule.matches(c):
            c.classification = rule.classification
            c.severity = rule.severity
            c.needs_review = bool(rule.needs_review(c))
            c.rule_id = rule.id
            return c
    # 理论上不可达（R-STDLOSS + R-OVER 覆盖所有非负差异）；兜底转人工
    c.classification = "未分类·待核"
    c.severity = "高"
    c.needs_review = True
    c.rule_id = "R-NONE"
    return c


def classify_all(components: list[ComponentReconcile], cfg=_config) -> list[ComponentReconcile]:
    """对一组对账结果逐条分类。"""
    return [classify(c, cfg) for c in components]


def rule_version(cfg=_config) -> str:
    return cfg.RULE_VERSION
