"""FI10 配置 —— 数据源开关 ＋ 规则版本 ＋ **三类性质不同的缺口占位**。

三类缺口性质不同，`__init__.py` 已列，此处是它们在配置层的落点：
  ⑴ **前置未满足**（芯片价格 API）—— 上游独立立行 `#475`，且其标的本身尚待判定；
  ⑵ **判据无源可取**（呆滞口径）—— 要"从 SC7 取"，但 SC7 那份口径尚未落地；
  ⑶ **判据未签认**（跌价测试与预警门限）—— 同其余四个财务场景。
"""
from __future__ import annotations

import os

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
)

# ── ⑵ 🔴 判据无源可取：L9 呆滞口径 ──
SLOW_MOVING_CRITERIA = None
L9_SOURCE_ABSENT = (
    "链 D 联动点 L9 要求本场景跌价口径与 `SC7` 呆滞口径**同口径**（#474：「呆滞口径应从"
    "那里取、不得另立一套」）。**但本泳道 2026-09-03 实测：SC7 工程实体里没有任何呆滞"
    "口径** —— `sc7_inventory/business_rules.py` 只有 R1 金额阈值 / R2 未认证供应商两条；"
    "`SC7/CLAUDE.md` 三处明写「呆滞库存处置」属②期深化（2027-01）**尚未落地**，其业务口径"
    "「待姚祖怡确认」。⇒ **要对齐的那个口径当前不存在**。本场景自行定义即等于 #474 明令"
    "禁止的「另立一套」，且属 🟡 change_criteria ⇒ **不代判，停下登记**。"
)

# ── ⑶ 🔴 未签认判据（一律 None）──
# NRV（可变现净值）的估算口径：售价取哪个、扣不扣销售费用与税金，准则给框架、落地要企业定
NRV_ESTIMATION_BASIS = None
# 库龄超期预警门限（多少天算超期？分不分物料类别？）
AGING_ALERT_THRESHOLD = None
# 项目终止未耗物料的预警口径（终止后多久触发？在途的怎么算？）
TERMINATED_PROJECT_ALERT_CRITERIA = None

# ── 规则注册表版本 ──
RULE_VERSION = "fi10-skeleton-unsigned-2026-09-03"

# ── ⑶' 🔴 OEM 隔离（本场景是五个财务场景里唯一明确触及的一个）──
OEM_ISOLATION_REQUIRED = (
    "OEM 项目计划（PLM，含 APQP/EOP 生命周期）涉 OEM 专属数据，按根 `CLAUDE.md` §7-3 "
    "**须按客户路由、禁跨库**，实现时不得混库（走 "
    "`zhuopin_platform.data_isolation_layer.OEMRouter`，跨库须抛 `CrossOEMAccessError`）。"
    "🔴 比亚迪/上汽/理想的项目数据严格隔离，不得交叉。"
)

# ── fail-loud 文案 ──
U9C_INVENTORY_NOT_READY = (
    "U9C 库存模块（账龄/在途采购）取数通道未核实。real 模式一律 fail-loud，不得回退 mock。"
)
