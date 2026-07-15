"""成品保供预警看板（齐套维度）—— 复用 SC8 物料到货引擎，按保供口径出看板。

与 SC8 交付承诺（forecast.forecast_for_order：齐料→SMT→物流→交付日 vs 客户目标日）不同，
本模块只看**保供/齐套维度**：成品全部直接子件最晚到货日（齐料日）vs 计划出货日，
回答"出货前料能不能齐"。不引入 SMT 工时（真实工时连接器未接），口径更窄但全用真实数据可得项。

预警机制收割自 supplychain `srm_risk_monitor` / `delivery_forecast` 三色分组：
  · 子件到货 = 携客云承诺交期（有）/ 无答复 → max(成品出货日, 今天) + NO_FEEDBACK_LEAD_DAYS；
  · 齐料日 = 全部直接子件最晚到货日（关键路径瓶颈）；
  · 缺口天数 = 齐料日 − 计划出货日；🔴>3天 / 🟡1-3天 / 🟢≤0；无 BOM/无法齐套 → 🔴。

无答复基准 max(出货日, 今天)+30（Paul 2026-06-22 定）：由本模块在调用 estimate_material_arrivals
时喂 demand_date=max(出货日,今天)，**不改 forecast 引擎默认值**，故 SC8 交付承诺黄金值不漂移。

红线：本看板为**内部保供运维**用途，不对客（CUSTOMER_OUTBOUND_ENABLED 全程关，与本模块无关）。
"""
from __future__ import annotations

import html as _html
import json as _json
from dataclasses import dataclass, field
from datetime import date

from zhuopin_platform.agents.kit_engine import explode_bom
from zhuopin_platform.shared_tools.models import ProductionPlan

from . import config
from .config import ForecastParams
from .forecast import MaterialArrivals, estimate_material_arrivals
from .models import SalesOrder
from .period_match import PeriodMatchResult, match_period_cumulative_supply

# 四色风险（2026-06-24 口径细化，Paul 定）：把"承诺缺口"从"真延期"中拆出——
#   🔴 真延期 = 有真实承诺但齐料晚于出货 >3 天（硬信号，确定的瓶颈）
#   🟠 待催   = 存在供应商未答复子件、无真实承诺可判定（信息缺口，需催答交，非确定延期）
#   🟡 偏紧   = 有真实承诺、齐料晚出货 1-3 天
#   🟢 按期   = 全部子件有承诺且齐料 ≤ 出货
# "真延期"优先级最高：即便同时有未答复子件，只要有确定承诺已晚，即判 🔴。
RISK_RED = "🔴"
RISK_GAP = "🟠"
RISK_YELLOW = "🟡"
RISK_GREEN = "🟢"


@dataclass
class BaoguanRow:
    """一条成品保供预警结果（成品行粒度）。"""
    so_id:          str
    product_id:     str
    product_name:   str
    customer_name:  str
    qty:            int
    ship_date:      date                       # 计划出货日（保供目标日）
    kit_date:       date | None                # 齐料日（全子件最晚到货，含无答复+30 估算）；无 BOM→None
    gap_days:       int | None                 # 缺口天数 = 齐料日 − 出货日（含估算）；无 BOM→None
    risk:           str                        # 🔴/🟠/🟡/🟢
    bottleneck_material: str | None            # 关键路径瓶颈子件
    no_feedback_materials: list[str] = field(default_factory=list)  # 供应商未答复子件
    component_count: int = 0                   # 直接子件总数
    has_bom:        bool = False
    action:         str = ""                   # 建议动作
    # 仅基于"有真实承诺"子件的齐料/缺口（剔除无答复估算）——用于区分真延期 vs 待催
    confirmed_kit_date: date | None = None     # 确定承诺子件的最晚到货；无确定承诺→None
    confirmed_gap_days: int | None = None      # 确定齐料 − 出货；无确定承诺→None
    # B2 周期累计供需匹配（shortage-baoguan-criteria-v3，2026-07-10 会议定稿）：
    # {子件料号: PeriodMatchResult}；纯附加信息，不影响上方 kit_date/gap_days/risk/action
    # 的既有语义。material_commitments 未传（默认）时恒为空字典，零漂移。
    period_match: dict[str, PeriodMatchResult] = field(default_factory=dict)
    # C-1 替代料合并（sc8-baoguan-substitute-partial-kit，2026-07-15）：
    # {主料component_id: [替代料component_id,...]}，供看板标注"含替代料 Rxx"；
    # BOM 无替代料关系时恒为空字典。纯展示信息，不影响 kit_date/gap_days/risk 既有语义。
    substitute_groups: dict[str, list[str]] = field(default_factory=dict)
    # C-2 部分齐套（sc8-baoguan-substitute-partial-kit，2026-07-15）：与净额开关（现货数据）
    # 耦合——SC8_NET_INVENTORY=off 或无现货数据时三者恒为 None，零漂移；不改 risk 既有判定。
    kittable_qty:        int | None = None   # 可齐套套数 = min(全部直接子件 floor(现货/单机用量))
    kittable_bottleneck: str | None = None   # 卡住可齐套数的瓶颈子件料号
    kittable_shortfall:  int | None = None   # 该瓶颈子件凑够下一整套还差多少件


