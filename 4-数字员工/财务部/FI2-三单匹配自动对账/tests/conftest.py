"""FI2 测试夹具。"""
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
    """临时口径阈值的测试副本（与 config 默认一致，可在用例内改）。"""
    return SimpleNamespace(
        QTY_TOLERANCE_PCT=0.02,
        QTY_TOLERANCE_ABS=5,
        AMOUNT_TAIL_TOLERANCE=0.5,
        PO_LEVEL_AMOUNT_TOLERANCE=0.5,
        RULE_VERSION="fi2-temp-2026-07-07",
        DATA_SOURCE_DEFAULT="mock",
        U9C_FI_NOT_READY="U9C 财务接口未开放（测试夹具）",
    )
