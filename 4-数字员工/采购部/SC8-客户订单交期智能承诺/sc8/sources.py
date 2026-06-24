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
                     limit: int | None = None, audit=None,
                     ops_webhook_url: str | None = None,
                     status: str | None = None, date_from: str | None = None,
                     date_to: str | None = None) -> list[SalesOrder]:
    """从 FO API 拉真实预测订单 → SalesOrder（计划出货日作 required_date）。

    status：接口状态过滤（"2"=已审核，剔除草稿/关闭；None=不过滤）。
    date_from/date_to：按 ShipPlanDate 区间过滤（None=不限）。
    limit：小样本验证时只取前 N 条（按订单行，不放量）。
    FO 不可达时：先发内部运维告警（audit + 企微内部群，见 fo_health），**再 re-raise**——
    fail-loud，绝不静默回退 mock（红线）。audit/ops_webhook_url 缺省则分别不留痕/不推送。
    """
    try:
        fos = load_forecast_orders_from_api(
            api_base, audit=audit, status=status,
            date_from=date_from, date_to=date_to)
    except Exception as e:
        from .fo_health import alert_fo_unreachable
        alert_fo_unreachable(e, api_base=api_base or "",
                             audit=audit, webhook_url=ops_webhook_url)
        raise   # fail-loud：告警后仍抛，不回退 mock
    orders = fo_to_sales_orders(fos)
    return orders[:limit] if limit else orders


def load_real_bom(product_ids: list[str], *, max_depth: int = 1,
                  audit=None) -> list:
    """从 U9C BOM/Query 拉真实直接子件（凭据从环境/SecretsProvider 注入）。

    B1：`get_bom_for_products` 现返回 (rows, failed_ids)——部分失败的料号清单经
    UserWarning 暴露（残缺 BOM 不静默通过，下游可据此判断是否阻断对客承诺）。
    B4：注入 ConnectorAudit（缺省 None；生产应传入 access-trace sink）。
    """
    import warnings

    from zhuopin_platform.shared_tools.erp_connector.connector import ZpConnector
    zp = ZpConnector.from_env(audit=audit)
    rows, failed_ids = zp.get_bom_for_products(
        list(dict.fromkeys(product_ids)), max_depth=max_depth)
    if failed_ids:
        warnings.warn(
            f"BOM 部分拉取失败 {failed_ids}：齐套可能残缺，对客承诺前须人工核对",
            UserWarning, stacklevel=2,
        )
    return rows


def _extract_board_po_map(board: list, materials: set[str] | None):
    """从供应计划看板原始记录中提取分层取数所需的两张映射。

    看板真实结构（2026-06-18 实测）：record{innerVendorCode, productCode,
    itemList[]{boardDate, poLineList[]{poErpNo}}}。**PO 字段是 `poErpNo`**
    （非历史代码里找的 `pdrNo`）。

    Returns:
        (mat_pairs, mat_board)
        mat_pairs: {material → set((poErpNo, vendor))}  —— /purchase/answer 权威源的入参
        mat_board: {material → 最早 boardDate}            —— 看板辅助日期
    """
    mat_pairs: dict[str, set[tuple[str, str]]] = {}
    mat_board: dict[str, str] = {}
    for rec in board:
        material = str(rec.get("productCode") or "")
        if not material or (materials is not None and material not in materials):
            continue
        vendor = str(rec.get("innerVendorCode") or "")
        for item in (rec.get("itemList") or []):
            bdate = ""
            raw_bd = item.get("boardDate")
            if raw_bd is not None:
                s = str(raw_bd)
                bdate = (date.fromtimestamp(int(s) // (1000 if len(s) > 10 else 1)).isoformat()
                         if s.isdigit() else s[:10])
            if bdate and (material not in mat_board or bdate < mat_board[material]):
                mat_board[material] = bdate
            for po in (item.get("poLineList") or []):
                pe = str(po.get("poErpNo") or "")
                if pe and vendor:
                    mat_pairs.setdefault(material, set()).add((pe, vendor))
    return mat_pairs, mat_board


def load_srm_deliveries(mode: str, *, start: str | None = None,
                        end: str | None = None, audit=None,
                        materials: set[str] | None = None,
                        connector=None) -> list:
    """SRM 承诺交付记录（分层取数，SOP §4.6）。

    mode != "real" → 返回空（降级：所有物料走无反馈启发式、低置信）。
    mode == "real" → **分层取数**：
      ① 主源 `/purchase/answer`（按 PO+vendor 的供应商权威承诺交期 vExpectedDate）；
      ② 辅助：供应计划看板 boardDate（补窗口内、无答交 PO 的子件）；
      ③ 兜底：两者皆无 → 不产生记录 → 上游走无反馈 +30 启发式（v0 不变）。
    合并优先级 answer > board；同物料多 PO/多看板行取**最早**承诺日（与引擎 srm_index 一致）。

    materials：仅对这些料号取数（BOM 直接子件），**显著减少 /purchase/answer 调用**
               （携客云限流 1 req/30s）；None=不过滤（全看板，慎用）。
    connector：注入 XkySrmConnector（测试用）；None 时 from_env。
    B4：注入 ConnectorAudit（缺省 None；生产应传 access-trace sink）。
    """
    if mode != "real":
        return []
    from zhuopin_platform.shared_tools.models import SrmDeliveryOrder
    if connector is None:
        from zhuopin_platform.shared_tools.srm_connector.connector import XkySrmConnector
        connector = XkySrmConnector.from_env(audit=audit)
    s = start or date.today().isoformat()
    e = end or (date.today() + timedelta(days=60)).isoformat()

    board = connector.get_receive_board(s, e)
    mat_pairs, mat_board = _extract_board_po_map(board, materials)

    # ① 主源：对 distinct (PO, vendor) 查 /purchase/answer 权威承诺交期
    distinct_pairs = sorted({pv for pairs in mat_pairs.values() for pv in pairs})
    confirmed: dict[str, str] = {}
    if distinct_pairs:
        confirmed, _failed = connector.get_confirmed_dates(distinct_pairs)

    # ③ 合并 material → 承诺交期（answer 优先，取最早）
    out: list = []
    for material in sorted(set(mat_pairs) | set(mat_board)):
        auth_dates = [confirmed[po] for (po, _v) in sorted(mat_pairs.get(material, set()))
                      if po in confirmed]
        if auth_dates:
            committed, src_status = min(auth_dates), "confirmed"     # 权威
        elif mat_board.get(material):
            committed, src_status = mat_board[material], "planned"   # 看板辅助
        else:
            continue                                                 # 兜底：无记录→无反馈启发式
        out.append(SrmDeliveryOrder(
            delivery_id=f"SRM-{material}", demand_id="",
            supplier_id="", material_id=material,
            qty_committed=0, committed_date=committed, status=src_status,
        ))
    return out
