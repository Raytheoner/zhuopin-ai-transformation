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

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta

from zhuopin_platform.agents.kit_engine import explode_bom
from zhuopin_platform.shared_tools.models import ProductionPlan

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


def _shift_months(anchor: date, months: int) -> date:
    """自然月加减；目标月无该日时收敛到该月最后一天（1-31 推 1 个月 ⇒ 2-28/29）。

    收敛而不是抛错：调用点全部是「某某日往前/往后 N 个自然月」这类业务口径，
    2 月没有 31 号时业务上说的就是月末，不是一个错误输入。
    """
    idx = anchor.month - 1 + months
    year = anchor.year + idx // 12
    month = idx % 12 + 1
    return date(year, month, min(anchor.day, calendar.monthrange(year, month)[1]))


def ship_within_horizon(today: date, ship_date: date,
                        params: ForecastParams | None = None) -> bool:
    """出货日是否「在三个月内」—— 规则 1 与规则 2 的**唯一**分界判据。

    读法（本次落定，姚祖怡原话只说了「三个月内／不在三个月内」这两个词）：
      · 边界 ＝ `今天` 往后推 `rule1_horizon_months` 个**自然月**（月末收敛，见
        `_shift_months`），**含边界当天**（`<=`）；
      · **已过期的出货日（≤ 今天）恒判「在三个月内」** —— 它天然落在窗口里，
        且现行代码对这 38 行的结论本就与规则 2 逐字一致（#344 实测）。

    🔴 **为什么取「含边界」而不是「不含」**：两种读法只在边界当天那一批行上分歧，
    而「在三个月内」⇒ 走规则 2 ⇒ 起算点更晚 ⇒ **结论更保守**。他签认的是规则文本、
    不是这个边界的开闭；在他没说的地方，取偏保守那一侧，与 #344 design D3 同一原则。
    ⚠️ 已登记待其以判例确认（随采购部#19 的对照表，队列 §一 #402）。
    """
    p = params or config.default_params()
    return ship_date <= _shift_months(today, p.rule1_horizon_months)


def no_feedback_start_date(ship_date: date, today: date,
                           params: ForecastParams | None = None) -> date:
    """无答交启发式的**起算点**（姚祖怡 2026-08-18 书面签认的规则 1／规则 2）。

    返回值随后 `+ no_feedback_lead_days`（90）得到该子件的估算到货日。

      · **规则 1**（出货日**不在**三个月内）→ 出货日往前推 `rule1_months_back` 个自然月，
        取那个自然月的第 `rule1_start_day` 日（＝20 号）。他 08-18 原话确认的例子：
        「出货日是 12 月 5 日，往前推 3 个月是 9 月，起算点就是 **9 月 20 日**」。
      · **规则 2**（出货日**在**三个月内，含已过期）→ **原样保留现行口径** `max(出货日, 今天)`。

    🔴 **规则 2 这一支本次刻意不动，尽管实测它只是「部分覆盖」**：出货日在未来但仍在三个
    月内的那 24 行，现行是「出货日+90」而规则 2 逐字是「此时此刻+90」，现行更晚、偏保守。
    §四 #111 拍板 (a) 的标的是**规则 1**；把规则 2 顺手一起改，就是在一次上线里塞进两个
    自变量——那正是 #344 拒绝顺手改规则 1 时给出的理由，不能反过来自己犯。**已登记为独立
    待办**（本变更包 design D2 ／ 队列 §一 #401 收工回写）。

    ⚠️ **规则 1 的起算点允许早于今天，且刻意不向今天钳制**：出货日刚过三个月边界时，
    「前推 3 个月的 20 日」可能落在今天之前（例：今天 08-25、出货 11-30 ⇒ 起算 08-20）。
    钳到今天会让规则 1 在边界附近**静默退化成规则 2**，等于这条规则在最该生效的那批行上
    不生效；而不钳制时 `起算+90 ≈ 出货日`，估算到货日仍在未来，不会产生「到货日在过去」
    这种荒谬结论。
    """
    p = params or config.default_params()
    if ship_within_horizon(today, ship_date, p):
        return max(ship_date, today)
    anchor = _shift_months(ship_date.replace(day=1), -p.rule1_months_back)
    return date(anchor.year, anchor.month, p.rule1_start_day)


