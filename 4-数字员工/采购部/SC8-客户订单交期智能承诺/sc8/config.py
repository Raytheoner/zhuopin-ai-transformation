"""SC8 可配参数与委外识别（design D2 / D3）。

门禁文档（《SC8 上线前置门禁》）要求启发式阈值"定稿后回填"，故所有启发式/阈值集中此处，
**改 config 即改行为**，业务逻辑代码不散落写死。每条预测审计记录所用 `PARAM_VERSION`，
保证可复现、可追溯（IATF 16949）。
"""
from __future__ import annotations

import os
from dataclasses import dataclass

# ── 数据源开关（design D2）：mock→真实切换点，默认 mock，保留 mock 回退 ─────────
def data_source_mode() -> str:
    """SC8 数据源：`SC8_DATA_SOURCE=mock|real`（默认 mock）。real 走 FO+BOM 真实连接器。"""
    return "real" if os.environ.get("SC8_DATA_SOURCE", "mock").strip().lower() == "real" else "mock"


def srm_source_mode() -> str:
    """SRM 子开关：`SC8_SRM_SOURCE=mock|real`（默认 real）。

    2026-07-15 更新：携客云 OpenAPI 900401 阻塞已解除（真实只读实测确认
    `get_receive_board`/`get_confirmed_dates` 均可用），SRM 联调已通过。

    默认改为 real（而非沿用 `U9C_DATA_SOURCE`/`SC8_NET_INVENTORY` 的"默认关"
    惯例）——原因：本开关**唯一消费方**是 `sc8/run.py` 这个小样本真实验证
    runner，该 runner 里 FO/BOM 早就无条件真实（不受任何开关控制），SRM 此前
    单独挂 mock 默认纯粹是给 900401 阻塞期打的技术补丁，不是业务判断类开关
    （不同于 `SC8_NET_INVENTORY` 那种需要专员签字复核的口径变更）；阻塞已
    解除，继续默认 mock 反而制造"同一工具里 FO/BOM 真实、SRM 却假"的不一致。
    无任何测试依赖本函数默认值触发真实网络调用（唯一消费方 `run.py` 不被
    任何测试导入调用），改默认值零回归风险。仍保留显式 `mock` 覆盖，供
    临时脱敏验证或凭据不可用场景使用。
    """
    return "mock" if os.environ.get("SC8_SRM_SOURCE", "real").strip().lower() == "mock" else "real"


def net_inventory_enabled() -> bool:
    """保供现货净额开关：`SC8_NET_INVENTORY=on|off`（**默认 OFF**）。

    OFF = 现行为、零保供四色漂移（保供看板不看库存，与接入前完全一致）。
    ON  = 直接子件"白名单仓可用现货 ≥ 其毛需求"→ 视为已齐、退出待催/催货（消除缺料误判 P0）。
    翻 ON 会改变保供四色，MUST 先由采购专员重核保供黄金基准 + 登记原因 + 签字后方可开启
    （stock-api-inventory-source 变更包 §验收晋档条件）。
    """
    return os.environ.get("SC8_NET_INVENTORY", "off").strip().lower() in ("on", "1", "true", "yes")


def kit_date_rule1_enabled() -> bool:
    """无答交启发式起算点「规则 1」开关：`SC8_KIT_DATE_RULE1=on|off`（**默认 OFF**）。

    判据来源＝姚祖怡 2026-08-18 书面签认的规则 1（出货日不在三个月内 ⇒ 无答交按
    「出货日往前推 3 个月那个自然月的 20 日」起算、再推 `no_feedback_lead_days` 天），
    排期由 Shao Peishen 2026-08-25 拍板 (a)（队列 §四 #111 ／ §一 #401）。

    OFF = 现行为（起算点恒为 `max(出货日, 今天)`），**逐字节零漂移**——mock 全量回归、
    `data/golden/` 黄金基准、`sc8/pipeline.py` 对客承诺主流水线一律不受本变更影响。
    ON  = 起算点按 `forecast.no_feedback_start_date` 分支取值；对 2026-08-24 那份生产载荷
    实测**43 行适用、齐料日一律前移 89~92 天（中位 91）**——红的会变少。

    🔴 **与 `net_inventory_enabled` 同级：翻 ON 会改变保供四色，MUST 先由姚祖怡复核
    「修复前后对照表」并签认后方可开启**（对照表随采购部#19 出，队列 §一 #402）。
    判据本身他已签认，此处要他确认的是**这批真实行搬动的结果**，不是规则文本。
    """
    return os.environ.get("SC8_KIT_DATE_RULE1", "off").strip().lower() in ("on", "1", "true", "yes")


