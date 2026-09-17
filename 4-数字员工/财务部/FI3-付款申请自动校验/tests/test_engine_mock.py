"""档 1 mock 端到端：十二张合成申请逐张对四态与子场景命中；u9c fail-loud；审计留痕；仪表盘。"""
from __future__ import annotations

import json
from datetime import date

import pytest

from zhuopin_platform.shared_tools.connector_errors import RealEndpointNotReadyError

from fi3_payment_validation import checks, dashboard, feed_source, validation_engine as ve
from fi3_payment_validation.holiday_calendar import CalendarOutOfRangeError
from fi3_payment_validation.models import PaymentRequest

EXPECTED = {
    "REQ-001": (ve.OUTCOME_PASS, set(), "2026-10-10"),                    # 验收后30天落调休周六，不顺延
    "REQ-002": (ve.OUTCOME_BLOCK, {"over_invoice_total"}, "2026-10-08"),  # 10-05 国庆 → 10-08
    "REQ-003": (ve.OUTCOME_REMIND, {"new_account_first_use", "suspected_duplicate"}, "2026-10-08"),
    "REQ-004": (ve.OUTCOME_BLOCK, {"account_mismatch", "three_way_unmatched"}, "2026-09-20"),  # 票到后10天落 9-20 调休周日，不顺延
    "REQ-005": (ve.OUTCOME_BLOCK, {"over_contract_cap"}, "2026-10-30"),   # 框架汇总 270k+40k > 300k
    "REQ-006": (ve.OUTCOME_REMIND, {"provisional_warn"}, "2026-10-08"),   # 35% 预警
    "REQ-007": (ve.OUTCOME_BLOCK, {"provisional_block"}, "2026-10-09"),   # 55% 拦截
    "REQ-008": (ve.OUTCOME_BLOCK, {"prepay_no_support", "due_date_unresolved"}, None),
    "REQ-009": (ve.OUTCOME_PASS, set(), "2026-10-10"),
    "REQ-010": (ve.OUTCOME_REMIND, {"prepay_unwrittenoff"}, "2026-10-08"),
    "REQ-011": (ve.OUTCOME_BLOCK, {"account_mismatch", "due_date_unresolved"}, None),
    "REQ-012": (ve.OUTCOME_SPECIAL, {"three_way_unmatched"}, "2026-10-15"),
}


def test_mock_batch_matches_expected_outcomes(ctx, requests_by_no):
    verdicts = {v.req_no: v for v in ve.validate_batch(list(requests_by_no.values()), ctx)}
    assert set(verdicts) == set(EXPECTED)
    for req_no, (outcome, codes, due) in EXPECTED.items():
        v = verdicts[req_no]
        assert v.outcome == outcome, (req_no, v.findings)
        assert {f.code for f in v.findings} == codes, (req_no, v.findings)
        assert v.due_date == due, req_no
        assert v.needs_manual_review is True and v.automation_level == "L3"
        assert v.rule_version.startswith("fi3-v1-tangyanping")


def test_special_approval_uses_r7_and_workday_deadline(ctx, requests_by_no, calendar):
    v = ve.validate(requests_by_no["REQ-012"], ctx)
    sa = v.special_approval
    assert (sa["approver"], sa["tag"], sa["tracking_list"]) == ("CFO", "紧急特批", "未匹配付款跟踪清单")
    assert sa["backfill_deadline"] == calendar.add_workdays(date(2026, 9, 17), 7).isoformat() == "2026-09-28"
    assert calendar.is_workday(date(2026, 9, 20))        # 9-20 调休上班计入 7 个工作日
    assert not calendar.is_workday(date(2026, 9, 25))   # 9-25 中秋不计入
    assert ctx.tracking_list and ctx.tracking_list[0]["req_no"] == "REQ-012"


def test_urgent_does_not_bypass_non_three_way_blocks(ctx, requests_by_no):
    """R7 只豁免「三单未配齐」；紧急标记对账户不符／超合同无效。"""
    r = requests_by_no["REQ-004"]
    r.is_urgent = True
    assert ve.validate(r, ctx).outcome == ve.OUTCOME_BLOCK


