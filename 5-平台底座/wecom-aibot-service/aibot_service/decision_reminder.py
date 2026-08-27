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

━━━ 🔴 **判据关不掉（队列 §四 #47／#124 实证，`OP-0828-B` 修）** ━━━

**缺陷原样**：本模块判"该不该提醒"只看**截止列**——`✅` 在不在、日期过没过。
而队列行守「历史记录不追改」，一行处置完了是**在行尾追加结论、原字样不动**
⇒ 只要截止列那个日期落在过去、又没人补上 `✅`，**这一行会被永远报下去**。

**2026-08-28 对真实队列的只读实测（今天 §四 落进"已过截止"的共 6 条）**：
- `#47`——事项列末句「本行处置完毕」，截止列写的是 `**已收口 2026-08-03**`
  （**已经收口了，只是没写那个 ✅**）⇒ 🔴 **纯误报**；
- `#124`——截止列开头就是「🔴 **不设默认生效**……**不卡时间**」，那里出现的
  `2026-08-26` 是**登记日期**、不是截止日期，被 `_first_full_date` 当成截止
  ⇒ 🔴 **另一种形状的误报：它压根没有截止日期**；
- `#58`／`#59`／`#103`／`#132`——**是真的**（`#103` 事项列虽以 `✅ 已拍板并执行`
  开头，但同一格里写着「🔴 **未闭合：转态动作本身尚未执行**……须 Shao Peishen
  定转态形态（三选一）」）。

🔑 **`#103` 这一条最要紧**：它长得**特别像**误报——开头就是 ✅、还写着「本项到
此闭环」。**靠读事项列里的中文措辞去自动关闭，第一个被误杀的就是它**，而它
是一个真的、没人答的三选一。这正是本模块 docstring 下方"只看第 4 列"那条
铁律的第二个活样本（第一个是 `#38`）。

**修法＝指纹确认，与 `工具-未闭合产出扫描.py::--ack-form1`／`工具-落库sweep.py::
cmd_ack_stale_change` 同族，复用其形态而不是另造一套**（`OP-0827-G` 已在形态 1
上比过三条路子，理由不重述，见那份 docstring）。落到本模块：

- `--ack-item <KEY> --note <依据>` 记一次「我核过了，这一项确已闭环」；
- 指纹**只盖本模块真正据以判定的那一格**——§四 是**截止列**，§一 是**状态列**
  （🔴 **不盖整行**：§四 事项列一天被追加三五段是常态，盖整行等于每追加一句
  无关的话就把已核实的重新捅红一次，那正是本次要治的病换个方向再犯一遍）；
- 语义因此正好是「**我在这一格是这个样子的时候核过它**」：截止列被改写
  （补了新截止、登记了新决策）⇒ 指纹变 ⇒ **自动重新告警**；
- `--note` 不得为空、算不出指纹拒绝记录（两条都抄 `--ack-stale-change`）。

⚠️ **它不是"机制守"，如实说清楚**：ack 这一步仍要人去跑一条命令。它比"在行
里补个 ✅"强的只有三点——① 确认带判定依据且落在机器读得到的地方；② 指纹会
自己失效，确认不会烂在那里；③ 提醒正文每轮把关掉它的那条命令原样打出来，
**告警自己就是那份操作说明**。不夸大成"已机制化"。

⚠️ **一处已知代价**：ack 不会替谁去补那个 `✅`。被 ack 的行在**队列里看起来
仍是未闭合的**——本模块只负责"别再拿它烦人"，"把 `✅` 补上"仍是人的活。

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
import hashlib
import json
import re
import warnings
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from zhuopin_platform.audit import AuditEvent
from zhuopin_platform.shared_tools.queue_table import SECTION_COLUMN_COUNTS

SECTION_FOUR_HEADING = "## 四、"
SECTION_ONE_HEADING = "## 一、"
_NEXT_HEADING = "\n## "

# 第 1 次候选出现即提醒（0 天等待）；第 2 次至少间隔 3 天；第 3 次起每次
# 至少间隔 7 天（"之后每周一次"）——索引越界时回落最后一档。
ESCALATION_INTERVALS_DAYS: tuple[int, ...] = (0, 3, 7)
DEFAULT_PRIORITY_PENDING_MIN_AGE_DAYS = 3
DEFAULT_STATE_REL = "reports/decision_reminder_state.json"
#: 指纹确认落盘位置（`OP-0828-B`）。与 `reports/` 下其余状态文件同归属——
#: 本机状态、`.gitignore` 覆盖、不入库，同 `sweep-stale-change-ack.json`。
DEFAULT_ACK_REL = "reports/decision_reminder_ack.json"

