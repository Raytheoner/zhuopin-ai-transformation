"""FI9 配置 —— 数据源开关 ＋ 规则版本 ＋ **未签认判据注册表与未核实数据源占位**。

🔴 本文件的空值比其余四个场景更硬气一点，理由在 `__init__.py`：本场景产出是**对外申报
材料**。一个编出来的资本化判据不会报错，但会写进报给政府的材料里。

📌 **2026-09-03 迁移（`criteria-signoff-platform` A4 段）**：三条裸 `None` 判据常量 ＋ 本地
守卫用例改为**引用平台底座** `zhuopin_platform.criteria_signoff`；🔴 **行为一处未变**
（未签认 ⇒ 值恒 `None`、读取即抛，无 `default=` 旁路）。

🔴 **`TIMESHEET_SYSTEM_EXISTS` 刻意不进注册表**（Shao Peishen 2026-09-03 拍板 `G-2 = (a)`）：
它是**存在性未核实**，解除路径是**去问一个人**（已立队列 §一 `#477`），不是签认。
"""
from __future__ import annotations

import os
from typing import Any

from zhuopin_platform.criteria_signoff import CriteriaRegistry, Criterion

# ── 数据源开关（骨架期只有 mock）──
DATA_SOURCE_DEFAULT = os.environ.get("FI9_DATA_SOURCE", "mock").strip().lower()

# ── 🔴 未签认判据注册表（**唯一**声明处；本文件内不得再有任何裸 `None` 判据常量）──
CRITERIA = CriteriaRegistry("FI9", [
    Criterion(
        key="CAPITALIZATION_CRITERIA",
        question="资本化/费用化判据：会计准则 ＋ 企业会计政策落到本公司的规则集是什么",
        owner="财务侧",
        note="判错会写进报给政府的申报材料，代价比其余财务场景高一个量级",
    ),
    Criterion(
        key="HIGH_TECH_POLICY_LIBRARY",
        question="高新认定政策库：研发费用归集口径、人员/费用范围、辅助账格式要求各是什么",
        owner="财务侧",
        note="辅助账的**格式本身**就由政策库定，未签认前不得用任何模板猜测",
    ),
    Criterion(
        key="RD_RATIO_DEFINITION",
        question="研发费用占比等核心指标的计算口径：准则口径与高新口径的分子分母各含什么",
        owner="财务侧",
        note="两套口径并不一致，须分别定义、分别计算，不得以一套充当两者",
    ),
])

# ── 规则注册表版本 ──
RULE_VERSION = "fi9-skeleton-unsigned-2026-09-03"

# 🔴 导入期即校验版本号与签认状态一致（原 `test_rule_version_marked_unsigned` 的职责）。
CRITERIA.assert_rule_version(RULE_VERSION)


def audit_decision(**fields: Any) -> dict[str, Any]:
    """构造写审计用的 `decision`，**恒带当时生效的 `RULE_VERSION`**。

    🔴 **G-5 反向依赖**（Shao Peishen 2026-09-03 拍板 `G-5 = (a)`）：判据底座**不接**
    `AuditLogger`（保其零依赖）；改由**各场景引擎**在 `record(AuditEvent(...))` 时把
    `RULE_VERSION` 写进 `decision`。**方向是审计日志指向判据版本，不是判据模块去写日志。**

    本场景产出对外申报材料，审计轨迹不可简化 ⇒ 人工确认与改判亦须经此口留痕。
    """
    return {**fields, "rule_version": RULE_VERSION}


# ── 🔴 数据源存在性未核实（不是「还没接」，是「不知道有没有」⇒ 刻意不进 `CRITERIA`）──
TIMESHEET_SYSTEM_EXISTS = None
TIMESHEET_SYSTEM_UNVERIFIED = (
    "「工时系统」在本仓库内**无任何既有取数指针**（本泳道 2026-09-03 实测）：`工时` 二字"
    "仅作为依赖名出现于 4 份规划文档；代码侧唯一一处是 "
    "`zhuopin_platform/shared_tools/models.py:126` 的注释「用于 SMT 工时查询」——"
    "那是 product_id 字段的用途说明，不是连接器。**是否存在、由谁维护、能否取数，"
    "三问皆未核实**。承接方开工第一件事应是核实它是否存在，而不是假设它存在。"
    "人工费用归集在该问题解决前 MUST fail-loud，不得以任何分摊估算代替。"
    "🔴 **不并入 `CRITERIA` 注册表**（`G-2 = (a)`）：它靠**去问一个人**解除、不靠签认解除，"
    "核实动作已独立立行为队列 §一 `#477`。"
)

