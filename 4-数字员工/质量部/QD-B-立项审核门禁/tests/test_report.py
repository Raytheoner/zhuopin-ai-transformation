"""审核报告聚合测试（任务 6.1/6.3/6.7，M5 判定聚合 + M7 报告聚合核心交付物）。

合成 RuleResult 覆盖各判定分档的报告归类；真实文档端到端见
test_golden_product_class.py 里 EQ17/邦奇 的 build_report 集成断言。
"""
from qd_b_gate.models import ProposalDocument, RuleResult, Verdict
from qd_b_gate.report import build_report
from qd_b_gate.scoring import ScoreResult


def _score(veto=False, veto_rules=None, tier="合格", total=100.0, provisional=False, pending=0):
    return ScoreResult(veto=veto, veto_rules=veto_rules or [], total_score=total, tier=tier,
                       module_scores={}, provisional=provisional, evaluated=82 - pending,
                       pending=pending)


def _doc():
    return ProposalDocument(template_version="A2.1", project_type="产品类")


def test_blocking_items_only_contains_blocking_fails():
    results = [
        RuleResult(rule_id="1", check_item="必填", verdict=Verdict.PASS, impl_class="A"),
        RuleResult(rule_id="80", check_item="项目经理签字", verdict=Verdict.FAIL,
                   severity_level="错误", evidence="未签字", impl_class="C"),
        RuleResult(rule_id="42", check_item="应对措施", verdict=Verdict.WARN,
                   severity_level="警告", evidence="部分未填", impl_class="C"),
    ]
    rep = build_report(_doc(), results=results, score_result=_score(veto=True, veto_rules=["80"], tier="不合格"))
    assert [r.rule_id for r in rep.blocking_items] == ["80"]
    assert [r.rule_id for r in rep.warning_items] == ["42"]


def test_manual_items_are_the_transfer_to_human_todo_list():
    results = [
        RuleResult(rule_id="20", check_item="产品是什么", verdict=Verdict.MANUAL,
                   evidence="占位待人工复核", impl_class="B"),
        RuleResult(rule_id="82", check_item="立项决议", verdict=Verdict.NA,
                   evidence="申请阶段不判", impl_class="C"),
        RuleResult(rule_id="1", check_item="必填", verdict=Verdict.PASS, impl_class="A"),
    ]
    rep = build_report(_doc(), results=results, score_result=_score())
    # NA（立项决议）不算"待办"——申请阶段本就不判，不该占用转人工清单
    assert [r.rule_id for r in rep.manual_todo_items] == ["20"]


def test_cross_module_is_reported_item_by_item_not_one_blanket_sentence():
    """④段须逐条呈现 C01–C10。

    此前这里断言的是"整段一句话说未实现"——而实测其中 4 条一直由规则 14/68/59/60 在核，
    那句话把已核的说成没核（队列 #340）。故契约改为：十条都在、各带实现状态。
    """
    rep = build_report(_doc(), results=[], score_result=_score())
    assert [i.rule_id for i in rep.cross_module_items] == [f"C{n:02d}" for n in range(1, 11)]
    assert "C01–C10 共 10 条" in rep.cross_module_note
    assert "尚未实现" not in rep.cross_module_note


def test_cross_module_section_never_says_the_whole_range_is_unimplemented():
    """回归锁：只要有任何一条实际在核，报告就不得出现"C01–C10 尚未实现"式整段否定。"""
    rep = build_report(_doc(), results=[], score_result=_score())
    text = rep.to_text()
    assert "C01–C10 跨模块校验尚未实现" not in text
    for cid in ("C01", "C05", "C10"):
        assert cid in text


def test_verdict_follows_score_result_tier():
    rep = build_report(_doc(), results=[], score_result=_score(tier="有条件合格", total=70.0))
    assert rep.verdict == "有条件合格"


def test_to_text_contains_six_sections_and_disclaimer():
    results = [
        RuleResult(rule_id="80", check_item="项目经理签字", verdict=Verdict.FAIL,
                   severity_level="错误", evidence="未签字", suggestion="请签字", impl_class="C"),
    ]
    rep = build_report(_doc(), results=results,
                       score_result=_score(veto=True, veto_rules=["80"], tier="不合格"),
                       sample_id="test001")
    text = rep.to_text()
    assert "AI 预审建议" in text
    assert "决策在评审委员会" in text
    for marker in ("① 总判定", "② 阻断项清单", "③ 警告/提示清单",
                   "④ 跨模块校验结果", "⑤ 转人工待办项", "⑥ 审计元数据"):
        assert marker in text
    assert "规则80" in text and "请签字" in text
    assert "test001" in text


def test_to_text_notes_provisional_pending():
    rep = build_report(_doc(), results=[], score_result=_score(provisional=True, pending=5))
    assert "暂定" in rep.to_text()