def bom_max_depth() -> int:
    """真实 BOM 拉取递归深度：`SC8_BOM_MAX_DEPTH`（默认 5）。

    根因修复（姚祖怡 07-26 V6 #9，"半成品未逐级展开"，队列 #117）：B1
    （shortage-multilevel-bom-b1）只把**算法**（`kit_engine.explode_bom`）
    改成无条件递归展开半成品至叶子件，但生产环境实际取数
    `baoguan_service.compute_snapshot` 调用 `load_real_bom(..., max_depth=1)`
    从未跟着提高——U9C BOM/Query 只拉了成品的直接子件一层，半成品自己的
    子件行从未被拉取，`explode_bom` 因而拿不到数据可展开（半成品 component_id
    从未出现为某行的 product_id，被误当叶子件）。现网 F02N.0226 瓶颈子件
    停在半成品 S02Y.0198 即由此而来。本函数把 max_depth 提到 5（覆盖"成品→
    半成品→原材料"及更深一层的余量），修复取数深度使 B1 算法名副其实。
    可用 env 覆盖以应对真实 LAN 环境性能/限流问题（独立后续验证）。
    """
    raw = os.environ.get("SC8_BOM_MAX_DEPTH", "5").strip()
    try:
        depth = int(raw)
    except ValueError:
        depth = 5
    return max(1, depth)


def po_transit_enabled() -> bool:
    """PO 在途数据接入开关：`SC8_PO_TRANSIT=on|off`（**默认 ON**）。

    姚祖怡 07-23 新功能诉求批1（#12 子件供给状态全展示 / #14 需求日可齐套数量）的共享基础。
    与 `net_inventory_enabled` 不同：本开关只影响**纯展示/派生列**，不改四色判定/净额/
    缺料计算口径（红线，见开场prompt-保供看板功能批1），故默认开启，无需专员重核签字。
    若 PO 端点异常导致立即重算变慢/超时，可临时关闭作应急开关；关闭时 #12/#14 相关字段
    退化为空/None（零漂移，不影响既有四色/净额/kittable_qty 等已上线功能）。
    """
    return os.environ.get("SC8_PO_TRANSIT", "on").strip().lower() not in ("off", "0", "false", "no")


def po_transit_lookback_days() -> int:
    """PO 在途聚合回溯窗口：`SC8_PO_TRANSIT_DAYS`（默认 365）。

    根因修复（姚祖怡 07-28 判例回件 #18-c，队列 #139）：原窗口 60 天按 PO `makeDate`
    （单据创建日）过滤，误伤"创建很久但仍未关闭"的真实未清 PO——真实案例 PO
    `ZPCG20251105008`（2025-11-05 下单，约 266 天前）R01D.0006 行仍有 3,000pcs
    已审核未清量，60 天窗口下被排除，导致该子件误判"无未交订单"。

    真实数据核实（2026-07-28）：`ZpViewPurOrder/Query` 无客户端可读的"关闭/结案"
    状态字段（`status` 字段是审核工作流状态，全库 99.5% 恒为 2，与"是否已完结"
    无关）——服务端也不做日期区间过滤（`_zp_post` 全量拉取，客户端按 `makeDate`
    二次过滤），故只能退而求其次靠"回溯窗口"折衷：窗口越大越不会漏真实未清 PO，
    但全库存在大量 2021 年即已停止收货、从未在系统里正式关闭的历史"呆滞"未清行
    （抽样统计：>1095 天的仍标"未清"行仍有 2000+ 条），窗口过大会把这类噪声
    也误判为"有未交订单"。365 天是基于真实分布的折衷值（覆盖本次真实案例的
    266 天），**不是精确解**——彻底修复需 IT 提供 PO 行级"关闭/结案"状态字段
    （与队列 #139 里 FO `Status` 字段同类缺口，另案跟催）。
    """
    raw = os.environ.get("SC8_PO_TRANSIT_DAYS", "365").strip()
    try:
        days = int(raw)
    except ValueError:
        days = 365
    return max(1, days)