_FULL_DATE_RE = re.compile(r"20\d{2}-\d{2}-\d{2}")
_MMDD_RE = re.compile(r"(?<!\d)(\d{2})-(\d{2})(?!\d)")
_PRIORITY_RE = re.compile(r"\bP[01]\b")
# 队列 #308（2026-08-09，决策点 4）：§一 状态列开头机器可读字段——本文件
# 独立实现一份解析（同本项目"跨文件不 import 同一份判据"既有惯例，见
# 编辑锁/sweep 两处同名常量的注释）。
_STATUS_FIELD_RE = re.compile(
    r"^\[S:(done|open|partial|hold|blocked|timed=\d{4}-\d{2}-\d{2})\]"
    r"(?:\[D:(机|业)\])?"
)
_STATUS_LEADING_STRIP_CHARS = "* \t　"


def _parse_status_domain_fields(status_cell: str) -> tuple[str | None, str | None, str]:
    stripped = status_cell.lstrip(_STATUS_LEADING_STRIP_CHARS)
    m = _STATUS_FIELD_RE.match(stripped)
    if not m:
        return None, None, status_cell
    return m.group(1), m.group(2), stripped[m.end():]


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
    status_cell: str = ""  # 指纹判据格（`OP-0828-B`），见 `item_fingerprint`


@dataclass
class ReminderItem:
    key: str  # 如 "§四#38" / "§一#171"
    section: str  # "§四" | "§一"
    row_id: str
    reason: str  # "新增" | "已过截止" | "待领超期"
    summary: str
    fingerprint: str = ""  # 判据格内容指纹（`OP-0828-B`），见 `item_fingerprint`


@dataclass
class SuppressedItem:
    """被指纹确认压住、本轮不提醒的项——**必须回显条数**，见 `format_digest_message`。"""

    key: str
    fingerprint: str
    note: str = ""
    acked_at: str = ""


@dataclass
class Evaluation:
    """一次判定的完整结果。

    `evaluate_candidates()` 只回 `(items, state)` 两元组（既有调用方与测试都
    按两元组解包，不动）；需要"被压住了几条""哪些确认已对不上行"的调用方
    走 `evaluate()`。
    """

    items: list[ReminderItem] = field(default_factory=list)
    state: dict = field(default_factory=dict)
    suppressed: list[SuppressedItem] = field(default_factory=list)
    stale_acks: list[str] = field(default_factory=list)


# —— 指纹确认（`OP-0828-B`，同族＝`工具-未闭合产出扫描.py::--ack-form1`）——


def item_fingerprint(judging_cell: str) -> str:
    """确认指纹 ＝ **本模块据以判定的那一格**的内容哈希。

    🔴 **只盖判据格，不盖整行**，这一条决定了这个机制会不会退化成噪音：
    §四 的事项列是叙事载体，一天被追加三五段是常态；指纹若盖整行，每追加
    一句无关的话就把已核实的重新捅红一次——**那正是本次要治的病换个方向
    再犯一遍**（同 `工具-未闭合产出扫描.py::form1_fingerprint` 的取舍）。

    哪一格是"判据格"：
    - **§四 ⇒ 截止列**——`is_closed`（有没有 ✅）与 `deadline_date`（哪天到期）
      全部只从这一格算，别处一个字都不看；
    - **§一 ⇒ 状态列**——`[S:open]` 与 `P0/P1` 全部只从这一格算。

    ⚠️ **已知盲区，如实写在这里**：若有人**只往事项列追加一个新决策点、
    却不动截止列**，指纹不变 ⇒ 该行仍被压住。**这不是可以糊过去的**——它的
    正解是「新决策点要么另起一行、要么把截止列改成新的截止日期」，那本来
    就是 §四 的书写约定（截止列承载该行的处置结论）。本机制**刻意不去读
    事项列来兜这个底**：读它就得猜中文，而 `#103` 已经证明猜中文的第一个
    受害者恰恰是真的未闭合项。
    """
    return hashlib.sha256(judging_cell.encode("utf-8")).hexdigest()[:16]


def default_acks() -> dict:
    return {}


