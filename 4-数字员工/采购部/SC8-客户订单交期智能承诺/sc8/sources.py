"""数据源解析层（design D2）—— mock→真实切换点集中于此。

切换点性质：`pipeline.compute_forecasts` 是纯依赖注入，真实化只改**加载层**。
本模块封装真实连接器的拉取 + 审计按源标记，预测/门禁逻辑零改。

本期（部分切换 D1）：
  · 订单 FO 真实（携客云 OpenAPI 不影响 FO）；
  · BOM U9C 真实；
  · SRM 降级 mock（携客云 OpenAPI 900401 未开通）；
  · SMT 工时 lead_time 仍 mock（无工时连接器）。
异常时调用方可回退 mock（保留 mock 黄金样本回归）。
"""
from __future__ import annotations

from datetime import date, timedelta

from .loaders import fo_to_sales_orders, load_forecast_orders_from_api
from .models import SalesOrder


def build_data_sources(*, order_src: str, bom_src: str,
                       srm_src: str, lead_src: str = "mock") -> dict[str, str]:
    """组装审计用的「按源标记」字典（如实反映每路输入来自 real 还是 mock）。"""
    return {"fo": order_src, "bom": bom_src,
            "srm_committed": srm_src, "smt_lead": lead_src}


def load_real_orders(*, api_base: str | None = None,
                     limit: int | None = None) -> list[SalesOrder]:
    """从 FO API 拉真实预测订单 → SalesOrder（计划出货日作 required_date）。

    limit：小样本验证时只取前 N 条（按订单行，不放量）。
    """
    fos = load_forecast_orders_from_api(api_base)
    orders = fo_to_sales_orders(fos)
    return orders[:limit] if limit else orders


def load_real_bom(product_ids: list[str], *, max_depth: int = 1) -> list:
    """从 U9C BOM/Query 拉真实直接子件（凭据从环境/SecretsProvider 注入）。"""
    from zhuopin_platform.shared_tools.erp_connector.connector import ZpConnector
    zp = ZpConnector.from_env()
    return zp.get_bom_for_products(list(dict.fromkeys(product_ids)), max_depth=max_depth)


def load_srm_deliveries(mode: str, *, start: str | None = None,
                        end: str | None = None) -> list:
    """SRM 承诺交付记录。

    mode != "real" → 返回空（降级：所有物料走无反馈启发式、低置信，本期预期形态）。
    mode == "real" → 从携客云 SRM 看板拉（≤60 天窗口；当前被 900401 阻塞）。
    """
    if mode != "real":
        return []
    from zhuopin_platform.shared_tools.srm_connector.connector import XkySrmConnector
    srm = XkySrmConnector.from_env()
    s = start or date.today().isoformat()
    e = end or (date.today() + timedelta(days=60)).isoformat()
    return srm.get_delivery_orders(s, e)