def material_commitment_lookahead_days() -> int:
    """物料答交承诺前瞻窗口：`SC8_COMMITMENT_LOOKAHEAD_DAYS`（默认 365）。

    根因修复（姚祖怡 08-05 三度举证，队列 #262）：`load_material_commitments`
    此前查询窗口固定 `[今天, 今天+60]`（SRM 单次查询跨度硬限 ≤60 天，见
    `XkySrmConnector.get_receive_board`），而真实确认批次可能落在更远的未来——
    真实案例 `R01A.1028` 确认于 2026-11-25（距今约 112 天）、此前 08-03 批次
    `R01B.0754` 确认于 2026-12-25（距今约 144 天），两次都被这个固定窗口结构性
    排除：即便 receiveType 筛选/累计逻辑本身完全正确，看板仍如实显示"无"。
    姚祖怡 08-05 明确："查不到就如实显示无"这个此前被当作可接受兜底的行为，
    业务侧从未认可过——本函数即为解除该结构性限制。

    真实探测坐实（2026-08-05，`R01A.1028` 案例）：`[今天,+60)` 窗口内该料仅有
    未答交排程 + 一条按订单交货(receiveType=1)记录（后者按既有口径不计入）；
    `[+60,+120)` 窗口命中 `answerQty=10000`／`boardDate=2026-11-25`，与姚祖怡
    举证的正确值逐位吻合。继续探测更远窗口分布：`[+120,+180)` 仍有 71 条
    已答交(receiveType=2)记录、涉及 65 个料号（非孤例）；`[+180,+240)` 仅 1
    条原始 record 且 0 条已答交——180 天窗口经验上覆盖了绝大多数真实答交
    记录，240 天内边际收益趋零。**不是精确解**（未来分布可能变化，业务上
    也没有"答交必在 N 天内"的硬约束），可用 env 覆盖。

    实现为多段 ≤60 天窗口顺序查询（`sources._chunk_date_windows`，SRM 硬性
    单次跨度限制）。携客云限流 1 req/30s（进程级令牌桶，见
    `XkySrmConnector._get_bucket`）——本参数每增加 60 天，`load_material_commitments`
    每次调用增加约 30 秒阻塞等待（不重试不丢弃，只是排队）。

    365 天（队列 #296，姚祖怡 08-06 第四次举证后明确要求放宽，v4）：真实测算
    `_chunk_date_windows` 从 180 天的 3 段增至 6 段（非估算"约7段"，实测 6 段），
    比 180 天多 3 次顺序调用，最坏情形（令牌桶初始为空）多等约 90 秒——与
    180 天口径落地时（#262）"约 60-90 秒、与 BOM 多层递归等步骤同数量级可接受"
    同一论证成立，判定可接受，不设止步点（design.md D3）。该函数是保供看板
    每小时后台重算/手动"立即重算"里的一步。
    """
    raw = os.environ.get("SC8_COMMITMENT_LOOKAHEAD_DAYS", "365").strip()
    try:
        days = int(raw)
    except ValueError:
        days = 365
    return max(1, days)


def material_board_month_span() -> int:
    """物料看板月度缺口列的月份跨度：`SC8_MATERIAL_BOARD_MONTHS`（默认 3）。

    姚祖怡 2026-08-12 采购部#13 回件给出的列模板写的是「8 月／9 月／10 月／8-10 月
    总缺口」，但他是在 8 月写的、且第 4 列表述为「三者相加」——是**相对表述而非
    常量**（design D2）。故实现为「以快照业务日期所在月为首的连续 N 个自然月」，
    月份随快照滚动、列标题显示真实月份，不写死。

    **为何可配**：3 是他当天给出的实例，不是经过验证的业务判据——采购备料的可视
    区间会随物料交期结构变化（长交期料看 6 个月才有意义）。本参数留给他在判例包
    里确认；改一个 env 即改，不需改代码、不需重新 design 审。跨度加大**不增加任何
    取数请求**（纯派生自同一份快照，见 material_board.build_material_board），只影响
    列数与「窗口外缺口」的划分边界。
    """
    raw = os.environ.get("SC8_MATERIAL_BOARD_MONTHS", "3").strip()
    try:
        months = int(raw)
    except ValueError:
        months = 3
    return max(1, months)


# ── 对客外发总开关（红线 §7.4）──────────────────────────────────────────────
# 全程关闭，直到 ① SRM 真正联调通过 ② 真实黄金基准零偏差 ③ 门禁 6 项全勾。
# 关闭期间：所有对客通报只生成草稿、入待审批队列，绝不自动外发客户。
CUSTOMER_OUTBOUND_ENABLED = False

