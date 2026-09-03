"""FI9 测试夹具（骨架期）。"""
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

from fi9_rd_cost.models import CostEntry, LaborRecord, RdProject

_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def mock_dir() -> Path:
    return _ROOT / "data" / "mock"


@pytest.fixture
def simple_projects() -> list[RdProject]:
    return [
        RdProject("RD-2026-001", "示例 ECU 平台预研", "2026-01-05", "", "在研"),
        RdProject("RD-2026-002", "示例控制器软件迭代", "2026-03-01", "", "在研"),
    ]


@pytest.fixture
def simple_costs() -> list[CostEntry]:
    return [
        CostEntry("RD-2026-001", "CE-0001", "材料", 86000.0, "2026-08",
                  "研发支出-材料", invoice_no="00000000000101"),
        CostEntry("RD-2026-001", "CE-0002", "制造费用", 24000.0, "2026-08", "研发支出-制造费用"),
        CostEntry("RD-2026-002", "CE-0003", "材料", 41000.0, "2026-08",
                  "研发支出-材料", invoice_no="00000000000102"),
    ]


@pytest.fixture
def synthetic_labor() -> list[LaborRecord]:
    """🔴 合成工时——工时系统是否存在都未核实（见 config）。"""
    return [
        LaborRecord("RD-2026-001", "EMP-001", "2026-08", 152.0, "synthetic"),
        LaborRecord("RD-2026-002", "EMP-002", "2026-08", 88.0, "synthetic"),
    ]
