"""FI3-1 … FI3-6 六个子场景的校验器（纯函数；口径全部从 `config.CRITERIA` 读，不写死）。

每个校验器：输入一张 `PaymentRequest` ＋ 所需上下文，输出 `list[CheckFinding]`（空列表＝该项通过）。
等级字面由 `_level(code)` 从 R1 取——检查器只说「命中了什么」，「命中算拦截还是提醒」是财务侧定的。

🔴 三条共同纪律：
  · 主数据缺失不等于通过（无收款账户主数据／无合同记录 ⇒ 拦截，不猜）。
  · 算不出来就说算不出来（账期条款解析失败／锚点缺失 ⇒ 提醒需人工，不回落默认）。
  · 日历越界 fail-loud，由 `HolidayCalendar` 抛，本模块不捕获。
"""
from __future__ import annotations

import re
from calendar import monthrange
from datetime import date, timedelta

from . import config
from .holiday_calendar import HolidayCalendar
from .models import (
    CheckFinding,
    Contract,
    FI2MatchResult,
    PaidVoucher,
    PaymentRequest,
    Prepayment,
    SupplierAccount,
    mask_account,
)


def _level(code: str) -> str:
    return config.CRITERIA.value_of("R1_SEVERITY_MAP")[code]


def _d(s: str) -> date:
    return date.fromisoformat(s)


# ── FI3-1 三单匹配状态前置校验（消费 FI2 结果）──

def check_three_way_match(req: PaymentRequest, fi2: dict[str, FI2MatchResult]) -> list[CheckFinding]:
    """每张所附发票须在 FI2 结果里且类别 ∈ `FI2_MATCHED_CLASSES`，否则「未配齐」。预付款不适用。"""
    if req.pay_type != "正式":
        return []
    unmatched: list[dict] = []
    for inv in req.invoices:
        r = fi2.get(inv.inv_no)
        if r is None:
            unmatched.append({"inv_no": inv.inv_no, "fi2": "无匹配结果"})
        elif r.match_class not in config.FI2_MATCHED_CLASSES:
            unmatched.append({"inv_no": inv.inv_no, "fi2": r.match_class, "ap_no": r.ap_no})
    if not req.invoices:
        unmatched.append({"inv_no": "", "fi2": "申请未附发票"})
    if not unmatched:
        return []
    return [CheckFinding(
        "FI3-1", "three_way_unmatched", _level("three_way_unmatched"),
        f"三单未配齐：{len(unmatched)} 张发票未通过 FI2 匹配",
        {"unmatched": unmatched},
    )]


# ── FI3-2 收款账户与合同比对 ──

def check_account(req: PaymentRequest, accounts: list[SupplierAccount], today: date) -> list[CheckFinding]:
    rules = config.CRITERIA.value_of("R2_ACCOUNT_RULES")
    active = [a for a in accounts if a.supplier_id == req.supplier_id and a.status == "生效"]
    if not active:
        return [CheckFinding(
            "FI3-2", "account_mismatch", _level("account_mismatch"),
            "供应商主数据无生效收款账户，无法比对（缺主数据不等于通过）",
            {"supplier_id": req.supplier_id},
        )]
    # 变更生效前 30 天新旧并行：取所有仍在并行窗口内的账户作比对候选
    parallel = timedelta(days=rules["change_parallel_days"])
    candidates = []
    for a in active:
        eff = _d(a.effective_from)
        if eff <= today + parallel:
            candidates.append(a)
    matched = None
    for a in candidates:
        if all(getattr(a, f).strip() == getattr(req, f).strip() for f in rules["fields"]):
            matched = a
            break
    if matched is None:
        latest = max(active, key=lambda a: a.effective_from)
        diff = [f for f in rules["fields"] if getattr(latest, f).strip() != getattr(req, f).strip()]
        return [CheckFinding(
            "FI3-2", "account_mismatch", _level("account_mismatch"),
            f"收款账户与主数据不一致（{'／'.join(diff)}）",
            {"request_account": mask_account(req.bank_account), "master_account": mask_account(latest.bank_account),
             "diff_fields": diff},
        )]
    findings: list[CheckFinding] = []
    if today - _d(matched.effective_from) <= parallel and not matched.first_use_confirmed_by:
        findings.append(CheckFinding(
            "FI3-2", "new_account_first_use", _level("new_account_first_use"),
            f"新账户首次使用，须{rules['first_use_confirmer']}确认",
            {"effective_from": matched.effective_from, "account": mask_account(matched.bank_account)},
        ))
    return findings


# ── FI3-3 重复付款检测 ──

