"""FI6 测试夹具（骨架期）。"""
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

from fi6_anomaly_detect.models import HistoryBaseline, PartyProfile, Transaction

_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def mock_dir() -> Path:
    return _ROOT / "data" / "mock"


@pytest.fixture
def simple_txns() -> list[Transaction]:
    return [
        Transaction("TX-0001", "AP", "SUP-001", "应付账款-材料", 128000.0, "2026-09-01", "2026-09"),
        Transaction("TX-0002", "AP", "SUP-001", "应付账款-材料", 131500.0, "2026-09-02", "2026-09"),
        Transaction("TX-0003", "AR", "CUS-001", "应收账款-整车", 980000.0, "2026-09-02", "2026-09"),
    ]


@pytest.fixture
def simple_parties() -> list[PartyProfile]:
    return [
        PartyProfile("SUP-001", "示例供应商甲", "供应商", "91000000MA0000001X", "示例市"),
        PartyProfile("CUS-001", "示例客户乙", "客户", "91000000MA0000002X", "示例市"),
    ]


@pytest.fixture
def simple_baseline() -> list[HistoryBaseline]:
    return [
        HistoryBaseline("SUP-001", "应付账款-材料", "AP", 12, 125000.0, 124000.0, 9000.0, 2.5),
        HistoryBaseline("CUS-001", "应收账款-整车", "AR", 12, 910000.0, 905000.0, 48000.0, 1.2),
    ]
