"""FI2 测试夹具（v3 口径修正 2026-07-09）。"""
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
