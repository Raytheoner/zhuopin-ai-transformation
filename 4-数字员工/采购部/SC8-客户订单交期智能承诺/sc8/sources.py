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

    status：接口状态过滤（"2"=已审核；None=不过滤）。
    ⚠️ **已知缺口，未解决（队列 #139 ①，2026-07-28 真实探测证实，未实现）**：
    姚祖怡诉求"只取 ERP 里状态=核准的预测订单，剔除已关闭的"——探测发现 `status`
    过滤的判据是**单据头**审核状态，恒为 2（全量样本 100%），与 U9C 预测订单
    UI 上**行级**"状态"列（可独立为"核准"或"关闭"，如实测 `FO2026070001`
    行60 `S02Y.0120`/行230 `S02Y.0166` UI 均显示"关闭"）是两回事——`status=2`
    过滤对行级关闭**完全没有过滤效果**，本函数当前**无法**实现姚祖怡的诉求。
    根因：`/zp/api/ForecastOrder/Query` 响应体没有行级状态字段（只有单据头
    `Status`，逐行同值广播）。需 IT 在该接口补一个行级"关闭/核准"状态字段，
    或提供等价查询能力，才能真正实现——不是本函数的过滤逻辑写错，是接口
    没有可用字段。**不要凭旧假设"传 status=2 即可剔除关闭"，已被证伪。**
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


def _is_cancelled_plan(item: dict) -> bool:
    """一条供应计划排程明细（itemList 元素）是否已作废（姚祖怡 07-26 V6 回件 #7）。

    姚反馈"SRM 系统供应计划排程详情中，所有'作废的订单'不取数"（她举了 4 个交付计划
    编号为例，非通用规则——按 Paul 07-27 拍板，实现为"排除全部有效未作废计划"）。
    真实看板 itemList 每项自带 `cancelFlag` 字段（2026-07 生产抓包实测确认存在此
    字段，当前样本恒为 None，尚未观测到真实作废记录，但字段已在生产 schema
    中）。请求层已传 `cancelFlag: 0`（见 XkySrmConnector.get_receive_board），
    但不能保证服务端据此完全过滤——本函数在客户端做二次防御性过滤，双保险。

    None/0/False/缺失/空串 → 有效（不过滤，向后兼容不含该字段的旧测试 fixture）；
    其余真值（1/True/"1"/"true" 等）→ 已作废，跳过。
    """
    flag = item.get("cancelFlag")
    if flag is None:
        return False
    if isinstance(flag, str):
        return flag.strip().lower() not in ("", "0", "false", "no", "n")
    return bool(flag)


