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

_UNSET = object()   # `_doc(asil=...)` 的"未解析"哨兵，见 _doc docstring


def _doc(*, budget_hours=None, personnel_total=None, stages=None,
         cost_e=None, income_basis=None, start=None, end=None,
         asil=_UNSET, risks=None, objectives=None, regulations=None) -> ProposalDocument:
    """合成一份立项书。

    `asil` 三态：不传＝字段未解析（NOT_FOUND）／传 None＝锚点命中但空（MISSING，即"漏填"）／
    传字符串＝已填。**这三态在档三里判定各不相同**，用一个默认 None 表达不了，故用哨兵。
    """
    doc = ProposalDocument(template_version="A2.1", project_type="产品类")
    for name, value in (("预算总工时", budget_hours), ("开始日期", start), ("结束日期", end)):
        key = f"一、项目信息/{name}"
        if value is None:
            doc.fields[key] = FieldValue(key=key, status=ExtractStatus.MISSING)
        else:
            doc.fields[key] = FieldValue(key=key, value=value, status=ExtractStatus.EXTRACTED)
    if asil is not _UNSET:
        key = "一、项目信息/功能安全目标ASIL"
        doc.fields[key] = (FieldValue(key=key, status=ExtractStatus.MISSING) if asil is None
                           else FieldValue(key=key, value=asil, status=ExtractStatus.EXTRACTED))
    if personnel_total is not None:
        doc.tables["人员安排合计"] = [{"合计人月": personnel_total}]
    if stages is not None:
        doc.tables["预算表"] = stages
    if cost_e is not None:
        doc.tables["成本效益"] = [{"is_total": True, "成本E": cost_e, "收入D": cost_e}]
    if income_basis is not None:
        doc.tables["收入依据合计"] = [{"合计": income_basis}]
    if risks is not None:
        doc.tables["风险"] = [{"序号": i + 1, "行号": 50 + i, "所属里程碑": m}
                             for i, m in enumerate(risks)]
    if objectives is not None:
        doc.tables["项目目标"] = [{"目标类型": k, "详细指标": v, "交付物": ""}
                                for k, v in objectives.items()]
    if regulations is not None:
        doc.checkboxes["适用法规/体系"] = list(regulations)
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


# （原 test_implemented_ids_excludes_the_three_blocked_checks 已随档三落地退休，
#   等价断言见文件末 test_no_check_is_blocked_on_pending_criteria_anymore）


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


# ---- 档三 C05：陈忱 2026-08-21 Q1 的 10 条判例逐条锁死 ----

#: EQ17／邦奇的模块九阶段集（真实取值），C05 判例的右侧
_FULL_STAGES = ["立项评审", "G1质量阀（A样阀）/概念设计", "G2质量阀（B样阀）/基本功能",
                "G3质量阀（OTS阀）/详细功能", "G4质量阀（量产阀）/量产工艺", "结项评审"]
#: 华丰的模块九只填了两个阶段
_HUAFENG_STAGES = ["立项评审", "结项评审"]


def _c05_of(milestones, stages):
    doc = _doc(risks=milestones, stages=[_stage(s) for s in stages])
    return _by_id(build_cross_module_items(doc))["C05"]


@pytest.mark.parametrize("case_no, milestone, stages", [
    (1, "项目立项", _HUAFENG_STAGES),   # 华丰 r56
    (2, "项目立项", _HUAFENG_STAGES),   # 华丰 r57
    (3, "项目立项", _HUAFENG_STAGES),   # 华丰 r58
    (4, "立项", _FULL_STAGES),          # 邦奇 r53
    (5, "立项", _FULL_STAGES),          # 邦奇 r54
    (6, "立项", _FULL_STAGES),          # 邦奇 r55
])
def test_c05_cases_1_to_6_pass_as_chenchen_ticked(case_no, milestone, stages):
    """陈忱对判例 1–6 均判 ✅（拟改判定「通过」是对的）。

    1–3 靠映射表白名单（`项目立项` 与 `立项评审` 互不为子串，只能由表命中）；
    4–6 靠子串匹配（`立项` ⊂ `立项评审`）。
    """
    assert _c05_of([milestone], stages).verdict == Verdict.PASS


@pytest.mark.parametrize("case_no, milestone", [
    (7, "需求确认与资料交付"),
    (10, "认证与合规阶段"),
])
def test_c05_cases_7_and_10_are_errors_as_chenchen_ticked(case_no, milestone):
    """判例 7／10 陈忱判 ✅——拟改判定「错误」是对的，引擎须照判错误。"""
    item = _c05_of([milestone], _FULL_STAGES)
    assert item.verdict == Verdict.FAIL
    assert item.severity_level == "错误"


