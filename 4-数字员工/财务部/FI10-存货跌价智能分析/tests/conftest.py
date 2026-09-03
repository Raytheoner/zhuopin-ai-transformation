"""FI10 测试夹具（骨架期）。"""
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

from fi10_inventory_writedown.models import (
    BomUsage,
    InTransitPo,
    InventoryAging,
    OemProjectPhase,
)

_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def mock_dir() -> Path:
    return _ROOT / "data" / "mock"


@pytest.fixture
def simple_aging() -> list[InventoryAging]:
    return [
        InventoryAging("MAT-001", "示例芯片 A", "B2025-11", 1200, 38.50, 296, "原料库", "2026-09-03"),
        InventoryAging("MAT-002", "示例电容 B", "B2026-05", 8000, 0.42, 121, "原料库", "2026-09-03"),
        InventoryAging("MAT-003", "示例连接器 C", "B2024-09", 300, 12.80, 719, "原料库", "2026-09-03"),
    ]


@pytest.fixture
def simple_in_transit() -> list[InTransitPo]:
    return [
        InTransitPo("PO-0201", "MAT-001", 2000, 500, 37.90, "2026-09-25"),
        InTransitPo("PO-0202", "MAT-003", 1000, 0, 12.60, "2026-10-10"),
    ]


@pytest.fixture
def simple_bom_usage() -> list[BomUsage]:
    return [
        BomUsage("MAT-001", "FIN-001", 2.0, True),
        BomUsage("MAT-003", "FIN-009", 1.0, False),   # 机型已停产
    ]


@pytest.fixture
def simple_oem_phases() -> list[OemProjectPhase]:
    """🔴 合成 OEM 项目数据。客户名为占位，不对应任何真实 OEM 项目。"""
    return [
        OemProjectPhase("PRJ-A", "OEM-占位甲", "量产", ["MAT-001"], "2026-03-01"),
        OemProjectPhase("PRJ-B", "OEM-占位乙", "终止", ["MAT-003"], "2026-06-30"),
    ]
