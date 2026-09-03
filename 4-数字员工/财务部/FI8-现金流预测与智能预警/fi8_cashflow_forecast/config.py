"""FI8 配置 —— 预测窗口 ＋ 规则版本 ＋ **未签认判据注册表与未授权数据面占位**。

本文件里有**两类**空值，性质不同，勿混为一谈：
  ⑴ **判据类** —— 须财务侧签认的阈值口径，同其余四个财务场景，**已登记进 `CRITERIA` 注册表**；
  ⑵ **数据面授权类**（`BANK_BALANCE_ACCESS`）—— 不是「还没定个数」，而是**这份数据能不能
     取都还没人批**。它涉资金安全，须财务侧 ＋ CFO 办公室明确。
     🔴 **它刻意不进注册表**（Shao Peishen 2026-09-03 拍板 `G-2 = (a)`）：机械形状虽像判据，
     但解除路径是**授权**不是**签认**，混进去等于把两件事的解除条件也混了。

📌 **2026-09-03 迁移（`criteria-signoff-platform` A4 段）**：三条裸 `None` 判据常量 ＋ 本地
守卫用例改为**引用平台底座** `zhuopin_platform.criteria_signoff`；🔴 **行为一处未变**。

🔴 **EE-2（Shao Peishen 2026-09-03 拍板）**：银行余额取数授权**由他本人去推**
（财务侧 ＋ CFO 办公室，**属权限缺口、非判据缺口**）。⇒ 本场景先做**不依赖余额的部分**，
`BANK_BALANCE_ACCESS` 保持空值并由独立用例守，**不得绕过**。
"""
from __future__ import annotations

import os
from typing import Any

from zhuopin_platform.criteria_signoff import CriteriaRegistry, Criterion

# ── 数据源开关（骨架期只有 mock）──
DATA_SOURCE_DEFAULT = os.environ.get("FI8_DATA_SOURCE", "mock").strip().lower()

# ── 预测窗口（#472 标的原文写死 4/8/12 周，属场景定义、非待签认判据）──
FORECAST_HORIZONS_WEEKS = (4, 8, 12)

# ── 🔴 未签认判据注册表（**唯一**声明处；本文件内不得再有任何裸 `None` 判据常量）──
CRITERIA = CriteriaRegistry("FI8", [
    Criterion(
        key="CASH_GAP_THRESHOLD",
        question="资金缺口窗口的高亮门限：余额低于多少算「缺口」，留不留安全垫",
        owner="财务侧",
    ),
    Criterion(
        key="COLLECTION_ESCALATION_CRITERIA",
        question="大额逾期应收触发催收 escalation 的门限：金额与逾期天数如何组合",
        owner="财务侧",
    ),
    Criterion(
        key="PAYMENT_CYCLE_SAMPLING",
        question="历史回款周期的取样口径：取几个月、中位数还是均值、剔不剔异常单",
        owner="财务侧",
        note="不同选法能差出两周，故不得由实现方自定",
    ),
])

# ── 规则注册表版本 ──
RULE_VERSION = "fi8-skeleton-unsigned-2026-09-03"

# 🔴 导入期即校验版本号与签认状态一致（原 `test_rule_version_marked_unsigned` 的职责）。
CRITERIA.assert_rule_version(RULE_VERSION)


def audit_decision(**fields: Any) -> dict[str, Any]:
    """构造写审计用的 `decision`，**恒带当时生效的 `RULE_VERSION`**。

    🔴 **G-5 反向依赖**（Shao Peishen 2026-09-03 拍板 `G-5 = (a)`）：判据底座**不接**
    `AuditLogger`（保其零依赖）；改由**各场景引擎**在 `record(AuditEvent(...))` 时把
    `RULE_VERSION` 写进 `decision`。**方向是审计日志指向判据版本，不是判据模块去写日志。**
    """
    return {**fields, "rule_version": RULE_VERSION}


# ── 🔴 数据面授权未取得（**不是判据缺口，是取数权限缺口** ⇒ 刻意不进 `CRITERIA`）──
BANK_BALANCE_ACCESS = None
BANK_BALANCE_NOT_AUTHORIZED = (
    "银行账户余额的取数授权尚未取得。该数据面既不在既有 U9C 财务侧 10 端点清单内，"
    "又涉资金安全（同 FI3 的 L4 晋级须 CFO 会签口径）——**是否可取、以何种方式取，"
    "须财务侧与 CFO 办公室明确，属须签认事项、不得默认可得**（队列 #472 状态列）。"
    "骨架期一律走合成期初余额；引擎读到未授权即 fail-loud，MUST NOT 以 0 余额或任何"
    "推算值代替。"
    "🔴 **EE-2（Shao Peishen 2026-09-03）：该授权由他本人去推**，属权限缺口、非判据缺口，"
    "故**不并入 `CRITERIA` 注册表**（`G-2 = (a)`）——判据靠签认解除，授权靠审批解除，"
    "两者混在一处会让「谁该去解它」也一起糊掉。本场景先做不依赖余额的部分，不得绕过。"
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
