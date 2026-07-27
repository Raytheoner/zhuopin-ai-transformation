"""report_items.py 测试 —— 网页明细/Excel 导出共用的逐项打分展示口径。

红线校验重点：① 标准分公式须与 scoring.py::score() 的 ded 公式逐条一致（不得另起
一套权重）；② 转人工/未实现绝不能被伪装成"通过"；③ 模块得分率一览合并展示后
仍是 13 行（八的两个计分池只在展示层合并，判据不变）。
"""
import pytest

from qd_b_gate.models import ProposalDocument, RuleResult, Verdict
from qd_b_gate.report import build_report
from qd_b_gate.report_items import (
    STATUS_LABELS,
    ScoredItem,
    build_basic_info,
    build_financial_summary,
    build_module_rates,
    build_scored_items,
    deduction_items,
    deduction_subtotals,
)
from qd_b_gate.rules.registry import load_registry
from qd_b_gate.scoring import score


@pytest.fixture(scope="module")
def reg():
    return load_registry()


def _report(reg, overrides: dict[str, Verdict] | None = None):
    overrides = overrides or {}
    results = [RuleResult(rule_id=r.rule_id, check_item=r.check_item,
                          verdict=overrides.get(r.rule_id, Verdict.PASS), impl_class=r.impl_class)
               for r in reg.rules]
    sr = score(results, reg)
    return build_report(ProposalDocument(), results=results, score_result=sr,
                        registry=reg, rule_version=reg.rule_version)


def test_build_scored_items_covers_every_registry_rule_in_order(reg):
    report = _report(reg)
    items = build_scored_items(report, reg)
    assert [it.rule_id for it in items] == [r.rule_id for r in reg.rules]


def test_all_pass_items_have_zero_deduction(reg):
    items = build_scored_items(_report(reg), reg)
    assert all(it.deduction == 0 for it in items)
    assert all(it.actual_score == it.std_score for it in items)


def test_std_score_formula_matches_scoring_module(reg):
    """标准分＝模块基础分×规则系数/模块权重和 —— 必须与 scoring.py 的 ded 公式一致。"""
    items = build_scored_items(_report(reg), reg)
    base_scores = reg.scoring["module_base_scores"]
    weight_sums = reg.scoring["module_weight_sums"]
    for it in items:
        expected = round(base_scores[it.module_key] * it.coefficient / weight_sums[it.module_key], 2)
        assert abs(it.std_score - expected) < 1e-6


def test_violated_item_deduction_equals_std_score(reg):
    report = _report(reg, {"25": Verdict.FAIL})  # 规则25：模块四，重要（非阻断）
    it25 = next(i for i in build_scored_items(report, reg) if i.rule_id == "25")
    assert it25.status_label == "不合格"
    assert it25.deduction == it25.std_score
    assert it25.actual_score == 0.0


def test_status_labels_do_not_disguise_manual_or_pending():
    """转人工/未实现须如实标注，绝不伪装成"通过"（红线，见场景 CLAUDE.md §4）。"""
    assert STATUS_LABELS[Verdict.MANUAL] == "转人工"
    assert STATUS_LABELS[Verdict.PENDING] == "未实现"
    assert STATUS_LABELS[Verdict.PASS] == "通过"
    assert STATUS_LABELS[Verdict.FAIL] == "不合格"
    assert STATUS_LABELS[Verdict.WARN] == "待改进"
    assert STATUS_LABELS[Verdict.NA] == "不适用"


def test_manual_verdict_item_keeps_manual_label(reg):
    report = _report(reg, {"42": Verdict.MANUAL})
    it42 = next(i for i in build_scored_items(report, reg) if i.rule_id == "42")
    assert it42.status_label == "转人工"
    assert it42.verdict == Verdict.MANUAL


def test_module_rates_merge_module_eight_into_thirteen_rows(reg):
    rates = build_module_rates(_report(reg), reg)
    assert len(rates) == 13
    keys = [r.module_key for r in rates]
    assert "八（一）" not in keys and "八（二）" not in keys
    assert "八" in keys
    eight = next(r for r in rates if r.module_key == "八")
    base_scores = reg.scoring["module_base_scores"]
    assert abs(eight.base - (base_scores["八（一）"] + base_scores["八（二）"])) < 1e-6


def test_module_rates_all_pass_when_no_violation(reg):
    rates = build_module_rates(_report(reg), reg)
    assert all(r.all_pass for r in rates)
    assert all(r.rate_pct == 100.0 for r in rates)


def test_module_rates_flags_violated_module(reg):
    rates = build_module_rates(_report(reg, {"25": Verdict.FAIL}), reg)
    mod4 = next(r for r in rates if r.module_key == "四")
    assert not mod4.all_pass
    assert mod4.rate_pct < 100.0


def test_deduction_items_only_fail_and_warn_sorted_by_deduction_desc(reg):
    report = _report(reg, {"25": Verdict.FAIL, "21": Verdict.WARN})
    rows = deduction_items(build_scored_items(report, reg))
    assert {r.rule_id for r in rows} == {"25", "21"}
    assert rows[0].deduction >= rows[1].deduction


def test_deduction_subtotals_split_fail_vs_warn(reg):
    report = _report(reg, {"25": Verdict.FAIL, "21": Verdict.WARN})
    items = build_scored_items(report, reg)
    fail_ded, warn_ded = deduction_subtotals(items)
    it25 = next(i for i in items if i.rule_id == "25")
    it21 = next(i for i in items if i.rule_id == "21")
    assert abs(fail_ded - it25.deduction) < 1e-6
    assert abs(warn_ded - it21.deduction) < 1e-6


@pytest.mark.parametrize("verdict,expected", [
    (Verdict.PASS, False), (Verdict.NA, False),
    (Verdict.WARN, True), (Verdict.FAIL, True),
    (Verdict.MANUAL, True), (Verdict.PENDING, True),
])
def test_is_problem_property(verdict, expected):
    item = ScoredItem(idx=1, rule_id="1", module_key="一", section="一、项目信息",
                      check_item="x", pass_condition="x", verdict=verdict,
                      status_label=STATUS_LABELS[verdict], coefficient=1.0,
                      std_score=1.0, actual_score=1.0, deduction=0.0,
                      evidence="", suggestion="")
    assert item.is_problem is expected


def test_build_basic_info_missing_field_shows_dash_not_blank():
    info = build_basic_info(ProposalDocument())
    assert info["项目名称"] == "—"
    assert info["项目编号"] == "—"  # 解析器未实现抽取，如实标注，不伪造


def test_build_financial_summary_defaults_to_dash_when_absent():
    fin = build_financial_summary(ProposalDocument())
    assert fin["项目收入"] == "—"
    assert fin["毛利率"] == "—"
