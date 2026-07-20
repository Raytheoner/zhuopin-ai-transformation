"""规则引擎 —— 在解析后的立项书上运行注册规则，产出 RuleResult 列表。

未实现判定的规则标 PENDING（不冒判）。提供与 K 列试评的「试评对账」，
作为黄金基准回归的雏形（design.md D10）。
"""
from __future__ import annotations

from dataclasses import dataclass

from ..models import ProposalDocument, RuleResult, Verdict
from . import deterministic, semantic
from .registry import RuleRegistry, load_registry


def run_rules(doc: ProposalDocument, registry: RuleRegistry | None = None) -> list[RuleResult]:
    """对文档运行所有 A 类规则；已实现的判定，未实现的标 PENDING。"""
    reg = registry or load_registry()
    impl = deterministic.implemented_ids()
    out: list[RuleResult] = []
    for r in reg.by_class("A"):
        if r.rule_id in impl:
            out.append(deterministic._RULES[r.rule_id](doc, r))
        else:
            out.append(RuleResult(rule_id=r.rule_id, check_item=r.check_item,
                                  verdict=Verdict.PENDING, impl_class="A"))
    return out


def run_manual_class_rules(doc: ProposalDocument, registry: RuleRegistry | None = None) -> list[RuleResult]:
    """C 类 4 条转人工规则：只验在否不下结论（任务 6.2；实现见 deterministic.py 42/80/81/82）。"""
    reg = registry or load_registry()
    impl = deterministic.implemented_ids()
    out: list[RuleResult] = []
    for r in reg.by_class("C"):
        if r.rule_id in impl:
            out.append(deterministic._RULES[r.rule_id](doc, r))
        else:
            out.append(RuleResult(rule_id=r.rule_id, check_item=r.check_item,
                                  verdict=Verdict.PENDING, impl_class="C"))
    return out


def run_semantic_rules(doc: ProposalDocument, registry: RuleRegistry | None = None) -> list[RuleResult]:
    """B 类 10 条语义判定：MVP 占位"待人工复核"（任务 5.1/5.3，扩容期接入 v4 判据）。"""
    reg = registry or load_registry()
    return semantic.run_semantic_placeholder(doc, reg.by_class("B"))


def run_all(doc: ProposalDocument, registry: RuleRegistry | None = None) -> list[RuleResult]:
    """A + C(转人工) + B(语义占位) 全量判定 —— 报告聚合/评分/审计全链的输入（任务 6.1）。"""
    reg = registry or load_registry()
    return (run_rules(doc, reg) + run_manual_class_rules(doc, reg)
            + run_semantic_rules(doc, reg))


@dataclass
class ReconcileRow:
    rule_id: str
    check_item: str
    engine: str          # 引擎判定
    trial: str           # K 列试评期望
    agree: bool
    note: str = ""


@dataclass
class ReconcileReport:
    rows: list[ReconcileRow]

    @property
    def compared(self) -> list[ReconcileRow]:
        """引擎已实现 且 K 列有明确标签 的可比条目。"""
        return [r for r in self.rows if r.engine != Verdict.PENDING.value and r.trial]

    @property
    def agreement_rate(self) -> float:
        c = self.compared
        return sum(1 for r in c if r.agree) / len(c) if c else 0.0

    def summary(self) -> str:
        c = self.compared
        agree = sum(1 for r in c if r.agree)
        lines = [
            f"试评对账（引擎 vs K 列试评）",
            f"  可比条目: {len(c)}  一致: {agree}  一致率: {self.agreement_rate:.0%}",
            f"  (引擎已实现 {sum(1 for r in self.rows if r.engine != '未实现')} / "
            f"总 A 类 {len(self.rows)})",
        ]
        disagree = [r for r in c if not r.agree]
        if disagree:
            lines.append("  分歧项:")
            for r in disagree:
                lines.append(f"    规则{r.rule_id} {r.check_item}: 引擎={r.engine} / 试评={r.trial} {r.note}")
        return "\n".join(lines)


def reconcile_with_trial(doc: ProposalDocument,
                         registry: RuleRegistry | None = None) -> ReconcileReport:
    """运行引擎并与注册表里的 K 列试评结果逐条对账。"""
    reg = registry or load_registry()
    results = {rr.rule_id: rr for rr in run_rules(doc, reg)}
    rows: list[ReconcileRow] = []
    for r in reg.by_class("A"):
        rr = results.get(r.rule_id)
        expected = Verdict.from_trial_tag(r.trial_result)
        eng_v = rr.verdict.value if rr else Verdict.PENDING.value
        exp_v = expected.value if expected else ""
        agree = bool(expected) and rr is not None and rr.verdict == expected
        rows.append(ReconcileRow(
            rule_id=r.rule_id, check_item=r.check_item,
            engine=eng_v, trial=exp_v, agree=agree,
            note=(rr.evidence[:40] if rr else ""),
        ))
    return ReconcileReport(rows=rows)
