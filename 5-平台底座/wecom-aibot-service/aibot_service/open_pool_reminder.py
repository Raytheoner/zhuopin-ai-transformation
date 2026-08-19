"""「可 Open 池」事件驱动提醒——CC 半（队列 #312）。

背景：Shao Peishen 2026-08-09 提出、2026-08-10 再次提出同一诉求（两日内
两次由他本人主动发起"有没有可开展的任务"，这正是本模块要消灭的现象本身）
——把"有待领任务可 Open"从他主动问一句变成事件驱动的提醒。设计已在队列
#312 行内定稿：主落点是看板 artifact `zhuopin-project-status`（Cowork
半，拉取式，零打扰，见该行 ⑴）；本模块是辅落点——企微推送，且只在"池从
0 变非 0"或"新增可 Open 行"时推一次（复用队列 #308 子项 D2 的指纹抑制
思路：指纹＝当前可 Open 行号集合，集合不出现新行号即静默）。

**能力边界（如实登记，不假装闭合）**：机制能提醒，替不了 Shao Peishen
点"新建对话"——回合制 session 无法自我唤醒（队列 #230 第二形态）。本模块
把他要做的动作从"主动问一句『现在有什么可推进』＋等一个 session 算出来"
压缩到"收到一条带 opener 路径的推送，然后粘贴"，不是"自动开工"。

**判据（与 Cowork 半看板卡同一份，队列 #308 机器字段）**：§一 状态列
`[S:open]` 即"可立即开工"——`timed=`/`hold`/`blocked`/`partial`/`done`
均为不同枚举取值，天然被排除，不需要额外的"非 timed 非 hold"否定判断。
`partial`（主体已完成而子项待领，如 #96/#118/#264）行本轮已如实登记为
已知边界（见队列 #312 行"本轮还实测出一个池子算法必须处理的边界"段：
"只取 open 会漏掉 13 条中的绝大多数可做项"）——本模块不处理该边界，只
处理"整行仍是 open"的最直接情形；若未来要把 partial 的"仍有待领子项"
纳入本池，须先有一个可机读的二次判据，不能靠正则猜中文（同 #308 立行
初衷），此处只登记不代定实现方案。

**独立解析（不跨文件 import 判据）**：同 `decision_reminder.py` 既有
惯例（见该文件"本文件独立实现一份解析"注释），本模块重新实现一份 §一
状态字段解析与表格切分，不 import `decision_reminder.py` 的同名函数。
"""
from __future__ import annotations

import asyncio
import json
import re
import subprocess
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from zhuopin_platform.audit import AuditEvent
from zhuopin_platform.shared_tools.queue_table import (
    SECTION_COLUMN_COUNTS,
    iter_queue_paths,
)

SECTION_ONE_HEADING = "## 一、"
_NEXT_HEADING = "\n## "

# 队列 #308（2026-08-09，决策点 4）：§一 状态列开头机器可读字段——本文件
# 独立实现一份解析（同本项目"跨文件不 import 同一份判据"既有惯例，见
# decision_reminder.py 同名常量的注释）。
_STATUS_FIELD_RE = re.compile(
    r"^\[S:(done|open|partial|hold|blocked|timed=\d{4}-\d{2}-\d{2})\]"
    r"(?:\[D:(机|业)\])?"
)
_STATUS_LEADING_STRIP_CHARS = "* \t　"

# 队列 #302 同款教训：`#(\d+)` 按完整数字游程提取——`#220` 只会被提取为
# 整数 220，不会被"#22 是否为其子串"这类朴素子串搜索误判命中（2026-08-07
# 实测坐实：`git log --grep="#22"` 命中 29 条，因 `#22` 是 `#220`/`#221`/
# `#223`/`#225`/`#227` 的子串），本模块用同一手法判定 opener 文件是否
# 引用过某行号。
_ROW_NUMBER_RE = re.compile(r"#(\d+)")

DEFAULT_STATE_REL = "reports/open_pool_reminder_state.json"

