"""FI2 测试夹具（v3 口径修正 2026-07-09）。"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def mock_dir() -> Path:
    return _ROOT / "data" / "mock"


@pytest.fixture
def golden_dir() -> Path:
    return _ROOT / "data" / "golden"


@pytest.fixture
def cfg():
    """R1/R5/R7 定稿真值阈值的测试副本（与 config 默认一致，可在用例内改）。"""
    return SimpleNamespace(
        QTY_TOLERANCE_PCT=0.0,
        QTY_TOLERANCE_ABS=0.0,
        AMOUNT_TAIL_TOLERANCE=0.5,
        UNTAXED_AMOUNT_TOLERANCE_PCT=0.005,
        AP_LEVEL_AMOUNT_TOLERANCE=0.5,
        L2_GATE_ABS_THRESHOLD=1.0,
        AP_PO_PRICE_TOLERANCE_PCT=0.02,
        RULE_VERSION="fi2-v3-tangyanping-2026-07-10",
        DATA_SOURCE_DEFAULT="mock",
        U9C_FI_NOT_READY="U9C 财务接口未开放（测试夹具）",
    )