def test_findings_never_expose_full_account(ctx, requests_by_no):
    v = ve.validate(requests_by_no["REQ-004"], ctx)
    for f in v.findings:
        for val in f.evidence.values():
            assert "6222000000009999" not in str(val) and "6222000000002233" not in str(val)


def test_prepay_ageing_is_measure_only(ctx, requests_by_no):
    v = ve.validate(requests_by_no["REQ-010"], ctx)
    assert v.prepay_ageing == [{"prepay_no": "PP-001", "outstanding": 150000.0, "age_days": 130,
                                "invoice_received": False}]
    assert not any(f.code == "prepay_ageing" for f in v.findings)   # 天数未签认 ⇒ 不判预警


def test_missing_master_data_is_block_not_pass(ctx):
    r = PaymentRequest("REQ-Z", "SUP-404", "无主数据供应商", 1.0, "正式", "2026-09-16",
                       "x", "1", "y", contract_no="CT-404", invoices=())
    v = ve.validate(r, ctx)
    codes = {f.code for f in v.findings}
    assert {"account_mismatch", "over_contract_cap", "three_way_unmatched"} <= codes
    assert v.outcome == ve.OUTCOME_BLOCK


def test_term_clause_parser_follows_r6():
    assert checks.parse_term_clause("验收后30天") == ("验收后", 30)
    assert checks.parse_term_clause("月结60天") == ("月结", 60)
    assert checks.parse_term_clause("票到后") == ("票到后", 10)      # R6 票到后默认 10 天
    assert checks.parse_term_clause("季度结算") is None
    assert checks.parse_term_clause("验收后") is None                # 缺天数不猜


def test_due_date_beyond_calendar_fails_loud(ctx, requests_by_no):
    r = requests_by_no["REQ-001"]
    r.accept_date = "2028-01-01"
    with pytest.raises(CalendarOutOfRangeError):
        ve.validate(r, ctx)


def test_u9c_source_fails_loud_no_mock_fallback():
    with pytest.raises(RealEndpointNotReadyError):
        feed_source.load_context("u9c")
    with pytest.raises(ValueError):
        feed_source.load_context("csv")


def test_audit_written_per_request_with_rule_version(tmp_path, requests_by_no):
    from zhuopin_platform.audit import AuditLogger
    from zhuopin_platform.audit.sinks import JsonlSink
    log = tmp_path / "audit.jsonl"
    ctx = feed_source.load_context("mock", today=date(2026, 9, 17), audit_logger=AuditLogger(JsonlSink(log)))
    ve.validate_batch(list(requests_by_no.values()), ctx)
    rows = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(rows) == 12
    assert all(r["decision"]["rule_version"] == "fi3-v1-tangyanping-2026-07-10" for r in rows)
    assert all(r["automation_level"] == "L3" and r["scenario"] == "FI3" for r in rows)
    assert "6222000000009999" not in log.read_text(encoding="utf-8")


def test_dashboard_summary_and_markdown(ctx, requests_by_no):
    verdicts = ve.validate_batch(list(requests_by_no.values()), ctx)
    s = dashboard.summarize(verdicts)
    assert s["total"] == 12
    assert s["by_outcome"] == {ve.OUTCOME_PASS: 2, ve.OUTCOME_REMIND: 3, ve.OUTCOME_BLOCK: 6, ve.OUTCOME_SPECIAL: 1}
    assert set(s["by_check"]) == {"FI3-1", "FI3-2", "FI3-3", "FI3-4", "FI3-5", "FI3-6"}
    md = dashboard.render_markdown(verdicts)
    assert "付款执行永远由人" in md and "REQ-012" in md and "紧急特批" in md
    assert "6222000000009999" not in md


def test_cli_runs_on_mock(tmp_path):
    from fi3_payment_validation import run
    out = tmp_path / "list.md"
    assert run.main(["--today", "2026-09-17", "--out", str(out), "--audit", str(tmp_path / "a.jsonl")]) == 0
    assert out.read_text(encoding="utf-8").startswith("# FI3 付款申请校验清单")
