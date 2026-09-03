"""FI10 配置 —— 数据源开关 ＋ 规则版本 ＋ **两类性质不同的缺口占位**。

📌 **2026-09-03 迁移（`criteria-signoff-platform` A4 段）＋ `EE-4` 裁决落地**，三类缺口现为两类：
  ⑴ **前置未满足**（芯片价格 API）—— 上游独立立行 `#475`，且其标的本身尚待判定；
     🔴 **刻意不进 `CRITERIA` 注册表**（`G-2 = (a)`）：它靠**上游前置落地**解除、不靠签认解除。
  ⑵ **判据未签认**（NRV 口径／库龄门限／项目终止口径 ＋ **呆滞口径**）—— 已登记进 `CRITERIA`。
     🔴 呆滞口径原属「判据无源可取」（等 SC7），**是 `EE-4`「FI10 先定、SC7 后对齐」把它
     变成了一条标准的待签认判据**（`G-3 = (a)` 归进注册表）。⚠️ **「先定」不等于现在就填**
     —— 被定下的只是**口径归属**，判据本身仍未签认、值恒 `None`。

🔴 **行为一处未变**：未签认 ⇒ 值恒 `None`、读取即抛，注册表无 `default=` 旁路。
"""
from __future__ import annotations

import os
from typing import Any

from zhuopin_platform.criteria_signoff import CriteriaRegistry, Criterion

# ── 数据源开关（骨架期只有 mock）──
DATA_SOURCE_DEFAULT = os.environ.get("FI10_DATA_SOURCE", "mock").strip().lower()

# ── ⑴ 🔴 前置未满足：芯片价格 API（独立立行 #475）──
CHIP_PRICE_API = None
CHIP_PRICE_API_BLOCKED = (
    "芯片价格 API 尚未选型签约，已由队列 §一 `#475` 独立立行（跨域基础设施，与 O2 芯片"
    "预警共用，不挂单一场景名下）。⇒ **本场景中依赖该 API 的部分（芯片降价超阈值预警）"
    "前置未满足、停下登记，不实现**；不依赖它的部分照做。"
    "⚠️ 该前置的标的本身尚待判定，本场景不代下结论：前置总表 O2 行写「芯片**供货** API」、"
    "实施计划写「芯片**市场价格** API」，命名／服务对象／时点三项均不同，**是否同一项未定**；"
    "若是两项，「供货」那项尚未逾期（11 月底截止）、「价格」那项已逾期，紧迫度完全不同。"
    "🔴 **不并入 `CRITERIA` 注册表**（`G-2 = (a)`）：它靠上游前置落地解除、不靠财务侧签认解除。"
)

# ── ⑵ 🔴 未签认判据注册表（**唯一**声明处；本文件内不得再有任何裸 `None` 判据常量）──
CRITERIA = CriteriaRegistry("FI10", [
    Criterion(
        key="NRV_ESTIMATION_BASIS",
        question="NRV（可变现净值）的估算口径：售价取哪个、扣不扣销售费用与税金",
        owner="财务侧",
        note="准则给框架、落地要企业定",
    ),
    Criterion(
        key="AGING_ALERT_THRESHOLD",
        question="库龄超期预警门限：多少天算超期、分不分物料类别",
        owner="财务侧",
    ),
    Criterion(
        key="TERMINATED_PROJECT_ALERT_CRITERIA",
        question="项目终止未耗物料的预警口径：终止后多久触发、在途的怎么算",
        owner="财务侧",
    ),
    # 🔴 `G-3 = (a)`（Shao Peishen 2026-09-03 拍板）：以下 `owner` 与 `question` 逐字取自
    # `openspec/changes/criteria-signoff-platform/tasks.md` 4.1a，**不得改写**。
    Criterion(
        key="SLOW_MOVING_CRITERIA",
        question=(
            "呆滞物料的认定口径（库龄门限／周转率门限／例外物料）—— "
            "本口径 FI10 先出、SC7 后对齐（EE-4 拍板 2026-09-03），"
            "签认前须知会 SC7 口径确认人"
        ),
        owner="财务侧",
        note=(
            "口径用于存货跌价计提（进财务报表），故 owner 归财务侧而非 SC7 业务口径确认人；"
            "#474 要求与 SC7 呆滞口径同口径，但 SC7 那份属②期深化（2027-01）尚未落地，"
            "经 EE-4 裁为「FI10 先定、SC7 后对齐」——故它已不再是「无源可取」，而是一条标准待签认判据"
        ),
    ),
])

