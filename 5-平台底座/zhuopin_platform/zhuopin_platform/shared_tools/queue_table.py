"""跨桌任务队列表格解析权威模块 · 转义与列数校验（队列 #306＋#307）。

背景：跨桌任务队列.md 的"按竖线切列＋取某一列语义"这一解析逻辑，历史上
曾在至少 7 处各自独立实现，且 `工具-队列查询.py` 文件头一度把这种重复
正当化为"本项目一贯做法"（理由是本目录多个 `.py` 文件名含中文/连字符、
不是标准可 import 的模块路径——该理由已被证伪，`zhuopin_platform` 本就
是 `pip install -e` 的可安装包，见 #307）。队列 #308（状态机器字段，
2026-08-09 apply 落地）从根本上消解了这七份实现里最重的两件事——①列
语义解析、③开头片段提取——消费者此后只需读一个定长的 `[S:...][D:...]`
前缀字段，不再需要理解 8 列各是什么语义。Shao Peishen 2026-08-08 拍板
措施 A：原定要建的"权威解析器"大工程降级为 P3、缩范围为本模块承载的
两件事，完整决策记录见 openspec 变更包
`queue-table-shared-parser-consolidation`。

本模块**原不**承载①表格切分/列语义解析或③开头片段提取——这两件事
曾随 #308 的状态机器字段作废/大幅萎缩，一度交各消费者按需继续各自独立
按 `|` 切分表格行。**队列 #314 起，①表格切分的其中一个子问题（反引号
感知）已收拢进本模块**（见下方"队列 #314"段），③开头片段提取仍不在
本模块权威化范围内、仍各消费者独立实现（同项目既有惯例：判据独立实现、
不跨 `0-学习与工具/*.py` 互相 import，理由见 `工具-队列查询.py` 文件头）。

队列 #313 追加第④件事——队列文件自身相对路径 `QUEUE_PATH_REL`：
`工具-共享文档编辑锁.py`／`工具-队列查询.py`／`工具-文档台账生成.py`
三处此前各自硬编码同一个字符串字面量（"队列路径"，与仓库根解析是两回
事）。收拢范围**只这 3 处**——`工具-落库sweep.py` 也有一份独立的
`QUEUE_REL` 字面量（第 4 处），但 #313 派单件明确点名的是前 3 处，
本次未纳入，如实登记见队列 #313 回写。仓库根解析（10 处，各工具自行
拼出仓库根目录，与"队列文件在仓库根下的哪个相对路径"是不同层面的
关注点）同样不在本次范围内。

队列 #314：新增反引号感知切列（`split_row_cells`）与"列数不变式收进
解析入口"（`parse_section_rows`），openspec 变更包
`queue-table-backtick-aware-split`。背景——#313 行的真实破损（`git grep`
的正则交替符——用反引号包裹的一段代码示例，内含连接两个搜索关键词的
半角竖线——被朴素 `str.split("|")` 当作列分隔符撑破）暴露出本模块此前
只做"转义/列数校验两件小事"，切列本身仍是 4 处消费者各自独立的朴素
实现，对 Markdown 表格规范允许的"反引号内的竖线是字面量、不算列分隔符"
这一约定完全无感知。本次新增两个函数把这一子问题收拢进来，`has_bare_pipe`
的"反引号包裹不豁免"既有语义不变（服务不同问题：能不能写入，不是该
不该被当分隔符）。
"""
from __future__ import annotations

# 跨桌任务队列.md 各分区标准列数（含编号列，若该分区有编号列）——
# §一"任务看板"8 列／§二"待 commit 批次"4 列／§四"需 Shao Peishen
# 的动作"4 列。三个分区名与既有各消费者的叫法一致（中文数字，非阿拉伯
# 数字），供多处消费者引用同一份常量而非各自硬编码。
SECTION_COLUMN_COUNTS: dict[str, int] = {"一": 8, "二": 4, "四": 4}

# 队列 #313：队列文件自身相对仓库根的路径（POSIX 分隔符——`pathlib.Path`
# 的 `/` 运算符在 Windows 上同样能正确解析正斜杠字符串，消费者按需
# `REPO_ROOT / QUEUE_PATH_REL` 或直接当字符串使用均可）。
# 队列 #315（apply，2026-08-11）：物理拆分为两份文件后，`QUEUE_PATH_REL`
# 本身转为纯指针文件（不再是权威内容承载），保留路径不变、不删除，避免
# 历史引用（归档件/CLAUDE.md/规划文档）404。真正的内容分别落在下面两份。
QUEUE_PATH_REL = "1-转型规划/0-全景路线图/跨桌任务队列.md"

