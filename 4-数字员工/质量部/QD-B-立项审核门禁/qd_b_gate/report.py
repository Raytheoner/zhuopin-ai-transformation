"""审核报告聚合（qd-b-review-gate）—— 任务 6.1/6.3/6.7（M5 两档/三档判定 + M7 报告聚合）。

聚合 A 类确定性规则 + C 类转人工（只验在否）+ B 类语义判定（MVP 占位）的判定结果，
产出 spec「立项审核报告输出契约」要求的六段式《立项审核报告》：
① 总判定（三档，评分层 scoring.py 已落地，收口-1 后三档生效）
② 阻断项清单 ③ 警告/提示清单 ④ 跨模块校验结果（C01-C10，openspec 任务4未实现，本报告如实留白）
⑤ 转人工待办项（C 类 4 条 + B 类 10 条占位）⑥ 审计元数据

AI 结论永远是"预审建议"，非终局（design.md D9 / L2 复核确认门禁，任务 6.4）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import ProposalDocument, RuleResult, Verdict
from .rules.engine import run_all
from .rules.registry import RuleRegistry, load_registry
from .scoring import ScoreResult, score

DISCLAIMER = "⚠ AI 预审建议，立项决策在评审委员会/PMO 复核确认（L2 人工确认门禁，AI 结论非终局）"
CROSS_MODULE_NOTE = "C01–C10 跨模块校验尚未实现（openspec 任务 4，扩容期补齐），本报告不含跨模块判定结果"


@dataclass
class GateReport:
    verdict: str                          # 合格 / 有条件合格 / 不合格
    score_result: ScoreResult
    blocking_items: list[RuleResult]
    warning_items: list[RuleResult]
    manual_todo_items: list[RuleResult]   # C 类 4 条 + B 类 10 条占位
    all_results: list[RuleResult]
    template_version: str
    rule_version: str
    project_type: str
    sample_id: str = ""
    cross_module_items: list[RuleResult] = field(default_factory=list)
    disclaimer: str = DISCLAIMER
    cross_module_note: str = CROSS_MODULE_NOTE

    @staticmethod
    def _render_items(items: list[RuleResult]) -> list[str]:
        out = []
        for r in items:
            line = f"  - 规则{r.rule_id} {r.check_item}：{r.evidence}"
            if r.suggestion:
                line += f"｜建议：{r.suggestion}"
            out.append(line)
        return out

    def to_text(self) -> str:
        """六段式文本报告（部门/评审委员会可读）。"""
        head = "❌ 一票否决" if self.score_result.veto else f"得分 {self.score_result.total_score:.2f}"
        lines = [
            f"《立项审核报告》｜样本：{self.sample_id or '(未命名)'}",
            self.disclaimer,
            "",
            f"① 总判定：{self.verdict}（{head}）",
            "",
            f"② 阻断项清单（{len(self.blocking_items)} 条）：",
            *(self._render_items(self.blocking_items) or ["  无"]),
            "",
            f"③ 警告/提示清单（{len(self.warning_items)} 条）：",
            *(self._render_items(self.warning_items) or ["  无"]),
            "",
            f"④ 跨模块校验结果：{self.cross_module_note}",
            "",
            f"⑤ 转人工待办项（{len(self.manual_todo_items)} 条）：",
            *(self._render_items(self.manual_todo_items) or ["  无"]),
            "",
            f"⑥ 审计元数据：模板版本={self.template_version}｜规则版本={self.rule_version}"
            f"｜项目类型={self.project_type or '未识别'}",
        ]
        if self.score_result.provisional:
            lines.append(f"  ⚠ 暂定：{self.score_result.pending} 条 A 类规则未实现（视为通过），全量实现后复核")
        return "\n".join(lines)


def build_report(
    doc: ProposalDocument,
    *,
    results: list[RuleResult] | None = None,
    score_result: ScoreResult | None = None,
    registry: RuleRegistry | None = None,
    rule_version: str = "",
    sample_id: str = "",
) -> GateReport:
    """聚合规则判定 → GateReport。results/score_result 可由调用方预算好传入，避免重复计算。"""
    reg = registry or load_registry()
    results = results if results is not None else run_all(doc, reg)
    sr = score_result if score_result is not None else score(results, reg)

    blocking = [r for r in results if r.is_blocking]
    warning = [r for r in results if r.verdict == Verdict.WARN
              or (r.verdict == Verdict.FAIL and not r.is_blocking)]
    manual = [r for r in results if r.verdict == Verdict.MANUAL]

    return GateReport(
        verdict=sr.tier,
        score_result=sr,
        blocking_items=blocking,
        warning_items=warning,
        manual_todo_items=manual,
        all_results=results,
        template_version=doc.template_version,
        rule_version=rule_version or reg.rule_version,
        project_type=doc.project_type,
        sample_id=sample_id,
    )
