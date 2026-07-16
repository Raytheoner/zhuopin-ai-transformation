"""SC8 小样本真实验证 runner（任务 5，部分切换 D1）。

把数据源解析 → 预测 → 对客路由（真阻塞）串起来，跑 1-2 张真实订单：
  FO+BOM 真实、SRM 降级 mock、lead_time mock；结果**只进待审批队列、不外发客户**。
供 Paul 核对预测交付日 vs 实际承诺/到货，并抽查全链审计。

非生产入口，仅小样本验证用。放量/对客上线另议（SRM 联调通过 + 门禁 6 项全勾）。
"""
from __future__ import annotations

from pathlib import Path

from zhuopin_platform.audit import AuditLogger

from . import config
from .dispatch import route_forecast
from .gate import is_first_commitment
from .pending_queue import FilePendingQueue
from .pipeline import compute_forecasts
from .sources import (
    build_data_sources,
    load_real_bom,
    load_real_orders,
    load_srm_deliveries,
)

# 无 SMT 工时连接器 → 验证期默认工时（mock，如实标记 smt_lead=mock）
DEFAULT_SMT_LEAD_DAYS = 5


def run_small_sample(
    *,
    limit: int = 2,
    data_dir: Path | str = "data",
    smt_lead_days: int = DEFAULT_SMT_LEAD_DAYS,
) -> dict:
    """跑小样本真实验证（FO+BOM 真实、SRM mock），结果只进待审批队列。

    Returns: 汇总 dict（订单数/预测数/入队数/各预测要点），供人工核对。
    """
    mode = config.data_source_mode()          # 期望 real（由环境 SC8_DATA_SOURCE 控制）
    srm_mode = config.srm_source_mode()        # 默认 real（2026-07-15 起，900401 已解除，与同函数里 FO/BOM 的无条件真实保持一致）；可显式 SC8_SRM_SOURCE=mock 临时脱敏
    data_dir = Path(data_dir)

    # 1. 真实订单（FO API）小样本
    orders = load_real_orders(limit=limit)
    product_ids = list(dict.fromkeys(o.item_code for o in orders))

    # 2. 真实 BOM（U9C）+ SRM 降级 mock + 工时 mock
    bom = load_real_bom(product_ids)
    srm_deliveries = load_srm_deliveries(srm_mode)            # mock → []
    lead_time_map = {pid: smt_lead_days for pid in product_ids}
    data_sources = build_data_sources(
        order_src="real", bom_src="real", srm_src=srm_mode, lead_src="mock",
    )

    # 3. 审计 + 待审批队列（落场景 data/ 下，已 gitignore）
    audit = AuditLogger.jsonl(data_dir / "audit" / "sc8_real_validation.jsonl")
    queue = FilePendingQueue(data_dir / "pending_approvals.jsonl")

    # 4. 预测（全链审计按源标记）
    forecasts = compute_forecasts(
        orders, bom, srm_deliveries, lead_time_map,
        audit=audit, outsource_ids=config.outsource_ids_from_env(),
        data_sources=data_sources,
    )

    # 5. 逐条对客路由 —— 真阻塞：只入待审批队列、绝不自动外发
    queued = []
    for fc in forecasts:
        first = is_first_commitment(audit, fc.customer_name)
        outcome, item_id = route_forecast(
            fc, queue=queue, first_commitment=first, mode=mode, audit=audit,
        )
        queued.append((fc, outcome, item_id))

    return {
        "mode": mode,
        "srm_mode": srm_mode,
        "orders": len(orders),
        "products": product_ids,
        "bom_rows": len(bom),
        "forecasts": [
            {
                "so_id": fc.so_id, "product": fc.product_id,
                "customer_key": config.customer_isolation_key(fc),
                "target": fc.target_date.isoformat(),
                "forecast": fc.forecast_date.isoformat() if fc.forecast_date else None,
                "delay_days": fc.delay_days, "risk": fc.risk_level,
                "confidence": fc.confidence, "bottleneck_material": fc.bottleneck_material,
                "outcome": outcome,
            }
            for fc, outcome, _ in queued
        ],
        "pending_in_queue": len(queue.list_pending()),
    }