def load_acks(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_acks()
    return data if isinstance(data, dict) else default_acks()


def save_acks(path: Path, acks: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(acks, ensure_ascii=False, indent=2), encoding="utf-8")


def _now_utc_str() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def record_ack(
    acks: dict, key: str, *, fingerprint: str, note: str, now: str | None = None,
) -> dict:
    """记一条确认（纯函数，落盘交调用方）。`note` 为空即拒——空确认等于没
    确认，还会伪装成已核（抄 `--ack-stale-change` 的既有强制）。"""
    if not note.strip():
        raise ValueError("--note 不能为空：须写明本次核的是什么、凭什么核的。")
    updated = dict(acks)
    updated[key] = {
        "fingerprint": fingerprint,
        "acked_at": now or _now_utc_str(),
        "note": note,
    }
    return updated


def ackable_state(queue_text: str, today: date) -> dict:
    """给 `--ack-item` 用的评估状态：**把所有行都当成"见过的"**。

    🔴 **为什么不能直接用空状态**：空状态下每一行都算"新增"⇒ 全部进候选 ⇒
    一个**截止日期还在未来**的行也能被 ack。那之后截止日到了、而截止列一个字
    没改 ⇒ 指纹不变 ⇒ **它永远不会响**。那正是「永久白名单」，本机制的整个
    要点就是不能有它。

    把 `seen_*` 填满后，候选恰好只剩「**已过截止**」与「**待领超期**」——也就是
    **此刻真的在烦人的那些**。只有这些才允许被 ack。

    `escalation` 刻意留空：升级间隔管的是"今天出不出声"，与"这一项该不该被
    确认"无关；用生产 escalation 会让一条明明在超期、只是今天不到期的行
    ack 不了。
    """
    four = parse_section_four_rows(queue_text)
    one = parse_priority_pending_rows(queue_text, today)
    return {
        "seen_section_four_ids": [r.row_id for r in four],
        "seen_priority_pending_ids": [r.row_id for r in one],
        "escalation": {},
    }


def _ack_matches(acks: dict, key: str, fingerprint: str) -> Optional[dict]:
    """「已确认 ＋ 指纹未变」**双条件**才算命中（同 `--ack-form1` 语义）。"""
    entry = acks.get(key)
    if isinstance(entry, dict) and entry.get("fingerprint") == fingerprint:
        return entry
    return None


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
        if len(cells) != SECTION_COLUMN_COUNTS["四"]:
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
    """解析队列 §一"任务看板"里状态列为待领（机器字段 `open`，队列 #308
    决策点 4 起改读字段）且带 P0/P1 标记的行
    （# | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记）。
    `today` 用于消解"登记"列 MM-DD 缺年份的歧义（见 `_first_mmdd_date`），
    纯函数不读系统时钟，保证可测。

    只认 `open`（不含 `partial`——在办中已有人认领，无需"待领"提醒；也不含
    `blocked`/`timed=`/`hold`/`done`，这正是队列 #308 E1 子项要根治的
    形态：`timed=` 只是自然语言写了触发日期，旧的"待领"子串判据会误判
    为立即待领，机器字段落地后天然区分）。字段缺失/非法时（未来绕锁写入
    等场景）非静默降级——发出 `RuntimeWarning` 并回退旧的"待领"子串判据，
    不静默改变行为。"""
    rows = []
    for cells in _parse_table_rows(queue_text, SECTION_ONE_HEADING):
        if len(cells) != SECTION_COLUMN_COUNTS["一"]:
            continue  # 列数不符的行不纳入判定，交人工核查（如队列 #164 修复前的六行）
        row_id, task_cell, _owner, _input, _output, status_cell, _touch, registered_cell = cells
        status_value, _, _ = _parse_status_domain_fields(status_cell)
        if status_value is None:
            warnings.warn(
                f"§一 #{row_id} 状态字段缺失/非法，已回退旧「待领」子串判据（非静默降级，见队列 #308）",
                RuntimeWarning, stacklevel=2,
            )
            if "待领" not in status_cell:
                continue
        elif status_value != "open":
            continue
        m = _PRIORITY_RE.search(status_cell)
        if not m:
            continue
        rows.append(PriorityPendingRow(
            row_id=row_id, task_cell=task_cell, priority=m.group(0),
            registered_date=_first_mmdd_date(registered_cell, today),
            status_cell=status_cell,
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
    acks: Optional[dict] = None,
) -> tuple[list[ReminderItem], dict]:
    """`evaluate()` 的两元组包装（既有调用方按 `(items, state)` 解包，不动）。"""
    result = evaluate(queue_text, today, state, min_priority_pending_age_days, acks)
    return result.items, result.state


def evaluate(
    queue_text: str, today: date, state: dict,
    min_priority_pending_age_days: int = DEFAULT_PRIORITY_PENDING_MIN_AGE_DAYS,
    acks: Optional[dict] = None,
) -> Evaluation:
    """核心判定（纯函数，不做任何 I/O）：解析队列 → 算出"新增"/"超期"候选
    → 剔掉已被指纹确认压住的 → 按各自的升级间隔决定本次是否真的要提醒。
    调用方负责落盘 `state`（`save_state`）与实际发送。

    **被 ack 压住的项刻意不进 `escalation`**：它的升级计数就此清零，指纹一旦
    失效（判据格被改写）便从"首次候选"重新起算 ⇒ **立即提醒一次**，而不是
    接着上一轮的 1/3/7 天节奏慢慢来。这是 fail-loud 方向的选择。
    """
    acks = acks or {}
    suppressed: list[SuppressedItem] = []
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
        fingerprint = item_fingerprint(row.deadline_cell)
        acked = _ack_matches(acks, key, fingerprint)
        if acked is not None:
            suppressed.append(SuppressedItem(
                key=key, fingerprint=fingerprint,
                note=acked.get("note", ""), acked_at=acked.get("acked_at", ""),
            ))
            continue
        active_keys.add(key)
        entry = escalation.get(key) or {"first_flagged_at": today.isoformat(), "alert_count": 0}
        if not _is_due(entry, today):
            continue
        reason = "新增" if is_new and entry.get("alert_count", 0) == 0 else "已过截止"
        summary = row.item_cell[:80] + ("…" if len(row.item_cell) > 80 else "")
        candidates.append(ReminderItem(key=key, section="§四", row_id=row_id,
                                       reason=reason, summary=summary,
                                       fingerprint=fingerprint))
        entry["alert_count"] = int(entry.get("alert_count") or 0) + 1
        entry["last_alerted_at"] = today.isoformat()
        escalation[key] = entry

    for row_id, row in priority_ids.items():
        is_new = row_id not in seen_priority
        is_stale = row_id in stale_priority
        if not (is_new or is_stale):
            continue
        key = f"§一#{row_id}"
        fingerprint = item_fingerprint(row.status_cell)
        acked = _ack_matches(acks, key, fingerprint)
        if acked is not None:
            suppressed.append(SuppressedItem(
                key=key, fingerprint=fingerprint,
                note=acked.get("note", ""), acked_at=acked.get("acked_at", ""),
            ))
            continue
        active_keys.add(key)
        entry = escalation.get(key) or {"first_flagged_at": today.isoformat(), "alert_count": 0}
        if not _is_due(entry, today):
            continue
        reason = "新增" if is_new and entry.get("alert_count", 0) == 0 else "待领超期"
        summary = row.task_cell[:80] + ("…" if len(row.task_cell) > 80 else "")
        candidates.append(ReminderItem(
            key=key, section="§一", row_id=row_id, reason=f"{reason}（{row.priority}）",
            summary=summary, fingerprint=fingerprint,
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

    # 🔴 确认记录对不上任何现存行时要说出来，不静默留着（同
    # `工具-未闭合产出扫描.py` 的 `stale_acks`）：行可能已关闭、编号可能变了；
    # 一条对不上的确认躺在文件里，下次读的人会以为"那一项已经被核过"——
    # 而它核的是一个已经不存在的东西。
    live = {f"§四#{rid}" for rid in open_ids} | {f"§一#{rid}" for rid in priority_ids}
    stale_acks = sorted(key for key in acks if key not in live)

    return Evaluation(items=candidates, state=new_state,
                      suppressed=suppressed, stale_acks=stale_acks)


ACK_COMMAND_HINT = (
    "python 5-平台底座/wecom-aibot-service/scripts/decision_reminder_check.py "
    "--ack-item '<上面那个 key>' --note '<凭什么判定它已闭环>'"
)


def format_digest_message(
    items: list[ReminderItem],
    suppressed: Optional[list[SuppressedItem]] = None,
    stale_acks: Optional[list[str]] = None,
) -> Optional[str]:
    """提醒正文。

    🔴 **抑制条数与命中数同行回显**（同 `OP-0827-G` 给 sweep 加的那一行）——
    **一个只会变长、从不回显的抑制清单，正是这套告警最该防的"看起来干净"**。
    🔴 **关掉它的那条命令每轮原样打出来**：告警自己就是那份操作说明，收信人
    不必去翻文档才知道"这条明明已经闭环了，怎么让它别再报"。
    """
    suppressed = suppressed or []
    stale_acks = stale_acks or []
    if not items:
        return None
    head = f"📌 队列有 {len(items)} 项需要你留意（新增或超期，非例行提醒）"
    if suppressed:
        head += f"；另有 {len(suppressed)} 项已确认闭环、本轮静默"
    lines = [head + "："]
    for item in items:
        lines.append(f"- {item.key}（{item.reason}）：{item.summary}")
    if stale_acks:
        lines.append(
            f"⚠️ 有 {len(stale_acks)} 条确认已对不上任何现存行（{'、'.join(stale_acks)}）"
            "——那一行可能已关闭或改了编号，确认记录建议清掉。"
        )
    lines.append("详见跨桌任务队列.md 对应小节；本条为自动巡检，非重复轰炸——同一项已按 1/3/7 天间隔去重。")
    lines.append(f"🔕 某一项确已闭环、只是队列里没补 ✅ ⇒ 跑一条命令让它别再报：\n  {ACK_COMMAND_HINT}")
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