def test_c05_case_8_must_not_pass_via_string_similarity():
    """🔴 判例 8：陈忱判 ❌——`软硬件开发设计` **不得**因与「概念设计」共有「设计」二字而通过。

    这是他两条护栏里的第二条（"用里程碑-阶段映射表做白名单校验，不要只靠字符串相似度"）。
    引擎须判错误，**并把"相似度指向了谁"如实写进证据**——看见了但不予采信，
    与压根没看见是两回事，报告上必须能区分。
    """
    item = _c05_of(["软硬件开发设计"], _FULL_STAGES)
    assert item.verdict == Verdict.FAIL
    assert "概念设计" in item.evidence          # 相似度指向谁，如实写出
    assert "不予采信" in item.evidence          # 但不作为通过依据


def test_c05_case_9_pervasive_value_is_exempt_not_an_error():
    """🔴 判例 9：陈忱判 ❌——`全项目周期` **不得**判错误。

    它压根不是里程碑，是"贯穿全程"的意思；任何匹配口径对它都无效。这是他两条护栏里的
    第一条（豁免词表），目的正是"避免第 9 条这种合格项目被误伤"——EQ17 恰是评审判合格的那份。
    """
    item = _c05_of(["全项目周期"], _FULL_STAGES)
    assert item.verdict == Verdict.PASS
    assert "豁免" in item.evidence


def test_c05_eq17_full_row_set_matches_chenchen_ticks_exactly():
    """EQ17 四条风险合判：7/8/10 错误、9 豁免 ⇒ 整条错误，且逐条可追。"""
    item = _c05_of(["需求确认与资料交付", "软硬件开发设计", "全项目周期", "认证与合规阶段"],
                   _FULL_STAGES)
    assert item.verdict == Verdict.FAIL
    assert "豁免 1" in item.evidence and "对不上 3" in item.evidence


def test_c05_flags_the_draft_tables_as_awaiting_confirmation():
    """两份表是按 Q1 反推草拟的、他尚未确认——**每条 C05 结论都必须自带这句**。

    否则读报告的人会以为这是已签认口径（判据类永不默认生效，IATF 显式签认红线）。
    """
    assert "待陈忱确认" in _c05_of(["立项"], _FULL_STAGES).evidence


def test_c05_missing_milestone_is_an_error_naming_the_row():
    item = _c05_of([""], _FULL_STAGES)
    assert item.verdict == Verdict.FAIL and "漏填" in item.evidence


def test_c05_pending_when_no_stage_parsed_rather_than_blaming_the_filler():
    """模块九没解析出阶段时判 PENDING——不得反过来说风险填错了。"""
    assert _c05_of(["立项"], []).verdict == Verdict.PENDING


def test_c05_na_when_there_is_no_risk_row():
    doc = _doc(risks=[], stages=[_stage(s) for s in _FULL_STAGES])
    assert _by_id(build_cross_module_items(doc))["C05"].verdict == Verdict.NA


# ---- 档三 C06：ASIL ↔ 模块四功能安全目标（Q2 + Q3） ----

def _c06_of(asil, objectives):
    return _by_id(build_cross_module_items(_doc(asil=asil, objectives=objectives)))["C06"]


@pytest.mark.parametrize("written", ["/", "NA", "N/A", "无", "不涉及", "不适用"])
def test_c06_all_six_na_synonyms_make_the_check_not_applicable(written):
    """陈忱 Q2 封闭词表六种写法一律视同 NA——含此前不在集内、正在误判 EQ17 的「无」。"""
    item = _c06_of(written, {"功能安全目标（如有）": ""})
    assert item.verdict == Verdict.NA


def test_c06_empty_asil_is_missing_data_not_na():
    """🔴 Q2 后半句：空单元格判「漏填」，**不视同 NA**。

    视同 NA 会让整条校验被静默跳过；此处判转人工，并写明扣分归规则 12，不重复否决。
    """
    item = _c06_of(None, {"功能安全目标（如有）": ""})
    assert item.verdict == Verdict.MANUAL
    assert "漏填" in item.evidence and "规则 12" in item.evidence


