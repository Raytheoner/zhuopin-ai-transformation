"""SC8 可配参数与委外识别（design D2 / D3）。

门禁文档（《SC8 上线前置门禁》）要求启发式阈值"定稿后回填"，故所有启发式/阈值集中此处，
**改 config 即改行为**，业务逻辑代码不散落写死。每条预测审计记录所用 `PARAM_VERSION`，
保证可复现、可追溯（IATF 16949）。
"""
from __future__ import annotations

from dataclasses import dataclass

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