# 队列 #312 行内定稿原文只写"扫『派单件-*.md』内的行号引用"——本模块把
# glob 扩到另外两类真实承载 opener 的既有命名律（`开场prompt-` 前缀现存
# 30 份／`本周计划-` 前缀现存 8 份，均见 CLAUDE.md R4 命名律 + 本目录
# 现存文件盘点）。**扩大范围的理由如实登记**：#312 自身当前的 opener
# 就落在《本周计划-2026-08-10》而非任何『派单件-*.md』——若只按字面
# glob，本模块会把自己所在的这一行判成"未出 opener"，是一个可预见且
# 会立刻在生产数据上验证失败的假阴性，故扩大范围、在此明确登记（不是
# 悄悄改写设计文本的字面意思）。
OPENER_GLOB_PATTERNS: tuple[str, ...] = (
    "派单件-*.md", "开场prompt-*.md", "本周计划-*.md",
)
OPENER_SEARCH_DIR_REL = "1-转型规划/0-全景路线图"


def _parse_status_domain_fields(status_cell: str) -> tuple[str | None, str | None, str]:
    stripped = status_cell.lstrip(_STATUS_LEADING_STRIP_CHARS)
    m = _STATUS_FIELD_RE.match(stripped)
    if not m:
        return None, None, status_cell
    return m.group(1), m.group(2), stripped[m.end():]


def _parse_table_rows(queue_text: str, heading: str) -> list[list[str]]:
    """同 `decision_reminder.py` 同名函数——提取 `heading` 到下一个
    `## ` 标题之间的表格数据行（跳过表头/分隔行），原样切分不做列数
    校验，交调用方按预期列数处理。"""
    start = queue_text.find(heading)
    if start == -1:
        return []
    rest = queue_text[start + len(heading):]
    next_heading = rest.find(_NEXT_HEADING)
    section = rest if next_heading == -1 else rest[:next_heading]

    rows: list[list[str]] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not cells:
            continue
        first = cells[0]
        if first in ("#", "") or set(first) <= {"-", " "}:
            continue  # 表头行 / 分隔行
        rows.append(cells)
    return rows


@dataclass
class OpenPoolRow:
    row_id: str
    domain: Optional[str]  # "机" / "业" / None（域字段缺失时）
    summary: str


def parse_open_pool_rows(queue_text: str) -> list[OpenPoolRow]:
    """解析队列 §一 中状态字段为 `open` 的行（即"可立即开工"）。

    字段缺失/非法时非静默降级——发 `RuntimeWarning` 并跳过该行。不像
    `decision_reminder.parse_priority_pending_rows` 那样回退旧"待领"
    子串判据：队列 #308 落地后 `工具-队列结构lint.py` 已把"§一 新行必须
    带机器字段"升级为 CI 硬门禁，此处的"跳过"只是防御性兜底、不是常态
    路径，不值得为它复刻一份已被正式退休的旧判据。"""
    rows: list[OpenPoolRow] = []
    for cells in _parse_table_rows(queue_text, SECTION_ONE_HEADING):
        if len(cells) != SECTION_COLUMN_COUNTS["一"]:
            continue  # 列数不符（如裸竖线撑列）的行不纳入判定，交人工核查
        row_id, task_cell, _owner, _input, _output, status_cell, _touch, _registered = cells
        status_value, domain_value, _rest = _parse_status_domain_fields(status_cell)
        if status_value is None:
            warnings.warn(
                f"§一 #{row_id} 状态字段缺失/非法，已跳过可 Open 池判定（非静默降级，见队列 #308）",
                RuntimeWarning, stacklevel=2,
            )
            continue
        if status_value != "open":
            continue
        summary = task_cell[:80] + ("…" if len(task_cell) > 80 else "")
        rows.append(OpenPoolRow(row_id=row_id, domain=domain_value, summary=summary))
    return rows


def discover_opener_files(repo_root: Path) -> list[Path]:
    """在 `OPENER_SEARCH_DIR_REL` 下按 `OPENER_GLOB_PATTERNS` 枚举候选
    opener 文件，按路径排序（稳定顺序，不因目录遍历顺序而漂移）。目录
    不存在返回空列表（非法环境的防御性兜底，不是常态路径）。"""
    base = repo_root / OPENER_SEARCH_DIR_REL
    if not base.is_dir():
        return []
    files: set[Path] = set()
    for pattern in OPENER_GLOB_PATTERNS:
        files.update(base.glob(pattern))
    return sorted(files)


