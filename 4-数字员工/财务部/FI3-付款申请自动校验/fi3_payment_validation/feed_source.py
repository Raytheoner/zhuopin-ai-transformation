"""FI3 数据接入层 —— `mock`（合成 CSV）／`u9c`（fail-loud 占位）两源开关。

档 1 只接 mock。`u9c` 抛 `RealEndpointNotReadyError`（平台共享异常），**不回退 mock**：
静默把 mock 混进真实决策是合规＋正确性双重风险（合规红线 §7-1）。

mock 六表（`data/mock/`，全部合成、供应商名与账号为占位）：
  payment_requests.csv / supplier_accounts.csv / contracts.csv / paid_vouchers.csv /
  prepayments.csv / fi2_match_results.csv
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from zhuopin_platform.shared_tools.connector_errors import RealEndpointNotReadyError

from . import config
from .holiday_calendar import HolidayCalendar
from .models import (
    Contract,
    FI2MatchResult,
    InvoiceRef,
    PaidVoucher,
    PaymentRequest,
    Prepayment,
    SupplierAccount,
)
from .validation_engine import ValidationContext

MOCK_DIR = Path(__file__).resolve().parent.parent / "data" / "mock"


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"mock 数据件缺失：{path}")
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _bool(s: str) -> bool:
    return s.strip().lower() in ("1", "true", "是", "y", "yes")


def _split(s: str) -> tuple[str, ...]:
    return tuple(x.strip() for x in s.split(";") if x.strip())


def load_payment_requests(d: Path = MOCK_DIR) -> list[PaymentRequest]:
    out = []
    for r in _rows(d / "payment_requests.csv"):
        invs = tuple(InvoiceRef(*p.split(":")) for p in _split(r["invoices"]))
        invs = tuple(InvoiceRef(i.inv_no, float(i.inv_amount)) for i in invs)
        out.append(PaymentRequest(
            req_no=r["req_no"], supplier_id=r["supplier_id"], supplier_name=r["supplier_name"],
            amount=float(r["amount"]), pay_type=r["pay_type"], submitted_on=r["submitted_on"],
            account_name=r["account_name"], bank_account=r["bank_account"], bank_name=r["bank_name"],
            contract_no=r["contract_no"], po_nos=_split(r["po_nos"]), invoices=invs,
            support_level=r["support_level"], accept_date=r["accept_date"], receipt_date=r["receipt_date"],
            invoice_date=r["invoice_date"], is_urgent=_bool(r["is_urgent"]), deduct_prepay_no=r["deduct_prepay_no"],
        ))
    return out


def load_context(source: str = config.DATA_SOURCE_DEFAULT, data_dir: Path = MOCK_DIR,
                 today: date | None = None, **kw) -> ValidationContext:
    if source == "u9c":
        raise RealEndpointNotReadyError("fi3.load_context", config.U9C_NOT_WIRED)
    if source != "mock":
        raise ValueError(f"未知数据源 {source!r}（只认 mock / u9c）")
    accounts = [SupplierAccount(r["supplier_id"], r["account_name"], r["bank_account"], r["bank_name"],
                                r["effective_from"], r["status"], r["first_use_confirmed_by"])
                for r in _rows(data_dir / "supplier_accounts.csv")]
    contracts = {r["contract_no"]: Contract(r["contract_no"], r["supplier_id"], float(r["cap_amount"]),
                                            r["term_clause"], _bool(r["is_framework"]), r["parent_contract_no"],
                                            _bool(r["is_provisional"]), r["status"])
                 for r in _rows(data_dir / "contracts.csv")}
    vouchers = [PaidVoucher(r["voucher_no"], r["supplier_id"], float(r["amount"]), r["pay_date"],
                            r["inv_no"], r["po_no"], r["contract_no"])
                for r in _rows(data_dir / "paid_vouchers.csv")]
    prepays = [Prepayment(r["prepay_no"], r["supplier_id"], float(r["amount"]), r["paid_on"],
                          float(r["written_off_amount"]), _bool(r["invoice_received"]), r["contract_no"])
               for r in _rows(data_dir / "prepayments.csv")]
    fi2 = {r["inv_no"]: FI2MatchResult(r["inv_no"], r["ap_no"], r["match_class"])
           for r in _rows(data_dir / "fi2_match_results.csv")}
    return ValidationContext(
        accounts=accounts, contracts=contracts, vouchers=vouchers, prepayments=prepays,
        fi2_results=fi2, calendar=HolidayCalendar.load(), today=today or date.today(),
        data_source=source, **kw,
    )
