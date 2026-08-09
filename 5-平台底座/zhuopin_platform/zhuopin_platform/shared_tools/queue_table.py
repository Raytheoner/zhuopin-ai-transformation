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
QUEUE_PATH_REL = "1-转型规划/0-全景路线图/跨桌任务队列.md"


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