def _cumulative_confirmed_batches(
    commitments: list[tuple[date, float]], target_qty: float,
) -> tuple[tuple[date, float], ...]:
    """按确认日期升序累计 SRM 供应计划确认数量，直至覆盖 target_qty 为止（#18-a，
    姚祖怡 07-28 判例回件："答交数量小于缺口数量，则继续显示下一个确认数量，直至
    累计数量满足缺口数量为止"）。

    返回按顺序纳入的 (确认日期, 确认数量) 元组；每条记录的数量原样展示，不因
    "凑够即止"而截断最后一条的数值（Yao 原话未要求截断，只要求"够了就不再往下加"）。
    target_qty<=0 或无承诺记录 → 空元组。

    队列 #296（v4）修正：`q==0` 是合法的"差异已确认、答复为0"记录（此前
    `_extract_board_commitments` 会把它与"待答交"混淆一并丢弃，D2a 已根治
    该源头 bug）——本函数**不得**再跳过 `q==0` 的记录（此前 `if q <= 0:
    continue` 是同一个"「无」与「0」混为一谈"缺陷在下游的第二处落点，2026-08-07
    真实数据核验时发现：R01D.0015 唯一的确认记录恰好是 `answerQty=0`，若继续
    跳过会导致状态列正确显示"已答交"、但答交数量却错误显示"无"，重新引入
    #296 要根治的同一矛盾）。`q==0` 记录累计贡献为 0（不推进 `total`），故不会
    单独让循环提前 break，符合"0 不构成满足缺口"的直觉；仍保留对负数的防御
    （实测数据从未出现，属数据异常，不应计入累计展示）。

    🔴 **本函数由 `sc8/baoguan.py` 下沉至此（队列 #344，2026-08-24）**：改造前
    "上方齐料日期"与"下方 BOM 缺口清单"各按各的口径取值（前者取最早答交日、
    完全不看数量，后者按数量累计），正是姚祖怡"下面的清单对、上面的汇总数不对"
    那句话的根因。下沉后 `estimate_material_arrivals`（齐料日）、
    `baoguan._component_supply_status`（缺口清单）、`material_board`（物料看板）
    **共用同一个函数对象**——口径此后不可能漂移，而不是"记得同步改三处"。
    `baoguan.py` 保留再导出，既有 `from .baoguan import _cumulative_confirmed_batches`
    的调用方与单测零改动。
    """
    if target_qty <= 0 or not commitments:
        return ()
    ordered = sorted(commitments, key=lambda t: t[0])
    out: list[tuple[date, float]] = []
    total = 0.0
    for d, q in ordered:
        if q < 0:
            continue   # 负数视为数据异常，不计入展示（真实数据从未出现，防御性保留）
        out.append((d, q))
        total += q
        if total >= target_qty:
            break
    return tuple(out)


