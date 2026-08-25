"""跟进信 README 的 markdown 表格读写（供 delivery.py 场景①、
approval.py 场景③、dispatch.py 场景④共用）。

按管道符 `|` 切分/拼接，不支持单元格内含转义 `|`（该 README 目前全是中文
自然语言内容，无代码块/管道符，够用）。

🔴 **队列 #399（followup-supplement-channel，§四 #119 决策点 2 答 (b)）：
表格定位由「文件里第一个含『发送状态』的表」改为「按所属 `##` 章节标题
显式选表」。**

改判前两份独立实现（本模块与 `工具-共享文档编辑锁.py::_followup_readme_
rows`）同时依赖着一条**从未被任何人声明**的判据——目标表恰好排在文件里
第一个。README 一旦多出第二张同构表（补件登记表即是），把它挪到主表之前
**一次纯排版编辑**就能让两份实现同时把补件表读成主表，**且都不报错**。
本模块因此改为：`section` 不传时**强制匹配主表章节标题**，匹配不到即
`raise ReadmeTableError`，MUST NOT 回退到任何「取第一个表」的行为。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional

from zhuopin_platform.shared_tools.followup_gate import (
    UNNUMBERED_MARKERS,
    parse_letter_number,
)


class ReadmeTableError(LookupError):
    pass


# 队列 #399：两张表各有其名。匹配按「`##` 标题正文以此串起首」判定——README
# 实际标题带括注（`## 补件登记（不占编号、不占串行闸，2026-08-24 立表）`），
# 用前缀匹配既能容忍括注，又不会把两个名字互相误命中。
MAIN_TABLE_SECTION = "现有跟进信清单"
SUPPLEMENT_TABLE_SECTION = "补件登记"

# 补件表专有列名（design 决策点 1(a)：首列刻意**不叫**「编号」——补件不占号）。
SUPPLEMENT_CARRY_NUMBER_COLUMN = "承接编号"
# 决策点 5(b)：「需回复」是补件表的**显式列**，不靠读散文判断。
SUPPLEMENT_REPLY_REQUIRED_COLUMN = "需回复"
SUPPLEMENT_REPLY_REQUIRED_YES = "是"
SUPPLEMENT_REPLY_REQUIRED_NO = "否"

# 决策点 5(b)：通知型（需回复＝否）补件发送成功即置终态，不再需要任何后续
# 人工转态。该取值本就属 `followup_gate.CLOSED_STATUS_PREFIXES` 闭环四态之一，
# 不新增状态词汇。
NO_REPLY_NEEDED_STATUS = "✅ 无需回复"


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


def _is_level_two_heading(line: str) -> bool:
    """`## X` 是章节标题；`### X` 不是（它是节内小标题，如补件表下方逐封
    正文的 `### 财务部 · 唐燕萍 ——…`）。`"### x".startswith("## ")` 为
    False，判据天然把三级标题排除在外，无需额外条件。"""
    return line.strip().startswith("## ")


def section_span(lines: list[str], section: str) -> tuple[int, int]:
    """返回 `section` 章节的行区间 `[start, end)`——从其 `##` 标题行的下一行
    起，到**下一个 `##` 标题行**为止（末章节到文件尾）。

    匹配不到 MUST 抛错，MUST NOT 回落到「全文」或「第一个表」（队列 #399：
    静默回落正是本次要退休的那条判据的形态）。
    """
    start: Optional[int] = None
    for i, line in enumerate(lines):
        if not _is_level_two_heading(line):
            continue
        if start is None:
            if line.strip()[3:].strip().startswith(section):
                start = i + 1
            continue
        return start, i
    if start is None:
        raise ReadmeTableError(
            f'跟进信 README 中未找到章节标题「## {section}…」——按队列 #399 '
            "改判后表格一律按章节标题定位，此处 MUST NOT 回退到「取文件里第一个"
            "含『发送状态』的表」。请检查 README 章节标题是否被改名或删除。"
        )
    return start, len(lines)


def iter_rows(text: str, section: Optional[str] = None) -> list[RowLocation]:
    """返回指定章节内那张表的全部数据行（供批量扫描场景使用，如 dispatch.py
    场景④逐行判定是否可发送）——与 `locate_row` 共用同一套表头/分隔行判定
    逻辑，区别只在"取第一个匹配"还是"取全部"。

    `section`（队列 #399 决策点 2 答 (b)）：目标表所属 `##` 章节标题的起首
    字样。**不传时取 `MAIN_TABLE_SECTION`（主表），而不是「文件里第一个
    表」**——后者正是本次退休的隐式判据。章节找不到、或章节内没有含
    「发送状态」列的表，一律 `raise ReadmeTableError`，MUST NOT 返回空列表
    当作「这张表没有数据」（那会让调用方把"读错了对象"读成"今天没活"）。

    表头行：章节区间内第一条以 `|` 开头且含"发送状态"字样的行。表头下一行是
    `|---|---|...` 分隔行，再往下直到第一条非 `|` 开头的行为止都是数据行。
    """
    section = MAIN_TABLE_SECTION if section is None else section
    lines = text.splitlines()
    span_start, span_end = section_span(lines, section)

    header_idx = None
    header_cells: list[str] = []
    status_col_index = -1

    for i in range(span_start, span_end):
        line = lines[i]
        if line.strip().startswith("|") and "发送状态" in line:
            header_cells = _split_row(line)
            for j, cell in enumerate(header_cells):
                if cell.startswith("发送状态"):
                    status_col_index = j
                    break
            header_idx = i
            break

    if header_idx is None or status_col_index < 0:
        raise ReadmeTableError(
            f'章节「## {section}…」内未找到含"发送状态"列的表格'
        )

    rows: list[RowLocation] = []
    for i in range(header_idx + 2, span_end):
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


def locate_row(
    text: str, match: Callable[[list[str]], bool], section: Optional[str] = None
) -> RowLocation:
    """定位指定章节那张表中"发送状态"列所在、且满足 `match(cells)` 的第一行。
    `section` 语义同 `iter_rows`（不传＝主表，且匹配不到章节即抛错）。"""
    for row in iter_rows(text, section):
        if match(row.cells):
            return row
    raise ReadmeTableError("未找到匹配的跟进信行")


def write_status(text: str, loc: RowLocation, new_status: str) -> str:
    """把 `loc` 定位到的行的状态列原子替换为 `new_status`，返回新文本。"""
    return write_cells(text, loc, {loc.status_col_index: new_status})


def write_cells(text: str, loc: RowLocation, updates: dict[int, str]) -> str:
    """把 `loc` 定位到的行的**多个**单元格在**同一次写出**里一起替换。

    🔴 队列 #400（并入 #399）：批准脚本转终态时须**同时**剥掉编号列的
    「（待你审，暂不占号）」括注。分两次写就多出一个「状态改了、括注没改」
    的中间态，**而那正是 #400 这个缺陷本身**——故本函数存在的意义不是省一次
    IO，是让「两格必须一起变」这件事在类型上就无法被拆开。
    """
    lines = text.splitlines()
    cells = loc.cells.copy()
    for idx, value in updates.items():
        cells[idx] = value
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


# 队列 #400（并入 #399）：编号列里「这封信还没真的发出、不占号」的括注。
# 形态实测三种：`采购部#17` ／ `IT部#7（待发，暂不占号）` ／
# `销售部（未发，不编号）`。半角括号一并容忍（README 现无此写法，但成本为零）。
_NUMBER_ANNOTATION_RE = re.compile(r"（[^（）]*）|\([^()]*\)")


def strip_unnumbered_annotation(number_cell: str) -> str:
    """剥掉编号列中表示「未发／不占号」的括注，返回新值；无可剥者原样返回。

    🔴 **只剥括注、不改编号数值**——占号推算（`_next_available_number`）是
    读侧派生行为，写侧不该去动它（design §四）。

    🔴 **无 `<部门>#<数字>` 的单元格一律不动**：`销售部（未发，不编号）` 这类
    行的括注是该格**仅有的信息**，剥掉只会留下一个失去含义的 `销售部`。本
    要求修的是「编号已存在、括注却还说没发」这一种自相矛盾，不是「清理所有
    括注」。

    幂等：剥完再喂一次不产生任何修改（无括注可命中）。
    """
    if parse_letter_number(number_cell) is None:
        return number_cell

    def _drop(m: "re.Match[str]") -> str:
        inner = m.group(0)
        return "" if any(marker in inner for marker in UNNUMBERED_MARKERS) else inner

    return _NUMBER_ANNOTATION_RE.sub(_drop, number_cell).strip()


def build_target_file_annotation(filename: str) -> str:
    """起草新行时追加到"主要事项"列末尾的固定格式片段（队列 #241 修法⑴）。
    只在既有单元格内追加文本，不新增列——不改变表格结构，`_validate_
    followup_readme_release`/`_validate_release_structure`（编辑锁工具的
    列数/身份校验）因此不受影响，无需同步修改。"""
    return f" → 目标文件：`{filename}`"