# ── 审批授权分级（B3 / 审计报告 §3.3 P1-C，配置即策略）────────────────────────
# 重点客户 / 首次承诺（/ 关联金额>50万，SC8 暂不可得，见 design B3-a）的对客承诺，
# 放行须 VP 级确认人；其余 L2 即可。改 config 不改逻辑。
VP_APPROVERS: set[str] = {"Paul"}                       # VP 级确认人白名单（运营维护）
KEY_CUSTOMERS: set[str] = {"比亚迪", "上汽", "理想"}      # 重点客户（默认三家 OEM）

LEVEL_VP = "vp"
LEVEL_L2 = "l2"


def required_approval_level(customer_name: str, *, first_commitment: bool) -> str:
    """计算一条对客承诺所需审批级别（B3）。

    命中 重点客户 OR 首次承诺 → VP 级；否则 L2。
    （"关联金额>50万"在 SC8 数据面暂不可得，记 amount_unknown，留待 IT 补金额/SC5 承接。）
    """
    if (customer_name or "").strip() in KEY_CUSTOMERS or first_commitment:
        return LEVEL_VP
    return LEVEL_L2


def approver_meets_level(confirmed_by: str, required_level: str) -> bool:
    """确认人级别是否达标：VP 级须在白名单；L2 级任意非空确认人即可。"""
    if required_level == LEVEL_VP:
        return confirmed_by in VP_APPROVERS
    return bool(confirmed_by)


# ── 客户数据隔离键（design D4，可切换）──────────────────────────────────────
# 现状 FO API 只返回客户名 → 用 customer_name 做隔离键。IT 补好 customer_id 后，
# 把本常量改为 "customer_id" 这一处即可全局切换（值为空时回退客户名，防空键串库）。
ISOLATION_KEY_FIELD = "customer_name"


def customer_isolation_key(obj) -> str:
    """取一条订单/预测的客户隔离键（按 ISOLATION_KEY_FIELD，空值回退客户名）。"""
    val = str(getattr(obj, ISOLATION_KEY_FIELD, "") or "").strip()
    return val or str(getattr(obj, "customer_name", "") or "").strip()

# ── 参数版本（D2 补充：审计每条预测"用了哪组参数版本"，可复现可追溯）──────────────
# 每次调整下方任一启发式/阈值常量，必须 bump 本版本号，使审计可还原当时算法行为。
PARAM_VERSION = "sc8-params-v1"

# ── D2 启发式参数（v1，姚祖怡 2026-07-23 业务口径校准，Paul 同日拍板）─────────────
NO_FEEDBACK_LEAD_DAYS = 90   # 无 SRM 承诺交期的物料：按需求日 +N 天估算到货（并标低置信）
                             # v0=30（Paul 2026-06-22 定）；姚祖怡 07-23 反馈"30 天不符实际
                             # 周期"，Paul 07-23 拍板改 90（队列 §四#29）
OUTSOURCE_EXTRA_DAYS  = 10   # 委外加工成品：齐套日基础上 +N 天附加工期
LOGISTICS_DAYS        = 1    # 物流天数（默认国内快递）
DEVIATION_ALERT_DAYS  = 3    # 偏差监控阈值：实际进展 vs 预测交付日，超 N 天告警/重算

# ── 规则 1 起算点参数（姚祖怡 2026-08-18 书面签认，队列 §一 #401）──────────────
# 只在 `kit_date_rule1_enabled()` 为 ON 时生效；OFF 时这三个值不参与任何计算。
RULE1_HORIZON_MONTHS = 3     # 「出货日在三个月内」的自然月数 —— 规则1／规则2 的分界
RULE1_MONTHS_BACK    = 3     # 规则1：出货日往前推 N 个自然月
RULE1_START_DAY      = 20    # 规则1：落在那个自然月的第 N 日（他 08-18 确认＝自然月 20 号）


@dataclass(frozen=True)
class ForecastParams:
    """一次预测运行所用参数快照（写入审计 → 可复现）。"""
    param_version:         str = PARAM_VERSION
    no_feedback_lead_days: int = NO_FEEDBACK_LEAD_DAYS
    outsource_extra_days:  int = OUTSOURCE_EXTRA_DAYS
    logistics_days:        int = LOGISTICS_DAYS
    deviation_alert_days:  int = DEVIATION_ALERT_DAYS
    rule1_horizon_months:  int = RULE1_HORIZON_MONTHS
    rule1_months_back:     int = RULE1_MONTHS_BACK
    rule1_start_day:       int = RULE1_START_DAY


