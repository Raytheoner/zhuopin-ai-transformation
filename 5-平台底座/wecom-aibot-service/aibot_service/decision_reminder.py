"""需 Shao Peishen 决策项/待领 opener 主动提醒（队列 #172）。

背景：拆件巡逻已能把"需 Shao Peishen 项"自动登进队列 §四（live 转正增项），
值周巡检周一出《本周计划》带 opener，但**两次巡检之间新产生的 §四 项与
高优先待领行，无任何主动推送**——只躺在队列里等人翻，最长可静置到下周一。
本模块补这个缺口，走既有通道（企微机器人私信 `PAUL_USERID`，主通道失败
再走群 webhook 兜底，同 `gap_alert.py`/`queue_git_sync.py` 既有范式）。

**设计红线（吸取 #147 gap_alert 狼来了教训）**：判据必须是"新增"或"超期"，
不得是"存在即提醒"——凡是"一直存在、没有变化"的项，不重复打扰；去重与
升级间隔见 `ESCALATION_INTERVALS_DAYS`。

**两层提醒共用同一套判定，不是两套代码**：
① 事件驱动即时提醒——拆件巡逻收工时调用本模块（`run_check` /
   `scripts/decision_reminder_check.py`），若本轮 §四 新登了行、或 §一
   新增了 P0/P1 待领行，因其"从未见过"（不在 `seen_ids` 里）而在评估时
   进入候选池，首次评估即算"到期"（`ESCALATION_INTERVALS_DAYS[0] == 0`），
   立即触发一条提醒——零延迟。
② 每日超期汇总——独立定时任务（见 `scripts/decision_reminder_check.py`
   注册的计划任务）每日固定时点调用**同一个** `run_check`，此时"新增"
   信号大概率已在上一次调用时报过（`alert_count >= 1`），真正起作用的是
   "超期"判据：§四 已过 `deadline_cell` 里写明日期的开放行、§一 P0/P1
   待领超 `min_priority_pending_age_days` 天——按 1/3/7 天递减升级（见
   `ESCALATION_INTERVALS_DAYS`），同一天内两层都调用也不会重复提醒（同一
   item 当天已提醒过，`_is_due` 判 False）。

**§四"是否已关闭"的判据**（实证，见 2026-07-31 对 #33-#40 八行的逐行核证）：
本表没有独立状态列，但约定俗成地把结论写进"截止"这一列——已解决的行
在"截止"列里带"✅"（如"✅ 已拍板…"/"✅ 已由 Paul…拍板整体销行"），仍
悬而未决的行"截止"列只有日期/建议给结论的措辞、不带"✅"。**只看第 4
列（截止列）本身**，不看整行——"事项"列（第 2 列）里出现的"✅"只说明
"事项描述中提到的某个子问题已解决"，不代表这一整行已结案（#38 即活样本：
事项列开头带✅描述安全项①已收口，但截止列仍写"建议…前给结论"，指向
另一个仍待裁决的子问题②）。
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from zhuopin_platform.audit import AuditEvent

SECTION_FOUR_HEADING = "## 四、"
SECTION_ONE_HEADING = "## 一、"
_NEXT_HEADING = "\n## "

# 第 1 次候选出现即提醒（0 天等待）；第 2 次至少间隔 3 天；第 3 次起每次
# 至少间隔 7 天（"之后每周一次"）——索引越界时回落最后一档。
ESCALATION_INTERVALS_DAYS: tuple[int, ...] = (0, 3, 7)
DEFAULT_PRIORITY_PENDING_MIN_AGE_DAYS = 3
DEFAULT_STATE_REL = "reports/decision_reminder_state.json"

_FULL_DATE_RE = re.compile(r"20\d{2}-\d{2}-\d{2}")
_MMDD_RE = re.compile(r"(?<!\d)(\d{2})-(\d{2})(?!\d)")
_PRIORITY_RE = re.compile(r"\bP[01]\b")


@dataclass
class SectionFourRow:
    row_id: str
    item_cell: str
    waiting_on_cell: str
    deadline_cell: str
    is_closed: bool
    deadline_date: Optional[date]


@dataclass
class PriorityPendingRow:
    row_id: str
    task_cell: str
    priority: str
    registered_date: Optional[date]


@dataclass
class ReminderItem:
    key: str  # 如 "§四#38" / "§一#171"
    section: str  # "§四" | "§一"
    row_id: str
    reason: str  # "新增" | "已过截止" | "待领超期"
    summary: str


def _parse_table_rows(queue_text: str, heading: str) -> list[list[str]]:
    """提取 `heading` 到下一个 `## ` 标题之间的表格数据行（跳过表头/分隔行），
    每行返回原样切分（不 strip 语义、不做列数校验，交调用方按预期列数处理）。
    """
    start = queue_text.find(heading)
    if start == -1:
        return []
    rest = queue_text[start + len(heading):]
    next_heading = rest.find(_NEXT_HEADING)
    section = rest if next_heading == -1 else rest[:next_heading]

    rows: list[list[str]] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not cells:
            continue
        first = cells[0]
        if first in ("#", "") or set(first) <= {"-", " "}:
            continue  # 表头行 / 分隔行
        rows.append(cells)
    return rows


def _first_full_date(text: str) -> Optional[date]:
    m = _FULL_DATE_RE.search(text)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(0), "%Y-%m-%d").date()
    except ValueError:
        return None


def _first_mmdd_date(text: str, today: date) -> Optional[date]:
    """解析形如"07-30"的登记日期——本项目队列全在 2026 年内产生，缺年份
    时默认按 `today.year`；若据此算出的日期反而"晚于今天"（如年初解析到
    12 月的登记行，是上一年度残留），回退用 `today.year - 1`，避免把陈旧
    行误判成"来自未来、尚不足龄"。"""
    m = _MMDD_RE.search(text)
    if not m:
        return None
    month, day = int(m.group(1)), int(m.group(2))
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    try:
        candidate = date(today.year, month, day)
    except ValueError:
        return None
    if candidate > today:
        try:
            candidate = date(today.year - 1, month, day)
        except ValueError:
            return None
    return candidate


def parse_section_four_rows(queue_text: str) -> list[SectionFourRow]:
    """解析队列 §四"需 Shao Peishen 的动作"表格（# | 事项 | 等谁 | 截止）。"""
    rows = []
    for cells in _parse_table_rows(queue_text, SECTION_FOUR_HEADING):
        if len(cells) != 4:
            continue  # 列数不符（如仍含裸竖线）的行不纳入判定，交人工核查
        row_id, item_cell, waiting_on_cell, deadline_cell = cells
        rows.append(SectionFourRow(
            row_id=row_id,
            item_cell=item_cell,
            waiting_on_cell=waiting_on_cell,
            deadline_cell=deadline_cell,
            is_closed="✅" in deadline_cell,
            deadline_date=_first_full_date(deadline_cell),
        ))
    return rows


