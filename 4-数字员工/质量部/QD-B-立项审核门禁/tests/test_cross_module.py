"""C01–C10 跨模块校验单测（变更包 qd-b-cross-module-check，档一＋档二）。

合成 ProposalDocument 覆盖判定分档；三份真实样本的端到端断言见
test_golden_product_class.py / test_golden_huafeng.py。
"""
import pytest

from qd_b_gate.models import (
    ExtractStatus,
    FieldValue,
    ProposalDocument,
    RuleResult,
    Verdict,
)
from qd_b_gate.rules.cross_module import (
    CROSS_CHECKS,
    build_cross_module_items,
    check_meta,
    implemented_ids,
    summarize,
)


def _doc(*, budget_hours=None, personnel_total=None, stages=None,
         cost_e=None, income_basis=None, start=None, end=None) -> ProposalDocument:
    doc = ProposalDocument(template_version="A2.1", project_type="产品类")
    for name, value in (("预算总工时", budget_hours), ("开始日期", start), ("结束日期", end)):
        key = f"一、项目信息/{name}"
        if value is None:
            doc.fields[key] = FieldValue(key=key, status=ExtractStatus.MISSING)
        else:
            doc.fields[key] = FieldValue(key=key, value=value, status=ExtractStatus.EXTRACTED)
    if personnel_total is not None:
        doc.tables["人员安排合计"] = [{"合计人月": personnel_total}]
    if stages is not None:
        doc.tables["预算表"] = stages
    if cost_e is not None:
        doc.tables["成本效益"] = [{"is_total": True, "成本E": cost_e, "收入D": cost_e}]
    if income_basis is not None:
        doc.tables["收入依据合计"] = [{"合计": income_basis}]
    return doc


def _stage(name, manmonth=None, subtotal=None, income=None, start=None, end=None):
    return {"阶段": name, "is_total": False, "人月": manmonth, "小计⑩": subtotal,
            "收入⑪": income, "开始": start, "结束": end}


def _by_id(items):
    return {i.rule_id: i for i in items}


# ---- 结构 ----

def test_all_ten_checks_present_in_fixed_order():
    items = build_cross_module_items(_doc())
    assert [i.rule_id for i in items] == [f"C{n:02d}" for n in range(1, 11)]
    assert all(i.impl_class == "Cross" for i in items)


def test_implemented_ids_excludes_the_three_blocked_checks():
    assert implemented_ids() == {"C01", "C02", "C03", "C04", "C08", "C09", "C10"}


def test_check_meta_carries_section_three_原文():
    meta = check_meta("C08")
    assert meta is not None
    assert "预算总工时" in meta.rule_text and meta.deviation == "偏差 > 10% → 警告"
    assert check_meta("C99") is None


# ---- C01 / C08 数值偏差类 ----

def test_c01_c08_pass_when_consistent():
    doc = _doc(budget_hours="50人月", personnel_total=50.0,
               stages=[_stage("立项", 20.0), _stage("结项", 30.0)])
    items = _by_id(build_cross_module_items(doc))
    assert items["C01"].verdict == Verdict.PASS
    assert items["C08"].verdict == Verdict.PASS
    assert "50" in items["C01"].evidence


def test_c01_warns_beyond_ten_percent_and_passes_within():
    """§三 判据是 10% 容差——9% 通过、20% 警告（与 82 条表的 0.05 人月精确容差是两套口径）。"""
    within = _by_id(build_cross_module_items(
        _doc(personnel_total=100.0, stages=[_stage("S1", 91.0)])))
    assert within["C01"].verdict == Verdict.PASS

    beyond = _by_id(build_cross_module_items(
        _doc(personnel_total=100.0, stages=[_stage("S1", 80.0)])))
    assert beyond["C01"].verdict == Verdict.WARN
    assert beyond["C01"].severity_level == "警告"
    assert "20.0%" in beyond["C01"].evidence


