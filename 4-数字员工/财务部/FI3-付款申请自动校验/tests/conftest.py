"""FI3 测试夹具。"""
from __future__ import annotations

import sys
from datetime import date
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

from fi3_payment_validation import feed_source
from fi3_payment_validation.holiday_calendar import HolidayCalendar
from fi3_payment_validation.validation_engine import ValidationContext

TODAY = date(2026, 9, 17)   # 夹具基准日；不用机器时钟


@pytest.fixture(scope="session")
def calendar() -> HolidayCalendar:
    return HolidayCalendar.load()


@pytest.fixture
def ctx() -> ValidationContext:
    return feed_source.load_context("mock", today=TODAY)


@pytest.fixture
def requests_by_no():
    return {r.req_no: r for r in feed_source.load_payment_requests()}
