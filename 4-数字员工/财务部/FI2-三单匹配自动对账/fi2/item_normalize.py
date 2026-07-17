"""料品编码归一化预处理（R1 附注，design D14；权威文字见
`1-转型规划/FI2-FI3-规则定稿-交CC-2026-07-10.md` §一"匹配算法注意"）。

唐燕萍团队实操描述：AP/INV 侧同一料品的编码常见差异模式=字符空格、全角/半角、括号类符号、
"-"与"/"记法不一致——都是表层书写差异，不是真实编码不同。本模块只做覆盖大头的表层归一化，
供 `match_engine.build_item_matches` 的聚合 key 比对使用；不改写原始存储字段（原始 item_code
仍用于报告/审计/confirm CLI 展示，保持可读、可追溯）。

**不做**：模糊匹配 + 置信度分档 + 人工确认队列 + 自学习精确对照表——这是料品映射的长线
机制（见《FI2-FI3-规则定稿-交CC-2026-07-10.md》§一"料品映射"段），依赖真实《料品↔INV规格
型号/项目名称映射表》，留待 U9C/OCR 真实数据接入阶段另行设计，不在本次范围。
"""
from __future__ import annotations

import re
import unicodedata

# "-"/"/"及其全角变体、下划线，统一视作同一类分隔符
_SEPARATOR_MAP = str.maketrans({"/": "-", "－": "-", "—": "-", "_": "-"})
# 去空格 + 半角括号类符号（全角括号已被 NFKC 归一化为半角，故此处只需处理半角）
_STRIP_CHARS = re.compile(r"[\s()\[\]{}]")


def normalize_item_code(code: str | None) -> str:
    """去空格 / 全角转半角 / 括号类符号 / "-"与"/"等价类归一化，仅供匹配 key 比对用。"""
    if not code:
        return ""
    normalized = unicodedata.normalize("NFKC", code)
    normalized = normalized.translate(_SEPARATOR_MAP)
    normalized = _STRIP_CHARS.sub("", normalized)
    return normalized.upper()
