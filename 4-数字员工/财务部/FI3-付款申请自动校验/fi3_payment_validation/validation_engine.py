"""FI3 校验引擎 —— 一张付款申请跑完全部适用校验，归入四态（就绪清单 §四 口径底稿）。

  🟢 通过     全部适用校验在规则内
  🟡 提醒放行 有提醒／预警级发现（新账户首用／疑似重复／暂估价 30%／未扣回预付款／到期日算不出）
  🔴 拦截     有拦截级发现
  🟣 特批     拦截项**仅**为 FI3-1 三单未配齐、且申请标紧急 ⇒ 走 R7 通道（CFO 批＋限期补齐＋跟踪清单）

🔴 L3：`ValidationVerdict.needs_manual_review` 恒 `True`，四态都是「建议」，付款执行永远人工。
🔴 每张申请的结论写平台 `audit`（append-only）：`decision` 走 `config.audit_decision()` 恒带
   `RULE_VERSION`，payload 不含原始账号（只留尾 4 位）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from zhuopin_platform.audit import AuditEvent, AuditLogger

from . import checks, config
from .holiday_calendar import HolidayCalendar
from .models import (
    CheckFinding,
    Contract,
    FI2MatchResult,
    PaidVoucher,
    PaymentRequest,
    Prepayment,
    SupplierAccount,
    ValidationVerdict,
)

OUTCOME_PASS = "🟢通过"
OUTCOME_REMIND = "🟡提醒放行"
OUTCOME_BLOCK = "🔴拦截"
OUTCOME_SPECIAL = "🟣特批"


@dataclass
class ValidationContext:
    """一次批量校验所需的全部上游数据（档 1 由 mock CSV 装载）。"""
    accounts: list[SupplierAccount]
    contracts: dict[str, Contract]
    vouchers: list[PaidVoucher]
    prepayments: list[Prepayment]
    fi2_results: dict[str, FI2MatchResult]
    calendar: HolidayCalendar
    today: date
    data_source: str = "mock"
    audit_logger: AuditLogger | None = None
    evaluator: str = "待指定"                # L3 清单的复核人（实名由财务侧指定，本包不代填）
    tracking_list: list[dict] = field(default_factory=list)   # 《未匹配付款跟踪清单》


def _classify(findings: list[CheckFinding], req: PaymentRequest) -> str:
    blocks = [f for f in findings if f.level == config.LEVEL_BLOCK]
    if blocks:
        only_three_way = all(f.code == "three_way_unmatched" for f in blocks)
        if only_three_way and req.is_urgent:
            return OUTCOME_SPECIAL
        return OUTCOME_BLOCK
    if any(f.level in (config.LEVEL_REMIND, config.LEVEL_WARN) for f in findings):
        return OUTCOME_REMIND
    return OUTCOME_PASS


def validate(req: PaymentRequest, ctx: ValidationContext) -> ValidationVerdict:
    findings: list[CheckFinding] = []
    findings += checks.check_three_way_match(req, ctx.fi2_results)
    findings += checks.check_account(req, ctx.accounts, ctx.today)
    findings += checks.check_duplicate(req, ctx.vouchers, ctx.prepayments, ctx.today)
    findings += checks.check_contract_cap(req, ctx.contracts, ctx.vouchers)
    findings += checks.check_prepayment(req, ctx.prepayments, ctx.today)
    due, due_findings = checks.compute_due_date(req, ctx.contracts.get(req.contract_no), ctx.calendar)
    findings += due_findings

    verdict = ValidationVerdict(
        req_no=req.req_no,
        outcome=_classify(findings, req),
        findings=findings,
        due_date=due.isoformat() if due else None,
        prepay_ageing=checks.prepay_ageing(req, ctx.prepayments, ctx.today),
        automation_level=config.AUTOMATION_LEVEL,
        rule_version=config.RULE_VERSION,
    )
    if verdict.outcome == OUTCOME_SPECIAL:
        r7 = config.CRITERIA.value_of("R7_URGENT_CHANNEL")
        deadline = ctx.calendar.add_workdays(ctx.today, r7["backfill_workdays"])
        verdict.special_approval = {
            "approver": r7["approver"], "tag": r7["tag"],
            "backfill_deadline": deadline.isoformat(), "tracking_list": r7["tracking_list"],
        }
        ctx.tracking_list.append({"req_no": req.req_no, "supplier_id": req.supplier_id,
                                  "amount": req.amount, "backfill_deadline": deadline.isoformat()})
    _audit(req, verdict, ctx)
    return verdict


def validate_batch(reqs: list[PaymentRequest], ctx: ValidationContext) -> list[ValidationVerdict]:
    return [validate(r, ctx) for r in reqs]


def _audit(req: PaymentRequest, v: ValidationVerdict, ctx: ValidationContext) -> None:
    if ctx.audit_logger is None:
        return
    ctx.audit_logger.record(AuditEvent(
        scenario="FI3",
        action="payment_request_validate",
        evaluator=ctx.evaluator,
        automation_level=config.AUTOMATION_LEVEL,
        decision=config.audit_decision(
            req_no=req.req_no, outcome=v.outcome, due_date=v.due_date,
            findings=[{"check": f.check_id, "code": f.code, "level": f.level, "reason": f.reason} for f in v.findings],
            special_approval=v.special_approval,
        ),
        data_sources={"payment_request": ctx.data_source, "fi2_match": ctx.data_source,
                      "holiday_calendar": "tangyanping-2026-08-22"},
    ))