# ── 🔴 EE-3：本场景带出 OEM 项目标识，接法五条定夺项已裁（隔离层接线见 oem_isolation.py）──
OEM_ISOLATION_DECISION = (
    "🔴 **Shao Peishen 2026-09-03 裁决 `EE-3` ＝ (a)**：本场景**会**带出 OEM 项目标识，"
    "**按接 `zhuopin_platform.data_isolation_layer` 设计**。原话理由：研发费用归集按项目走，"
    "OEM 项目几乎必然出现；**这一条错了是合规问题，宁可多接**。"
    "⇒ 接法须守根 `CLAUDE.md` §7 红线 3（OEM 数据按客户路由、禁跨库）与 "
    "`5-平台底座/CLAUDE.md` 的隔离边界。"
    "✅ **接法命中 openspec 门槛②（涉鉴权与数据可见性），已走 design 审**："
    "`openspec/changes/fi9-rd-cost-mvp/design.md` §定夺项五条已于 2026-09-03 由 Shao Peishen "
    "逐条裁定（①(c)分层／②(c)立豁免款+三道锁／③(b)允许归集禁汇总／④(a)研发侧认定"
    "财务侧使用／⑤(a)不卡），隔离层接线落地在 `fi9_rd_cost/oem_isolation.py`。"
    "🔴 **本常量记录的是「已裁决」这件事本身，不是防后来者假设「未裁」——"
    "它防的是后来者按 FI5/FI6/FI8 的「财务数据不隔离」结论顺手把本场景也归进去** —— "
    "那个结论对本场景不成立，即便五条已裁，本场景仍是 OEM 隔离场景。"
    "⚠️ **`tasks.md` §3 起（cost-collection/capitalization-rules/aux-ledger-and-filing 三个 "
    "capability 的业务引擎）仍未开工**——五条定夺项只解决了「隔离层怎么接」，不代表 "
    "§2 其余六条收口项（2.1/2.2/2.3/2.5/2.7/2.8）已完成。"
)


def cross_oem_aggregation_enabled() -> bool:
    """②(c) 高新认定辅助账跨 OEM 汇总开关：`FI9_CROSS_OEM_AGGREGATION=on|off`（**默认 OFF**）。

    判据来源＝ design.md §定夺项 ②，Shao Peishen 2026-09-03 裁 (c)（立法定申报豁免款 ＋
    三道锁：限用途／限流向／限留痕与人工闸，见 `EXTERNAL_FILING_GATE`）。

    🔴 **翻开条件 ＝ ② 的豁免款已正式立进《OEM 数据隔离规范》**
    （`3-治理与合规/OEM数据隔离规范.md` §2/§3；待批文本见变更包内
    `oem-isolation-spec-amendment-draft.md`，因触碰区与 `oem-chroma-ownership-rejudge`
    在办改动重叠，规范修订须等其收口后并批，且须 Shao Peishen 本人批准）。

    **裁决已下 ≠ 规范已立**：`②` 的三道锁已由本人裁定，但那是"批准一种做法"，不等于
    "这种做法已经写进 IATF 正式规范"——代码若先于规范落地，在"单一可信源"审核标准下
    站不住（同族先例：`SC8_KIT_DATE_RULE1`，判据已签认但仍须姚祖怡复核对照表签认
    才可翻开，是"两次门槛"而非"判据签一次就地生效"）。

    OFF = `oem_isolation.cross_oem_filing_gate()` 一律 fail-loud（不静默返回空结果）；
    ON 之后仍须过三道锁的必填字段校验，并非"翻开即放行"。
    """
    return os.environ.get("FI9_CROSS_OEM_AGGREGATION", "off").strip().lower() in ("on", "1", "true", "yes")

# ── 🔴 对外材料红线 ──
EXTERNAL_FILING_GATE = (
    "本场景产出用于**政府申报与高新认定**，属对外材料。按根 `CLAUDE.md` §7-4 口径，"
    "结论一律须人工确认后方可使用，**AI 不得自动出具对外文件**。"
    "辅助账、加计扣除备查资料包等任何可直接对外提交的产物，"
    "MUST 标注「AI 归集建议，须财务/研发总监审核确认」，且 MUST NOT 具备"
    "「一键生成即可提交」的路径。"
)

# ── fail-loud 文案 ──
U9C_PROJECT_COST_NOT_READY = (
    "U9C 项目成本模块的取数通道未核实。real 模式一律 fail-loud，不得回退 mock。"
)
