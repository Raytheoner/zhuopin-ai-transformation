"""评分层（收口-1 权威：扣分权重标准_82条规则.xlsx）—— 独立可插拔（design.md D7）。

算法：
  ① 一票否决：任一「阻断」规则不合格 → 直接判「不合格」（<60），不再计分。
  ② 否则模块扣分：单条扣分值 = 模块基础分 × 该规则系数 / 模块内系数之和；
     模块得分 = 基础分 − Σ违规扣分；总分 = 100 − Σ全部扣分。
  ③ 分档：≥80 合格 / 60~80 有条件合格 / <60 不合格。

与规则引擎解耦：输入 RuleResult 列表 + 注册表评分数据，输出 ScoreResult。
未实现（PENDING）规则默认「视为通过、不扣分」，但标记 provisional=True——
全量 A 类规则实现前，分数为暂定值。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import RuleResult, Verdict
from .rules.registry import RuleRegistry, load_registry

# 计入扣分的判定（违规）：不合格 / 待改进
_VIOLATION = {Verdict.FAIL, Verdict.WARN}


@dataclass
class ModuleScore:
    module_key: str
    base: float
    deduction: float
    score: float
    violations: list[str] = field(default_factory=list)


@dataclass
class ScoreResult:
    veto: bool                       # 是否触发一票否决
    veto_rules: list[str]            # 触发一票否决的规则ID
    total_score: float               # 最终得分（veto 时为 None 语义，用 0.0 占位并看 tier）
    tier: str                        # 合格 / 有条件合格 / 不合格
    module_scores: dict[str, ModuleScore]
    provisional: bool                # 是否含未实现规则（分数暂定）
    evaluated: int
    pending: int

    def summary(self) -> str:
        head = "❌ 一票否决" if self.veto else f"得分 {self.total_score:.2f}"
        lines = [f"立项评分：{self.tier}（{head}）"]
        if self.veto:
            lines.append(f"  触发一票否决（阻断级不合格）：规则 {self.veto_rules}")
        if self.provisional:
            lines.append(f"  ⚠ 暂定：{self.pending} 条 A 类规则未实现（视为通过），全量实现后复核")
        return "\n".join(lines)


def score(results: list[RuleResult], registry: RuleRegistry | None = None) -> ScoreResult:
    reg = registry or load_registry()
    sc = reg.scoring
    base_scores: dict[str, float] = sc.get("module_base_scores", {})
    weight_sums: dict[str, float] = sc.get("module_weight_sums", {})
    thr = sc.get("tier_thresholds", {"合格": 80, "有条件合格": 60})

    by_id = {r.rule_id: r for r in results}
    veto_rules = [r.rule_id for r in reg.rules
                  if r.blocking and by_id.get(r.rule_id)
                  and by_id[r.rule_id].verdict == Verdict.FAIL]

    # 模块扣分
    modules: dict[str, ModuleScore] = {}
    for mk, base in base_scores.items():
        modules[mk] = ModuleScore(module_key=mk, base=float(base), deduction=0.0,
                                  score=float(base))
    for rule in reg.rules:
        rr = by_id.get(rule.rule_id)
        if not rr or rr.verdict not in _VIOLATION:
            continue
        mk = rule.module_key
        ws = weight_sums.get(mk, 0.0)
        if mk not in modules or ws <= 0:
            continue
        ded = round(float(base_scores[mk]) * rule.coefficient / ws, 4)
        modules[mk].deduction = round(modules[mk].deduction + ded, 4)
        modules[mk].score = round(modules[mk].base - modules[mk].deduction, 4)
        modules[mk].violations.append(rule.rule_id)

    total = round(sum(m.score for m in modules.values()), 2)
    pending = sum(1 for r in results if r.impl_class == "A" and r.verdict == Verdict.PENDING)
    evaluated = sum(1 for r in results if r.impl_class == "A" and r.verdict != Verdict.PENDING)

    if veto_rules:
        tier = "不合格"
    elif total >= thr["合格"]:
        tier = "合格"
    elif total >= thr["有条件合格"]:
        tier = "有条件合格"
    else:
        tier = "不合格"

    return ScoreResult(
        veto=bool(veto_rules), veto_rules=veto_rules,
        total_score=total, tier=tier, module_scores=modules,
        provisional=pending > 0, evaluated=evaluated, pending=pending,
    )