def _classify(confirmed_gap: int | None, has_bom: bool, params: ForecastParams,
              no_feedback_n: int, bottleneck: str | None,
              confirmed_bottleneck: str | None) -> tuple[str, str]:
    """定四色 + 建议动作（保供口径）。返回 (risk, action)。

    分级只看**确定承诺**的缺口 confirmed_gap（剔除无答复估算）：
      · 有确定承诺且晚 >3 天 → 🔴 真延期（确定瓶颈，最高优先级）；1-3 天 → 🟡 偏紧；
      · 无确定延期、但有未答复子件 → 🟠 待催（信息缺口，催答交）；
      · 全部有承诺且按期 → 🟢。
    """
    if not has_bom:
        return RISK_RED, "无 BOM 直接子件数据，无法判定齐套，需人工核对子件清单"

    cbn = f"，确定瓶颈子件 {confirmed_bottleneck}" if confirmed_bottleneck else ""
    bn = f"，瓶颈子件 {bottleneck}" if bottleneck else ""

    # ① 有确定承诺且已晚 → 真延期（硬信号，优先于"待催"）
    if confirmed_gap is not None and confirmed_gap > 3:
        return RISK_RED, (f"保供高风险（真延期）：已有供应商承诺、但确定齐料晚出货 "
                          f"{confirmed_gap} 天{cbn}，需紧急协调到货/评估改期")
    if confirmed_gap is not None and confirmed_gap >= 1:
        return RISK_YELLOW, (f"保供偏紧：确定齐料晚出货 {confirmed_gap} 天{cbn}，"
                             f"确认能否提前备料/加快到货")

    # ② 无确定延期，但存在未答复子件 → 待催（不确定，非确定延期）
    if no_feedback_n:
        return RISK_GAP, (f"承诺缺口待催：{no_feedback_n} 个子件供应商未答复、无确定承诺，"
                          f"齐料无法判定{bn}，需催供应商答交后再评估（已确定部分按期）")

    # ③ 全部有承诺且按期
    gap_txt = f"出货前 {-confirmed_gap} 天齐套" if confirmed_gap is not None else "全部子件已承诺按期"
    return RISK_GREEN, f"齐料按期（{gap_txt}）{cbn}"


def _substitute_groups(bom: list, product_id: str) -> dict[str, list[str]]:
    """按 sequence 把 product_id 直属行的主料/替代料分组（C-1，2026-07-15）。

    返回 {主料 component_id: [替代料 component_id, ...]}；无替代料关系的料位不出现在结果中。

    仅扫描 `product_id` 直属行——与生产环境现状 `max_depth=1` 一致（BOM 仅取直接子件，
    未递归取半成品自身的替代料关系）。若未来接入更深层 BOM 取数，半成品自身的替代料
    分组需要对其自身 product_id 再调一次本函数，是独立后续任务。
    """
    by_sequence: dict[str, list] = {}
    for row in bom:
        if row.product_id != product_id or not row.sequence:
            continue
        by_sequence.setdefault(row.sequence, []).append(row)
    result: dict[str, list[str]] = {}
    for rows in by_sequence.values():
        primaries = [r for r in rows if not r.is_substitute]
        substitutes = [r for r in rows if r.is_substitute]
        if not primaries or not substitutes:
            continue
        for p in primaries:
            result.setdefault(p.component_id, []).extend(s.component_id for s in substitutes)
    return result


def _gross_need(so: SalesOrder, bom: list) -> dict[str, float]:
    """成品**全部叶子件**（多层递归展开半成品子件）毛需求 = 订货量 × 逐层用量 ×(1+损耗)。

    B1（shortage-multilevel-bom-b1，2026-07-13，姚祖怡批改发现）：原先只取直接
    子件（level==1），半成品子件（如 F02N.0226 的 S02Y.0198）不继续分解，其下
    真实原材料需求完全不进入计算——"所有F开头需求的共性问题"。改为复用
    `kit_engine.explode_bom`（O2/SC7 已用、已测试的多层递归算法），无条件展开
    到叶子件；单层 BOM（无半成品）场景结果与改造前完全一致（向后兼容）。

    C-1（sc8-baoguan-substitute-partial-kit，2026-07-15）：替代料行（`is_substitute=True`）
    在展开前剔除，毛需求只按主料链路计一份，不因替代料存在而重复计算该料位需求。
    """
    main_bom = [row for row in bom if not row.is_substitute]
    plan = ProductionPlan(plan_id=so.so_id, product_id=so.item_code,
                          product_name=so.item_name, planned_qty=so.qty,
                          planned_date=so.required_date)
    return explode_bom(main_bom, [plan])


def _covered_by_stock(so: SalesOrder, bom: list, inventory: dict) -> set[str]:
    """白名单仓可用现货 ≥ 毛需求 的直接子件（视为已齐、无需采购到货）。

    C-1（sc8-baoguan-substitute-partial-kit，2026-07-15）：有替代料关系的料位，
    可用现货 = 主料现货 + 组内全部替代料现货合计（等价合并，无优先主料顺序）。
    """
    groups = _substitute_groups(bom, so.item_code)
    covered = set()
    for m, q in _gross_need(so, bom).items():
        if q <= 0:
            continue
        avail = float(inventory.get(m, 0) or 0)
        avail += sum(float(inventory.get(s, 0) or 0) for s in groups.get(m, []))
        if avail >= q:
            covered.add(m)
    return covered


