"""跟进信「串行闸」判据的权威实现（队列 #366 / S1-S4，2026-08-21）。

## 为什么要有这个模块

`README-跟进机制与命名约定.md` 下表「发送状态」列是**一封信状态的唯一权威源**
（S1，Shao Peishen 2026-08-21 答 §四 #85 选 (b) 确立）。但「什么样的状态算
闭环」这条判据此前**在两处各写了一份、而且两份不一样**：

- README 正文（串行原则段，2026-08-18 修订）写的是**闭环四态**：
  `📥 已回件并回灌` ／ `✅ 无需回复` ／ `📨 已确认闭环` ／ `❌ 已作废`。
- `工具-共享文档编辑锁.py::_validate_followup_readme_release` 的机器判据
  只认 `📥` 一个前缀（`FOLLOWUP_SERIAL_CLOSED_PREFIX`）。

两者不一致的代价是实测过的：质量部#7 形态为 `✅ 无需回复`、**按纪律串行闸
早已打开**，但机器判据不认，起草下一封时只能编一条 `串行豁免：` 去绕过它
——**拿逃生阀去绕它本来要拦的那件事**。根 CLAUDE.md §5 把这条边界原样记了
下来（「⚠️ 但机器判据 … 仍只认 `📥` 前缀，起草时须走 `串行豁免：`」）。

⇒ 本模块把这条判据收敛成**一份**，供三类消费者共用：
`工具-跟进闸查询.py`（读侧派生入口）、`工具-共享文档编辑锁.py`（release
校验）、`aibot_service`（入信桥）。**判据只此一份，不得在消费者侧另写。**

## 与 `queue_table` 的关系

同一个位置、同一套惯例：权威判据落 `zhuopin_platform.shared_tools`，消费者
按 #300 式 `sys.path` 引导 import，隔离环境用兜底桩。理由见 `queue_table.py`
模块文档，本模块不重复。

## 本模块**不**做的事

- 不解析 README 表格结构（那是 `aibot_service.readme_table.iter_rows` 与
  `工具-共享文档编辑锁.py::_followup_readme_rows` 两处既有实现的职责，本
  模块只接收已经切好的单元格文本）。
- 不写任何文件。纯判据、无副作用。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional

# ---------------------------------------------------------------------------
# 一、状态取值
# ---------------------------------------------------------------------------

# 闭环四态（README 串行原则段 2026-08-18 修订版的原文口径）——命中任一即
# 「这封信已经了结」，串行闸对该收信人放行。
#
# 🔴 顺序有意义：`📨 已确认闭环` 必须排在 `REPLY_ARRIVED_STATUS`（同样以
# 📨 开头）之外单独比对，故此处一律按**整串前缀**匹配，不得退化为只比对
# 首个 emoji。
CLOSED_STATUS_PREFIXES: tuple[str, ...] = (
    "📥 已回件并回灌",
    "✅ 无需回复",
    "📨 已确认闭环",
    "❌ 已作废",
)

# 已发出但尚未了结的在途态（列出来是为了让「未知状态」与「已知在途态」
# 可区分——前者说明 README 里出现了本模块没见过的写法，值得报出来，而不是
# 静默当成在途）。
IN_FLIGHT_STATUS_PREFIXES: tuple[str, ...] = (
    "✅ 已推送",
    "✅ 已发",
    "⏳ 待你审",
    "🆕 待发",
    "⏸ 暂缓",
)

# 第九态（S4 桥一，队列 #366 M1）：回件**物理到达**、尚未拆件回灌。
# 语义＝仍属在途、闸仍锁；它的价值是让「回件到了」这件事在权威源上立刻
# 可见，而不必等人拆完件才在 README 上留下任何痕迹。
REPLY_ARRIVED_STATUS = "📨 回件已到，待拆件"

# 串行闸逃生阀标记（与 `工具-共享文档编辑锁.py::FOLLOWUP_SERIAL_WAIVER_MARKER`
# 同一取值；该常量此后从本模块取，编辑锁侧不再自持一份字面量）。
SERIAL_WAIVER_MARKER = "串行豁免："

# S4 桥二逃生阀：拆件已完成但确有理由暂不转闭环态时用。
STATE_SYNC_WAIVER_MARKER = "转态豁免："

# 编号列里表示「这封信还没真的发出、不占号」的括注用词。
UNNUMBERED_MARKERS: tuple[str, ...] = ("未发", "待发", "待你审", "暂不占号", "不编号")

# 归一化时要剥掉的装饰字符：markdown 强调星号、普通空白、全角空格。
# （README 状态列实测写法含 `✅ **无需回复**（…）`、`**❌ 已作废 · 9 月重写**`、
# 以及用全角空格 `　` 分段的 `✅ 已推送 …　🔴 **回件已到…**`。）
_DECORATION_CHARS = "*　 \t"


def normalize_status(status_cell: str) -> str:
    """把状态单元格归一化到「可按前缀比对」的形态。

    只做两件事：① 去掉 markdown 强调星号；② 收敛首尾空白/全角空格。
    **不做任何语义猜测**——归一化后仍不认识的写法一律归入"未知"，由调用方
    显式报出来，而不是悄悄当成在途或闭环。
    """
    return status_cell.replace("*", "").strip(_DECORATION_CHARS)


def is_closed_status(status_cell: str) -> bool:
    """该状态是否属闭环四态之一（＝串行闸对这封信放行）。"""
    normalized = normalize_status(status_cell)
    return any(normalized.startswith(p) for p in CLOSED_STATUS_PREFIXES)


def is_reply_arrived_status(status_cell: str) -> bool:
    """该状态是否为第九态「回件已到，待拆件」。

    ⚠️ 必须先于 `is_closed_status` 的 `📨 已确认闭环` 分支理解：两者同以
    📨 开头，靠整串前缀区分，不得按 emoji 判。
    """
    return normalize_status(status_cell).startswith(REPLY_ARRIVED_STATUS)


def classify_status(status_cell: str) -> str:
    """返回 `"closed"` / `"reply_arrived"` / `"in_flight"` / `"unknown"` 之一。

    `"unknown"` 是刻意保留的第四类：README 里出现本模块没见过的状态写法时，
    调用方 SHOULD 把它显示出来（并按在途处理，即闸仍锁——保守方向），
    MUST NOT 静默归入任何一类。同 CLAUDE.md §5「工具静默回退」那一族教训。
    """
    if is_reply_arrived_status(status_cell):
        return "reply_arrived"
    if is_closed_status(status_cell):
        return "closed"
    normalized = normalize_status(status_cell)
    if any(normalized.startswith(p) for p in IN_FLIGHT_STATUS_PREFIXES):
        return "in_flight"
    return "unknown"


# ---------------------------------------------------------------------------
# 二、编号列
# ---------------------------------------------------------------------------

# 编号列实测三种形态：`采购部#17` ／ `IT部#7（待发，暂不占号）` ／
# `销售部（未发，不编号）`。正则容忍括注（派单件 §一「一个必须处理的边界」）。
_LETTER_NUMBER_RE = re.compile(r"(?P<dept>[一-鿿A-Za-z]+部)#(?P<n>\d+)")


def parse_letter_number(number_cell: str) -> Optional[tuple[str, int]]:
    """从编号列取 `(部门, 序号)`；取不到（如 `销售部（未发，不编号）`）返回
    None。括注一律容忍——只认 `<部门>#<数字>` 这个片段本身。"""
    m = _LETTER_NUMBER_RE.search(number_cell)
    if not m:
        return None
    return m.group("dept"), int(m.group("n"))


def number_cell_claims_unsent(number_cell: str) -> bool:
    """编号列是否自称「还没发、不占号」。"""
    return any(marker in number_cell for marker in UNNUMBERED_MARKERS)


def number_status_mismatch(number_cell: str, status_cell: str) -> bool:
    """编号列与状态列**互相矛盾**：编号列自称「未发／待发／暂不占号」，而
    状态列表明这封信其实早已发出（在途已推送态，或闭环四态里除「已作废」
    之外的三态——已作废的信本就可以不占号，不算矛盾）。

    这正是 README 顶部「下一个可用号」段落连续失真四次的第二个源头：
    2026-08-21 那次校准的原文写着「**失真的不是一处而是两处，且两处会互相
    印证着一起错**」——状态列有 `_validate_followup_readme_release` 看着，
    编号列则一直是纯自由文本、没有任何机器判据覆盖。本函数补的就是那一格。
    """
    if not number_cell_claims_unsent(number_cell):
        return False
    normalized = normalize_status(status_cell)
    if normalized.startswith("❌ 已作废"):
        return False
    kind = classify_status(status_cell)
    if kind == "closed":
        return True
    return normalized.startswith("✅ 已推送") or normalized.startswith("✅ 已发")


# ---------------------------------------------------------------------------
# 三、入信文件名 ↔ 原信文件名
# ---------------------------------------------------------------------------

# `aibot_service.intake._build_filename` 产出的归档文件名形态：
#   <部门>-<发送人>-回复-<YYYY-MM-DD>-<主题>-<disambiguator><ext>
# 其中 <主题> 对 text 类消息恒为字面量 "文本反馈"；对 file 类消息＝专员回传
# 文件的 stem，实测即原信 docx 的 stem（如
# `采购部-姚祖怡-跟进-2026-08-20-SC2采购周报口径判例批改`）。
_TEXT_FEEDBACK_TOPIC = "文本反馈"
_ARCHIVE_NAME_RE = re.compile(
    r"^(?P<dept>[^-]+)-(?P<sender>[^-]+)-回复-(?P<date>\d{4}-\d{2}-\d{2})-"
    r"(?P<topic>.+)-(?P<disambiguator>[0-9a-zA-Z]{6,})$"
)

# 专员回传时常在原 stem 后缀一个「-回复」（实测财务部全部 8 份如此）。
# 这是一条**确定性归一**、不是模糊匹配：剥掉之后仍要求与原信 stem **逐字
# 相等**才算命中，命不中即报未匹配，绝不打分排序取最相似的一个。
_REPLY_SUFFIXES = ("-回复", "-回件")


def extract_reply_source_stem(archive_filename: str) -> Optional[str]:
    """从归档入信文件名里取出「它回的是哪封信」的原信 stem。

    取不到时返回 None，三种情形：① 文件名不符合 `intake` 的命名形态；
    ② 主题段是 `文本反馈`（text 类消息，天然不带原信标题，**无从匹配**）；
    ③ 主题段为空。

    🔴 返回 None **不是**「随便猜一个」的信号，而是「不要动 README」的信号
    ——见派单件 §二「匹配不上时不要猜」。
    """
    stem = archive_filename
    for suffix in (".docx", ".md", ".xlsx", ".pdf", ".doc", ".txt", ".png", ".jpg"):
        if stem.lower().endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    m = _ARCHIVE_NAME_RE.match(stem)
    if not m:
        return None
    topic = m.group("topic").strip()
    if not topic or topic == _TEXT_FEEDBACK_TOPIC:
        return None
    return topic


def normalize_letter_stem(stem: str) -> str:
    """剥掉专员回传时附加的 `-回复`／`-回件` 尾缀，得到可与原信 stem 逐字
    比对的形态。只剥一层，且只剥这两个确定尾缀。"""
    for suffix in _REPLY_SUFFIXES:
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def reply_matches_letter(archive_filename: str, letter_target_filename: str) -> bool:
    """入信归档文件是否**确定地**对应 README 某行标注的目标文件（队列 #241
    的 `目标文件：`xxx.md`` 标注）。

    判据 ＝ 归一化后的 stem **逐字相等**。不做包含、不做编辑距离、不做
    最相似匹配——本函数只回答「是」或「不知道」，永远不回答「大概是」。
    """
    source = extract_reply_source_stem(archive_filename)
    if source is None:
        return False
    target_stem = letter_target_filename
    for suffix in (".md", ".docx"):
        if target_stem.lower().endswith(suffix):
            target_stem = target_stem[: -len(suffix)]
            break
    return normalize_letter_stem(source) == normalize_letter_stem(target_stem)


# ---------------------------------------------------------------------------
# 四、拆件完成 ↔ README 转态 的配对（S4 桥二判据核心）
# ---------------------------------------------------------------------------
#
# 🔴 本节**只做纯配对**，不解析任何文件。两个消费者各自用自己已有的解析器
# 把行读出来喂进来：`工具-共享文档编辑锁.py` 用 `_followup_readme_rows` ＋
# `_table_data_rows`，`工具-跟进闸查询.py` 用 `aibot_service.readme_table`
# ＋ 同一套队列解析。**判据一份、解析各自**——这正是本仓库既有的分工惯例
# （见 `queue_table.py` 与 `_followup_readme_rows` 两处 docstring）。


@dataclass(frozen=True)
class IntakeRecord:
    """队列 §一 里由企微机器人自动追加的一条入信行（已由调用方解析好）。"""

    row_id: str
    queue_file: str
    archived_filename: str
    dismantled: bool          # 状态列是否已 `[S:done]`（＝已拆件回灌）


@dataclass(frozen=True)
class LetterRecord:
    """README「现有跟进信清单」的一行（已由调用方解析好）。"""

    number: str
    target_filename: Optional[str]   # 队列 #241 的 `目标文件：`xxx.md`` 标注
    status: str


@dataclass(frozen=True)
class UnsyncedLetter:
    letter: LetterRecord
    intakes: tuple[IntakeRecord, ...]

    def describe(self) -> str:
        ids = " / ".join(f"§一 #{i.row_id}" for i in self.intakes)
        return (
            f"{ids} 已拆件（[S:done]），但 README「{self.letter.number}」仍为"
            f"「{normalize_status(self.letter.status)[:40]}」。"
            f"请先转闭环态（{'／'.join(CLOSED_STATUS_PREFIXES)}）再 release，"
            f"或在本次改动里写明「{STATE_SYNC_WAIVER_MARKER}〈理由〉」。"
        )


def find_unsynced_letters(
    intakes: Iterable[IntakeRecord],
    letters: Iterable[LetterRecord],
) -> list[UnsyncedLetter]:
    """找出「回件已拆件、README 却还没转闭环态」的信。

    配对只走 `reply_matches_letter`（归一化后 stem 逐字相等）——**匹配不上
    就不配对，绝不猜**。因此：

    - 文本反馈类入信（文件名主题段恒为 `文本反馈`）**永远配不上任何信**，
      本函数对它们零输出。这是设计取舍不是缺陷：一条纯文本回件无法确定地
      指向哪一封信，硬配会造出比漏配更难发现的错误。
    - README 行没有 `目标文件：` 标注（队列 #241 之前的历史行，实测 49 行
      里只有 14 行有）同样配不上，零输出。

    ⇒ **本判据只覆盖"能被确定配对"的那部分，覆盖率是它的已知边界。**
      调用方 SHOULD 在文案里说明这一点，不得让读者以为"没报违规＝全同步"。
    """
    letters = [ln for ln in letters if ln.target_filename]
    dismantled = [i for i in intakes if i.dismantled]
    results: list[UnsyncedLetter] = []
    for letter in letters:
        if is_closed_status(letter.status):
            continue
        matched = tuple(
            i for i in dismantled
            if reply_matches_letter(i.archived_filename, letter.target_filename or "")
        )
        if matched:
            results.append(UnsyncedLetter(letter=letter, intakes=matched))
    return results
