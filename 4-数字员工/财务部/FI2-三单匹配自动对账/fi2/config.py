"""FI2 配置 —— 数据源开关 + 临时容差口径 + 规则版本。

⚠️ 临时口径（Paul 2026-07-07 拍板 D2，design.md）：容差量级为**临时基线**（mock 备料稿
   strawman 默认），待财务 AI 对接人唐燕萍 R1-R6 规则草案（约 2026-08 底）定稿后替换（收口-后续）；
   替换只改本文件 + 规则版本号，不改 match_engine.py / result_classify.py 的判定顺序/算法结构。
"""
from __future__ import annotations

import os

# 数据源：mock（开发/回归）| csv（应急桥接，接口占位）| u9c（最终目标，端点未开放时 fail-loud）
DATA_SOURCE_DEFAULT = os.environ.get("FI2_DATA_SOURCE", "mock").strip().lower()

# ── 四维匹配临时容差（strawman，待唐燕萍定稿）──
# 数量容差：±pct 或 ±N 个，两者取宽松者（任一满足即算容差内）
QTY_TOLERANCE_PCT = float(os.environ.get("FI2_QTY_TOLERANCE_PCT", "0.02"))
QTY_TOLERANCE_ABS = float(os.environ.get("FI2_QTY_TOLERANCE_ABS", "5"))
# 金额尾差容差（元/行）：区分"完全匹配"(diff=0) vs "金额微差"(0<|diff|<=此值) vs "数量金额不符"(超此值)
AMOUNT_TAIL_TOLERANCE = float(os.environ.get("FI2_AMOUNT_TAIL_TOLERANCE", "0.5"))
# "明细错位"判定用：同 PO 号总额差异容差（元），跨行配对校验通过线
PO_LEVEL_AMOUNT_TOLERANCE = float(os.environ.get("FI2_PO_LEVEL_AMOUNT_TOLERANCE", "0.5"))

# ── 分类规则版本（随规则表更新登记，IATF 单一可信源）──
RULE_VERSION = "fi2-temp-2026-07-07"   # 临时口径；唐燕萍定稿后改版本号

# 真实端点未就绪原因（u9c 直读 fail-loud 文案）
U9C_FI_NOT_READY = (
    "U9C 财务模块接口（PO/GR/发票）预计 2026-09 开放，当前不可用；"
    "过渡期可用 FI2_DATA_SOURCE=csv 应急桥接（接口占位，真实路径待接通）"
)
