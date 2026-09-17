"""Q2 数据契约：输入（D 段文本＋标签＋抽取置信）→ 逐条发现 → 整份判定。

承接点＝ D 段全文（评估件 §5.1），不是 QD-A 的 12 字段；12 字段只服务红线④追溯字段与安全相关分流入口。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Confidence(str, Enum):
    """与 QD-A `field_extractor.Confidence` 同字面，便于适配。"""
    HIGH = "HIGH"
    MED = "MED"
    LOW = "LOW"


@dataclass(frozen=True)
class TraceField:
    """红线④追溯字段的一条（值＋抽取置信）。P2：只有 HIGH ＋ 空 才算「真为空」。"""
    name: str
    value: str
    confidence: Confidence

    @property
    def confirmed_empty(self) -> bool:
        return self.confidence == Confidence.HIGH and not self.value.strip()

    @property
    def extraction_miss(self) -> bool:
        return self.confidence != Confidence.HIGH and not self.value.strip()


@dataclass
class EightDInput:
    """一份待评 8D。`sections` 的 key 为 D1…D8（或映射前的 七步法「一」…「七」／客户模板自定义键）。"""
    report_id: str
    sections: dict[str, str]
    scene: str | None                      # 编制人勾选：制造／研发；None＝未勾选
    template: str = "标准8D"               # 标准8D／七步法／客户模板
    safety_related: bool | None = None     # QD-A `safety_related`；None＝未抽到
    safety_confidence: Confidence = Confidence.LOW
    asil_level: str = ""                   # "", "QM", "A", "B", "C", "D"
    trace_fields: tuple[TraceField, ...] = ()
    is_external: bool = False              # 外部编制（客户侧模板／供应商编制；J6 入集、判定不区分）
    meta: dict[str, Any] = field(default_factory=dict)


class RuleStatus(str, Enum):
    PASS = "得分"
    FAIL = "不得分"
    PARTIAL = "部分得分"
    PENDING = "待人工（语义层未上线）"
    NA = "不适用（场景不符）"


@dataclass(frozen=True)
class RuleFinding:
    rule_id: str
    step: str
    dimension: str
    judge_method: str
    max_score: float
    score: float
    status: RuleStatus
    evidence: str = ""


class RedlineStatus(str, Enum):
    CLEAR = "未触发"
    TRIGGERED = "触发（自动判 D）"
    SUSPECTED = "疑似触发·转人工裁决"
    MANUAL_CHECK = "抽取未命中·转人工核"
    NOT_ACCEPTED = "本批不验收·转人工"


@dataclass(frozen=True)
class RedlineFinding:
    redline_no: int
    step: str
    description: str
    status: RedlineStatus
    evidence: str = ""


class Disposition(str, Enum):
    """处置建议（M3 ③：一律「建议」，退回决定由质量工程师签发）。"""
    STRUCTURAL_RETURN = "建议结构性退回"
    RETURN_REWRITE = "建议退回重写"
    RETURN_REVISE = "建议退回修改"
    PASS_MINOR = "建议小修改后通过"
    ARCHIVE = "建议归档"
    MANUAL = "转人工裁决"


@dataclass
class Verdict:
    report_id: str
    scene: str
    scene_flags: tuple[str, ...]
    structural_return: bool
    structural_empty_sections: tuple[str, ...]
    redlines: tuple[RedlineFinding, ...]
    rules: tuple[RuleFinding, ...]
    score_auto: float          # 已自动判定条目实得
    score_pending_max: float   # 语义层待人工条目的满分合计
    score_max: float           # 本场景满分（100）
    grade: str | None          # 语义层全落定才有单一等级
    grade_range: tuple[str, str]   # (下界等级, 上界等级)
    disposition: Disposition
    needs_manual_review: bool = True     # L2 恒真
    automation_level: str = "L2"
    notes: tuple[str, ...] = ()

    @property
    def score_upper(self) -> float:
        return round(self.score_auto + self.score_pending_max, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "scene": self.scene,
            "scene_flags": list(self.scene_flags),
            "structural_return": self.structural_return,
            "structural_empty_sections": list(self.structural_empty_sections),
            "redlines": [{"no": r.redline_no, "step": r.step, "status": r.status.value, "evidence": r.evidence} for r in self.redlines],
            "rules": [{"rule_id": r.rule_id, "status": r.status.value, "score": r.score, "max": r.max_score, "evidence": r.evidence} for r in self.rules],
            "score_auto": self.score_auto,
            "score_pending_max": self.score_pending_max,
            "score_upper": self.score_upper,
            "score_max": self.score_max,
            "grade": self.grade,
            "grade_range": list(self.grade_range),
            "disposition": self.disposition.value,
            "needs_manual_review": self.needs_manual_review,
            "automation_level": self.automation_level,
            "notes": list(self.notes),
        }