def _build_opener_index(opener_files: list[Path]) -> list[tuple[Path, set[int]]]:
    """每份候选文件只读一次、提取一次行号引用集合——避免"每行都重新扫
    全部文件"的 O(行数×文件数) 重复 I/O（候选文件现存约 40 份、合计约
    570KB，行数常年个位数，重复读的代价虽不致命但没有必要）。单个文件
    读取失败（如扫描瞬间被删除）跳过，不影响其余文件的索引。"""
    index: list[tuple[Path, set[int]]] = []
    for path in opener_files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        index.append((path, {int(n) for n in _ROW_NUMBER_RE.findall(text)}))
    return index


def find_opener_path(row_id: str, opener_index: list[tuple[Path, set[int]]]) -> Optional[Path]:
    """在 `opener_index`（`_build_opener_index` 的产出）里找第一个引用过
    `#<row_id>` 的文件（按 `opener_index` 顺序，稳定返回同一份结果）。
    `row_id` 非纯数字（本项目 §一 编号列既有惯例恒为纯数字）或未命中均
    返回 None。

    **已知精度边界（如实登记，2026-08-10 对生产队列真实验证时实测坐实，
    非推演）**：本判据是"该文件是否提到过这个行号"，不是"该文件是否
    就是这个行号的权威 opener"——对生产数据真实跑一次即发现一例：
    #98（月度环境体检例行）命中的是《开场prompt-【CC】192-199-...》，
    该文件标题与正文主体都在讲 #192-199，#98 只在正文中段作为一句
    "待 #98 体检清"的前瞻性提及出现，并非该文件的opener 目标。同一次
    验证里 #82／#315 的命中则确属真实相关（各自的核心内容就是该行）。
    **未做进一步收紧**（如"只认标题行"）——那会把 #82／#315 这两个真
    命中一并滤掉（它们的引用同样不在标题行），属于本项目已反复验证过的
    "为了堵一个假阳性，牺牲更多真阳性"陷阱（同队列 #302 副判据"必然有
    误报"的取舍）。误报代价低（人点开链接发现文不对题，等同于"尚未出
    opener"的体验，不会更差），故保留现状、如实标注，不为此新增复杂度。"""
    if not row_id.isdigit():
        return None
    target = int(row_id)
    for path, numbers in opener_index:
        if target in numbers:
            return path
    return None


@dataclass
class OpenPoolItem:
    row_id: str
    domain: Optional[str]
    summary: str
    opener_path: Optional[str]  # 仓库相对路径字符串；None＝尚未出 opener
    # 队列 #312 缺口二：该行所在的物理队列文件（仓库相对路径）——陈化催办要
    # 去这个文件上查该行的 git 末次触碰时间，池合并后无法再从"当初读的是哪
    # 份文本"反推，故随行携带。`None` 表示调用方走的是单文本入口
    # `build_pool_items` 且未声明来源（该入口保留给既有单测与单文件场景）。
    queue_rel: Optional[str] = None


def _items_from_rows(
    rows: list[OpenPoolRow], opener_index: list[tuple[Path, set[int]]],
    repo_root: Path, queue_rel: Optional[str],
) -> list[OpenPoolItem]:
    """把已解析出的可 Open 行配上 opener 路径与来源文件，组装成
    `OpenPoolItem`。抽出来是为了让单文件入口（`build_pool_items`）与双文件
    入口（`build_pool_items_from_repo`）共用同一段组装逻辑——两个入口的差别
    只在"读哪些文本"，不该在"怎么组装"上再分叉一次。"""
    items: list[OpenPoolItem] = []
    for row in rows:
        opener = find_opener_path(row.row_id, opener_index)
        opener_rel: Optional[str] = None
        if opener is not None:
            try:
                opener_rel = str(opener.relative_to(repo_root))
            except ValueError:
                opener_rel = str(opener)
        items.append(OpenPoolItem(
            row_id=row.row_id, domain=row.domain, summary=row.summary,
            opener_path=opener_rel, queue_rel=queue_rel,
        ))
    return items


def build_pool_items(
    queue_text: str, repo_root: Path, queue_rel: Optional[str] = None,
) -> list[OpenPoolItem]:
    """解析**单份**队列文本 → 可 Open 行 → 逐行核对是否已出 opener，返回
    该份文本对应的池快照（不筛"新增"，那是 `compute_new_ids` 的职责——本
    函数纯粹是"此刻池子长什么样"）。

    🔴 **生产调用方一律用 `build_pool_items_from_repo`，不要用本函数**——
    队列 #315 拆分后队列有两份物理文件，只读其中一份正是本轮要修的缺口一
    （见该函数 docstring）。本函数保留为纯函数（给文本、给根，返回池）：
    既有单测全部建立在这个形状上，且"给我一份文本、算出它的池"本身是一个
    正当且可独立测试的能力，不必为了少一个入口而把 I/O 塞进来。
    """
    rows = parse_open_pool_rows(queue_text)
    if not rows:
        return []
    opener_index = _build_opener_index(discover_opener_files(repo_root))
    return _items_from_rows(rows, opener_index, repo_root, queue_rel)