def check_duplicate(req: PaymentRequest, vouchers: list[PaidVoucher], prepays: list[Prepayment],
                    today: date) -> list[CheckFinding]:
    p = config.CRITERIA.value_of("R3_DUPLICATE_PARAMS")
    findings: list[CheckFinding] = []
    lookback_start = today - timedelta(days=30 * p["lookback_months"])
    hist = [v for v in vouchers if v.supplier_id == req.supplier_id and _d(v.pay_date) >= lookback_start]

    # 发票级累计：已付 ＋ 本次 ≤ 发票额（允许分次付款）
    if p["invoice_level_cumulative"] and req.invoices:
        total_inv = sum(i.inv_amount for i in req.invoices)
        paid = sum(v.amount for v in hist if v.inv_no in {i.inv_no for i in req.invoices})
        if round(paid + req.amount, 2) > round(total_inv, 2):
            findings.append(CheckFinding(
                "FI3-3", "over_invoice_total", _level("over_invoice_total"),
                f"累计付款超发票额：已付 {paid:.2f} ＋ 本次 {req.amount:.2f} ＞ 发票额 {total_inv:.2f}",
                {"paid": paid, "this": req.amount, "invoice_total": total_inv},
            ))

    # 疑似重复：同供应商 ＋ 同金额 ＋ ±N 天
    window = timedelta(days=p["same_supplier_same_amount_days"])
    sub = _d(req.submitted_on)
    suspects = [v.voucher_no for v in hist
                if abs(v.amount - req.amount) < 0.005 and abs(_d(v.pay_date) - sub) <= window]
    if suspects:
        findings.append(CheckFinding(
            "FI3-3", "suspected_duplicate", _level("suspected_duplicate"),
            f"疑似重复付款：同供应商同金额、{p['same_supplier_same_amount_days']} 天内已有 {len(suspects)} 笔",
            {"vouchers": suspects},
        ))

    # 预付款扣回：存在未核销预付款而本次正式付款未扣回
    if req.pay_type == "正式":
        open_prepays = [x for x in prepays if x.supplier_id == req.supplier_id and x.outstanding > 0]
        if open_prepays and not req.deduct_prepay_no:
            findings.append(CheckFinding(
                "FI3-3", "prepay_unwrittenoff", _level("prepay_unwrittenoff"),
                f"该供应商有 {len(open_prepays)} 笔未核销预付款，本次未扣回",
                {"prepays": [{"prepay_no": x.prepay_no, "outstanding": x.outstanding} for x in open_prepays]},
            ))
    return findings


# ── FI3-4 累计付款超合同/订单拦截 ──

def _rollup_contract_nos(contract: Contract, contracts: dict[str, Contract]) -> set[str]:
    """框架合同：父合同 ＋ 全部子订单一并汇总（R4 framework_rollup）。"""
    root = contract
    while root.parent_contract_no and root.parent_contract_no in contracts:
        root = contracts[root.parent_contract_no]
    if not root.is_framework:
        return {contract.contract_no}
    nos = {root.contract_no}
    nos |= {c.contract_no for c in contracts.values() if c.parent_contract_no == root.contract_no}
    return nos


def check_contract_cap(req: PaymentRequest, contracts: dict[str, Contract],
                       vouchers: list[PaidVoucher]) -> list[CheckFinding]:
    if not req.contract_no:
        return []
    r4 = config.CRITERIA.value_of("R4_CONTRACT_CAP")
    contract = contracts.get(req.contract_no)
    if contract is None:
        return [CheckFinding(
            "FI3-4", "over_contract_cap", _level("over_contract_cap"),
            f"合同 {req.contract_no} 在合同主数据中不存在，无法核对上限（缺记录不等于通过）",
            {"contract_no": req.contract_no},
        )]
    nos = _rollup_contract_nos(contract, contracts) if r4["framework_rollup"] else {contract.contract_no}
    cap_holder = contracts[contract.parent_contract_no] if (contract.parent_contract_no in contracts
                                                            and contracts[contract.parent_contract_no].is_framework) else contract
    cap = cap_holder.cap_amount
    paid = sum(v.amount for v in vouchers if v.contract_no in nos)
    cumulative = round(paid + req.amount, 2)
    ev = {"contract_no": cap_holder.contract_no, "cap": cap, "paid": paid, "this": req.amount,
          "cumulative": cumulative, "basis": r4["basis"], "rolled_up": sorted(nos)}
    if cumulative > cap:
        return [CheckFinding("FI3-4", "over_contract_cap", _level("over_contract_cap"),
                             f"累计付款 {cumulative:.2f} 超合同上限 {cap:.2f}（{r4['basis']}口径）", ev)]
    if cap_holder.is_provisional and cap > 0:
        ratio = cumulative / cap
        ev["ratio"] = round(ratio, 4)
        if ratio >= r4["provisional_block_pct"]:
            return [CheckFinding("FI3-4", "provisional_block", _level("provisional_block"),
                                 f"暂估价合同累计付款达 {ratio:.0%}，触及 {r4['provisional_block_pct']:.0%} 拦截线", ev)]
        if ratio >= r4["provisional_warn_pct"]:
            return [CheckFinding("FI3-4", "provisional_warn", _level("provisional_warn"),
                                 f"暂估价合同累计付款达 {ratio:.0%}，触及 {r4['provisional_warn_pct']:.0%} 预警线", ev)]
    return []