def parse_priority_pending_rows(queue_text: str, today: date) -> list[PriorityPendingRow]:
    """解析队列 §一"任务看板"里状态列含"待领"且带 P0/P1 标记的行
    （# | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记）。
    `today` 用于消解"登记"列 MM-DD 缺年份的歧义（见 `_first_mmdd_date`），
    纯函数不读系统时钟，保证可测。"""
    rows = []
    for cells in _parse_table_rows(queue_text, SECTION_ONE_HEADING):
        if len(cells) != 8:
            continue  # 列数不符的行不纳入判定，交人工核查（如队列 #164 修复前的六行）
        row_id, task_cell, _owner, _input, _output, status_cell, _touch, registered_cell = cells
        if "待领" not in status_cell:
            continue
        m = _PRIORITY_RE.search(status_cell)
        if not m:
            continue
        rows.append(PriorityPendingRow(
            row_id=row_id, task_cell=task_cell, priority=m.group(0),
            registered_date=_first_mmdd_date(registered_cell, today),
        ))
    return rows


def compute_overdue_section_four_ids(rows: list[SectionFourRow], today: date) -> list[str]:
    return [
        r.row_id for r in rows
        if not r.is_closed and r.deadline_date is not None and r.deadline_date < today
    ]


def compute_stale_priority_pending_ids(
    rows: list[PriorityPendingRow], today: date,
    min_age_days: int = DEFAULT_PRIORITY_PENDING_MIN_AGE_DAYS,
) -> list[str]:
    return [
        r.row_id for r in rows
        if r.registered_date is not None and (today - r.registered_date).days >= min_age_days
    ]


def default_state() -> dict:
    return {"seen_section_four_ids": [], "seen_priority_pending_ids": [], "escalation": {}}


def load_state(path: Path) -> dict:
    if not path.exists():
        return default_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default_state()
    if not isinstance(data, dict):
        return default_state()
    state = default_state()
    state.update({k: v for k, v in data.items() if k in state})
    return state


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _next_interval_days(alert_count: int) -> int:
    if alert_count < len(ESCALATION_INTERVALS_DAYS):
        return ESCALATION_INTERVALS_DAYS[alert_count]
    return ESCALATION_INTERVALS_DAYS[-1]


def _is_due(entry: dict, today: date) -> bool:
    alert_count = int(entry.get("alert_count") or 0)
    if alert_count == 0:
        return True
    last_alerted_at = entry.get("last_alerted_at")
    if not last_alerted_at:
        return True
    try:
        last = datetime.strptime(last_alerted_at, "%Y-%m-%d").date()
    except ValueError:
        return True
    return (today - last).days >= _next_interval_days(alert_count)


