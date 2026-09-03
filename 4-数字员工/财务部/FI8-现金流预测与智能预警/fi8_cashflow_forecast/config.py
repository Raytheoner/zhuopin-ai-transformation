"""FI8 配置 —— 预测窗口 ＋ 规则版本 ＋ **未签认判据与未授权数据面占位**。

本文件里有**两类**空值，性质不同，勿混为一谈：
  ⑴ **判据类**（`None`）—— 须财务侧签认的阈值口径，同其余四个财务场景；
  ⑵ **数据面授权类**（`BANK_BALANCE_ACCESS`）—— 不是"还没定个数"，而是**这份数据能不能
     取都还没人批**。它涉资金安全，须财务侧 ＋ CFO 办公室明确。
"""
from __future__ import annotations

import os

# ── 数据源开关（骨架期只有 mock）──
DATA_SOURCE_DEFAULT = os.environ.get("FI8_DATA_SOURCE", "mock").strip().lower()

# ── 预测窗口（#472 标的原文写死 4/8/12 周，属场景定义、非待签认判据）──
FORECAST_HORIZONS_WEEKS = (4, 8, 12)

# ── 🔴 未签认判据（一律 None）──
# 资金缺口窗口的高亮门限（余额低于多少算"缺口"？留不留安全垫？）
CASH_GAP_THRESHOLD = None
# 大额逾期应收触发催收 escalation 的门限（金额 × 逾期天数如何组合，未定）
COLLECTION_ESCALATION_CRITERIA = None
# 历史回款周期的取样口径（取几个月？中位数还是均值？剔不剔异常单？）
PAYMENT_CYCLE_SAMPLING = None

# ── 规则注册表版本 ──
RULE_VERSION = "fi8-skeleton-unsigned-2026-09-03"

# ── 🔴 数据面授权未取得（不是判据缺口，是取数权限缺口）──
BANK_BALANCE_ACCESS = None
BANK_BALANCE_NOT_AUTHORIZED = (
    "银行账户余额的取数授权尚未取得。该数据面既不在既有 U9C 财务侧 10 端点清单内，"
    "又涉资金安全（同 FI3 的 L4 晋级须 CFO 会签口径）——**是否可取、以何种方式取，"
    "须财务侧与 CFO 办公室明确，属须签认事项、不得默认可得**（队列 #472 状态列）。"
    "骨架期一律走合成期初余额；引擎读到未授权即 fail-loud，MUST NOT 以 0 余额或任何"
    "推算值代替。"
)

# ── 🔗 链 D L8：O2 缺口口径（**读既有实现，不另立一套**）──
O2_SHORTAGE_SEMANTICS = (
    "O2 缺口口径的权威实现 ＝ `zhuopin_platform.agents.kit_engine.calc_shortage`："
    "可用量 ＝ 当前库存 − 安全库存 ＋ 在途未到货（qty_ordered − qty_received）；"
    "缺口 ＝ max(毛需求 − 可用量, 0)，只保留缺口 > 0 的物料。"
    "B6：物料不在库存快照时，在途量仍计入可用量（available ＝ 在途），并记入 "
    "missing_snapshot 告警清单——**该情形在真实切换后必踩，收入递延口径须显式处理它，"
    "不得当作缺口为 0**。"
)

# ── fail-loud 文案 ──
U9C_AR_AP_NOT_READY = (
    "U9C 应收/应付计划与在手订单的取数通道未核实。real 模式一律 fail-loud，不得回退 mock。"
)