# ── FI3-5 预付款管控与核销校验 ──

def prepay_tier(amount: float) -> tuple[str, str]:
    """按 R5 返回 (最低单据支撑, 审批人)。"""
    for lo, hi, support, approver in config.CRITERIA.value_of("R5_PREPAY_TIERS")["tiers"]:
        if amount >= lo and (hi is None or amount < hi):
            return support, approver
    raise ValueError(f"金额 {amount} 未落入任何 R5 档位")   # 档位连续覆盖 [0, ∞)，到这里即配置损坏


def check_prepayment(req: PaymentRequest, prepays: list[Prepayment], today: date) -> list[CheckFinding]:
    findings: list[CheckFinding] = []
    if req.pay_type == "预付":
        r5 = config.CRITERIA.value_of("R5_PREPAY_TIERS")
        rank = list(r5["support_rank"])
        need, approver = prepay_tier(req.amount)
        have = req.support_level or "无单据"
        if have not in rank:
            raise ValueError(f"support_level={have!r} 不在 R5 support_rank 中")
        if rank.index(have) < rank.index(need):
            findings.append(CheckFinding(
                "FI3-5", "prepay_no_support", _level("prepay_no_support"),
                f"预付款 {req.amount:.2f} 按 R5 须「{need}」（{approver}批），实际「{have}」；"
                f"例外一律 {r5['exception_approver']} 批＋≤{r5['exception_backfill_workdays']} 工作日补签",
                {"required_support": need, "required_approver": approver, "actual_support": have},
            ))
    return findings


def prepay_ageing(req: PaymentRequest, prepays: list[Prepayment], today: date) -> list[dict]:
    """账龄**度量**（天数），不判预警——`PENDING.PREPAY_AGEING_WARN_DAYS` 未签认。"""
    return [
        {"prepay_no": x.prepay_no, "outstanding": x.outstanding, "age_days": (today - _d(x.paid_on)).days,
         "invoice_received": x.invoice_received}
        for x in prepays if x.supplier_id == req.supplier_id and x.outstanding > 0
    ]


# ── FI3-6 付款日期自动计算 ──

_CLAUSE_RE = re.compile(r"^(验收后|到货后|月结|票到后)\s*(\d+)?\s*天?$")


def parse_term_clause(clause: str) -> tuple[str, int] | None:
    """解析账期条款为 (种类, 天数)；解析不出返回 None（由调用方标提醒，不猜）。"""
    r6 = config.CRITERIA.value_of("R6_TERM_CLAUSES")
    m = _CLAUSE_RE.match(clause.strip())
    if not m or m.group(1) not in r6["kinds"]:
        return None
    kind, days = m.group(1), m.group(2)
    if days is None:
        if kind == "票到后":
            return kind, r6["invoice_default_days"]
        return None
    return kind, int(days)


def compute_due_date(req: PaymentRequest, contract: Contract | None,
                     calendar: HolidayCalendar) -> tuple[date | None, list[CheckFinding]]:
    clause = contract.term_clause if contract else ""
    if not clause:
        return None, [CheckFinding("FI3-6", "due_date_unresolved", _level("due_date_unresolved"),
                                   "无合同账期条款，付款到期日无法计算", {"contract_no": req.contract_no})]
    parsed = parse_term_clause(clause)
    if parsed is None:
        return None, [CheckFinding("FI3-6", "due_date_unresolved", _level("due_date_unresolved"),
                                   f"账期条款「{clause}」不在 R6 四类之内，需人工判定", {"clause": clause})]
    kind, days = parsed
    anchor_field = {"验收后": "accept_date", "到货后": "receipt_date", "票到后": "invoice_date", "月结": "invoice_date"}[kind]
    anchor = getattr(req, anchor_field)
    if not anchor:
        return None, [CheckFinding("FI3-6", "due_date_unresolved", _level("due_date_unresolved"),
                                   f"账期「{clause}」需要 {anchor_field}，申请未提供", {"clause": clause})]
    a = _d(anchor)
    if kind == "月结":
        month_end = date(a.year, a.month, monthrange(a.year, a.month)[1])
        raw = month_end + timedelta(days=days)
    else:
        raw = a + timedelta(days=days)
    return calendar.roll_to_workday(raw), []   # 越界由日历 fail-loud