# 🔴 **本段是「登记进注册表」，不是「给它填值」** —— `SLOW_MOVING_CRITERIA` 与其余三条一样，
# 仍是未签认判据、值恒 `None`、读取即抛。谁在此填值即触发迁移验收失败（`tasks.md` 4.3）。

# ── 🔗 L9 呆滞口径的来龙去脉（**原文保留**，注册表的 `note` 不替代它）──
L9_SOURCE_ABSENT = (
    "链 D 联动点 L9 要求本场景跌价口径与 `SC7` 呆滞口径**同口径**（#474：「呆滞口径应从"
    "那里取、不得另立一套」）。**但本泳道 2026-09-03 实测：SC7 工程实体里没有任何呆滞"
    "口径** —— `sc7_inventory/business_rules.py` 只有 R1 金额阈值 / R2 未认证供应商两条；"
    "`SC7/CLAUDE.md` 三处明写「呆滞库存处置」属②期深化（2027-01）**尚未落地**，其业务口径"
    "「待姚祖怡确认」。⇒ **要对齐的那个口径当前不存在**。本场景自行定义即等于 #474 明令"
    "禁止的「另立一套」，且属 🟡 change_criteria ⇒ **不代判，停下登记**。"
)
L9_OWNERSHIP_RULED = (
    "🔴 **上段的「停下登记」已于 2026-09-03 收到裁决，`EE-4` ＝ (a)：口径归属定为"
    "「FI10 先定、SC7 后对齐」**（Shao Peishen 拍板）。⇒ 本场景先出呆滞口径**不再构成"
    "「另立一套」**，SC7 ②期深化（2027-01）落地时反过来与本口径对齐。"
    "⚠️ **「先定」不等于现在就填那个口径** —— 被定下的只是**口径归属**："
    "`SLOW_MOVING_CRITERIA` 仍是未签认判据、值恒 `None`、读取即抛，"
    "签认前**须知会 SC7 口径确认人**（`owner` 归财务侧，因口径用于跌价计提、进财务报表）。"
    "📌 上段原文刻意保留：它记的是 `#474` 与 `EE-4` 的来龙去脉——"
    "「这条判据为什么一度无源可取、又是被哪条裁决改变了性质」，删了就只剩结论、没有成因。"
)

# ── 规则注册表版本 ──
RULE_VERSION = "fi10-skeleton-unsigned-2026-09-03"

# 🔴 导入期即校验版本号与签认状态一致（原 `test_rule_version_marked_unsigned` 的职责）。
CRITERIA.assert_rule_version(RULE_VERSION)


def audit_decision(**fields: Any) -> dict[str, Any]:
    """构造写审计用的 `decision`，**恒带当时生效的 `RULE_VERSION`**。

    🔴 **G-5 反向依赖**（Shao Peishen 2026-09-03 拍板 `G-5 = (a)`）：判据底座**不接**
    `AuditLogger`（保其零依赖）；改由**各场景引擎**在 `record(AuditEvent(...))` 时把
    `RULE_VERSION` 写进 `decision`。**方向是审计日志指向判据版本，不是判据模块去写日志。**

    ⚠️ 本场景涉 OEM 隔离，写审计时另须按既有约定填 `AuditEvent.oem_context`；
    那是 `AuditEvent` 自己的字段，与本函数无关，别塞进 `decision`。
    """
    return {**fields, "rule_version": RULE_VERSION}


# ── ⑵' 🔴 OEM 隔离 ──
OEM_ISOLATION_REQUIRED = (
    "OEM 项目计划（PLM，含 APQP/EOP 生命周期）涉 OEM 专属数据，按根 `CLAUDE.md` §7-3 "
    "**须按客户路由、禁跨库**，实现时不得混库（走 "
    "`zhuopin_platform.data_isolation_layer.OEMRouter`，跨库须抛 `CrossOEMAccessError`）。"
    "🔴 比亚迪/上汽/理想的项目数据严格隔离，不得交叉。"
    "📌 **2026-09-03 校正**：本包骨架期曾写「本场景是五个财务场景里**唯一**触及 OEM 隔离的"
    "一个」——该句已被 `EE-3` 推翻（Shao Peishen 当日裁 FI9 研发费用归集按项目走、"
    "OEM 项目几乎必然出现，**会**带出 OEM 项目标识）。⇒ **FI9 亦触及**，其接法待 design 审。"
    "本场景的隔离要求不因此改变，改变的只是「唯一」二字。"
)

# ── fail-loud 文案 ──
U9C_INVENTORY_NOT_READY = (
    "U9C 库存模块（账龄/在途采购）取数通道未核实。real 模式一律 fail-loud，不得回退 mock。"
)
