"""FI6 配置 —— 数据源开关 ＋ 规则版本 ＋ **未签认判据占位**。

🔴 同 FI5：凡须财务侧签认的判据一律落成 `None`，**不给默认数**。异常检测尤其容易被
「先随便设个 3 倍标准差」蒙混过去——那个数一旦落地就会静默决定谁被推给财务主管、谁被
放过，且不会报错。`tests/test_scaffold.py` 有用例守住。
"""
from __future__ import annotations

import os

# ── 数据源开关（骨架期只有 mock）──
DATA_SOURCE_DEFAULT = os.environ.get("FI6_DATA_SOURCE", "mock").strip().lower()

# ── 🔴 未签认判据（一律 None）──
# 金额突增：相对历史基线的判定口径（倍数？分位数？绝对额下限？三者如何组合，均未定）
AMOUNT_SURGE_CRITERIA = None
# 频率异常：窗口长度 ＋ 笔数上限（"频繁"是几次/几天，本项目无成文口径）
FREQUENCY_ANOMALY_CRITERIA = None
# 关联方识别口径：如何判定"关联"（供应商主数据比对？股权关系？亲属？）——未定
RELATED_PARTY_CRITERIA = None
# 高风险触发审批并推送财务主管的门限
L2_ESCALATION_CRITERIA = None

# ── 规则注册表版本 ──
RULE_VERSION = "fi6-skeleton-unsigned-2026-09-03"

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
