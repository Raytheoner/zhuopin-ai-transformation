"""跨桌任务队列 · 单格 K2 外置工具（队列 §一 `#552`，2026-09-10，CC 泳道 `552-k2-tool`／`OP-0910-V`）。

## 它治的是什么

K2 口径（`.claude/rules/队列与落库.md`「读侧禁通读」）：§一 状态格／§四 事项格
≤4 KB，超限把历史回写段迁 `1-转型规划/0-全景路线图/队列行日志/#N.md`，行内留
首段＋末段＋指针。⏰ 2026-09-11 起行长闸（编辑锁 release ⑪）从告警转阻断。

这件事此前**没有工具**，全靠每次手写一次性脚本，安全性取决于当次记得多少——
2026-09-10 当天同一支笔写过两版：`#455` 那版有 `assert log.exists()` 且走追加；
十分钟后 `#550` 那版对既有外置件 `write_text` **整体覆盖**，把 `OP-0910-R` 刚写
的 3178 B 建造对账清成 2079 B，靠 sweep 恰好已 commit 才 `git checkout --` 救回
（成因全文见队列 §一 `#552`）。同日手写原型另外两次实撞：**保留段选错致改后
仍超闸**；**重跑把同一段追加两次**。⇒ 本工具是 K2 外置的**单一入口**，把上述
四条都做成机器断言，不再靠记性。

## 硬性三条（`#552` ⑴⑵，一条都不放松）

1. 🔴 **外置件只追加、绝不覆盖**：既有文件 ⇒ `exists` ＋体积下限断言后
   `open(path, "a")` 追加；不存在 ⇒ 才走创建路径。全文件没有任何一处
   `write_text`／`open(..., "w")` 指向外置件。
2. 🔴 **写后回读两侧**：新段命中（每个外置段原文在回读文本里逐字出现）＋
   旧内容锚点仍在（回读文本以写前全文为前缀，`startswith`）＋ md5 与内存中
   预计算值一致。任一不符 ⇒ 非零退出、不产出新格 JSON。
3. 🔴 **段结构先断言再动手，不猜**：`--apply` 必带 `--expect-segments N`，
   实际段数≠N 即拒绝；§一 首段必须以 `[S:` 机器字段起首且必须保留（否则
   状态机器字段随外置消失）；每段的序号／字节数／首 40 字在 plan 阶段全部
   打印，人看过再 `--apply`。

## 幂等（`#552` ⑷ 与原型实撞 ②）

已在外置件里逐字出现的段**不再追加**（只从新格里移除、并在指针里计数）；
既有指针段（含本行外置件路径的段）不外置、并入新指针文案（原文本就在外置件
里，重复写只会制造第二份"真相"）。新格 UTF-8 字节数 **<4096 才产出**，否则
报错、外置件一个字节都不写（原型实撞 ①）。

## 边界（如实写，不暗示全覆盖）

- 🔴 **本工具不写队列真身**。它只产出 `{"set": {"状态": "<新格>"}}` 形态的
  JSON（§四 为 `"事项"`），由调用方持锁后走
  `工具-共享文档编辑锁.py edit-row --changes-json <该文件>` 落格——写入路径
  仍是编辑锁那一条，本工具不开第二条。
- 外置件本身不在编辑锁保护下（它不是队列真身）；调用方 release 时仍须把它
  登进 §二 文件清单（反引号包路径），本工具不代登。
- 段切分只认 `━━━`（与编辑锁 `CONCLUSION_SEGMENT_SEPARATOR` 同一常量）；
  反引号内作为字面量出现的 `━━━` 同样会被切——`--expect-segments` 就是防
  这一类的，plan 打印出来的段表看一眼即知。

## 用法

    # 1) 只看：打印段表与预计新格字节数，不写任何文件
    python 0-学习与工具/工具-队列行K2外置.py --row 552
    # 2) 执行：追加写外置件、产出 edit-row 用 JSON（默认保留首段＋末段）
    python 0-学习与工具/工具-队列行K2外置.py --row 552 --expect-segments 5 \\
        --who "CC OP-0910-V" --apply
    # 3) 落格（持锁，正常编辑锁纪律）
    python 0-学习与工具/工具-共享文档编辑锁.py acquire --who "CC OP-0910-V" --note "…"
    python 0-学习与工具/工具-共享文档编辑锁.py edit-row --who "CC OP-0910-V" \\
        --section 一 --number 552 --changes-json "reports/k2外置/一-#552.changes.json"
    # 4) 反查：队列里该格现在与 JSON 一致且 <4096 B
    python 0-学习与工具/工具-队列行K2外置.py --verify-json "reports/k2外置/一-#552.changes.json"

`--keep` 指定行内保留哪几段（1 起算，负数从末尾数，默认 `1,-1`＝首段＋末段）；
`--section 一|四`（默认按行号在 §一 找，两分区都命中时要求显式给）；`--file`
指向某一份队列文件（默认在两份真身里找）。

## 单段格拆分（`OP-0911-F`，派单件 `派单件-【CC】K2单段格拆分-2026-09-11.md`）

整格**没有 `━━━`、只有一段**且 >4096 B 时（`#537` 4409 B 实例），`--keep` 给不出
「保留首段但把它拆开」这个动作——首段带 `[S:][D:]` 机器字段不能整段外置。本分支
允许**在段内切一刀**：行内留切点之前的部分＋指针，切点之后的原文外置。
🔴 **只加分支、不动主干**：多段格照旧走上面的按段路径，一行代码都没改。

🔴 **安全切点三条同时满足才算**（判据一律只读引用编辑锁／`queue_table`，不重抄）：
① 反引号成对——切完两侧各自成对（`_balance_backticks` 偶数判据）且各自没有
   未闭合游程（`queue_table.has_unbalanced_backtick_run`，即 `edit-row` 写侧同一把闸）；
② 不在代码块内——`工具-opener块lint.py::iter_fenced_blocks` 认出的围栏块之内不切；
③ 不在 markdown 表格行内——以 `|` 开头的行内不切（`#532` 实撞：裸竖线顶偏两列）。
**切点选法**：先语义边界（`⑴⑵⑶`／`①②③` 序号前、`🔴🔑⚠️` 等标记前、`**粗体小标题**`
前）取最靠近上限的可行点；再退到「句号后」；最后退到字节兜底（自上限向前找最近的
安全且读得通的切点）。行内那部分须仍以 `[S:` 起首、新格 <4096 B、且**读得通**
（切点前一字是句末标点，不是半句话）。🔴 **找不到任何安全切点 ⇒ 拒绝、退出码 2、
一个字节不写**——宁可该行继续超限（它不阻断别人），也不可切坏。

    python 0-学习与工具/工具-队列行K2外置.py --row 537            # plan：打印切点位置与两侧字节
    python 0-学习与工具/工具-队列行K2外置.py --row 537 --split-single \\
        --expect-segments 1 --who "CC OP-0911-F" --apply             # 真写（外置侧硬性三条照旧）
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
_REPO_GUESS = _TOOLS_DIR.parent

# 复用编辑锁的判据常量（同 `工具-跟进信README行长外置.py` 手法）：行长上限、
# 段分隔符、仓库根（`git rev-parse --git-common-dir`，各 worktree 共用同一份
# 队列与同一个外置件目录）。不另立第二套数值，避免"外置工具认为达标、
# release 判据仍拦"的口径漂移。
_EDIT_LOCK_SCRIPT = _TOOLS_DIR / "工具-共享文档编辑锁.py"
_editlock_spec = importlib.util.spec_from_file_location("_k2_externalize_editlock_reuse", _EDIT_LOCK_SCRIPT)
editlock = importlib.util.module_from_spec(_editlock_spec)
sys.modules[_editlock_spec.name] = editlock
_editlock_spec.loader.exec_module(editlock)

REPO_ROOT: Path = editlock.REPO_ROOT
ROW_LENGTH_CAP_BYTES: int = editlock.ROW_LENGTH_CAP_BYTES
SEGMENT_SEP: str = editlock.CONCLUSION_SEGMENT_SEPARATOR
# §一 取状态列（cells[5]）、§四 取事项列（cells[1]）——与编辑锁 ⑪ 同一口径。
_CHECK_INDEX: dict[str, int] = dict(editlock._ROW_LENGTH_CHECK_INDEX)
_CHECK_LABEL: dict[str, str] = {"一": "状态", "四": "事项"}

_PLATFORM_PATH = _REPO_GUESS / "5-平台底座" / "zhuopin_platform"
if not _PLATFORM_PATH.is_dir():
    _PLATFORM_PATH = REPO_ROOT / "5-平台底座" / "zhuopin_platform"
if _PLATFORM_PATH.is_dir() and str(_PLATFORM_PATH) not in sys.path:
    sys.path.insert(0, str(_PLATFORM_PATH))
from zhuopin_platform.shared_tools import queue_table  # noqa: E402

LOG_DIR_REL = "1-转型规划/0-全景路线图/队列行日志"
# 既有文件的体积下限：一个合法外置件至少有 frontmatter（`---`＋title＋…），
# 比这还小的"既有文件"更像是被截断的残骸——停手让人看，而不是往残骸上追加。
MIN_EXISTING_LOG_BYTES = 64
DEFAULT_OUT_DIR_REL = "reports/k2外置"
CELL_JOIN = f" {SEGMENT_SEP} "

LIVE_SECTION_HEADING_RE = re.compile(r"^## ([一二三四])、", re.MULTILINE)
STATUS_FIELD_PREFIX = "[S:"


class K2Error(RuntimeError):
    """任何让本工具停手的情形——调用方据此知道：外置件未动、JSON 未产出。"""


# ---------------------------------------------------------------------------
# 读单格
# ---------------------------------------------------------------------------

def _split_live_sections(text: str) -> dict[str, str]:
    matches = list(LIVE_SECTION_HEADING_RE.finditer(text))
    sections: dict[str, str] = {}
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[m.group(1)] = text[start:end]
    return sections


def find_cell(text: str, section: str, row_id: str) -> str | None:
    """在一份队列文件正文里找 §section 编号 row_id 的目标格（§一 状态／§四 事项）。
    找不到返回 None；列数≠分区标准列数的行直接拒绝（塌列行先修再外置）。"""
    section_text = _split_live_sections(text).get(section, "")
    for _line, cells, count_ok in queue_table.parse_section_rows(section_text, section):
        if not cells or cells[0] != row_id:
            continue
        if not count_ok:
            raise K2Error(
                f"§{section} #{row_id} 列数 {len(cells)} ≠ 分区标准 "
                f"{queue_table.SECTION_COLUMN_COUNTS[section]}——塌列行请先走 "
                "`edit-row --repair` 修好，再外置。"
            )
        return cells[_CHECK_INDEX[section]]
    return None


def locate_cell(
    row_id: str, section: str | None, file_rel: str | None,
) -> tuple[str, str, str]:
    """返回 (命中的队列文件相对路径, 分区, 目标格原文)。两分区／两文件都命中
    时不猜，要求调用方显式指定。"""
    files = [file_rel] if file_rel else list(queue_table.iter_queue_paths())
    sections = [section] if section else ["一", "四"]
    hits: list[tuple[str, str, str]] = []
    for rel in files:
        path = REPO_ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for sec in sections:
            cell = find_cell(text, sec, row_id)
            if cell is not None:
                hits.append((rel, sec, cell))
    if not hits:
        raise K2Error(f"#{row_id} 在 {'、'.join(files)} 的 §{'/'.join(sections)} 里都没找到。")
    if len(hits) > 1:
        where = "；".join(f"{rel} §{sec}" for rel, sec, _ in hits)
        raise K2Error(f"#{row_id} 命中不止一处（{where}），请用 --section／--file 指明。")
    return hits[0]


# ---------------------------------------------------------------------------
# 段切分与选段
# ---------------------------------------------------------------------------

def split_segments(cell: str) -> list[str]:
    """按 `━━━` 切段并去首尾空白；空段（如格尾多余分隔符）丢弃。"""
    return [seg.strip() for seg in cell.split(SEGMENT_SEP) if seg.strip()]


def parse_keep(spec: str, total: int) -> list[int]:
    """把 `1,-1` 这类写法解析成 0 起算的下标列表（去重、按原序）。越界即报错。"""
    out: list[int] = []
    for raw in spec.split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            n = int(raw)
        except ValueError:
            raise K2Error(f"--keep 里「{raw}」不是整数。") from None
        if n == 0 or abs(n) > total:
            raise K2Error(f"--keep 里「{raw}」越界（本格共 {total} 段，序号 1..{total} 或 -1..-{total}）。")
        idx = n - 1 if n > 0 else total + n
        if idx not in out:
            out.append(idx)
    if not out:
        raise K2Error("--keep 不能为空。")
    return out


def log_path_for(section: str, row_id: str) -> Path:
    # 既有命名惯例：§一 `#N.md`，§四 `#N-四.md`（目录里已有 `#122-四.md` 等）。
    name = f"#{row_id}.md" if section == "一" else f"#{row_id}-{section}.md"
    return REPO_ROOT / LOG_DIR_REL / name


def log_rel_for(section: str, row_id: str) -> str:
    return f"{LOG_DIR_REL}/{log_path_for(section, row_id).name}"


def is_pointer_segment(segment: str, log_rel: str) -> bool:
    """既有指针段＝提到了本行自己的外置件路径。它的内容（md5／批次说明）在
    外置件里没有对应原文，外置它没有意义；并入新指针即可。"""
    return log_rel in segment


class Plan:
    __slots__ = (
        "file_rel", "section", "row_id", "cell", "segments", "keep", "externalize",
        "already", "pointers", "pointer_record", "log_path", "log_rel", "log_exists",
    )

    def __init__(self, file_rel: str, section: str, row_id: str, cell: str, keep_spec: str):
        self.file_rel = file_rel
        self.section = section
        self.row_id = row_id
        self.cell = cell
        self.segments = split_segments(cell)
        if not self.segments:
            raise K2Error(f"§{section} #{row_id} 目标格为空。")
        self.keep = parse_keep(keep_spec, len(self.segments))
        self.log_path = log_path_for(section, row_id)
        self.log_rel = log_rel_for(section, row_id)
        self.log_exists = self.log_path.exists()
        existing = self.log_path.read_text(encoding="utf-8") if self.log_exists else ""
        self.externalize: list[int] = []
        self.already: list[int] = []
        self.pointers: list[int] = []
        # 被并入新指针、要从本格移除的旧指针段：其原文（旧 md5／旧批次说明）也
        # 要留一份在外置件里，"原文原样"不留缺口；已在件内的不重录（幂等）。
        self.pointer_record: list[int] = []
        for i, seg in enumerate(self.segments):
            if i in self.keep:
                continue
            if is_pointer_segment(seg, self.log_rel):
                self.pointers.append(i)
                if not (existing and seg in existing):
                    self.pointer_record.append(i)
            elif existing and seg in existing:
                self.already.append(i)
            else:
                self.externalize.append(i)

    # ---- 结构断言（`#552` ⑵）------------------------------------------------
    def assert_structure(self, expect_segments: int | None) -> None:
        n = len(self.segments)
        if n < 2:
            raise K2Error(f"§{self.section} #{self.row_id} 只有 {n} 段，没有可外置的中间段。")
        if expect_segments is not None and expect_segments != n:
            raise K2Error(f"段数断言失败：--expect-segments {expect_segments}，实际 {n} 段。先看 plan 再动手。")
        if 0 not in self.keep:
            raise K2Error("首段必须保留（--keep 须含 1）——§一 的 `[S:…][D:…]` 机器字段就在首段。")
        if self.section == "一" and not self.segments[0].startswith(STATUS_FIELD_PREFIX):
            raise K2Error(f"§一 首段不以 `{STATUS_FIELD_PREFIX}` 起首（实际：{self.segments[0][:40]!r}），结构不符预期，停手。")
        if not (self.externalize or self.already or self.pointers):
            raise K2Error("按当前 --keep 没有任何段会离开本格——无事可做。")

    def classify(self, i: int) -> str:
        if i in self.keep:
            return "KEEP"
        if i in self.pointers:
            return "POINTER→并入新指针"
        if i in self.already:
            return "ALREADY-IN-LOG（不重复追加）"
        return "EXTERNALIZE"

    def table(self) -> str:
        lines = [f"§{self.section} #{self.row_id} @ {self.file_rel}：原格 {len(self.cell.encode('utf-8'))} B，共 {len(self.segments)} 段；外置件 {self.log_rel}（{'已存在' if self.log_exists else '不存在，将创建'}）"]
        for i, seg in enumerate(self.segments):
            head = seg[:40].replace("\n", " ")
            lines.append(f"  [{i + 1:>2}] {len(seg.encode('utf-8')):>5} B  {self.classify(i):<28} {head}…")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 产物拼装
# ---------------------------------------------------------------------------

def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def build_log_batch(plan: Plan, who: str, today: str, batch_no: int) -> str:
    """本批要追加到外置件末尾的文本。分隔线＋标题＋逐段原文（段间留 `━━━`
    独立一行，保证每段原文逐字可 grep、也可被幂等判定 `seg in existing` 命中）。"""
    idx_text = "、".join(str(i + 1) for i in plan.externalize) or "无"
    body = f"\n\n{SEGMENT_SEP}\n\n".join(plan.segments[i] for i in plan.externalize)
    text = (
        f"\n---\n\n# §{plan.section} #{plan.row_id} · 外置段（{today} 外置，工具第 {batch_no} 批，"
        f"{len(plan.externalize)} 段，原文原样）\n\n"
        f"> 外置人 {who}；外置前整格 {len(plan.cell.encode('utf-8'))} B、共 {len(plan.segments)} 段；"
        f"本批外置第 {idx_text} 段；本格保留第 {'、'.join(str(i + 1) for i in sorted(plan.keep))} 段。\n"
    )
    if body:
        text += f"\n{body}\n"
    if plan.pointer_record:
        text += (
            f"\n> 以下 {len(plan.pointer_record)} 条为本批并入新指针、自本格移除的旧指针段原文"
            f"（第 {'、'.join(str(i + 1) for i in plan.pointer_record)} 段）：\n\n"
            + f"\n\n{SEGMENT_SEP}\n\n".join(plan.segments[i] for i in plan.pointer_record) + "\n"
        )
    return text


def build_log_frontmatter(plan: Plan, today: str) -> str:
    return (
        "---\n"
        f'title: "队列行日志 #{plan.row_id}（§{plan.section}）"\n'
        f"created: {today}\n"
        "status: 生效\n"
        f"用途: 跨桌任务队列 §{plan.section} #{plan.row_id} 的{_CHECK_LABEL[plan.section]}格历史回写段外置件"
        "（K2 口径：单格 ≤4 KB，超限外置；原文原样、可 grep）。行内只留首段＋末段＋指针。\n"
        f"生成: 0-学习与工具/工具-队列行K2外置.py\n"
        "---\n"
    )


def build_pointer(plan: Plan, who: str, today: str, file_md5: str, batch_no: int) -> str:
    """行内指针文案（`#552` ⑶：统一文案，含 md5 与「本格只留哪几段」）。"""
    moved = len(plan.externalize) + len(plan.already)
    kept = "、".join(str(i + 1) for i in sorted(plan.keep))
    parts = [
        f"📎 **{moved} 段已于 {today} 外置**（K2 口径，原文原样、可 grep，文件 md5:{file_md5[:8]}，工具第 {batch_no} 批）"
        f"见 `{plan.log_rel}`；本格只留原第 {kept} 段（共 {len(plan.segments)} 段）＋本指针（外置人 {who}）。"
    ]
    if plan.already:
        parts.append(f"其中 {len(plan.already)} 段此前已在外置件内、本次未重复追加。")
    if plan.pointers:
        parts.append(f"此前 {len(plan.pointers)} 条指针段已并入本指针，先后各批原文均在同一文件。")
    return "".join(parts)


def build_new_cell(plan: Plan, pointer: str) -> str:
    """新格＝保留段按原序拼回，指针紧跟首段。"""
    kept = [plan.segments[i] for i in sorted(plan.keep)]
    return CELL_JOIN.join([kept[0], pointer, *kept[1:]])


def count_batches(log_text: str, plan: Plan) -> int:
    # 只数本工具自己写的批次标题——手写外置件的标题五花八门，数进来会虚报。
    return len(re.findall(rf"^# §{plan.section} #{re.escape(plan.row_id)} · 外置段（", log_text, flags=re.MULTILINE))


# ---------------------------------------------------------------------------
# 单段格拆分（`OP-0911-F`）：切点判据与选点
# ---------------------------------------------------------------------------

# 语义边界（派单件 §一.1 的「切点选法」）。三类同属「子句级」边界，不分先后、
# 取最靠近上限的可行点；「句号后」单独一档在其后；再往后才是字节兜底。
# 🔴 类别只决定退档顺序与指针里的「切点依据」文案，安全与否另由三条判据判。
_SEQ_MARK_RE = re.compile(r"[⑴-⑽①-⑳]")
_CLAUSE_MARK_RE = re.compile(r"[🔴🔑⚠✅⏰📦🔁📎🟡🛑⏭🛡📌❌✗✓ℹ]")
_BOLD_HEAD_RE = re.compile(r"\*\*[^*\n]{1,60}\*\*")
_SENTENCE_END_RE = re.compile(r"。")
# 「读得通」＝切点前一字是句末标点或闭合的粗体（`**`）——半句话不算。
_READABLE_TAIL = ("。", "；", "！", "？", "）", "」", "』", "】", ")", ".", ";", "**")
# 兜底字节切时允许停在哪些字符之后（与「读得通」同一集合，只是不要求语义标记）。
_FALLBACK_STOP_CHARS = "。；！？）」』】).;"


class Cut:
    __slots__ = ("pos", "kind", "head", "tail")

    def __init__(self, cell: str, pos: int, kind: str):
        self.pos = pos
        self.kind = kind
        self.head = cell[:pos].rstrip()
        self.tail = cell[pos:].lstrip()

    @property
    def head_bytes(self) -> int:
        return len(self.head.encode("utf-8"))

    @property
    def tail_bytes(self) -> int:
        return len(self.tail.encode("utf-8"))


def _line_at(text: str, pos: int) -> str:
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    return text[start:] if end == -1 else text[start:end]


def _fenced_block_line_numbers(text: str) -> set[int]:
    """围栏代码块覆盖的行号集（1 起算，含开闭围栏行）。判据只读引用
    `工具-opener块lint.py::iter_fenced_blocks`（编辑锁 release 守卫同一份），不重写。"""
    lint = editlock._load_opener_lint_module()
    covered: set[int] = set()
    for block in lint.iter_fenced_blocks(text):
        first = block.start_line - 1                 # 开启围栏行（start_line＝块首行正文）
        last = block.start_line + len(block.lines)   # 闭合围栏行（无闭合时＝文末下一行，无害）
        covered.update(range(first, last + 1))
    return covered


def _blocked_by_backticks(head: str, tail: str) -> bool:
    """切点判据①：反引号成对。两侧各自偶数（`_balance_backticks` 判据）且各自无
    未闭合游程（`edit-row` 写侧同一把闸 `has_unbalanced_backtick_run`）。"""
    return editlock._balance_backticks(head) != head or editlock._balance_backticks(tail) != tail or queue_table.has_unbalanced_backtick_run(head) or queue_table.has_unbalanced_backtick_run(tail)  # 切点判据①


def _blocked_by_code_fence(text: str, pos: int) -> bool:
    """切点判据②：不在代码块内。切点所在行落在围栏块（含围栏行）之内即拒。"""
    return (text.count("\n", 0, pos) + 1) in _fenced_block_line_numbers(text)  # 切点判据②


def _blocked_by_table_row(text: str, pos: int) -> bool:
    """切点判据③：不在 markdown 表格行内。切点所在行以 `|` 开头即拒。"""
    return _line_at(text, pos).lstrip().startswith("|")  # 切点判据③


_CODE_SPAN_RE = re.compile(r"(`+)[^`]*?\1")


def _bold_marks_outside_code(text: str) -> int:
    """`**` 计数，反引号跨度内的字面量不算（`#537` 实例：引用的 hook 回显 `… 🔴 **代执行优先…`
    夹在反引号里，若照数会让其后每个切点的粗体奇偶全部错位）。只服务粗体奇偶，不是反引号判据。"""
    return _CODE_SPAN_RE.sub("", text).count("**")


def _head_reads_whole(head: str) -> bool:
    """切点判据④（行内部分须读得通）：切点前一字是句末标点／闭合粗体，不是半句话；
    且行内部分的 `**` 成对（`…复跑一次。** 🔴` 这类「句号后紧跟粗体闭合」的位置不切）。"""
    return head.endswith(_READABLE_TAIL) and _bold_marks_outside_code(head) % 2 == 0  # 切点判据④


def cut_block_reason(cell: str, pos: int, section: str) -> str | None:
    """返回该位置**不能**切的原因（点名卡在哪一类边界）；能切返回 None。"""
    cut = Cut(cell, pos, "")
    if not cut.head or not cut.tail:
        return "切点在格首或格尾"
    if section == "一" and not cut.head.startswith(STATUS_FIELD_PREFIX):
        return "行内部分不以 [S: 起首"
    if _blocked_by_backticks(cut.head, cut.tail):
        return "反引号"
    if _blocked_by_code_fence(cell, pos):
        return "代码块"
    if _blocked_by_table_row(cell, pos):
        return "表格行"
    if not _head_reads_whole(cut.head):
        return "半句话（读不通）"
    return None


def _semantic_candidates(cell: str) -> list[tuple[int, str]]:
    """子句级语义边界候选：(切点位置, 依据)。位置＝标记之前。"""
    out: list[tuple[int, str]] = []
    for m in _SEQ_MARK_RE.finditer(cell):
        out.append((m.start(), "序号前"))
    for m in _CLAUSE_MARK_RE.finditer(cell):
        out.append((m.start(), "标记前"))
    for m in _BOLD_HEAD_RE.finditer(cell):
        out.append((m.start(), "粗体小标题前"))
    return out


def _sentence_candidates(cell: str) -> list[tuple[int, str]]:
    return [(m.end(), "句号后") for m in _SENTENCE_END_RE.finditer(cell)]


def _fallback_candidates(cell: str) -> list[tuple[int, str]]:
    return [(i + 1, "字节兜底") for i, ch in enumerate(cell) if ch in _FALLBACK_STOP_CHARS]


def find_cut(cell: str, section: str, fits: "callable") -> tuple[Cut | None, dict[str, int]]:
    """按档位退：子句级语义边界 → 句号后 → 字节兜底；每档内取**最靠近上限**的可行点。
    `fits(cut)` 由调用方给（新格是否 <4096，含指针）。返回 (切点或 None, 各拒绝原因计数)。"""
    rejects: dict[str, int] = {}
    seen: set[int] = set()
    for tier in (_semantic_candidates(cell), _sentence_candidates(cell), _fallback_candidates(cell)):
        for pos, kind in sorted(tier, key=lambda t: -t[0]):
            if pos in seen:
                continue
            seen.add(pos)
            cut = Cut(cell, pos, kind)
            if not fits(cut):
                rejects["新格仍 ≥ 上限"] = rejects.get("新格仍 ≥ 上限", 0) + 1
                continue
            reason = cut_block_reason(cell, pos, section)
            if reason is None:
                return cut, rejects
            rejects[reason] = rejects.get(reason, 0) + 1
    return None, rejects


# ---------------------------------------------------------------------------
# 单段格拆分：产物拼装
# ---------------------------------------------------------------------------

def build_split_pointer(plan: Plan, cut: Cut, who: str, today: str, file_md5: str, batch_no: int, already: bool) -> str:
    """单段切分的行内指针——与按段外置的指针文案刻意区分：读的人要知道外置件里
    那批正文**直接接在行内结尾之后**，不是另一段。"""
    text = (
        f"✂ **单段格已于 {today} 切分**（K2 口径、原文原样可 grep；切在「{cut.kind}」边界，"
        f"行内留前 {cut.head_bytes} B、后 {cut.tail_bytes} B 已外置；md5:{file_md5[:8]}，工具第 {batch_no} 批）"
        f"见 `{plan.log_rel}`——该批正文**直接接在本格结尾之后**，不是另一段（外置人 {who}）。"
    )
    if already:
        text += "切点后原文此前已在外置件内、本次未重复追加。"
    return text


def build_split_log_batch(plan: Plan, cut: Cut, who: str, today: str, batch_no: int) -> str:
    head_end = cut.head[-24:].replace("\n", " ")
    tail_begin = cut.tail[:24].replace("\n", " ")
    return (
        f"\n---\n\n# §{plan.section} #{plan.row_id} · 外置段（{today} 外置，工具第 {batch_no} 批，"
        f"单段切分，原文原样）\n\n"
        f"> 外置人 {who}；外置前整格 {len(plan.cell.encode('utf-8'))} B、单段无 `{SEGMENT_SEP}`；"
        f"切在「{cut.kind}」边界，行内留切点前 {cut.head_bytes} B、以下为切点后 {cut.tail_bytes} B。"
        f"🔴 **以下正文直接接在行内结尾之后**（行内末「…{head_end}」→ 本批首「{tail_begin}…」），不是另一段。\n"
        f"\n{cut.tail}\n"
    )


def build_split_cell(cut: Cut, pointer: str) -> str:
    return CELL_JOIN.join([cut.head, pointer])


def split_table(plan: Plan, cut: Cut | None, rejects: dict[str, int], predicted_size: int | None) -> str:
    lines = [f"  [拆分] 单段格 {len(plan.cell.encode('utf-8'))} B ≥ {ROW_LENGTH_CAP_BYTES} B，走单段切分分支（--split-single）："]
    if cut is None:
        summary = "；".join(f"{k}×{v}" for k, v in rejects.items()) or "无候选"
        lines.append(f"  ✗ 找不到安全切点（候选逐一被拒：{summary}）——拒绝，不猜、不硬切。")
        return "\n".join(lines)
    lines.append(
        f"  切点 @ 字符 {cut.pos}／字节 {len(plan.cell[:cut.pos].encode('utf-8'))}，依据「{cut.kind}」；"
        f"行内留 {cut.head_bytes} B，外置 {cut.tail_bytes} B；预计新格 {predicted_size} B"
    )
    lines.append(f"  行内末：…{cut.head[-40:]!r}")
    lines.append(f"  外置首：{cut.tail[:40]!r}…")
    if rejects:
        lines.append("  更靠近上限的候选被拒：" + "；".join(f"{k}×{v}" for k, v in rejects.items()))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 只追加写 ＋ 回读两侧
# ---------------------------------------------------------------------------

def append_only_write(path: Path, existing: str, addition: str) -> str:
    """🔴 外置件唯一的写盘函数。既有文件只能 `a` 模式追加；返回回读全文。

    写后三项回读：① 以写前全文为前缀（旧内容锚点仍在，一个字节都没少）；
    ② 追加文本逐字出现；③ 长度恰等于两者之和。任一不成立即抛错——不回滚、
    不重试，让人看。"""
    if path.exists():
        size = path.stat().st_size
        if size < MIN_EXISTING_LOG_BYTES:
            raise K2Error(f"既有外置件 {path.name} 只有 {size} B（< {MIN_EXISTING_LOG_BYTES} B 下限），疑似残骸，停手。")
        if path.read_text(encoding="utf-8") != existing:
            raise K2Error(f"外置件 {path.name} 在本工具读取后被改动，停手重跑。")
        with path.open("a", encoding="utf-8", newline="") as fh:
            fh.write(addition)
    else:
        if existing:
            raise K2Error("内部不一致：文件不存在却带有既有内容。")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="") as fh:  # `x`：已存在即抛，不可能覆盖
            fh.write(addition)
    reread = path.read_text(encoding="utf-8")
    if not reread.startswith(existing):
        raise K2Error(f"回读失败：旧内容锚点不在（{path.name} 不以写前全文为前缀）。")
    if addition not in reread:
        raise K2Error(f"回读失败：新段未命中（{path.name}）。")
    if len(reread) != len(existing) + len(addition):
        raise K2Error(f"回读失败：长度 {len(reread)} ≠ {len(existing)} + {len(addition)}（{path.name}）。")
    return reread


def apply(plan: Plan, who: str, today: str, out_path: Path) -> dict:
    existing = plan.log_path.read_text(encoding="utf-8") if plan.log_exists else ""
    needs_write = bool(plan.externalize or plan.pointer_record)
    batch_no = count_batches(existing, plan) + (1 if needs_write else 0)
    addition = ""
    if needs_write:
        addition = ("" if existing else build_log_frontmatter(plan, today)) + build_log_batch(plan, who, today, batch_no)
    elif not existing:
        raise K2Error("没有新段要写，外置件却不存在——ALREADY/POINTER 判定不可能在无文件时成立，内部不一致。")
    predicted = existing + addition
    file_md5 = _md5(predicted)

    # 先算新格、先卡闸，再碰磁盘（原型实撞 ①：保留段选错致改后仍超闸）。
    pointer = build_pointer(plan, who, today, file_md5, max(batch_no, 1))
    new_cell = build_new_cell(plan, pointer)
    new_size = len(new_cell.encode("utf-8"))
    if new_size >= ROW_LENGTH_CAP_BYTES:
        raise K2Error(
            f"新格 {new_size} B ≥ {ROW_LENGTH_CAP_BYTES} B，仍超闸——外置件未写、JSON 未产出。"
            f"请换 --keep（当前保留第 {'、'.join(str(i + 1) for i in sorted(plan.keep))} 段）。"
        )
    if queue_table.has_bare_pipe(new_cell) and not queue_table.has_bare_pipe(plan.cell):
        raise K2Error("新格出现裸竖线而原格没有——指针文案有误，停手。")

    if addition:
        reread = append_only_write(plan.log_path, existing, addition)
        for i in [*plan.externalize, *plan.pointer_record]:
            if plan.segments[i] not in reread:
                raise K2Error(f"回读失败：第 {i + 1} 段原文未在外置件中逐字命中。")
        if _md5(reread) != file_md5:
            raise K2Error("回读失败：外置件 md5 与预计算不一致。")
    else:
        reread = existing
        for i in plan.already:
            if plan.segments[i] not in reread:
                raise K2Error(f"内部不一致：第 {i + 1} 段判为已在外置件，回读却未命中。")

    payload = {"set": {_CHECK_LABEL[plan.section]: new_cell}}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "file_rel": plan.file_rel, "section": plan.section, "row_id": plan.row_id,
        "old_size": len(plan.cell.encode("utf-8")), "new_size": new_size,
        "externalized": [i + 1 for i in plan.externalize], "already": [i + 1 for i in plan.already],
        "pointers_merged": [i + 1 for i in plan.pointers], "pointers_recorded": [i + 1 for i in plan.pointer_record], "kept": [i + 1 for i in sorted(plan.keep)],
        "log_rel": plan.log_rel, "log_md5": file_md5, "log_bytes": len(reread.encode("utf-8")),
        "batch_no": max(batch_no, 1), "changes_json": str(out_path),
    }


def plan_split(plan: Plan, who: str, batch_hint: int) -> tuple[Cut | None, dict[str, int], int | None]:
    """选切点：`fits` 用真实指针文案（md5 占位、宽度相同）算新格字节数，
    保证 plan 打出来的预计字节与 apply 真算的一致。"""
    if len(plan.segments) != 1:
        raise K2Error(f"§{plan.section} #{plan.row_id} 有 {len(plan.segments)} 段，走按段外置路径（--keep），不用 --split-single。")
    if len(plan.cell.encode("utf-8")) < ROW_LENGTH_CAP_BYTES:
        raise K2Error(f"§{plan.section} #{plan.row_id} 单段 {len(plan.cell.encode('utf-8'))} B 未超闸，无事可做。")
    if plan.section == "一" and not plan.cell.startswith(STATUS_FIELD_PREFIX):
        raise K2Error(f"§一 格不以 `{STATUS_FIELD_PREFIX}` 起首（实际：{plan.cell[:40]!r}），结构不符预期，停手。")

    def predicted(cut: Cut) -> int:
        pointer = build_split_pointer(plan, cut, who, "0000-00-00", "0" * 32, batch_hint, already=True)
        return len(build_split_cell(cut, pointer).encode("utf-8"))

    cut, rejects = find_cut(plan.cell, plan.section, lambda c: predicted(c) < ROW_LENGTH_CAP_BYTES)
    return cut, rejects, (predicted(cut) if cut else None)


def apply_split(plan: Plan, cut: Cut, who: str, today: str, out_path: Path) -> dict:
    """单段切分真写。外置侧硬性与 `apply` 一字不差：只追加（`append_only_write` 唯一
    写盘口）、写前 exists＋体积下限、写后回读两侧、幂等跳过、新格 <4096 才产出。"""
    existing = plan.log_path.read_text(encoding="utf-8") if plan.log_exists else ""
    already = bool(existing) and cut.tail in existing
    needs_write = not already
    batch_no = count_batches(existing, plan) + (1 if needs_write else 0)
    addition = ""
    if needs_write:
        addition = ("" if existing else build_log_frontmatter(plan, today)) + build_split_log_batch(plan, cut, who, today, batch_no)
    predicted_text = existing + addition
    file_md5 = _md5(predicted_text)

    # 先算新格、先卡闸，再碰磁盘（同 `apply`）。
    pointer = build_split_pointer(plan, cut, who, today, file_md5, max(batch_no, 1), already)
    new_cell = build_split_cell(cut, pointer)
    new_size = len(new_cell.encode("utf-8"))
    if new_size >= ROW_LENGTH_CAP_BYTES:  # 切点判据⑤：新格 <4096 才产出
        raise K2Error(f"新格 {new_size} B ≥ {ROW_LENGTH_CAP_BYTES} B，仍超闸——外置件未写、JSON 未产出。")
    if plan.section == "一" and not new_cell.startswith(STATUS_FIELD_PREFIX):
        raise K2Error("新格不以 [S: 起首——机器字段丢失，停手。")
    if queue_table.has_bare_pipe(new_cell) and not queue_table.has_bare_pipe(plan.cell):
        raise K2Error("新格出现裸竖线而原格没有——指针文案有误，停手。")
    if queue_table.has_unbalanced_backtick_run(new_cell):
        raise K2Error("新格反引号游程未闭合——切点判据失效，停手。")

    if addition:
        reread = append_only_write(plan.log_path, existing, addition)
        if cut.tail not in reread:
            raise K2Error("回读失败：切点后原文未在外置件中逐字命中。")
        if _md5(reread) != file_md5:
            raise K2Error("回读失败：外置件 md5 与预计算不一致。")
    else:
        reread = existing

    payload = {"set": {_CHECK_LABEL[plan.section]: new_cell}}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "file_rel": plan.file_rel, "section": plan.section, "row_id": plan.row_id,
        "old_size": len(plan.cell.encode("utf-8")), "new_size": new_size,
        "cut_pos": cut.pos, "cut_kind": cut.kind, "head_bytes": cut.head_bytes, "tail_bytes": cut.tail_bytes,
        "already": already, "log_rel": plan.log_rel, "log_md5": file_md5, "log_bytes": len(reread.encode("utf-8")),
        "batch_no": max(batch_no, 1), "changes_json": str(out_path),
    }


# ---------------------------------------------------------------------------
# 落格后反查
# ---------------------------------------------------------------------------

def verify_json(json_path: Path, row_id: str | None, section: str | None, file_rel: str | None) -> int:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    label, expected = next(iter(payload["set"].items()))
    sec = section or {"状态": "一", "事项": "四"}[label]
    if row_id is None:
        m = re.search(r"#(\d+)\.changes\.json$", json_path.name)
        if not m:
            raise K2Error("从文件名推不出行号，请传 --row。")
        row_id = m.group(1)
    rel, sec, cell = locate_cell(row_id, sec, file_rel)
    size = len(cell.encode("utf-8"))
    if cell != expected:
        print(f"✗ §{sec} #{row_id} @ {rel} 现格（{size} B）≠ JSON 里的新格（{len(expected.encode('utf-8'))} B）——edit-row 未落或落了别的。")
        return 1
    if size >= ROW_LENGTH_CAP_BYTES:
        print(f"✗ §{sec} #{row_id} 现格 {size} B ≥ {ROW_LENGTH_CAP_BYTES} B。")
        return 1
    print(f"✓ §{sec} #{row_id} @ {rel} 现格与 JSON 一致，{size} B < {ROW_LENGTH_CAP_BYTES} B。")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None, today: datetime.date | None = None) -> int:
    parser = argparse.ArgumentParser(description="跨桌任务队列单格 K2 外置（只追加、回读两侧、先断言再动手）")
    parser.add_argument("--row", help="行号（§一/§四）")
    parser.add_argument("--section", choices=("一", "四"), default=None)
    parser.add_argument("--file", default=None, help="队列文件相对仓库根路径（默认两份真身都找）")
    parser.add_argument("--keep", default="1,-1", help="行内保留的段序号，1 起算、负数从末尾数（默认 1,-1）")
    parser.add_argument("--expect-segments", type=int, default=None, help="段数断言（--apply 必填）")
    parser.add_argument("--who", default=None, help="外置人（写进外置件与指针；--apply 必填）")
    parser.add_argument("--apply", action="store_true", help="真写：追加外置件＋产出 edit-row JSON；不带即只打印 plan")
    parser.add_argument("--out", default=None, help=f"JSON 落点（默认 {DEFAULT_OUT_DIR_REL}/<分区>-#<行号>.changes.json）")
    parser.add_argument("--verify-json", default=None, metavar="文件", help="落格后反查：队列现格是否等于该 JSON 的新格且 <4096 B")
    parser.add_argument("--split-single", action="store_true", help="单段格拆分分支：整格只有一段且 ≥4096 B 时在段内切一刀（--apply 时必须显式给）")
    args = parser.parse_args(argv)
    today_str = (today or datetime.date.today()).isoformat()

    try:
        if args.verify_json:
            return verify_json(Path(args.verify_json), args.row, args.section, args.file)
        if not args.row:
            parser.error("--row 为必填（--verify-json 除外）")
        rel, sec, cell = locate_cell(args.row, args.section, args.file)
        plan = Plan(rel, sec, args.row, cell, args.keep)
        print(plan.table())
        single_over_cap = len(plan.segments) == 1 and len(cell.encode("utf-8")) >= ROW_LENGTH_CAP_BYTES
        if args.split_single or single_over_cap:
            # 单段格拆分分支（`OP-0911-F`）：plan 阶段即打出切点与两侧字节；找不到安全切点即非零退出。
            who_for_plan = args.who or "<外置人>"
            existing_batches = count_batches(plan.log_path.read_text(encoding="utf-8"), plan) if plan.log_exists else 0
            cut, rejects, predicted_size = plan_split(plan, who_for_plan, existing_batches + 1)
            print(split_table(plan, cut, rejects, predicted_size))
            if cut is None:
                raise K2Error("找不到安全切点——拒绝，一个字节未写。宁可该行继续超限，也不可切坏。")
            if not args.apply:
                print("[PLAN] 未写任何文件。确认切点无误后加 --split-single --apply --expect-segments 1 --who <外置人>。")
                return 0
            if not args.split_single:
                raise K2Error("单段格拆分是显式动作：--apply 须同时给 --split-single。")
            if args.expect_segments != 1 or not args.who:
                parser.error("--split-single --apply 必须同时给 --expect-segments 1 与 --who")
            out_path = Path(args.out) if args.out else REPO_ROOT / DEFAULT_OUT_DIR_REL / f"{sec}-#{args.row}.changes.json"
            result = apply_split(plan, cut, args.who, today_str, out_path)
            print(
                f"[OK] 外置件 {result['log_rel']}（{result['log_bytes']} B，md5:{result['log_md5'][:8]}，第 {result['batch_no']} 批）；"
                f"单段切分@字符 {result['cut_pos']}（{result['cut_kind']}），行内留 {result['head_bytes']} B、外置 {result['tail_bytes']} B"
                f"{'（此前已在件内，未重复追加）' if result['already'] else ''}；新格 {result['old_size']} → {result['new_size']} B。"
            )
            print(f"[NEXT] 持锁后：python 0-学习与工具/工具-共享文档编辑锁.py edit-row --who <同持锁人> "
                  f"--section {result['section']} --number {result['row_id']} --changes-json \"{result['changes_json']}\"")
            print(f"[NEXT] 落格后反查：python 0-学习与工具/工具-队列行K2外置.py --verify-json \"{result['changes_json']}\"")
            return 0
        if not args.apply:
            print("[PLAN] 未写任何文件。确认段表无误后加 --apply --expect-segments N --who <外置人>。")
            return 0
        if args.expect_segments is None or not args.who:
            parser.error("--apply 必须同时给 --expect-segments N 与 --who")
        plan.assert_structure(args.expect_segments)
        out_path = Path(args.out) if args.out else REPO_ROOT / DEFAULT_OUT_DIR_REL / f"{sec}-#{args.row}.changes.json"
        result = apply(plan, args.who, today_str, out_path)
    except K2Error as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2

    print(
        f"[OK] 外置件 {result['log_rel']}（{result['log_bytes']} B，md5:{result['log_md5'][:8]}，第 {result['batch_no']} 批）；"
        f"外置第 {result['externalized']} 段，已在件内 {result['already']}，并入指针 {result['pointers_merged']}；"
        f"新格 {result['old_size']} → {result['new_size']} B，保留第 {result['kept']} 段。"
    )
    print(f"[NEXT] 持锁后：python 0-学习与工具/工具-共享文档编辑锁.py edit-row --who <同持锁人> "
          f"--section {result['section']} --number {result['row_id']} --changes-json \"{result['changes_json']}\"")
    print(f"[NEXT] 落格后反查：python 0-学习与工具/工具-队列行K2外置.py --verify-json \"{result['changes_json']}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
