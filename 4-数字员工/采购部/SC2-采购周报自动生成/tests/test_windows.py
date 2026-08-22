"""窗口层单测（spec: sc2-feed-source「周窗口切分口径」）。

对应 tasks 3.1-3.3。核心命题：窗口划分是基准日期的纯函数，**不读当前时刻**——
否则周报不可复算，价值指标「口径一致性」就失去证据。
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from sc2.windows import Window, WindowSet, build_windows, procurement_week, week_of


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


def test_ISO周标签保留为对照():
    """ISO 周号不再是期次标识（见下方采购口径周序），但作为对照必须仍算得出。"""
    ws = build_windows(date(2026, 8, 19))
    assert ws.current.iso_label() == "2026-W34"


# ── 采购口径周序（判例回灌 2026-08-22，design D22/D23）──────────────────────

def test_采购口径周序与ISO在2026年恒差一周():
    """🔴 本次判例回灌的核心命题，也是那五条环比全部对不上的根因。

    姚祖怡 2026-08-21 回件里自算的周行数与我方逐周对不上；实测把我方周号整体
    减 1 后，他的 8 个自算数里有 6 个逐字相等（绝对误差和 1275 → 7）。根因是
    ISO 8601 把「含首个周四的那一周」定为 W1（2026 年即 2025-12-29 起，主体落在
    上一年），而采购从本年首个周一 2026-01-05 起算 W1。
    """
    day = date(2026, 1, 5)
    while day <= date(2026, 12, 21):
        w = week_of(day)
        assert procurement_week(w.start)[1] == w.start.isocalendar().week - 1, \
            f"{w.start} 采购口径与 ISO 之差不是 1 周"
        day += timedelta(days=7)


def test_姚祖怡回件里那几周的采购口径周号():
    """拿他信里逐字写下的周号来钉死映射，而不是只测一条通用公式。"""
    assert Window(date(2026, 6, 29), date(2026, 7, 5)).label() == "2026-W26"
    assert Window(date(2026, 7, 6), date(2026, 7, 12)).label() == "2026-W27"
    assert Window(date(2026, 4, 27), date(2026, 5, 3)).label() == "2026-W17"
    assert Window(date(2026, 5, 25), date(2026, 5, 31)).label() == "2026-W21"


def test_本年首个周一所在周为第一周():
    assert procurement_week(date(2026, 1, 5)) == (2026, 1)     # 2026 首个周一
    assert procurement_week(date(2027, 1, 4)) == (2027, 1)     # 2027 首个周一
    assert procurement_week(date(2025, 1, 6)) == (2025, 1)     # 2025 首个周一


def test_年初残日归上一年末周而非本年第一周():
    """2026-01-01~04 的周一落在 2025-12-29 ⇒ 归 2025 年末周，编号不重叠不留缝。"""
    assert procurement_week(date(2025, 12, 29)) == (2025, 52)
    # 紧接着的下一周才是 2026 年第 1 周——首尾相接，中间没有缝
    assert procurement_week(date(2026, 1, 5)) == (2026, 1)


def test_跨年周序连续不重叠():
    """把 2024-2027 的每个周一都走一遍：周号只会 +1，或在跨年处回到 1。"""
    day = date(2024, 1, 1)                       # 恰为周一
    prev = procurement_week(day)
    day += timedelta(days=7)
    while day <= date(2027, 12, 27):
        cur = procurement_week(day)
        assert (cur == (prev[0], prev[1] + 1)) or (cur == (prev[0] + 1, 1)), \
            f"{day} 周序不连续：{prev} → {cur}"
        prev = cur
        day += timedelta(days=7)


def test_周序函数只接受周一():
    """防御式：传进来一个非周一，说明调用方算错了窗口，宁可报错也不悄悄给个数。"""
    with pytest.raises(ValueError):
        procurement_week(date(2026, 6, 30))      # 周二


def test_期次文本三者齐全():
    """只给一个周号是不够的——两套编号各自自洽、相差整周也不报错。"""
    text = Window(date(2026, 6, 29), date(2026, 7, 5)).label_text()
    assert "2026-W26" in text            # 采购口径
    assert "2026-W27" in text            # ISO 对照
    assert "2026-06-29" in text and "2026-07-05" in text
