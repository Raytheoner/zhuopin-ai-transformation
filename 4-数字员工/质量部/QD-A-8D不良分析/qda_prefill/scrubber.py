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
        elif entity_type == "email":
            token = f"邮箱-{seq_label}"
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

# 主机厂客户简称白名单——裸名不带后缀词，_ORG_RE 无法匹配（如"比亚迪"/"上汽"/"理想"）
# 注意：不使用 re.IGNORECASE，避免与 [一-鿿] 范围共用时的 Python 已知行为问题。
# 左边界：不接 CJK 字符或字母，防止"来自比亚迪"中"自"构成复合词头部。
# 右边界：只拦截后接 ASCII 字母/数字（防截断英文缩写），不拦截 CJK——
#         汉字中 OEM 名后必然紧跟动词/助词（如"比亚迪要求"），放行 CJK 右侧是有意设计。
_OEM_ALIAS_RE = re.compile(
    r"(?<![一-鿿A-Za-z])"
    r"(比亚迪|BYD|上汽|SAIC|理想汽车|理想|Li\s*Auto|蔚来|NIO|"
    r"吉利|GEELY|长城|GWM|奇瑞|CHERY|特斯拉|Tesla|广汽|GAC|"
    r"东风|DFAC|一汽|FAW|长安|Changan)"
    r"(?![A-Za-z\d])",
    re.UNICODE,
)

# 常见客户/机构名（带行业后缀词的通用规则）
_ORG_RE = re.compile(
    r"([一-龥]{2,8}(?:汽车|集团|机械|动力|商用车|工程机械|重工|农机|发动机|客车|"
    r"卡车|电动|科技|工业)(?:股份)?(?:有限)?(?:公司)?|"
    r"[A-Z][A-Za-z]{2,20}(?:\s+(?:Corp|Ltd|Inc|Co|Group|GmbH|AG))?)",
    re.UNICODE,
)

# 邮箱（含姓名+公司域名，身份指纹）——必须最先跑，否则 ORG/OEM 会吃掉 local-part
_EMAIL_RE = re.compile(r"[A-Za-z0-9][\w.\-]*@[\w.\-]+\.[A-Za-z]{2,}", re.UNICODE)

# 车型/平台代号。汉字分支须带明确平台标记（EV/DM/车型/平台/型号），
# 否则会把「联系/确认/邮箱」等常用词误判为平台（原 [一-龥]{1,4}…型? 后缀全可选之弊）。
_PLATFORM_RE = re.compile(
    r"(?<![A-Z\d])"           # 左侧：不是更长编号的一部分
    r"([A-Z]{1,3}\d{2,3}[A-Z]?(?:EV|HEV|PHEV)?|"
    r"[一-龥]{1,4}(?:EV|HEV|PHEV|DM|DMi|车型|平台|型号)|"
    r"[A-Z]{2,6}(?:平台|车型))"
    r"(?!\d)",                 # 右侧：后不接数字（否则是料号的一部分）
    re.UNICODE,
)

# 零件编号：大写字母开头 + 数字/字母混合（至少4位）
_PART_NO_RE = re.compile(r"\b([A-Z][A-Z0-9]{3,}(?:[-_][A-Z0-9]+)*)\b")

# 供应商（前缀 {1,6}：单字前缀如「某电子有限公司」也需捕获，原 {2,6} 会漏）
_SUPPLIER_RE = re.compile(
    r"供应商\s*[：:]\s*([一-龥A-Za-z]{2,20})|"
    r"([一-龥]{1,6}(?:电子|芯片|材料|科技|制造)(?:有限)?(?:公司)?)",
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

    # 处理顺序：邮箱最先（含姓名+域名，否则会被 ORG/OEM 吃掉 local-part 后残留域名）
    _apply(suggested, entities, state, _EMAIL_RE,      "email",    0)
    suggested = _replace_from(text, entities)
    # 先长后短，防止零件编号被公司名消费
    _apply(suggested, entities, state, _ORG_RE,        "oem",      0)
    suggested = _replace_from(text, entities)
    _apply(suggested, entities, state, _OEM_ALIAS_RE,  "oem",      1)  # 裸名补漏
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
        # 优先取指定组；为空则回退到首个非空捕获组（多分支正则如供应商有多组）
        val = m.group(group_idx) if group_idx <= (m.re.groups or 0) else None
        if not val:
            val = next((g for g in m.groups() if g), m.group(0))
        raw = (val or "").strip()
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