# 协议〇（十条协议正文）／§三（口径冻结标）／§四（需 Shao Peishen 的动作）／
# 编号高水位线声明，均归属本文件——它们体量小、跨域适用（design.md 决策点1）。
QUEUE_MECHANISM_PATH_REL = "1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md"
# §一/§二 中 [D:业] 域的行落此文件；§二 批次的域判定＝物理文件位置本身，
# 不新增字段（design.md 决策点3）。
QUEUE_BUSINESS_PATH_REL = "1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md"

_DOMAIN_TO_PATH: dict[str, str] = {
    "机": QUEUE_MECHANISM_PATH_REL,
    "业": QUEUE_BUSINESS_PATH_REL,
}


def resolve_queue_path(domain: str) -> str:
    """按域返回对应物理队列文件的仓库相对路径（队列 #315 决策点4）。

    `domain` 仅接受 `"机"`／`"业"`；其它取值 fail-loud（抛异常），不静默
    返回默认路径——与 #308 已确立的"非静默降级"原则一致，调用方传入非法
    域值属编程错误，不是需要容错的运行时输入。
    """
    try:
        return _DOMAIN_TO_PATH[domain]
    except KeyError:
        raise ValueError(
            f"未知域值 {domain!r}，仅接受 \"机\"／\"业\"（不静默回退任一份文件）"
        ) from None


def iter_queue_paths() -> list[str]:
    """返回两份物理队列文件的仓库相对路径，供需要"读取全部队列内容"的
    消费者（sweep 起跑段扫描、台账生成、值周巡检等）遍历，替代此前假设
    "只有一份队列文件"的遍历逻辑（队列 #315 决策点4）。"""
    return [QUEUE_MECHANISM_PATH_REL, QUEUE_BUSINESS_PATH_REL]


def has_bare_pipe(cell: str) -> bool:
    """判定字段值中是否含半角竖线 `|`（未转义即会撑列/致列偏移）。

    只做最朴素的子串检测，不做反引号感知——本项目现有表格解析对反引号
    无感知，即便竖线被反引号包裹也一样会被切列（`工具-共享文档编辑锁.py
    ::_cell_has_bare_pipe` 既有文档已说明这一点，本函数与其口径一致）。
    """
    return "|" in cell


def escape_bare_pipe(text: str) -> str:
    """写侧半角竖线 → 全角 `／`（队列 #164 已确立并在生产队列文件实际
    使用过的转义口径：六行历史正文的裸竖线即按此改写）。

    ⚠️ 本项目并存两种"竖线不能直接进单元格"的处理惯例，本函数只服务
    其中一种，调用前须确认场景匹配：
    - **#164 口径（本函数）**：事后修复"已落库的正文里出现裸竖线"——
      把 `|` 替换为全角 `／`，静默转换后继续使用，适合批量清理历史行、
      或程序化生成的说明性文字需要提及竖线本身时。
    - **`append-row` 口径（不同函数，见编辑锁 `_cell_has_bare_pipe`）**：
      写入那一刻直接**拒绝**含裸竖线的字段值，提示改用全角『｜』或改写
      措辞，不做自动转义——那是刻意的设计（"拒绝而非静默改写"，逼调用
      方自己决定怎么改），本函数不应被接入 `append-row` 路径替代其拒绝
      语义。
    """
    return text.replace("|", "／")


def column_count_ok(section: str, cells: list[str]) -> bool:
    """判定给定分区的一行单元格数是否符合该分区标准列数
    （`SECTION_COLUMN_COUNTS`）。

    未知分区名返回 `True`——本函数只对已登记的三个分区（一/二/四）做
    断言，不猜测未来新增分区应有几列，交调用方自行处理未知分区。
    """
    expected = SECTION_COLUMN_COUNTS.get(section)
    if expected is None:
        return True
    return len(cells) == expected


