"""FI1 测试夹具。"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from zhuopin_platform.shared_tools.models import BomRow

from fi1.models import MaterialFeed, ProductionOutput

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
        L2_SHORTAGE_PCT=0.03,
        L2_OVERLOSS_PCT=0.02,
        RULE_VERSION="fi1-temp-2026-06-29",
        DATA_SOURCE_DEFAULT="mock",
        U9C_MO_NOT_READY="U9C MO/领料 CommonEntity 外网 404",
    )


@pytest.fixture
def simple_bom() -> list[BomRow]:
    """C001 用于 F001(用量2)+F002(用量3)；C002 仅 F001(用量1)。"""
    return [
        BomRow("F001", "C001", "电阻", 1, 2, 0.05, "PCS"),
        BomRow("F001", "C002", "电容", 1, 1, 0.02, "PCS"),
        BomRow("F002", "C001", "电阻", 1, 3, 0.05, "PCS"),
    ]


@pytest.fixture
def simple_outputs() -> list[ProductionOutput]:
    return [
        ProductionOutput("F001", "成品A", 100, "2026-08"),
        ProductionOutput("F002", "成品B", 50, "2026-08"),
    ]


@pytest.fixture
def simple_feeds() -> list[MaterialFeed]:
    return [
        MaterialFeed("C001", "电阻", 360, "PCS", "2026-08"),
        MaterialFeed("C002", "电容", 103, "PCS", "2026-08"),
    ]