def _extract_board_po_map(board: list, materials: set[str] | None):
    """从供应计划看板原始记录中提取分层取数所需的两张映射。

    看板真实结构（2026-06-18 实测）：record{innerVendorCode, productCode,
    itemList[]{boardDate, poLineList[]{poErpNo}}}。**PO 字段是 `poErpNo`**
    （非历史代码里找的 `pdrNo`）。已作废的排程明细（见 `_is_cancelled_plan`）不提取。

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
            if _is_cancelled_plan(item):
                continue
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


def _extract_board_commitments(
    board: list, materials: set[str] | None
) -> dict[str, list[tuple[date, float]]]:
    """从供应计划看板提取逐笔 (承诺日期, 承诺数量) 记录（B2 周期累计供需匹配用）。

    与 `_extract_board_po_map` 不同：本函数**不收窄成"最早一条"**，保留每条
    `answerQty > 0` 的记录，供 `sc8.period_match.match_period_cumulative_supply`
    逐笔累加（现状 `load_srm_deliveries` 硬编码 `qty_committed=0`，本函数是
    B2 需要的真实数量数据管线）。`answerQty <= 0`（未答交）不产生记录；
    已作废的排程明细（见 `_is_cancelled_plan`）同样不产生记录。
    """
    out: dict[str, list[tuple[date, float]]] = {}
    for rec in board:
        material = str(rec.get("productCode") or "")
        if not material or (materials is not None and material not in materials):
            continue
        for item in (rec.get("itemList") or []):
            if _is_cancelled_plan(item):
                continue
            answer_qty = int(item.get("answerQty") or 0)
            if answer_qty <= 0:
                continue
            s = str(item.get("boardDate") or "")
            if not s:
                continue
            bdate_str = (date.fromtimestamp(int(s) // (1000 if len(s) > 10 else 1)).isoformat()
                         if s.isdigit() else s[:10])
            out.setdefault(material, []).append((date.fromisoformat(bdate_str), float(answer_qty)))
    return out


def load_material_commitments(
    mode: str, *, start: str | None = None, end: str | None = None,
    materials: set[str] | None = None, connector=None,
) -> dict[str, list[tuple[date, float]]]:
    """物料逐笔承诺提取（B2，shortage-baoguan-criteria-v3，2026-07-10 会议定稿）。

    mode != "real" → 返回空（与 `load_srm_deliveries` 一致的降级语义）。
    返回 {material_id: [(承诺日期, 承诺数量), ...]}，供 `sc8.period_match`
    的周期累计供需匹配、以及 `baoguan._component_supply_status` 的"答交数量/答交
    日期累计展示"（#18-a/b，队列 #139）共用。不做"取最早/去重"，原样保留全部承诺记录。

    ⚠️ 与 `load_srm_deliveries` 各自独立请求 `get_receive_board`（未共享同一份响应）——
    两者在 `compute_snapshot` 里先后调用时会对携客云同一端点（1 req/30s 限流）连打
    两次请求，第二次会被连接器自身的令牌桶/退避逻辑自动等待或重试（非本函数处理，
    见 XkySrmConnector.get_receive_board），不会报错，只是多等最多约 30 秒。刻意不做
    "预取 board 后共享"式耦合——保持与既有 `load_srm_deliveries`/`load_purchase_orders_by_material`
    一致的"各数据源独立可 monkeypatch/独立失败域"测试与降级架构，避免为省一次请求
    引入跨函数的隐式依赖。
    """
    if mode != "real":
        return {}
    if connector is None:
        from zhuopin_platform.shared_tools.srm_connector.connector import XkySrmConnector
        connector = XkySrmConnector.from_env()
    s = start or date.today().isoformat()
    e = end or (date.today() + timedelta(days=60)).isoformat()
    board = connector.get_receive_board(s, e)
    return _extract_board_commitments(board, materials)


def load_purchase_orders_by_material(
    materials: set[str] | None = None, *, days: int | None = None, audit=None, connector=None,
) -> dict[str, float]:
    """按料号汇总在途采购订单未清量（PO 在途数据接入，#12/#14 共享基础，2026-07-23）。

    在途未清量 = Σ(qty_ordered − qty_received)，只统计 status 为 in_transit/partial
    的采购订单行（status=received 已全部收货，不计入"在途"）。materials 给定时只保留
    这些料号（与 load_srm_deliveries 一致的收窄口径，减少下游遍历量）；None=不过滤。

    days：回溯窗口天数；缺省 None → 取 `config.po_transit_lookback_days()`（默认 365，
    见该函数 docstring 的根因说明——#18-c，队列 #139：60 天窗口曾漏掉一张创建于
    ~266 天前、至今仍有未清量的真实在途 PO，导致对应子件误判"无未交订单"）。

    connector：注入 ZpConnector（测试用）；None 时 from_env（复用与 BOM 相同的凭据）。
    real fail-loud：连接器异常原样上抛，由调用方（compute_snapshot）决定是否降级
    （本功能为纯展示派生列，调用方对失败采用"降级为无数据"而非阻断整体重算，
    与 FO/BOM/SRM 等核心数据源的强 fail-loud 语义有意区分，见 baoguan_service 注释）。
    """
    if days is None:
        from . import config
        days = config.po_transit_lookback_days()
    if connector is None:
        from zhuopin_platform.shared_tools.erp_connector.connector import ZpConnector
        connector = ZpConnector.from_env(audit=audit)
    orders = connector.get_purchase_orders(days=days)
    out: dict[str, float] = {}
    for po in orders:
        if po.status not in ("in_transit", "partial"):
            continue
        if materials is not None and po.material_id not in materials:
            continue
        outstanding = max(float(po.qty_ordered) - float(po.qty_received), 0.0)
        if outstanding <= 0:
            continue
        out[po.material_id] = out.get(po.material_id, 0.0) + outstanding
    return out


def load_srm_deliveries(mode: str, *, start: str | None = None,
                        end: str | None = None, audit=None,
                        materials: set[str] | None = None,
                        connector=None,
                        cache_path: str | None = None,
                        ttl_sec: int = 0) -> list:
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
    cache_path/ttl_sec：firm 承诺交期缓存（提速「立即重算」）。cache_path 给定且 ttl_sec>0 时，
               firm 命中 TTL 内复用、跳过 /purchase/answer；未答交始终重查。
               缺省（cache_path=None / ttl_sec=0）= 原全量行为（测试/golden 不受影响）。
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
        if cache_path and ttl_sec > 0:
            # 增量：firm 承诺 TTL 内复用，只重查新增/未答复/过期（提速立即重算）
            from .srm_answer_cache import fetch_confirmed_cached
            confirmed, _stats = fetch_confirmed_cached(
                connector, distinct_pairs, cache_path=cache_path, ttl_sec=ttl_sec)
        else:
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
