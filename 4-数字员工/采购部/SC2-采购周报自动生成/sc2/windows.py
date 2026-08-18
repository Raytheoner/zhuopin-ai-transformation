"""窗口层 —— 基准日期 → 三个自然周窗口（纯函数）。

design D16：三窗口＝本周 W、上周 W-1、**四周前同一自然周 W-4**（非上月整月）。
取 W-4 的理由是 SRM 单次查询跨度硬上限 60 天：整月会让最早边界落到 W-9 附近、
逼近或超过上限，须拆多次查询并撞上 30 秒限流；且「单周 vs 整月」要除以周数换算，
反而多引入一层口径。取 W-4 后整体跨度约 35 天，一次查询即可覆盖三窗口，且三者
同为「一个自然周」，量纲可直接比较。

🔴 本模块 **不读当前时刻**：窗口只由显式传入的基准日期决定。这是「周报可复算」
的前提——同一基准日期在任何时刻、任何机器上必须给出同一划分，否则价值指标里的
「口径一致性」就没有证据可言。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

#: 「上月环比」回溯的周数（design D16，design 审 ②(a) 定）。
MONTH_AGO_WEEKS = 4


@dataclass(frozen=True)
class Window:
    """一个自然周窗口（周一 → 周日，闭区间）。"""

    start: date
    end: date

    def contains(self, day: date) -> bool:
        """`day` 是否落在本窗口内（含首尾）。"""
        return self.start <= day <= self.end

    def iso_label(self) -> str:
        """ISO 周标签，如 ``2026-W34``——周报期次标识，跨年不回绕。"""
        iso = self.start.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"

    def as_text(self) -> str:
        """人可读的起止范围，供周报「可追溯标注」使用。"""
        return f"{self.start.isoformat()} ~ {self.end.isoformat()}"


@dataclass(frozen=True)
class WindowSet:
    """一期周报涉及的三个窗口。

    `base` 保留**实际传入的基准日期**（而非推导出的周一）——周报的「基准日期」
    标注取它，使读者能看出这份报表是按哪天生成的；窗口起止另有 `window_text`
    呈现，两者不互相替代。
    """

    current: Window
    previous: Window
    month_ago: Window
    base: date | None = None

    def overall_range(self) -> tuple[date, date]:
        """三窗口的整体覆盖区间——取数层据此**一次**向 SRM 发查询。"""
        return self.month_ago.start, self.current.end

    def span_days(self) -> int:
        """整体跨度天数（含首尾）。用于对照 SRM 的 60 天硬上限。"""
        lo, hi = self.overall_range()
        return (hi - lo).days


def week_of(day: date) -> Window:
    """`day` 所属的自然周（周一 → 周日）。"""
    monday = day - timedelta(days=day.weekday())
    return Window(start=monday, end=monday + timedelta(days=6))


def build_windows(base: date) -> WindowSet:
    """由基准日期构造三窗口。

    `base` 落在周内哪一天不影响结果——窗口按自然周对齐，故周一与周日给出同一组窗口。
    """
    current = week_of(base)
    return WindowSet(
        current=current,
        previous=Window(current.start - timedelta(days=7),
                        current.end - timedelta(days=7)),
        month_ago=Window(current.start - timedelta(weeks=MONTH_AGO_WEEKS),
                         current.end - timedelta(weeks=MONTH_AGO_WEEKS)),
        base=base,
    )