# 队列 #314：反引号跨度识别——按 CommonMark code span 规则（反引号
# **游程**开合，闭合游程须与开启游程长度完全一致），不是简单的
# `` `[^`]*` `` 单反引号配对正则。
#
# apply 阶段真实数据踩坑记录（design.md 决策点 1 的原定方案在此处修正，
# 不是纸面推演）：最初按 design.md 决策点 1 直接复用
# `工具-共享文档编辑锁.py::BACKTICK_SPAN_RE`（单反引号正则），对当前
# 生产队列文件跑任务 3.2 的新旧切列 diff 时，真实命中 §二 批次
# `B-0809_312可Open池立行与接力收工` 的"文件清单"列从 4 列被错误合并成
# 3 列——该列正文用 CommonMark 标准写法（双反引号游程，专门用于包裹
# "内容本身含单个反引号"的文本，本例是在描述"字符串里的反引号被吃掉"
# 这件事本身）：单反引号正则把这类双反引号游程里的每个反引号都当成
# 独立的配对边界，游程配对全部错位，导致后续所有竖线（含真正的列分
# 隔符）保护范围全部漂移。**这不是理论风险，是 2026-08-09 真实生产数据
# 实测坐实的缺陷**，故改为下方 `_mask_backtick_spans`——手写扫描而非
# 正则，逐字符找"同长度反引号游程"配对，忠实复刻 CommonMark 规则；找
# 不到同长度闭合游程的开启游程视为普通文本（等同 Markdown 渲染器对
# "落单/无匹配反引号"的既有处理，design.md 决策点 1 关于"未闭合情形是
# 期望行为"的论证依然成立，只是配对算法本身升级为游程感知）。
_PROTECTED_PIPE_SENTINEL = ""


def _mask_backtick_spans(s: str) -> str:
    """按 CommonMark 规则扫描 `s`，把反引号 code span 跨度内的竖线替换
    为 `_PROTECTED_PIPE_SENTINEL`，返回等长（跨度外原样、跨度内竖线被
    替换）的字符串。非跨度部分与原字符串逐字符一致，供调用方按 `|`
    切分。"""
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        if s[i] != "`":
            out.append(s[i])
            i += 1
            continue
        j = i
        while j < n and s[j] == "`":
            j += 1
        run_len = j - i
        k = j
        close_start = -1
        close_end = -1
        while k < n:
            if s[k] != "`":
                k += 1
                continue
            k2 = k
            while k2 < n and s[k2] == "`":
                k2 += 1
            if k2 - k == run_len:
                close_start, close_end = k, k2
                break
            k = k2
        if close_start == -1:
            # 找不到同长度闭合游程——开启游程本身视为普通文本（同
            # Markdown 渲染器对未闭合反引号的处理），照原样输出后继续。
            out.append(s[i:j])
            i = j
        else:
            span = s[i:close_end]
            out.append(span.replace("|", _PROTECTED_PIPE_SENTINEL))
            i = close_end
    return "".join(out)


def split_row_cells(line: str) -> list[str] | None:
    """反引号感知切列——把一行 Markdown 表格文本切分为单元格列表；反引号
    跨度内的竖线 `|` 不被当作列分隔符（跨度识别按 CommonMark 反引号游程
    规则，见 `_mask_backtick_spans`）。

    行不以 `|` 开头返回 `None`（不是一条表格行）。行不以 `|` 结尾**不**
    导致返回 `None`——沿用队列 #314① 的教训（`工具-共享文档编辑锁.py::
    _table_data_rows` 曾因误要求"行首行尾都必须是 `|`"，把结尾被外部
    工具截断的行静默排除在返回结果之外，连列数校验都没机会跑，见该函数
    docstring 的完整实测记录）：结构本身已经损坏的行，仍应被切出单元格
    交调用方通过列数校验发现异常，不得在切分这一步就静默丢弃。
    """
    s = line.strip()
    if not s.startswith("|"):
        return None
    protected = _mask_backtick_spans(s)
    cells = [
        c.replace(_PROTECTED_PIPE_SENTINEL, "|").strip()
        for c in protected.strip("|").split("|")
    ]
    return cells


_TABLE_HEADER_OR_SEPARATOR_FIRST_CELLS = ("#", "批次", "")


def parse_section_rows(
    section_text: str, section: str,
) -> list[tuple[str, list[str], bool]]:
    """逐行调用 `split_row_cells` 解析给定分区正文，跳过表头/分隔行，
    为每条数据行返回 `(原始行文本, 单元格列表, 列数是否符合该分区标准
    列数)` 三元组——把"这一行列数对不对"这件事收进解析入口本身，调用方
    不需要另外记得调用 `column_count_ok`。

    复用 `column_count_ok` 完成列数判定，不重新实现列数比较逻辑。
    """
    rows: list[tuple[str, list[str], bool]] = []
    for line in section_text.splitlines():
        cells = split_row_cells(line)
        if cells is None:
            continue
        first = cells[0] if cells else ""
        if first in _TABLE_HEADER_OR_SEPARATOR_FIRST_CELLS:
            continue
        if set(first) <= {"-", " "}:
            continue
        rows.append((line, cells, column_count_ok(section, cells)))
    return rows