def test_c06_unparsed_asil_field_is_manual_not_a_business_failure():
    item = _by_id(build_cross_module_items(_doc(objectives={"功能安全目标（如有）": ""})))["C06"]
    assert item.verdict == Verdict.MANUAL


def test_c06_passes_when_asil_graded_and_module4_has_real_content():
    """邦奇形态：ASIL=A ＋ 模块四有实质内容 → 通过。"""
    item = _c06_of("A", {"功能安全目标（如有）": "① 硬件设计需满足 ISO 26262 功能安全要求…"})
    assert item.verdict == Verdict.PASS


@pytest.mark.parametrize("filled", ["", "不涉及", "无", "不适用", "/"])
def test_c06_fails_when_module4_goal_is_blank_or_a_not_filled_synonym(filled):
    """🔴 Q3 选 (b)：模块四「视为没填」词表复用 Q2 那组。

    若按「非空即算有」实现，填一个「无」就能绕过——判据形同虚设。
    """
    item = _c06_of("B", {"功能安全目标（如有）": filled})
    assert item.verdict == Verdict.FAIL and item.severity_level == "错误"


def test_c06_manual_when_module4_not_parsed_at_all():
    """解析未命中 ≠ 业务未填（场景红线）——不得据此判错误。"""
    item = _c06_of("A", None)     # objectives=None ⇒ 模块四整张表都没解析出来
    assert item.verdict == Verdict.MANUAL and "未解析" in item.evidence


# ---- 档三 C07：ISO21434 ↔ 模块四信息安全目标（Q4） ----

_EQ17_REGS = [("无", False), ("ISO26262", False), ("ISO21434", True),
              ("IATF16949", True), ("CMMI4", True)]
#: 华丰实测：`N8` 整格缺失 ⇒ ISO21434 这个选项**根本不在表里**（不是"没勾"）
_HUAFENG_REGS = [("ISO26262", False), ("IATF16949", False), ("CMMI4", False)]


def _c07_of(regs, objectives):
    return _by_id(build_cross_module_items(
        _doc(regulations=regs, objectives=objectives)))["C07"]


def test_c07_passes_when_iso21434_checked_and_module4_has_content():
    item = _c07_of(_EQ17_REGS, {"信息安全目标（如有）": "① 完成 ISO/SAE 21434 网络安全功能开发…"})
    assert item.verdict == Verdict.PASS


def test_c07_fails_when_iso21434_checked_but_module4_goal_missing():
    item = _c07_of(_EQ17_REGS, {"信息安全目标（如有）": "不涉及"})
    assert item.verdict == Verdict.FAIL and item.severity_level == "错误"


def test_c07_not_applicable_when_iso21434_present_but_unchecked():
    regs = [("无", True), ("ISO21434", False)]
    assert _c07_of(regs, {"信息安全目标（如有）": ""}).verdict == Verdict.NA


def test_c07_huafeng_option_absent_is_manual_not_silently_not_applicable():
    """🔴 Q4 选 (b) 的全部要害：**「读不出来」不得被压成「不适用」**。

    华丰的 ISO21434 选项因 `N8` 整格缺失而从选项表里消失。按字面实现会静默判不适用跳过，
    返回值完全正常、结论却是反的（「工具静默回退」同族）。此处必须转人工，
    且证据要说清楚是"表里没有这一项"而不是"没勾"。
    """
    item = _c07_of(_HUAFENG_REGS, {"信息安全目标（如有）": ""})
    assert item.verdict == Verdict.MANUAL
    assert "没有 ISO21434 这一项" in item.evidence
    assert "不是「未勾选」" in item.evidence


def test_c07_manual_when_regulation_row_not_parsed():
    assert _c07_of(None, {"信息安全目标（如有）": ""}).verdict == Verdict.MANUAL


# ---- 档三落地后：不再有"口径未定"条目 ----

def test_no_check_is_blocked_on_pending_criteria_anymore():
    """档三三条已落地 ⇒ `implemented_ids()` 覆盖全部 10 条，不再有"未实现"分类。"""
    assert implemented_ids() == {f"C{n:02d}" for n in range(1, 11)}


def test_tier3_checks_never_leak_into_the_scored_result_set():
    """C05/C06/C07 与档一档二同样只进 `cross_module_items`——本函数不返回 82 条那一份。

    这是档三与 2026-08-18 归档件预期的显式差异：EQ17 的 C05 实测判错误，接进扣分
    会当场把评审判合格的样本打成不合格。
    """
    items = build_cross_module_items(
        _doc(asil="A", risks=["不存在的里程碑"], stages=[_stage("立项评审")]))
    assert all(i.impl_class == "Cross" for i in items)
    assert len(items) == 10


