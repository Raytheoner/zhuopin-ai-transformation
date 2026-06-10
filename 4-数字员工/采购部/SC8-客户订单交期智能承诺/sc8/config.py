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
    """SRM 子开关：`SC8_SRM_SOURCE=mock|real`（默认 mock）。

    本期固定 mock —— 携客云 OpenAPI 未开通（900401），SRM 承诺交期降级，
    所有物料走无反馈启发式（低置信）。SRM 联调通过后才切 real。
    """
    return "real" if os.environ.get("SC8_SRM_SOURCE", "mock").strip().lower() == "real" else "mock"


# ── 对客外发总开关（红线 §7.4）──────────────────────────────────────────────
# 全程关闭，直到 ① SRM 真正联调通过 ② 真实黄金基准零偏差 ③ 门禁 6 项全勾。
# 关闭期间：所有对客通报只生成草稿、入待审批队列，绝不自动外发客户。
CUSTOMER_OUTBOUND_ENABLED = False

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
PARAM_VERSION = "sc8-params-v0"

# ── D2 启发式参数（v0 初值，黄金基准/真实数据校准后回填）────────────────────────
NO_FEEDBACK_LEAD_DAYS = 30   # 无 SRM 承诺交期的物料：按需求日 +N 天估算到货（并标低置信）
OUTSOURCE_EXTRA_DAYS  = 10   # 委外加工成品：齐套日基础上 +N 天附加工期
LOGISTICS_DAYS        = 1    # 物流天数（默认国内快递）
DEVIATION_ALERT_DAYS  = 3    # 偏差监控阈值：实际进展 vs 预测交付日，超 N 天告警/重算


@dataclass(frozen=True)
class ForecastParams:
    """一次预测运行所用参数快照（写入审计 → 可复现）。"""
    param_version:         str = PARAM_VERSION
    no_feedback_lead_days: int = NO_FEEDBACK_LEAD_DAYS
    outsource_extra_days:  int = OUTSOURCE_EXTRA_DAYS
    logistics_days:        int = LOGISTICS_DAYS
    deviation_alert_days:  int = DEVIATION_ALERT_DAYS


def default_params() -> ForecastParams:
    """取当前模块常量构造参数快照（测试可传入覆盖版做参数化验证）。"""
    return ForecastParams(
        param_version=PARAM_VERSION,
        no_feedback_lead_days=NO_FEEDBACK_LEAD_DAYS,
        outsource_extra_days=OUTSOURCE_EXTRA_DAYS,
        logistics_days=LOGISTICS_DAYS,
        deviation_alert_days=DEVIATION_ALERT_DAYS,
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
