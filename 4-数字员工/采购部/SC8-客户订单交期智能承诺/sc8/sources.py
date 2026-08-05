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

    status：接口状态过滤（"2"=已审核；None=不过滤）——**这是单据头审核状态，恒为 2**
    （全量样本 100%，2026-07-28 真实探测证实），与"只取核准状态 FO"的行级关闭诉求
    是两回事，本参数对行级关闭**没有过滤效果**（历史遗留，保留仅为向后兼容既有调用）。

    ✅ **行级关闭过滤已实现（队列 #173，#19 根治，2026-08-03）**：`load_forecast_orders_from_api`
    → `parse_forecast_order_rows` 现按行级 `LineStatus` 剔除已关闭行（IT 2026-07-30 已在
    `/zp/api/ForecastOrder/Query` 补齐该字段，取自 `SM_ForecastOrderLine.Status`，
    2=核准/3=关闭；已用真实单号 `FO2026070001` 行60 `S02Y.0120`/行230 `S02Y.0166`
    验证 `LineStatus=3` 与 U9C 界面"关闭"一致）——姚祖怡"只取核准状态 FO"的诉求已解锁，
    本函数无需额外改动即自动生效（过滤发生在 `load_forecast_orders_from_api` 内部）。
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


# 交货方式（队列 #211，姚祖怡 07-31 权威判定）：供应计划看板每条 record 自带
# `receiveType`，2026-08-03 真实探测确认取值语义——
#   receiveType=2：按排程交货（有 scheduleBatch/排程计划编号，poLineList 恒空）
#   receiveType=1：按订单交货（挂 poErpNo，无 scheduleBatch）
# 真实复现 R01B.0754 案例（姚祖怡举证的错误答交 500/2026-08-07）：命中的正是
# receiveType=1（按订单交货）那条记录；同料号同时存在的 receiveType=2（按排程
# 交货）记录才是姚祖怡指定的权威口径来源。此前 `_extract_board_commitments`
# 未按 receiveType 筛选，两种交货方式的记录被一并计入答交数量，是本次偏差主因。
_RECEIVE_TYPE_SCHEDULED = 2   # 按排程交货（唯一权威口径，姚祖怡 07-31 指定）


def _extract_board_commitments(
    board: list, materials: set[str] | None
) -> dict[str, list[tuple[date, float]]]:
    """从供应计划看板提取逐笔 (承诺日期, 承诺数量) 记录（B2 周期累计供需匹配用）。

    与 `_extract_board_po_map` 不同：本函数**不收窄成"最早一条"**，保留每条
    `answerQty > 0` 的记录，供 `sc8.period_match.match_period_cumulative_supply`
    逐笔累加（现状 `load_srm_deliveries` 硬编码 `qty_committed=0`，本函数是
    B2 需要的真实数量数据管线）。`answerQty <= 0`（未答交）不产生记录；
    已作废的排程明细（见 `_is_cancelled_plan`）同样不产生记录。

    交货方式筛选（队列 #211 v2，2026-08-03）：只取 `receiveType==2`（按排程交货），
    剔除 `receiveType==1`（按订单交货）的记录——姚祖怡权威判定"SRM 交付计划看板-
    交货方式只能选取『按排程交货』，不要选取『按订单交货』"。**范围仅限本函数**
    （驱动 `_component_supply_status` 的答交数量/日期⑦⑧展示与 B2 周期匹配展示），
    不影响 `_extract_board_po_map`/`load_srm_deliveries`（驱动 kit_date/gap_days/
    四色风险判定的既有口径）——未经授权不改判定逻辑，本次范围只是展示层取数源头。
    """
    out: dict[str, list[tuple[date, float]]] = {}
    for rec in board:
        material = str(rec.get("productCode") or "")
        if not material or (materials is not None and material not in materials):
            continue
        if rec.get("receiveType") != _RECEIVE_TYPE_SCHEDULED:
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


def _chunk_date_windows(
    start: date, end: date, *, max_span_days: int = 60,
) -> list[tuple[str, str]]:
    """把 `[start, end]` 切分成若干首尾相接、互不重叠的 ≤max_span_days 天窗口。

    SRM `get_receive_board` 硬性单次查询跨度 ≤60 天（超出即抛错），故任何超过
    该跨度的需求都必须拆成多次顺序查询（队列 #262）。窗口刻意不重叠（下一段
    起点 = 上一段终点 + 1 天），避免边界日期的记录被两个窗口重复命中、在下游
    累计计算里被计两次。`start > end` 返回空列表（调用方传参异常时不查）。
    """
    windows: list[tuple[str, str]] = []
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=max_span_days), end)
        windows.append((cur.isoformat(), chunk_end.isoformat()))
        cur = chunk_end + timedelta(days=1)
    return windows


