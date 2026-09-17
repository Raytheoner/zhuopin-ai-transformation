"""节假日日历 —— FI3-6 付款日期顺延的唯一权威源。

数据件：`data/holidays/holiday_calendar.csv`（由 `scripts/build_holiday_calendar.py` 从唐燕萍
2026-08-22 交付的 745 行 xlsx 原样搬运；覆盖 2026-01-01 ～ 2028-01-15）。

三条口径（就绪包 §二.2，propose 时照抄进 design 的正本）：
  1. 唯一权威源＝上述 745 行表；**旧 33 天表已作废**，本模块与代码里不得再出现「2026 全年 33 天」口径。
  2. 工作日判定＝**直查 `是否工作日` 列，不自行推导**（实测四格自洽：工作日 495＋调休上班 17＝是 512；
     节假日 61＋周末 172＝否 233）。
  3. 🔴 覆盖上界 2028-01-15 是一条**显式的边界失败**：任何落在覆盖区间之外的日期一律
     `CalendarOutOfRangeError`，**不得静默外推、不得回落到「按自然日算」**。让机器在那一天替我们喊出来。
"""
from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

DEFAULT_CALENDAR = Path(__file__).resolve().parent.parent / "data" / "holidays" / "holiday_calendar.csv"


class CalendarOutOfRangeError(RuntimeError):
    """日期落在节假日日历覆盖区间之外（fail-loud，不外推）。"""


class HolidayCalendar:
    def __init__(self, workday_by_date: dict[date, bool]):
        if not workday_by_date:
            raise ValueError("节假日日历为空——空表不是「全是工作日」，此处不放行")
        self._map = workday_by_date
        self.first = min(workday_by_date)
        self.last = max(workday_by_date)

    @classmethod
    def load(cls, path: Path | str = DEFAULT_CALENDAR) -> "HolidayCalendar":
        mapping: dict[date, bool] = {}
        with Path(path).open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                flag = row["是否工作日"].strip()
                if flag not in ("是", "否"):
                    raise ValueError(f"节假日日历 {row['日期']} 的 `是否工作日`={flag!r} 不是 是/否，拒绝加载")
                mapping[date.fromisoformat(row["日期"])] = flag == "是"
        return cls(mapping)

    def __len__(self) -> int:
        return len(self._map)

    def _require_in_range(self, d: date) -> None:
        if d < self.first or d > self.last:
            raise CalendarOutOfRangeError(
                f"日期 {d.isoformat()} 超出节假日日历覆盖区间 "
                f"{self.first.isoformat()}～{self.last.isoformat()}。"
                f"不得按自然日外推——请向财务侧索取新年度日历（唐燕萍，年度更新由李姣龙执行）。"
            )

    def is_workday(self, d: date) -> bool:
        self._require_in_range(d)
        return self._map[d]

    def roll_to_workday(self, d: date) -> date:
        """落节假日顺延至下一工作日（R6）；本身是工作日则原样返回。"""
        cur = d
        while not self.is_workday(cur):
            cur += timedelta(days=1)
        return cur

    def add_workdays(self, d: date, n: int) -> date:
        """自 d 起（不含 d）数 n 个工作日。用于 R7「7 个工作日补齐」／R5「≤15 工作日补签」。"""
        if n < 0:
            raise ValueError("工作日数不得为负")
        cur = d
        remaining = n
        while remaining > 0:
            cur += timedelta(days=1)
            if self.is_workday(cur):
                remaining -= 1
        return cur
