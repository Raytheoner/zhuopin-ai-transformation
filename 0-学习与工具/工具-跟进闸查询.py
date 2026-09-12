"""跟进信「串行闸」只读派生查询（队列 #366 / S3，2026-08-21）。

## 它解决的问题

**串行闸永远不会自己开。** 闸的判据源是
`6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md` 的「发送状态」列，
而机器只写队列——回件到达时机器人自动追 §一 行、拆件回灌由人写队列行，
**唯独没有任何东西去改 README 那一格**，也**没有任何一处能一句话回答
「这个人的闸此刻开没开」**。于是每次都得去读六处文字再自己拼，而
2026-08-21 一天之内就因此咬了两次（质量部#8 回灌全做完闸还锁着；采购部#17
回件 13:13 到、13:15 队列已追行而 README 未动）。

本工具是**读侧的唯一出口**（架构设计 §二 S3）：它**派生、不可写**，所以
永远不会与权威源漂移。**所有消费者一律跑它，不裸读 README、不裸读队列。**
同协议〇.5 对队列已经确立的那条纪律（「查队列行状态一律用只读 CLI」）。

## 判据来自哪里

闭环四态的判定 **一律** 走 `zhuopin_platform.shared_tools.followup_gate`
（本工具、编辑锁 release 校验、aibot 入信桥三处共用同一份），本文件不另写
一套。见该模块文档。

## 用法

    python 0-学习与工具/工具-跟进闸查询.py --to 姚祖怡
    python 0-学习与工具/工具-跟进闸查询.py --all
    python 0-学习与工具/工具-跟进闸查询.py --to 陈忱 --json

退出码：**闸开 0／闸锁 0**（🔴 闸锁不是错误，是一个正常答案——若把它做成
非零，调用方的 `&&` 链会把「他手上还有在途信」当成工具故障）；README 解析
失败或收信人不存在 `2`。

## 人读格式与 --json 由同一份数据渲染

两条渲染路径共用 `build_report()` 产出的同一个 `GateReport`——派单件 §一
明写「不得两套逻辑」。任何新增字段先进 `GateReport`，两侧同时可见。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
_REPO_GUESS = _TOOLS_DIR.parent

# 队列解析复用编辑锁已有的分区/表格实现（同 `工具-队列结构lint.py` 的既定
# 手法：按文件路径 importlib 加载，不走 `import 工具-...` 的包名解析）。
# 顺带拿到它算好的 `REPO_ROOT`——那是经 `git rev-parse --git-common-dir`
# 解到的**主工作区**，而不是本 worktree 自己那份可能过期的签出（队列 #314①
# 实测坐实两者会给出不同答案，且不报错）。
_EDIT_LOCK_SCRIPT = _TOOLS_DIR / "工具-共享文档编辑锁.py"
_spec = importlib.util.spec_from_file_location("_followup_gate_editlock_reuse", _EDIT_LOCK_SCRIPT)
editlock = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(editlock)

REPO_ROOT: Path = editlock.REPO_ROOT
README_REL = "6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md"
QUEUE_PATHS_REL = [editlock.QUEUE_MECHANISM_PATH_REL, editlock.QUEUE_BUSINESS_PATH_REL]
EXTERNAL_DOCS_DIRNAME = "7-外部文档"

# #300 式 sys.path 引导（不用 `pip install -e`——本模块与其两层 `__init__.py`
# 均无第三方依赖）。目录不存在时用兜底桩，理由同 `工具-队列查询.py`。
_PLATFORM_PATH = _REPO_GUESS / "5-平台底座" / "zhuopin_platform"
if not _PLATFORM_PATH.is_dir():
    _PLATFORM_PATH = REPO_ROOT / "5-平台底座" / "zhuopin_platform"
if _PLATFORM_PATH.is_dir() and str(_PLATFORM_PATH) not in sys.path:
    sys.path.insert(0, str(_PLATFORM_PATH))
from zhuopin_platform.shared_tools import followup_gate  # noqa: E402

_AIBOT_PATH = _REPO_GUESS / "5-平台底座" / "wecom-aibot-service"
if not _AIBOT_PATH.is_dir():
    _AIBOT_PATH = REPO_ROOT / "5-平台底座" / "wecom-aibot-service"
if _AIBOT_PATH.is_dir() and str(_AIBOT_PATH) not in sys.path:
    sys.path.insert(0, str(_AIBOT_PATH))
# 🔴 README 表格解析复用 `aibot_service.readme_table.iter_rows`——派单件 §一
# 明写「不要自己写正则拆 README 表」。
from aibot_service.readme_table import (  # noqa: E402
    ReadmeTableError,
    column_index,
    extract_target_filename,
    iter_rows,
    split_department_and_name,
)


class GateQueryError(RuntimeError):
    """README 解析失败／收信人不存在——对应退出码 2。"""


@dataclass
class IntakeRow:
    """队列 §一 里由企微机器人自动追加的一条「入信行」。"""

    number: str
    queue_file: str
    status_field: str | None          # [S:xxx] 里的 xxx，缺失为 None
    archived_path: str
    dismantled: bool                  # 是否已拆件（[S:done]）
    matches_current_letter: bool      # 归档文件名是否确定对应本行信的目标文件


@dataclass
class GateReport:
    recipient: str
    department: str | None
    gate_open: bool
    letter_number: str
    letter_status: str
    letter_status_kind: str           # closed / reply_arrived / in_flight / unknown
    letter_target_file: str | None
    next_number: str | None
    pending_intakes: list[IntakeRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # 变更包 `followup-closure-form-survives-backfill`（决策点 1(a) 代价①的缓解
    # ＋ 决策点 5(c) 必配缓解）：「怎样算闭环」与「当前状态」同报。
    # `closure_snapshot` ＝ 状态格里发出时冻结的快照取值（**闸只认这个**）；
    # `closure_annotation` ＝ 「主要事项」列此刻的标注取值（只供人读、对闸零效果）。
    closure_snapshot: str | None = None
    closure_annotation: str | None = None


# ---------------------------------------------------------------------------
# README 侧
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _readme_rows(readme_text: str):
    try:
        rows = iter_rows(readme_text)
    except ReadmeTableError as exc:
        raise GateQueryError(f"README 表格解析失败：{exc}") from exc
    if not rows:
        raise GateQueryError("README「现有跟进信清单」表没有任何数据行")
    return rows


_ARCHIVE_GLOB = "README-归档-*.md"


def _archived_max_number(department: str) -> int:
    """`followup-readme-phase2` D2：扫全部归档件，取该部门出现过的最大
    `#N`。2026-09-06 归档能力落地前实测坐实的风险——若某部门在主表里只剩
    低编号在途信（其历史高编号信已全部归档），`_next_available_number`
    若只看主表会把「下一个可用号」算低，与一个刚被迁走的归档编号撞上，
    直接违反「归档编号不复用」。归档件尚不存在（`glob` 命中 0 个文件）时
    天然返回 0，不是特殊分支。逐份归档件独立 try/except，单份解析失败不
    影响其余归档件被扫到（同 `resolve_letter_number` 的既有容错惯例）。
    """
    readme_dir = (REPO_ROOT / README_REL).parent
    if not readme_dir.is_dir():
        return 0
    highest = 0
    for archive_path in readme_dir.glob(_ARCHIVE_GLOB):
        try:
            text = archive_path.read_text(encoding="utf-8")
            rows = iter_rows(text)
        except (OSError, ReadmeTableError):
            continue
        num_idx = column_index(rows[0].header_cells, "编号") if rows else None
        if num_idx is None:
            continue
        for row in rows:
            if len(row.cells) <= num_idx:
                continue
            parsed = followup_gate.parse_letter_number(row.cells[num_idx])
            if parsed and parsed[0] == department:
                highest = max(highest, parsed[1])
    return highest


def _archived_recipients() -> dict[str, str]:
    """`followup-readme-phase2` D2（2026-09-06 归档实施后实测坐实的缺口）：
    扫全部归档件，返回 {姓名: 部门}——供 `build_report`/`all_recipients` 在
    主表已无该收信人任何行时（其全部历史信均已归档，如首个真实归档批次
    里的「销售部 · 泓钦」）仍能确认「历史上确有此人，只是信已全部归档」，
    而不是把「查不到」误判为「这个名字压根不存在」。
    """
    readme_dir = (REPO_ROOT / README_REL).parent
    result: dict[str, str] = {}
    if not readme_dir.is_dir():
        return result
    for archive_path in sorted(readme_dir.glob(_ARCHIVE_GLOB)):
        try:
            text = archive_path.read_text(encoding="utf-8")
            rows = iter_rows(text)
        except (OSError, ReadmeTableError):
            continue
        header = rows[0].header_cells if rows else []
        col = column_index(header, "收信人")
        if col is None:
            continue
        for row in rows:
            if len(row.cells) <= col:
                continue
            identity = followup_gate.recipient_identity(row.cells[col])
            if identity and identity[1] not in result:
                # 🔴 存**原文**部门段：本 dict 的取值下游要喂
                # `_next_available_number`（按 `<部门>#<数字>` 匹配），归一化值
                # 会一封都匹配不上、把「下一个可用号」算成 `质量#1`。
                result[identity[1]] = followup_gate.recipient_department_raw(
                    row.cells[col]
                )
    return result


def _next_available_number(rows, number_col: int, department: str | None) -> str | None:
    """该部门下一个可用号 ＝ max(表中该部门已出现的最大 `#N`, 全部归档件中
    该部门已出现的最大 `#N`) ＋ 1。

    ⚠️ 只看**下表**，不读 README 顶部那段自由文本的「当前各部门下一个可用
    号」——那一段实测已连续失真四次（2026-08-10／08-12／08-18／08-21），
    正是本工具存在的理由之一。

    🔴 **必须同时看归档件**（`followup-readme-phase2` D2 补丁，2026-09-06）：
    某部门若已无新信、其主表在途信恰好都是低编号，而历史高编号信已归档，
    只看主表会把编号往回算，与刚归档的编号撞上。
    """
    if not department:
        return None
    highest = _archived_max_number(department)
    for row in rows:
        parsed = followup_gate.parse_letter_number(row.cells[number_col])
        if parsed and parsed[0] == department:
            highest = max(highest, parsed[1])
    if highest == 0:
        return f"{department}#1"
    return f"{department}#{highest + 1}"


# ---------------------------------------------------------------------------
# 队列侧（入信行）
# ---------------------------------------------------------------------------

_POINTER_RE = re.compile(r"`(" + EXTERNAL_DOCS_DIRNAME + r"/[^`]+)`")
INTAKE_TASK_MARKER = "企微反馈自动归档"


def _department_dir_aliases(department: str) -> tuple[str, ...]:
    """README 收信人列的部门名 → `7-外部文档/` 下真实的归档目录名。

    两者**不总是同一个字符串**：`department_mapping.yaml` 把陈承（userid
    `2023458`）映射到 `IT`，而 README 写的是 `IT部` ⇒ 只按 README 的写法找
    目录会对陈承恒返回零条入信行，**且不报错**（同 CLAUDE.md §5「工具静默
    回退」：一个「太干净」的结果）。故显式列出去「部」后的别名，两个都试。
    """
    aliases = [department]
    if department.endswith("部"):
        aliases.append(department[:-1])
    return tuple(aliases)


def _collect_intake_rows(department: str | None, letter_target_file: str | None) -> list[IntakeRow]:
    """扫两份物理队列文件的 §一，取该部门名下由机器人自动追加的入信行。

    🔴 逐份解析后合并，**不拼接文本再解析一次**——`_split_live_sections`
    按标题定位、同名 label 后写覆盖先写，拼接会把第一份的 §一 静默顶掉
    （队列 #312 缺口一踩过一模一样的坑）。

    ⚠️ 归属粒度是**部门**，不是人：入信行只带归档路径，路径里只有部门段。
    当前五个部门各只有一位在册收信人（见 `department_mapping.yaml`），故部门
    级等价于人级；**哪天某部门有了第二位收信人，这一行就会把两人的入信混在
    一起**——届时须改为按 `reply_matches_letter` 逐封精确归属，本注释即是那
    一天的路标。
    """
    rows: list[IntakeRow] = []
    if not department:
        return rows
    dir_aliases = _department_dir_aliases(department)
    for queue_rel in QUEUE_PATHS_REL:
        target = REPO_ROOT / queue_rel
        if not target.exists():
            # fail-loud：缺一份队列文件就少一批入信行，不能静默当成「没有」。
            rows.append(
                IntakeRow(
                    number="?", queue_file=queue_rel, status_field=None,
                    archived_path=f"（队列文件不存在：{queue_rel}）",
                    dismantled=False, matches_current_letter=False,
                )
            )
            continue
        sections = editlock._split_live_sections(_read(target))
        for line, cells in editlock._table_data_rows(sections.get("一", "")):
            if len(cells) < 6 or INTAKE_TASK_MARKER not in cells[1]:
                continue
            m = _POINTER_RE.search(cells[3])
            if not m:
                continue
            pointer = m.group(1)
            if not any(f"/{alias}/" in pointer for alias in dir_aliases):
                continue
            status_field, _, _ = editlock._parse_status_domain_fields(cells[5])
            filename = pointer.rsplit("/", 1)[-1]
            matches = bool(
                letter_target_file
                and followup_gate.reply_matches_letter(filename, letter_target_file)
            )
            rows.append(
                IntakeRow(
                    number=cells[0], queue_file=queue_rel, status_field=status_field,
                    archived_path=pointer, dismantled=(status_field == "done"),
                    matches_current_letter=matches,
                )
            )
    return rows


# ---------------------------------------------------------------------------
# 组装
# ---------------------------------------------------------------------------

def build_report(recipient: str, readme_text: str) -> GateReport:
    """对单个收信人算闸。人读与 --json 两条渲染路径共用本函数的返回值。"""
    rows = _readme_rows(readme_text)
    header = rows[0].header_cells
    number_col = column_index(header, "编号")
    recipient_col = column_index(header, "收信人")
    topic_col = column_index(header, "主要事项")
    if number_col is None or recipient_col is None:
        raise GateQueryError("README 表头缺「编号」或「收信人」列")

    # 🔴 **「最近一封」＝ 日期 → 编号序号 → 表内行序**（变更包
    # `followup-serial-gate-hardening` D3 拍板 (a)，2026-09-07）。
    #
    # 改造前这里取的是「表格顺序上该收信人的最后一行」，而
    # `followup_gate._letter_sort_key` 的 docstring 早就写着「⚠️ 不能只按表内
    # 行序」并给了实测反例（`采购部#4` 07-21 排在 `采购部#17` 08-20 之后）——
    # **闸侧用的正是那个 docstring 说了不该用的东西**。2026-09-07 实测两把
    # 尺子正对陈忱给出相反答案：物理行序取到已闭环的 `质量部#12`（闸开），
    # 日期排序键取到 `✅ 已推送` 的 `质量部#13`（闸锁）。判据只此一把。
    #
    # 收信人匹配同批改为 `recipient_identity` 二元组（部门 ＋ 姓名，后括号
    # 注记剥除、不参与匹配）——只取姓名会让跨部门同名被合并成一个人。
    date_col = column_index(header, "日期")
    metas = []
    for order, row in enumerate(rows):
        identity = followup_gate.recipient_identity(row.cells[recipient_col])
        if identity is None:
            continue
        metas.append((identity, followup_gate.LetterRow(
            number=row.cells[number_col],
            date=(row.cells[date_col] if date_col is not None
                  and len(row.cells) > date_col else ""),
            recipient=row.cells[recipient_col],
            target_filename=None,
            status=row.cells[row.status_col_index],
            order=order,
        ), row))
    wanted = [m for m in metas if m[0][1] == recipient]
    latest = None
    department = None
    if wanted:
        identity = wanted[0][0]
        newest = followup_gate.latest_letter_for_recipient(
            [m[1] for m in wanted], identity
        )
        latest = next(r for i, m, r in wanted if m.order == newest.order)
        # 🔴 **原文**部门段（`质量部`），不是身份键里的归一化值（`质量`）：
        # 它下游要喂 `_next_available_number`（按 `<部门>#<数字>` 匹配占号）与
        # `_department_dir_aliases`（按 `7-外部文档/<部门>/` 找入信归档目录），
        # 两处喂归一化值都会给出一个**干净的错答案**、且都不报错。
        department = followup_gate.recipient_department_raw(
            latest.cells[recipient_col]
        )
    if latest is None:
        # `followup-readme-phase2` D2：主表查不到不等于这个人不存在——他的
        # 全部历史信可能已被归档（如首个真实归档批次里的「销售部 · 泓钦」，
        # 其唯一一封信 2026-09-06 因终态+超30天被迁走）。查不到即报「不存在」
        # 会把「历史信已了结」误判成「压根没这个人」。
        archived_department = _archived_recipients().get(recipient)
        if archived_department is not None:
            return GateReport(
                recipient=recipient,
                department=archived_department,
                gate_open=True,
                letter_number="（无在途，历史信件均已归档）",
                letter_status="（该收信人历史信件均已归档，当前无在途信）",
                letter_status_kind="closed",
                letter_target_file=None,
                next_number=_next_available_number(rows, number_col, archived_department),
                pending_intakes=[],
                warnings=[],
            )
        known = sorted({
            i[1] for r in rows
            for i in [followup_gate.recipient_identity(r.cells[recipient_col])] if i
        })
        raise GateQueryError(
            f"收信人「{recipient}」在 README 清单里不存在。已知收信人：{'、'.join(known)}"
        )

    status = latest.cells[latest.status_col_index]
    number_cell = latest.cells[number_col]
    kind = followup_gate.classify_status(status)
    gate_open = kind == "closed"
    topic_cell = (
        latest.cells[topic_col]
        if topic_col is not None and len(latest.cells) > topic_col else ""
    )
    target_file = extract_target_filename(topic_cell) if topic_cell else None

    warnings: list[str] = []

    # ---- 闭环形态：快照（闸的判据）与标注（人读）同报，不一致必须出声 ----
    # 决策点 5(c) 取「结构性防止」而不新增门禁 ⇒ 事后追认**写得进去**、只是
    # 对闸零效果；不把这一点报出来，(c) 就是用一个静默失效换掉了一个静默滥用。
    closure_snapshot = followup_gate.extract_closure_snapshot(status)
    closure_form = followup_gate.parse_closure_form(topic_cell)
    closure_annotation = None
    if closure_form is not None:
        closure_annotation = closure_form.value if closure_form.is_valid else closure_form.raw
        if closure_form.problem:
            warnings.append(f"⚠ 「{number_cell}」{closure_form.problem}")
    mismatch = followup_gate.closure_form_mismatch_warning(topic_cell, status)
    if mismatch:
        warnings.append(f"{mismatch}（行「{number_cell}」）")
    if kind == "unknown":
        warnings.append(
            f"README 状态列出现本工具不认识的写法「{followup_gate.normalize_status(status)[:40]}」"
            "——已按**在途**（闸锁）保守处理；若它其实是一种闭环形态，"
            "须先把写法归一到闭环四态之一，或扩 followup_gate.CLOSED_STATUS_PREFIXES。"
        )
    if followup_gate.number_status_mismatch(number_cell, status):
        warnings.append(
            f"编号列「{number_cell}」自称未发/不占号，状态列却表明这封信已发出"
            "——README 顶部「下一个可用号」段与本行编号列是同一事实的两份副本，"
            "已连续失真四次（见 README 该段原文）。本工具的「下一个可用号」只按"
            "下表实际 `#N` 最大值推算，不受该括注影响。"
        )

    intakes = _collect_intake_rows(department, target_file)
    pending = [r for r in intakes if not r.dismantled]
    if not gate_open:
        dismantled_match = [r for r in intakes if r.matches_current_letter and r.dismantled]
        if dismantled_match:
            ids = " / ".join(f"§一 #{r.number}" for r in dismantled_match)
            warnings.append(
                f"🔴 {ids} 已拆件（[S:done]），而 README「{number_cell}」仍为"
                f"「{followup_gate.normalize_status(status)[:30]}」——请先转闭环态。"
                "（这正是 S4 桥二 release 校验会拒绝的形态）"
            )
        elif pending:
            ids = " / ".join(f"§一 #{r.number}" for r in pending)
            warnings.append(
                f"⚠ 入信已到但 README 未转态（{ids}）——拆件回灌后须回改 README "
                "状态列（见 §一 #366 M4）"
            )

    return GateReport(
        recipient=recipient,
        department=department,
        gate_open=gate_open,
        letter_number=number_cell,
        letter_status=status,
        letter_status_kind=kind,
        letter_target_file=target_file,
        next_number=_next_available_number(rows, number_col, department),
        pending_intakes=pending,
        warnings=warnings,
        closure_snapshot=closure_snapshot,
        closure_annotation=closure_annotation,
    )


def all_recipients(readme_text: str) -> list[str]:
    """主表 ＋ 归档件里出现过的全部收信人，按首次出现顺序去重（主表在前）。

    `followup-readme-phase2` D2：归档实施后，某收信人的全部历史信可能已
    全部迁出主表——若只看主表，`--all` 会把他从值周巡检的名单里悄悄漏掉，
    与「归档动作不改变活行读取方结果」的既定承诺冲突。
    """
    rows = _readme_rows(readme_text)
    recipient_col = column_index(rows[0].header_cells, "收信人")
    if recipient_col is None:
        raise GateQueryError("README 表头缺「收信人」列")
    seen: list[str] = []
    for row in rows:
        identity = followup_gate.recipient_identity(row.cells[recipient_col])
        if identity and identity[1] not in seen:
            seen.append(identity[1])
    for name in _archived_recipients():
        if name not in seen:
            seen.append(name)
    return seen


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def render_human(report: GateReport) -> str:
    lines = [f"闸：{'✅ 开' if report.gate_open else '🔒 锁'}"]
    status_brief = followup_gate.normalize_status(report.letter_status)
    status_brief = status_brief.split("　")[0].split("\n")[0]
    if len(status_brief) > 60:
        status_brief = status_brief[:60] + "…"
    kind_label = {
        "closed": "已闭环", "reply_arrived": "回件已到、待拆件",
        "in_flight": "在途", "unknown": "状态写法未知（按在途处理）",
    }[report.letter_status_kind]
    # 「当前状态」与「怎样算闭环」拼在同一行（决策点 1(a) 代价①的缓解：两者
    # 落在两列，人读要合看两格——这里替他合）。
    if report.closure_snapshot is not None:
        closure = f"闭环形态（发出时快照）＝{report.closure_snapshot}"
    elif report.closure_annotation is not None:
        closure = f"闭环形态标注＝{report.closure_annotation}（未快照，对闸零效果）"
    else:
        closure = "闭环形态：无标注（按状态格首段判）"
    lines.append(f"依据：{report.letter_number} · {status_brief} · {kind_label} · {closure}")
    if report.pending_intakes:
        ids = " / ".join(f"§一 #{r.number}" for r in report.pending_intakes)
        states = "、".join(sorted({f"[S:{r.status_field or '缺字段'}]" for r in report.pending_intakes}))
        lines.append(f"最近入信：{ids}（未拆件，{states}）")
    else:
        lines.append("最近入信：无未拆件的入信行")
    if report.next_number:
        lines.append(f"下一个可用号：{report.next_number}")
    lines.extend(report.warnings)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="跟进信串行闸只读查询——权威源＝跟进信 README「发送状态」列"
                    "（队列 #366 / S3）。闸开与闸锁都返回 0。",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--to", help="按收信人算闸，如 --to 姚祖怡")
    group.add_argument("--all", action="store_true", help="列出全部收信人的闸状态（值周巡检用）")
    parser.add_argument("--json", action="store_true", help="机器消费用；与人读格式由同一份数据渲染")
    args = parser.parse_args(argv)

    readme_path = REPO_ROOT / README_REL
    try:
        readme_text = _read(readme_path)
    except OSError as exc:
        print(f"✗ 读取 README 失败：{readme_path}（{exc}）")
        return 2

    try:
        targets = all_recipients(readme_text) if args.all else [args.to]
        reports = [build_report(name, readme_text) for name in targets]
    except GateQueryError as exc:
        print(f"✗ {exc}")
        return 2

    if args.json:
        print(json.dumps([asdict(r) for r in reports], ensure_ascii=False, indent=2))
        return 0

    print("\n\n".join(
        (f"── {r.recipient}（{r.department or '部门未知'}）──\n" if args.all else "") + render_human(r)
        for r in reports
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