def _arrival_by_cumulative_qty(
    commitments: list[tuple[date, float]], target_qty: float, *,
    fallback: date, legacy_date: date | None,
) -> tuple[date, bool]:
    """单个子件的到货日（队列 #344 累计口径）。返回 `(到货日, 是否算已答交)`。

    `fallback` ＝ 无答交启发式估算日（需求日 + no_feedback_lead_days）。
    `legacy_date` ＝ 该料在 `srm_deliveries` 里的最早承诺日（可能为 None），**只在
    `target_qty <= 0` 时用得上**——见下。

    四种情形：
      · **该料有逐笔记录、且累计覆盖需求** → 取覆盖发生的那一笔的日期，判**已答交**
        （口径 ⑴⑵⑶）。
      · **有逐笔记录但累计不覆盖（含全 0）** → 判**未答交**，取
        `max(fallback, 最晚一笔正数答交日)`（口径 ⑷ ＋ design D3）。
      · 🔴 **该料在逐笔明细里根本没有记录** → **原样沿用改造前口径**（`legacy_date`，
        即 `/purchase/answer` ＋ 看板辅助算出的最早承诺日）。**见下方"为什么不判无答交"。**
      · 无记录、也无 `legacy_date` → 判**未答交**，取 `fallback`（与改造前一致）。

    🔴 **为什么"逐笔明细无记录"不判无答交（design D1，2026-08-24 真实数据当场改判）**：
    `load_material_commitments` 只取 `receiveType==2`（按排程交货）、前瞻 180 天，而
    `load_srm_deliveries` 走 `/purchase/answer` ＋ 看板辅助、窗口 60 天——**是两条取数
    管线**。若把前者当作"有没有答交"的权威，等于把 #211 v2 的 `receiveType==2` 筛选
    推广到四色判定上；而 **#211 v2 的原文明写「范围仅限本函数……不影响
    `load_srm_deliveries`（驱动 kit_date/gap_days/四色风险判定的既有口径）——未经授权
    不改判定逻辑」**。队列 #344 领的活是**答交数量匹配那一层**，不是换取数源。
    ⇒ **本函数只在"该料确实有逐笔答交记录"时改变其取值方式**；换源与否是另一条独立
    判据，已登记待姚祖怡签认，不在本变更包内擅动。

    🔑 **一处必须如实记下的自我更正**：本条最初是拿"影响面"论证的（"106 个子件翻面、
    看板会全红"）。**2026-08-24 真实数据把那个论证否掉了**——换源变体与已采纳口径
    相比只差 **2 行**，四色计数**完全相同**（两者都是 105 红），因为这 106 个料本来
    就不是各自成品行的瓶颈。⇒ **换源该不该做，只能用"谁授权的"来论证，不能用
    "影响大不大"**：按影响面论证时，两个方向都能编出理由，而且都听着很有道理。

    `target_qty <= 0`（现货已完全覆盖该料的毛需求）是一个**退化输入**：这类子件
    随后会被 `baoguan._drop_covered` 整个剔出到货估算，其日期只用于 `#14 需求日
    可齐套` 的净额抵扣前快照。此时按"需要累计多少"提问本身没有意义，故同样沿用
    改造前口径，**不把它错判成"无答交"**——否则一个明明有货的料会在快照里被标成待催。
    """
    if target_qty <= 0 or not commitments:
        return (legacy_date or fallback), legacy_date is not None
    batches = _cumulative_confirmed_batches(commitments, target_qty)
    if batches and sum(q for _, q in batches) >= target_qty:
        return batches[-1][0], True
    positives = [d for d, q in commitments if q > 0]
    if positives:
        return max(fallback, max(positives)), False
    return fallback, False


