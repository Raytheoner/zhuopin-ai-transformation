"""语义判定（qd-b-semantic-judge）—— MVP 极简版占位实现（design.md 任务 5）。

B 类 10 条真实语义判定（接入收口-2 半自动判断标准 v4 的 LLM 判据 + 二级置信度）
延后到扩容期（任务 5.2）。极简版先上线原则（QD-B极简版先上线-最小任务集-2026-07-09.md
M6）明确：B 类统一输出"待人工复核"，不做 AI 判定——避免未经业务判据校准的自动
判断污染报告，也呼应 design.md D6："判据未定前全部转人工兜底"。

真正实现 5.2 时：本模块替换为逐条 LLM 提示词 + 输出 schema + 置信阈值，
低置信默认转人工（D6 二级置信度）；`run_semantic_placeholder` 签名不变，
`rules/engine.py::run_semantic_rules` 调用方无需改动。
"""
from __future__ import annotations

from ..models import ProposalDocument, RuleResult, Verdict
from .registry import Rule

_PLACEHOLDER_NOTE = "语义判定占位：待人工复核（v4 判据接入前，MVP 统一转人工，design D6 兜底）"


def placeholder_result(rule: Rule) -> RuleResult:
    return RuleResult(
        rule_id=rule.rule_id, check_item=rule.check_item, verdict=Verdict.MANUAL,
        evidence=_PLACEHOLDER_NOTE, impl_class="B",
    )


def run_semantic_placeholder(doc: ProposalDocument, rules: list[Rule]) -> list[RuleResult]:
    return [placeholder_result(r) for r in rules]
