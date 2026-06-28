"""FI1 配置 —— 数据源开关 + L2 阈值 + 规则版本。

⚠️ 临时口径（Paul 2026-06-29 占位）：L2 阈值与分类规则版本为**临时基线**，
   待财务 AI 对接人 7/31 定稿后替换（收口-1）；替换只改本文件 + 规则注册表，不改引擎。
"""
from __future__ import annotations

import os

# 数据源：mock（开发/回归）| csv（过渡期应急桥接，真实数据）| u9c（最终目标，端点 404 时 fail-loud）
DATA_SOURCE_DEFAULT = os.environ.get("FI1_DATA_SOURCE", "mock").strip().lower()

# ── L2 人工门禁阈值（临时·configurable·待对接人 7/31 定稿）──
# 负向差异（来料短缺）绝对差异率超此 → 需人工确认
L2_SHORTAGE_PCT = float(os.environ.get("FI1_L2_SHORTAGE_PCT", "0.03"))
# 超出标准损耗的部分占理论净用量比例超此 → 需人工确认
L2_OVERLOSS_PCT = float(os.environ.get("FI1_L2_OVERLOSS_PCT", "0.02"))

# ── 分类规则注册表版本（随规则表更新登记，IATF 单一可信源）──
RULE_VERSION = "fi1-temp-2026-06-29"   # 临时口径；对接人定稿后改版本号

# 真实端点未就绪原因（u9c 直读 fail-loud 文案）
U9C_MO_NOT_READY = (
    "U9C MO（UFIDA.U9.MO.MO.MO）/ 领料（MOPickList）走 CommonEntity/Query，"
    "外网当前 404，待 IT 开放或 LAN/VPN；过渡期用 FI1_DATA_SOURCE=csv 应急桥接"
)
