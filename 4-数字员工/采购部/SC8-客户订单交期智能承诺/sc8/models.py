"""SC8 场景层业务模型（design D1/Q1：留 SC8，不进平台底座）。

- SalesOrder / ForecastOrder：收割自 supplychain data_loader（业务聚合概念，属交付域需求）。
- DeliveryForecast：收割并**扩展**——新增 confidence（二级置信度）/ confidence_reason /
  bottleneck_material（瓶颈物料）/ param_version（D2 参数版本，可复现可追溯）。

平台 ProductionPlan / SrmDemandOrder / SrmDeliveryOrder 从底座 import，不在此重建。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# 置信度二级常量（design D1）。与三色风险**正交**：
#   置信度 = 对"预测日期本身"的确定性；风险 = 预测日 vs 客户目标日。
#   "有反馈但晚于目标日" = 高置信 + 红风险（不折进置信度）。
CONFIDENCE_HIGH = "高"
CONFIDENCE_LOW  = "低"


@dataclass
class SalesOrder:
    """销售订单行（收割自 supplychain）。"""
    so_id:         str        # 销售订单号，如 SO2026040068
    customer_id:   str        # 客户编码，如 Z012003
    customer_name: str        # 客户名称
    item_code:     str        # 料号，如 F02N.0040（成品/半成品）
    qty:           int        # 订货数量（本次订单行）
    required_date: str        # 客户要求交货日期 YYYY-MM-DD
    doc_type:      str = ""   # 单据类型
    item_name:     str = ""   # 品名（可选）


@dataclass
class ForecastOrder:
    """预测订单行（计划部门整合 SO + 安全库存后的正式生产计划，收割自 supplychain）。"""
    fo_id:         str   # 预测订单号，如 FO2026040001
    item_code:     str   # 料号（F/S/Y/X 成品或半成品）
    item_name:     str   # 品名
    qty:           int   # 本行计划数量
    ship_date:     str   # 计划出货日期 YYYY-MM-DD（计划部门承诺日）
    customer_id:   str   # 客户编码
    customer_name: str   # 客户名称


@dataclass
class DeliveryForecast:
    """单张销售订单行的交付日预测结果（收割 + SC8 扩展）。

    扩展字段（核心增量）：
      confidence          二级置信度（高/低，design D1）
      confidence_reason   置信度判定依据（可解释，IATF 可追溯）
      bottleneck_material 关键路径上最晚到货的物料号（瓶颈物料，None=无法排产/无 BOM）
      param_version       本次预测所用启发式参数版本（design D2，可复现）
    """
    so_id:             str
    product_id:        str
    customer_id:       str
    customer_name:     str
    target_date:       date            # 客户要求交货日
    smt_complete_date: date | None     # SMT 完工日（None=物料未到齐无法排产）
    logistics_days:    int
    forecast_date:     date | None     # 预测交付日（None=无法预测）
    delay_days:        int | None      # 延期天数（正=延期，负=提前，None=无法预测）
    risk_level:        str             # 🟢 / 🟡 / 🔴（vs 客户目标日，正交于置信度）
    bottleneck:        str             # 关键瓶颈描述（文字）
    # ── SC8 扩展 ──────────────────────────────────────────────────────────────
    confidence:          str = CONFIDENCE_LOW   # 高/低
    confidence_reason:   str = ""               # 判定依据
    bottleneck_material: str | None = None      # 关键路径瓶颈物料号
    param_version:       str = ""               # 启发式参数版本
