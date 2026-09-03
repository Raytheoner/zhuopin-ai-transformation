"""FI8 测试夹具（骨架期）。"""
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

from fi8_cashflow_forecast.models import (
    OpeningBalance,
    PayablePlan,
    PaymentHistory,
    ReceivablePlan,
)

_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def mock_dir() -> Path:
    return _ROOT / "data" / "mock"


@pytest.fixture
def synthetic_opening() -> OpeningBalance:
    """🔴 合成期初余额——真实银行余额取数授权未取得（见 config）。"""
    return OpeningBalance(as_of_date="2026-09-07", amount=8_500_000.0, source="synthetic")


@pytest.fixture
def simple_receivables() -> list[ReceivablePlan]:
    return [
        ReceivablePlan("AR-0001", "CUS-001", 1_200_000.0, "2026-09-20", "2026-09", 0, "SO-0031"),
        ReceivablePlan("AR-0002", "CUS-002", 460_000.0, "2026-08-25", "2026-08", 13, "SO-0028"),
    ]


@pytest.fixture
def simple_payables() -> list[PayablePlan]:
    return [
        PayablePlan("AP-0001", "SUP-001", 380_000.0, "2026-09-15", "2026-09", "PO-0102"),
        PayablePlan("AP-0002", "SUP-002", 920_000.0, "2026-10-05", "2026-10", "PO-0110"),
    ]


@pytest.fixture
def simple_history() -> list[PaymentHistory]:
    return [
        PaymentHistory("CUS-001", "AR-9001", "2026-06-20", "2026-06-28", 1_100_000.0),
        PaymentHistory("CUS-001", "AR-9002", "2026-07-20", "2026-07-25", 980_000.0),
        PaymentHistory("CUS-002", "AR-9003", "2026-06-25", "2026-07-30", 450_000.0),
    ]
