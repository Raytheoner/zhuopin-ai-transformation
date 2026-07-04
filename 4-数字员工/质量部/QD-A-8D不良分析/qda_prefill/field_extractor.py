"""12字段提取器 — DocumentSections → EightDRecord。

提取策略：确定性优先（正则），不依赖LLM，低置信字段明确标注。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from .doc_reader import DocumentSections


class Confidence(str, Enum):
    HIGH = "HIGH"   # 确定性提取（日期/关键词）
    MED  = "MED"    # 段落匹配（有节标头）
    LOW  = "LOW"    # 推断或缺失（需人工确认）


@dataclass
class FieldResult:
    value: str
    confidence: Confidence
    note: str = ""

    def __str__(self) -> str:
        return self.value


@dataclass
class EightDRecord:
    """§1.1 模板的12字段提取结果。"""
    case_id:             FieldResult
    customer_raw:        FieldResult   # 原始客户名（未令牌化）
    defect_description:  FieldResult   # 失效现象描述 D2
    defect_category:     FieldResult   # 不良分类
    safety_related:      FieldResult   # 安全相关 是/否
    containment:         FieldResult   # 临时对策 D3
    root_cause:          FieldResult   # 根本原因 D4
    corrective_actions:  FieldResult   # 纠正/预防 D5-D7
    fmea_reference:      FieldResult   # 关联FMEA条目（可选）
    material_supplier:   FieldResult   # 关联物料/供应商（可选）
    closure_date:        FieldResult   # 结案日期
    root_cause_verified: FieldResult   # 根因验证有效 是/否

    def to_dict(self) -> dict[str, dict]:
        return {
            "案例ID":       {"value": self.case_id.value,             "confidence": self.case_id.confidence.value,             "note": self.case_id.note},
            "客户(脱敏)":   {"value": self.customer_raw.value,         "confidence": self.customer_raw.confidence.value,         "note": self.customer_raw.note},
            "失效现象描述": {"value": self.defect_description.value,   "confidence": self.defect_description.confidence.value,   "note": self.defect_description.note},
            "不良分类":     {"value": self.defect_category.value,      "confidence": self.defect_category.confidence.value,      "note": self.defect_category.note},
            "安全相关":     {"value": self.safety_related.value,       "confidence": self.safety_related.confidence.value,       "note": self.safety_related.note},
            "临时对策(D3)": {"value": self.containment.value,          "confidence": self.containment.confidence.value,          "note": self.containment.note},
            "根本原因(D4)": {"value": self.root_cause.value,           "confidence": self.root_cause.confidence.value,           "note": self.root_cause.note},
            "纠正/预防(D5-D7)": {"value": self.corrective_actions.value, "confidence": self.corrective_actions.confidence.value, "note": self.corrective_actions.note},
            "关联FMEA条目": {"value": self.fmea_reference.value,       "confidence": self.fmea_reference.confidence.value,       "note": self.fmea_reference.note},
            "关联物料/供应商": {"value": self.material_supplier.value, "confidence": self.material_supplier.confidence.value,    "note": self.material_supplier.note},
            "结案日期":     {"value": self.closure_date.value,         "confidence": self.closure_date.confidence.value,         "note": self.closure_date.note},
            "根因验证有效": {"value": self.root_cause_verified.value,   "confidence": self.root_cause_verified.confidence.value,  "note": self.root_cause_verified.note},
        }


# ── 正则常量 ─────────────────────────────────────────────────────────────────

_CASE_ID_RE = re.compile(
    r"(?:案例.{0,4}[：:号]\s*|8[Dd][-_\s]*|编号.{0,4}[：:]\s*)"
    r"([A-Z0-9\-]{4,20}|8D[-\s]?\d{4}[-\s]\d+)",
    re.IGNORECASE,
)
_CASE_TITLE_RE = re.compile(r"8D\s*报告\s*[—\-–]?\s*(.{5,40}?)(?:\s|$)", re.IGNORECASE)

_DATE_RE = re.compile(
    r"(\d{4})\s*[-./年]\s*(\d{1,2})\s*[-./月]\s*(\d{1,2})\s*(?:日|号)?",
)

_SAFETY_KEYWORDS = re.compile(
    r"(?:ASIL|安全相关|功能安全|ISO\s*26262|安全等级|safety[- ]?related|functional[- ]?safety)",
    re.IGNORECASE,
)

_CATEGORY_MAP = {
    "设计": ["设计", "design", "电路设计", "软件设计", "结构设计"],
    "制程": ["制程", "工艺", "焊接", "装配", "SMT", "制造", "process"],
    "物料": ["物料", "来料", "原材料", "器件", "供应商来料", "material", "component"],
    "使用不当": ["使用不当", "操作不当", "用户", "客户操作", "misuse", "improper"],
}

_FMEA_RE = re.compile(r"(?:FMEA|pfmea|dfmea)[\s\-_]*([A-Z0-9\-]{2,20})", re.IGNORECASE)

_PART_NO_RE = re.compile(r"\b([A-Z][A-Z0-9]{3,}(?:[-_][A-Z0-9]+)*)\b")

_VERIFIED_YES = re.compile(
    r"(?:根因.{0,10}(?:验证有效|已验证|confirmed|effective)|验证结果.{0,5}(?:有效|通过|合格))",
    re.IGNORECASE,
)
_VERIFIED_NO = re.compile(
    r"(?:根因.{0,10}(?:验证无效|未验证|未通过|invalid)|验证结果.{0,5}(?:无效|不通过|不合格))",
    re.IGNORECASE,
)


# ── 主入口 ───────────────────────────────────────────────────────────────────

def extract_fields(doc: DocumentSections) -> EightDRecord:
    """从 DocumentSections 提取12字段，返回 EightDRecord。"""
    s = doc.sections
    full = doc.full_text
    header = doc.header_text

    return EightDRecord(
        case_id             = _extract_case_id(header, full),
        customer_raw        = _extract_customer(s.get("D1", ""), header),
        defect_description  = _extract_section(s, "D2", "失效现象描述"),
        defect_category     = _extract_category(s.get("D4", ""), full),
        safety_related      = _extract_safety(full),
        containment         = _extract_section(s, "D3", "临时对策"),
        root_cause          = _extract_section(s, "D4", "根本原因"),
        corrective_actions  = _extract_corrective(s),
        fmea_reference      = _extract_fmea(full),
        material_supplier   = _extract_material_supplier(s.get("D4", ""), full),
        closure_date        = _extract_closure_date(s.get("D8", ""), full),
        root_cause_verified = _extract_verified(s.get("D7", ""), s.get("D8", ""), full),
    )


# ── 字段提取函数 ─────────────────────────────────────────────────────────────

def _extract_case_id(header: str, full: str) -> FieldResult:
    for text in (header, full):
        m = _CASE_ID_RE.search(text)
        if m:
            return FieldResult(m.group(1).strip(), Confidence.HIGH)
        m = _CASE_TITLE_RE.search(text)
        if m:
            return FieldResult(m.group(1).strip(), Confidence.MED, "从标题推断，建议确认")
    return FieldResult("", Confidence.LOW, "未找到案例编号，请手动填写")


def _extract_customer(d1: str, header: str) -> FieldResult:
    for text in (d1, header):
        if not text:
            continue
        # 查找"客户：XXX"模式
        m = re.search(r"客户\s*[：:]\s*(.{2,20}?)(?:\s|$|，|,)", text)
        if m:
            return FieldResult(m.group(1).strip(), Confidence.MED,
                               "请按§1.2令牌化（OEM-A-01格式），映射关系存机密映射表")
        # 任何已知客户词汇
        m = re.search(r"([一-龥A-Za-z]{2,12}(?:汽车|集团|机械|动力|商用车|工程|重工))", text)
        if m:
            return FieldResult(m.group(1).strip(), Confidence.MED,
                               "识别到可能的客户名，请令牌化")
    return FieldResult("", Confidence.LOW, "未识别客户名，请手动填写并令牌化")


def _extract_section(sections: dict[str, str], key: str, label: str) -> FieldResult:
    text = sections.get(key, "").strip()
    if text:
        return FieldResult(text, Confidence.MED)
    return FieldResult("", Confidence.LOW, f"未找到{key}段落（{label}），请手动填写")


def _extract_category(d4: str, full: str) -> FieldResult:
    for text in (d4, full):
        for category, keywords in _CATEGORY_MAP.items():
            for kw in keywords:
                if kw.lower() in text.lower():
                    return FieldResult(category, Confidence.HIGH,
                                       f"关键词[{kw}]匹配")
    return FieldResult("", Confidence.LOW, "未能自动分类，请从设计/制程/物料/使用不当中选择")


def _extract_safety(full: str) -> FieldResult:
    if _SAFETY_KEYWORDS.search(full):
        return FieldResult("是", Confidence.HIGH, "检测到安全相关关键词，请确认ASIL等级")
    # 默认否，但用LOW置信——工程师必须确认
    return FieldResult("否", Confidence.LOW, "未检测到安全相关关键词，请人工确认（漏标有合规风险）")


def _extract_corrective(sections: dict[str, str]) -> FieldResult:
    parts = []
    for key in ("D5", "D6", "D7"):
        text = sections.get(key, "").strip()
        if text:
            parts.append(f"[{key}] {text}")
    if parts:
        return FieldResult("\n".join(parts), Confidence.MED)
    return FieldResult("", Confidence.LOW, "未找到D5/D6/D7段落，请手动填写纠正/预防措施")


def _extract_fmea(full: str) -> FieldResult:
    m = _FMEA_RE.search(full)
    if m:
        return FieldResult(m.group(0).strip(), Confidence.MED)
    return FieldResult("", Confidence.LOW, "未检测到FMEA条目编号（选填）")


def _extract_material_supplier(d4: str, full: str) -> FieldResult:
    for text in (d4, full):
        m = re.search(
            r"(?:料号|P/N|PN|零件号|part\s*no\.?)\s*[：:＃#]?\s*([A-Z][A-Z0-9\-]{3,15})",
            text, re.IGNORECASE
        )
        if m:
            return FieldResult(m.group(1).strip(), Confidence.MED,
                               "料号请按§1.2脱敏为 料号-A/B/C")
        m = re.search(
            r"供应商\s*[：:]\s*([一-龥A-Za-z]{2,20})",
            text
        )
        if m:
            return FieldResult(m.group(1).strip(), Confidence.MED,
                               "供应商名请脱敏为 供应商-A/B")
    return FieldResult("", Confidence.LOW, "未识别关联物料/供应商（选填）")


def _extract_closure_date(d8: str, full: str) -> FieldResult:
    for text in (d8, full):
        m = _DATE_RE.search(text)
        if m:
            y, mo, d = m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
            return FieldResult(f"{y}-{mo}-{d}", Confidence.HIGH)
    return FieldResult("", Confidence.LOW, "未找到日期，请手动填写结案日期")


def _extract_verified(d7: str, d8: str, full: str) -> FieldResult:
    combined = f"{d7}\n{d8}"
    if _VERIFIED_YES.search(combined):
        return FieldResult("是", Confidence.MED)
    if _VERIFIED_NO.search(combined):
        return FieldResult("否", Confidence.MED)
    # 在 D8 找到任何正向词也算
    if d8 and re.search(r"(已关闭|close|结案|完成|有效)", d8, re.IGNORECASE):
        return FieldResult("是", Confidence.LOW, "从D8结案信息推断，请确认根因验证有效性")
    return FieldResult("", Confidence.LOW,
                       "无法自动判断，请手动确认根因是否经验证有效（D7/D8）——此字段影响样本入库质量")
