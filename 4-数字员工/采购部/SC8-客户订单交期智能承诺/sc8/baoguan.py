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


@dataclass(frozen=True)
class NoFeedbackDetail:
    """一个"无答复"子件的估算明细（判据说明 V2 答复2，姚祖怡 2026-07-23，Paul 同日拍板）：

    姚反馈"预计齐套依据"看不清具体是哪些子件在按估算算——本结构把每个无 SRM 承诺交期
    子件的料号/毛需求量/估算到货日显式列出，供看板展示，纯附加信息，不影响四色/action。
    """
    component_id:       str
    qty:                float
    estimated_arrival:  date
    # 料品名称（功能批1 ③，姚祖怡 07-23）：料号旁显示品名，纯展示，取自 BOM component_name。
    component_name:     str = ""


# 子件供给状态短码（#12，功能批1，姚祖怡 07-23 新增诉求）——PO 在途 + SRM 答交交叉分类：
STATUS_NO_TRANSIT          = "no_transit"           # 无在途：查无采购订单
STATUS_TRANSIT_UNCONFIRMED = "transit_unconfirmed"  # 有在途，供应商未答复（无 SRM 承诺）
STATUS_TRANSIT_CONFIRMED   = "transit_confirmed"    # 有在途，供应商已答交（有 SRM 承诺）
# 边界情况：有 SRM 承诺记录但查无在途 PO（数据口径不一致，如实展示不隐藏，不臆造原因）
STATUS_CONFIRMED_NO_TRANSIT = "confirmed_no_transit"


@dataclass(frozen=True)
class ComponentSupplyStatus:
    """一个"无法从现货立即满足需求"子件的实际供给状态（#12，姚祖怡 07-23 新增诉求）。

    姚反馈只看到"未答复子件数"看不出具体在补货的哪一步——本结构交叉 PO 在途数据
    （`purchase_orders`，见 sources.load_purchase_orders_by_material）与 SRM 答交承诺
    （已由 mat.arrivals/no_feedback_materials 判定），给出四态之一：
      无在途 / 有在途未答复（显示在途量）/ 既有在途又有答交（显示答交日期+在途量）/
      有答交但查无在途（边界，如实展示）。纯展示派生信息，不改四色/kit_date 既有判定。
    """
    component_id:     str
    component_name:   str
    qty_needed:       float          # 毛需求（本成品对该子件的需求量）
    status:           str            # STATUS_* 四态之一
    transit_qty:      float          # 在途未清量（无在途=0）
    confirmed_date:   date | None    # 供应商已答交日期（沿用旧口径：取自 mat.arrivals，
                                     # 即 srm_deliveries 分层取数里"最早一条"承诺日）；未答交=None
    # 答交数量累计明细（#18-a/b，姚祖怡 07-28 判例回件，队列 #139）：按 SRM 供应计划-
    # 交付计划的确认日期升序，累计确认数量直至覆盖本行毛需求为止，[(确认日期,确认数量),...]。
    # 取值来源与 confirmed_date 不同——confirmed_date 来自 /purchase/answer（PO 整单口径，
    # 会漏掉"多期分批答交、只有部分期数已确认"的情况）；confirmed_batches 来自供应计划
    # 看板逐期明细（sources.load_material_commitments），是姚祖怡截图指向的真实数据源。
    # 仅当调用方传入 material_commitments 且该子件命中"已答交"两态之一时才计算，
    # 否则恒为空列表（未传参数时零漂移，向后兼容旧行为）。
    confirmed_batches: tuple[tuple[date, float], ...] = field(default_factory=tuple)
    # 可用现货数量（④）/ 缺口数量（⑥）（姚祖怡 07-26 V6 回件原文签认，07-29 第三次重申
    # 队列 #152）：available_qty＝调用方传入的该料号净额（已按优先级分配扣减，见
    # build_dashboard._allocate_sequential_inventory）；gap_qty＝qty_needed−available_qty。
    # 仅当净额开关开启且传入 inventory 时计算，否则恒为 None（不以 0 冒充，同
    # kittable_qty 等既有字段约定）；gap_qty≤0 的子件由 _component_supply_status
    # 在构造前过滤掉，不会出现在返回列表里（#151，展示层过滤，不改计算输入）。
    available_qty:     float | None = None
    gap_qty:           float | None = None


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
    # 无答复子件明细（料号+毛需求量+估算到货日），判据说明 V2 答复2；与 no_feedback_materials
    # 一一对应，纯附加展示信息，不影响四色/action 既有语义。无 BOM/无无答复子件时恒为空列表。
    no_feedback_detail: list[NoFeedbackDetail] = field(default_factory=list)
    component_count: int = 0                   # 直接子件总数
    has_bom:        bool = False
    action:         str = ""                   # 建议动作
    # 仅基于"有真实承诺"子件的齐料/缺口（剔除无答复估算）——用于区分真延期 vs 待催
    confirmed_kit_date: date | None = None     # 确定承诺子件的最晚到货；无确定承诺→None
    confirmed_gap_days: int | None = None      # 确定齐料 − 出货；无确定承诺→None
    # 姚祖怡 07-29 二次举证真实缺陷（队列 #147）：卡片头部"确定齐料晚 N 天"徽标取自
    # confirmed_gap_days/该瓶颈子件，但卡片头部"出货→齐料"日期与"瓶颈"标签此前取自
    # bottleneck_material/gap_days（全量口径，含无答复估算），两套指标各自计算正确
    # 但混排展示会造成"数字对不上"的错觉——本字段补上确定口径的瓶颈子件，供渲染层
    # 把头部日期/瓶颈换成与徽标同源的确定口径（纯展示，不改 bottleneck_material/
    # gap_days/四色判定既有语义，无确定承诺子件时恒为 None）。
    confirmed_bottleneck: str | None = None    # 确定承诺子件里的最晚到货瓶颈；无确定承诺→None
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
    kittable_shortfall:  int | None = None   # 该瓶颈子件凑够客户下单总量（so.qty）还差多少件
    # ── 功能批1（姚祖怡 07-23 新功能诉求，队列 #87④/开场prompt-保供看板功能批1）──────
    # ③ 料品名称（料号旁显示品名）：{子件料号: 品名}，跨全部层级（含多层展开的叶子件），
    # 取自 BOM component_name，纯展示，has_bom=False 时恒为空字典。
    component_names: dict[str, str] = field(default_factory=dict)
    # #12 子件供给状态全展示：mat.arrivals（"无法从现货立即满足需求"的子件）逐条实际状态
    # （无在途/有在途未答复/既有在途又有答交/有答交无在途）。仅当 purchase_orders 参数传入
    # 时计算；未传入（默认）恒为空列表，零漂移，不影响既有四色/no_feedback_detail 语义。
    component_status: list[ComponentSupplyStatus] = field(default_factory=list)
    # #14 需求日可齐套数量：与 C-2 kittable_qty 同口径（全部直接子件+替代料等价合并），
    # 但可用量 = 现货 +（该子件到货日 ≤ 计划出货日 时的在途 PO 量）。与 kittable_qty 同一
    # 前置（净额开关 ON 且有 inventory）+ 需另传 purchase_orders，否则恒为 None。
    demand_kittable_qty:        int | None = None
    demand_kittable_bottleneck: str | None = None


