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
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from zhuopin_platform.audit import AuditEvent
from zhuopin_platform.shared_tools.queue_table import SECTION_COLUMN_COUNTS

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


def build_pool_items(queue_text: str, repo_root: Path) -> list[OpenPoolItem]:
    """解析队列文本 → 可 Open 行 → 逐行核对是否已出 opener，返回完整
    池快照（不筛"新增"，那是 `compute_new_ids` 的职责——本函数纯粹是
    "此刻池子长什么样"）。"""
    rows = parse_open_pool_rows(queue_text)
    if not rows:
        return []
    opener_index = _build_opener_index(discover_opener_files(repo_root))
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
            row_id=row.row_id, domain=row.domain, summary=row.summary, opener_path=opener_rel,
        ))
    return items


def default_state() -> dict:
    return {"known_open_ids": []}


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
) -> None:
    """形状仿 `decision_reminder.send_decision_reminder`（同一通道范式：
    主通道——智能机器人私信——失败时若提供 `fallback_send`（同步函数，
    走独立群 webhook 通道）在线程池里兜底发一次）。审计 action 名单独
    区分（`open_pool_reminder_*` 而非 `decision_reminder_*`），避免两条
    互不相干的提醒链路在审计轨迹里混为一谈——IATF 可追溯性要求动作可
    精确归因到具体机制，不是"反正都是提醒就共用一个标签"。"""
    try:
        await connector.send_markdown(recipient, alert_text)
    except Exception:  # noqa: BLE001
        audit.record(AuditEvent(
            scenario="wecom-aibot", action="open_pool_reminder_send_failed", evaluator="system",
            automation_level="L1", decision={"sent": False}, data_sources={},
        ))
        if fallback_send is None:
            return
        try:
            await asyncio.to_thread(fallback_send, alert_text)
        except Exception:  # noqa: BLE001
            audit.record(AuditEvent(
                scenario="wecom-aibot", action="open_pool_reminder_fallback_failed",
                evaluator="system", automation_level="L1",
                decision={"sent": False}, data_sources={},
            ))
        else:
            audit.record(AuditEvent(
                scenario="wecom-aibot", action="open_pool_reminder_fallback_sent",
                evaluator="system", automation_level="L1",
                decision={"sent": True, "channel": "webhook"}, data_sources={},
            ))
        return
    audit.record(AuditEvent(
        scenario="wecom-aibot", action="open_pool_reminder_sent", evaluator="system",
        automation_level="L1", decision={"sent": True, "recipient": recipient}, data_sources={},
    ))