def _drop_covered(mat: MaterialArrivals, covered: set[str]) -> MaterialArrivals:
    """从到货估算剔除现货已覆盖的直接子件并重算瓶颈（现货齐备的子件不再驱动待催/瓶颈）。"""
    arrivals = {m: d for m, d in mat.arrivals.items() if m not in covered}
    no_fb = [m for m in mat.no_feedback_materials if m not in covered]
    bottleneck = max(arrivals, key=lambda m: arrivals[m]) if arrivals else None
    return MaterialArrivals(arrivals=arrivals, no_feedback_materials=no_fb,
                            bottleneck_material=bottleneck, has_bom=mat.has_bom)


def _period_match_for_so(
    so: SalesOrder, bom: list, ship: date,
    material_commitments: dict[str, list[tuple[date, float]]] | None,
) -> dict[str, PeriodMatchResult]:
    """逐直接子件跑周期累计供需匹配（B2）。`material_commitments` 为空/None → 空字典。

    范围提醒（design D2）：本次只做单一需求维度，`previous_demand_date`/
    `carry_in_balance` 均用 MVP 缺省（None/0.0）——跨运行的"上一周期期望交付日/
    结转余额"持久化账本是独立后续任务，不在本次范围内。
    """
    if not material_commitments:
        return {}
    result: dict[str, PeriodMatchResult] = {}
    for material_id, need in _gross_need(so, bom).items():
        if need <= 0:
            continue
        result[material_id] = match_period_cumulative_supply(
            material_id=material_id, demand_qty=need, demand_date=ship,
            commitments=material_commitments.get(material_id, []),
        )
    return result