# ---- 抬头摘要 ----

def test_summarize_states_progress_and_that_it_does_not_affect_score():
    text = summarize(build_cross_module_items(_doc()))
    assert "C01–C10 共 10 条" in text
    assert "不计入总分" in text
    assert "判定逻辑已实现 10 条" in text
    assert "暂未实现" not in text          # 档三落地后不应再有这一分句


def test_summarize_no_longer_claims_anything_is_unimplemented():
    """档三落地 ⇒ 10 条全部有判定逻辑；空文档下它们是"缺数未能比对"，不是"未实现"。

    这两者的分开正是本能力的立身之本（把已核的说成没核，是 #340 的原始缺陷）。
    """
    text = summarize(build_cross_module_items(_doc()))
    assert "判定逻辑已实现 10 条" in text
    assert "因本份文件缺数未能比对" in text


def test_summarize_counts_manual_verdicts():
    """C06/C07 的"读不出来→转人工"是常态结论，漏计会让抬头计数与下表条数对不上。"""
    doc = _doc(asil=None, regulations=_HUAFENG_REGS, objectives={"功能安全目标（如有）": ""})
    text = summarize(build_cross_module_items(doc))
    assert "转人工 2 条" in text


def test_cross_checks_metadata_covers_ten_and_records_equivalence():
    assert len(CROSS_CHECKS) == 10
    eq = {c.check_id: c.equivalent for c in CROSS_CHECKS}
    assert eq["C09"] == "59" and eq["C10"] == "60" and eq["C01"] == "14+68"
    assert eq["C02"] == "" and eq["C03"] == ""   # 真新增，无既有等价规则


# ---- 状态标签：未实现 vs 已实现但缺数 ----

def test_status_label_marks_pending_as_待人工核_now_that_nothing_is_unimplemented():
    """通用 STATUS_LABELS 把 PENDING 一律显示"未实现"——本段须区分两种来历。

    档三落地后已无"逻辑没写"的条目，故所有 PENDING 都是"这份文件缺数比不了"，
    一律标「待人工核」；把它们标成「未实现」就又回到了"把已核的说成没核"。
    """
    from qd_b_gate.rules.cross_module import status_label

    items = _by_id(build_cross_module_items(_doc()))          # 空文档：全部缺数
    for cid in ("C01", "C04", "C05"):
        assert status_label(items[cid]) == "待人工核"

    doc = _doc(personnel_total=50.0, stages=[_stage("S1", 50.0)])
    assert status_label(_by_id(build_cross_module_items(doc))["C01"]) == "通过"


# ---- C05 判定表的落盘与可达性 ----

def test_c05_tables_file_is_present_and_non_empty():
    """🔴 `data/rules/cross_module_c05.json` 缺失时 C05 **静默判错**，不报错。

    `_c05_tables()` 读不到文件就退化为空表 ⇒ 豁免与白名单同时失效 ⇒ 华丰/邦奇的 C05
    从「通过」翻成「错误」，而本地永远复现不出来（本地文件在）。本条把"文件必须真的在"
    钉成断言，使这种退化在任何跑得到测试的环境里立刻转红。

    ⚠️ 它拦不住"没被 git 跟踪"——那一层靠 `.gitignore` 的 `!data/rules/*.json` 负例守。
    """
    from qd_b_gate.rules.cross_module import C05_TABLE_PATH, _c05_tables

    assert C05_TABLE_PATH.exists(), f"C05 判定表缺失：{C05_TABLE_PATH}"
    exempt, mapping, _ = _c05_tables()
    assert "全项目周期" in exempt          # 护栏⑴ 的判例锚点
    assert mapping.get("项目立项")          # 护栏⑵ 的判例锚点


def test_c05_mapping_table_must_not_whitelist_the_case_8_mismapping():
    """🔴 映射表**不得**含「软硬件开发设计 → G2/G3」。

    信里那句"软硬件开发实际对应 G2/G3"是我方的说明，不是陈忱的裁定；他对第 8 条判 ❌。
    把它写进白名单会让第 8 条从「错误」翻回「通过」，与他的勾选直接相反——
    这是最容易被"顺手补全"补出来的一条，故单独设锁。
    """
    from qd_b_gate.rules.cross_module import _c05_tables

    _, mapping, _ = _c05_tables()
    assert "软硬件开发设计" not in mapping
