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


def _first_monday(year: int) -> date:
    """某年的第一个周一。采购口径周序以它为第 1 周的起点。"""
    jan1 = date(year, 1, 1)
    return jan1 + timedelta(days=(-jan1.weekday()) % 7)


def procurement_week(monday: date) -> tuple[int, int]:
    """采购口径周序（design D22/D23）——返回 ``(归属年, 周号)``。

    **定义**：本年第一个完整周（＝本年首个周一所在的那一周）为第 1 周；某周的归属年
    取**该周周一所在的年**，年初那段周一落在上一年的残日归上一年的末周。

    🔴 **为什么不能用 ISO 周号**（2026-08-22 实测坐实，本函数即由此而生）：ISO 8601 把
    「含首个周四的那一周」定为 W1 —— 2026 年那一周是 **2025-12-29 ~ 2026-01-04**，
    主体落在上一年；而采购（与国内 ERP／Excel 惯例）从本年首个周一 **2026-01-05** 起
    算 W1。于是 **2026 全年 ISO 周号恒比采购口径大 1**。

    姚祖怡 2026-08-21 判例批改回件里五条环比与我方全部对不上，根因就是这一周之差：
    我方叫 W27 的那一周（2026-06-29 ~ 07-05），采购叫 W26。实测中把我方周号整体减 1
    后，他自算的 8 个周行数里有 6 个逐字相等（此前误差和 1275 → 7）。

    🔑 **这个错误此前能一直活着，是因为它不产生任何信号**：两套编号各自自洽、都不越界、
    都不报错，只是指的不是同一周——直到有人拿自己的数来对。故周报此后**同时呈现**两套
    周号与起止日期（`Window.label_text`），使分歧一眼可见，不必再等人对数。
    """
    if monday.weekday() != 0:                    # 防御：本函数只接受周一
        raise ValueError(f"procurement_week 只接受周一，收到 {monday}（周{monday.weekday() + 1}）")
    # 归属年即周一所在年——因此「1 月 1~3 日这几天算上一年末周」是自动成立的：
    # 它们的周一落在上一年，`monday.year` 本身就是上一年，无需额外分支。
    year = monday.year
    return year, (monday - _first_monday(year)).days // 7 + 1


@dataclass(frozen=True)
class Window:
    """一个自然周窗口（周一 → 周日，闭区间）。"""

    start: date
    end: date

    def contains(self, day: date) -> bool:
        """`day` 是否落在本窗口内（含首尾）。"""
        return self.start <= day <= self.end

    def iso_label(self) -> str:
        """ISO 周标签，如 ``2026-W34``。

        🔴 **2026-08-22 起它不再是周报的期次标识**——期次改用 `label()`（采购口径）。
        本方法保留为**对照信息**：周报同时呈现两套周号，使编号口径分歧一眼可见。
        """
        iso = self.start.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"

    def label(self) -> str:
        """采购口径周标签，如 ``2026-W26``——**周报期次标识**（design D22）。

        与 `iso_label()` 的差别见 `procurement_week` 的说明：2026 年两者恒差 1 周。
        """
        year, week = procurement_week(self.start)
        return f"{year}-W{week:02d}"

    def label_text(self) -> str:
        """期次的完整可读形式：采购口径周号 ＋ ISO 对照 ＋ 起止日期。

        **三者必须一起出现**：只给一个周号时，两套编号各自自洽、相差整周也不报错，
        读者无从判断自己看的是不是同一周——这正是 2026-08-21 判例回件里五条环比
        全部对不上的成因。
        """
        return f"{self.label()}（采购口径；ISO {self.iso_label()}；{self.as_text()}）"

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
