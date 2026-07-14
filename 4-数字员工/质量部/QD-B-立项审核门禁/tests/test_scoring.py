"""评分层测试 —— 锁定收口-1 权威扣分模型（扣分权重标准_82条规则.xlsx）。

对照「评分计算示例」页的各模块扣分公式（注：该示例页模块一结果 13.44 系其自身
算术笔误，正确应为 14.04；本测试以其逐模块公式字符串为准，均可复现）。
"""
import pytest

from qd_b_gate.models import RuleResult, Verdict
from qd_b_gate.rules.registry import load_registry
from qd_b_gate.scoring import score


@pytest.fixture(scope="module")
def reg():
    return load_registry()


def _results(reg, overrides: dict[str, Verdict]):
    """构造全 PASS 的结果，overrides 指定某些 rule_id 的判定。"""
    return [RuleResult(rule_id=r.rule_id, check_item=r.check_item,
                       verdict=overrides.get(r.rule_id, Verdict.PASS), impl_class=r.impl_class)
            for r in reg.rules]


def test_all_pass_is_100_qualified(reg):
    res = score(_results(reg, {}), reg)
    assert res.total_score == 100.0
    assert res.tier == "合格"
    assert not res.veto


def test_blocking_fail_triggers_veto(reg):
    """任一阻断规则不合格 → 一票否决 → 不合格（收口-1 权威）。"""
    res = score(_results(reg, {"1": Verdict.FAIL}), reg)   # 规则1 项目名称 阻断
    assert res.veto and res.veto_rules == ["1"]
    assert res.tier == "不合格"


def test_important_only_deducts_not_veto(reg):
    """重要规则不合格只扣分，不触发一票否决（区别于旧 MVP 默认）。"""
    res = score(_results(reg, {"25": Verdict.FAIL}), reg)  # 规则25 项目目标 重要(模块四)
    assert not res.veto
    # 20260710 权威：模块四 26/27 由阻断→重要，模块四全为重要，权重和 5×0.5=2.5；
    # 8 - 8×0.5/2.5 = 8 - 1.6 = 6.4
    assert abs(res.module_scores["四"].score - 6.4) < 0.01
    assert res.tier == "合格"        # 仅扣 1.6，总分仍 ≥80


def test_module_deduction_matches_authoritative(reg):
    """逐模块扣分复现示例页公式：模块六 一条重要违规 → 8 − 8×0.5/4.5 = 7.11。"""
    res6 = score(_results(reg, {"35": Verdict.FAIL}), reg)   # 规则35 风险识别 重要(模块六)
    assert abs(res6.module_scores["六"].score - (8 - 8 * 0.5 / 4.5)) < 0.01


def test_severity_override_rule34_is_tip(reg):
    """收口-1 权威覆盖：规则34 由「重要」改「提示」（系数 0.1）。"""
    r34 = reg.get(34)
    assert r34.severity == "提示"
    assert abs(r34.coefficient - 0.1) < 1e-9


def test_provisional_when_pending(reg):
    """含未实现（PENDING）A 类规则时，分数标暂定。"""
    results = _results(reg, {})
    results[0].verdict = Verdict.PENDING           # 制造一个 A 类 PENDING
    res = score(results, reg)
    assert res.provisional
    assert res.pending >= 1