def build_pool_items_from_repo(repo_root: Path) -> list[OpenPoolItem]:
    """队列 #312 缺口一（2026-08-19 零时巡检查清）：可 Open 池的取数覆盖
    **全部**物理队列文件，而不是只读 `repo_paths.DEFAULT_QUEUE_RELATIVE_PATH`
    指向的那一份。

    **修的是什么**：`#315`（2026-08-11）把队列拆成"机制环境"与"业务场景"
    两份物理文件，而本模块的调用方仍只读前者 ⇒ **采购／财务／质量三域的
    构建任务全部住在后者里，从未进过池**。实测坐实：生产状态文件当时的
    `known_open_ids` ＝ `["240","337","338","341","98"]`，五个全是机制环境行，
    采购 `#334`／`#344` 一个都不在——而 `#334` 的两个排队前置已于 2026-08-18
    全部完成、还经姚祖怡本人抽查验收通过，**却没有任何机制会去重算它**。

    **为何不改 `DEFAULT_QUEUE_RELATIVE_PATH`**：那个常量还被写侧
    （`queue_appender` 等）消费，其"按 `[D:机/业]` 域路由"是队列 `#341`
    承接的另一笔独立欠账；读侧漏一份不在 `#341` 范围内，两者不要互相并入
    （派单件 OP-0819-A ⑵ 明写的范围红线）。故本函数是"可 Open 池专用的
    双文件取数"，`DEFAULT_QUEUE_RELATIVE_PATH` 一字未动。

    🔴 **逐份解析后合并，绝不先拼接文本再解析一次**：`_parse_table_rows`
    用 `text.find(heading)` 定位 `## 一、`，**只取第一个**——拼接两份文本会
    让第二份的 §一 被静默丢弃，**症状与本次要修的缺口一模一样、且更难发现**。

    某一份文件读取失败/不存在时发 `RuntimeWarning` 并跳过（同本模块
    `parse_open_pool_rows` 对字段缺失的"非静默降级"既有惯例），继续处理
    其余文件——**不把残缺的结果当作完整的池**，那正是缺口一的形态。
    """
    opener_index = _build_opener_index(discover_opener_files(repo_root))
    items: list[OpenPoolItem] = []
    for queue_rel in iter_queue_paths():
        path = repo_root / queue_rel
        try:
            queue_text = path.read_text(encoding="utf-8")
        except OSError as exc:
            warnings.warn(
                f"队列文件读取失败，可 Open 池已跳过该份（非静默降级，队列 #312 缺口一）："
                f"{queue_rel}：{exc}",
                RuntimeWarning, stacklevel=2,
            )
            continue
        rows = parse_open_pool_rows(queue_text)
        if not rows:
            continue
        items.extend(_items_from_rows(rows, opener_index, repo_root, queue_rel))
    return items


# 队列 #312 缺口二（2026-08-19 零时巡检查清，Shao Peishen 当日答定夺 1
# 选 (a)、N＝7）：陈化阈值与催办间隔。
#
# **缺口二是什么**：既有指纹的定义是"当前可 Open 行号集合，集合不出现新
# 行号即静默"——它只覆盖了"有新活了通知我"，**对"有活一直没开"结构性
# 沉默**。而 Shao Peishen 要的恰恰是后者（原话「最好 workflow 可以提醒我
# 加快」）。两件事在原实现里是同一个判据。
STALE_THRESHOLD_DAYS = 7
STALE_REMINDER_INTERVAL_DAYS = 7


def default_state() -> dict:
    return {"known_open_ids": [], "stale_notified_at": {}}


