"""脱敏建议模块 — 识别实体，按§1.2范式生成令牌建议。

不自动替换原文，只输出映射建议，工程师确认后手动（或调用 apply_tokens）替换。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# ── 数据模型 ─────────────────────────────────────────────────────────────────

@dataclass
class EntityToken:
    original: str
    token: str
    entity_type: str   # oem/platform/component/supplier/part_no/person/location

@dataclass
class TokenState:
    """跨字段共享的令牌计数器，保证同一实体得到同一令牌。"""
    oem_level: str = "B"            # 默认B级，可通过 oem_level= 覆盖
    _counters: dict[str, int] = field(default_factory=dict)
    _assigned: dict[str, str] = field(default_factory=dict)  # original → token

    def assign(self, original: str, entity_type: str) -> str:
        if original in self._assigned:
            return self._assigned[original]
        key = entity_type
        self._counters[key] = self._counters.get(key, 0) + 1
        seq = self._counters[key]
        seq_label = chr(ord("A") + seq - 1) if seq <= 26 else str(seq)
        if entity_type == "oem":
            token = f"OEM-{self.oem_level}-{seq:02d}"
        elif entity_type == "platform":
            token = f"某车型平台-{seq_label}"
        elif entity_type == "component":
            token = f"电子器件-{seq_label}"   # 将被调用方细化为 电容-A/开关-A 等
        elif entity_type == "supplier":
            token = f"供应商-{seq_label}"
        elif entity_type == "part_no":
            token = f"料号-{seq_label}"
        elif entity_type == "person":
            token = f"工程师-{seq_label}"
        elif entity_type == "location":
            token = f"工厂-{seq_label}"
        else:
            token = f"实体-{entity_type}-{seq_label}"
        self._assigned[original] = token
        return token

    @property
    def mapping(self) -> dict[str, str]:
        return dict(self._assigned)


@dataclass
class ScrubbingResult:
    """对单段文本的脱敏建议结果。"""
    original: str
    suggested: str             # 替换后的建议文本
    entities: list[EntityToken]


# ── 识别模式 ─────────────────────────────────────────────────────────────────

# 常见客户/机构名（可按实际客户扩充）
_ORG_RE = re.compile(
    r"([一-龥]{2,8}(?:汽车|集团|机械|动力|商用车|工程机械|重工|农机|发动机|客车|"
    r"卡车|电动|科技|工业)(?:股份)?(?:有限)?(?:公司)?|"
    r"[A-Z][A-Za-z]{2,20}(?:\s+(?:Corp|Ltd|Inc|Co|Group|GmbH|AG))?)",
    re.UNICODE,
)

# 车型/平台代号（\b 右锚，防止部分匹配更长的料号/编号）
_PLATFORM_RE = re.compile(
    r"(?<![A-Z\d])"           # 左侧：不是更长编号的一部分
    r"([A-Z]{1,3}\d{2,3}[A-Z]?(?:EV|HEV|PHEV)?|"
    r"[一-龥]{1,4}(?:EV|Pro|Plus|X|S|i)?(?:\d)?型?|"
    r"[A-Z]{2,6}(?:平台|车型))"
    r"(?!\d)",                 # 右侧：后不接数字（否则是料号的一部分）
    re.UNICODE,
)

# 零件编号：大写字母开头 + 数字/字母混合（至少4位）
_PART_NO_RE = re.compile(r"\b([A-Z][A-Z0-9]{3,}(?:[-_][A-Z0-9]+)*)\b")

# 供应商
_SUPPLIER_RE = re.compile(
    r"供应商\s*[：:]\s*([一-龥A-Za-z]{2,20})|"
    r"([一-龥]{2,6}(?:电子|芯片|材料|科技|制造)(?:有限|公司)?)",
    re.UNICODE,
)

# 中文人名（常见姓氏 + 2-3字）
_PERSON_RE = re.compile(
    r"(?<![一-龥])([张王李赵陈吴刘杨黄周徐孙马朱胡郭林何高梁郑罗宋谢唐韩曹许邓]"
    r"[一-龥]{1,2})(?!\w)",
    re.UNICODE,
)

# 产线/地点
_LOCATION_RE = re.compile(
    r"([一-龥]{1,4}(?:工厂|产线|车间|基地|分厂)|"
    r"(?:工厂|factory|plant)\s*[A-Za-z\d])",
    re.IGNORECASE | re.UNICODE,
)


# ── 主入口 ───────────────────────────────────────────────────────────────────

def scrub_text(text: str, state: TokenState) -> ScrubbingResult:
    """对单段文本识别实体并生成令牌建议，不修改 state 的映射（view only per call）。"""
    entities: list[EntityToken] = []
    suggested = text

    # 处理顺序：先长后短，防止零件编号被公司名消费
    _apply(suggested, entities, state, _ORG_RE,      "oem",      0)
    suggested = _replace_from(text, entities)
    _apply(suggested, entities, state, _PLATFORM_RE, "platform", 0)
    suggested = _replace_from(text, entities)
    _apply(suggested, entities, state, _PART_NO_RE,  "part_no",  1)
    suggested = _replace_from(text, entities)
    _apply(suggested, entities, state, _SUPPLIER_RE, "supplier", 1)
    suggested = _replace_from(text, entities)
    _apply(suggested, entities, state, _PERSON_RE,   "person",   1)
    suggested = _replace_from(text, entities)
    _apply(suggested, entities, state, _LOCATION_RE, "location", 1)
    suggested = _replace_from(text, entities)

    return ScrubbingResult(original=text, suggested=suggested, entities=entities)


def _apply(text: str, entities: list[EntityToken], state: TokenState,
           pattern: re.Pattern, entity_type: str, group_idx: int) -> None:
    """在 text 中查找 pattern，为每个匹配项分配令牌（若未见过）。"""
    for m in pattern.finditer(text):
        raw = m.group(group_idx).strip() if m.group(group_idx) else ""
        if not raw or len(raw) < 2:
            continue
        # 排除已在 entities 中被更高优先级捕获的
        if any(e.original == raw for e in entities):
            continue
        token = state.assign(raw, entity_type)
        entities.append(EntityToken(original=raw, token=token, entity_type=entity_type))


def _replace_from(original: str, entities: list[EntityToken]) -> str:
    """用 entities 映射对文本做替换（长实体优先替换）。"""
    result = original
    for e in sorted(entities, key=lambda x: -len(x.original)):
        result = result.replace(e.original, e.token)
    return result


def build_token_table(state: TokenState) -> str:
    """生成 Markdown 格式的令牌映射表，供陈忱确认。"""
    mapping = state.mapping
    if not mapping:
        return "（未检测到需脱敏实体）"
    rows = ["| 原始内容 | 建议令牌 |", "|----------|---------|"]
    for original, token in sorted(mapping.items()):
        rows.append(f"| {original} | {token} |")
    return "\n".join(rows)
