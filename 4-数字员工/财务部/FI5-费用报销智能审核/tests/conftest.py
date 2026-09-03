"""FI5 测试夹具（骨架期）。"""
from __future__ import annotations

import sys
from pathlib import Path

# —— 平台底座路径引导（队列 #345 收拢；唯一被允许的样板，实现见
# `5-平台底座/zhuopin_platform/zhuopin_platform/bootstrap.py`）。必须放在本文件任何
# zhuopin_platform / 场景包 import 之前。下方五行只负责让 bootstrap 自身可被 import、
# 不含任何判断分支；开发机 monorepo 与 `.51` 扁平部署两种布局的分歧由 ensure_paths 处理。——
_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, _HERE.parent.parent, strict=True)  # noqa: E402

import pytest

from fi5_expense_audit.models import BudgetBalance, ExpenseClaim, ExpenseLine

_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def mock_dir() -> Path:
    return _ROOT / "data" / "mock"


@pytest.fixture
def simple_claim() -> ExpenseClaim:
    return ExpenseClaim(
        claim_id="EXP-2026-09-0001",
        claimant="示例申请人",
        department="供应链",
        period="2026-09",
        claim_type="差旅",
        total_amount=2860.0,
    )


@pytest.fixture
def simple_lines() -> list[ExpenseLine]:
    return [
        ExpenseLine("EXP-2026-09-0001", 1, "差旅费-住宿", 2400.0,
                    invoice_no="00000000000001", travel_grade="M2", nights=3),
        ExpenseLine("EXP-2026-09-0001", 2, "业务招待费", 460.0,
                    invoice_no="00000000000002", occasion="客户来访", headcount=4),
    ]


@pytest.fixture
def simple_budget() -> list[BudgetBalance]:
    return [
        BudgetBalance("供应链", "差旅费-住宿", "2026-09", 20000.0, 18500.0),
        BudgetBalance("供应链", "业务招待费", "2026-09", 6000.0, 5800.0),
    ]
