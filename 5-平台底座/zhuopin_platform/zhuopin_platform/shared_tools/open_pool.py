"""「可 Open 池」判定权威实现（队列 #312，2026-09-02 Shao Peishen 裁定
「以看板判据为准」；本模块＝两侧共用的**唯一**判定函数）。

背景：同一个「可 Open 池」概念此前有两套独立实现——企微推送器
`aibot_service/open_pool_reminder.py`（Python）与看板 artifact
`zhuopin-project-status` 的数据层 `0-学习与工具/工具-项目状态卡数据层.ps1`
（PowerShell）。2026-09-02 Cowork `OP-0902-A` 对两份队列真身实跑比对：
推送器 25 条、看板 35 条，**差异双向**（看板独有 11 条全是 `[S:partial]`；
推送器独有 `#439`／`#440` 以 🛑 起首）。本班（`OP-0912-H`）再跑一次：
48 vs 72，差 ＝ partial 29 行 ＋ 🛑 起首 5 行——**漂移随时间放大**。
裁定原文：「**对齐不是抄一遍判据，是让两侧共用同一个判定函数**，否则今天
修完明天照样漂」；🔴 不取「各保留、只加对账告警」——两套数长期并存正是
本项目反复吃亏的「第二份真身」形态。

⇒ 本模块承载判据；Python 侧 `open_pool_reminder.py` 直接 import；
PowerShell 侧 `工具-项目状态卡数据层.ps1` 经 `0-学习与工具/工具-可Open池.py`
（CLI 薄壳）以子进程调本模块取 JSON——**两侧都不再各自持有一份判据**。

**判据（逐条对应看板 `index.html` 第 480 行自述与数据层 ps1 原实现）**：
1. 状态列开头须有 `[S:x][D:y]` 机器字段（队列 #308）。缺 `[S:]` 或缺
   `[D:]` ⇒ `degraded`（看板 `$poolDeg`：字段缺失／无法判定，**单列出来、
   不静默丢弃**）。🔴 缺 `[D:]` 归 degraded 而不是「域未知也入池」：看板
   按 `[D:机/业]` 分组渲染，域为 None 的行会**计入 N 却渲染不出来**——
   数与页面对不上正是最难发现的失效形态；且推送器不猜域（同 `#523`
   「不把缺域行一律计成机」的理由）。
2. `[S:open]` ⇒ 结构性入池；`[S:partial]` ⇒ **默认入池**（语义即「主体做
   完、尾巴挂着」，尾巴本身就是可开工的活——2026-09-02 裁定 ⑴）；
   `done／blocked／hold／timed=` ⇒ 结构性排除（`out`）。
3. 状态列含 `[A:`（assigned，`OP-0830-D` design D1）⇒ `out`，不解析取值。
4. **以 🛑 起首者排除**（2026-09-02 裁定 ⑵：🛑 是明示的「结构性不可动」）。
   🔴 认两列——状态列正文或任务列任一以 🛑 起首即排除：看板判据自述
   「同 `工具-共享文档编辑锁.py::_count_mechanism_wip` 口径」，而该口径已于
   2026-09-11（`OP-0911-N`，design D-B 甲）改为认两列（`#381` 形态：任务列
   「🛑 排队中·暂非可动」、状态列不含 🛑，只认状态列会把自陈「暂非可动」
   的行推成「可开工」）。本班实测生产队列 `#382`／`#448` 即此形态、此前两侧
   都误入池。
5. `[S:partial]` 且状态列开头片段自陈「在办／在建／进行中／建造中」⇒
   `excluded`（看板 `$poolEx`：排除但**单列出来供反查**，不静默丢弃）。
   开头片段＝剥前导 `*`／空白后截到首个 `。`／`——`／`━━━` 之前（同
   `工具-落库sweep.py::_leading_status_segment` 口径）。
6. `[S:partial]` 且开头片段以 ✅ 起首 ⇒ 仍入池，但带 `flag`（「字段＝partial
   但首标记写 ✅，以字段为准」，#308 决策点 1）。
7. 列数不符（裸竖线撑列等）⇒ `skipped`，行号列出来交人工核查。

🔴 **改判据只改这一处**；改后 `open_pool_reminder.py` 与看板自动跟随。
`工具-共享文档编辑锁.py::_mechanism_wip_row_counts`（WIP 计数）与本模块
判据同源但**不是同一件事**（WIP 计 hold、不看 `[A:`），仍各自实现；两者对
🛑 的认列口径须保持一致，见上第 4 条。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from zhuopin_platform.shared_tools.queue_table import (
    iter_queue_paths,
    parse_section_rows,
)

SECTION_ONE_HEADING = "## 一、"
_NEXT_HEADING = "\n## "

# 队列 #308（决策点 4）：§一 状态列开头机器可读字段。与
# `工具-共享文档编辑锁.py::STATUS_FIELD_RE` 同形——该文件按项目惯例不被
# import（中文文件名），故此处保留一份同形正则；`[D:]` 组可选是为了把
# 「缺 [D:]」与「缺 [S:]」区分开来分别报告，不是为了把缺域行放进池。
STATUS_FIELD_RE = re.compile(
    r"^\[S:(done|open|partial|hold|blocked|timed=\d{4}-\d{2}-\d{2})\]"
    r"(?:\[D:(机|业)\])?"
)
STATUS_LEADING_STRIP_CHARS = "* \t　"
POOL_STATUS_VALUES: tuple[str, ...] = ("open", "partial")
ASSIGNED_MARKER = "[A:"
STOP_MARKER = "🛑"
# 看板 ps1 原文：`$LR -match '在办|在建|进行中|建造中'`（partial 例外排除）。
PARTIAL_IN_PROGRESS_RE = re.compile(r"在办|在建|进行中|建造中")
# 看板 ps1 原文：`$LR -match '^\s*✅'`（partial 但首标记写 ✅ ⇒ 入池带 flag）。
_PARTIAL_DONE_MARK_RE = re.compile(r"^\s*✅")
PARTIAL_DONE_MARK_FLAG = "字段=partial 但首标记写 ✅（以字段为准，#308 决策点 1）"
PARTIAL_IN_PROGRESS_WHY = "partial 但开头片段自陈在办"
# 同 `工具-落库sweep.py::LEADING_SEGMENT_SEPARATORS`／看板 ps1 `Get-LeadSeg`。
LEADING_SEGMENT_SEPARATORS: tuple[str, ...] = ("。", "——", "━━━")
# 看板 ps1 原文：任务列开头片段超 78 字截断加 `…`。
LEAD_TASK_MAX_CHARS = 78

VERDICT_POOL = "pool"
VERDICT_EXCLUDED = "excluded"
VERDICT_DEGRADED = "degraded"
VERDICT_OUT = "out"
VERDICT_SKIPPED = "skipped"


def leading_segment(text: str) -> str:
    """状态列「开头片段」：剥前导 `*`／空白／Tab／全角空格，截到首个句级
    分隔符（`。`／`——`／`━━━`）之前。同 sweep `_leading_status_segment`
    与看板 ps1 `Get-LeadSeg`，判据锚定开头而非全列扫描（`#248` 实证全列
    扫描会命中说明文字里被引用的判据原文）。"""
    t = text.lstrip(STATUS_LEADING_STRIP_CHARS)
    cut = len(t)
    for sep in LEADING_SEGMENT_SEPARATORS:
        i = t.find(sep)
        if 0 <= i < cut:
            cut = i
    return t[:cut]


def parse_status_domain_fields(status_cell: str) -> tuple[str | None, str | None, str]:
    """解析 §一 状态列开头的 `[S:...][D:...]` 机器字段。返回
    (状态取值或 None, 域取值或 None, 字段之后的自然语言正文)；字段缺失时
    返回 (None, None, 原文)，消费方须走非静默降级路径。"""
    stripped = status_cell.lstrip(STATUS_LEADING_STRIP_CHARS)
    m = STATUS_FIELD_RE.match(stripped)
    if not m:
        return None, None, status_cell
    return m.group(1), m.group(2), stripped[m.end():]


def _starts_with_stop_marker(text: str) -> bool:
    return text.lstrip(STATUS_LEADING_STRIP_CHARS).startswith(STOP_MARKER)


def lead_task_text(task_cell: str) -> str:
    """任务列首段（看板显示用）：开头片段截 78 字加 `…`。"""
    t = leading_segment(task_cell)
    if len(t) > LEAD_TASK_MAX_CHARS:
        t = t[:LEAD_TASK_MAX_CHARS] + "…"
    return t


@dataclass(frozen=True)
class OpenPoolVerdict:
    """单行判定结果。`verdict` ∈ {pool, excluded, degraded, out, skipped}；
    `why` 只在 excluded／degraded／skipped 时有值（给人看的一句理由）；
    `flag` 只在 pool 时可能非空（入池但带提示）。"""
    row_id: str
    status: Optional[str]
    domain: Optional[str]
    verdict: str
    why: str = ""
    flag: str = ""
    lead_status: str = ""
    lead_task: str = ""
    task_cell: str = ""
    owner_cell: str = ""
    status_cell: str = ""
    assigned: bool = False


def judge_open_pool_row(cells: list[str], column_ok: bool = True) -> OpenPoolVerdict:
    """🔴 可 Open 池**单行判据只写这一处**（队列 #312，2026-09-02 裁定）。
    `cells` 为 §一 一行的 8 个单元格；`column_ok` 为 False 时直接判
    `skipped`（列数不符的行不纳入判定、行号列出交人工核查）。"""
    row_id = cells[0] if cells and cells[0] else "?"
    if not column_ok or len(cells) < 8:
        return OpenPoolVerdict(
            row_id=row_id, status=None, domain=None, verdict=VERDICT_SKIPPED,
            why=f"列数不符（{len(cells)} 列，§一 应为 8 列），未纳入判定",
        )
    task_cell, owner_cell, status_cell = cells[1], cells[2], cells[5]
    status_value, domain_value, rest = parse_status_domain_fields(status_cell)
    assigned = ASSIGNED_MARKER in status_cell
    lead_status = leading_segment(rest) if status_value is not None else ""
    base = dict(
        row_id=row_id, status=status_value, domain=domain_value,
        lead_status=lead_status, lead_task=lead_task_text(task_cell),
        task_cell=task_cell, owner_cell=owner_cell, status_cell=status_cell,
        assigned=assigned,
    )
    if status_value is None:
        return OpenPoolVerdict(verdict=VERDICT_DEGRADED, why="状态字段缺失/非法（无 [S:…]）", **base)
    if status_value not in POOL_STATUS_VALUES:
        return OpenPoolVerdict(verdict=VERDICT_OUT, why=f"[S:{status_value}] 结构性排除", **base)
    if domain_value is None:
        return OpenPoolVerdict(
            verdict=VERDICT_DEGRADED,
            why=f"[S:{status_value}] 可动但缺 [D:机|业] 域字段，不猜域（队列 #523 同理）",
            **base,
        )
    if assigned:
        return OpenPoolVerdict(verdict=VERDICT_OUT, why="状态列含 [A: （已派出/在办）", **base)
    if _starts_with_stop_marker(rest):
        return OpenPoolVerdict(verdict=VERDICT_OUT, why="状态列正文以 🛑 起首", **base)
    if _starts_with_stop_marker(task_cell):
        return OpenPoolVerdict(verdict=VERDICT_OUT, why="任务列以 🛑 起首（#381 形态，OP-0911-N 认两列）", **base)
    if status_value == "partial" and PARTIAL_IN_PROGRESS_RE.search(lead_status):
        return OpenPoolVerdict(verdict=VERDICT_EXCLUDED, why=PARTIAL_IN_PROGRESS_WHY, **base)
    flag = ""
    if status_value == "partial" and _PARTIAL_DONE_MARK_RE.match(lead_status):
        flag = PARTIAL_DONE_MARK_FLAG
    return OpenPoolVerdict(verdict=VERDICT_POOL, flag=flag, **base)


def section_one_text(queue_text: str) -> str:
    """截出 `## 一、` 到下一个 `## ` 标题（或文末）之间的正文；找不到标题
    返回空串。🔴 只取**第一个** `## 一、`——两份物理队列文件必须逐份解析后
    合并，绝不拼接文本再解析（`#312` 缺口一已配反例单测）。"""
    start = queue_text.find(SECTION_ONE_HEADING)
    if start == -1:
        return ""
    rest = queue_text[start + len(SECTION_ONE_HEADING):]
    nxt = rest.find(_NEXT_HEADING)
    return rest if nxt == -1 else rest[:nxt]


def judge_section_one(queue_text: str) -> list[OpenPoolVerdict]:
    """对**单份**队列文本的 §一 逐行判定（含 skipped／degraded／out，不筛），
    交调用方按 `verdict` 取用。"""
    return [
        judge_open_pool_row(cells, column_ok)
        for _line, cells, column_ok in parse_section_rows(section_one_text(queue_text), "一")
    ]


@dataclass
class OpenPoolSnapshot:
    """对全部物理队列文件判定后的池快照。`verdicts` 按 (文件序, 行序)；
    `errors` 为读不到的文件（相对路径 → 原因）——**残缺的结果不当作完整的
    池**：消费方须据此告警或判「无法核验」。"""
    verdicts: list[tuple[str, OpenPoolVerdict]]
    errors: list[tuple[str, str]]

    def of(self, verdict: str) -> list[tuple[str, OpenPoolVerdict]]:
        return [(rel, v) for rel, v in self.verdicts if v.verdict == verdict]

    @property
    def pool(self) -> list[tuple[str, OpenPoolVerdict]]:
        return self.of(VERDICT_POOL)

    def pool_ids(self) -> list[str]:
        return [v.row_id for _rel, v in self.pool]


def compute_open_pool(repo_root: Path) -> OpenPoolSnapshot:
    """对 `iter_queue_paths()` 列出的全部物理队列文件逐份判定后合并。"""
    verdicts: list[tuple[str, OpenPoolVerdict]] = []
    errors: list[tuple[str, str]] = []
    for rel in iter_queue_paths():
        try:
            text = (Path(repo_root) / rel).read_text(encoding="utf-8")
        except OSError as exc:
            errors.append((rel, str(exc)))
            continue
        verdicts.extend((rel, v) for v in judge_section_one(text))
    return OpenPoolSnapshot(verdicts=verdicts, errors=errors)


def snapshot_to_kanban_payload(snapshot: OpenPoolSnapshot) -> dict:
    """转成看板数据层 ps1 消费的 JSON 形状（键名与 ps1 原 `$pool`／`$poolEx`／
    `$poolDeg` 逐字一致，`op`（opener 出处）仍由 ps1 自己的扫描器附上）。"""
    return {
        "pool": [
            {"no": v.row_id, "dom": v.domain, "st": v.status, "task": v.lead_task, "flag": v.flag}
            for _rel, v in snapshot.pool
        ],
        "poolEx": [
            {"no": v.row_id, "dom": v.domain, "why": v.why, "lead": v.lead_status}
            for _rel, v in snapshot.of(VERDICT_EXCLUDED)
        ],
        "poolDeg": [v.row_id for _rel, v in snapshot.of(VERDICT_DEGRADED)],
        "skipped": [v.row_id for _rel, v in snapshot.of(VERDICT_SKIPPED)],
        "errors": [{"file": rel, "why": why} for rel, why in snapshot.errors],
    }