def estimate_material_arrivals(
    product_id: str,
    bom: list,                 # list[BomRow]（平台 models）
    srm_deliveries: list,      # list[SrmDeliveryOrder]（平台 models，含 committed_date）
    demand_date: date,         # 该成品需求日（无反馈启发式的基准日）
    params: ForecastParams | None = None,
    material_commitments: dict[str, list[tuple[date, float]]] | None = None,
    required_qty: dict[str, float] | None = None,
    heuristic_base_date: date | None = None,
) -> MaterialArrivals:
    """按 BOM 全部叶子件（多层递归展开半成品）+ SRM 承诺交期估算各物料到货日（关键路径齐套）。

    无 SRM 承诺交期的物料 → 需求日 + no_feedback_lead_days（启发式，标无反馈）。

    B1（shortage-multilevel-bom-b1，2026-07-13，姚祖怡批改发现）：原先只取直接子件
    （level==1），半成品子件不继续分解，会被误当作"待供应商答交的物料"去查 SRM
    （半成品是自制件，从不会有供应商承诺记录）。改为复用 `kit_engine.explode_bom`
    无条件递归展开到叶子件；单层 BOM（无半成品）场景结果与改造前完全一致。

    ── 答交数量累计口径（队列 #344，2026-08-24，姚祖怡判例批改 3 条 ✅ 全签认）──

    `material_commitments`（{material_id: [(答交日期, 答交数量), ...]}，来源
    `sources.load_material_commitments`）与 `required_qty`（{material_id: 累计目标
    数量}）**两者同时给定**时，各子件到货日改按已签认的四条口径取值：

      ⑴ 到货日 ＝ **按答交数量累计到覆盖该料需求为止的那一笔的日期**（判例 1：
         `R01I.0622` 逐笔答交为 7 笔 qty=0 ＋ 2027-05-20 的 10000 ⇒ 取 2027-05-20，
         而不是改造前采用的 2026-08-20 那笔 **数量为 0** 的记录）；
      ⑵ 一笔即够则不再往后累（判例 2）；
      ⑶ 不够则继续累计到够为止（判例 3：8000＋9000 覆盖 15000 ⇒ 取第二笔）；
      ⑷ **有答交记录但数量为 0 ＝ 等同没有答交**，走无答交启发式，绝不把那个 0
         数量的日期当到货日（姚祖怡 2026-08-19 文本回件答"对"）。

    **累计到最后仍不覆盖需求时**（签认口径未覆盖的真空地带，design D3，🔴 我方
    保守外推、待其事后以判例确认）：判为**无答交**（该料还得继续催，语义上是
    "待催"而非"有确定承诺"，落到四色即被 `_classify` 剔除出"真延期"判定），
    到货日取 `max(无答交启发式估算日, 该料最晚一笔正数答交日)`——取更晚与他自己
    写的规则 3（"更晚的那一个是齐套日期"）同向；只取估算日会**再次低估**，而低估
    正是本次要根治的病。⑷（全 0）是本规则的**特例而非例外**：全 0 时不存在正数
    答交日，`max` 自然退化为纯估算日，逐字复现他签认的口径 ⑷。

    🔴 **两参必须同时给定才走新分支**（design D4）：任一为 `None` ⇒ 逐字节回到
    改造前的 `srm_index` 最早承诺日口径。直接后果是 `sc8/pipeline.py`（对客承诺
    主流水线）与 `data/golden/` 全部 mock 黄金基准**结构性不受影响**——它们不传新
    入参、根本走不进新代码，这比"跑了测试没发现漂移"硬。同时这也是
    `compute_snapshot` 里 `material_commitments` 整体加载失败时的降级路径：数据源
    挂掉退回旧口径，而不是让全场变"无答交"、把看板刷成一片红。**刻意不做
    "只传 commitments 就按毛需求兜底"**——那是一次静默回退（返回值完全正常、结论
    却是另一套口径），宁可不走新分支。

    ── 无答交起算点（规则 1，队列 #401，2026-08-25）──────────────────────────────

    `heuristic_base_date` 给定时，无答交启发式改从**该日**起算（＝ `heuristic_base_date +
    no_feedback_lead_days`），而不是 `demand_date + no_feedback_lead_days`。取值由
    `no_feedback_start_date()` 单点决定，调用方只负责把结果传进来。

    🔴 **缺省 `None` ⇒ 逐字节回到 `demand_date` 起算**（同 design D4 的做法）：
    `sc8/pipeline.py`（对客承诺主流水线）与 `data/golden/` 全部 mock 黄金基准不传本参数、
    **结构性走不进新分支**，零漂移不靠「跑了测试没发现」而靠调用图。
    """
    p = params or config.default_params()

    plan = ProductionPlan(plan_id="_probe", product_id=product_id, product_name="",
                          planned_qty=1, planned_date="")
    components = list(explode_bom(bom, [plan]).keys())
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

    qty_cumulative = material_commitments is not None and required_qty is not None
    base = heuristic_base_date if heuristic_base_date is not None else demand_date
    fallback = base + timedelta(days=p.no_feedback_lead_days)

    arrivals: dict[str, date] = {}
    no_feedback: list[str] = []
    for mid in components:
        if qty_cumulative:
            arrival, answered = _arrival_by_cumulative_qty(
                material_commitments.get(mid) or [],
                float(required_qty.get(mid, 0.0) or 0.0),
                fallback=fallback, legacy_date=srm_index.get(mid))
            arrivals[mid] = arrival
            if not answered:
                no_feedback.append(mid)
        elif mid in srm_index:
            arrivals[mid] = srm_index[mid]
        else:
            # 无反馈启发式：需求日 + N 天（低置信兜底）
            arrivals[mid] = fallback
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
