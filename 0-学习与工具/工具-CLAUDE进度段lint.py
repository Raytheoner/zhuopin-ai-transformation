"""CLAUDE.md 顶部进度段 lint（队列 §四 #80 / 派单件 OP-0821-C，判据 J1-J5）。

## 为什么要有这道门禁

「顶部进度段只留最近一批」这条**人守**规则 2026-08-09 与 2026-08-16 被执行过两次，
两次都在 5-6 天内被超额长回来，回涨速率还从 3.4 KB/天升到 7.7 KB/天（2026-08-16 瘦到
83,883 B、5 天后 122,509 B，**已超过瘦身前水位 15%**）。2026-08-21 是第三次人工执行。
按协议〇「规则退休制」，人守条目被违反 3 次即须机制化或删除——本脚本是机制化那一半。

🔴 **但根因不是执行力**：顶部进度段**同时承担两个职能**——① 进度记录（该迁）
② **未闭合项的唯一跨会话载体**（迁走即丢）。2026-08-21 逐条核 12 个待迁条目时，SC2
那两条自己在正文里写着「本段与上一段是本任务仅有的跨会话载体」——机械执行「只留最近
一批」就会把它们丢掉，于是执行的人每次都在同一个地方卡死，然后整段一起不迁。

**⇒ 只做「超限报错」会把它逼成「为了过 lint 而丢掉未闭合项」，比现状更糟。故 J1
（承接载体安全阀）必须先于 J2/J3 生效：本脚本永远不会对一条没有承接载体的条目输出
「请迁移」。**

## 五条判据

- **J1 · 承接载体安全阀**：不单独报错，只作为 J2 的拒绝理由。一条待迁条目通过的条件是
  ⑴ 正文点名了一个**真实存在于队列 §一／§四 的行号**，或 ⑵ 正文含一个**仓库内真实存在
  的文件路径 ＋ 紧随其后的章节号**。不通过 ⇒ 输出「该条无承接载体，请先立队列行再迁」，
  **绝不输出「请迁移」**。
- **J2 · 条目数上限**（默认 6）。
- **J3 · 单条长度上限**（默认 1,200 字符，`len(str)` 非字节）。
- **J4 · 写入侧拦截**：不在本脚本，在 `工具-共享文档编辑锁.py::
  _validate_claude_progress_open_item`（release 校验族）。J1/J2/J3 都是事后收拾，
  **J4 才是治本的那条**——在源头不让「顶部段兼任待办载体」这件事再发生。
- **J5 · 场景级同款**：对 `4-数字员工/*/*/CLAUDE.md` 与 `5-平台底座/*/CLAUDE.md`
  套用 J2/J3。**场景级的「顶部段」边界与根文件不同**，见下方「结构识别」。

## 结构识别（刻意用白名单签名，不做内容猜测）

**支持两种结构，其余一律报「未支持的结构」并列出文件名，不静默放过**（同 CLAUDE.md §5
「工具静默回退」教训——静默跳过会让人以为「全库都扫过了、零违规」）：

- **结构 A · 根文件型**：文件开头到第一条独占一行的 `---` 之间的引用块内，含
  `> **当前进度**` 头行。进度条目区 = 该头行之后 → `📦` 迁移指针行之前。
- **结构 B · SC8 表格型**：含 `## 5. 状态时间线` 标题，其下有表头为 `| 日期 | 状态 |`
  的 markdown 表。进度条目 = 该表的数据行，条目正文取「状态」列。

🔴 **为什么 A 型要靠 `> **当前进度**` 头行而不是「引用块里所有像条目的行」**：派单件
给的裸正则（`^>\\s*(?:🔴\\s*)?\\*\\*` ＋ 日期模式）在 2026-08-21 的真身上数出 **4 条**，
而真值是 **2 条**——多出的两条是 `📦` 迁移指针行与「memory 层已收割并停用」元说明行，
两者结构上与进度条目**完全无法区分**（都是「`> **` ＋ 粗体标题 ＋（日期）」）。靠内容
关键词排除只会再造一条会漂移的人守约定；靠**区间边界**才是结构性的。此事本身就是派单件
警告的那类「判据看起来很确定但错了」的第三个实例（前两个是只匹配 `> **` 前缀那两次）。

## 分期上线（重要）

存量必然超限（2026-08-21 实测根文件两条各 3,131／3,066 字符，均 > 1,200）。故：
- **一期（本次）**：默认 `--warn`，只打印不退非零，CI job 配 `continue-on-error: true`。
- **二期（另派）**：存量清理到位后切 `--enforce`，与 `bootstrap-stub-lint` 一致。

🔴 **一期就上 `--enforce` 会立刻挡住所有人的 push，那会让这条规则第四次被绕过——这次
是被绕过 lint 本身。**

用法：
  python 0-学习与工具/工具-CLAUDE进度段lint.py             # 告警模式（退出码恒 0）
  python 0-学习与工具/工具-CLAUDE进度段lint.py --enforce    # 阻断模式（有违规即 1）
  python 0-学习与工具/工具-CLAUDE进度段lint.py --stats      # 额外打印每条的字符数
  python 0-学习与工具/工具-CLAUDE进度段lint.py --root-only  # 只查根 CLAUDE.md（跳过 J5）
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── 与 `工具-队列结构lint.py` 同一手法：按文件路径加载编辑锁模块，复用其
#    `_split_live_sections`（队列分区切分）与 `queue_table` 委托，不自己再写
#    一套拆表正则——派单件 J1 明文「用 queue_table 模块解析，不要自己写正则拆表」。
EDIT_LOCK_SCRIPT = Path(__file__).resolve().with_name("工具-共享文档编辑锁.py")
_spec = importlib.util.spec_from_file_location("claude_progress_lint_editlock_reuse",
                                               EDIT_LOCK_SCRIPT)
editlock = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(editlock)

# 🔴 REPO_ROOT 刻意**不**复用 `editlock.REPO_ROOT`（那是 `git rev-parse
# --git-common-dir` 解出的「所有 worktree 共享的主工作区」），与
# `工具-队列结构lint.py` 的选择相反——两者治的不是同一种东西：
#   · 队列文件是**共享可变状态**，权威副本只有主工作区那一份，在 linked
#     worktree 里校验本地副本会得出与 release 校验相反的结论（该脚本
#     REPO_ROOT 注释处有完整实测记录）；
#   · CLAUDE.md 是**普通被跟踪文件**，随分支走。本 lint 要回答的是「我这棵
#     树提交上去合不合规」，故必须校验**当前 checkout 这一份**。若解到主
#     工作区，CI（一次性 checkout，两者恰好同一路径）看不出差别，但本机在
#     worktree 里跑就会校验另一份文件、且不报错——正是要避免的静默回退。
REPO_ROOT = Path(__file__).resolve().parents[1]

ROOT_CLAUDE_REL = "CLAUDE.md"
SCENE_GLOBS = ("4-数字员工/*/*/CLAUDE.md", "5-平台底座/*/CLAUDE.md")

ENTRY_COUNT_CAP_DEFAULT = 6
ENTRY_LENGTH_CAP_DEFAULT = 1200

# 结构 A 的四个锚点**一律取编辑锁那份定义**，本文件不另立——J4（release 侧）
# 与 J2/J3（CI 侧）若各持一套正则，会出现「lint 说 7 条、release 说 6 条」
# 这种两套判据各自为政的情形，而这恰恰是本次要治的那一族问题的翻版。
ENTRY_PREFIX_RE = editlock.CLAUDE_PROGRESS_ENTRY_RE
ENTRY_DATE_RE = editlock.CLAUDE_PROGRESS_DATE_RE
PROGRESS_HEADER_RE = editlock.CLAUDE_PROGRESS_HEADER_RE
MIGRATION_POINTER_RE = editlock.CLAUDE_PROGRESS_POINTER_RE

# 结构 B（SC8 表格型）锚点。
SC8_TIMELINE_HEADING_RE = re.compile(r"^##\s*5\.\s*状态时间线")
SC8_TABLE_HEADER_RE = re.compile(r"^\|\s*日期\s*\|\s*状态\s*\|")

# J1 ⑵：路径 ＋ 章节号。路径先按反引号包裹取（本项目正文引用路径的既定写法），
# 章节号须落在该路径之后 `CARRIER_SECTION_WINDOW` 个字符内——不做全条目范围的
# 「有路径 且 有 §」松判据：那会把「条目里随便提到过某文件、又在别处提到某章节」
# 也算成有承接载体，而 J1 判错的代价是对一条其实没有承接的条目说「请迁移」。
CARRIER_PATH_RE = re.compile(r"`([^`\n]{3,200}?\.(?:md|py|ps1|json|yml|yaml))`")
CARRIER_SECTION_RE = re.compile(r"§\s*[0-9一二三四五六七八九十]")
CARRIER_SECTION_WINDOW = 60
CARRIER_ROW_ID_RE = re.compile(r"#(\d{1,4})\b")


@dataclass
class Entry:
    """一条进度条目。`body` 是已剥去 markdown 引用前缀／表格框线的正文，
    J3 的字符数与 J1 的承接载体判定都基于它。"""

    index: int          # 在本文件进度段内的序号，1 起
    line_no: int        # 原文行号，1 起（供人定位）
    body: str
    preview: str = field(default="", repr=False)


@dataclass
class ParsedFile:
    rel_path: str
    structure: str              # "A-根文件型" / "B-SC8表格型" / "" （未支持）
    entries: list[Entry]
    meta_lines: list[tuple[int, str]]   # 被判为元说明、不计入条目的行（供回显）
    unsupported_reason: str = ""


# ────────────────────────────────── 结构解析 ──────────────────────────────────

def top_section_text(text: str) -> tuple[str, int]:
    """结构 A 的「顶部段」＝文件开头 → 第一条**独占一行**的 `---` 之前。

    返回 (顶部段文本, 该 `---` 的行号；无则 0)。注意这条 `---` 是 §1 前的
    分隔线，**不是 frontmatter 分隔符**——本项目的根 CLAUDE.md 没有 frontmatter，
    文件首行是 `# CLAUDE.md — …` 标题。
    """
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip() == "---":
            return "\n".join(lines[:i]), i + 1
    return text, 0


def _strip_quote_prefix(line: str) -> str:
    return re.sub(r"^>\s?", "", line)


def parse_structure_a(text: str) -> ParsedFile | None:
    """结构 A（根文件型）。识别签名＝顶部段内存在 `> **当前进度**` 头行；
    不含该头行即返回 None（交调用方继续试别的结构），**不猜**。

    条目切分**委托 `editlock._claude_progress_entries`**，不在本处另写一套
    ——J4（release 侧）与 J2/J3（CI 侧）必须对「哪几行算进度条目」给出完全
    一致的答案，否则会出现「lint 说 7 条、release 说 6 条」这种两套判据各自
    为政的情形（同 `工具-队列结构lint.py` 复用编辑锁解析函数的既有理由）。
    本函数只额外负责把**落在条目区之外、但形状与条目一样的行**列为元说明行
    并回显——那正是 2026-08-21 把 2 条数成 4 条的那两行，必须让人看见它们被
    排除了，不能静默吞掉。
    """
    head, _ = top_section_text(text)
    lines = head.split("\n")

    if not any(PROGRESS_HEADER_RE.match(ln) for ln in lines):
        return None

    raw = editlock._claude_progress_entries(text)
    entry_line_nos = {line_no for line_no, _ in raw}
    entries = [
        Entry(index=i, line_no=line_no, body=body, preview=body[:60])
        for i, (line_no, body) in enumerate(raw, 1)
    ]
    meta = [
        (i + 1, _strip_quote_prefix(line)[:60])
        for i, line in enumerate(lines)
        if ENTRY_PREFIX_RE.match(line) and ENTRY_DATE_RE.search(line)
        and (i + 1) not in entry_line_nos
    ]
    return ParsedFile(rel_path="", structure="A-根文件型", entries=entries, meta_lines=meta)


def parse_structure_b(text: str) -> ParsedFile | None:
    """结构 B（SC8 表格型）：`## 5. 状态时间线` 标题下、表头为 `| 日期 | 状态 |`
    的表。条目正文取「状态」列——日期列不计入 J3 长度（那不是可压缩的内容）。"""
    lines = text.split("\n")
    heading_idx = next((i for i, ln in enumerate(lines) if SC8_TIMELINE_HEADING_RE.match(ln)), None)
    if heading_idx is None:
        return None

    entries: list[Entry] = []
    meta: list[tuple[int, str]] = []
    in_table = False
    for i in range(heading_idx + 1, len(lines)):
        line = lines[i]
        if line.startswith("## "):
            break
        if SC8_TABLE_HEADER_RE.match(line.strip()):
            in_table = True
            continue
        if not in_table:
            if line.strip():
                meta.append((i + 1, line.strip()[:60]))
            continue
        cells = editlock.queue_table.split_row_cells(line)
        if cells is None:
            if line.strip():
                in_table = False
            continue
        if set(cells[0]) <= {"-", " "}:
            continue
        body = cells[1] if len(cells) > 1 else ""
        entries.append(Entry(index=len(entries) + 1, line_no=i + 1, body=body,
                             preview=f"{cells[0]} | {body[:50]}"))

    if not entries and not in_table:
        return None
    return ParsedFile(rel_path="", structure="B-SC8表格型", entries=entries, meta_lines=meta)


def parse_file(rel_path: str, text: str) -> ParsedFile:
    for parser in (parse_structure_a, parse_structure_b):
        parsed = parser(text)
        if parsed is not None:
            parsed.rel_path = rel_path
            return parsed
    return ParsedFile(
        rel_path=rel_path, structure="", entries=[], meta_lines=[],
        unsupported_reason=(
            "未支持的结构（既无结构 A 的 `> **当前进度**` 头行，也无结构 B 的 "
            "`## 5. 状态时间线` 表）——已跳过，未做 J2/J3 判定"
        ),
    )


# ─────────────────────────────── J1 · 承接载体 ───────────────────────────────

def load_queue_row_ids(repo_root: Path) -> tuple[set[str], list[str]]:
    """读取全部物理队列文件的 §一／§四 行号集合。返回 (行号集合, 告警列表)。

    🔴 **逐份解析后合并，绝不拼接文本再解析一次**：`_split_live_sections`
    用正则依次匹配 `## 一、`… 标题并以「下一个标题或文本末尾」为分区终点，
    把两份文件文本拼起来解析时，第二份的 `## 一、` 会成为第一份 §四 之后的
    又一个分区标题——`sections` 是 dict，**同名 label 后写覆盖先写**，第一份
    的 §一 被第二份整段顶掉、零报错。此坑 2026-08-19 `#312` 已真实发生过一次
    （可 Open 池提醒只跟了一份文件），派单件明文要求配反例单测锁死。

    某份文件缺失 ⇒ 记一条告警并跳过，**不静默降级**（同 #312 修法）。
    """
    ids: set[str] = set()
    warnings: list[str] = []
    for rel in editlock.queue_table.iter_queue_paths():
        path = repo_root / rel
        if not path.is_file():
            warnings.append(f"队列文件 {rel} 不存在——J1 承接载体判定的取数面不完整"
                            f"（不静默降级：此时 J1 只会更保守地拒绝迁移，不会误放行）")
            continue
        sections = editlock._split_live_sections(path.read_text(encoding="utf-8"))
        for label in ("一", "四"):
            for _line, cells in editlock._table_data_rows(sections.get(label, "")):
                if cells and cells[0].strip().lstrip("#").isdigit():
                    ids.add(cells[0].strip().lstrip("#"))
    return ids, warnings


def carrier_of(body: str, repo_root: Path, queue_ids: set[str]) -> str | None:
    """J1：返回该条目的承接载体描述；无载体返回 None。"""
    for m in CARRIER_ROW_ID_RE.finditer(body):
        if m.group(1) in queue_ids:
            return f"队列行 #{m.group(1)}"
    for m in CARRIER_PATH_RE.finditer(body):
        rel = m.group(1).replace("\\", "/")
        if not (repo_root / rel).exists():
            continue
        tail = body[m.end():m.end() + CARRIER_SECTION_WINDOW]
        if CARRIER_SECTION_RE.search(tail):
            return f"具名文件 `{rel}` ＋ 章节号"
    return None


# ───────────────────────────────── J2 / J3 ──────────────────────────────────

def check_entry_count(parsed: ParsedFile, repo_root: Path, queue_ids: set[str],
                      cap: int) -> list[str]:
    """J2（含 J1 安全阀）。超限时对**最早的 N-cap 条**逐条跑 J1：
    有载体的才说「请迁移」，无载体的说「请先立队列行再迁」。"""
    n = len(parsed.entries)
    if n <= cap:
        return []
    to_migrate = parsed.entries[: n - cap]
    lines = [
        f"【J2】顶部进度段现有 {n} 条（上限 {cap}）。请对最早的 {n - cap} 条先跑 J1，"
        f"通过后迁入 1-转型规划/0-全景路线图/进度编年-CHANGELOG.md"
    ]
    for entry in to_migrate:
        carrier = carrier_of(entry.body, repo_root, queue_ids)
        if carrier:
            lines.append(f"  · 第 {entry.index} 条（第 {entry.line_no} 行）可迁——"
                         f"承接载体：{carrier}｜{entry.preview}…")
        else:
            lines.append(f"  · 🔴 第 {entry.index} 条（第 {entry.line_no} 行）"
                         f"**该条无承接载体，请先立队列行再迁**｜{entry.preview}…")
    return lines


def check_entry_length(parsed: ParsedFile, cap: int) -> list[str]:
    """J3。"""
    out = []
    for entry in parsed.entries:
        if len(entry.body) > cap:
            out.append(
                f"【J3】第 {entry.index} 条超长（{len(entry.body)} 字符 > {cap}，"
                f"第 {entry.line_no} 行）。超出部分请写进对应队列行或场景 CLAUDE.md，"
                f"顶部只留结论与指针｜{entry.preview}…"
            )
    return out


# ─────────────────────────────────── 驱动 ───────────────────────────────────

def target_files(repo_root: Path, root_only: bool) -> list[str]:
    targets = [ROOT_CLAUDE_REL]
    if root_only:
        return targets
    for pattern in SCENE_GLOBS:
        targets.extend(sorted(p.relative_to(repo_root).as_posix()
                              for p in repo_root.glob(pattern)))
    return targets


def lint(repo_root: Path, *, root_only: bool = False,
         count_cap: int = ENTRY_COUNT_CAP_DEFAULT,
         length_cap: int = ENTRY_LENGTH_CAP_DEFAULT) -> tuple[list[str], list[str], list[ParsedFile]]:
    """返回 (违规说明列表, 告警列表, 逐文件解析结果)。"""
    queue_ids, warnings = load_queue_row_ids(repo_root)
    violations: list[str] = []
    parsed_all: list[ParsedFile] = []

    for rel in target_files(repo_root, root_only):
        path = repo_root / rel
        if not path.is_file():
            warnings.append(f"{rel} 不存在，已跳过")
            continue
        parsed = parse_file(rel, path.read_text(encoding="utf-8"))
        parsed_all.append(parsed)
        if not parsed.structure:
            # J5 明文要求：未支持的结构须**报出来并列出文件名**，不静默放过。
            warnings.append(f"{rel}：{parsed.unsupported_reason}")
            continue
        for v in check_entry_count(parsed, repo_root, queue_ids, count_cap):
            violations.append(f"[{rel}] {v}")
        for v in check_entry_length(parsed, length_cap):
            violations.append(f"[{rel}] {v}")
    return violations, warnings, parsed_all


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="CLAUDE.md 顶部进度段 lint（J1-J3/J5）")
    ap.add_argument("--enforce", action="store_true",
                    help="有违规即以退出码 1 阻断（默认只告警、退出码 0）")
    ap.add_argument("--stats", action="store_true", help="额外打印每个文件每条的字符数")
    ap.add_argument("--root-only", action="store_true", help="只查根 CLAUDE.md，跳过 J5")
    ap.add_argument("--count-cap", type=int, default=ENTRY_COUNT_CAP_DEFAULT)
    ap.add_argument("--length-cap", type=int, default=ENTRY_LENGTH_CAP_DEFAULT)
    ap.add_argument("--repo-root", default=None, help="覆盖仓库根（默认＝本 checkout）")
    args = ap.parse_args(argv)

    repo_root = Path(args.repo_root).resolve() if args.repo_root else REPO_ROOT
    violations, warnings, parsed_all = lint(
        repo_root, root_only=args.root_only,
        count_cap=args.count_cap, length_cap=args.length_cap,
    )

    if args.stats:
        for parsed in parsed_all:
            if not parsed.structure:
                continue
            lengths = [len(e.body) for e in parsed.entries]
            avg = sum(lengths) // len(lengths) if lengths else 0
            print(f"· {parsed.rel_path}｜结构 {parsed.structure}｜条目 {len(lengths)} 条"
                  f"｜均值 {avg}｜最大 {max(lengths) if lengths else 0}")
            for entry in parsed.entries:
                print(f"    #{entry.index} 行{entry.line_no} {len(entry.body)} 字符"
                      f"｜{entry.preview}…")
            for line_no, preview in parsed.meta_lines:
                print(f"    （元说明行，不计入）行{line_no}｜{preview}…")

    for w in warnings:
        print(f"⚠ {w}")

    # 二期工作量基线（派单件 §六硬要求：一期上线后必须给出这两个数）。
    over_count = [p for p in parsed_all if p.structure and len(p.entries) > args.count_cap]
    over_length = [(p, e) for p in parsed_all if p.structure
                   for e in p.entries if len(e.body) > args.length_cap]
    unsupported = [p for p in parsed_all if not p.structure]
    print(
        f"📊 二期基线：{len(over_count)} 个文件违反 J2（超 {args.count_cap} 条，"
        f"合计需迁出 {sum(len(p.entries) - args.count_cap for p in over_count)} 条）；"
        f"{len(over_length)} 条违反 J3（超 {args.length_cap} 字符）；"
        f"{len(unsupported)} 个文件结构未支持、未判定。"
    )

    if not violations:
        print(f"✓ CLAUDE.md 进度段 lint 通过（J2 上限 {args.count_cap} 条／"
              f"J3 上限 {args.length_cap} 字符）。")
        return 0

    mode = "阻断" if args.enforce else "告警（一期，不阻断）"
    print(f"✗ CLAUDE.md 进度段 lint 发现 {len(violations)} 处违规【{mode}】：")
    for v in violations:
        print(f"  - {v}")
    print("\n  判据正本见 1-转型规划/0-全景路线图/"
          "memory与上下文预算治理-审核与方案-2026-08-21.md §六。")
    return 1 if args.enforce else 0


if __name__ == "__main__":
    sys.exit(main())
