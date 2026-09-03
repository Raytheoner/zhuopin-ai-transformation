"""FI9 配置 —— 数据源开关 ＋ 规则版本 ＋ **未签认判据与未核实数据源占位**。

🔴 本文件的空值比其余四个场景更硬气一点，理由在 `__init__.py`：本场景产出是**对外申报
材料**。一个编出来的资本化判据不会报错，但会写进报给政府的材料里。
"""
from __future__ import annotations

import os

# ── 数据源开关（骨架期只有 mock）──
DATA_SOURCE_DEFAULT = os.environ.get("FI9_DATA_SOURCE", "mock").strip().lower()

# ── 🔴 未签认判据（一律 None）──
# 资本化/费用化判据：会计准则 ＋ 企业会计政策的落地规则集
CAPITALIZATION_CRITERIA = None
# 高新认定政策库：研发费用归集口径、人员/费用范围、辅助账格式要求
HIGH_TECH_POLICY_LIBRARY = None
# 研发费用占比等核心指标的计算口径（分子分母各含什么，准则与高新口径并不一致）
RD_RATIO_DEFINITION = None

# ── 规则注册表版本 ──
RULE_VERSION = "fi9-skeleton-unsigned-2026-09-03"

# ── 🔴 数据源存在性未核实（不是"还没接"，是"不知道有没有"）──
TIMESHEET_SYSTEM_EXISTS = None
TIMESHEET_SYSTEM_UNVERIFIED = (
    "「工时系统」在本仓库内**无任何既有取数指针**（本泳道 2026-09-03 实测）：`工时` 二字"
    "仅作为依赖名出现于 4 份规划文档；代码侧唯一一处是 "
    "`zhuopin_platform/shared_tools/models.py:126` 的注释「用于 SMT 工时查询」——"
    "那是 product_id 字段的用途说明，不是连接器。**是否存在、由谁维护、能否取数，"
    "三问皆未核实**。承接方开工第一件事应是核实它是否存在，而不是假设它存在。"
    "人工费用归集在该问题解决前 MUST fail-loud，不得以任何分摊估算代替。"
)

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
