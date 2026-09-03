"""FI6 配置 —— 数据源开关 ＋ 规则版本 ＋ **未签认判据注册表**。

🔴 同 FI5：凡须财务侧签认的判据一律**未签认**，**不给默认数**。异常检测尤其容易被
「先随便设个 3 倍标准差」蒙混过去——那个数一旦落地就会静默决定谁被推给财务主管、谁被
放过，且不会报错。

📌 **2026-09-03 迁移（`criteria-signoff-platform` A4 段）**：四条裸 `None` 常量 ＋ 本地
守卫用例改为**引用平台底座** `zhuopin_platform.criteria_signoff`；🔴 **行为一处未变**
（未签认 ⇒ 值恒 `None`、读取即抛，无 `default=` 旁路）。
"""
from __future__ import annotations

import os
from typing import Any

from zhuopin_platform.criteria_signoff import CriteriaRegistry, Criterion

# ── 数据源开关（骨架期只有 mock）──
DATA_SOURCE_DEFAULT = os.environ.get("FI6_DATA_SOURCE", "mock").strip().lower()

# ── 🔴 未签认判据注册表（**唯一**声明处；本文件内不得再有任何裸 `None` 判据常量）──
CRITERIA = CriteriaRegistry("FI6", [
    Criterion(
        key="AMOUNT_SURGE_CRITERIA",
        question="金额突增如何判：相对历史基线取倍数、分位数还是绝对额下限，三者如何组合",
        owner="财务侧",
        note="最容易被「先随便设个 3 倍标准差」蒙混过去的一条",
    ),
    Criterion(
        key="FREQUENCY_ANOMALY_CRITERIA",
        question="频率异常如何判：窗口长度多长、窗口内笔数上限多少（「频繁」是几次/几天）",
        owner="财务侧",
        note="本项目无成文口径",
    ),
    Criterion(
        key="RELATED_PARTY_CRITERIA",
        question="关联方如何判定：供应商主数据比对？股权关系？亲属关系？",
        owner="财务侧",
        note="口径签认前，`PartyProfile` 上不得出现任何「是否关联方」布尔字段——"
             "留一个字段会诱使实现方先填上再说，判据就是这样被默默造出来的",
    ),
    Criterion(
        key="L2_ESCALATION_CRITERIA",
        question="高风险交易触发审批并推送财务主管的门限是什么",
        owner="财务侧",
    ),
])

# ── 规则注册表版本 ──
RULE_VERSION = "fi6-skeleton-unsigned-2026-09-03"

# 🔴 导入期即校验版本号与签认状态一致（原 `test_rule_version_marked_unsigned` 的职责，
# 迁移后由底座承接，且比原来更早——导入即校验，不必等测试跑到）。
CRITERIA.assert_rule_version(RULE_VERSION)


def audit_decision(**fields: Any) -> dict[str, Any]:
    """构造写审计用的 `decision`，**恒带当时生效的 `RULE_VERSION`**。

    🔴 **G-5 反向依赖**（Shao Peishen 2026-09-03 拍板 `G-5 = (a)`）：判据底座**不接**
    `AuditLogger`（保其零依赖）；改由**各场景引擎**在 `record(AuditEvent(...))` 时把
    `RULE_VERSION` 写进 `decision`。**方向是审计日志指向判据版本，不是判据模块去写日志。**
    刻意每个场景各留一份、不收进底座——收进去就等于底座反向知道了场景与 audit。
    """
    return {**fields, "rule_version": RULE_VERSION}


# ── fail-loud 文案 ──
U9C_TXN_NOT_READY = (
    "U9C 应付/应收交易流水的实时取数通道未核实。real 模式一律 fail-loud，不得回退 mock。"
)

CASE_LIBRARY_ABSENT = (
    "「历史异常案例库」在本项目内无既有载体（本泳道 2026-09-03 实测），属须从零建的"
    "知识型资产。无案例库时检测器 MUST NOT 以「无历史即正常」放行——那正是把空数据"
    "当成阴性结论，与静默回退同族。"
)

FI3_NO_ENTITY = (
    "FI3 付款校验目前无工程实体（`4-数字员工/财务部/` 下只有 FI1 与 FI2，本泳道 "
    "2026-09-03 实测）。#471 所述「联动 FI3 付款校验结果」在建造时无对象可接；"
    "FI3 排 2026-11、早于本场景 2027-04，顺序不倒置，但依赖须等其落地。"
)