def load_state(path: Path) -> dict:
    if not path.exists():
        return default_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default_state()
    if not isinstance(data, dict):
        return default_state()
    state = default_state()
    state.update({k: v for k, v in data.items() if k in state})
    # 升级前写入的旧状态文件只有 `known_open_ids`——上面的 `update` 已让
    # 缺失键自动取默认空 dict（无需迁移脚本）。此处只再防一手"键在但类型
    # 不对"（手工编辑过的状态文件），不静默把非 dict 当 dict 用。
    if not isinstance(state.get("stale_notified_at"), dict):
        state["stale_notified_at"] = {}
    return state


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def compute_new_ids(items: list[OpenPoolItem], state: dict) -> set[str]:
    """队列 #312：指纹＝当前可 Open 行号集合。只在"新出现的行号"上触发
    ——同时覆盖设计文本点名的两种场景："池从 0 变非 0"（此时全部当前
    行号相对空的历史状态都是新的）与"新增可 Open 行"（只有部分行号是
    新的）。池子"缩小"（行被领走/转 partial/done）不触发推送——那是
    好消息，不是"有事需要你开工"，同设计文本"绝不写'有 N 条可开'式的
    存在即提醒"的红线（队列 #147「狼来了」教训）。"""
    known = set(state.get("known_open_ids") or [])
    current = {item.row_id for item in items}
    return current - known


def new_known_state(items: list[OpenPoolItem]) -> dict:
    """更新后的状态——直接替换为"本轮实际算出的完整集合"（而非并集
    累加）。这样一个行号离开池子后若未来重新进入会被当"新出现"再提醒
    一次（同 `工具-落库sweep.py::_track_and_alert_standing_state` 的
    "出现→消失→再出现即再报"语义，区别于 `decision_reminder.py` 式的
    "seen 只增不减"——两种语义各自服务不同的判断，此处按 #312 行内
    "指纹＝可 Open 编号集合；集合不变即静默，变了才推"的字面定义选择
    与 sweep 那版一致的语义）。"""
    return {"known_open_ids": sorted({item.row_id for item in items})}


# —— 队列 #312 缺口二：陈化催办 ——————————————————————————————————

def last_touched_at(repo_root: Path, queue_rel: str, row_id: str) -> Optional[datetime]:
    r"""返回队列行 `#<row_id>` 在 `queue_rel` 这份文件上的**末次触碰提交
    时间**（带时区的 `datetime`）；查不到返回 `None`。

    🔴 **必须用 git，不能用文件 mtime**（派单件明写，`#338`④ 已记过 A9
    教训）：队列文件几乎每天都被写入，其 mtime 恒为"最近"，**用它判"这一
    行动没动"恒为假**——判据会永远认为每一行都刚动过，陈化催办永不触发。

    **查法＝`git log -1 --format=%cI -G'^\| *<行号> *\|' -- <文件>`**。
    `-G` 匹配"patch 里增删的行中有匹配该正则的行"；编辑一行 ＝ 删旧行 ＋
    加新行，两侧都以 `| <行号> |` 起首 ⇒ **任何对该行正文的改动都会命中**。

    **为何不用 `-L<n>,<n>` 或 `git blame -L`**：那两者追的是"当前第 n 行"
    的历史，而队列行的物理行号随上方增删不断漂移，追出来的很可能是另一行
    的历史——**是一个会静默给出错误答案的判据**（同 #308 要根治的形态）。

    **已知精度边界（如实登记）**：若同一文件别处出现行首为 `| <同一数字> |`
    的文本也会命中。实测队列文件里行首 `| <数字> |` 只可能是 §一 数据行
    本身，概率极低；且**误命中的方向是"以为它动过、于是不催"**，属保守
    失败——`#147` 狼来了教训指向"乱催"的代价更高，故取这一侧。
    """
    if not row_id.isdigit():
        return None
    pattern = rf"^\| *{row_id} *\|"
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "log", "-1", "--format=%cI",
             f"-G{pattern}", "--", queue_rel],
            capture_output=True, text=True, encoding="utf-8",
        )
    except (OSError, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    stamp = result.stdout.strip()
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp)
    except ValueError:
        return None


@dataclass
class StaleCandidate:
    """一条判定为"陈化"的可 Open 行 ＋ 它已闲置的天数（供文案显示）。"""
    item: OpenPoolItem
    idle_days: int