# ---------------------------------------------------------------------------
# 队列 #414（2026-08-26）：按列名写入 ＋ 全入口共用的单元格校验
#
# 成因＝2026-08-25／26 两天内同一族事故 5 次，三种外形共一个共同点——
# **内容落错结构位、且不报错**：
#   ① 裸竖线撑列（内容变成列分隔符）
#   ② 反引号被 bash 执行（内容变成命令）
#   ③ 列位数错（内容落进相邻格；错到编号格时行头断裂，grep 与队列查询双双
#      找不到该行）
# ① 已有守卫（`has_bare_pipe`，`append-row` 会当场拒绝），但**只守住走正门
# 的人**：直接改队列文件的路径（python 插行、整文件重写）完全绕过它。
# ⇒ 本段做两件事：
#   **B（绕过侧）** `validate_row_cells` —— 把校验抽成可被所有写盘路径复用
#   的单一函数，凡写盘前一律调它，守卫不再依赖「调用方走了哪条路」。
#   **C（列位侧）** `SECTION_COLUMN_NAMES` / `resolve_column_index` /
#   `build_row_cells` —— 按列名定位，使调用方永远不必数下标。
#   A（JSON 入口，正文不进 argv）在 `工具-共享文档编辑锁.py` 侧实现，
#   因为它是 CLI 层的事。
#
# 🔑 判据（比这三条修法本身更要紧）：**一道已经存在且有效的守卫，会因为存在
# 一条绕过它的常用路径而形同虚设**——同族＝「告警机制建成 9 天、每天在跑，
# 却从来没有真正发出过一条消息」（OP-0819-F）。故 B 的落点不是「再加一道
# 校验」，而是「把入口收敛到同一个函数上」。
# ---------------------------------------------------------------------------

# 各分区表头列名（按列序，含编号列）——与生产队列文件表头逐字一致。
# 改表头须同步改这里；`header_mismatch` 供 lint 作机器守，不靠人记。
SECTION_COLUMN_NAMES: dict[str, tuple[str, ...]] = {
    "一": ("#", "任务", "领取方", "输入（指针）", "期望产出", "状态", "触碰区", "登记"),
    "二": ("批次", "文件清单", "建议 message", "状态"),
    "四": ("#", "事项", "等谁", "截止"),
}

# 列名别名——调用方手写列名时的常见等价写法。刻意只收**无歧义**的别名；
# 同一别名在不同分区指向不同列（如「状态」在 §一 是第 6 列、§二 是第 4 列）
# 由 `resolve_column_index` 按分区各自解析，不在此处消歧。
_COLUMN_ALIASES: dict[str, str] = {
    "输入指针": "输入（指针）",
    "输入": "输入（指针）",
    "编号": "#",
    "行号": "#",
    "产出": "期望产出",
    "领取": "领取方",
    "建议message": "建议 message",
    "建议 commit message": "建议 message",
    "message": "建议 message",
}


class QueueCellError(ValueError):
    """单元格校验失败——写盘前抛出，调用方据此不写入任何内容。

    同 `工具-共享文档编辑锁.py::AppendRowFailedError` 的 fail-loud 原则：
    宁可让调用方明确知道，也不可写进一个可能已损坏的行。
    """


def resolve_column_index(section: str, name: str) -> int:
    """把列名解析为该分区内的列下标（0 起，含编号列）。

    🔴 这是 #414 修复面 C 的核心：**调用方永远不必数下标**。历史上第 3、4
    次事故正是数错下标——把收工叙述写进触碰区格、把「✅ 已完成」写进期望
    产出格而状态列始终停在 [S:open]，机器读状态列 ⇒ 一直认为任务没做完。

    未知分区或未知列名一律 fail-loud（抛 `QueueCellError` 并列出该分区的
    合法列名），不猜、不静默回退到某个下标——静默猜错正是本函数要消灭的
    那个失效形态。
    """
    names = SECTION_COLUMN_NAMES.get(section)
    if names is None:
        raise QueueCellError(
            f"未知分区 {section!r}，仅支持 {sorted(SECTION_COLUMN_NAMES)}"
        )
    key = name.strip()
    canonical = _COLUMN_ALIASES.get(key, key)
    try:
        return names.index(canonical)
    except ValueError:
        raise QueueCellError(
            f"§{section} 无列名 {name!r}；合法列名："
            + "、".join(names)
            + "（别名：" + "、".join(sorted(_COLUMN_ALIASES)) + "）"
        ) from None


