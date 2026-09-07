"""「规划倒逼开工」扫描器（队列 §一 `#462` ／ openspec 包 `plan-backpressure-scanner`）。

## 它回答的唯一问题

**全景规划权威排期表里有 35 个场景，其中哪些在执行侧「三处皆无」——队列没有承接行、
`4-数字员工/` 没有工程、`openspec/changes`（含 archive）没有变更包？**

⚠️ **它只回答「这个场景对现役机制可不可见」，不回答「该不该做」「什么时候做」。**
排期与优先级是业务总线与 Shao Peishen 的事（队列 `#463`）；本模块的输出**不是**开工授权。

## 为什么必须有它（`#462` 取证，2026-09-02 → 09-07 两次实测）

现有全部机制（可 Open 池／拆件巡逻／值周巡检／泳道看护）**只扫队列 §一**。规划里有、
但没人立行的场景对它们**完全不可见，且不产生任何信号**——不报错、不超时、没人抱怨，
只会在排期月到了以后才被发现从来没人接。取证件
`1-转型规划/0-全景路线图/取证件-2026-09-02-规划与执行覆盖差集.md` §二 是这条根因的正本。

## 判据（四条，每条都是对一个**已实测的误判形态**的修正）

取证件 §三 有一段已跑通的一次性脚本。**它是起点不是终点**：propose 期在真实数据上复跑，
坐实四个缺陷，本模块逐条修掉。四个形态与对应修法：

**⑴ 自指行假阴性 —— 宣布问题存在的那一行，被判据当成了问题已解决的证据。**
旧判据整行 grep，于是 `#463`（任务列写「规划里有、执行侧完全没有的 14 个场景：立行与
排期」）让销售域 S1/S2/S3/S5/S6 五个场景全部被判「已承接」。
⇒ **修法 A：只扫 §一 任务列**（不扫状态列、不扫全行）——`#463` 那 14 个场景码写在它的
**状态列**里，只扫任务列这一条就已消掉这族假阴性。
⇒ **修法 B：再收到任务列的「标的段」**（首个粗体段；无粗体取前 60 字）——本项目 §一 的
书写律是「行的标的写在首个粗体段里，其后是背景、沿革与对别的场景的引用」，故标的段之外
的提及不构成承接。

🔴 **起草期撤回过一条判据，此处写死不得复活**：design D2 初稿曾定「任务列点名 ≥3 个场景码
即元任务行、一律排除」，逐行核对后**不成立**——它会误杀 `#339`（FI3 唯一真承接行）与
`#467`（SC4 场景立行行），**把一个假阴性换成四个**。本模块**不存在**任何按"标的段点名的
场景数量"做整体排除的分支，`test_工具-规划倒逼扫描器.py` 有一条 AST 断言守着它。

**⑵ 命名空间正面对撞 —— 本项目有几套编号体系与场景码字面完全相同。**
需求侧改进项 R1-R5（`#439`「R1 · 口径点台账」／`#440`「R4 · 纪律 eval 套件」）、Phase 1
阶段编号 S1/S2/S3（`#259`「S1 收口外部对抗性评审」，根 CLAUDE.md 第一句就在用）、跟进信
稿次 R5、2027-Q4 季度写法……只靠正则分不开。
⇒ **修法：registry 的 `excludes` 表**（每条附真实来源行号）＋ 🔴 **命中 excludes 只降级、
不剔除**——降为「疑似已承接·待人确认」单列一档，**不从清单里消失**。
判据：**漏报与误报在本模块里不对称**——漏报一个场景 ＝ 回到"完全不可见"（本模块存在的
理由的反面），误报一个 ＝ 有人花两分钟看一眼清单。⇒ **宁可多报。**

**⑶ 右边界缺失 —— 一句"注释声称有守卫、实际没有"的自我保证。**
取证件 `hit()` 的注释写「前置断言避免 O1 命中 O10」，实测 `(?<![A-Za-z0-9])` **只守左边界**：
`'O1' in 'O10 设备'` → True、`'FI1' in 'FI10-存货跌价智能分析'` → True。今天没出事只因
FI1/SC1/O1 各自也有工程目录、结果碰巧一致。
⇒ **修法：`_alias_regex` 两侧都守**，且单测含**反向对照组**（去掉右侧 lookahead 后那三条
断言必须全部失败——否则说明测试根本没测到守卫）。
🔑 **一个"注释声称有守卫、实际没有"的判据，比一个明说没守卫的判据更危险**：它让下一个
读代码的人不再去查。

**⑷ 场景清单硬编码在文档里 —— 一份会过期的快照。**
权威排期表最近三个月改过三次结构级（v6 整域顺延 11 个／v7 下架 5 个／v8 换内涵 2 个），
每次都不会有人记得回头改取证件里那份硬编码。
⇒ **修法：registry JSONL 正本（入库）＋ 与排期表的一致性 lint（CI 硬失败）**。
**副本与失控副本的分界，就是有没有机器守着。**

## 前置依赖：只展示、不设闸（design D4 ＝ (a) 先行，Shao Peishen 2026-09-07 合审）

清单里每个场景附《跨场景前置数据与知识库任务总表》对应行原文；无行则显式标注
「前置总表无此场景行」。
🔴 **本模块不存在任何按 emoji 推断前置就绪的分支**——该表图例原文是
「🔴 关键前置（卡场景上线）｜🟡 已在某文档排期、需拉齐｜⚪ 后置场景、提前提醒」，
**🔴 ＝「这条重要」，不是「这条没就绪」**；按 emoji 判会得到与语义相反的结果。
(b) 档（给前置总表加机器可读 `[P:]` 字段）是另一条队列行的事，本模块预留
`_prereq_machine_field` 的**非静默降级**口径，不自行推断。

## 写侧：本模块一个字节都不写队列（design D5 ＝ (b)，Shao Peishen 2026-09-07 合审）

`#462` 硬要求「产出队列行、不只报告」，而"机器自动向 §一 追加业务场景行"同时撞三条现行
边界：协议〇.10 并入审核（机器做不了的语义判断）／环境保障线边界（`#463`：机制线只出取证
与扫描器）／他的域级暂缓明令。**拍板结果 ＝ (b)：出可粘贴的队列行草案落 `reports/`，由人
一条命令落库。** ⇒ 本模块 **MUST NOT** 调用编辑锁、**MUST NOT** 打开任何队列文件做写入；
单测有一条"跑完扫描后两份队列逐字节不变"的断言守着。
🔴 **`suspended` 场景无论哪一档都不出草案**（他已明令不立的行，不该由机器写出来给人按）。

## 落点与共用（design D6／D7 ＝ (a′)）

判定核心落 `0-学习与工具/`（与 sweep／编辑锁／队列 lint 同族，判定对象是**仓库结构本身**），
不落 `aibot_service/`（那是服务进程，不该多一条对仓库布局的依赖）。
🔴 **D7 (a′)：「三处查」逻辑只在本模块实现一份**——实测 `open_pool_reminder.py` 806 行内
`grep "4-数字员工\\|openspec\\|三处"` 零命中，**没有可 import 的东西**；且该模块 docstring
明写"同 `decision_reminder.py` 既有惯例，本模块重新实现一份 §一 解析，**不 import**"。
⇒ 兑现他 2026-09-02 答 (a) 的实质约束「不造第二套逻辑」的唯一形式是"新逻辑只写一份"，
不是 import。§一 表格切分沿用现行惯例（本模块自持一份 `_split_section_one`，切列委托
`queue_table.split_row_cells`——切列是**格式解析**、不是判据，已是全仓单一实现）。

## 用法

    python 0-学习与工具/工具-规划倒逼扫描器.py              # 三档清单（人读）
    python 0-学习与工具/工具-规划倒逼扫描器.py --json        # 机读（sweep 第 13 类走这个）
    python 0-学习与工具/工具-规划倒逼扫描器.py --lint-registry   # registry ↔ 排期表 一致性校验（CI）
    python 0-学习与工具/工具-规划倒逼扫描器.py --write-report    # 另落一份 reports/ 清单件（不入库）
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

REGISTRY_PATH_REL = "1-转型规划/0-全景路线图/场景registry-规划倒逼扫描器.jsonl"
PLAN_DOC_PATH_REL = "1-转型规划/0-全景路线图/卓品智能AI转型全景规划.md"
PREREQ_DOC_PATH_REL = "1-转型规划/0-全景路线图/跨场景前置数据与知识库任务总表.md"
QUEUE_PATHS_REL = (
    "1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md",
    "1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md",
)
SCENE_ROOT_REL = "4-数字员工"
OPENSPEC_CHANGES_REL = "openspec/changes"
OPENSPEC_ARCHIVE_REL = "openspec/changes/archive"
REPORT_PATH_REL = "reports/规划倒逼-未承接清单.md"

# 输出文案里写死的范围声明（spec `plan-backpressure-output`：不被误当排期建议）。
SCOPE_DISCLAIMER = (
    "本清单只回答「该场景对现役机制是否可见」，**不构成排期建议、也不是开工授权**；"
    "排期与优先级见队列 §一 `#463` 与业务总线。"
)

# 六域 → 该域在权威排期表里的列下标（含首列月份，故从 1 起）与允许的场景码前缀。
# 🔴 **按列取码是一致性 lint 不误报的关键**：表里「销售域整域顺延入 S3」这类沿革句
# 写在采购/工程研发列，若不按列限定前缀，`S3` 会被当成采购域的码。
DOMAIN_COLUMNS: dict[str, tuple[int, str]] = {
    "采购": (1, "SC"),
    "运营": (2, "O"),
    "工程研发": (3, "R"),
    "质量": (4, "Q"),
    "财务": (5, "FI"),
    "销售": (6, "S"),
}

# 权威排期表的表头首格（用于定位那张表；表在 `### 🚀 加速启动总览` 节内）。
PLAN_TABLE_HEADER_FIRST_CELL = "月份"
PLAN_TABLE_SECTION_ANCHOR = "加速启动总览"
# 前置总表第一张表的表头首格。
PREREQ_TABLE_HEADER_FIRST_CELL = "场景"

# 🔴 一致性 lint 前先剥掉单元格里的**括注**（`（…）〔…〕【…】`）。
# 成因（2026-09-07 apply 期实测）：排期表单元格的括注里塞满**沿革**——
# 「（原 SC5 引擎承接部署位）」「〔🔴 v7：原 Q1／Q5 下架撤下〕」「（原 SC9 并入）」，
# 这些码是**历史引用**，不是"本表排了这个场景"。不剥括注，lint 会把 SC5／SC6／SC9
# 报成"排期表有而 registry 无"，而下一个人会用"把 lint 关掉"来解决它。
_BRACKET_NOTE_RE = re.compile(r"[（(〔【][^（()〔【】〕)]*[）)〕】]")

_BOLD_SPAN_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_TARGET_SEGMENT_FALLBACK_CHARS = 60

_ARCHIVE_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-")

_SECTION_ONE_HEADING_RE = re.compile(r"^## 一、", re.MULTILINE)
_ANY_SECTION_HEADING_RE = re.compile(r"^## [〇一二三四五六七八九十]+、", re.MULTILINE)


def _import_queue_table():
    """切列委托 `zhuopin_platform.shared_tools.queue_table`（同 `工具-队列查询.py`
    既有做法）。🔴 **切列是格式解析、不是判据**——反引号跨度内的竖线不得被当列
    分隔符（队列 `#314` 实测事故），这件事全仓只该有一份实现。取不到时给一个
    退化桩，保证隔离环境（无 editable 安装）里本模块仍可跑。"""
    platform_path = REPO_ROOT / "5-平台底座" / "zhuopin_platform"
    if str(platform_path) not in sys.path:
        sys.path.insert(0, str(platform_path))
    try:
        from zhuopin_platform.shared_tools import queue_table  # noqa: PLC0415
        return queue_table
    except ImportError:  # pragma: no cover —— 隔离环境兜底
        class _Fallback:
            @staticmethod
            def split_row_cells(line: str):
                stripped = line.strip()
                if not stripped.startswith("|"):
                    return None
                return [c.strip() for c in stripped.strip("|").split("|")]
        return _Fallback()


_queue_table = _import_queue_table()


class RegistryError(ValueError):
    """registry 行解析失败——fail loud，**绝不跳过该行继续**。

    spec `plan-scenario-registry`：任一行解析失败 SHALL 使整个扫描以非零退出码
    失败并指明行号。跳过一行 ＝ 静默把一个场景变成不可见，正是本模块要治的病。
    """


@dataclass(frozen=True)
class Exclude:
    """一条同名冲突排除词 ＋ 它的**真实来源行号**。

    🔴 **`source` 必填、且由 `load_registry` 强制**（tasks 3.1，同
    `TRIAGE_NEGATION_PHRASES` 的既有做法）。成因：一条不写来源的排除词，下一个人
    只能猜它当初是为了挡什么，于是要么不敢删（表越滚越大），要么删错（假阴性回归）。
    """
    phrase: str
    source: str


@dataclass(frozen=True)
class Scenario:
    code: str
    domain: str
    title: str
    planned_month: str
    aliases: tuple[str, ...]
    excludes: tuple[Exclude, ...]
    suspended: str
    retired: bool = False


@dataclass
class Evidence:
    """一条「已承接」结论的命名证据。

    🔴 **只给布尔值的判据无法被质疑，也就无法被修正**——这是取证件那版四个缺陷
    能同时存活五天的直接原因。故每条结论都必须能指出是哪一处、哪个具体对象。
    """
    where: str          # queue / project / openspec
    ref: str            # 行号 / 目录路径 / 包名
    alias: str
    excerpt: str = ""

    def render(self) -> str:
        tail = f"｜{self.excerpt}" if self.excerpt else ""
        return f"{self.where}:{self.ref}（别名 `{self.alias}`）{tail}"


@dataclass
class ScenarioVerdict:
    scenario: Scenario
    accepted: list[Evidence] = field(default_factory=list)
    downgraded: list[tuple[Evidence, str]] = field(default_factory=list)
    prereq_row: str | None = None

    @property
    def bucket(self) -> str:
        if self.accepted:
            return "已承接"
        if self.downgraded:
            return "疑似已承接·待人确认"
        return "三处皆无"


# ---------------------------------------------------------------------------
# 别名匹配：两侧都守边界
# ---------------------------------------------------------------------------

def _alias_regex(alias: str, right_boundary: bool = True) -> re.Pattern[str]:
    """别名匹配正则。

    🔴 `right_boundary=False` **只供单测的反向对照组使用**——取证件那版正是只守
    左边界，注释却声称守住了 `O1` 不命中 `O10`。把这个开关留在生产代码里是刻意的：
    单测据它证明"守卫本身确实生效"，没有它，一个恒真的断言与一个真守卫长得一样。
    """
    pattern = r"(?<![A-Za-z0-9])" + re.escape(alias)
    if right_boundary:
        pattern += r"(?![A-Za-z0-9])"
    return re.compile(pattern)


def _alias_hits(aliases, haystack: str, right_boundary: bool = True) -> list[str]:
    return [a for a in aliases if _alias_regex(a, right_boundary).search(haystack)]


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------

def load_registry(root: Path = REPO_ROOT) -> list[Scenario]:
    path = root / REGISTRY_PATH_REL
    if not path.exists():
        raise RegistryError(f"registry 不存在：{REGISTRY_PATH_REL}")
    scenarios: list[Scenario] = []
    seen: set[str] = set()
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RegistryError(f"{REGISTRY_PATH_REL} 第 {lineno} 行不是合法 JSON：{exc}") from exc
        if not isinstance(obj, dict):
            raise RegistryError(f"{REGISTRY_PATH_REL} 第 {lineno} 行不是 JSON 对象")
        code = str(obj.get("code") or "").strip()
        if not code:
            raise RegistryError(f"{REGISTRY_PATH_REL} 第 {lineno} 行缺 `code`")
        if code in seen:
            raise RegistryError(f"{REGISTRY_PATH_REL} 第 {lineno} 行场景码重复：{code}")
        seen.add(code)
        retired = bool(obj.get("retired"))
        domain = str(obj.get("domain") or "").strip()
        if not retired and domain not in DOMAIN_COLUMNS:
            raise RegistryError(
                f"{REGISTRY_PATH_REL} 第 {lineno} 行 `domain` 非六域之一：{domain!r}")
        suspended = str(obj.get("suspended") or "").strip()
        if suspended and not _suspended_shape_ok(suspended):
            raise RegistryError(
                f"{REGISTRY_PATH_REL} 第 {lineno} 行 `suspended` 缺来源或日期："
                f"{suspended!r}（须同时含 `#N` 来源与 YYYY-MM-DD 日期）")
        aliases = tuple(str(a) for a in (obj.get("aliases") or []))
        if not retired and not aliases:
            raise RegistryError(f"{REGISTRY_PATH_REL} 第 {lineno} 行缺 `aliases`")
        scenarios.append(Scenario(
            code=code,
            domain=domain,
            title=str(obj.get("title") or ""),
            planned_month=str(obj.get("planned_month") or ""),
            aliases=aliases,
            excludes=_parse_excludes(obj.get("excludes") or [], lineno),
            suspended=suspended,
            retired=retired,
        ))
    return scenarios


def _parse_excludes(raw, lineno: int) -> tuple[Exclude, ...]:
    out: list[Exclude] = []
    for item in raw:
        if not isinstance(item, dict):
            raise RegistryError(
                f"{REGISTRY_PATH_REL} 第 {lineno} 行 `excludes` 项须为对象 "
                f"{{\"phrase\":…, \"source\":…}}，实为 {item!r}——"
                "**排除词必须带真实来源行号**（tasks 3.1）")
        phrase = str(item.get("phrase") or "").strip()
        source = str(item.get("source") or "").strip()
        if not phrase:
            raise RegistryError(f"{REGISTRY_PATH_REL} 第 {lineno} 行 `excludes` 项缺 `phrase`")
        if not _SUSPENDED_SOURCE_RE.search(source):
            raise RegistryError(
                f"{REGISTRY_PATH_REL} 第 {lineno} 行 excludes「{phrase}」的 `source` "
                f"未含 `#N` 队列行号：{source!r}")
        out.append(Exclude(phrase, source))
    return tuple(out)


_SUSPENDED_SOURCE_RE = re.compile(r"#\d+")
_SUSPENDED_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _suspended_shape_ok(value: str) -> bool:
    """`suspended` 必须同时带来源与生效日期。

    🔴 成因（design Risks 那行）：`suspended` 是他明令的一份**副本**，副本会过期。
    他哪天说"销售域可以排了"而 registry 没改，六个场景就继续静默。带上来源与日期，
    才谈得上按周期复核"这条暂缓已 N 天，是否仍成立"。
    """
    return bool(_SUSPENDED_SOURCE_RE.search(value) and _SUSPENDED_DATE_RE.search(value))


# ---------------------------------------------------------------------------
# ⑴ 队列承接行
# ---------------------------------------------------------------------------

def _split_section_one(text: str) -> str:
    """切出 §一 正文。

    本模块自持一份（不 import 编辑锁的 `_split_live_sections`）——同
    `open_pool_reminder.py` / `decision_reminder.py` 的现行惯例：跨文件不 import
    同一份**判据**，格式解析各自一份、由各自单测钉住。
    """
    m = _SECTION_ONE_HEADING_RE.search(text)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = _ANY_SECTION_HEADING_RE.search(rest)
    return rest[:nxt.start()] if nxt else rest


def target_segment(task_cell: str) -> str:
    """任务列的「标的段」＝ 首个粗体段；无粗体则取前 60 字。

    🔴 **这是本模块最要紧的一条判据。** 本项目 §一 的任务列有一条稳定的书写律：
    行的标的写在首个粗体段里（`**FI3 付款校验 design 阶段——…**`／
    ``**`SC4` 合同条款自动提取与审核 · 场景立行**``），其后是背景、沿革与对别的
    场景的引用。收到标的段，是"报 2 个、其中 0 个真"变成"报 13 个、13 个都真"的
    那一步（design D2 实测表）。

    ⚠️ **本函数不看、也不得看"标的段里点名了几个场景"**——design D2 起草期定过
    一条"≥3 个即元任务行、整体排除"的判据，逐行核对后不成立、已撤回（会误杀
    `#339` 与 `#467` 两条真承接行）。单测有 AST 断言守着它不复活。
    """
    m = _BOLD_SPAN_RE.search(task_cell)
    if m:
        return m.group(1)
    return task_cell[:_TARGET_SEGMENT_FALLBACK_CHARS]


def _row_id(cells: list[str]) -> str:
    return cells[0].strip().strip("`").lstrip("#").strip() if cells else "?"


def scan_queue(root: Path, scenarios: list[Scenario],
               right_boundary: bool = True) -> dict[str, list[tuple[Evidence, str]]]:
    """三处查之 ⑴：两份队列 §一 的承接行。

    返回 `{场景码: [(证据, 命中的 excludes 词或 "")]}`。**excludes 命中不在这里
    剔除**——只标注，由 `classify` 降级为「疑似已承接·待人确认」。
    """
    out: dict[str, list[tuple[Evidence, str]]] = {s.code: [] for s in scenarios}
    for rel in QUEUE_PATHS_REL:
        path = root / rel
        if not path.exists():
            continue
        section = _split_section_one(path.read_text(encoding="utf-8"))
        name = Path(rel).name
        for line in section.splitlines():
            cells = _queue_table.split_row_cells(line)
            if cells is None or len(cells) < 2:
                continue
            head = cells[0].strip()
            if head in ("#", "编号") or set(head) <= {"-", " ", ":"} or not head:
                continue
            seg = target_segment(cells[1])
            for sc in scenarios:
                if sc.retired:
                    continue
                hits = _alias_hits(sc.aliases, seg, right_boundary)
                if not hits:
                    continue
                blocked = next((e for e in sc.excludes if e.phrase in seg), None)
                out[sc.code].append((
                    Evidence("queue", f"{name} §一 #{_row_id(cells)}", hits[0],
                             _excerpt(seg)),
                    f"{blocked.phrase}（来源 {blocked.source}）" if blocked else "",
                ))
    return out


def _excerpt(text: str, limit: int = 48) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[:limit] + "…"


# ---------------------------------------------------------------------------
# ⑵ 4-数字员工 工程目录
# ---------------------------------------------------------------------------

def scan_projects(root: Path, scenarios: list[Scenario],
                  right_boundary: bool = True) -> dict[str, list[Evidence]]:
    """三处查之 ⑵：`4-数字员工/<部门>/<场景目录>/`，**只扫一层，不递归**。

    取证件那版 `rglob("*")` 扫全树，把场景内部的 `tests`／`docs`／`reports` 子目录
    名也拌进了干草堆，纯属增加撞名面。
    """
    out: dict[str, list[Evidence]] = {s.code: [] for s in scenarios}
    base = root / SCENE_ROOT_REL
    if not base.is_dir():
        return out
    for dept in sorted(p for p in base.iterdir() if p.is_dir()):
        for scene_dir in sorted(p for p in dept.iterdir() if p.is_dir()):
            for sc in scenarios:
                if sc.retired:
                    continue
                hits = _alias_hits(sc.aliases, scene_dir.name, right_boundary)
                if hits:
                    out[sc.code].append(Evidence(
                        "project", f"{SCENE_ROOT_REL}/{dept.name}/{scene_dir.name}",
                        hits[0]))
    return out


# ---------------------------------------------------------------------------
# ⑶ openspec/changes（含 archive）
# ---------------------------------------------------------------------------

def package_head_segment(pkg_name: str) -> str:
    """包名里用于比对的首段。

    `fi5-expense-audit-mvp` → `fi5`；**归档包带 `YYYY-MM-DD-` 前缀**
    （`2026-07-02-o2-kit-shortage-alert`），先剥日期再取首段 → `o2`。

    🔴 **剥日期这一步是 2026-09-07 apply 期实测补的**：design/spec 原文只写"首个
    `-` 之前的段"，照字面实现会让**全部 59 个归档包的首段恒为 `2026`**——
    `openspec` 这一处查在 archive 上**结构上永远不命中**，而那正好是已交付场景
    （SC1／SC3／SC5／O2／Q6…）的证据所在。**一个恒不命中的检查与一个正常检查，
    在输出上长得一样**，与本模块要治的病同族，故当场修掉并留痕。
    """
    stripped = _ARCHIVE_DATE_PREFIX_RE.sub("", pkg_name)
    return stripped.split("-", 1)[0].lower()


def scan_openspec(root: Path, scenarios: list[Scenario],
                  right_boundary: bool = True) -> dict[str, list[Evidence]]:
    out: dict[str, list[Evidence]] = {s.code: [] for s in scenarios}
    dirs: list[tuple[str, str]] = []
    for rel in (OPENSPEC_CHANGES_REL, OPENSPEC_ARCHIVE_REL):
        base = root / rel
        if not base.is_dir():
            continue
        for pkg in sorted(p for p in base.iterdir() if p.is_dir()):
            if pkg.name == "archive":
                continue
            dirs.append((f"{rel}/{pkg.name}", package_head_segment(pkg.name)))
    for path_ref, head in dirs:
        for sc in scenarios:
            if sc.retired:
                continue
            # 包名是 kebab-case 小写、场景码是大写 ⇒ 统一小写后比；且只在首段里比，
            # 比"整名子串"严得多（`fi10-…` 的首段是 `fi10`，与 `fi1` 不相等）。
            hits = [a for a in sc.aliases
                    if _alias_regex(a.lower(), right_boundary).search(head)]
            if hits:
                out[sc.code].append(Evidence("openspec", path_ref, hits[0]))
    return out


# ---------------------------------------------------------------------------
# 前置总表（只展示、不设闸）
# ---------------------------------------------------------------------------

def _table_block(lines: list[str], header_first_cell: str) -> list[str]:
    """取出表头首格等于 `header_first_cell` 的那张表的数据行（原始行文本）。"""
    out: list[str] = []
    collecting = False
    for line in lines:
        cells = _queue_table.split_row_cells(line)
        if cells is None:
            if collecting:
                break
            continue
        first = cells[0].strip()
        if not collecting:
            if first == header_first_cell:
                collecting = True
            continue
        if set(first) <= {"-", " ", ":"}:
            continue
        out.append(line.strip())
    return out


def prereq_rows(root: Path, scenarios: list[Scenario]) -> dict[str, str | None]:
    """每个场景在《跨场景前置数据与知识库任务总表》第一张表里的对应行原文。

    🔴 **只取原文、不解读**。本函数**不存在**任何按 emoji（🔴/🟡/🟢/⚪/⏸）推断
    前置是否就绪的分支——该表图例里 🔴 ＝「关键前置（卡场景上线）」而非「未就绪」，
    按它判会得到与语义相反的结果（design D4 实测：FI2 行是 🟢 但闸已解除、Q6 行是
    🔴 但场景已交付）。单测有 AST 断言守着这一条。
    """
    path = root / PREREQ_DOC_PATH_REL
    result: dict[str, str | None] = {s.code: None for s in scenarios}
    if not path.exists():
        return result
    rows = _table_block(path.read_text(encoding="utf-8").splitlines(),
                        PREREQ_TABLE_HEADER_FIRST_CELL)
    for line in rows:
        cells = _queue_table.split_row_cells(line)
        if not cells:
            continue
        subject = cells[0]
        for sc in scenarios:
            if sc.retired or result[sc.code]:
                continue
            if _alias_regex(sc.code).search(subject):
                result[sc.code] = _excerpt(line, 160)
    return result


def _prereq_machine_field(cell: str) -> str:
    """(b) 档预留：前置总表若增设机器可读 `[P:ready]`／`[P:blocked]`／`[P:none]`
    字段，从状态列取它。

    🔴 **缺字段／格式非法一律非静默降级为「未知，视同可开」并留痕**，
    MUST NOT 回退到任何关键词或 emoji 推断（spec `plan-backpressure-scan`）。
    今天该字段尚未回填（另一条队列行的事），故本函数目前恒返回 `unknown`。
    """
    m = re.search(r"\[P:(ready|blocked|none)\]", cell)
    return m.group(1) if m else "unknown"


# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------

def classify(root: Path = REPO_ROOT, right_boundary: bool = True) -> list[ScenarioVerdict]:
    scenarios = [s for s in load_registry(root) if not s.retired]
    q = scan_queue(root, scenarios, right_boundary)
    b = scan_projects(root, scenarios, right_boundary)
    o = scan_openspec(root, scenarios, right_boundary)
    pre = prereq_rows(root, scenarios)
    verdicts: list[ScenarioVerdict] = []
    for sc in scenarios:
        v = ScenarioVerdict(sc, prereq_row=pre.get(sc.code))
        for ev, blocked in q[sc.code]:
            (v.downgraded.append((ev, blocked)) if blocked else v.accepted.append(ev))
        v.accepted.extend(b[sc.code])
        v.accepted.extend(o[sc.code])
        verdicts.append(v)
    return verdicts


def buckets(verdicts: list[ScenarioVerdict]) -> dict[str, list[ScenarioVerdict]]:
    out: dict[str, list[ScenarioVerdict]] = {
        "三处皆无": [], "疑似已承接·待人确认": [], "已承接": []}
    for v in verdicts:
        out[v.bucket].append(v)
    return out


def unaccepted_codes(verdicts: list[ScenarioVerdict], include_suspended: bool = True) -> set[str]:
    """告警指纹 ＝ 「三处皆无」的场景码集合。

    `include_suspended=False` 即推送口径：域级暂缓场景**保留在清单、移出推送**
    （spec `plan-backpressure-output`），否则每轮都在报他已明令不立的那几个。
    """
    return {v.scenario.code for v in verdicts
            if v.bucket == "三处皆无" and (include_suspended or not v.scenario.suspended)}


def queue_row_drafts(verdicts: list[ScenarioVerdict]) -> list[dict]:
    """design D5 ＝ (b)：出「待追加的队列行草案」，**由人一条命令落库**。

    🔴 **本函数不写任何文件、不调编辑锁、不产生 `suspended` 场景的草案。**
    它只是把人的动作从"读报告 → 判断 → 想措辞 → 取号 → 拼 7 个格"压到
    "看一眼草案 → 按一条命令"，与 `open_pool_reminder` 当年的定位完全同构。
    """
    drafts = []
    for v in verdicts:
        if v.bucket != "三处皆无" or v.scenario.suspended:
            continue
        sc = v.scenario
        drafts.append({
            "code": sc.code,
            "domain": sc.domain,
            "任务": f"**{sc.code} {sc.title} · 场景立行**（规划倒逼扫描器 {sc.planned_month} 排期，三处皆无）",
            "领取方": "待领（Cowork 业务总线）",
            "输入（指针）": f"全景规划 §加速启动总览权威排期表 {sc.code} 行；"
                            + (v.prereq_row or "前置总表无此场景行"),
            "期望产出": "场景立行与排期（本行由扫描器出草案，落库前须人做并入审核）",
            "prereq": v.prereq_row or "前置总表无此场景行",
        })
    return drafts


# ---------------------------------------------------------------------------
# registry ↔ 权威排期表 一致性 lint
# ---------------------------------------------------------------------------

def _plan_table_rows(root: Path) -> list[list[str]]:
    text = (root / PLAN_DOC_PATH_REL).read_text(encoding="utf-8")
    idx = text.find(PLAN_TABLE_SECTION_ANCHOR)
    lines = (text[idx:] if idx != -1 else text).splitlines()
    rows: list[list[str]] = []
    for line in _table_block(lines, PLAN_TABLE_HEADER_FIRST_CELL):
        cells = _queue_table.split_row_cells(line)
        if cells and len(cells) >= 7:
            rows.append(cells)
    return rows


def plan_table_codes(root: Path, scenarios: list[Scenario]) -> tuple[set[str], set[str]]:
    """从权威排期表逐格提取场景码，返回 (表里出现的码, 通过别名认出的码)。

    **只比"有没有这个码"，不校验排期月、不比对中文标题**（design D1）——把易碎的
    解析留在必须精确的位置上。两处例外如实登记：

    1. **按域列取码**：`SC`／`O`／`R`／`Q`／`FI`／`S` 六个前缀各只在自己那一列生效。
       不这么做，"销售域整域顺延入 S3"这句写在采购列的沿革会被当成采购域有个 S3。
    2. **别名兜底**（2026-09-07 apply 期实测补）：质量域三个场景在表里**根本没有
       写码**——2026-10 格写「8D① 启动／立项门禁② 启动」、2027-04 格写「PPAP 审核」。
       只按码比，Q2／Q4／Q6 会**永久**报"registry 有而排期表无"，而下一个人会用
       "把 lint 关掉"来解决它。⇒ 场景的 registry 别名在其域列命中，同样算表里有它。
       别名是 registry 里的结构化数据，不是对中文标题的自由解析。
    """
    rows = _plan_table_rows(root)
    literal: set[str] = set()
    by_alias: set[str] = set()
    for cells in rows:
        for domain, (col, prefix) in DOMAIN_COLUMNS.items():
            if col >= len(cells):
                continue
            cell = _BRACKET_NOTE_RE.sub("", cells[col])
            for m in re.finditer(r"(?<![A-Za-z0-9])" + prefix + r"(\d+)(?![A-Za-z0-9])", cell):
                literal.add(prefix + m.group(1))
            for sc in scenarios:
                if sc.retired or sc.domain != domain:
                    continue
                if _alias_hits(sc.aliases, cell):
                    by_alias.add(sc.code)
    return literal, by_alias


def lint_registry(root: Path = REPO_ROOT) -> tuple[list[str], list[str]]:
    """双向差集。返回 (排期表有而 registry 无, registry 有而排期表无)。

    🔴 `retired` 码（Q1/Q3/Q5/Q7/Q8）**两侧都排除**：它们既不该因"registry 有而
    排期表没有"被报，也不该因排期表的下架沿革注里提到它们而被报。否则这条 lint
    会永远红着，而一条永远红着的 lint 等于没有 lint。
    """
    scenarios = load_registry(root)
    retired = {s.code for s in scenarios if s.retired}
    live = [s for s in scenarios if not s.retired]
    literal, by_alias = plan_table_codes(root, live)
    in_table = (literal | by_alias) - retired
    in_registry = {s.code for s in live}
    return sorted(in_table - in_registry), sorted(in_registry - in_table)


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def render_text(verdicts: list[ScenarioVerdict]) -> str:
    bk = buckets(verdicts)
    out: list[str] = []
    out.append("规划倒逼扫描：三处查（队列 §一 承接行／4-数字员工 工程／openspec 变更包）")
    out.append(f"  场景总数 {len(verdicts)}｜🔴 三处皆无 {len(bk['三处皆无'])}"
               f"｜🟡 疑似已承接·待人确认 {len(bk['疑似已承接·待人确认'])}"
               f"｜✅ 已承接 {len(bk['已承接'])}")
    out.append(f"  {SCOPE_DISCLAIMER}")
    out.append("")
    out.append(f"🔴 三处皆无（{len(bk['三处皆无'])}）")
    for v in bk["三处皆无"]:
        sus = f"　⏸ 暂缓：{v.scenario.suspended}" if v.scenario.suspended else ""
        out.append(f"  - {v.scenario.code} {v.scenario.title}（规划 {v.scenario.planned_month}）{sus}")
        out.append(f"      前置：{v.prereq_row or '前置总表无此场景行'}")
    out.append("")
    out.append(f"🟡 疑似已承接·待人确认（{len(bk['疑似已承接·待人确认'])}）"
               "——别名命中但同段命中 excludes，**只降级不剔除**")
    for v in bk["疑似已承接·待人确认"]:
        out.append(f"  - {v.scenario.code} {v.scenario.title}")
        for ev, blocked in v.downgraded:
            out.append(f"      · {ev.render()}　⇦ excludes 命中：「{blocked}」")
    out.append("")
    out.append(f"✅ 已承接（{len(bk['已承接'])}）")
    for v in bk["已承接"]:
        refs = "；".join(e.render() for e in v.accepted[:3])
        more = f"（另 {len(v.accepted) - 3} 处）" if len(v.accepted) > 3 else ""
        out.append(f"  - {v.scenario.code} {v.scenario.title}：{refs}{more}")
    return "\n".join(out)


def to_payload(verdicts: list[ScenarioVerdict]) -> dict:
    bk = buckets(verdicts)
    return {
        "scope": SCOPE_DISCLAIMER,
        "total": len(verdicts),
        "counts": {k: len(v) for k, v in bk.items()},
        "unaccepted": [
            {
                "code": v.scenario.code,
                "domain": v.scenario.domain,
                "title": v.scenario.title,
                "planned_month": v.scenario.planned_month,
                "suspended": v.scenario.suspended,
                "prereq": v.prereq_row or "前置总表无此场景行",
            }
            for v in bk["三处皆无"]
        ],
        "suspected": [
            {
                "code": v.scenario.code,
                "title": v.scenario.title,
                "hits": [{"evidence": ev.render(), "excludes": blocked}
                         for ev, blocked in v.downgraded],
            }
            for v in bk["疑似已承接·待人确认"]
        ],
        "accepted": [
            {"code": v.scenario.code, "evidence": [e.render() for e in v.accepted]}
            for v in bk["已承接"]
        ],
        "queue_row_drafts": queue_row_drafts(verdicts),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(REPO_ROOT), help="仓库根（默认＝本脚本上一级）")
    ap.add_argument("--json", action="store_true", help="机读输出（sweep 第 13 类走这个）")
    ap.add_argument("--lint-registry", action="store_true",
                    help="只跑 registry ↔ 权威排期表 一致性校验，差集非空即退出码 1")
    ap.add_argument("--write-report", action="store_true",
                    help=f"另落一份清单件到 {REPORT_PATH_REL}（reports/ 已被 .gitignore 覆盖）")
    args = ap.parse_args(argv)
    root = Path(args.root)

    try:
        if args.lint_registry:
            missing, extra = lint_registry(root)
            if not missing and not extra:
                print("registry ↔ 权威排期表 一致性校验：✓ 通过（双向差集为空）")
                return 0
            if missing:
                print(f"✗ 排期表有而 registry 无（{len(missing)}）：{'、'.join(missing)}")
            if extra:
                print(f"✗ registry 有而排期表无（{len(extra)}）：{'、'.join(extra)}")
            print("⇒ 处置：改 registry 使其跟随排期表。**MUST NOT 反向改排期表**"
                  "（registry 永远不是排期正本）。")
            return 1

        verdicts = classify(root)
    except RegistryError as exc:
        print(f"✗ registry 解析失败：{exc}", file=sys.stderr)
        return 2

    if args.write_report:
        report = root / REPORT_PATH_REL
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(render_text(verdicts) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(to_payload(verdicts), ensure_ascii=False, indent=2))
    else:
        print(render_text(verdicts))
        if args.write_report:
            print(f"\n清单件已落：{REPORT_PATH_REL}（不入库）")
    return 0


# ---------------------------------------------------------------------------
# 自省断言的取数口（供单测做 AST 扫描用，不在运行时调用）
# ---------------------------------------------------------------------------

def module_ast() -> ast.Module:
    return ast.parse(Path(__file__).read_text(encoding="utf-8"))


if __name__ == "__main__":
    sys.exit(main())
