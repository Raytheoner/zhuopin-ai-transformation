"""FI5 配置 —— 数据源开关 ＋ 规则版本 ＋ **未签认判据占位**。

🔴 **本文件最要紧的一条**：凡须财务侧签认的阈值，一律落成 `None`，**不给默认数**。
理由与本项目其他「静默回退」事故同族——一个看似合理的默认值不会报错、不产生任何信号，
却已经在替财务部做判断。`tests/test_scaffold.py` 有一条用例专门守这几个 `None`，
谁填了数、CI 立刻红。签认到位后的正确改法见下方「签认落地方式」。

签认落地方式（design 审后执行，不在骨架内）：
  1. 财务侧交付《报销政策判据表》（差旅标准／招待限额／超预算阈值／风险分级边界），实名签认；
  2. 本文件把对应常量从 `None` 改为实数、`RULE_VERSION` 升版；
  3. 引擎侧读到 `None` 即 fail-loud（不得回退到任何内置数），该行为由引擎单测守。
"""
from __future__ import annotations

import os

# ── 数据源开关（骨架期只有 mock；u9c 报销模块端点是否在既有 10 个财务侧端点内**未经核实**）──
DATA_SOURCE_DEFAULT = os.environ.get("FI5_DATA_SOURCE", "mock").strip().lower()

# ── 🔴 未签认判据（一律 None，不得填默认数；见本文件首部说明）──
# 差旅标准：{职级: 每日住宿上限}，知识型资产，须财务侧产出并签认
TRAVEL_STANDARD_TABLE = None
# 招待限额：{场合类型: 人均上限}，同上
ENTERTAINMENT_LIMIT_TABLE = None
# 超预算拦截阈值：占用预算余额比例超此 → 拦截并通知上级
L2_BUDGET_BLOCK_PCT = None
# 异常报销风险分级边界：{风险等级: 判定条件}（超标／频繁／关联交易三类）
RISK_GRADE_BOUNDARIES = None

# ── 规则注册表版本（IATF 单一可信源；签认落地时升版）──
RULE_VERSION = "fi5-skeleton-unsigned-2026-09-03"

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