def _numbered_section(section: str) -> bool:
    """该分区首列是否为行编号列（§一/§四 是；§二 首列是批次号）。"""
    return SECTION_COLUMN_NAMES.get(section, ("",))[0] == "#"


# 🔴 **「按字样识别 shell 污染」已被实测否决，刻意不实现**（2026-08-26）。
#
# 队列 #414 行内建议 ⑶ 原文要求：「疑似被 shell 污染的痕迹（如整格为空、含
# `Is a directory`／`command not found`、或含多行路径列表）即告警」。本次照此
# 实现后**对当前生产队列实测，5 行全部误报**：
#   - §一 #414 的「任务」格与「期望产出」格 —— 因为**它正是描述这个 bug 的
#     那一行**，正文里写着 `Is a directory`；
#   - §一 #98 的「状态」格 —— 正文合法地讨论 `Permission denied`；
#   - §二 一条批次行的「文件清单」格 —— 同理。
#
# 🔑 判据：**这类判据把「格子里被污染成了报错文本」与「格子里在谈论报错文本」
# 当成同一件事，而它们在字面上无法区分**——一个负责记录事故的载体，必然会
# 大量引用事故的原文。判据越贴近事故原文，越必然打到记录事故的那一行。
# ⇒ 只保留**结构性**信号（换行、关键格为空、列数、格位哨兵）：它们不依赖
# 正文措辞，不会因为「有人在写关于它的文档」而误报。
#
# 这一条比它拦下的 bug 更值得记住：**误报会把调用方推去绕过守卫**，而绕过
# 正是修复面 B 要消灭的东西——一道误报的守卫，比没有守卫更糟。


def _preview(cell: str, limit: int = 60) -> str:
    flat = cell.replace("\n", "⏎")
    return flat if len(flat) <= limit else flat[:limit] + "…"


def validate_row_cells(
    section: str, cells: list[str], *, source: str = "write",
) -> list[str]:
    """**所有写盘路径共用的单元格校验**（#414 修复面 B）。返回问题清单；
    空列表＝通过。不抛异常——由调用方决定 fail-loud 的措辞与出口。

    `source` 区分两种调用场景，**只影响竖线一项**：
      - `"write"`（默认，写侧）——待写入的字段值。竖线一律拒绝，**反引号
        包裹不豁免**，沿用 `append-row` 既有语义不放宽。
      - `"parsed"`（读侧）——已被 `split_row_cells` 切好的单元格。此时
        **跳过竖线检查**：切列本身已是反引号感知的，格内残留的竖线是被
        反引号正当保护的字面量（生产队列 §一 #324／#326 即如此，两行都
        正好是 8 列）。🔴 读侧若照搬写侧口径，会把两条**结构完全正常**的
        行报成违规——本参数就是为分开这两种口径而存在，不是可省的装饰。

    覆盖的失效外形（成因见本段顶部）：
      ① **裸竖线**（仅写侧）——内容变成列分隔符。
      ② **跨行**——单元格不得含换行（2026-08-25 事故：25 行 `git worktree
         list` 输出被注入进一个格）。这是「正文被 bash 执行过」留下的
         **结构性**信号；按字样识别的那条已被实测否决，见上方长注释。
      ③ **关键格哨兵**——不只查「格数对不对」，还查「内容像不像该落在这
         一格」。第 ③ 类正是列位错置**唯一**会留下的痕迹：格数是对的，
         错的是内容与格位的对应关系。
    """
    problems: list[str] = []
    names = SECTION_COLUMN_NAMES.get(section)
    if names is None:
        return [f"未知分区 {section!r}，仅支持 {sorted(SECTION_COLUMN_NAMES)}"]
    if source not in ("write", "parsed"):
        raise QueueCellError(
            f"未知 source={source!r}，仅接受 \"write\"／\"parsed\"（不静默按默认处理）"
        )

    expected = len(names)
    if len(cells) != expected:
        problems.append(
            f"§{section} 列数为 {len(cells)}，应为 {expected}"
            f"（列序：{'、'.join(names)}）"
        )

    for i, cell in enumerate(cells):
        label = names[i] if i < expected else f"第 {i + 1} 列（超出列序）"
        if source == "write" and has_bare_pipe(cell):
            problems.append(
                f"「{label}」格含半角竖线（会撑列；改用全角「｜」或改写措辞）："
                + _preview(cell)
            )
        if "\n" in cell:
            problems.append(
                f"「{label}」格含换行——单元格不得跨行（历史事故：25 行命令输出"
                f"被注入进一个格）：" + _preview(cell)
            )

    if len(cells) == expected:
        problems.extend(_key_cell_problems(section, cells, names))
    return problems