def test_numeric_missing_side_is_pending_not_zero():
    """任一侧缺数 → PENDING 并写明缺哪一侧；**不得**把缺失侧当 0 从而报"偏差 100%"。"""
    items = _by_id(build_cross_module_items(
        _doc(personnel_total=50.0)))  # 无预算表 → 右侧缺数
    assert items["C01"].verdict == Verdict.PENDING
    assert "模块九各阶段人月之和" in items["C01"].evidence
    assert "100" not in items["C01"].evidence


def test_stage_sum_excludes_total_row():
    """§三 比的是"各阶段之和"，合计行不得重复计入（否则恒定翻倍）。"""
    doc = _doc(personnel_total=50.0, stages=[
        _stage("S1", 20.0), _stage("S2", 30.0),
        {"阶段": "合计", "is_total": True, "人月": 50.0},
    ])
    assert _by_id(build_cross_module_items(doc))["C01"].verdict == Verdict.PASS


# ---- C02 / C03 ----

def test_c02_converts_yuan_scale_before_comparing():
    """成本效益表以「元」计价时（收入依据表为万元锚点），须换算后再比对，否则恒报巨大偏差。"""
    doc = _doc(cost_e=2_532_000.0, income_basis=253.2,
               stages=[_stage("S1", subtotal=253.2)])
    assert _by_id(build_cross_module_items(doc))["C02"].verdict == Verdict.PASS


def test_c02_warns_on_real_bangqi_shaped_gap():
    """邦奇形态：成本 E 131.96 万 vs 小计⑩和 85.298 万（差 46.662 万）→ 警告。"""
    doc = _doc(cost_e=131.96, income_basis=131.96,
               stages=[_stage("S1", subtotal=85.298)])
    item = _by_id(build_cross_module_items(doc))["C02"]
    assert item.verdict == Verdict.WARN
    assert "46.662" in item.evidence


def test_c03_compares_income_basis_total_against_stage_income():
    doc = _doc(income_basis=803.0, stages=[_stage("S1", income=400.0), _stage("S2", income=403.0)])
    assert _by_id(build_cross_module_items(doc))["C03"].verdict == Verdict.PASS


# ---- C04 时间一致性 ----

def test_c04_warns_on_start_date_mismatch_but_never_blocks():
    """EQ17 形态：起始差 3 天 → 警告（"止"半边的阻断责任在规则 66，本段不重复否决）。"""
    doc = _doc(start="2026-06-01", end="2027-11-30",
               stages=[_stage("立项评审", start="2026-05-29", end="2027-01-01"),
                       _stage("结项评审", start="2027-01-02", end="2027-11-30")])
    item = _by_id(build_cross_module_items(doc))["C04"]
    assert item.verdict == Verdict.WARN
    assert item.severity_level == "警告"
    assert "2026-05-29" in item.evidence


def test_c04_reports_each_half_independently_when_one_half_lacks_data():
    """华丰形态：起一致、止因项目结束日期未填无从比对——已核的那半不得被说成没核。"""
    doc = _doc(start="2026-06-15", end=None,
               stages=[_stage("立项评审", start="2026-06-15"), _stage("结项评审", end=None)])
    item = _by_id(build_cross_module_items(doc))["C04"]
    assert item.verdict == Verdict.PENDING
    assert "一致" in item.evidence          # 起半边的结论仍然给出
    assert "缺数" in item.evidence          # 止半边如实标注


def test_c04_passes_when_both_halves_match():
    doc = _doc(start="2026-01-26", end="2026-11-30",
               stages=[_stage("立项评审", start="2026-01-26"), _stage("结项评审", end="2026-11-30")])
    assert _by_id(build_cross_module_items(doc))["C04"].verdict == Verdict.PASS


# ---- C09 / C10 复用 ----