def _parse_iso(value) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def compute_stale_candidates(
    items: list[OpenPoolItem], state: dict, now: datetime,
    *, touched_at: Callable[[OpenPoolItem], Optional[datetime]],
    threshold_days: int = STALE_THRESHOLD_DAYS,
    interval_days: int = STALE_REMINDER_INTERVAL_DAYS,
) -> tuple[list[StaleCandidate], list[str]]:
    """队列 #312 缺口二：判定哪些可 Open 行该发陈化催办。返回
    `(候选列表, 降级日志列表)`——降级日志交调用方打印/记 audit，**不静默**。

    两条**合取**条件（缺一不催）：
      ① 该行的末次触碰时间距 `now` 超过 `threshold_days`；
      ② 距上次对该行发出陈化催办已满 `interval_days`（从未催过即满足）。

    🔴 **与「新增即推」（`compute_new_ids`）分别计指纹、互不覆盖**——两者
    判的是不同的事：前者判"池里出现了以前没有的活"（低延迟、事件驱动），
    后者判"某条活一直没被领走"（周期性、存量催办）。用其一取代另一个，
    要么让新活最多迟一周才被提醒，要么就是本轮要修的这个缺口本身。

    **`touched_at` 由调用方注入**（生产接 `last_touched_at`，单测注入假
    函数）——避免为了测一个纯判定逻辑而必须造一个真 git 仓库。

    🔴 **时间比较必须同基准**：git `%cI` 自带时区偏移，`now` 也 MUST 是带
    时区的时刻（根 CLAUDE.md「时间戳必判 UTC vs Win 本地」硬规则的具体
    落点）；把带时区的时刻与朴素本地时刻相减在 Python 里会直接抛
    `TypeError`，本函数不吞这个异常——它该炸出来，不该被兜成"不催"。
    """
    notified = state.get("stale_notified_at") or {}
    candidates: list[StaleCandidate] = []
    degraded: list[str] = []
    threshold = timedelta(days=threshold_days)
    interval = timedelta(days=interval_days)
    for item in items:
        touched = touched_at(item)
        if touched is None:
            # 尚未 commit 的新行等情形——**保守失败：视为"刚触碰、不催"**。
            # 反过来把 None 当"很久没动"，会让每一条新行在下一次运行时立刻
            # 被催，等于把机制退化成定夺 1 里已被否决的 (c)「池非空就推」。
            degraded.append(
                f"#{item.row_id} 取不到 git 末次触碰时间（{item.queue_rel or '来源未声明'}），"
                f"按『刚触碰』处理、本轮不催（非静默降级，队列 #312 缺口二）"
            )
            continue
        idle = now - touched
        if idle <= threshold:
            continue
        last_notified = _parse_iso(notified.get(item.row_id))
        if last_notified is not None and now - last_notified < interval:
            continue
        candidates.append(StaleCandidate(item=item, idle_days=idle.days))
    return candidates, degraded


def new_stale_state(
    items: list[OpenPoolItem], state: dict, notified_ids: set[str], now: datetime,
) -> dict:
    """更新后的 `stale_notified_at`——**每轮裁剪为仅保留当前仍在池中的行
    号**，本轮真发出催办的行时间戳刷新为 `now`。

    裁剪的理由与 `new_known_state` 的"替换而非并集累加"同源：一条行被领走
    （转 `partial`/`done`）后又退回 `open` 时，应按新的计时起点重新起算，
    **而不是带着三个月前的催办记录立刻被催**。只增不减还会让状态文件无界
    增长。
    """
    current = {item.row_id for item in items}
    previous = state.get("stale_notified_at") or {}
    kept = {k: v for k, v in previous.items() if k in current}
    stamp = now.isoformat()
    for row_id in notified_ids:
        if row_id in current:
            kept[row_id] = stamp
    return kept


def format_stale_reminder_message(candidates: list[StaleCandidate]) -> Optional[str]:
    """陈化催办文案。同 `format_pool_reminder_message` 的既有红线——**自带
    下一步动作**，不写"有 N 条可开"式的存在即提醒（队列 #147「狼来了」
    教训）；尚未出 opener 的行如实标注，不假装存在一个路径。

    与「新增即推」是**两条独立消息**（派单件：两条判据分别计指纹、不要
    互相覆盖），故文案首行也明确区分，使他一眼能分清"这是新活"还是"这是
    催我快点"。
    """
    if not candidates:
        return None
    lines = [f"⏳ 可 Open 池陈化催办 {len(candidates)} 条（已排队多日无进展，非新增）："]
    for cand in sorted(
        candidates, key=lambda c: (-c.idle_days, int(c.item.row_id) if c.item.row_id.isdigit() else 0)
    ):
        item = cand.item
        domain_tag = f"[{item.domain}]" if item.domain else "[域未标注]"
        if item.opener_path:
            action = f"opener 在 `{item.opener_path}`，复制即用"
        else:
            action = "尚未出 opener，需先备一份"
        lines.append(f"- #{item.row_id} {domain_tag} 已滞留 {cand.idle_days} 天 {item.summary}：{action}")
    lines.append(
        f"同一行每 {STALE_REMINDER_INTERVAL_DAYS} 天最多催一次；行被领走或状态改变即自动停催。"
    )
    return "\n".join(lines)


