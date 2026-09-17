"""档 1 mock：规则表装载、覆盖层、结构闸、红线流、评分分级、分流、审计。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from zhuopin_platform.audit import AuditLogger, JsonlSink
from zhuopin_platform.criteria_signoff import CriterionNotSignedOffError

from q2_8d_verdict import config
from q2_8d_verdict.engine import AsilExcludedError, VerdictEngine
from q2_8d_verdict.models import Disposition, EightDInput, RedlineStatus, RuleStatus
from q2_8d_verdict.rules_loader import RULES_JSON_PATH
from q2_8d_verdict.semantic import HumanVerdictSource

REPO = RULES_JSON_PATH.parents[5]


# ── 规则表与签认 ──
def test_rules_json_is_canon_copy():
    canon = REPO / config.RULES_JSON_CANON_RELPATH
    assert hashlib.sha256(canon.read_bytes()).hexdigest() == config.RULES_JSON_SHA256
    assert hashlib.sha256(RULES_JSON_PATH.read_bytes()).hexdigest() == config.RULES_JSON_SHA256


def test_ruleset_totals_and_overlay(ruleset):
    assert len(ruleset.rules) == 51                       # 51 − D3-03（并入）＋ D3-06
    assert ruleset.max_score("制造") == 100.0 and ruleset.max_score("研发") == 100.0
    ids = {r.rule_id: r for r in ruleset.rules}
    assert "D3-03" not in ids and ids["D3-06"].deduct_cap == 8.0
    assert ids["D7-M3"].judge_method == "关键词" and ids["D2-R3"].judge_method == "关键词" and ids["D6-R1"].judge_method == "关键词"
    assert ids["D7-03"].deduct_cap == 4.0
    assert ids["D2-R2"].deduct_cap == 0.5                # M6 封顶
    rl = {r.redline_no: r for r in ruleset.redlines}
    assert rl[3].judge_method == "规则引擎" and "不符" in rl[2].description
    assert ruleset.grade_of(89.5) == "B" and ruleset.grade_of(90) == "A" and ruleset.grade_of(74.99) == "C" and ruleset.grade_of(59) == "D"


def test_signoffs_are_named_and_pending_fails_loud():
    assert config.CRITERIA.fully_signed and "unsigned" not in config.RULE_VERSION
    assert all(c.signoff.signed_by == "陈忱" for c in config.CRITERIA)
    assert "unsigned" in config.PENDING_VERSION
    with pytest.raises(CriterionNotSignedOffError):
        config.PENDING.value_of("MEASURE_VERIFIABILITY_STANDARD")
    with pytest.raises(CriterionNotSignedOffError):
        config.PENDING.value_of("SEMANTIC_LAYER_ACCEPTANCE")
    assert config.AUTOMATION_LEVEL == "L2"


# ── 样本逐份对照 ──
def test_all_mock_samples_match_expected(engine, samples):
    for rid, (doc, exp) in samples.items():
        v = engine.evaluate(doc)
        assert v.structural_return == exp["structural_return"], rid
        assert v.needs_manual_review is True and v.automation_level == "L2"
        if exp.get("empties"):
            assert list(v.structural_empty_sections) == exp["empties"], rid
            assert v.redlines == () and v.rules == () and v.disposition == Disposition.STRUCTURAL_RETURN
        st = {r.redline_no: r.status for r in v.redlines}
        for n in exp.get("redlines_triggered", []):
            assert st[n] == RedlineStatus.TRIGGERED, (rid, n, v.redlines)
        for n in exp.get("redlines_clear", []):
            assert st[n] == RedlineStatus.CLEAR, (rid, n, st)
        for n in exp.get("redlines_suspected", []):
            assert st[n] == RedlineStatus.SUSPECTED, (rid, n, st)
        if not v.structural_return:
            assert st[2] == RedlineStatus.NOT_ACCEPTED and st[3] == RedlineStatus.NOT_ACCEPTED, rid   # 判例 11
            assert not [r for r in v.redlines if r.redline_no in (1, 5) and r.status == RedlineStatus.TRIGGERED], rid  # P1
        if "grade" in exp:
            assert v.grade == exp["grade"], (rid, v.grade, v.notes)
        if "grade_upper" in exp:
            assert v.grade_range[1] == exp["grade_upper"], (rid, v.score_auto, v.score_upper)
        if exp.get("all_deterministic_pass"):
            bad = [f for f in v.rules if f.status == RuleStatus.FAIL]
            assert not bad, (rid, bad)
        for fid in exp.get("fail_rules", []):
            assert next(f for f in v.rules if f.rule_id == fid).status == RuleStatus.FAIL, rid
        for step in exp.get("na_steps", []):
            assert all(f.status == RuleStatus.NA for f in v.rules if f.step == step), rid
        if "scene" in exp:
            assert v.scene == exp["scene"] and tuple(exp["flags"]) == v.scene_flags[:1]
        if "disposition" in exp:
            assert v.disposition.value == exp["disposition"], rid


def test_semantic_pending_gives_range_not_grade(engine, samples):
    v = engine.evaluate(samples["MOCK-B-合格-制造"][0])
    assert v.grade is None and v.score_pending_max > 0
    assert v.score_auto + v.score_pending_max == pytest.approx(100.0)   # 全部确定性条满分
    assert v.grade_range == ("D", "A") and v.disposition == Disposition.MANUAL
    assert sum(1 for f in v.rules if f.status == RuleStatus.PENDING) == 20   # 制造场景语义条数（通用 17 ＋ 制造 3）


def test_human_verdict_completes_grade_and_archive_advice(ruleset, samples):
    doc = samples["MOCK-B-合格-制造"][0]
    src = HumanVerdictSource()
    src.rules[doc.report_id] = {r.rule_id: 1.0 for r in ruleset.for_scene("制造") if r.is_semantic}
    src.redlines[doc.report_id] = {1: False, 5: False}
    v = VerdictEngine(ruleset=ruleset, semantic=src).evaluate(doc)
    assert v.grade == "A" and v.score_auto == 100.0 and v.disposition == Disposition.MANUAL   # ②③ 仍转人工（判例 11）
    src.redlines[doc.report_id] = {1: True, 5: False}
    v2 = VerdictEngine(ruleset=ruleset, semantic=src).evaluate(doc)
    assert v2.grade == "D" and {r.redline_no for r in v2.redlines if r.status == RedlineStatus.TRIGGERED} == {1}


def test_d3_subfield_deduction_capped(engine, samples):
    doc = samples["MOCK-6-沙特不良"][0]
    v = engine.evaluate(doc)
    ded = next(f for f in v.rules if f.rule_id == "D3-06·扣分")
    assert ded.score <= 0 and abs(ded.score) <= 8.0
    d3_total = sum(f.score for f in v.rules if f.step == "D3")
    assert d3_total >= 0                                   # 段内不扣负


def test_safety_related_routes_manual_even_when_clean(ruleset, samples):
    doc, _ = samples["MOCK-B-合格-制造"]
    doc2 = EightDInput(**{**doc.__dict__, "report_id": "SAFE", "safety_related": True})
    v = VerdictEngine(ruleset=ruleset).evaluate(doc2)
    assert v.disposition == Disposition.MANUAL and any("判例 6" in n for n in v.notes)


def test_asil_cd_is_hard_excluded(engine, samples):
    doc, _ = samples["MOCK-B-合格-制造"]
    with pytest.raises(AsilExcludedError):
        engine.evaluate(EightDInput(**{**doc.__dict__, "asil_level": "C"}))


def test_extraction_miss_never_triggers_redline4(engine, samples):
    doc, _ = samples["MOCK-7-不小心撞击"]
    from q2_8d_verdict.models import Confidence, TraceField
    tf = tuple(TraceField(t.name, t.value, Confidence.LOW if not t.value else t.confidence) for t in doc.trace_fields)
    v = engine.evaluate(EightDInput(**{**doc.__dict__, "trace_fields": tf}))
    assert {r.status for r in v.redlines if r.redline_no == 4} == {RedlineStatus.MANUAL_CHECK}   # P2


def test_audit_every_report(tmp_path: Path, ruleset, samples):
    log = tmp_path / "audit.jsonl"
    eng = VerdictEngine(ruleset=ruleset, audit=AuditLogger(JsonlSink(log)))
    for doc, _ in samples.values():
        eng.evaluate(doc)
    rows = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == len(samples)
    assert all(r["decision"]["rule_version"] == config.RULE_VERSION and r["automation_level"] == "L2" for r in rows)


def test_cli_renders(tmp_path: Path):
    from q2_8d_verdict.run import main
    assert main(["--source", "mock", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "q2_verdicts.md").exists() and (tmp_path / "q2_audit.jsonl").exists()
