"""跟进信 README 的 markdown 表格读写（供 delivery.py 场景①、
approval.py 场景③、dispatch.py 场景④共用）。

只处理"现有跟进信清单"这一张表——按管道符 `|` 切分/拼接，不支持单元格内含
转义 `|`（该 README 目前全是中文自然语言内容，无代码块/管道符，够用）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional

from zhuopin_platform.shared_tools import followup_gate


class ReadmeTableError(LookupError):
    pass


# design.md D1：两态语义草稿标记——起草唯一合法产物，转终态（gates.py 的
# FINALIZED_STATUS_MARKER = "🆕 待发"）仅能经 approve_followup_letter.py。
DRAFT_PENDING_REVIEW_STATUS = "⏳ 待你审"

# 队列 #294 修法⑴：三态语义第三态——已批准（内容审过）但主动暂缓发送，
# 与草稿态语义不同（草稿是"内容还没审"，暂缓是"内容已审、只是主动不发"）。
# 真实事故：队列行写了"暂不发"，但 README 状态列因为没有这个状态可写，
# 只能留在 FINALIZED_STATUS_MARKER 不变，`ZhuopinFollowupDispatchDaily`
# 只认状态列字面值，次日照发。此状态存在的意义正是让"暂缓"这个决定本身
# 也能被机制读到，而不是只能被人读到。不经任何脚本转换——由持锁编辑者
# 直接把状态列从 FINALIZED_STATUS_MARKER 手工改写为此值（反向恢复同理）；
# delivery.py/dispatch.py 的门禁只认 FINALIZED_STATUS_MARKER 这一个可发送
# 值，此值与草稿态一样被结构性排除在可发送范围之外。
# ⚠️ 本状态与队列侧决定是否一致，本次未做强制校验（那是 #258 的范围）。
PAUSED_STATUS = "⏸ 暂缓"


class DraftNotPendingReviewError(RuntimeError):
    """批准脚本拒绝：目标行「发送状态」列不是约定的待审草稿标记。"""


def assert_draft_pending_review(status_value: str) -> None:
    if status_value.strip() != DRAFT_PENDING_REVIEW_STATUS:
        raise DraftNotPendingReviewError(
            f'批准被拒绝：当前状态 "{status_value.strip()}" 非约定的待审草稿标记 '
            f'"{DRAFT_PENDING_REVIEW_STATUS}"'
        )


def _split_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _join_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


@dataclass
class RowLocation:
    line_index: int
    cells: list[str]
    status_col_index: int
    header_cells: list[str]


def iter_rows(text: str) -> list[RowLocation]:
    """返回表格全部数据行（供批量扫描场景使用，如 dispatch.py 场景④逐行
    判定是否可发送）——与 `locate_row` 共用同一套表头/分隔行判定逻辑，
    区别只在"取第一个匹配"还是"取全部"。

    表头行：任意以 `|` 开头且含"发送状态"字样的行。表头下一行是
    `|---|---|...` 分隔行，再往下直到第一条非 `|` 开头的行为止都是数据行。
    """
    lines = text.splitlines()
    header_idx = None
    header_cells: list[str] = []
    status_col_index = -1

    for i, line in enumerate(lines):
        if line.strip().startswith("|") and "发送状态" in line:
            header_cells = _split_row(line)
            for j, cell in enumerate(header_cells):
                if cell.startswith("发送状态"):
                    status_col_index = j
                    break
            header_idx = i
            break

    if header_idx is None or status_col_index < 0:
        raise ReadmeTableError('未找到含"发送状态"列的表格')

    rows: list[RowLocation] = []
    for i in range(header_idx + 2, len(lines)):
        line = lines[i]
        if not line.strip().startswith("|"):
            break
        cells = _split_row(line)
        if len(cells) <= status_col_index:
            continue
        rows.append(
            RowLocation(
                line_index=i,
                cells=cells,
                status_col_index=status_col_index,
                header_cells=header_cells,
            )
        )
    return rows


def locate_row(text: str, match: Callable[[list[str]], bool]) -> RowLocation:
    """定位表格中"发送状态"列所在、且满足 `match(cells)` 的第一行。"""
    for row in iter_rows(text):
        if match(row.cells):
            return row
    raise ReadmeTableError("未找到匹配的跟进信行")


def write_status(text: str, loc: RowLocation, new_status: str) -> str:
    """把 `loc` 定位到的行的状态列原子替换为 `new_status`，返回新文本。"""
    lines = text.splitlines()
    cells = loc.cells.copy()
    cells[loc.status_col_index] = new_status
    lines[loc.line_index] = _join_row(cells)
    newline = "\n" if text.endswith("\n") else ""
    return "\n".join(lines) + newline


def column_index(header_cells: list[str], contains: str) -> Optional[int]:
    """按表头单元格是否包含子串定位列序号（供 dispatch.py/draft_gap_detection.py
    共用，避免各自重复实现同一个查找）。"""
    for i, cell in enumerate(header_cells):
        if contains in cell:
            return i
    return None


def split_department_and_name(recipient_cell: str) -> tuple[Optional[str], Optional[str]]:
    """"质量部 · 陈忱（可分担朱映桦）" -> ("质量部", "陈忱")。取不到则返回
    (None, None)，调用方据此判失败，不臆造。原属 dispatch.py，队列 #245
    需要同一套解析（README 已起草行 vs 发布收口场景按收信人交叉比对），
    迁到本共享模块，dispatch.py 改为调用本函数。"""
    if "·" not in recipient_cell:
        return None, None
    department, _, rest = recipient_cell.partition("·")
    department = department.strip()
    name = rest.strip()
    for cut in ("（", "("):
        idx = name.find(cut)
        if idx != -1:
            name = name[:idx]
    name = name.strip()
    if not department or not name:
        return None, None
    return department, name


# 队列 #241 修法⑴：README 行携带目标文件名，dispatch 直接读、不再仅凭
# 「收信人＋日期」猜测（同日多封必然歧义，2026-08-04 首次真实触发命中）。
# 起草时统一由 `build_target_file_annotation` 写入固定格式；历史行（如
# 队列 #150，值周巡检人工消歧写入）措辞略有出入但同样含"目标文件"关键字
# + 反引号围栏的 .md 文件名，本正则对两者兼容，不需要回改历史行内容。
_TARGET_FILE_RE = re.compile(r"目标文件[^`]*`([^`]+\.md)`")


def extract_target_filename(topic_cell: str) -> Optional[str]:
    """从"主要事项"列文本中提取队列 #241 标注的目标文件名，未标注返回 None
    （调用方据此回落旧的「部门＋姓名＋日期」glob 判据，向后兼容未标注的
    历史行）。"""
    m = _TARGET_FILE_RE.search(topic_cell)
    return m.group(1) if m else None


def build_target_file_annotation(filename: str) -> str:
    """起草新行时追加到"主要事项"列末尾的固定格式片段（队列 #241 修法⑴）。
    只在既有单元格内追加文本，不新增列——不改变表格结构，`_validate_
    followup_readme_release`/`_validate_release_structure`（编辑锁工具的
    列数/身份校验）因此不受影响，无需同步修改。"""
    return f" → 目标文件：`{filename}`"


# ---------------------------------------------------------------------------
# 闭环形态标注（队列 #353；openspec `followup-closure-form-survives-backfill`）
# ---------------------------------------------------------------------------
#
# 手法**逐字复刻**上面的 `build_target_file_annotation`（队列 #241，2026-08-04
# 起在生产上跑着）：同列（「主要事项」）、只在既有单元格内追加文本、**不新增
# 列** ⇒ 编辑锁的列数/身份校验（`_validate_release_structure`／
# `_followup_readme_rows`）不受影响，无需同步修改。
#
# 🔴 **判据不在本模块**：取值枚举与合法性一律走
# `zhuopin_platform.shared_tools.followup_gate`（模块文档明令「判据只此一份，
# 不得在消费者侧另写」）。本模块只负责**写入格式**与**取一格文本去问它**。


class ClosureFormAnnotationError(ValueError):
    """写入侧 fail-loud：给的取值不在闭环四态枚举内，或依据文本不合法。"""


def _format_closure_form(label: str, form: str, basis: str) -> str:
    """标注与快照共用的唯一格式化实现——两者若各写一份，`parse_closure_form`
    迟早只认得其中一份。"""
    value = followup_gate.normalize_status(form)
    if value not in followup_gate.CLOSED_STATUS_PREFIXES:
        raise ClosureFormAnnotationError(
            f"闭环形态取值「{form}」不在闭环四态枚举内"
            f"（{'／'.join(followup_gate.CLOSED_STATUS_PREFIXES)}）"
        )
    text = (basis or "").strip()
    if not text:
        raise ClosureFormAnnotationError("闭环形态标注的依据文本不得为空（design 决策点 4(a)）")
    if "）" in text or "`" in text:
        raise ClosureFormAnnotationError(
            "闭环形态标注的依据文本不得含全角右括号「）」或反引号——"
            "两者都是本标注的语法边界，写进去会让解析在错误的位置截断"
        )
    return f"{label}：`{value}`（依据：{text}）"


def build_closure_form_annotation(form: str, basis: str) -> str:
    """起草新行时追加到「主要事项」列末尾的闭环形态标注。

    形如 `` → 闭环形态：`✅ 无需回复`（依据：正文三要素表明写「不用回」）``。

    🔴 **只在起草时写才有用**：闸采信的是**发出时快照**（见
    `build_closure_form_snapshot`），信发出之后再补写本标注对闸零效果
    （design 决策点 5(c)，防「事后追认」靠结构而非门禁）。
    """
    return " → " + _format_closure_form(
        followup_gate.CLOSURE_FORM_MARKER, form, basis
    )


def build_closure_form_snapshot(form: str, basis: str) -> str:
    """回填时写进「发送状态」格的那一段——**发出时快照**。

    返回的是**不带分段符的裸段**，由调用方用
    `followup_gate.PRESERVED_SEGMENT_SEPARATOR` 与其它段拼接
    （`delivery.build_backfill_status` 是唯一调用方）——分段符只在拼接那一处
    出现一次，本函数不各带一份。

    快照是回填那一刻的值；此后「主要事项」列被如何修改都不改变它
    （spec `followup-status-backfill-preservation`「快照冻结」）。
    """
    return _format_closure_form(
        followup_gate.CLOSURE_FORM_SNAPSHOT_LABEL, form, basis
    )


def extract_closure_form(cell_text: str) -> "followup_gate.ClosureFormParse":
    """从一格文本里取闭环形态标注/快照。薄封装，判据全在 `followup_gate`。

    保留本入口是为了让「主要事项」列的两条标注（`目标文件：` 与
    `闭环形态：`）在调用方看来来自同一个模块，与 `extract_target_filename`
    对称；**不在此处复制任何取值清单或校验逻辑**。
    """
    return followup_gate.parse_closure_form(cell_text)
