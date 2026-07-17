"""FI2 配置 —— 数据源开关 + 容差口径（唐燕萍团队 R1-R7 定稿真值）+ 规则版本。

✅ 真值口径（design.md D14，2026-07-10 唐燕萍团队两份圈改回件 + Paul 三拍板，权威全文见
   `1-转型规划/FI2-FI3-规则定稿-交CC-2026-07-10.md`，队列 #14/#16）：本文件原 2026-07-07/
   07-09 的 CC 占位量级已替换为真值。替换只改本文件 + match_engine.py 里与容差公式直接
   绑定的读取点（税额改按税率动态换算、未税金额新增比例备用线），判定优先级/分层架构不变。
   R7 的"外币供应商连续 2 次同向偏移推人工抽查"过渡规则、"方案一"原始外币单价+汇率升级位，
   均因缺前置数据（供应商清单/跨运行历史状态）暂未实现，见 design D14 Open Questions。
"""
from __future__ import annotations

import os

# 数据源：mock（开发/回归）| csv（应急桥接，接口占位）| u9c（最终目标，端点未开放时 fail-loud）
DATA_SOURCE_DEFAULT = os.environ.get("FI2_DATA_SOURCE", "mock").strip().lower()

# ── R1 料品汇总归集容差（真值）──
# 数量容差：合计 ±0（精确匹配，唐燕萍定稿取消了 CC 占位的 ±2%/±5 个豁口）
QTY_TOLERANCE_PCT = float(os.environ.get("FI2_QTY_TOLERANCE_PCT", "0"))
QTY_TOLERANCE_ABS = float(os.environ.get("FI2_QTY_TOLERANCE_ABS", "0"))
# 未税金额尾差容差（元/料品）：区分"完全匹配"(diff=0) vs "金额微差"(容差内) vs "数量金额不符"(超容差)
AMOUNT_TAIL_TOLERANCE = float(os.environ.get("FI2_AMOUNT_TAIL_TOLERANCE", "0.5"))
# 未税金额比例口径备用（R1"比例口径备用：未税 ≤0.5%"）：与上行绝对值容差两者取宽松者
# （任一满足即算容差内，大额料品场景下比例线通常比固定 0.5 元更宽松）
UNTAXED_AMOUNT_TOLERANCE_PCT = float(os.environ.get("FI2_UNTAXED_AMOUNT_TOLERANCE_PCT", "0.005"))
# 税额容差：R1"税额随税率"——不再是独立固定值，改按该料品 AP 侧有效税率动态换算
# （tax_tolerance = AMOUNT_TAIL_TOLERANCE × 有效税率，见 match_engine.assign_category）；
# AP 未税金额合计为 0（理论异常）时有效税率记 0，即该场景下税额差异必须恰好为 0 才算容差内。
# "明细错位"判定用：同 AP 单号总额差异容差（元），跨料品配对校验通过线（唐燕萍定稿未涉及
# 此项，非 R1 三容差之一，维持 CC 原占位量级不变）
AP_LEVEL_AMOUNT_TOLERANCE = float(os.environ.get("FI2_AP_LEVEL_AMOUNT_TOLERANCE", "0.5"))

# ── R5 门禁（整单差异总额分级，design D14 新增）──
# 差异总额 ≤1 元（或 ≤UNTAXED_AMOUNT_TOLERANCE_PCT，两者取宽松者）→ L2 AP 自行消化，不转
# 人工；超线 → L3 人工。仅对"金额微差"类生效，见 recon_report._l2_gated_ap_docs 的从紧解读。
L2_GATE_ABS_THRESHOLD = float(os.environ.get("FI2_L2_GATE_ABS_THRESHOLD", "1.0"))

# ── R7 AP-PO 单价强制比对容差（真值）──
# 人民币供应商统一 ±2%（方案二，拦截线；替换 CC 占位 ±3%）
AP_PO_PRICE_TOLERANCE_PCT = float(os.environ.get("FI2_AP_PO_PRICE_TOLERANCE_PCT", "0.02"))
# 外币供应商清单（过渡规则：R7 容差内连续 2 次同向偏移 → 推人工抽查）——供应商清单待唐燕萍
# 团队提供，暂空；且该规则本身需要跨运行历史状态（本 MVP 单次运行无状态），本次未实现，
# 见 design D14 future-work。清单到位前，外币供应商行按人民币同一 ±2% 容差处理，不触发
# 增量抽查。
FOREIGN_CURRENCY_SUPPLIERS: tuple[str, ...] = tuple(
    s.strip() for s in os.environ.get("FI2_FOREIGN_CURRENCY_SUPPLIERS", "").split(",") if s.strip()
)
# 方案一升级位（原始外币单价 + 下单日汇率字段）：IT 评估中，本次不实现，仅登记
# future-work（见 design D14 + tasks.md），勿在 price_check.py 抢先实现。

# ── 分类规则版本（随规则表更新登记，IATF 单一可信源）──
RULE_VERSION = "fi2-v3-tangyanping-2026-07-10"   # 唐燕萍团队 R1-R7 定稿真值（队列 #14/#16）

# 真实端点未就绪原因（u9c 直读 fail-loud 文案，v3：发票源改 U9C 应付附件+OCR，不再经 SRM）
U9C_FI_NOT_READY = (
    "U9C 财务模块接口（PO/GR/应付配票 AP）预计 2026-09 开放，当前不可用；"
    "发票源为 U9C 应付单附件 + OCR（不经 SRM）；"
    "过渡期可用 FI2_DATA_SOURCE=csv 应急桥接（接口占位，真实路径待接通）"
)
