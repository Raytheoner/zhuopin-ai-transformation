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

# 🔴 「尚未发出」的三态（`OP-0823-D` 新增）——它是 `IN_FLIGHT_STATUS_PREFIXES`
# 的真子集，但语义完全不同，**必须单独成一份**：
#
# 「在途」在本仓库一直混着两件事——「已经发出去、等着回」与「还没发出去」。
# 判「回件该配哪封信」时只有前者算数：一封 `⏳ 待你审` 的草稿不可能收到回件。
# 派单件 §3.1 只点名了 `⏳ 待你审`，此处一并纳入 `🆕 待发`（已批准、等轮巡
# 投递）与 `⏸ 暂缓`（内容已审、主动不发）——**三者的共同事实是「专员那边
# 还没看到这封信」**，把其中任何一个漏掉，都会让机器去配一封对方根本没
# 收到的信。
NOT_YET_SENT_STATUS_PREFIXES: tuple[str, ...] = (
    "⏳ 待你审",
    "🆕 待发",
    "⏸ 暂缓",
)

# ---- 配对通道标识（`OP-0823-D`）。定义在此而不是 §五，是因为 §四 的
# `UnsyncedLetter` 用它做字段默认值，而模块体是自上而下求值的。 ----
PAIR_CHANNEL_STEM = "stem"                    # 文件名 stem 逐字相等（确定性最高）
PAIR_CHANNEL_LATEST = "latest"                # 该收信人最新一封已发出的信（仅桥一用）
PAIR_CHANNEL_REPLY_ARRIVED = "reply_arrived"  # 第九态单元格里的溯源回指（仅桥二用）

# 未命中的三种原因（**都要能被区分**——处置级别不同：前两种 fail-loud
# WARN，第三种是预期内常态、只能低噪，见 `PairingOutcome.is_expected_quiet`）
PAIR_MISS_NO_DEPARTMENT = "no_department"         # 收信人解析不出
PAIR_MISS_NO_DISPATCHED = "no_dispatched_letter"  # 该收信人一封已发出的信都没有
PAIR_MISS_LATEST_CLOSED = "latest_closed"         # 🔴 最新一封已闭环 ＝ 闭环后的补充说明

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


def is_not_yet_sent(status_cell: str) -> bool:
    """该状态是否表示「这封信还没发到专员手里」（草稿／待投递／主动暂缓）。"""
    normalized = normalize_status(status_cell)
    return any(normalized.startswith(p) for p in NOT_YET_SENT_STATUS_PREFIXES)


def is_dispatched(status_cell: str) -> bool:
    """该信是否**已经发出去了**（＝专员那边看得到它）。

    🔴 定义为 `not is_not_yet_sent`，而不是「命中某个已发前缀」——**未知
    写法必须算已发出**。理由是两个方向的代价不对称：把一封已发出的信误判
    为未发出，会让它在「最新一封」的排序里被跳过，于是回件被配到更早的
    另一封信上，**错得悄无声息**；反过来把一封草稿误判为已发出，最坏结果
    是配到一封没人收到的信，人拆件时一眼就能看出来。同 `classify_status`
    对 `"unknown"` 的处理方向（保守 ＝ 闸仍锁），此处保守 ＝ 仍算在排序里。
    """
    return not is_not_yet_sent(status_cell)


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