def _kittable_qty(
    so: SalesOrder, bom: list, inventory: dict,
) -> tuple[int | None, str | None, int | None]:
    """可齐套套数（C-2，2026-07-15）：min(全部直接子件( floor(可用现货÷单机用量) ))。

    全部直接子件参与、无例外（即便某子件现货为 0 也拉低整体可齐套数）。含替代料的
    料位按 C-1 等价合并口径，可用现货 = 主料 + 组内全部替代料现货合计。

    Returns:
        (可齐套套数, 瓶颈子件料号, 该子件凑够下一整套还差多少件)；
        无直接子件或某子件单机用量非正（数据异常）时返回 (None, None, None)。
    """
    groups = _substitute_groups(bom, so.item_code)
    direct = [row for row in bom
             if row.product_id == so.item_code and not row.is_substitute]
    if not direct:
        return None, None, None

    best_qty: int | None = None
    best_material: str | None = None
    best_shortfall: int | None = None
    for row in direct:
        if row.qty_per_unit <= 0:
            return None, None, None   # 数据异常，无法计算，不以 0 冒充
        avail = float(inventory.get(row.component_id, 0) or 0)
        avail += sum(float(inventory.get(s, 0) or 0) for s in groups.get(row.component_id, []))
        possible = int(avail // row.qty_per_unit)
        if best_qty is None or possible < best_qty:
            best_qty = possible
            best_material = row.component_id
            needed_for_next = (possible + 1) * row.qty_per_unit
            best_shortfall = max(int(round(needed_for_next - avail)), 0)
    return best_qty, best_material, best_shortfall


def assess_supply_risk(so: SalesOrder, bom: list, srm_deliveries: list, *,
                       today: date, params: ForecastParams | None = None,
                       inventory: dict | None = None,
                       material_commitments: dict[str, list[tuple[date, float]]] | None = None,
                       ) -> BaoguanRow:
    """对单张成品行（预测订单行）做保供齐套评估。

    无答复基准：demand_date = max(出货日, 今天) → 无答复子件到货 = 该日 + no_feedback_lead_days。
    分级基于"确定承诺"子件的缺口（剔除无答复估算），区分真延期 vs 待催（见 _classify）。

    现货净额（`inventory`={material_id→白名单仓可用量}）：仅当 `SC8_NET_INVENTORY=on` 时生效，
    现货可用量≥毛需求的物料视为已齐、退出待催/催货（消除"有货却被追料"误判 P0）；
    默认 OFF → inventory 被忽略、四色与接入前完全一致（零漂移）。

    周期累计供需匹配（`material_commitments`，B2，shortage-baoguan-criteria-v3）：仅当传入时
    附加计算，写入 `BaoguanRow.period_match`（纯信息，不影响 kit_date/gap_days/risk/action）；
    缺省 None → `period_match` 恒为空字典，零漂移。

    多层 BOM 展开（B1，shortage-multilevel-bom-b1，2026-07-13）：`estimate_material_arrivals`
    内部已改为多层递归展开半成品子件至叶子件（无条件生效，非开关控制——姚祖怡批改发现的
    "半成品未分解"是结构性正确性问题，不是需要专员签字的业务口径）；单层 BOM（无半成品）
    场景结果与改造前完全一致。
    """
    p = params or config.default_params()
    ship = date.fromisoformat(so.required_date)
    effective_demand = max(ship, today)        # ← Paul 定的 max(需求日,今天) 基准

    # C-1（sc8-baoguan-substitute-partial-kit）：estimate_material_arrivals/explode_bom
    # 不识别 is_substitute，若替代料行混入会被当成独立"待答交组件"查 SRM（幻影组件）。
    # 传入前剔除替代料行，齐料估算只看主料链路；替代料现货合计判齐在下方 _covered_by_stock
    # 单独处理。不改 forecast.py（其余调用方如 pipeline.py 暂不受影响，是本变更包范围外的
    # 已知后续风险——一旦真实替代料数据流入，需要同样处理，见 design.md）。
    main_bom = [row for row in bom if not row.is_substitute]
    mat = estimate_material_arrivals(so.item_code, main_bom, srm_deliveries,
                                     demand_date=effective_demand, params=p)
    had_bom = mat.has_bom
    period_match = _period_match_for_so(so, bom, ship, material_commitments) if had_bom else {}
    # C-1（sc8-baoguan-substitute-partial-kit）：替代料分组信息，纯展示用，不受净额开关影响。
    substitute_groups = _substitute_groups(bom, so.item_code) if had_bom else {}

    # 现货净额（开关默认关；关时不改任何行为）；C-2 可齐套套数与净额同一入口（design.md D4）：
    # 开关 OFF 或无 inventory 时三者恒为 None，零漂移。
    kittable_qty = kittable_bottleneck = kittable_shortfall = None
    if inventory and had_bom and config.net_inventory_enabled():
        covered = _covered_by_stock(so, bom, inventory)
        if covered:
            mat = _drop_covered(mat, covered)
        kittable_qty, kittable_bottleneck, kittable_shortfall = _kittable_qty(so, bom, inventory)

    if not had_bom:
        risk, action = _classify(None, False, p, 0, None, None)
        return BaoguanRow(
            so_id=so.so_id, product_id=so.item_code, product_name=so.item_name,
            customer_name=so.customer_name, qty=so.qty, ship_date=ship,
            kit_date=None, gap_days=None, risk=risk,
            bottleneck_material=mat.bottleneck_material,
            no_feedback_materials=mat.no_feedback_materials,
            component_count=len(mat.arrivals), has_bom=False, action=action,
        )

    if not mat.arrivals:
        # 有 BOM，但全部直接子件被现货覆盖 → 现货齐备、按期（🟢）
        return BaoguanRow(
            so_id=so.so_id, product_id=so.item_code, product_name=so.item_name,
            customer_name=so.customer_name, qty=so.qty, ship_date=ship,
            kit_date=None, gap_days=None, risk=RISK_GREEN,
            bottleneck_material=None, no_feedback_materials=[],
            component_count=0, has_bom=True,
            action="全部直接子件现货可用量满足毛需求，现货齐备（无需采购到货）",
            period_match=period_match, substitute_groups=substitute_groups,
            kittable_qty=kittable_qty, kittable_bottleneck=kittable_bottleneck,
            kittable_shortfall=kittable_shortfall,
        )

    kit_date = max(mat.arrivals.values())      # 齐料日 = 关键路径最晚到货（含无答复估算）
    gap_days = (kit_date - ship).days

    # 仅"有确定承诺"子件（剔除无答复）的齐料/缺口/瓶颈 → 真延期判定依据
    nf_set = set(mat.no_feedback_materials)
    confirmed = {m: d for m, d in mat.arrivals.items() if m not in nf_set}
    confirmed_kit = max(confirmed.values()) if confirmed else None
    confirmed_gap = (confirmed_kit - ship).days if confirmed_kit is not None else None
    confirmed_bottleneck = (max(confirmed, key=confirmed.get) if confirmed else None)

    risk, action = _classify(confirmed_gap, True, p, len(mat.no_feedback_materials),
                             mat.bottleneck_material, confirmed_bottleneck)
    # C-2：部分齐套不改变四色判定（risk 已由 _classify 定），只在建议动作里附加提示。
    if kittable_qty is not None and kittable_qty > 0:
        action = f"{action}；可先齐 {kittable_qty} 套"
    return BaoguanRow(
        so_id=so.so_id, product_id=so.item_code, product_name=so.item_name,
        customer_name=so.customer_name, qty=so.qty, ship_date=ship,
        kit_date=kit_date, gap_days=gap_days, risk=risk,
        bottleneck_material=mat.bottleneck_material,
        no_feedback_materials=mat.no_feedback_materials,
        component_count=len(mat.arrivals), has_bom=True, action=action,
        confirmed_kit_date=confirmed_kit, confirmed_gap_days=confirmed_gap,
        period_match=period_match, substitute_groups=substitute_groups,
        kittable_qty=kittable_qty, kittable_bottleneck=kittable_bottleneck,
        kittable_shortfall=kittable_shortfall,
    )


def build_dashboard(orders: list[SalesOrder], bom: list, srm_deliveries: list, *,
                    today: date, params: ForecastParams | None = None,
                    inventory: dict | None = None,
                    material_commitments: dict[str, list[tuple[date, float]]] | None = None,
                    priority_resolver=None,
                    ) -> list[BaoguanRow]:
    """对全部成品行生成保供预警，按风险降序（🔴→🟡→🟢）、缺口天数降序排列。

    `inventory`（{material_id→白名单仓可用量}）仅当 `SC8_NET_INVENTORY=on` 生效（默认关，零漂移）。
    `material_commitments`（B2 周期累计供需匹配，见 assess_supply_risk）缺省 None 时
    各行 `period_match` 恒为空字典，不影响四色/缺口既有逻辑。

    `priority_resolver`（B4 框架桩，shortage-baoguan-criteria-v3，2026-07-10 会议定稿）：
    签名 `(material_id: str, competing_so_ids: list[str]) -> list[str]`（按 PMC 月度优先级
    排序后的 so_id 列表），用于未来"共用子件现货按 PMC 优先级占用"（同一物料被多个成品行
    同时竞争时谁先扣现货）。**本次只接受该参数、不调用/不实现真实排序逻辑**（PMC 数据源
    未就绪）——传入任何值都不改变当前结果，等真实数据到位后再接线。
    """
    rows = [assess_supply_risk(so, bom, srm_deliveries, today=today, params=params,
                               inventory=inventory, material_commitments=material_commitments)
            for so in orders]
    order = {RISK_RED: 0, RISK_GAP: 1, RISK_YELLOW: 2, RISK_GREEN: 3}
    rows.sort(key=lambda r: (order.get(r.risk, 4), -(r.gap_days if r.gap_days is not None else 9999)))
    return rows


def render_markdown(rows: list[BaoguanRow], *, today: date,
                    params: ForecastParams | None = None) -> str:
    """渲染保供预警看板（Markdown，三色分组）。"""
    p = params or config.default_params()
    n_red = sum(1 for r in rows if r.risk == RISK_RED)
    n_gap = sum(1 for r in rows if r.risk == RISK_GAP)
    n_yel = sum(1 for r in rows if r.risk == RISK_YELLOW)
    n_grn = sum(1 for r in rows if r.risk == RISK_GREEN)

    out: list[str] = []
    out.append(f"# 成品保供预警看板（齐套维度）")
    out.append("")
    out.append(f"> 生成日：{today.isoformat()}　｜　成品行 {len(rows)} 条　｜　"
               f"🔴 {n_red} / 🟠 {n_gap} / 🟡 {n_yel} / 🟢 {n_grn}　｜　参数版本 {p.param_version}")
    out.append(f"> 口径：分级只看**有确定承诺**子件的齐料缺口——🔴 真延期（有承诺仍晚>3天）/ "
               f"🟠 待催（子件未答复、无确定承诺）/ 🟡 偏紧（1-3天）/ 🟢 按期。"
               f"无答复子件齐料按 max(出货日,今天)+{p.no_feedback_lead_days} 天估算（仅供参考）。**内部保供运维用，不对客。**")
    out.append("")

    groups = [("🔴 保供高风险 · 真延期（有承诺仍晚 >3天 或 无 BOM）", RISK_RED),
              ("🟠 承诺缺口 · 待催（子件未答复，齐料待定）", RISK_GAP),
              ("🟡 保供偏紧（确定齐料晚 1-3天）", RISK_YELLOW),
              ("🟢 齐料按期", RISK_GREEN)]
    for title, risk in groups:
        grp = [r for r in rows if r.risk == risk]
        if not grp:
            continue
        out.append(f"## {title}")
        out.append("")
        out.append("| 成品 | 品名 | 客户 | 数量 | 计划出货日 | 齐料日 | 缺口天数 | 子件数 | 未答复 | 建议动作 |")
        out.append("|---|---|---|--:|---|---|--:|--:|--:|---|")
        for r in grp:
            kit = r.kit_date.isoformat() if r.kit_date else "—"
            gap = f"{r.gap_days:+d}" if r.gap_days is not None else "—"
            nf = len(r.no_feedback_materials)
            out.append(f"| {r.product_id} | {r.product_name} | {r.customer_name or '—'} | {r.qty} | "
                       f"{r.ship_date.isoformat()} | {kit} | {gap} | {r.component_count} | {nf} | {r.action} |")
        out.append("")
    return "\n".join(out)


# ── HTML 看板渲染（独立可在浏览器打开、自包含交互看板：筛选/搜索/排序/导出 CSV/KPI 动画）──
# 交互能力移植自 supplychain 预警中心的**纯前端部分**（后端类：实时预测/案例处置，不适用于静态文件，
# 等价物 = 重跑 Python runner）。零 CDN 依赖、离线秒开。渲染层与数据/逻辑层解耦：拿到 Claude Design
# 设计稿后，只替换 _HTML_STYLE + _HTML_JS + render_html 的结构，build_dashboard/assess 不动。
_HTML_STYLE = """<style>
:root{--bg:#f7f6f3;--surface:#fff;--surface2:#f1efe8;--text:#23221f;--text2:#5f5e5a;--text3:#8a8980;--border:rgba(0,0,0,.12);--danger-bg:#FCEBEB;--danger:#A32D2D;--gap-bg:#FBE3D0;--gap:#9C4221;--warn-bg:#FAEEDA;--warn:#854F0B;--ok-bg:#E1F5EE;--ok:#0F6E56;--info:#378ADD;--track:#e7e5de;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;--sans:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
@media(prefers-color-scheme:dark){:root{--bg:#1a1917;--surface:#252320;--surface2:#2f2d29;--text:#ECEAE3;--text2:#b4b2a9;--text3:#888780;--border:rgba(255,255,255,.14);--danger-bg:#3a1c1c;--danger:#F09595;--gap-bg:#3a2414;--gap:#F0A878;--warn-bg:#3a2c12;--warn:#FAC775;--ok-bg:#10302a;--ok:#5DCAA5;--info:#85B7EB;--track:#3a3833}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);font-size:15px;line-height:1.6;padding:24px}
.wrap{max-width:920px;margin:0 auto}
.head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:20px}
.title{font-size:20px;font-weight:600}
.sub{font-size:13px;color:var(--text2);margin-top:2px}
.badges{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}
.badge{font-size:12px;padding:4px 10px;border-radius:8px;background:var(--surface2);color:var(--text2);white-space:nowrap}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:18px}
.kpi{background:var(--surface2);border-radius:10px;padding:14px 16px}
.kpi-l{font-size:13px;color:var(--text2)}
.kpi-v{font-size:24px;font-weight:600;margin-top:4px}
.kpi-v.danger{color:var(--danger)}
.kpi-s{font-size:12px;color:var(--text3);margin-top:2px}
.toolbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.fbtns{display:flex;gap:6px;flex-wrap:wrap}
.fbtn{font-size:13px;padding:5px 12px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--text2);cursor:pointer}
.fbtn:hover{background:var(--surface2)}
.fbtn.active{background:var(--text);color:var(--bg);border-color:var(--text)}
.search{flex:1;min-width:160px;height:34px;padding:0 12px;border:1px solid var(--border);border-radius:8px;background:var(--surface);color:var(--text);font-size:14px;font-family:var(--sans)}
.sel{height:34px;padding:0 10px;border:1px solid var(--border);border-radius:8px;background:var(--surface);color:var(--text);font-size:13px;font-family:var(--sans);cursor:pointer}
.btn{height:34px;padding:0 14px;border:1px solid var(--border);border-radius:8px;background:var(--surface);color:var(--text);font-size:13px;cursor:pointer}
.btn:hover{background:var(--surface2)}
.cnt{font-size:12px;color:var(--text3);margin-bottom:10px}
.empty{padding:28px;text-align:center;color:var(--text3);font-size:14px;border:1px dashed var(--border);border-radius:12px}
.cards{display:flex;flex-direction:column;gap:10px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px 16px}
.card-h{display:flex;align-items:baseline;justify-content:space-between;gap:8px;flex-wrap:wrap}
.id{font-size:16px;font-weight:600;font-family:var(--mono)}
.nm{font-size:13px;color:var(--text2);margin-left:8px}
.gap{font-size:13px;font-weight:600;padding:3px 10px;border-radius:8px;white-space:nowrap}
.gap.danger{background:var(--danger-bg);color:var(--danger)}
.gap.gapc{background:var(--gap-bg);color:var(--gap)}
.gap.warn{background:var(--warn-bg);color:var(--warn)}
.gap.ok{background:var(--ok-bg);color:var(--ok)}
.meta{font-size:12px;color:var(--text2);margin-top:3px}
.strip{display:flex;align-items:center;gap:14px;margin-top:10px;font-size:13px;flex-wrap:wrap;color:var(--text2)}
.strip b{color:var(--text);font-weight:600}
.kd.danger{color:var(--danger)}.kd.gapc{color:var(--gap)}.kd.warn{color:var(--warn)}.kd.ok{color:var(--ok)}
.mono{font-family:var(--mono);color:var(--text)}
.cov{margin-top:10px}
.cov-h{display:flex;justify-content:space-between;font-size:12px;color:var(--text2);margin-bottom:4px}
.track{height:6px;border-radius:3px;background:var(--track);overflow:hidden}
.fill{height:100%;background:var(--info)}
.act{margin-top:10px;font-size:13px;background:var(--surface2);border-radius:8px;padding:8px 10px}
.foot{margin-top:14px;font-size:12px;color:var(--text3);line-height:1.6}
</style>"""

# 纯前端交互逻辑（raw 字符串：\n/﻿ 等保持 JS 字面量；__DATA__/__META__ 由 render_html 注入）。
_HTML_JS = r"""
const DATA=__DATA__;
const META=__META__;
const $=function(id){return document.getElementById(id);};
const esc=function(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});};
const fmt=function(n){return Number(n).toLocaleString('en-US');};
const RT={red:'真延期',gap:'待催',yel:'偏紧',grn:'按期'};
const CLS={red:'danger',gap:'gapc',yel:'warn',grn:'ok'};
var state={f:'all',q:'',sort:'gap'};

function cls(r){return CLS[r.risk]||'danger';}
function gapText(r){
 if(!r.hasBom)return'无 BOM';
 if(r.risk==='gap')return'待催 · '+r.nf+' 子件未答复';
 if(r.cg==null)return r.risk==='grn'?'按期':'—';
 if(r.cg<=0)return'确定提前 '+(-r.cg)+' 天';
 return'确定齐料晚 +'+r.cg+' 天';
}

function subsText(r,materialId){
 var subs=(r.subs||{})[materialId];
 return (subs&&subs.length)?'（含替代料 '+subs.map(esc).join('、')+'）':'';
}

function card(r){
 var c=cls(r),covered=r.comp-r.nf,pct=r.comp?Math.round(covered/r.comp*100):0;
 var cov=r.comp?'<div class="cov"><div class="cov-h"><span>子件承诺覆盖</span><span>'+covered+' / '+r.comp+' 命中 · '+r.nf+' 未答复</span></div><div class="track"><div class="fill" style="width:'+pct+'%"></div></div></div>':'';
 var bn=r.bn?'<span>瓶颈 <span class="mono">'+esc(r.bn)+'</span>'+subsText(r,r.bn)+'</span>':'';
 // C-2：可齐套套数（kq==null → 现货数据不可用，不显示徽标，不以 0 冒充）
 var kit=(r.kq==null)?'':'<span class="badge" title="'+(r.kbn?('卡在子件 '+esc(r.kbn)+subsText(r,r.kbn)+'、还差 '+fmt(r.ksf)+' 件'):'')+'">可齐套 '+fmt(r.kq)+' / '+fmt(r.qty)+'</span>';
 return '<div class="card"><div class="card-h"><div><span class="id">'+esc(r.id)+'</span><span class="nm">'+esc(r.name)+'</span></div><span class="gap '+c+'">'+gapText(r)+'</span></div>'
  +'<div class="meta">客户 '+(esc(r.cust)||'—')+' · 数量 '+fmt(r.qty)+(kit?' · '+kit:'')+'</div>'
  +'<div class="strip"><span>出货 <b>'+esc(r.ship)+'</b></span><span>→</span><span>齐料 <b class="kd '+c+'">'+(r.kit?esc(r.kit):'—')+'</b></span>'+bn+'</div>'
  +cov+'<div class="act">建议：'+esc(r.action)+'</div></div>';
}

function view(){
 var l=DATA.filter(function(r){return state.f==='all'||r.risk===state.f;});
 var q=state.q.trim().toLowerCase();
 if(q)l=l.filter(function(r){return (r.id+' '+r.name+' '+r.cust+' '+r.bn).toLowerCase().indexOf(q)>=0;});
 l.sort(function(a,b){
  if(state.sort==='ship')return a.ship.localeCompare(b.ship);
  if(state.sort==='id')return a.id.localeCompare(b.id);
  var ga=a.gap==null?1e9:a.gap,gb=b.gap==null?1e9:b.gap;return gb-ga;
 });
 return l;
}

function countUp(el){var t=+el.getAttribute('data-cu')||0,pre=el.getAttribute('data-pre')||'',suf=el.getAttribute('data-suf')||'';var v=0,step=Math.max(1,Math.ceil(t/45));var id=setInterval(function(){v=Math.min(v+step,t);el.textContent=pre+v+suf;if(v>=t)clearInterval(id);},16);}

function kpi(label,val,vc,sub,pre,suf){
 vc=vc||'';sub=sub||'';pre=pre||'';suf=suf||'';
 var num=(typeof val==='number')?'<span data-cu="'+val+'" data-pre="'+pre+'" data-suf="'+suf+'">0</span>':esc(val);
 return '<div class="kpi"><div class="kpi-l">'+label+'</div><div class="kpi-v '+vc+'">'+num+'</div>'+(sub?'<div class="kpi-s">'+sub+'</div>':'')+'</div>';
}

function renderKpis(){
 var nr=0,ngap=0,ny=0,ng=0,tc=0,cov=0,cgaps=[];
 DATA.forEach(function(r){if(r.risk==='red')nr++;else if(r.risk==='gap')ngap++;else if(r.risk==='yel')ny++;else ng++;tc+=r.comp;cov+=(r.comp-r.nf);if(r.cg!=null&&r.cg>0)cgaps.push(r.cg);});
 var pct=tc?Math.round(cov/tc*100):0;
 var mx=cgaps.length?Math.max.apply(null,cgaps):null;
 var h=kpi('成品行',DATA.length)+kpi('真延期(红)',nr,'danger','🟠 待催 '+ngap+' · 🟡 '+ny+' · 🟢 '+ng)
   +kpi('子件承诺覆盖',pct,'',tc?(cov+' / '+tc+' 子件'):'','','%')
   +(mx==null?kpi('最大确定延期','—','danger','无确定延期'):kpi('最大确定延期',mx,'danger','基于已承诺子件','+',' 天'));
 $('kpis').innerHTML=h;
 var els=document.querySelectorAll('[data-cu]');for(var i=0;i<els.length;i++)countUp(els[i]);
}

function renderFbtns(){
 var counts={all:DATA.length,red:0,gap:0,yel:0,grn:0};
 DATA.forEach(function(r){counts[r.risk]++;});
 var defs=[['all','全部'],['red','🔴 真延期'],['gap','🟠 待催'],['yel','🟡 偏紧'],['grn','🟢 按期']];
 $('fbtns').innerHTML=defs.map(function(d){return '<button class="fbtn'+(state.f===d[0]?' active':'')+'" data-f="'+d[0]+'" type="button">'+d[1]+' '+counts[d[0]]+'</button>';}).join('');
 var bs=$('fbtns').querySelectorAll('.fbtn');
 for(var i=0;i<bs.length;i++){bs[i].onclick=function(){state.f=this.getAttribute('data-f');renderFbtns();render();};}
}

function render(){
 var l=view();
 $('cards').innerHTML=l.length?l.map(card).join(''):'<div class="empty">没有匹配的成品</div>';
 $('cnt').textContent='显示 '+l.length+' / '+DATA.length+' 个成品';
}

function exportCSV(){
 var l=view();
 var hdr=['成品','品名','客户','数量','计划出货日','齐料日','缺口天数','子件数','未答复','瓶颈','风险'];
 var lines=[hdr.join(',')];
 l.forEach(function(r){
  var row=[r.id,r.name,r.cust,r.qty,r.ship,r.kit||'',r.gap==null?'':r.gap,r.comp,r.nf,r.bn,RT[r.risk]];
  lines.push(row.map(function(x){return '"'+String(x).replace(/"/g,'""')+'"';}).join(','));
 });
 var blob=new Blob(['﻿'+lines.join('\n')],{type:'text/csv;charset=utf-8'});
 var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='保供预警_'+META.today+'.csv';
 document.body.appendChild(a);a.click();document.body.removeChild(a);URL.revokeObjectURL(a.href);
}

renderKpis();renderFbtns();render();
$('q').addEventListener('input',function(e){state.q=e.target.value;render();});
$('sort').addEventListener('change',function(e){state.sort=e.target.value;render();});
$('csv').addEventListener('click',exportCSV);
"""


# 风险 emoji → 前端/JSON 用的短码（render_html / Web 服务 /api/baoguan / 案例去重共用）
RISK_CODE = {RISK_RED: "red", RISK_GAP: "gap", RISK_YELLOW: "yel", RISK_GREEN: "grn"}


def row_to_dict(r: BaoguanRow) -> dict:
    """把一条 BaoguanRow 序列化为前端/JSON 载荷（render_html 内嵌 + Web /api/baoguan 共用）。

    含 ``so``（预测订单号）—— 真延期去重/建案稳定键 (id, so, ship) 的一部分，
    静态 HTML 看板用不到但保留不影响（前端 JS 忽略多余字段）。
    """
    return {
        "id": r.product_id, "so": r.so_id, "name": r.product_name, "cust": r.customer_name,
        "qty": r.qty, "ship": r.ship_date.isoformat(),
        "kit": r.kit_date.isoformat() if r.kit_date else None,
        "gap": r.gap_days, "cg": r.confirmed_gap_days, "comp": r.component_count,
        "nf": len(r.no_feedback_materials), "bn": r.bottleneck_material or "",
        "risk": RISK_CODE.get(r.risk, "red"), "hasBom": r.has_bom, "action": r.action,
        # C-1（含替代料的主料 → 替代料料号列表；无替代料时为空对象，前端不显示标注）
        "subs": r.substitute_groups,
        # C-2（None → 前端不显示"可齐套"徽标，不以 0 冒充）
        "kq": r.kittable_qty, "kbn": r.kittable_bottleneck, "ksf": r.kittable_shortfall,
    }


def render_html(rows: list[BaoguanRow], *, today: date,
                params: ForecastParams | None = None) -> str:
    """渲染保供预警看板为独立交互 HTML 页面（浏览器可直接打开；筛选/搜索/排序/导出）。"""
    p = params or config.default_params()
    data = [row_to_dict(r) for r in rows]
    # 安全嵌入 <script>：转义 < > & 防 </script> 破出 / HTML 解析（JS 侧 \uXXXX 仍解回原字符）
    payload = (_json.dumps(data, ensure_ascii=False)
               .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))
    meta = _json.dumps({"today": today.isoformat(), "ver": p.param_version}, ensure_ascii=False)
    js = _HTML_JS.replace("__DATA__", payload).replace("__META__", meta)

    return (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\"><head><meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>成品保供预警看板</title>\n"
        + _HTML_STYLE + "</head><body><div class=\"wrap\">\n"
        + '<div class="head"><div><div class="title">成品保供预警看板</div>\n'
        + f'<div class="sub">齐套维度 · 齐料日 vs 计划出货日 · 生成 {today.isoformat()} · 参数 {_html.escape(p.param_version)}</div></div>\n'
        + '<div class="badges"><span class="badge">内部保供运维 · 不对客</span></div></div>\n'
        + '<div class="kpis" id="kpis"></div>\n'
        + '<div class="toolbar"><div class="fbtns" id="fbtns"></div>\n'
        + '<input class="search" id="q" type="text" placeholder="搜索 料号 / 品名 / 客户 / 瓶颈子件" aria-label="搜索">\n'
        + '<select class="sel" id="sort" aria-label="排序"><option value="gap">按缺口天数</option>'
        + '<option value="ship">按计划出货日</option><option value="id">按料号</option></select>\n'
        + '<button class="btn" id="csv" type="button">导出 CSV</button></div>\n'
        + '<div class="cnt" id="cnt"></div>\n<div class="cards" id="cards"></div>\n'
        + f'<div class="foot">分级只看<b>有确定承诺</b>子件的齐料缺口：🔴 真延期（有承诺仍晚 &gt;3天）· 🟠 待催（子件未答复、无确定承诺，齐料待定）· 🟡 偏紧（确定晚 1-3天）· 🟢 按期。未答复子件齐料按 max(出货日, 今天)+{p.no_feedback_lead_days} 天估算（仅参考，不计入真延期）。本看板为内部保供运维用途，不对客。</div>\n'
        + '</div>\n<script>\n' + js + '\n</script></body></html>'
    )
