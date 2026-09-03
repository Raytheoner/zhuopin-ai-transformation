"""FI5 配置 —— 数据源开关 ＋ 规则版本 ＋ **未签认判据注册表**。

🔴 **本文件最要紧的一条**：凡须财务侧签认的阈值，一律**未签认**，**不给默认数**。
理由与本项目其他「静默回退」事故同族——一个看似合理的默认值不会报错、不产生任何信号，
却已经在替财务部做判断。

📌 **2026-09-03 迁移（`criteria-signoff-platform` A4 段）**：本文件原先是**四条裸 `None`
常量 ＋ 一条本地守卫用例**；rule-of-three 已触发（FI5/FI6/FI8/FI9/FI10 五份手抄，5 > 3），
现改为**引用平台底座** `zhuopin_platform.criteria_signoff`。
🔴 **行为一处未变**：未签认 ⇒ 值恒 `None`、读取即抛（`CriterionNotSignedOffError`），
且注册表**没有** `default=` 旁路。变的只是「这条纪律写在哪」。

签认落地方式（三步齐了才动，缺一步都不要动）：
  1. 财务侧交付《报销政策判据表》（差旅标准／招待限额／超预算阈值／风险分级边界），实名签认；
  2. 本文件把对应 `Criterion` 改为 `.signed(值, Signoff(...))`、`RULE_VERSION` 升版；
  3. 引擎侧读到未签认判据即 fail-loud（不得回退到任何内置数），该行为由底座与场景单测共同守。
"""
from __future__ import annotations

import os
from typing import Any

from zhuopin_platform.criteria_signoff import CriteriaRegistry, Criterion

# ── 数据源开关（骨架期只有 mock；u9c 报销模块端点是否在既有 10 个财务侧端点内**未经核实**）──
DATA_SOURCE_DEFAULT = os.environ.get("FI5_DATA_SOURCE", "mock").strip().lower()

# ── 🔴 未签认判据注册表（**唯一**声明处；本文件内不得再有任何裸 `None` 判据常量）──
CRITERIA = CriteriaRegistry("FI5", [
    Criterion(
        key="TRAVEL_STANDARD_TABLE",
        question="差旅标准：各职级每日住宿上限分别是多少",
        owner="财务侧",
        note="属知识型资产，须财务侧产出《报销政策判据表》后实名签认，不是从系统里取得到的数",
    ),
    Criterion(
        key="ENTERTAINMENT_LIMIT_TABLE",
        question="招待限额：各场合类型的人均上限分别是多少",
        owner="财务侧",
        note="同差旅标准，属知识型资产",
    ),
    Criterion(
        key="L2_BUDGET_BLOCK_PCT",
        question="占用预算余额超过百分之几即拦截并通知上级",
        owner="财务侧",
    ),
    Criterion(
        key="RISK_GRADE_BOUNDARIES",
        question="异常报销风险分级边界：超标／频繁／关联交易三类各按什么条件定级",
        owner="财务侧",
        note="「频繁」是几次/几天、「关联」如何识别，本项目当前均无成文口径",
    ),
])

# ── 规则注册表版本（IATF 单一可信源；签认落地时升版）──
RULE_VERSION = "fi5-skeleton-unsigned-2026-09-03"

# 🔴 版本号与签认状态的一致性在**导入期**即校验：尚有判据未签认而版本号不自陈 `unsigned`
# （或反之）立即抛。这一条原是本包 `test_rule_version_marked_unsigned` 的职责，
# 迁移后由底座承接，并且比原来更早、更硬——导入即校验，不必等测试跑到。
CRITERIA.assert_rule_version(RULE_VERSION)


def audit_decision(**fields: Any) -> dict[str, Any]:
    """构造写审计用的 `decision`，**恒带当时生效的 `RULE_VERSION`**。

    🔴 **G-5 反向依赖**（Shao Peishen 2026-09-03 拍板 `G-5 = (a)`）：判据底座
    **不接** `AuditLogger`（保其零依赖）；改由**各场景引擎**在
    `AuditLogger.record(AuditEvent(...))` 时把 `RULE_VERSION` 写进 `decision`。
    **方向是审计日志指向判据版本，不是判据模块去写日志。**

    刻意**每个场景各留一份**、不收进底座：收进去就等于底座反向知道了场景与 audit，
    G-5 否掉的正是那条依赖。四行的重复是这条依赖方向的代价，是划算的。

    用法::

        audit.record(AuditEvent(
            scenario="FI5", action="expense_audit", evaluator="某某某",
            automation_level="L2",
            decision=audit_decision(claim_id=claim.claim_id, risk_grade=grade),
        ))
    """
    return {**fields, "rule_version": RULE_VERSION}


# ── 真实端点未就绪文案（fail-loud 用，仿 FI1/SC8 `RealEndpointNotReadyError` 语义）──
U9C_EXPENSE_NOT_READY = (
    "U9C 报销模块端点未核实：本项目既有 10 个财务侧端点清单中是否含报销模块，"
    "至今无人核实过（队列 #470 状态列）。real 模式一律 fail-loud，不得回退 mock。"
)

# ── OCR 前置未验证文案 ──
OCR_NOT_VERIFIED = (
    "报销发票 OCR 精度未经本场景实测。FI2 2026-08-04 的 65.8% 结论针对的是逐字段结构化"
    "取数，与本场景的真伪/合规校验用途不同，**既不适用也不等于已验证可用**（全景规划 "
    "§0.2 2026-08-09 行）。启用 OCR 前须先跑一次针对报销发票的精度实测。"
)
