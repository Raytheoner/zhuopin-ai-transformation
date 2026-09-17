"""判定引擎：模板映射（判例 10）→ D0/D8 豁免（判例 2）→ 结构闸（判例 9）→ 红线 → 51 条评分 → 分级 → 分流（判例 6）→ audit。

🔴 顺序不得颠倒（#612 ⑶）：结构性退回先于一切红线语义判定；安全相关分流在评分之后、退回建议之前。
🔴 ASIL C/D ＝ AI 绝对禁区：命中即抛 `AsilExcludedError`，不出任何评分。
"""
from __future__ import annotations

from dataclasses import dataclass

from zhuopin_platform.audit import AuditEvent, AuditLogger

from . import checks, config
from .models import Confidence, Disposition, EightDInput, RuleFinding, RuleStatus, RedlineStatus, Verdict
from .redlines import evaluate_redlines
from .rules_loader import RuleSet, load
from .semantic import PendingSemantic, SemanticSource


class AsilExcludedError(RuntimeError):
    """涉 ASIL C/D 的 8D 不走本规则库自动评审（M3 ②，合规红线）。"""


@dataclass
class VerdictEngine:
    ruleset: RuleSet | None = None
    semantic: SemanticSource | None = None
    audit: AuditLogger | None = None
    evaluator: str = "待指定"

    def __post_init__(self) -> None:
        self.ruleset = self.ruleset or load()
        self.semantic = self.semantic or PendingSemantic()

    # ── 步骤 1：模板映射 ＋ D0/D8 豁免 ──
    def normalize_sections(self, doc: EightDInput) -> dict[str, str]:
        exempt = set(config.CRITERIA.value_of("J2_D0_D8_EXEMPT"))
        mapping = config.CRITERIA.value_of("J10_TEMPLATE_MAPPING")
        out: dict[str, str] = {}
        if doc.template == "七步法":
            for k, v in doc.sections.items():
                target = mapping["七步法"].get(k, k)
                out[target] = (out.get(target, "") + "\n" + v).strip()
        else:
            out = {k: v for k, v in doc.sections.items()}
        return {k: v for k, v in out.items() if k not in exempt}

    # ── 步骤 2：结构闸 ──
    def structural_empty(self, sections: dict[str, str], doc: EightDInput) -> tuple[str, ...]:
        required = config.CRITERIA.value_of("J9_STRUCTURAL_RETURN_SECTIONS")
        skip = {"D6"} if (doc.template == "客户模板" and config.CRITERIA.value_of("J10_TEMPLATE_MAPPING")["客户模板缺D6不扣分"]) else set()
        return tuple(k for k in required if k not in skip and not sections.get(k, "").strip())

    # ── 步骤 4：51 条评分 ──
    def score_rules(self, sections: dict[str, str], doc: EightDInput, scene: str) -> tuple[list[RuleFinding], float, float, float]:
        findings: list[RuleFinding] = []
        auto = pending_max = max_total = 0.0
        d3_extra_deduction = 0.0
        skip_steps = {"D6"} if (doc.template == "客户模板" and not sections.get("D6", "").strip()) else set()
        for rule in self.ruleset.for_scene(scene):
            if rule.step in skip_steps:
                findings.append(RuleFinding(rule.rule_id, rule.step, rule.dimension, rule.judge_method, rule.score, 0.0, RuleStatus.NA, "客户模板无 D6，不扣分（判例 10）"))
                continue
            max_total += rule.score
            if rule.is_semantic:
                ratio = self.semantic.rule_ratio(rule.rule_id, doc)
                if ratio is None:
                    pending_max += rule.score
                    findings.append(RuleFinding(rule.rule_id, rule.step, rule.dimension, rule.judge_method, rule.score, 0.0, RuleStatus.PENDING, "语义层未上线（PENDING.SEMANTIC_LAYER_ACCEPTANCE）"))
                    continue
                ev = f"{self.semantic.kind} 裁决比例 {ratio}"
            elif checks.has_check(rule.rule_id):
                ratio, ev = checks.run_check(rule, sections, scene)
                if rule.rule_id == "D3-06":
                    d3_extra_deduction = min(len(checks.d3_missing_subfields(sections.get("D3", ""))) * config.CRITERIA.value_of("M4_D3_SUBFIELD_DEDUCTION")["step"], rule.deduct_cap)
            else:
                raise NotImplementedError(f"规则 {rule.rule_id}（{rule.judge_method}）无检查器——不得静默跳过")
            score = round(rule.score * ratio, 2)
            status = RuleStatus.PASS if ratio >= 1 else (RuleStatus.FAIL if ratio <= 0 else RuleStatus.PARTIAL)
            auto += score
            findings.append(RuleFinding(rule.rule_id, rule.step, rule.dimension, rule.judge_method, rule.score, score, status, ev))
        # 判例 4／M4：子字段缺失按个数递增扣分，落在 D3 段内、封顶 8、段内不扣负
        if d3_extra_deduction:
            d3_auto = sum(f.score for f in findings if f.step == "D3")
            applied = min(d3_extra_deduction, d3_auto)
            auto -= applied
            findings.append(RuleFinding("D3-06·扣分", "D3", "子字段缺失递增扣分", "规则引擎", 0.0, -applied, RuleStatus.PARTIAL, f"扣 {applied}（拟扣 {d3_extra_deduction}，段内已得 {d3_auto}，不扣负）"))
        floor = config.CRITERIA.value_of("M15_SCORING_GENERAL_RULE")["total_floor"]
        return findings, round(max(auto, floor), 2), round(pending_max, 2), round(max_total, 2)

    # ── 主流程 ──
    def evaluate(self, doc: EightDInput) -> Verdict:
        if doc.asil_level.upper() in ("C", "D"):
            raise AsilExcludedError(f"{doc.report_id}: ASIL {doc.asil_level} 属 AI 绝对禁区，不走本规则库；须 FSE 双签人工评审")
        scene_cfg = config.CRITERIA.value_of("SCENE_LABEL_SOURCE")
        flags: list[str] = []
        scene = doc.scene or scene_cfg["default_when_missing"]
        if doc.scene is None:
            flags.append(scene_cfg["flag_when_missing"])
        if scene not in (config.SCENE_MFG, config.SCENE_RND):
            raise ValueError(f"场景标签非法：{scene!r}")
        if doc.is_external:
            flags.append("外部编制（J6 判定不区分）")

        sections = self.normalize_sections(doc)
        empties = self.structural_empty(sections, doc)
        notes: list[str] = []
        if empties:
            v = Verdict(doc.report_id, scene, tuple(flags), True, empties, (), (), 0.0, 0.0, self.ruleset.max_score(scene),
                        config.GRADE_D, (config.GRADE_D, config.GRADE_D), Disposition.STRUCTURAL_RETURN,
                        notes=(f"判例 9：{list(empties)} 整段为空，结构性退回，未进入红线语义判定链",))
            self._audit(doc, v)
            return v

        redlines = evaluate_redlines(self.ruleset.redlines, doc, sections, scene, self.semantic)
        findings, auto, pending_max, max_total = self.score_rules(sections, doc, scene)

        triggered = [r for r in redlines if r.status == RedlineStatus.TRIGGERED]
        manual_rl = [r for r in redlines if r.status in (RedlineStatus.SUSPECTED, RedlineStatus.MANUAL_CHECK, RedlineStatus.NOT_ACCEPTED)]
        upper = auto + pending_max
        if triggered:
            grade, rng = config.GRADE_D, (config.GRADE_D, config.GRADE_D)
            notes.append(f"红线 {[r.redline_no for r in triggered]} 触发 ⇒ D 级、不计总分（分数仅供修改参考）")
        else:
            lo, hi = self.ruleset.grade_of(auto), self.ruleset.grade_of(upper)
            rng = (lo, hi)
            grade = lo if pending_max == 0 else None
            if pending_max:
                notes.append(f"语义层待人工 {sum(1 for f in findings if f.status == RuleStatus.PENDING)} 条（{pending_max} 分），等级只给区间")

        # 判例 6／M3：安全相关分流在评分之后、退回建议之前
        safety_manual = config.CRITERIA.value_of("J6_SAFETY_MANUAL_ROUTE")
        if safety_manual and (doc.safety_related is True or doc.safety_related is None or doc.safety_confidence != Confidence.HIGH):
            disposition = Disposition.MANUAL
            notes.append("安全相关＝是／未确认 ⇒ 不走自动退回建议，一律转人工裁决（判例 6；QD-A 红线 3）")
        elif triggered:
            disposition = Disposition.RETURN_REWRITE
        elif grade is None or manual_rl:
            disposition = Disposition.MANUAL
            if manual_rl:
                notes.append(f"红线 {[r.redline_no for r in manual_rl]} 待人工裁决（P1／判例 11）")
        else:
            disposition = {config.GRADE_A: Disposition.ARCHIVE, config.GRADE_B: Disposition.PASS_MINOR,
                           config.GRADE_C: Disposition.RETURN_REVISE, config.GRADE_D: Disposition.RETURN_REWRITE}[grade]

        v = Verdict(doc.report_id, scene, tuple(flags), False, (), redlines, tuple(findings), auto, pending_max, max_total,
                    grade, rng, disposition, notes=tuple(notes))
        self._audit(doc, v)
        return v

    def _audit(self, doc: EightDInput, v: Verdict) -> None:
        if self.audit is None:
            return
        self.audit.record(AuditEvent(
            scenario=config.SCENARIO, action="8d_report_verdict", evaluator=self.evaluator,
            automation_level=config.AUTOMATION_LEVEL,
            decision=config.audit_decision({"report_id": v.report_id, "scene": v.scene, "grade": v.grade, "grade_range": list(v.grade_range),
                                            "score_auto": v.score_auto, "score_upper": v.score_upper, "disposition": v.disposition.value,
                                            "structural_return": v.structural_return, "semantic_source": self.semantic.kind}),
            data_sources={"sections": doc.meta.get("source", "mock"), "rules": self.ruleset.sha256},
            oem_context=doc.meta.get("oem", ""),
        ))
