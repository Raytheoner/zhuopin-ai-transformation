"""窗口层单测（spec: sc2-feed-source「周窗口切分口径」）。

对应 tasks 3.1-3.3。核心命题：窗口划分是基准日期的纯函数，**不读当前时刻**——
否则周报不可复算，价值指标「口径一致性」就失去证据。
"""
from __future__ import annotations

from datetime import date

import pytest

from sc2.windows import Window, WindowSet, build_windows


def test_三窗口为本周_上周_四周前同期周():
    """D16（design 审 ②(a) 定）：上月环比取 W-4 同期周，非上月整月。"""
    ws = build_windows(date(2026, 8, 19))          # 周三
    assert ws.current.start == date(2026, 8, 17)   # 本周一
    assert ws.current.end == date(2026, 8, 23)     # 本周日
    assert ws.previous.start == date(2026, 8, 10)
    assert ws.previous.end == date(2026, 8, 16)
    assert ws.month_ago.start == date(2026, 7, 20)  # W-4
    assert ws.month_ago.end == date(2026, 7, 26)


def test_基准日期落在周一与周日给出同一本周窗口():
    """窗口按自然周对齐，基准日在周内任一天结果相同。"""
    mon = build_windows(date(2026, 8, 17))
    sun = build_windows(date(2026, 8, 23))
    assert mon.current == sun.current
    assert mon.month_ago == sun.month_ago


def test_同基准日期重复调用结果一致():
    """tasks 3.3：可复算。"""
    a = build_windows(date(2026, 8, 19))
    b = build_windows(date(2026, 8, 19))
    assert a == b


def test_不读当前时刻():
    """spec：MUST NOT 依赖运行时当前时刻。

    以 datetime 模块被替换为不可用也应正常工作——这里用一个足够久远的历史日期，
    若实现里混入了 today() 之类的调用，窗口就会偏到当下，断言随即失败。
    """
    ws = build_windows(date(2019, 1, 9))
    assert ws.current.start == date(2019, 1, 7)
    assert ws.current.end == date(2019, 1, 13)


@pytest.mark.parametrize("base", [date(2026, 12, 31), date(2027, 1, 1), date(2027, 1, 4)])
def test_跨年周边界连续且不重叠(base):
    """spec：跨年不得出现窗口缺口或重叠。"""
    ws = build_windows(base)
    for w in (ws.current, ws.previous, ws.month_ago):
        assert (w.end - w.start).days == 6
        assert w.start.weekday() == 0
        assert w.end.weekday() == 6
    # 相邻窗口首尾相接，不重叠不留缝
    assert (ws.current.start - ws.previous.end).days == 1


def test_三窗口合计跨度不超过SRM六十天上限():
    """D16 的成立理由本身要被测到：整体跨度 ≤60 天，一次 SRM 查询即可覆盖。"""
    ws = build_windows(date(2026, 8, 19))
    span = (ws.current.end - ws.month_ago.start).days
    assert span <= 60, f"三窗口跨度 {span} 天超过 SRM 单次查询 60 天硬上限"


def test_窗口可判定日期是否落入其中():
    w = Window(date(2026, 8, 17), date(2026, 8, 23))
    assert w.contains(date(2026, 8, 17))
    assert w.contains(date(2026, 8, 23))
    assert not w.contains(date(2026, 8, 16))
    assert not w.contains(date(2026, 8, 24))


def test_窗口集合给出整体取数区间():
    """取数层按这个区间向 SRM 发一次查询。"""
    ws: WindowSet = build_windows(date(2026, 8, 19))
    lo, hi = ws.overall_range()
    assert lo == ws.month_ago.start
    assert hi == ws.current.end


def test_ISO周标签():
    """周报期次标识用 ISO 周，跨年时不回绕。"""
    ws = build_windows(date(2026, 8, 19))
    assert ws.current.iso_label() == "2026-W34"