def test_c09_c10_reuse_rule_59_60_results_without_recomputing():
    results = [
        RuleResult(rule_id="59", check_item="项目本身毛利率", verdict=Verdict.PASS,
                   evidence="0.68 (验证: F/D=0.68)", impl_class="A"),
        RuleResult(rule_id="60", check_item="全生命周期毛利率", verdict=Verdict.NA,
                   evidence="无量产数据", impl_class="A"),
    ]
    items = _by_id(build_cross_module_items(_doc(), results))
    assert items["C09"].verdict == Verdict.PASS
    assert "复用规则59判定" in items["C09"].evidence and "F/D=0.68" in items["C09"].evidence
    assert items["C10"].verdict == Verdict.NA


def test_c09_pending_when_source_rule_absent_not_silently_skipped():
    item = _by_id(build_cross_module_items(_doc(), []))["C09"]
    assert item.verdict == Verdict.PENDING
    assert "规则59" in item.evidence


# ---- 等价规则并列标注（Q1 冲突可见） ----

def test_equivalent_rule_verdicts_are_shown_alongside():
    """82 条表（精确相等）与 §三（10% 容差）可给出不同结论——两者须同时可见，不静默择一。"""
    results = [RuleResult(rule_id="14", check_item="人月一致", verdict=Verdict.FAIL,
                          severity_level="错误", evidence="不一致", impl_class="A"),
               RuleResult(rule_id="68", check_item="节点表人月", verdict=Verdict.FAIL,
                          severity_level="错误", evidence="不一致", impl_class="A")]
    doc = _doc(personnel_total=100.0, stages=[_stage("S1", 97.0)])  # 3% → §三 判通过
    item = _by_id(build_cross_module_items(doc, results))["C01"]
    assert item.verdict == Verdict.PASS
    assert "规则14=不合格" in item.evidence and "规则68=不合格" in item.evidence


# ---- 未实现三条 ----

@pytest.mark.parametrize("check_id, keyword", [
    ("C05", "所属里程碑"), ("C06", "ASIL"), ("C07", "信息安全"),
])
def test_blocked_checks_state_a_concrete_reason_not_just_扩容期(check_id, keyword):
    item = _by_id(build_cross_module_items(_doc()))[check_id]
    assert item.verdict == Verdict.PENDING
    assert keyword in item.evidence
    assert "扩容期" not in item.evidence      # 笼统措辞正是本变更包要消灭的东西
    assert len(item.evidence) > 40            # 必须写清楚卡在哪里


def test_blocked_checks_never_guess_a_verdict():
    """口径未定前不得冒判——三条不得出现 PASS/FAIL/WARN。"""
    items = _by_id(build_cross_module_items(_doc()))
    for cid in ("C05", "C06", "C07"):
        assert items[cid].verdict == Verdict.PENDING


# ---- 抬头摘要 ----

def test_summarize_states_progress_and_that_it_does_not_affect_score():
    text = summarize(build_cross_module_items(_doc()))
    assert "C01–C10 共 10 条" in text
    assert "不计入总分" in text
    assert "暂未实现 3 条" in text


def test_summarize_separates_未实现_from_已实现但缺数():
    """空文档：7 条逻辑已实现但全部缺数、3 条口径待定——两者不得混为"未实现"。

    否则 C04 这种"逻辑已实现、只是这份文件没填结束日期"的条目会被计进"未实现"，
    正是本变更包要消灭的"把已核的说成没核"，只是尺度更小。
    """
    text = summarize(build_cross_module_items(_doc()))
    assert "判定逻辑已实现 7 条" in text
    assert "7 条因本份文件缺数未能比对" in text
    assert "暂未实现 3 条" in text


def test_cross_checks_metadata_covers_ten_and_records_equivalence():
    assert len(CROSS_CHECKS) == 10
    eq = {c.check_id: c.equivalent for c in CROSS_CHECKS}
    assert eq["C09"] == "59" and eq["C10"] == "60" and eq["C01"] == "14+68"
    assert eq["C02"] == "" and eq["C03"] == ""   # 真新增，无既有等价规则