def format_pool_reminder_message(items: list[OpenPoolItem], new_ids: set[str]) -> Optional[str]:
    """队列 #312 ⑶："提醒文案必须自带下一步动作"——不写"有 N 条可开"，
    写"有 N 条可开，opener 在 `<路径>`，复制即用"；尚未出 opener 的行
    如实标注"尚未出 opener"，不假装存在一个路径。只展示本轮触发的新增
    行（`new_ids`）——同一批次内若还有更早已提醒过、未变化的行，那些
    留给看板卡（拉取式，见队列 #312 行 ⑴），本消息不重复列出以免推送
    本身也变成"存在即提醒"。"""
    fresh = [item for item in items if item.row_id in new_ids]
    if not fresh:
        return None
    lines = [f"🔔 可 Open 池新增 {len(fresh)} 条（可立即开工，非例行提醒）："]
    for item in sorted(fresh, key=lambda i: int(i.row_id) if i.row_id.isdigit() else 0):
        domain_tag = f"[{item.domain}]" if item.domain else "[域未标注]"
        if item.opener_path:
            action = f"opener 在 `{item.opener_path}`，复制即用"
        else:
            action = "尚未出 opener，需先备一份"
        lines.append(f"- #{item.row_id} {domain_tag} {item.summary}：{action}")
    lines.append("详见跨桌任务队列.md §一；同一行号只在首次出现时提醒，不重复打扰。")
    return "\n".join(lines)


async def send_open_pool_reminder(
    connector, audit, alert_text: str, recipient: str, *, fallback_send=None,
    action_prefix: str = "open_pool_reminder",
) -> None:
    """形状仿 `decision_reminder.send_decision_reminder`（同一通道范式：
    主通道——智能机器人私信——失败时若提供 `fallback_send`（同步函数，
    走独立群 webhook 通道）在线程池里兜底发一次）。审计 action 名单独
    区分（`open_pool_reminder_*` 而非 `decision_reminder_*`），避免两条
    互不相干的提醒链路在审计轨迹里混为一谈——IATF 可追溯性要求动作可
    精确归因到具体机制，不是"反正都是提醒就共用一个标签"。

    `action_prefix`（队列 #312 缺口二）——同一条发送通道服务两种判据
    （「新增即推」与「陈化催办」），**两者的 audit action 名必须分开**，
    否则事后无从判断某次推送是哪一条判据发出的，与上一段的理由同源。
    缺省值保持既有 `open_pool_reminder`，既有调用点行为一字不变。"""
    try:
        await connector.send_markdown(recipient, alert_text)
    except Exception:  # noqa: BLE001
        audit.record(AuditEvent(
            scenario="wecom-aibot", action=f"{action_prefix}_send_failed", evaluator="system",
            automation_level="L1", decision={"sent": False}, data_sources={},
        ))
        if fallback_send is None:
            return
        try:
            await asyncio.to_thread(fallback_send, alert_text)
        except Exception:  # noqa: BLE001
            audit.record(AuditEvent(
                scenario="wecom-aibot", action=f"{action_prefix}_fallback_failed",
                evaluator="system", automation_level="L1",
                decision={"sent": False}, data_sources={},
            ))
        else:
            audit.record(AuditEvent(
                scenario="wecom-aibot", action=f"{action_prefix}_fallback_sent",
                evaluator="system", automation_level="L1",
                decision={"sent": True, "channel": "webhook"}, data_sources={},
            ))
        return
    audit.record(AuditEvent(
        scenario="wecom-aibot", action=f"{action_prefix}_sent", evaluator="system",
        automation_level="L1", decision={"sent": True, "recipient": recipient}, data_sources={},
    ))
