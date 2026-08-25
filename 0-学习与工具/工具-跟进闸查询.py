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
    # 队列 #353：闭环形态。**两份都显示**，因为它们回答的是两个不同的问题——
    # `annotation` ＝「主要事项」列里起草人写的判定（可被事后改动）；
    # `snapshot` ＝ 回填那一刻冻结进状态格的那一份，**闸只采信它**。
    closure_form_annotation: str | None = None
    closure_form_snapshot: str | None = None
    pending_intakes: list[IntakeRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


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


def _next_available_number(rows, number_col: int, department: str | None) -> str | None:
    """该部门下一个可用号 ＝ 表中该部门已出现的最大 `#N` ＋ 1。

    ⚠️ 只看**下表**，不读 README 顶部那段自由文本的「当前各部门下一个可用
    号」——那一段实测已连续失真四次（2026-08-10／08-12／08-18／08-21），
    正是本工具存在的理由之一。
    """
    if not department:
        return None
    highest = 0
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

    # 「最近一封」＝表格顺序上该收信人的最后一行（架构设计与 README 串行
    # 原则段的既定口径：按表格顺序，非日期——日期列存在补记情形）。
    latest = None
    department = None
    for row in rows:
        dept, name = split_department_and_name(row.cells[recipient_col])
        if name == recipient:
            latest, department = row, dept
    if latest is None:
        known = sorted({
            n for r in rows
            for _, n in [split_department_and_name(r.cells[recipient_col])] if n
        })
        raise GateQueryError(
            f"收信人「{recipient}」在 README 清单里不存在。已知收信人：{'、'.join(known)}"
        )

    status = latest.cells[latest.status_col_index]
    number_cell = latest.cells[number_col]
    kind = followup_gate.classify_status(status)
    gate_open = kind == "closed"
    target_file = (
        extract_target_filename(latest.cells[topic_col])
        if topic_col is not None and len(latest.cells) > topic_col else None
    )

    warnings: list[str] = []
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

    # 队列 #353 / design 决策点 5(c) 的**必配缓解**：(c) 只让事后追认「对闸
    # 无效」，**不阻止它被写下** ⇒ README 上仍可能出现一条「看起来像判定、
    # 实际不起作用」的标注。不把这条不一致报出来，(c) 就是用一个静默失效
    # 换掉了一个静默滥用。故此处一律显式报出，并声明**以快照为准**。
    topic_cell = (
        latest.cells[topic_col]
        if topic_col is not None and len(latest.cells) > topic_col else ""
    )
    annotation = followup_gate.parse_closure_form(topic_cell)
    snapshot = followup_gate.parse_closure_form(status)
    closure_annotation = annotation.form.form if annotation.form else None
    closure_snapshot = snapshot.form.form if snapshot.form else None

    for parse, where in ((annotation, "「主要事项」列的标注"), (snapshot, "状态格里的发出时快照")):
        if parse.violation:
            warnings.append(f"🔴 {where}不合法：{parse.violation}")

    if closure_snapshot and closure_annotation and closure_snapshot != closure_annotation:
        warnings.append(
            f"🔴 「主要事项」列的闭环形态标注（{closure_annotation}）与状态格里的"
            f"**发出时快照**（{closure_snapshot}）不一致——**以快照为准**："
            "闸只读发出那一刻冻结下来的那一份，发出之后改标注对闸零效果"
            "（design 决策点 5(c)）。请核实是哪一边写错了。"
        )
    elif closure_annotation and not closure_snapshot and followup_gate.is_dispatched(status):
        warnings.append(
            f"⚠ 「主要事项」列写着闭环形态标注（{closure_annotation}），但这封信"
            "**发出时状态格里没有快照** ⇒ 该标注对闸**零效果**（＝事后追认，"
            "design 决策点 5(c) 的结构性防线）。要让它生效，只能在**下一封**"
            "起草时就写好标注。"
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
        closure_form_annotation=closure_annotation,
        closure_form_snapshot=closure_snapshot,
        pending_intakes=pending,
        warnings=warnings,
    )


def all_recipients(readme_text: str) -> list[str]:
    """README 清单里出现过的全部收信人，按首次出现顺序去重。"""
    rows = _readme_rows(readme_text)
    recipient_col = column_index(rows[0].header_cells, "收信人")
    if recipient_col is None:
        raise GateQueryError("README 表头缺「收信人」列")
    seen: list[str] = []
    for row in rows:
        _, name = split_department_and_name(row.cells[recipient_col])
        if name and name not in seen:
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
    lines.append(f"依据：{report.letter_number} · {status_brief} · {kind_label}")
    # 队列 #353：闸判据的来源要看得见。**快照在前、标注在后**，因为闸只采信
    # 快照——顺序本身就是口径的一部分（验收条件 1 的观测口径也在这里取数）。
    if report.closure_form_snapshot or report.closure_form_annotation:
        parts = []
        if report.closure_form_snapshot:
            parts.append(f"发出时快照 `{report.closure_form_snapshot}`（闸采信这一份）")
        if report.closure_form_annotation:
            parts.append(f"主要事项列标注 `{report.closure_form_annotation}`")
        lines.append("闭环形态：" + "；".join(parts))
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
