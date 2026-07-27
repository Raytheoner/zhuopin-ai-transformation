"""评审报告 · 逐项打分明细（陈忱灰度反馈 #116 共享底座）。

网页报告（①②结果页重排）与 Excel 导出（③评分表下载）都需要"每条规则的标准分/
实得分/扣分"这份逐项拆解——两处若各写一套换算，未来判据/权重表调整时容易走漂，
故把它抽成本模块唯一实现，两个呈现层只做渲染。

**只做展示层换算，不改判据**：标准分沿用 scoring.py 已在用的公式
`模块基础分 × 规则系数 / 模块权重系数和`（与 scoring.py::score() 内部 `ded` 计算
逐行一致），扣分/实得分照此反推展示，不引入陈忱 v5.0 报告的逐项独立权重
（评分口径裁定见场景 CLAUDE.md 2026-07-14："QD-B 用 82 条权重表加权，不复现
v5.0 每项标准分"）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import ProposalDocument, RuleResult, Verdict
from .report import GateReport
from .rules.registry import RuleRegistry, load_registry
from .scoring import ModuleScore

# 状态展示标签（如实标注——转人工/未实现绝不伪装成"通过"，见红线）
STATUS_LABELS: dict[Verdict, str] = {
    Verdict.PASS: "通过",
    Verdict.NA: "不适用",
    Verdict.WARN: "待改进",
    Verdict.FAIL: "不合格",
    Verdict.MANUAL: "转人工",
    Verdict.PENDING: "未实现",
}

# 违规判定（计入扣分）——须与 scoring.py::_VIOLATION 保持一致
_VIOLATION = {Verdict.FAIL, Verdict.WARN}


@dataclass
class ScoredItem:
    """一条规则的完整展示行（网页明细表 / Excel 明细&扣分表共用）。"""
    idx: int
    rule_id: str
    module_key: str
    section: str
    check_item: str
    pass_condition: str
    verdict: Verdict
    status_label: str
    coefficient: float
    std_score: float
    actual_score: float
    deduction: float
    evidence: str
    suggestion: str

    @property
    def is_problem(self) -> bool:
        """"仅看问题项"筛选口径：不合格/待改进/转人工/未实现 均算需要关注，仅"通过""不适用"算无需关注。"""
        return self.verdict not in (Verdict.PASS, Verdict.NA)

    @property
    def detail_text(self) -> str:
        text = self.evidence or ""
        if self.suggestion:
            text = f"{text}｜建议：{self.suggestion}" if text else f"建议：{self.suggestion}"
        return text or "—"


@dataclass
class ModuleRateRow:
    module_key: str
    section: str
    base: float
    score: float
    deduction: float

    @property
    def rate_pct(self) -> float:
        return round(self.score / self.base * 100, 1) if self.base else 0.0

    @property
    def all_pass(self) -> bool:
        return self.deduction <= 0


def build_scored_items(report: GateReport, registry: RuleRegistry | None = None) -> list[ScoredItem]:
    """按注册表原始顺序（=模块顺序，一…十三）产出全部规则的逐项打分行。"""
    reg = registry or load_registry()
    base_scores: dict[str, float] = reg.scoring.get("module_base_scores", {})
    weight_sums: dict[str, float] = reg.scoring.get("module_weight_sums", {})
    by_id: dict[str, RuleResult] = {r.rule_id: r for r in report.all_results}

    items: list[ScoredItem] = []
    for i, rule in enumerate(reg.rules, start=1):
        r = by_id.get(rule.rule_id)
        verdict = r.verdict if r else Verdict.PENDING
        evidence = r.evidence if r else ""
        suggestion = r.suggestion if r else ""

        ws = weight_sums.get(rule.module_key, 0.0)
        base = base_scores.get(rule.module_key, 0.0)
        std = round(base * rule.coefficient / ws, 2) if ws else 0.0
        violated = verdict in _VIOLATION
        deduction = std if violated else 0.0
        actual = round(std - deduction, 2)

        items.append(ScoredItem(
            idx=i, rule_id=rule.rule_id, module_key=rule.module_key, section=rule.section,
            check_item=rule.check_item, pass_condition=rule.pass_condition,
            verdict=verdict, status_label=STATUS_LABELS.get(verdict, verdict.value),
            coefficient=rule.coefficient, std_score=std, actual_score=actual,
            deduction=deduction, evidence=evidence, suggestion=suggestion,
        ))
    return items


def module_order(registry: RuleRegistry | None = None) -> list[tuple[str, str]]:
    """模块 (module_key, section) 顺序表——按注册表首次出现顺序（已天然是一…十三）。"""
    reg = registry or load_registry()
    seen: dict[str, str] = {}
    for rule in reg.rules:
        seen.setdefault(rule.module_key, rule.section)
    return list(seen.items())


_EIGHT_COMBINED_SECTION = "八、项目全生命周期的成本效益分析（含收益分析说明）"


def build_module_rates(report: GateReport, registry: RuleRegistry | None = None) -> list[ModuleRateRow]:
    """13 模块得分率一览（②段）。

    注册表把"八"拆成两个独立计分池（八（一）成本效益表/八（二）收益分析说明，各有
    自己的 base/weight_sum），这是 scoring.py 判据的既有设计，本函数不改；但陈忱
    反馈原文按"十三个评审模块"（一…十三，八为其一）展示得分率，故此处仅在**展示
    汇总层**把八（一）（二）的 base/score/deduction 相加合并成一行，凑齐 13 行——
    纯展示合并，不影响 82 条规则各自的判定与扣分（评审明细/扣分明细两个 sheet 仍
    按八（一）/八（二）两个独立小节展示，与规则实际归属一致）。
    """
    reg = registry or load_registry()
    ms_map: dict[str, ModuleScore] = report.score_result.module_scores
    rows: list[ModuleRateRow] = []
    combined_eight: ModuleRateRow | None = None
    for mk, section in module_order(reg):
        ms = ms_map.get(mk)
        if ms is None:
            continue
        if mk.startswith("八"):
            if combined_eight is None:
                combined_eight = ModuleRateRow(module_key="八", section=_EIGHT_COMBINED_SECTION,
                                               base=0.0, score=0.0, deduction=0.0)
                rows.append(combined_eight)
            combined_eight.base += ms.base
            combined_eight.score += ms.score
            combined_eight.deduction += ms.deduction
            continue
        rows.append(ModuleRateRow(module_key=mk, section=section, base=ms.base,
                                  score=ms.score, deduction=ms.deduction))
    return rows


def deduction_items(items: list[ScoredItem]) -> list[ScoredItem]:
    """扣分明细（③段）：仅"不合格/待改进"两态，按扣分从高到低排序（便于快速定位问题）。"""
    rows = [it for it in items if it.verdict in _VIOLATION]
    return sorted(rows, key=lambda it: (-it.deduction, it.module_key, int(it.rule_id) if it.rule_id.isdigit() else 0))


def deduction_subtotals(items: list[ScoredItem]) -> tuple[float, float]:
    """(不合格扣分合计, 待改进扣分合计)。"""
    fail = round(sum(it.deduction for it in items if it.verdict == Verdict.FAIL), 2)
    warn = round(sum(it.deduction for it in items if it.verdict == Verdict.WARN), 2)
    return fail, warn


_BASIC_INFO_FIELDS = [
    ("项目名称", "一、项目信息/项目名称"),
    ("客户名称", "一、项目信息/客户名称"),
    ("项目经理", "一、项目信息/项目经理"),
    ("项目类型", "一、项目信息/项目类型"),
    ("所属事业部", "一、项目信息/项目所属事业部"),
]


def build_basic_info(doc: ProposalDocument) -> dict[str, str]:
    """项目基本信息（项目编号字段解析器未实现抽取，如实标注"—"，不伪造）。"""
    out: dict[str, str] = {}
    for label, key in _BASIC_INFO_FIELDS:
        fv = doc.get(key)
        out[label] = str(fv.value) if fv.is_present else "—"
    out["项目编号"] = "—"
    return out


def _fmt_num(value) -> str:
    if value is None or value == "":
        return "—"
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_ratio_as_percent(value) -> str:
    """毛利率是比率字段，约定按百分比展示；若源值本身已是文本（如 "36.78%"），原样透传不重复换算。"""
    if value is None or value == "":
        return "—"
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return str(value)


def build_financial_summary(doc: ProposalDocument) -> dict[str, str]:
    """财务摘要（项目收入/成本/毛利率/收益指标）——best-effort 从已解析表格/字段取值，
    取不到如实显示"—"，不臆造（同解析探针"真为空 vs 未命中"红线）。"""
    cb_rows = doc.table("成本效益")
    total_row = next((row for row in cb_rows if row.get("is_total")), None)
    income = total_row.get("收入J") if total_row else None
    cost = total_row.get("成本K") if total_row else None

    margin_fv = doc.get("八、（二）收益分析说明/全生命周期毛利率")
    margin = margin_fv.value if margin_fv.is_present else None

    benefit_key = "收益指标_产品类" if doc.project_type == "产品类" else "收益指标_技术服务类"
    benefit_fv = doc.get(f"八、（二）收益分析说明/{benefit_key}")
    benefit = benefit_fv.value if benefit_fv.is_present else None

    return {
        "项目收入": _fmt_num(income),
        "项目成本": _fmt_num(cost),
        "毛利率": _fmt_ratio_as_percent(margin),
        "收益指标": _fmt_num(benefit) if benefit not in (None, "") else "—",
    }
