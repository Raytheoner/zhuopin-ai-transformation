"""队列 #379：法定节假日日历「每年更新」提醒——纯逻辑层。

发送/连接 I/O 留在 `scripts/annual_holiday_reminder.py`（同
`decision_reminder_check.py` / `decision_reminder.py` 既有分工：可测的判断
逻辑放模块，网络 I/O 与 CLI 留在脚本），本模块只负责三件可独立测试的事：
① 今天是不是该发送的那天（日期门控＋幂等）；② 前置校验（队列 #380：
出站已知 ∧ 入站白名单，缺一不发）；③ 状态文件的读写与文案渲染。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Mapping

LI_JIAOLONG_USERID = "2025672"  # 队列 #380；纯数字工号，不可从名字推断
TRIGGER_MONTH = 9
TRIGGER_DAY = 1
STATE_REL = Path("reports") / "annual_holiday_reminder_state.json"

DEFAULT_MESSAGE_TEMPLATE = (
    "您好，根据约定，烦请提供 {next_year} 年度节假日日历更新，谢谢！"
    "（本提醒由系统于每年 9 月 1 日自动发送，如已提前提供可忽略）"
)


def is_trigger_day(today: date, *, month: int = TRIGGER_MONTH, day: int = TRIGGER_DAY) -> bool:
    return today.month == month and today.day == day


def already_sent_for_year(state: Mapping, today: date) -> bool:
    return state.get("last_sent_year") == today.year


def should_send(today: date, state: Mapping, *, force: bool = False) -> bool:
    """是否本次该真的发送——**发送前置**（#380 出站/入站校验）不在本函数
    范围内，由调用方在 `should_send` 为真之后另行核验（两者失败模式不同：
    本函数判"是不是该发的日子"，前置校验判"发得出去吗"，混在一起会让
    "日期不对不发"与"日期对了但被 #380 挡住不发"这两种截然不同的情况
    共用同一条日志，排查时分不清是哪一种）。"""
    if force:
        return True
    return is_trigger_day(today) and not already_sent_for_year(state, today)


def next_target_year(today: date) -> int:
    return today.year + 1


def format_reminder_message(next_year: int, *, template: str = DEFAULT_MESSAGE_TEMPLATE) -> str:
    return template.format(next_year=next_year)


@dataclass(frozen=True)
class AdmissionCheck:
    outbound_ok: bool
    inbound_ok: bool

    @property
    def passed(self) -> bool:
        return self.outbound_ok and self.inbound_ok


def check_admission(
    known_recipient_userids: Mapping[str, str],
    is_whitelisted_fn: Callable[[str], bool],
    userid: str = LI_JIAOLONG_USERID,
) -> AdmissionCheck:
    """队列 #380 是本行硬前置——出站已知（`dispatch.KNOWN_RECIPIENT_USERIDS`）
    与入站白名单（`whitelist.is_whitelisted`）均须放行，缺一不可：只出站通
    则消息能发出去、但对方回复会被 fail-closed 静默挡回；只入站通在本场景
    不会发生（入站是出站的超集，见 #380 判据(乙)），一并核验是防御性写法。
    """
    return AdmissionCheck(
        outbound_ok=userid in known_recipient_userids.values(),
        inbound_ok=is_whitelisted_fn(userid),
    )


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(path: Path, state: Mapping) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(state), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