def evaluate_candidates(
    queue_text: str, today: date, state: dict,
    min_priority_pending_age_days: int = DEFAULT_PRIORITY_PENDING_MIN_AGE_DAYS,
) -> tuple[list[ReminderItem], dict]:
    """核心判定（纯函数，不做任何 I/O）：解析队列 → 算出"新增"/"超期"候选
    → 按各自的升级间隔决定本次是否真的要提醒 → 返回 (待提醒项, 更新后状态)。
    调用方负责落盘 `state`（`save_state`）与实际发送。
    """
    section_four_rows = parse_section_four_rows(queue_text)
    priority_rows = parse_priority_pending_rows(queue_text, today)

    open_ids = {r.row_id: r for r in section_four_rows if not r.is_closed}
    priority_ids = {r.row_id: r for r in priority_rows}

    seen_four = set(state.get("seen_section_four_ids") or [])
    seen_priority = set(state.get("seen_priority_pending_ids") or [])
    escalation: dict = dict(state.get("escalation") or {})

    overdue_four = set(compute_overdue_section_four_ids(section_four_rows, today))
    stale_priority = set(compute_stale_priority_pending_ids(
        priority_rows, today, min_priority_pending_age_days,
    ))

    candidates: list[ReminderItem] = []
    active_keys: set[str] = set()

    for row_id, row in open_ids.items():
        is_new = row_id not in seen_four
        is_overdue = row_id in overdue_four
        if not (is_new or is_overdue):
            continue
        key = f"§四#{row_id}"
        active_keys.add(key)
        entry = escalation.get(key) or {"first_flagged_at": today.isoformat(), "alert_count": 0}
        if not _is_due(entry, today):
            continue
        reason = "新增" if is_new and entry.get("alert_count", 0) == 0 else "已过截止"
        summary = row.item_cell[:80] + ("…" if len(row.item_cell) > 80 else "")
        candidates.append(ReminderItem(key=key, section="§四", row_id=row_id, reason=reason, summary=summary))
        entry["alert_count"] = int(entry.get("alert_count") or 0) + 1
        entry["last_alerted_at"] = today.isoformat()
        escalation[key] = entry

    for row_id, row in priority_ids.items():
        is_new = row_id not in seen_priority
        is_stale = row_id in stale_priority
        if not (is_new or is_stale):
            continue
        key = f"§一#{row_id}"
        active_keys.add(key)
        entry = escalation.get(key) or {"first_flagged_at": today.isoformat(), "alert_count": 0}
        if not _is_due(entry, today):
            continue
        reason = "新增" if is_new and entry.get("alert_count", 0) == 0 else "待领超期"
        summary = row.task_cell[:80] + ("…" if len(row.task_cell) > 80 else "")
        candidates.append(ReminderItem(
            key=key, section="§一", row_id=row_id, reason=f"{reason}（{row.priority}）", summary=summary,
        ))
        entry["alert_count"] = int(entry.get("alert_count") or 0) + 1
        entry["last_alerted_at"] = today.isoformat()
        escalation[key] = entry

    # 不再是候选（行已关闭/不再 P0/P1 待领）的升级状态清掉，避免陈旧计数
    # 干扰未来一次全新的"首次候选"判定。
    escalation = {k: v for k, v in escalation.items() if k in active_keys}

    new_state = {
        "seen_section_four_ids": sorted(seen_four | set(open_ids)),
        "seen_priority_pending_ids": sorted(seen_priority | set(priority_ids)),
        "escalation": escalation,
    }
    return candidates, new_state


def format_digest_message(items: list[ReminderItem]) -> Optional[str]:
    if not items:
        return None
    lines = [f"📌 队列有 {len(items)} 项需要你留意（新增或超期，非例行提醒）："]
    for item in items:
        lines.append(f"- {item.key}（{item.reason}）：{item.summary}")
    lines.append("详见跨桌任务队列.md 对应小节；本条为自动巡检，非重复轰炸——同一项已按 1/3/7 天间隔去重。")
    return "\n".join(lines)


async def send_decision_reminder(
    connector,
    audit,
    alert_text: str,
    recipient: str,
    *,
    fallback_send=None,
) -> None:
    """发送形状仿 `gap_alert.send_gap_alert`/`queue_git_sync._send_degraded_alert`
    ——主通道（企微智能机器人私信）失败时，若提供 `fallback_send`（同步函数，
    走独立群 webhook 通道），线程池里兜底发一次；全程失败也不向上抛出（告警
    本身不应影响调用方——巡逻收工/每日定时任务——继续正常结束）。
    """
    try:
        await connector.send_markdown(recipient, alert_text)
    except Exception:  # noqa: BLE001
        audit.record(AuditEvent(
            scenario="wecom-aibot", action="decision_reminder_send_failed", evaluator="system",
            automation_level="L1", decision={"sent": False}, data_sources={},
        ))
        if fallback_send is None:
            return
        try:
            await asyncio.to_thread(fallback_send, alert_text)
        except Exception:  # noqa: BLE001
            audit.record(AuditEvent(
                scenario="wecom-aibot", action="decision_reminder_fallback_failed",
                evaluator="system", automation_level="L1",
                decision={"sent": False}, data_sources={},
            ))
        else:
            audit.record(AuditEvent(
                scenario="wecom-aibot", action="decision_reminder_fallback_sent",
                evaluator="system", automation_level="L1",
                decision={"sent": True, "channel": "webhook"}, data_sources={},
            ))
        return
    audit.record(AuditEvent(
        scenario="wecom-aibot", action="decision_reminder_sent", evaluator="system",
        automation_level="L1", decision={"sent": True, "recipient": recipient}, data_sources={},
    ))