def reply_arrived_cites(status_cell: str, archive_filename: str) -> bool:
    """该状态是否为第九态、且**溯源写的正是这份归档件**。

    这是桥一 → 桥二之间那条**确定性回指**：桥一在回件到达那一刻完成配对
    （那时才有"这条刚到的回件属于该收信人当前那封信"这个时间上下文），并把
    归档文件名原样写进第九态单元格；桥二事后只是把它读回来。

    🔴 **为什么桥二不能自己再跑一次通道②**：桥二在每次 `release` 时扫全部
    历史入信行，**没有任何时间上下文**。一条 7 月的 `[S:done]` 入信行按
    「该部门最新一封已发出的信」去配，会配到今天刚发出、根本还没人回的那
    封信上，并把它自动闭环——**错得悄无声息，且会开错闸**。实测反例：
    `财务部#14` 的回件与 `财务部#15` 的发出**同为 2026-08-23**，连按日期
    加护栏都挡不住。⇒ 桥二只认两条**确定**通道：stem 逐字相等，与本函数。
    """
    if not is_reply_arrived_status(status_cell):
        return False
    return bool(archive_filename) and archive_filename in status_cell


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
    # 本封是靠哪条确定通道配上的：`stem`（文件名逐字相等）／
    # `reply_arrived`（第九态单元格里的溯源回指，由桥一在到达时写下）。
    channel: str = PAIR_CHANNEL_STEM

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

    配对走**两条确定通道**，两条都是「对上就是对上、对不上就不配」，
    **绝不猜**（`OP-0823-D` 之前只有第一条）：

    1. `reply_matches_letter` —— 归一化后 stem 逐字相等；
    2. `reply_arrived_cites` —— 该信当前是第九态，且单元格里的溯源归档
       文件名正是这一份。**这条把纯文字回件第一次纳入了覆盖面**：它们配不上
       stem，README 行也多半没有 `目标文件：` 标注，此前永远漏在外面；现在
       由桥一在到达那一刻把配对结论写进单元格，本函数读回来即可。

    🔴 **本函数刻意不跑「该收信人最新一封已发出的信」那条通道**——理由见
    `reply_arrived_cites` 的红字：本函数扫的是全部历史入信行，**没有时间
    上下文**，按位置配会把今天刚发出、还没人回的信自动闭环。

    ⇒ **已知边界**：桥一没跑成（服务停摆／锁忙三次用尽）的那些纯文字回件，
      两条通道都对不上，本函数对它们零输出。调用方 SHOULD 在文案里说明这
      一点，不得让读者以为"没报违规＝全同步"。
    """
    dismantled = [i for i in intakes if i.dismantled]
    results: list[UnsyncedLetter] = []
    for letter in letters:
        if is_closed_status(letter.status):
            continue
        by_stem = tuple(
            i for i in dismantled
            if letter.target_filename
            and reply_matches_letter(i.archived_filename, letter.target_filename)
        )
        # `OP-0823-D` 第二条确定通道：桥一在回件到达那一刻写下的溯源回指。
        # 它让**纯文字回件**第一次进入桥二的覆盖面——此前这类回件既配不上
        # stem、README 行也多半没有 `目标文件：` 标注，于是永远漏在外面。
        by_backlink = tuple(
            i for i in dismantled
            if i not in by_stem
            and reply_arrived_cites(letter.status, i.archived_filename)
        )
        matched = by_stem + by_backlink
        if matched:
            results.append(UnsyncedLetter(
                letter=letter, intakes=matched,
                channel=(PAIR_CHANNEL_STEM if by_stem else PAIR_CHANNEL_REPLY_ARRIVED),
            ))
    return results


# ---------------------------------------------------------------------------
# 五、回件 ↔ 跟进信 两级配对（`OP-0823-D`，队列 #366）
# ---------------------------------------------------------------------------
#
# ## 本节替代了什么
#
# 原判据只有一级：`reply_matches_letter`（stem 逐字相等），**配不上就不动**。
# 该取舍的理由曾经成立（一条文本回件无法确定地指向哪封信），但后果是实测
# 到的：凡专员用纯文字而不是回传 docx，README 那一格就永远靠人改，最久积压
# 20 天以上。
#
# ## 为什么后备通道是「最新一封已发出的信」而不是「唯一在途的信」
#
# 🔴 **这一条是本节最该被记住的**：跟进闸的判据是「**该收信人最近一封是否
# 已闭环**」——**只看最新一封**。若配对改用「所有未闭环的信恰好一封」，那
# 是**第三种「在途」定义**，与闸不是同一把尺子 ⇒ 必然出现「配上了但闸没开」
# 或反过来。
#
# 而且它在生产数据上**恒不成立**：2026-08-23 实测四位收信人各有 7／6／4／4
# 封已发出未闭环的历史信（多为 2026-07-31 编号体系建立前，状态列从未维护），
# 「恰好一封」一次都不会命中 ⇒ 按它实现，机制上线当天就是哑的。
#
# ⇒ 「所有未闭环」这个量**不作废、但换位置**：降级为
# `unclosed_dispatched_by_department` 健康检查，只报数，不参与任何转态判定，
# **不得阻塞配对**。

@dataclass(frozen=True)
class LetterRow:
    """README「现有跟进信清单」的一行，带够做配对与排序的全部字段。

    与上一节的 `LetterRecord` 并存而不合并：那个是桥二既有校验的入参形态
    （只需编号／目标文件／状态），本节的配对还要用到收信人、日期与表内行序。
    强行合并会改掉 `find_unsynced_letters` 的对外签名，而那个函数有两个
    现役消费者与一条 CI 断言（`工具-队列结构lint.py` 盯着符号存在性）。
    """

    number: str
    date: str
    recipient: str
    target_filename: Optional[str]
    status: str
    order: int  # 在表格里的物理次序，仅作排序末位决胜用

    @property
    def department(self) -> Optional[str]:
        return recipient_department(self.recipient)


def normalize_department(department: Optional[str]) -> str:
    """部门名归一化：剥掉尾字「部」。

    🔴 这不是洁癖，是一处真实的不对齐：`department_mapping.yaml` 里陈承那
    一行的取值是 `IT`（不带「部」），而 README 收信人列写的是 `IT部 · 陈承`。
    直接字符串比对会让 IT 域的回件**一封都配不上**，且不报任何错。
    """
    value = (department or "").strip()
    return value[:-1] if value.endswith("部") and len(value) > 1 else value


def recipient_department(recipient_cell: str) -> Optional[str]:
    """从 README 收信人列取归一化后的部门名；取不到返回 None。

    实测形态：`采购部 · 姚祖怡`／`采购部 · 姚祖怡（+团队）`／
    `质量部 · 陈忱（可分担朱映桦）`／`采购部 · 姚祖怡（转汤易水第④项）`。
    括注一律忽略——它标的是「谁可以分担」，不改变这封信是写给谁的。
    """
    if "·" not in (recipient_cell or ""):
        return None
    department = recipient_cell.split("·", 1)[0].strip()
    normalized = normalize_department(department)
    return normalized or None


def _letter_sort_key(row: LetterRow) -> tuple:
    """「最新」的排序键 ＝（日期, 编号序号, 表内行序）。

    三个字段都需要，缺一不可：
    - **日期**为主（ISO 形态 `2026-08-18`，字典序即时间序）；
    - **编号**决胜同日多封（实测 `采购部#15`／`#16` 同为 2026-08-18）；
    - **表内行序**兜底无编号行（`采购部（未发，不编号）`）与两者都相同的情形。

    ⚠️ **不能只按表内行序**：实测 `采购部#4`（07-21）排在表格倒数第二行、
    位于 `采购部#17`（08-20）之后——README 的物理行序不是时间序。
    """
    parsed = parse_letter_number(row.number)
    return ((row.date or "").strip(), parsed[1] if parsed else -1, row.order)


def latest_dispatched_letter(
    rows: Iterable[LetterRow], department: Optional[str]
) -> Optional[LetterRow]:
    """该部门**最新一封已发出**的信；一封都没有则 None。

    「已发出」＝ `is_dispatched`（排除 `⏳ 待你审`／`🆕 待发`／`⏸ 暂缓`）。
    **与跟进闸同一把尺子**——闸判的也是「最近一封是否闭环」。
    """
    target = normalize_department(department)
    if not target:
        return None
    candidates = [
        r for r in rows
        if r.department == target and is_dispatched(r.status)
    ]
    if not candidates:
        return None
    return max(candidates, key=_letter_sort_key)


@dataclass(frozen=True)
class PairingOutcome:
    channel: str
    letter: Optional[LetterRow]
    detail: str

    @property
    def matched(self) -> bool:
        """🔴 按**通道**判，不按 `letter is not None` 判。

        `PAIR_MISS_LATEST_CLOSED` 也带着 `letter`（好让调用方能说出「是哪封
        信已闭环」），但它是**未命中**。用 `letter is not None` 当命中判据，
        会把「闭环后的补充说明」当成一次真配对去改 README——单测
        `test_最新一封已闭环则不动README且只低噪` 当场抓到过这个形态。
        """
        return self.channel in (
            PAIR_CHANNEL_STEM, PAIR_CHANNEL_LATEST, PAIR_CHANNEL_REPLY_ARRIVED,
        )

    @property
    def is_expected_quiet(self) -> bool:
        """本次未命中是否属**预期内常态**（⇒ 只记审计＋低噪，不得告警）。

        闭环后专员再补一条说明是常规操作（派单件 §3.3）；把它按告警报出去，
        等于每条补充说明制造一次假警报，而那正是「误报训练人忽略告警」。
        """
        return self.channel == PAIR_MISS_LATEST_CLOSED


def pair_reply_to_letter(
    *,
    archive_filename: str,
    department: Optional[str],
    rows: Iterable[LetterRow],
) -> PairingOutcome:
    """一条回件该配哪封信——两级通道，第一级命中即止。

    ① **stem 精确匹配**（确定性最高）：命中即配那封，**不进 ②**，也**不看
       部门**——文件名逐字对上已经足够确定，且这样能逐字保住改造前的既有
       行为，不制造净回归。
    ② **后备**：该收信人**最新一封已发出的信**。不看文件名、不看正文，
       **docx 与纯文字一视同仁**（派单件 §3.1）。

    未命中的三种原因分开返回，因为它们的处置级别不同：`LATEST_CLOSED` 是
    预期内常态（低噪），另两种是 fail-loud 的 WARN。
    """
    rows = list(rows)

    for row in rows:
        if row.target_filename and reply_matches_letter(
            archive_filename, row.target_filename
        ):
            return PairingOutcome(
                PAIR_CHANNEL_STEM, row,
                f"通道①stem：归档件 `{archive_filename}` 与「{row.number}」的"
                f"目标文件 `{row.target_filename}` 逐字相等。",
            )

    target = normalize_department(department)
    if not target:
        return PairingOutcome(
            PAIR_MISS_NO_DEPARTMENT, None,
            f"归档件 `{archive_filename}` 的收信人部门解析不出"
            f"（传入 {department!r}）——未改 README。",
        )

    latest = latest_dispatched_letter(rows, target)
    if latest is None:
        return PairingOutcome(
            PAIR_MISS_NO_DISPATCHED, None,
            f"「{target}」在 README 中一封已发出的信都没有"
            f"（草稿／待发／暂缓不算），归档件 `{archive_filename}` 未改 README。",
        )
    if is_closed_status(latest.status):
        return PairingOutcome(
            PAIR_MISS_LATEST_CLOSED, latest,
            f"「{target}」最新一封已发出的信「{latest.number}」已闭环"
            f"（{normalize_status(latest.status)[:24]}）——按 §3.3，闭环后到达的"
            f"补充说明只落档、不改状态列、不重开在途。",
        )
    return PairingOutcome(
        PAIR_CHANNEL_LATEST, latest,
        f"通道②最新一封：「{target}」最新一封已发出且未闭环的信是"
        f"「{latest.number}」（{latest.date}）。",
    )


def unclosed_dispatched_by_department(
    rows: Iterable[LetterRow],
) -> dict[str, list[LetterRow]]:
    """§3.1bis 健康检查：各部门「已发出且未闭环」的信有几封。

    🔴 **只报数。MUST NOT 参与任何转态判定，MUST NOT 阻塞配对。**
    它在这里的唯一用途是让「某位专员名下堆了 7 封从未闭环的历史信」这件事
    可见——那是账没维护好，不是回件配不上的理由。
    """
    grouped: dict[str, list[LetterRow]] = {}
    for row in rows:
        dept = row.department
        if not dept or not is_dispatched(row.status):
            continue
        if is_closed_status(row.status):
            continue
        grouped.setdefault(dept, []).append(row)
    for items in grouped.values():
        items.sort(key=_letter_sort_key)
    return grouped