def load_material_commitments(
    mode: str, *, start: str | None = None, end: str | None = None,
    materials: set[str] | None = None, connector=None,
) -> dict[str, list[tuple[date, float]]]:
    """物料逐笔承诺提取（B2，shortage-baoguan-criteria-v3，2026-07-10 会议定稿）。

    mode != "real" → 返回空（与 `load_srm_deliveries` 一致的降级语义）。
    返回 {material_id: [(承诺日期, 承诺数量), ...]}，供 `sc8.period_match`
    的周期累计供需匹配、以及 `baoguan._component_supply_status` 的"答交数量/答交
    日期累计展示"（#18-a/b，队列 #139）共用。不做"取最早/去重"，原样保留全部承诺记录。

    窗口（队列 #262，2026-08-05 根治）：`end` 缺省时不再是 `今天+60`——姚祖怡三度
    举证（含本次 `R01A.1028` 案例）证实真实确认批次常落在 60 天窗口外（真实探测
    见 `config.material_commitment_lookahead_days`），固定 60 天窗口会让"查不到"
    和"真的没有"无法区分、看板对本该有答交的物料如实展示"无"。默认改用
    `config.material_commitment_lookahead_days()`（180 天）；因 SRM 单次查询硬性
    跨度 ≤60 天，`[今天, 今天+180]` 按 `_chunk_date_windows` 拆成多段顺序查询、
    结果合并后再统一提取——**范围仅限本函数**，`load_srm_deliveries`/
    `_extract_board_po_map`（驱动 kit_date/gap_days/四色风险判定的既有口径）
    仍是各自独立的 60 天窗口，未经授权不改判定逻辑（红线不动，同 #211 v2 先例）。

    ⚠️ 与 `load_srm_deliveries` 各自独立请求 `get_receive_board`（未共享同一份响应）——
    两者在 `compute_snapshot` 里先后调用时会对携客云同一端点（1 req/30s 限流）连打
    请求，后续请求会被连接器自身的令牌桶/退避逻辑自动等待或重试（非本函数处理，
    见 XkySrmConnector.get_receive_board），不会报错，只是排队等待。刻意不做
    "预取 board 后共享"式耦合——保持与既有 `load_srm_deliveries`/`load_purchase_orders_by_material`
    一致的"各数据源独立可 monkeypatch/独立失败域"测试与降级架构，避免为省一次请求
    引入跨函数的隐式依赖。
    """
    if mode != "real":
        return {}
    if connector is None:
        from zhuopin_platform.shared_tools.srm_connector.connector import XkySrmConnector
        connector = XkySrmConnector.from_env()
    start_d = date.fromisoformat(start) if start else date.today()
    if end:
        end_d = date.fromisoformat(end)
    else:
        from . import config
        end_d = start_d + timedelta(days=config.material_commitment_lookahead_days())
    board: list = []
    for s, e in _chunk_date_windows(start_d, end_d):
        board.extend(connector.get_receive_board(s, e))
    return _extract_board_commitments(board, materials)


# 采购订单行级关闭状态（队列 #173，#139④ 根治，2026-08-03）：`PM_POLine.Status`
# 取值（IT 陈承 2026-07-30 回件）——0=开立/1=审核中/2=已审核未交清/3=自然关闭/
# 4=短缺关闭/5=超额关闭。3/4/5 三态即便数量口径（qty_ordered vs qty_received）
# 显示"仍有未清量"，ERP 判定上也已是关闭状态，不应再计入"在途"（真实案例：短缺
# 关闭/超额关闭的行 qty_received 常年不等于 qty_ordered，纯数量启发式会一直误判
# 为 partial/in_transit）。
PO_LINE_STATUS_CLOSED = frozenset({3, 4, 5})


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

    行级关闭状态过滤（队列 #173，#139④ 根治，2026-08-03）：`ZpViewPurOrder/Query`
    （本函数在途未清量的数量来源）不带行级关闭字段（2026-08-03 真实探测确认，
    27,641 行 0 命中 `LineStatus`）；真实行级关闭状态另在 `Purchase/Query` 暴露
    （`ZpConnector.get_purchase_line_status`，按 `itemCode` 批量查询，与 `materials`
    同一收窄集合），按 `(po_id, line_no)` JOIN 后剔除 `PO_LINE_STATUS_CLOSED` 三态
    的行。**365 天回溯窗口未退役**——它是数量数据（qty_ordered/qty_received）
    本身的取数范围折衷（见上），行级关闭过滤是叠加其上的正确性修正，两者互补
    非互斥；`materials` 为空/None 时（无法按料号收窄查询）跳过本步，行为与改造
    前完全一致。line_status 查询失败**单独降级**（fail-soft，与本函数其余部分
    real fail-loud 的既有约定有意区分）——它是本函数在既有数量口径之上的附加
    修正信号，其失败不应连累"仅按数量口径判定"这条改造前就存在、独立可用的
    既有能力退化。

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
    line_status: dict[tuple[str, str], int] = {}
    if materials:
        try:
            line_status = connector.get_purchase_line_status(sorted(materials))
        except Exception:
            line_status = {}   # fail-soft：仅放弃本次新增的关闭行剔除，不连累既有数量口径
    out: dict[str, float] = {}
    for po in orders:
        if po.status not in ("in_transit", "partial"):
            continue
        if materials is not None and po.material_id not in materials:
            continue
        if line_status.get((po.po_id, po.line_no)) in PO_LINE_STATUS_CLOSED:
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