def _key_cell_problems(
    section: str, cells: list[str], names: tuple[str, ...],
) -> list[str]:
    """关键格哨兵（`validate_row_cells` 第 ③ 类）。列数已确认正确时才调用。"""
    problems: list[str] = []
    if _numbered_section(section):
        number = cells[0].strip()
        if not number.isdigit():
            problems.append(
                f"「#」格为 {number!r}，不是纯数字行编号——**行头断裂**，grep 与"
                f"队列查询都将找不到该行（2026-08-26 实测形态之一）"
            )
    elif not cells[0].strip():
        problems.append(f"「{names[0]}」格为空——该格是本行唯一标识，不得为空")

    if section == "一":
        status = cells[resolve_column_index("一", "状态")].strip()
        if not status.startswith("[S:"):
            problems.append(
                "「状态」格未以 [S: 开头——§一 状态列须带机器可读字段（队列 #308）；"
                "**列位错置最常见的落点就是这一格**：" + _preview(status)
            )
        product = cells[resolve_column_index("一", "期望产出")].strip()
        if product.startswith("✅"):
            problems.append(
                "「期望产出」格以完成标记开头——极可能是把收工叙述写进了产出格、"
                "而状态格仍停在 [S:open]（2026-08-26 #412 实测：机器读状态列，"
                "于是一直认为该任务没做完）：" + _preview(product)
            )
    return problems


def build_row_cells(section: str, values: dict[str, str]) -> list[str]:
    """按列名构造一整行单元格（#414 修复面 C 的写侧入口）。

    `values` 的键是列名（走 `resolve_column_index`，支持别名），值是该格
    内容。**缺失的列一律 fail-loud，不填空串**——静默补空同样是「内容落错
    结构位而不报错」的一种；调用方要留空必须显式传空串。
    """
    names = SECTION_COLUMN_NAMES.get(section)
    if names is None:
        raise QueueCellError(
            f"未知分区 {section!r}，仅支持 {sorted(SECTION_COLUMN_NAMES)}"
        )
    cells: list[str | None] = [None] * len(names)
    for name, value in values.items():
        idx = resolve_column_index(section, name)
        if cells[idx] is not None:
            raise QueueCellError(
                f"「{names[idx]}」列被赋值两次（{name!r} 与它的别名指向同一列）"
            )
        cells[idx] = value
    missing = [names[i] for i, c in enumerate(cells) if c is None]
    if missing:
        raise QueueCellError(
            f"§{section} 缺少这些列的值：{'、'.join(missing)}"
            f"（要留空须显式传空串——工具不替你补，静默补空正是本次要消灭的失效形态）"
        )
    return [c for c in cells if c is not None]


def header_mismatch(section: str, header_cells: list[str]) -> str | None:
    """把「表头列名」与 `SECTION_COLUMN_NAMES` 对齐这件事变成机器守。

    返回不一致的说明，一致返回 None。存在的理由：`SECTION_COLUMN_NAMES`
    是按列名写入的唯一依据，一旦生产队列文件改了表头而这里没跟，
    `--set 列名=值` 会**静默写进错误的列**——那正是 #414 修复面 C 要
    消灭的失效形态，绝不能靠人记得同步。
    """
    names = SECTION_COLUMN_NAMES.get(section)
    if names is None:
        return None
    actual = tuple(c.strip() for c in header_cells)
    if actual != names:
        return (
            f"§{section} 表头与 queue_table.SECTION_COLUMN_NAMES 不一致——"
            f"按列名写入会写进错误的列。文件表头：{'、'.join(actual)}；"
            f"模块登记：{'、'.join(names)}"
        )
    return None