def _classify(gap_days: int | None, confirmed_gap: int | None, has_bom: bool,
              params: ForecastParams, no_feedback_n: int, bottleneck: str | None,
              confirmed_bottleneck: str | None, bottleneck_is_unanswered: bool) -> tuple[str, str]:
    """定四色 + 建议动作（保供口径）。返回 (risk, action)。

    **2026-07-29 姚祖怡二次举证真实缺陷后 Paul 拍板改口径（队列 #147 续）**：分级
    改用 `gap_days`（全量口径，含无答复子件按 `NO_FEEDBACK_LEAD_DAYS` 天保守估算）
    做主driver，**不再只看 confirmed_gap（仅确定承诺子件）**——理由：看板定位是
    "用现有信息做保守预测"，任何未答复子件都应假设最坏按 90 天估算并醒目预警，
    不能因为"还没答复"就把风险降级成不显眼的"待催"。`gap_days` 是全部子件
    （确定+估算）到货的最晚值，天然已经是两者中较大的一个，无需再取 max()。

    · gap_days>3 或无 BOM → 🔴；1-3 → 🟡；其余 → 🟢。
    · 措辞区分"真实确认延期"（瓶颈子件已有供应商答复）vs"保守预警"（瓶颈子件
      未答复、数字是估算而非事实）——颜色一致（都要醒目），但动作建议不同：
      前者"协调到货/评估改期"，后者"催供应商确认答交日期"（不能把估算当事实
      去跟客户/供应商谈判）。
    · `no_feedback_n>0` 时 `gap_days` 恒 ≥ `NO_FEEDBACK_LEAD_DAYS`（90，远超 3 天
      门槛），故"🟠 待催"分支在当前参数下已不会被触发——**Paul 07-29 拍板保留
      该分支/UI（筛选按钮、KPI 统计），后续再优化**，不删除、不改变其触发条件。
    """
    if not has_bom:
        return RISK_RED, "无 BOM 直接子件数据，无法判定齐套，需人工核对子件清单"

    cbn = f"，确定瓶颈子件 {confirmed_bottleneck}" if confirmed_bottleneck else ""
    bn = f"，瓶颈子件 {bottleneck}" if bottleneck else ""

    # ① gap_days（全量，取确定与估算中较晚者）晚出货 → 红/黄，措辞按瓶颈是否已答复区分
    if gap_days is not None and gap_days > 3:
        if bottleneck_is_unanswered:
            return RISK_RED, (f"保供高风险（保守预警）：瓶颈子件 {bottleneck} 尚未答复，"
                              f"按无答复估算晚出货 {gap_days} 天，需紧急催供应商确认答交日期")
        return RISK_RED, (f"保供高风险（真延期）：已有供应商承诺、但确定齐料晚出货 "
                          f"{gap_days} 天{cbn}，需紧急协调到货/评估改期")
    if gap_days is not None and gap_days >= 1:
        if bottleneck_is_unanswered:
            return RISK_YELLOW, (f"保供偏紧（保守预警）：瓶颈子件 {bottleneck} 尚未答复，"
                                 f"按无答复估算晚出货 {gap_days} 天，需催供应商确认答交日期")
        return RISK_YELLOW, (f"保供偏紧：确定齐料晚出货 {gap_days} 天{cbn}，"
                             f"确认能否提前备料/加快到货")

    # ② 无延期，但存在未答复子件 → 待催（结构性保留，当前参数下不可达，见 docstring）
    if no_feedback_n:
        return RISK_GAP, (f"承诺缺口待催：{no_feedback_n} 个子件供应商未答复、无确定承诺，"
                          f"齐料无法判定{bn}，需催供应商答交后再评估（已确定部分按期）")

    # ③ 全部有承诺且按期
    gap_txt = f"出货前 {-gap_days} 天齐套" if gap_days is not None else "全部子件已承诺按期"
    return RISK_GREEN, f"齐料按期（{gap_txt}）{cbn}"