def active_param_version() -> str:
    """当前生效的参数版本串（写入审计）。

    🔴 规则 1 开关是**会改变数值结论**的启发式分支，故它开着时版本串必须自带标记——
    否则同一个 `sc8-params-v1` 会对应两套不同的齐料日算法，审计记录再也无法还原
    「当时是按哪一支算的」（IATF 可追溯性）。**刻意做成自动派生而不是「翻开关时记得
    手动 bump 常量」**：后者是一个必然会被忘记的人工步骤。
    """
    return PARAM_VERSION + ("+rule1" if kit_date_rule1_enabled() else "")


def default_params() -> ForecastParams:
    """取当前模块常量构造参数快照（测试可传入覆盖版做参数化验证）。"""
    return ForecastParams(
        param_version=active_param_version(),
        no_feedback_lead_days=NO_FEEDBACK_LEAD_DAYS,
        outsource_extra_days=OUTSOURCE_EXTRA_DAYS,
        logistics_days=LOGISTICS_DAYS,
        deviation_alert_days=DEVIATION_ALERT_DAYS,
        rule1_horizon_months=RULE1_HORIZON_MONTHS,
        rule1_months_back=RULE1_MONTHS_BACK,
        rule1_start_day=RULE1_START_DAY,
    )


# ── D3 委外识别 ──────────────────────────────────────────────────────────────
# 【真实权威口径】U9C 工艺路线（Routing）API：成品工艺路线里任一工序 IsSubContract=true
#   → 该成品委外。字段见 supplychain/docs/API文档 工艺路线 JSON（Operations[].IsSubContract）。
#   该口径被 U9C MCP 阻塞（7/1 申请、6/12 数据到位前不可用）→ 见 is_outsourced_by_routing 接口缝。
# 【MVP 过渡口径】在 U9C 工艺路线接通前，用显式维护清单 OUTSOURCE_PRODUCT_IDS（运营维护，最准）。
#   料号前缀规则 OUTSOURCE_PREFIXES 默认**关闭**（卓品无可靠"委外=某前缀"约定，留着易误判）；
#   仅在确有前缀约定时按需开启。
OUTSOURCE_PRODUCT_IDS: set[str] = set()   # MVP 维护清单，例：{"F02N.0184"}
OUTSOURCE_PREFIXES: tuple[str, ...] = ()  # 默认关闭；如确有约定再填，例：("X",)


def outsource_ids_from_env() -> set[str]:
    """委外维护清单（可运营维护，无需改代码）：`SC8_OUTSOURCE_IDS=料号1,料号2`。

    真实料号由 PMC 确认 / U9C 工艺路线 IsSubContract 接通后接管；本函数是过渡口径，
    与模块常量 OUTSOURCE_PRODUCT_IDS 取并集。不臆造料号，留空即不判委外。
    """
    raw = os.environ.get("SC8_OUTSOURCE_IDS", "")
    env_ids = {x.strip() for x in raw.split(",") if x.strip()}
    return OUTSOURCE_PRODUCT_IDS | env_ids


def is_outsourced_by_routing(operations: list) -> bool:
    """【真实口径，6/12 接 U9C 工艺路线后启用】任一工序 IsSubContract=true → 委外。

    operations: U9C Routing API 返回的 Operations 列表（dict 或带 IsSubContract 属性的对象）。
    本批 mock 不调用；保留接口缝，切真实库时由连接器喂入工艺路线，is_outsourced 内部改走此路。
    """
    for op in operations or []:
        flag = op.get("IsSubContract") if isinstance(op, dict) else getattr(op, "IsSubContract", False)
        if flag:
            return True
    return False


def is_outsourced(
    product_id: str,
    *,
    product_ids: set[str] | None = None,
    prefixes: tuple[str, ...] | None = None,
) -> bool:
    """成品是否需委外加工（MVP 过渡口径：维护清单 OR 可选前缀）。

    维护清单命中 OR 料号前缀命中 → 视为委外。参数可注入便于测试，不传则用模块默认。
    6/12 U9C 工艺路线到位后，本函数内部改走 is_outsourced_by_routing(IsSubContract)，调用方不变。
    """
    ids = OUTSOURCE_PRODUCT_IDS if product_ids is None else product_ids
    pfx = OUTSOURCE_PREFIXES if prefixes is None else prefixes
    if product_id in ids:
        return True
    return bool(pfx) and product_id.startswith(pfx)
