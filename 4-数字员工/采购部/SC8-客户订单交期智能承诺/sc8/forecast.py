"""交付日预测核心引擎（收割 + SC8 核心增量：置信度 D1 + 启发式 D2/D3）。

收割代码（supplychain delivery_forecast）只算到"给定 SMT 完工日 → 交付日 + 三色风险"，
**没有** 门禁文档要求的置信度与启发式补全。本模块补齐这两块：

  1. 物料到货估算（关键路径）：成品齐套日 = 全部直接子件最晚到货日。
     - 有 SRM 承诺交期 → 用承诺日；
     - 无反馈物料 → 需求日 + NO_FEEDBACK_LEAD_DAYS（标低置信）。
  2. 委外加工（D3）：is_outsourced → 完工估算 + OUTSOURCE_EXTRA_DAYS（标低置信）。
  3. 二级置信度（D1，与三色风险正交）：
       高 = 有 BOM 且全部直接子件有 SRM 承诺交期 且 非委外；
       低 = 含任一无反馈物料 / 委外估算 / 无法排产。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from . import config
from .config import ForecastParams
from .models import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    DeliveryForecast,
    SalesOrder,
)


@dataclass
class MaterialArrivals:
    """某成品的物料到货估算结果（关键路径 + 无反馈追踪）。"""
    arrivals:              dict[str, date]        # material_id -> 估算到货日
    no_feedback_materials: list[str] = field(default_factory=list)  # 无 SRM 承诺交期的物料
    bottleneck_material:   str | None = None      # 关键路径瓶颈物料（最晚到货）
    has_bom:               bool = False           # 是否有 BOM 直接子件


def estimate_material_arrivals(
    product_id: str,
    bom: list,                 # list[BomRow]（平台 models）
    srm_deliveries: list,      # list[SrmDeliveryOrder]（平台 models，含 committed_date）
    demand_date: date,         # 该成品需求日（无反馈启发式的基准日）
    params: ForecastParams | None = None,
) -> MaterialArrivals:
    """按 BOM 直接子件 + SRM 承诺交期估算各物料到货日（关键路径齐套）。

    无 SRM 承诺交期的物料 → 需求日 + no_feedback_lead_days（启发式，标无反馈）。
    """
    p = params or config.default_params()

    # BOM 取该成品的直接子件（level=1）
    components = [r.component_id for r in bom
                 if r.product_id == product_id and r.level == 1]
    if not components:
        return MaterialArrivals(arrivals={}, has_bom=False)

    # SRM 物料 → 最早承诺交期 索引（同物料多条交付取最早）
    srm_index: dict[str, date] = {}
    for d in srm_deliveries:
        if not getattr(d, "committed_date", ""):
            continue
        committed = date.fromisoformat(d.committed_date)
        if d.material_id not in srm_index or committed < srm_index[d.material_id]:
            srm_index[d.material_id] = committed

    arrivals: dict[str, date] = {}
    no_feedback: list[str] = []
    for mid in components:
        if mid in srm_index:
            arrivals[mid] = srm_index[mid]
        else:
            # 无反馈启发式：需求日 + N 天（低置信兜底）
            arrivals[mid] = demand_date + timedelta(days=p.no_feedback_lead_days)
            no_feedback.append(mid)

    # 关键路径瓶颈物料 = 最晚到货
    bottleneck = max(arrivals, key=lambda m: arrivals[m]) if arrivals else None
    return MaterialArrivals(
        arrivals=arrivals,
        no_feedback_materials=no_feedback,
        bottleneck_material=bottleneck,
        has_bom=True,
    )


def _assess_confidence(mat: MaterialArrivals, outsourced: bool, schedulable: bool) -> tuple[str, str]:
    """二级置信度判定（D1，与三色风险正交）。返回 (置信度, 依据)。"""
    if not schedulable:
        return CONFIDENCE_LOW, "无法排产（无 BOM/工时或物料未到齐），按低置信兜底"
    if not mat.has_bom:
        return CONFIDENCE_LOW, "无 BOM 直接子件数据，无法确认齐套，低置信"
    if mat.no_feedback_materials:
        return CONFIDENCE_LOW, f"含无 SRM 承诺交期物料（{','.join(mat.no_feedback_materials)}），走 +{config.NO_FEEDBACK_LEAD_DAYS} 天估算"
    if outsourced:
        return CONFIDENCE_LOW, f"含委外加工估算（+{config.OUTSOURCE_EXTRA_DAYS} 天），低置信"
    return CONFIDENCE_HIGH, "全部直接子件均有 SRM 供应商承诺交期，且非委外"


def forecast_for_order(
    so: SalesOrder,
    mat: MaterialArrivals,
    lead_time_map: dict[str, int],
    params: ForecastParams | None = None,
    outsourced: bool = False,
) -> DeliveryForecast:
    """对单张销售订单行生成交付日预测（含置信度/瓶颈物料/参数版本）。

    完工日 = 齐料日(关键路径) + SMT 工时 [+ 委外附加工期]；预测交付日 = 完工日 + 物流天数。
    风险（三色，vs 客户目标日）与置信度（高/低，对预测确定性）**正交**输出。
    """
    p = params or config.default_params()
    target = date.fromisoformat(so.required_date)

    # ── 排产：齐料日 + SMT 工时；无工时或无物料 → 无法排产 ──────────────────────
    schedulable = (so.item_code in lead_time_map) and bool(mat.arrivals)
    if not schedulable:
        confidence, reason = _assess_confidence(mat, outsourced, schedulable=False)
        return DeliveryForecast(
            so_id=so.so_id, product_id=so.item_code,
            customer_id=so.customer_id, customer_name=so.customer_name,
            target_date=target, smt_complete_date=None, logistics_days=p.logistics_days,
            forecast_date=None, delay_days=None, risk_level="🔴",
            bottleneck="物料未齐套或无工时配置，无法确定 SMT 排产日期",
            confidence=confidence, confidence_reason=reason,
            bottleneck_material=mat.bottleneck_material, param_version=p.param_version,
        )

    kit_date = max(mat.arrivals.values())                       # 齐料日（关键路径）
    smt_complete = kit_date + timedelta(days=lead_time_map[so.item_code])
    if outsourced:                                              # D3 委外附加工期
        smt_complete = smt_complete + timedelta(days=p.outsource_extra_days)

    forecast_date = smt_complete + timedelta(days=p.logistics_days)
    delay_days = (forecast_date - target).days

    # 三色风险（vs 客户目标日，正交于置信度）
    if delay_days <= 0:
        risk, btxt = "🟢", "按期或提前"
    elif delay_days <= 3:
        risk, btxt = "🟡", f"预计延期 {delay_days} 天，请确认是否可提前备料或加快 SMT 排产"
    else:
        risk, btxt = "🔴", f"预计延期 {delay_days} 天，需紧急协调物料到货或 SMT 插单"

    confidence, reason = _assess_confidence(mat, outsourced, schedulable=True)
    bottleneck_txt = btxt
    if mat.bottleneck_material:
        bottleneck_txt = f"{btxt}（瓶颈物料 {mat.bottleneck_material} 齐料日 {kit_date.isoformat()}）"

    return DeliveryForecast(
        so_id=so.so_id, product_id=so.item_code,
        customer_id=so.customer_id, customer_name=so.customer_name,
        target_date=target, smt_complete_date=smt_complete, logistics_days=p.logistics_days,
        forecast_date=forecast_date, delay_days=delay_days, risk_level=risk,
        bottleneck=bottleneck_txt,
        confidence=confidence, confidence_reason=reason,
        bottleneck_material=mat.bottleneck_material, param_version=p.param_version,
    )