def _substitute_groups(bom: list, product_id: str) -> dict[str, list[str]]:
    """按 sequence 把 product_id 直属行的主料/替代料分组（C-1，2026-07-15）。

    返回 {主料 component_id: [替代料 component_id, ...]}；无替代料关系的料位不出现在结果中。

    仅扫描 `product_id` 直属行——本函数只关心"这个成品自己的直接子件里谁跟谁互为
    替代料"，与 BOM 取数深度（`config.bom_max_depth`，姚祖怡 07-26 V6 #9 后已提高到
    多层）无关。半成品自身的替代料关系（若半成品自己的子件里也有替代料）需要对其
    自身 product_id 再调一次本函数，未见真实需求前是独立后续任务。
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
        (可齐套套数, 瓶颈子件料号, 该子件凑够客户下单总量 so.qty 还差多少件)；
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
            needed_for_order = so.qty * row.qty_per_unit
            best_shortfall = max(int(round(needed_for_order - avail)), 0)
    return best_qty, best_material, best_shortfall


def _component_names(bom: list) -> dict[str, str]:
    """料号 → 品名（③ 功能批1，姚祖怡 07-23）：跨全部成品/层级扫描整个 bom 列表。

    `bom` 是本次重算传入的**全量组合 BOM**（多个成品的直接子件行合集，非单一成品过滤后
    的子集）——多层展开（B1）依赖这一点让半成品子件的下级叶子件也能在同批 bom 里找到，
    故这里同样不按 product_id 过滤，才能覆盖到深层叶子件的品名。同料号多次出现时后一条
    覆盖前一条（真实场景下同一物料号品名恒定，不构成冲突）。
    """
    return {row.component_id: row.component_name for row in bom if row.component_id}


def _cumulative_confirmed_batches(
    commitments: list[tuple[date, float]], target_qty: float,
) -> tuple[tuple[date, float], ...]:
    """按确认日期升序累计 SRM 供应计划确认数量，直至覆盖 target_qty 为止（#18-a，
    姚祖怡 07-28 判例回件："答交数量小于缺口数量，则继续显示下一个确认数量，直至
    累计数量满足缺口数量为止"）。

    返回按顺序纳入的 (确认日期, 确认数量) 元组；每条记录的数量原样展示，不因
    "凑够即止"而截断最后一条的数值（Yao 原话未要求截断，只要求"够了就不再往下加"）。
    target_qty<=0 或无承诺记录 → 空元组。
    """
    if target_qty <= 0 or not commitments:
        return ()
    ordered = sorted(commitments, key=lambda t: t[0])
    out: list[tuple[date, float]] = []
    total = 0.0
    for d, q in ordered:
        if q <= 0:
            continue
        out.append((d, q))
        total += q
        if total >= target_qty:
            break
    return tuple(out)


def _component_supply_status(
    mat: MaterialArrivals, gross: dict[str, float], names: dict[str, str],
    purchase_orders: dict[str, float],
    material_commitments: dict[str, list[tuple[date, float]]] | None = None,
    inventory: dict[str, float] | None = None,
) -> list[ComponentSupplyStatus]:
    """对 mat.arrivals 里每个"无法从现货立即满足需求"的子件，交叉 PO 在途 + SRM 答交
    分类出四态之一（#12，功能批1）。按料号排序，输出稳定、便于测试/前端渲染。

    material_commitments（#18-a/b，队列 #139，可选）：给出时为"已答交"两态
    （STATUS_TRANSIT_CONFIRMED / STATUS_CONFIRMED_NO_TRANSIT）额外计算
    confirmed_batches（供应计划逐期累计明细）；缺省 None 时该字段恒为空元组，
    不影响既有 status/transit_qty/confirmed_date 判定（零漂移）。

    inventory（④可用现货数量/⑥缺口数量，姚祖怡 07-29 三次重申，队列 #152，可选）：
    调用方仅在净额开关开启时传入（见 assess_supply_risk），值为该行订单在优先级分配
    后看到的每料号净额（build_dashboard._allocate_sequential_inventory 的输出，即
    "现货净额−优先级排在本项目前已占用量"，与姚祖怡定义逐字一致）。缺省 None 时
    available_qty/gap_qty 恒为 None，不做任何过滤（零漂移，与既有 kittable_qty 等
    字段"不以 0 冒充"同一约定）。gap_qty=qty_needed−available_qty；**≤0 的子件不
    纳入返回列表**（#151，姚祖怡 07-26 V6 回件原文签认"缺口数量如≤0，则该行视为
    满足齐套需求，不应该体现在缺料子件中"）——纯展示层过滤，不改变 mat/gross 等
    计算输入，不影响 component_count/kittable_qty 等既有统计口径。

    答交数量/日期累计目标（队列 #211 v2，2026-08-03 姚祖怡权威判定纠正）：累计
    目标是**缺口数量**（gap_qty），不是本项目需求数量（gross）——"答交数量展示
    如第一个答交数量小于缺口数量，则继续显示下一个答交数量，直至累计答交数量
    满足缺口数量为止"（姚祖怡原话）。此前 `_cumulative_confirmed_batches` 一直
    以 `gross` 为累计目标，净额开关关闭/无 inventory 时无 gap_qty 可用，仍按
    gross 累计（向后兼容，零漂移）。
    """
    nf_set = set(mat.no_feedback_materials)
    out: list[ComponentSupplyStatus] = []
    for m in sorted(mat.arrivals):
        confirmed = m not in nf_set
        transit_qty = float(purchase_orders.get(m, 0.0) or 0.0)
        if transit_qty > 0 and confirmed:
            status = STATUS_TRANSIT_CONFIRMED
        elif transit_qty > 0:
            status = STATUS_TRANSIT_UNCONFIRMED
        elif confirmed:
            status = STATUS_CONFIRMED_NO_TRANSIT
        else:
            status = STATUS_NO_TRANSIT
        need = gross.get(m, 0.0)
        available_qty: float | None = None
        gap_qty: float | None = None
        if inventory is not None:
            available_qty = float(inventory.get(m, 0.0) or 0.0)
            gap_qty = need - available_qty
            if gap_qty <= 0:
                continue   # #151：缺口≤0 不进 BOM 缺口物料清单（展示层过滤）
        batches: tuple[tuple[date, float], ...] = ()
        if confirmed and material_commitments:
            target_qty = gap_qty if gap_qty is not None else need
            batches = _cumulative_confirmed_batches(
                material_commitments.get(m, []), target_qty)
        out.append(ComponentSupplyStatus(
            component_id=m, component_name=names.get(m, ""),
            qty_needed=need, status=status,
            transit_qty=transit_qty,
            confirmed_date=mat.arrivals[m] if confirmed else None,
            confirmed_batches=batches,
            available_qty=available_qty,
            gap_qty=gap_qty,
        ))
    return out


def _demand_kittable_qty(
    so: SalesOrder, bom: list, inventory: dict, purchase_orders: dict[str, float],
    full_arrivals: dict[str, date], ship: date,
) -> tuple[int | None, str | None]:
    """需求日当日可齐套最大数量（#14，功能批1，姚祖怡 07-23）。

    与 C-2 `_kittable_qty` 同口径（全部直接子件参与、含替代料等价合并、木桶效应取 min），
    区别在"可用量"不只看现货，还叠加"计划出货日（需求日）前能到货的在途 PO 量"——
    该子件的（确定/估算）到货日 `full_arrivals.get(component_id)` ≤ ship 才计入其在途量，
    与 kit_date/no_feedback 判定使用同一份到货日估算，口径自洽。

    `full_arrivals` 须传入**净额抵扣前**（drop_covered 之前）的 mat.arrivals——现货已覆盖
    的子件仍需要知道其到货日以判断是否"需求日前已到"，不能因为已被现货覆盖就丢失该信息。

    已知边界（保守，不会高估）：替代料本身不参与 `estimate_material_arrivals`（避免幻影组件
    误查 SRM，见 assess_supply_risk 注释），故 `full_arrivals` 恒不含替代料料号——替代料的
    在途量在本函数里不会被计入（只计其现货），只有主料一侧的到货日估算生效。

    Returns: (可齐套套数, 瓶颈子件料号)；无直接子件或任一子件单机用量非正 → (None, None)。
    """
    groups = _substitute_groups(bom, so.item_code)
    direct = [row for row in bom
             if row.product_id == so.item_code and not row.is_substitute]
    if not direct:
        return None, None

    def _avail(component_id: str) -> float:
        avail = float(inventory.get(component_id, 0) or 0)
        arrival = full_arrivals.get(component_id)
        if arrival is not None and arrival <= ship:
            avail += float(purchase_orders.get(component_id, 0) or 0)
        return avail

    best_qty: int | None = None
    best_material: str | None = None
    for row in direct:
        if row.qty_per_unit <= 0:
            return None, None   # 数据异常，无法计算，不以 0 冒充
        total = _avail(row.component_id) + sum(_avail(s) for s in groups.get(row.component_id, []))
        possible = int(total // row.qty_per_unit)
        if best_qty is None or possible < best_qty:
            best_qty, best_material = possible, row.component_id
    return best_qty, best_material


def assess_supply_risk(so: SalesOrder, bom: list, srm_deliveries: list, *,
                       today: date, params: ForecastParams | None = None,
                       inventory: dict | None = None,
                       material_commitments: dict[str, list[tuple[date, float]]] | None = None,
                       purchase_orders: dict[str, float] | None = None,
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

    PO 在途数据（`purchase_orders`={material_id→在途未清量}，功能批1，姚祖怡 07-23）：仅当
    传入时附加计算 `component_status`（#12）与 `demand_kittable_qty`（#14，另需 inventory +
    净额开关 ON）；缺省 None → 两者恒为空/None，零漂移，不影响既有四色/kittable_qty 判定。
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
    full_arrivals = dict(mat.arrivals)   # 净额抵扣前快照，供 #14 需求日可齐套使用（见下）
    period_match = _period_match_for_so(so, bom, ship, material_commitments) if had_bom else {}
    # C-1（sc8-baoguan-substitute-partial-kit）：替代料分组信息，纯展示用，不受净额开关影响。
    substitute_groups = _substitute_groups(bom, so.item_code) if had_bom else {}
    # ③ 料品名称（功能批1）：料号→品名，纯展示，取自 BOM，不受净额/PO 开关影响。
    component_names = _component_names(bom) if had_bom else {}
    gross = _gross_need(so, bom) if had_bom else {}

    # 现货净额（开关默认关；关时不改任何行为）；C-2 可齐套套数与净额同一入口（design.md D4）：
    # 开关 OFF 或无 inventory 时三者恒为 None，零漂移。
    kittable_qty = kittable_bottleneck = kittable_shortfall = None
    demand_kittable_qty = demand_kittable_bottleneck = None
    net_inventory_active = bool(inventory and had_bom and config.net_inventory_enabled())
    if net_inventory_active:
        covered = _covered_by_stock(so, bom, inventory)
        if covered:
            mat = _drop_covered(mat, covered)
        kittable_qty, kittable_bottleneck, kittable_shortfall = _kittable_qty(so, bom, inventory)
        # #14 需求日可齐套数量：同 C-2 前置 + 另需 purchase_orders（功能批1）。
        if purchase_orders is not None:
            demand_kittable_qty, demand_kittable_bottleneck = _demand_kittable_qty(
                so, bom, inventory, purchase_orders, full_arrivals, ship)

    # #12 子件供给状态全展示：独立于净额开关，只要传了 purchase_orders 即计算（功能批1）。
    # material_commitments 一并传入以计算 confirmed_batches（#18-a/b，队列 #139）。
    # inventory 仅当净额开关生效时传入（④可用现货数量/⑥缺口数量，队列 #152），与
    # kittable_qty 等既有字段同一开关同一语义，开关关闭时两个新字段恒为 None。
    component_status = (_component_supply_status(
            mat, gross, component_names, purchase_orders, material_commitments,
            inventory=inventory if net_inventory_active else None)
        if had_bom and purchase_orders is not None else [])

    if not had_bom:
        risk, action = _classify(None, None, False, p, 0, None, None, False)
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
            component_names=component_names, component_status=component_status,
            demand_kittable_qty=demand_kittable_qty,
            demand_kittable_bottleneck=demand_kittable_bottleneck,
        )

    kit_date = max(mat.arrivals.values())      # 齐料日 = 关键路径最晚到货（含无答复估算）
    gap_days = (kit_date - ship).days

    # 仅"有确定承诺"子件（剔除无答复）的齐料/缺口/瓶颈 → 真延期判定依据
    nf_set = set(mat.no_feedback_materials)
    confirmed = {m: d for m, d in mat.arrivals.items() if m not in nf_set}
    confirmed_kit = max(confirmed.values()) if confirmed else None
    confirmed_gap = (confirmed_kit - ship).days if confirmed_kit is not None else None
    confirmed_bottleneck = (max(confirmed, key=confirmed.get) if confirmed else None)

    # 无答复子件明细（判据说明 V2 答复2）：料号+毛需求量+估算到货日，供看板展示"预计齐套依据"。
    no_feedback_detail = [
        NoFeedbackDetail(component_id=m, qty=gross.get(m, 0.0), estimated_arrival=mat.arrivals[m],
                        component_name=component_names.get(m, ""))
        for m in mat.no_feedback_materials
    ]

    bottleneck_is_unanswered = mat.bottleneck_material in nf_set
    risk, action = _classify(gap_days, confirmed_gap, True, p, len(mat.no_feedback_materials),
                             mat.bottleneck_material, confirmed_bottleneck,
                             bottleneck_is_unanswered)
    # C-2：部分齐套不改变四色判定（risk 已由 _classify 定），只在建议动作里附加提示。
    if kittable_qty is not None and kittable_qty > 0:
        action = f"{action}；可先齐 {kittable_qty} 套"
    return BaoguanRow(
        so_id=so.so_id, product_id=so.item_code, product_name=so.item_name,
        customer_name=so.customer_name, qty=so.qty, ship_date=ship,
        kit_date=kit_date, gap_days=gap_days, risk=risk,
        bottleneck_material=mat.bottleneck_material,
        no_feedback_materials=mat.no_feedback_materials,
        no_feedback_detail=no_feedback_detail,
        component_count=len(mat.arrivals), has_bom=True, action=action,
        confirmed_kit_date=confirmed_kit, confirmed_gap_days=confirmed_gap,
        confirmed_bottleneck=confirmed_bottleneck,
        period_match=period_match, substitute_groups=substitute_groups,
        kittable_qty=kittable_qty, kittable_bottleneck=kittable_bottleneck,
        kittable_shortfall=kittable_shortfall,
        component_names=component_names, component_status=component_status,
        demand_kittable_qty=demand_kittable_qty,
        demand_kittable_bottleneck=demand_kittable_bottleneck,
    )


def _resolve_priority_order(
    material_id: str, order_indices: list[int], orders: list[SalesOrder], priority_resolver,
) -> list[int]:
    """排出竞争同一料号现货的订单处理顺序（#118 批2·优先级分配引擎首版，队列
    #147④/#141 衍生，2026-07-29 Paul 拍板）。返回值是 `orders` 列表下标，不是 so_id——

    **真实数据踩坑（2026-07-29 部署后发现，本函数第二版）**：真实数据里同一张预测
    订单（FO）文档下的多个行项**共享同一个 `so_id`**（`fo_to_sales_orders` 按
    `fo.fo_id`——文档级单号——赋值，S02Y.0210 的 8 条真实需求行 so_id 全部是
    "FO2026070001"）。首版用 `so.so_id` 当字典键/去重键，导致 8 个订单对象被
    静默折叠成 1 个，跨订单竞争检测形同虚设（真实验证 kq 恒为 1153、risk 恒为
    🟢，逐级扣料完全没生效）。改用**下标**定位具体行，任何场景下保证唯一。

    真实案例（S02Y.0210）：同一料号被 3 张需求单（600/400/500 套，出货
    07-20/08-20/09-20）共同争用现货 1,153 件，此前 `_kittable_qty`/`_covered_by_stock`
    各自独立读取现货**全量**，3 行都判"齐套"，但 600+400+500=1,500 > 1,153，
    实际第三行不该判齐——姚祖怡 07-29 指出"必须逐级扣料"。

    优先级来源：`priority_resolver`（B4 框架桩，shortage-baoguan-criteria-v3，2026-07-10
    定义，签名 `(material_id, competing_so_ids) -> 按优先级排序的 so_id 列表`——接口
    粒度仍是 so_id，无法区分同一 so_id 下的多个行项；若多个下标共享同一 so_id，
    按其在 `orders` 中的原始相对顺序作二级排序）——真实 PMC 优先级表（#15）尚未
    上线，**临时用出货日期升序代替**（谁出货早谁先占，Paul 07-29 原话："先用出货
    日期早晚当临时优先级，等#15真正的PMC优先级表上线后再替换掉这条临时规则"）。
    #15 上线后传入真实 `priority_resolver` 即自动切换，本兜底届时不再生效。
    """
    if priority_resolver is not None:
        so_ids = [orders[i].so_id for i in order_indices]
        ordered_so_ids = priority_resolver(material_id, so_ids)
        rank = {so_id: i for i, so_id in enumerate(ordered_so_ids)}
        return sorted(order_indices, key=lambda i: (rank.get(orders[i].so_id, len(rank)), i))
    return sorted(order_indices, key=lambda i: (orders[i].required_date, i))


def _allocate_sequential_inventory(
    orders: list[SalesOrder], bom: list, inventory: dict[str, float],
    priority_resolver=None,
) -> list[dict[str, float]]:
    """按优先级顺序（见 `_resolve_priority_order`）从共享现货池依次扣减各料号毛需求，
    返回与 `orders` 位置一一对应的列表——`effective[i]` 是第 i 张订单在其处理
    顺位时点看到的有效库存快照（#118，2026-07-29）。

    **返回类型改为按下标对齐的 list（原第一版是 {so_id: ...} 的 dict）**：真实数据
    里 so_id 在同一 FO 文档的多个行项间会重复，dict 会把它们静默去重合并成一条，
    详见 `_resolve_priority_order` 文档串的踩坑记录。

    只对"同一料号被 2 个及以上订单同时需要"的场景生效——占用仅按需求数量、不含
    富余（Paul 07-28 拍板口径），排在后面的订单只能拿到前面订单消耗后的剩余部分。
    未被竞争触碰的物料键（含替代料、单一订单独占的物料）**原样保留调用方传入的
    `inventory` 全量值**，不受影响——不改变既有 `_covered_by_stock`/`_kittable_qty`/
    `_demand_kittable_qty` 对这些物料的既有行为，只在真正存在跨订单争用时才生效。

    已知边界（本版范围，未做）：替代料等价合并（C-1）不参与本次跨订单分配——
    `_gross_need` 本就不含替代料行，故替代料的现货池不会被本函数扣减；多个订单
    若都靠"主料+替代料"合并勉强齐套，本版可能对主料分配保守（因为看不到替代料
    也在被同一批订单消耗），但不会高估——留独立后续任务，需先有真实替代料+多单
    竞争的场景再评估是否需要处理。
    """
    gross_list = [_gross_need(so, bom) for so in orders]
    competitors: dict[str, list[int]] = {}
    for idx, gross in enumerate(gross_list):
        for material, need in gross.items():
            if need <= 0:
                continue
            competitors.setdefault(material, []).append(idx)

    effective: list[dict[str, float]] = [dict(inventory) for _ in orders]

    for material, idxs in competitors.items():
        if material not in inventory or len(idxs) < 2:
            continue   # 无库存数据或无跨订单争用 → 各行沿用原始 inventory 全量，不分配
        ordered = _resolve_priority_order(material, idxs, orders, priority_resolver)
        pool = float(inventory.get(material, 0.0))
        for idx in ordered:
            effective[idx][material] = max(pool, 0.0)
            need = gross_list[idx].get(material, 0.0)
            pool -= min(max(pool, 0.0), need)
    return effective


def build_dashboard(orders: list[SalesOrder], bom: list, srm_deliveries: list, *,
                    today: date, params: ForecastParams | None = None,
                    inventory: dict | None = None,
                    material_commitments: dict[str, list[tuple[date, float]]] | None = None,
                    priority_resolver=None,
                    purchase_orders: dict[str, float] | None = None,
                    ) -> list[BaoguanRow]:
    """对全部成品行生成保供预警，按风险降序（🔴→🟡→🟢）、缺口天数降序排列。

    `inventory`（{material_id→白名单仓可用量}）仅当 `SC8_NET_INVENTORY=on` 生效（默认关，零漂移）。
    `material_commitments`（B2 周期累计供需匹配，见 assess_supply_risk）缺省 None 时
    各行 `period_match` 恒为空字典，不影响四色/缺口既有逻辑。

    `priority_resolver`（B4 框架桩，shortage-baoguan-criteria-v3，2026-07-10 会议定稿；
    **2026-07-29 起接线生效，见 #118**）：签名 `(material_id: str, competing_so_ids: list[str])
    -> list[str]`（按 PMC 月度优先级排序后的 so_id 列表），用于"共用子件现货按优先级占用"
    （同一物料被多个成品行同时竞争时谁先扣现货）。真实 PMC 优先级数据源（#15）尚未上线，
    缺省 None 时**临时按出货日期升序**代替（谁出货早谁先占，Paul 07-29 拍板，见
    `_resolve_priority_order`）；传入真实 resolver 后自动切换，本兜底不再生效。

    `purchase_orders`（{material_id→在途未清量}，功能批1，姚祖怡 07-23）：驱动 #12 子件
    供给状态全展示 + #14 需求日可齐套数量，缺省 None 时两者恒为空/None，零漂移。
    """
    # #118（2026-07-29，Paul 拍板）：现货是跨订单共享的池子，同一物料被多张需求单
    # 同时争用时必须按优先级顺序依次扣减，不能让每一行各自独立看到"全量库存"
    # （真实案例 S02Y.0210：3 张单合计需求 1,500 > 现货 1,153，此前 3 行都误判齐套）。
    # 仅当净额开关打开且传了 inventory 时才分配；否则行为与改造前完全一致（零漂移）。
    effective_inventory = None
    if inventory and config.net_inventory_enabled():
        effective_inventory = _allocate_sequential_inventory(orders, bom, inventory,
                                                              priority_resolver)
    rows = [assess_supply_risk(
                so, bom, srm_deliveries, today=today, params=params,
                inventory=(effective_inventory[i] if effective_inventory is not None
                          else inventory),
                material_commitments=material_commitments, purchase_orders=purchase_orders)
            for i, so in enumerate(orders)]
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


# ── HTML 看板渲染（独立可在浏览器打开、自包含交互看板：筛选/搜索/排序/导出 Excel/KPI 动画）──
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
.nfd{margin-top:8px;font-size:12px;color:var(--warn)}
.act{margin-top:10px;font-size:13px;background:var(--surface2);border-radius:8px;padding:8px 10px}
.foot{margin-top:14px;font-size:12px;color:var(--text3);line-height:1.6}
.pager{display:flex;align-items:center;gap:10px;margin:8px 0;font-size:13px;color:var(--text2);flex-wrap:wrap}
.pager button{height:30px;padding:0 12px;border:1px solid var(--border);border-radius:8px;background:var(--surface);color:var(--text);font-size:13px;cursor:pointer}
.pager button:hover:not(:disabled){background:var(--surface2)}
.pager button:disabled{opacity:.4;cursor:default}
.legend{display:none;background:var(--surface2);border-radius:10px;padding:14px 16px;margin-bottom:14px;font-size:13px;line-height:1.7}
.legend.show{display:block}
.legend h4{margin:0 0 8px;font-size:14px}
.legend p{margin:8px 0}
.legend table{width:100%;border-collapse:collapse;margin:6px 0}
.legend th,.legend td{padding:5px 8px;text-align:left;border-bottom:1px solid var(--border);font-size:12px}
.cst{margin-top:8px;font-size:12px}
/* BOM 缺口物料清单八字段整体呈现（队列 #152，姚祖怡三次重申后改为真表格）：表格对齐 +
   子件上下行对齐 + 内容过长自动换行（word-break，不截断/不省略）。 */
.cst-table{width:100%;border-collapse:collapse;margin-top:6px;table-layout:fixed}
.cst-table th,.cst-table td{padding:5px 6px;text-align:left;vertical-align:top;font-size:12px;border-bottom:1px solid var(--border);word-break:break-word;white-space:normal}
.cst-table th{color:var(--text2);font-weight:500;white-space:nowrap}
/* 队列 #212（姚祖怡 07-31 补充问题1）：cst-tag 此前强制 white-space:nowrap，
   confirmed_no_transit 状态文案（含"（异常，如实展示）"注释）明显长于其余三态，
   在 table-layout:fixed 的窄列（状态列约占表宽 1/8）里溢出、视觉上盖住右侧
   "可用现货数量"列内容——这正是他红圈标出"看不清楚"的两个字段。改为允许换行
   （继承 .cst-table td 既有的 white-space:normal/word-break），并把注释性文字
   拆到独立的 .cst-tag-note 行单独展示，不再挤进同一个不可换行的徽标里。 */
.cst-tag{font-size:11px;padding:1px 7px;border-radius:6px;white-space:normal;display:inline-block;max-width:100%}
.cst-tag.no{background:var(--danger-bg);color:var(--danger)}
.cst-tag.un{background:var(--gap-bg);color:var(--gap)}
.cst-tag.co{background:var(--ok-bg);color:var(--ok)}
.cst-tag.cn{background:var(--warn-bg);color:var(--warn)}
.cst-tag-note{font-size:11px;color:var(--text3);margin-top:2px}
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
// 姚祖怡 07-26 V6 回件 #1：""在途""表述有歧义，统一改为""存在未交订单""口径的四态描述
// （无未交订单无答交/无未交订单有答交/有未交订单已答交/有未交订单无答交），均由既有
// STATUS_* 字段派生，不改判定本身，仅重述文案。
const CST_LABEL={no_transit:'无未交订单无答交',transit_unconfirmed:'有未交订单无答交',
  transit_confirmed:'有未交订单已答交',confirmed_no_transit:'无未交订单有答交'};
// 队列 #212：解释性注释（"数据口径不一致，如实展示不隐藏"）此前挤在 CST_LABEL 徽标
// 文本里，是长文案在窄列溢出的直接原因——拆成独立小字注释（cst-tag-note），徽标本身
// 与其余三态保持同等长度。
const CST_NOTE={confirmed_no_transit:'异常，如实展示'};
const CST_CLS={no_transit:'no',transit_unconfirmed:'un',transit_confirmed:'co',confirmed_no_transit:'cn'};
// 分页（②，功能批1）：10/50/100/200 行/页，初始 10 条/页（姚祖怡判据说明V2答复1明确要求）
var state={f:'all',q:'',sort:'gap',page:1,pageSize:10};

function cls(r){return CLS[r.risk]||'danger';}
// 队列#147续（姚祖怡07-29举证后Paul拍板）：分级/徽标改用 r.gap（全量口径，含无答复
// 子件按90天保守估算），不再只看 r.cg（仅确定承诺子件）——不能因为子件"还没答复"
// 就把风险显示得比全量估算更轻。r.bn（全量瓶颈）若命中 r.nfd 无答复清单，说明这个
// 数字是"保守估算"而非"真实确认"，措辞相应改为"保守预警"而非"确定"，不把猜测
// 包装成事实。
function bottleneckUnanswered(r){
 return (r.nfd||[]).some(function(d){return d.id===r.bn;});
}
function gapText(r){
 if(!r.hasBom)return'无 BOM';
 if(r.risk==='gap')return'待催 · '+r.nf+' 子件未答复';
 if(r.gap==null)return r.risk==='grn'?'按期':'—';
 if(r.gap<=0)return'确定提前 '+(-r.gap)+' 天';
 if(bottleneckUnanswered(r))return'保守预警 +'+r.gap+' 天（未答复估算）';
 return'确定齐料晚 +'+r.gap+' 天';
}

function subsText(r,materialId){
 var subs=(r.subs||{})[materialId];
 return (subs&&subs.length)?'（含替代料 '+subs.map(esc).join('、')+'）':'';
}

// ③ 料品名称（功能批1）：任意料号旁按 r.cn（料号→品名）查表显示品名，无品名数据时不显示。
function nm(r,materialId){
 var n=(r.cn||{})[materialId];
 return n?'（'+esc(n)+'）':'';
}

// 无答复子件明细（判据说明 V2 答复2）：料号+毛需求量+估算到货日，回答"预计齐套依据是什么"。
function nfdText(r){
 if(!r.nfd||!r.nfd.length)return'';
 var items=r.nfd.map(function(d){return '<span class="mono">'+esc(d.id)+'</span>'+(d.name?'（'+esc(d.name)+'）':'')+'×'+fmt(d.qty)+'（估到货 '+esc(d.eta)+'）';}).join('、');
 return '<div class="nfd">⚠ 按无答复估算（非确定承诺）：'+items+'</div>';
}

// 答交数量/答交日期（⑦⑧，队列 #152，姚祖怡三次重申后根治）：唯一取值来源＝s.cb
// （SRM 供应计划-供应计划排产逐期确认明细，见 sources.load_material_commitments）。
// s.cb 为空时**如实显示"无"**——不再回退 s.cd（旧 /purchase/answer 整单口径，姚祖怡
// 07-29 指认取错源头的正是这个字段：SRM 供应计划板对"7 天前数据"有查询限制，一旦
// s.cb 因此取不到，旧写法会静默顶替上场，看起来像是"修好了却还在犯同一个错"，这才是
// 三次重申的根因）。去掉"件·答交"之间的分隔符（姚祖怡要求）：8 个字段各自独立成列，
// 不再拼接在一行文本里，天然无需分隔符。
function answerQtyText(s){return (s.cb&&s.cb.length)?s.cb.map(function(b){return fmt(b.q);}).join('、'):'无';}
function answerDateText(s){return (s.cb&&s.cb.length)?s.cb.map(function(b){return esc(b.d);}).join('、'):'无';}

// #12/#152 BOM 缺口物料清单八字段整体呈现（姚祖怡三次重申：07-26 V6 #18-a → 07-28
// 判例回件 → 07-29 第三次），真表格渲染——表格对齐、子件上下行对齐、内容过长自动
// 换行（CSS word-break，见 .cst-table）。八字段：①料号 ②品名 ③状态 ④可用现货数量
// ⑤本项目需求数量 ⑥缺口数量 ⑦答交数量 ⑧答交日期；④⑥无库存数据时显示"—"（不以 0
// 冒充，同 kq/dkq 等既有字段约定），⑦⑧未答交时显示"无"（姚祖怡原话）。
function componentStatusHtml(r){
 if(!r.cst||!r.cst.length)return'';
 var rows=r.cst.map(function(s){
  var label=CST_LABEL[s.st]||s.st;
  var note=CST_NOTE[s.st];
  var tagCls=CST_CLS[s.st]||'no';
  var avail=s.aq==null?'—':fmt(s.aq);
  var gapq=s.gq==null?'—':fmt(s.gq);
  return '<tr><td class="mono">'+esc(s.id)+'</td><td>'+(s.name?esc(s.name):'—')+'</td>'
    +'<td><span class="cst-tag '+tagCls+'">'+label+'</span>'
    +(note?'<div class="cst-tag-note">'+esc(note)+'</div>':'')+'</td>'
    +'<td>'+avail+'</td><td>'+fmt(s.qty)+'</td><td>'+gapq+'</td>'
    +'<td>'+answerQtyText(s)+'</td><td>'+answerDateText(s)+'</td></tr>';
 }).join('');
 return '<div class="cst"><div class="cov-h"><span>BOM 缺口物料清单</span></div>'
   +'<table class="cst-table"><thead><tr>'
   +'<th>料号</th><th>品名</th><th>状态</th><th>可用现货数量</th>'
   +'<th>本项目需求数量</th><th>缺口数量</th><th>答交数量</th><th>答交日期</th>'
   +'</tr></thead><tbody>'+rows+'</tbody></table></div>';
}

function card(r){
 var c=cls(r),covered=r.comp-r.nf,pct=r.comp?Math.round(covered/r.comp*100):0;
 var cov=r.comp?'<div class="cov"><div class="cov-h"><span>子件承诺覆盖</span><span>'+covered+' / '+r.comp+' 命中 · '+r.nf+' 未答复</span></div><div class="track"><div class="fill" style="width:'+pct+'%"></div></div></div>':'';
 // 队列#147续（2026-07-29，姚祖怡二次举证后 Paul 拍板改口径）：头部"出货→齐料"
 // 日期/瓶颈与徽标（gapText()，现改用 r.gap 全量口径）统一改回都用 r.kit/r.bn
 // （全量口径，含无答复估算，天然取两套口径中较晚/较严重的一个）——badge 与
 // headline 同源即不会再对不上。r.ckit/r.cbn（仅确定承诺口径）仍保留在数据里
 // 供 action 文案区分"确定"/"保守预警"措辞，但不再是头部展示的默认来源。
 var bn=r.bn?'<span>瓶颈 <span class="mono">'+esc(r.bn)+'</span>'+nm(r,r.bn)+subsText(r,r.bn)+'</span>':'';
 // C-2：可齐套套数（kq==null → 现货数据不可用，不显示徽标，不以 0 冒充）
 var kit=(r.kq==null)?'':'<span class="badge" title="'+(r.kbn?('卡在子件 '+esc(r.kbn)+nm(r,r.kbn)+subsText(r,r.kbn)+'、还差 '+fmt(r.ksf)+' 件'):'')+'">可齐套 '+fmt(r.kq)+' / '+fmt(r.qty)+'</span>';
 // #14 需求日可齐套数量（dkq==null → 无 PO 在途数据，不显示徽标，不以 0 冒充）
 var dk=(r.dkq==null)?'':'<span class="badge" title="'+(r.dkbn?('需求日瓶颈 '+esc(r.dkbn)+nm(r,r.dkbn)):'')+'">需求日可齐套 '+fmt(r.dkq)+' / '+fmt(r.qty)+'</span>';
 return '<div class="card"><div class="card-h"><div><span class="id">'+esc(r.id)+'</span><span class="nm">'+esc(r.name)+'</span></div><span class="gap '+c+'">'+gapText(r)+'</span></div>'
  +'<div class="meta">客户 '+(esc(r.cust)||'—')+' · 数量 '+fmt(r.qty)+(kit?' · '+kit:'')+(dk?' · '+dk:'')+'</div>'
  +'<div class="strip"><span>出货 <b>'+esc(r.ship)+'</b></span><span>→</span><span>齐料 <b class="kd '+c+'">'+(r.kit?esc(r.kit):'—')+'</b></span>'+bn+'</div>'
  +cov+nfdText(r)+componentStatusHtml(r)+'<div class="act">建议：'+esc(r.action)+'</div></div>';
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
 for(var i=0;i<bs.length;i++){bs[i].onclick=function(){state.f=this.getAttribute('data-f');state.page=1;renderFbtns();render();};}
}

// 分页控件（②，功能批1）：渲染到 pagerTop/pagerBottom 两处，共享同一状态。
function renderPager(total,totalPages){
 var html='';
 if(total>0){
  html='<button type="button" class="pgPrev"'+(state.page<=1?' disabled':'')+'>‹ 上一页</button>'
    +'<span>第 '+state.page+' / '+totalPages+' 页 · 共 '+total+' 条</span>'
    +'<button type="button" class="pgNext"'+(state.page>=totalPages?' disabled':'')+'>下一页 ›</button>';
 }
 ['pagerTop','pagerBottom'].forEach(function(id){
  var el=$(id);if(!el)return;
  el.innerHTML=html;
  var prev=el.querySelector('.pgPrev'),next=el.querySelector('.pgNext');
  if(prev)prev.onclick=function(){if(state.page>1){state.page--;render();}};
  if(next)next.onclick=function(){if(state.page<totalPages){state.page++;render();}};
 });
}

function render(){
 var l=view();
 var totalPages=Math.max(1,Math.ceil(l.length/state.pageSize));
 if(state.page>totalPages)state.page=totalPages;
 if(state.page<1)state.page=1;
 var start=(state.page-1)*state.pageSize;
 var pageItems=l.slice(start,start+state.pageSize);
 $('cards').innerHTML=pageItems.length?pageItems.map(card).join(''):'<div class="empty">没有匹配的成品</div>';
 $('cnt').textContent=(pageItems.length?'显示 '+(start+1)+'-'+(start+pageItems.length):'显示 0')+' / '+l.length+' 个成品（共 '+DATA.length+' 条）';
 renderPager(l.length,totalPages);
}

// 明细导出 Excel（功能批1；姚祖怡 07-26 V6 #13 增强：每个成品行下追加子件明细展开行）：
// 零依赖，Excel 可直接打开的 HTML-table .xls 文件（同导出范围=当前筛选全集，非仅当前页）。
// 子件明细列取自 r.cst（BOM 缺口物料清单），成品主行这几列留空、子件行前 11 列同样留空——
// 单靠"前 11 列是否留空"这一独立列分组即可区分"项目行"与其下的"问题物料明细行"（姚祖怡
// 原话"需要能区分"），姚祖怡 07-28 判例回件 #17 要求去掉子件料号前的层级箭头符号，
// 去掉后层级信息不丢失——前 11 列留空本身就是分组标识，箭头只是冗余视觉提示。
function exportExcel(){
 var l=view();
 var hdr=['成品','品名','客户','数量','计划出货日','齐料日','缺口天数','子件数','未答复','瓶颈','风险',
   '子件料号','子件品名','子件状态','可用现货数量','本项目需求数量','缺口数量','未交订单量','答交数量','答交日期'];
 var thead='<tr>'+hdr.map(function(h){return '<th>'+esc(h)+'</th>';}).join('')+'</tr>';
 var tbody='';
 l.forEach(function(r){
  var main=[r.id,r.name,r.cust,r.qty,r.ship,r.kit||'',r.gap==null?'':r.gap,r.comp,r.nf,r.bn,RT[r.risk],
    '','','','','','','','',''];
  tbody+='<tr>'+main.map(function(c){return '<td>'+esc(c)+'</td>';}).join('')+'</tr>';
  (r.cst||[]).forEach(function(s){
   // 可用现货数量/缺口数量（④⑥，队列 #152）与答交数量/答交日期（⑦⑧，#18-a/b，与
   // 卡片视图 answerQtyText/answerDateText 同源、同一"无数据显示无/—"约定）。
   var avail=s.aq==null?'':s.aq;
   var gapq=s.gq==null?'':s.gq;
   var stLabel=(CST_LABEL[s.st]||s.st)+(CST_NOTE[s.st]?'（'+CST_NOTE[s.st]+'）':'');
   var sub=['','','','','','','','','','','',
     s.id, s.name, stLabel, avail, s.qty, gapq, s.tq, answerQtyText(s), answerDateText(s)];
   tbody+='<tr>'+sub.map(function(c){return '<td>'+esc(c)+'</td>';}).join('')+'</tr>';
  });
 });
 var html='﻿<html><head><meta charset="UTF-8"></head><body><table border="1">'+thead+tbody+'</table></body></html>';
 var blob=new Blob([html],{type:'application/vnd.ms-excel'});
 var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='保供预警_'+META.today+'.xls';
 document.body.appendChild(a);a.click();document.body.removeChild(a);URL.revokeObjectURL(a.href);
}

renderKpis();renderFbtns();render();
$('q').addEventListener('input',function(e){state.q=e.target.value;state.page=1;render();});
$('sort').addEventListener('change',function(e){state.sort=e.target.value;state.page=1;render();});
var xb=$('xlsx');if(xb)xb.addEventListener('click',exportExcel);
var ps=$('pageSize');if(ps)ps.addEventListener('change',function(e){state.pageSize=parseInt(e.target.value,10)||10;state.page=1;render();});
// ④ 图例入界面：判据说明面板由 Python 侧 render_legend() 静态生成内容，此处只做展开/收起。
var lb=$('legendBtn');if(lb)lb.addEventListener('click',function(){var lp=$('legendPanel');if(lp)lp.classList.toggle('show');});
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
        # 确定口径齐料日/瓶颈（队列 #147）：与 cg 同源，供前端卡片头部优先展示，
        # 避免头部日期/瓶颈（全量口径 kit/bn）与徽标（确定口径 cg）对不上；
        # 无确定承诺子件时恒为 None/""，前端回退展示 kit/bn（不丢已有行为）。
        "ckit": r.confirmed_kit_date.isoformat() if r.confirmed_kit_date else None,
        "cbn": r.confirmed_bottleneck or "",
        "risk": RISK_CODE.get(r.risk, "red"), "hasBom": r.has_bom, "action": r.action,
        # C-1（含替代料的主料 → 替代料料号列表；无替代料时为空对象，前端不显示标注）
        "subs": r.substitute_groups,
        # C-2（None → 前端不显示"可齐套"徽标，不以 0 冒充）
        "kq": r.kittable_qty, "kbn": r.kittable_bottleneck, "ksf": r.kittable_shortfall,
        # 无答复子件明细（判据说明 V2 答复2）：[{"id":料号,"qty":毛需求量,"eta":估算到货日,"name":品名}]；
        # 无无答复子件时为空列表，前端不显示明细区块。
        "nfd": [{"id": d.component_id, "qty": d.qty, "eta": d.estimated_arrival.isoformat(),
                "name": d.component_name}
               for d in r.no_feedback_detail],
        # ③ 料品名称（功能批1）：{子件料号: 品名}，供前端在任意料号旁查表显示品名。
        "cn": r.component_names,
        # #12 子件供给状态全展示（功能批1）：无 purchase_orders 数据时为空列表。
        # aq/gq（④可用现货数量/⑥缺口数量，队列 #152）：仅净额开关生效时非 None，
        # 见 _component_supply_status；gap_qty≤0 的子件已在该函数内被过滤，不会
        # 出现在这里。cb（#18-a/b，队列 #139）：答交数量累计明细
        # [{"d":确认日期,"q":确认数量},...]，按日期升序、累计满足本行毛需求为止；
        # cd（旧口径，来自 /purchase/answer 整单答交，姚祖怡 07-29 指认其为取错源头
        # 的字段，队列 #152）**只保留供内部排障参考，前端不再用它回填 cb 为空时的
        # 展示**——cb 为空时前端如实显示"无"（见 answerQtyText/answerDateText），
        # 不再静默顶替成这个已知不准的旧数值。
        "cst": [{"id": s.component_id, "name": s.component_name, "qty": s.qty_needed,
                "st": s.status, "tq": s.transit_qty,
                "aq": s.available_qty, "gq": s.gap_qty,
                "cd": s.confirmed_date.isoformat() if s.confirmed_date else None,
                "cb": [{"d": d.isoformat(), "q": q} for d, q in s.confirmed_batches]}
               for s in r.component_status],
        # #14 需求日可齐套数量（功能批1，None → 前端不显示徽标，不以 0 冒充）
        "dkq": r.demand_kittable_qty, "dkbn": r.demand_kittable_bottleneck,
    }


def render_legend(params: ForecastParams | None = None) -> str:
    """看板内嵌图例面板（④ 功能批1，姚祖怡 07-23）：四色判据 + 无答复估算依据 + 现货净额/
    部分齐套/子件供给状态口径说明，供采购一线在看板内直接核对，不必外挂文档。

    内容与《保供看板状态图例与判据说明-2026-07-22.md》一致，天数等随参数动态生成
    （不会因为 config 调整而与文档失步，如 NO_FEEDBACK_LEAD_DAYS 30→90 那次校准）。
    """
    p = params or config.default_params()
    return (
        '<h4>四色判据</h4>'
        '<table><tr><th>图标</th><th>名称</th><th>判据</th></tr>'
        '<tr><td>🔴</td><td>真延期</td><td>存在已有真实供应商承诺的子件，其承诺到货日晚于计划出货日 &gt;3 天</td></tr>'
        '<tr><td>🟠</td><td>待催</td><td>无真延期信号，但存在供应商未答复（无携客云承诺记录）的子件——齐料日无法确定，需催答交</td></tr>'
        '<tr><td>🟡</td><td>偏紧</td><td>已有真实承诺的子件，其到货日晚于计划出货日 1-3 天</td></tr>'
        '<tr><td>🟢</td><td>按期</td><td>全部子件均有真实承诺，且齐料日 ≤ 计划出货日</td></tr></table>'
        '<p>分级只看"已有真实承诺"子件的缺口，剔除"无答复"估算——即便同时存在未答复子件，'
        '只要有一个已确定承诺的子件已经延期，也优先判 🔴（确定信号优先于不确定信号）。</p>'
        f'<p><b>无答复子件齐料日估算</b>（问题5）：无携客云承诺交期的子件，按 '
        f'<code>max(计划出货日, 今天) + {p.no_feedback_lead_days} 天</code>（无反馈提前期，'
        f'参数版本 {_html.escape(p.param_version)}）估算，仅供参考排期，非确定交期。</p>'
        '<p><b>现货净额</b>：开关打开时，统计卓品自建库存 6 个白名单仓'
        '（WW01/ZP01/ZP21/ZP22/ZP02/ZP23）可用库存（ERP 口径 AvailQty），'
        '≥ 该子件毛需求视为已齐、退出待催/瓶颈判定；不参与四色判定基线本身。</p>'
        '<p><b>可齐套套数 / 需求日可齐套数量</b>：全部直接子件逐个 floor(可用量 ÷ 单机用量)，'
        '取最小值（木桶效应）；含替代料的料位按主料+替代料现货合计。"需求日可齐套"额外把'
        '计划出货日前能到货的未交订单量计入可用量。两者均不改变四色判定，仅辅助参考。</p>'
        '<p><b>BOM 缺口物料清单</b>（原"子件供给状态"，姚祖怡 07-26 V6 回件统一措辞）：'
        '"未交订单"指有审核通过但尚未关闭的采购订单，交叉未交订单与供应商答交记录得出'
        '四态之一——无未交订单无答交 / 无未交订单有答交（异常，如实展示）/ 有未交订单已答交 / '
        '有未交订单无答交，逐条附"本项目需求数量"（预测订单数量×BOM子件用量）；'
        '纯展示，不影响四色/齐套判定。</p>'
    )


def render_html(rows: list[BaoguanRow], *, today: date,
                params: ForecastParams | None = None) -> str:
    """渲染保供预警看板为独立交互 HTML 页面（浏览器可直接打开；筛选/搜索/排序/分页/导出/图例）。"""
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
        + '<select class="sel" id="pageSize" aria-label="每页行数"><option value="10">10 行/页</option>'
        + '<option value="50">50 行/页</option><option value="100">100 行/页</option>'
        + '<option value="200">200 行/页</option></select>\n'
        + '<button class="btn" id="xlsx" type="button">导出 Excel</button>\n'
        + '<button class="btn" id="legendBtn" type="button">📖 图例</button></div>\n'
        + '<div class="legend" id="legendPanel">' + render_legend(p) + '</div>\n'
        + '<div class="cnt" id="cnt"></div>\n<div class="pager" id="pagerTop"></div>\n'
        + '<div class="cards" id="cards"></div>\n<div class="pager" id="pagerBottom"></div>\n'
        + f'<div class="foot">分级只看<b>有确定承诺</b>子件的齐料缺口：🔴 真延期（有承诺仍晚 &gt;3天）· 🟠 待催（子件未答复、无确定承诺，齐料待定）· 🟡 偏紧（确定晚 1-3天）· 🟢 按期。未答复子件齐料按 max(出货日, 今天)+{p.no_feedback_lead_days} 天估算（仅参考，不计入真延期）。本看板为内部保供运维用途，不对客。</div>\n'
        + '</div>\n<script>\n' + js + '\n</script></body></html>'
    )
