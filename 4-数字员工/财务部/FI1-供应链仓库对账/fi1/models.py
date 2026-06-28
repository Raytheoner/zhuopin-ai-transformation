"""FI1 数据模型 —— 对账输入/输出记录。

输入：
  · `ProductionOutput` 成品产出（对账期完工数量，源 U9C MO.FinishedQty）。
  · `MaterialFeed` 实际投料（线体/工单领料净额，源 MOPickList/领料过账）。
  · BOM 复用平台 `zhuopin_platform.shared_tools.models.BomRow`（qty_per_unit + loss_rate=m_scrap）。
输出：
  · `ComponentReconcile` 逐子件对账结果（理论净用量/标准损耗/实际/总差异/差异率 + 分类）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProductionOutput:
    """成品产出（对账期完工数量）。"""
    product_id: str
    product_name: str
    finished_qty: float
    period: str = ""


@dataclass
class MaterialFeed:
    """子件实际投料（净额，已扣退料）。"""
    component_id: str
    component_name: str
    actual_qty: float
    unit: str = ""
    period: str = ""


@dataclass
class ComponentReconcile:
    """逐子件对账结果。

    引擎填：theoretical_net / standard_loss / actual_feed / total_variance / variance_pct / bom_incomplete。
    分类填：classification / severity / needs_review / rule_id。
    """
    component_id: str
    component_name: str
    theoretical_net: float           # 理论净用量（不含损耗）
    standard_loss: float             # 标准损耗基线 = 理论净用量 × m_scrap
    actual_feed: float               # 实际投料
    total_variance: float            # 实际 − 理论净用量
    variance_pct: Optional[float]    # 差异率；None = NA·无理论基准
    bom_incomplete: bool = False     # BOM 残缺/无理论基准 → 待人工核
    # ── 分类（variance_classify 填）──
    classification: str = ""
    severity: str = ""
    needs_review: bool = False
    rule_id: str = ""
