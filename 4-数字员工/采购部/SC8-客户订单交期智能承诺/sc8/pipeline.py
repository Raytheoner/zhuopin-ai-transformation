"""端到端编排（收割自 supplychain run_delivery_forecast.compute_forecasts + SC8 增量）。

数据流：订单 → aggregate_demand 聚合 → 按产品估算物料到货(SRM 承诺/关键路径/启发式)
        → schedule_smt → forecast_for_order(置信度/委外/三色风险) → list[DeliveryForecast]
每条预测可写平台 audit（含置信度/参数版本/瓶颈物料/so_id，automation_level=L2）。

本批只接 mock（BOM/SRM 交付/工时均为夹具入参），无真实网络调用（spec「先 mock 后真实」）。
真实 zp ERP BOM + 携客云 SRM 切换 = 任务 N.1（6/12 后）。
"""
from __future__ import annotations

from datetime import date

from zhuopin_platform.audit import AuditEvent, AuditLogger

from . import config
from .config import ForecastParams, is_outsourced
from .forecast import estimate_material_arrivals, forecast_for_order
from .intake import aggregate_demand
from .models import DeliveryForecast, SalesOrder

SCENARIO = "SC8"
ACTION_FORECAST = "delivery_forecast"


def compute_forecasts(
    orders: list[SalesOrder],
    bom: list,                     # list[BomRow]
    srm_deliveries: list,          # list[SrmDeliveryOrder]
    lead_time_map: dict[str, int],
    params: ForecastParams | None = None,
    *,
    audit: AuditLogger | None = None,
    outsource_ids: set[str] | None = None,
    outsource_prefixes: tuple[str, ...] | None = None,
) -> list[DeliveryForecast]:
    """对一批订单计算交付日预测（纯函数 + 可选审计留痕）。"""
    p = params or config.default_params()
    if not orders:
        return []

    # Step 1：聚合为产品需求（plan.planned_date = 该产品最早需求日，作启发式基准）
    plans = aggregate_demand(orders)
    demand_date_by_product: dict[str, date] = {
        plan.product_id: date.fromisoformat(plan.planned_date) for plan in plans
    }

    # Step 2：按产品估算物料到货（关键路径 + 无反馈启发式）
    mat_by_product = {
        plan.product_id: estimate_material_arrivals(
            plan.product_id, bom, srm_deliveries,
            demand_date_by_product[plan.product_id], p,
        )
        for plan in plans
    }

    # Step 3：逐订单行生成预测（委外判定 D3）
    forecasts: list[DeliveryForecast] = []
    for so in orders:
        mat = mat_by_product.get(so.item_code)
        if mat is None:
            continue
        outsourced = is_outsourced(
            so.item_code, product_ids=outsource_ids, prefixes=outsource_prefixes
        )
        fc = forecast_for_order(so, mat, lead_time_map, p, outsourced)
        forecasts.append(fc)
        if audit is not None:
            _record_forecast(audit, fc)

    return forecasts


def _record_forecast(audit: AuditLogger, fc: DeliveryForecast) -> None:
    """预测事件写平台 audit（全链审计起点；含置信度/参数版本/瓶颈物料/so_id）。"""
    audit.record(AuditEvent(
        scenario=SCENARIO,
        action=ACTION_FORECAST,
        evaluator="",                     # 预测为系统产出，外发确认人在 approve 阶段记录
        automation_level="L2",            # 推客户属 L2（须人工确认）
        decision={
            "so_id": fc.so_id,
            "product_id": fc.product_id,
            "customer_name": fc.customer_name,
            "target_date": fc.target_date.isoformat(),
            "forecast_date": fc.forecast_date.isoformat() if fc.forecast_date else None,
            "delay_days": fc.delay_days,
            "risk_level": fc.risk_level,
            "confidence": fc.confidence,
            "confidence_reason": fc.confidence_reason,
            "bottleneck_material": fc.bottleneck_material,
            "param_version": fc.param_version,
        },
        data_sources={"bom": "mock", "srm_committed": "mock", "smt_lead": "mock"},
    ))
