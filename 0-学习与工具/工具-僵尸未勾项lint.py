"""僵尸未勾项 lint（openspec 包 `tasks-zombie-item-detect` ／ 队列 §一 `#561` ／ `OP-0912-AA`）。

## 这道闸守什么

`openspec/changes/*/tasks.md` 里的未勾项，**做完了没人回来勾**。实例＝`fi2-recon-mvp` 的 `1.5`：
唐燕萍 2026-07-10 就交了东西，那一项挂着 `[ ]` 45 天，而依赖它的 `7.1`／`7.2` 早在 07-23 就被勾上了
——**不是没有信号，是没有人在听**。一个僵尸未勾项不会安静地待着，它会自己长出对外动作
（`财务部#13` 一次错误催办、一次错误的观察窗口声明；全部证据在该包 `proposal.md`）。

🔑 **本脚本只做检出、不做收口**——检出之后仍要人去核、去勾。它判的是 `tasks.md` 的**内部一致性**，
判不了「外部世界已经发生了什么」（design §已知边界 3）。

## 四条判据（定义与档位＝design §判据实测 ＋ 决策点 2／3／4，本文件不改写一字）

| 判据 | 内容 | 档位 |
|---|---|---|
| **J-A 前置矛盾** | 某项已 `[x]`，而它（或它所在节标题）声明的「前置 N.M」项仍 `[ ]` | **强**：违规，`--enforce` 下退出码 1 |
| **J-B 节内乱序** | 同节内序号靠后的项已 `[x]`，靠前的项仍 `[ ]` | **弱**：只出「请复核」清单，**永不**影响退出码 |
| **J-C 前置项无下游引用** | 「前置登记」项在本文件内无任何「前置 N.M」引用它 | **强**：违规，`--enforce` 下退出码 1 |
| **J-D 基线回显** | 每个包的未勾项数 ＋ 各项末次被 git 触碰日期 | 非判据：纯回显，供人工复核 |

🔴 **为什么 J-B 只能是弱判据，且措辞 MUST 是「请复核」、MUST NOT 是「疑似已完成」**（决策点 2 ＋ 已知边界 2）：
J-B 实测精度 4/5，唯一那条误报正是 `fi2` 的 `10.11b`——那一项是真未决（design D14 的 Open Question，
正在等唐燕萍团队批改）。若判违规，最省事的过关方式是把它勾掉；**误勾比漏勾更危险**——漏勾只会催错人一次，
误勾会让一条真开放口径从此消失。措辞本身就是防误勾的一道设计。

🔴 **为什么要有 J-C**（决策点 4，Shao Peishen 2026-09-12 拍 (a)）：J-A 的全部效力建立在「有人写了『前置 N.M』
这句话」之上——不写，J-A 对该项**结构性失效，且失效不产生任何信号**（判据恒真那一族）。J-C 就是 J-A 的自检：
写「前置登记」项时必须同时在某个下游项或节标题写下 `前置 N.M`。这是本包唯一给他人增加书写负担的判据，
一句话的负担，换 J-A 从此有自检。
R2 配套：脚本每次打印「本次扫描共发现 N 个前置声明」——**N 掉到 0 本身就是一个该被看见的信号**。

## 解析规则（实现取法，写在这里免得下一个读者以为是判据）

- **条目**＝`- [ ] N.M …`／`- [x] N.M …`（编号允许 `10.11b`／`0a.1`／`2.4.1`／`3.x` 这类真实形态；允许加粗）。
  不带编号的勾选框（如 `- [ ] a. …`）不参与 J-A／J-B／J-C，只计入 J-D 的未勾数。
- **节**＝任一 Markdown 标题行；J-B 的「同节」取最近一级标题。节标题里的「前置 N.M」对该标题之下、
  同级或更高级的下一个标题之前的全部条目生效（用标题栈实现，`###` 子节继承 `##` 父节的前置声明）。
- **前置引用**＝`前置 N.M`，🔴 **必须支持多值**：`前置 1.5/1.6`（斜杠）、`前置 0.1/0.4`（斜杠）、
  `前置 2.3、0.3`（顿号）、以及 `,`／`，`（spec 明列）。不支持多值 ⇒ `fi2` 1.6 与 `status-triage` 0.3
  上线即报 2 条假违规（决策点 4 (a) 的实现义务，2026-09-12 现取）。
- **被引用项号在本文件不存在** ⇒ 可见提示并跳过，**不判违规、不静默**（spec 第二条 Requirement）。
- **「前置登记」项**（J-C 的对象）＝条目正文**以**「前置登记」**起头**（允许加粗、后接 `：`／`:`），
  不是「正文任何位置提到这四个字」——否则本包自己 `tasks-zombie-item-detect/tasks.md` 的 1.2／1.7
  （在反引号／书名号里引用这个概念）会被当成两条前置登记项。design 2026-09-12 现取的「6 项」
  （`fi1` 1.6、`fi2` 1.5／1.6、`status-triage` 0.1／0.2／0.3）正是按「起头」数出来的。
- **扫描面**＝`openspec/changes/<包>/tasks.md`，🔴 **排除 `openspec/changes/archive/` 目录本身**——
  但**不排除名字里含 "archive" 的活跃包**（`audit-retention-archive`／`opener-batch-archive-precheck`
  是活跃包；design 用 `grep -v archive` 数出的 75 个就是把它们误滤掉了）。
- **纯只读**：零写盘，输出只经 stdout；J-D 的日期靠 `git blame --line-porcelain`（只读），
  git 不可用或非仓库时日期显示 `?`，不报错。

## 档位实现（决策点 3：分判据分档，在脚本内实现，CI job 不需要 `continue-on-error`）

退出码只看 J-A ＋ J-C：`--enforce` 且二者有命中 ⇒ 1；否则 0。J-B／J-D 无论命中多少条都不进退出码。

## 用法

    python 0-学习与工具/工具-僵尸未勾项lint.py              # 告警模式（退出码恒 0）
    python 0-学习与工具/工具-僵尸未勾项lint.py --enforce    # 阻断模式（J-A／J-C 有命中即 1）
    python 0-学习与工具/工具-僵尸未勾项lint.py --jd-summary # J-D 只出每包一行，不逐项列日期
    python 0-学习与工具/工具-僵尸未勾项lint.py --no-git     # 不取 git 触碰日期（单测／无 git 环境）
"""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHANGES_REL = "openspec/changes"
ARCHIVE_DIRNAME = "archive"

# `- [ ] 1.5 …`／`- [x] **0.1** …`／`- [x] 10.11b …`／`- [x] 2.4.1 …`／`- [x] 3.x …`
_ID = r"[0-9]+[a-z]?(?:\.(?:[0-9]+[a-z]?|x))+"
ITEM_RE = re.compile(r"^(\s*)- \[([ xX])\]\s*(?:\*\*)?(" + _ID + r")(?:\*\*)?(?:[:：.])?(?=\s|$)(.*)$")
ANY_CHECKBOX_RE = re.compile(r"^\s*- \[([ xX])\]")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")

# 「前置 N.M」引用，多值分隔＝`/`、`、`、`,`、`，`（spec 明列四种）
_REF_ID = r"[0-9]+[a-z]?\.[0-9]+[a-z]?"
PREREQ_RE = re.compile(r"前置\s*(" + _REF_ID + r"(?:\s*[/、,，]\s*" + _REF_ID + r")*)")
PREREQ_SPLIT_RE = re.compile(r"\s*[/、,，]\s*")
# 「前置登记」项：正文以「前置登记」起头（允许 **加粗**），后接冒号或空白
PREREQ_DECL_RE = re.compile(r"^(?:\*\*)?前置登记(?:\*\*)?\s*(?:[:：]|\s|$)")

JB_WORDING = "请复核"          # 已知边界 2：MUST 是「请复核」
JB_FORBIDDEN = "疑似已完成"     # MUST NOT 出现在 J-B 输出里（单测锁死）


@dataclass
class Section:
    level: int
    title: str
    line: int
    prereqs: list[str] = field(default_factory=list)     # 本标题自身声明的前置
    inherited: list[str] = field(default_factory=list)   # 含祖先标题声明的前置（已合并）


@dataclass
class Item:
    id: str
    checked: bool
    text: str
    line: int
    section: int                      # 所属节在 sections 里的下标；-1＝无标题之前
    body_prereqs: list[str] = field(default_factory=list)
    is_prereq_decl: bool = False      # J-C 对象


@dataclass
class FileReport:
    pkg: str
    rel_path: str
    items: list[Item] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    unchecked_total: int = 0          # J-D：含不带编号的勾选框
    prereq_refs: int = 0              # 「前置 N.M」引用处数（一处多值算一处）
    prereq_decls: int = 0             # 「前置登记」项数
    ja: list[str] = field(default_factory=list)
    jb: list[str] = field(default_factory=list)
    jc: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    jd_dates: dict[int, str] = field(default_factory=dict)   # 行号 → YYYY-MM-DD 或 "?"


@dataclass
class Report:
    scanned_packages: int = 0
    files: list[FileReport] = field(default_factory=list)

    @property
    def ja(self) -> list[str]:
        return [x for f in self.files for x in f.ja]

    @property
    def jb(self) -> list[str]:
        return [x for f in self.files for x in f.jb]

    @property
    def jc(self) -> list[str]:
        return [x for f in self.files for x in f.jc]

    @property
    def unresolved(self) -> list[str]:
        return [x for f in self.files for x in f.unresolved]

    @property
    def prereq_refs(self) -> int:
        return sum(f.prereq_refs for f in self.files)

    @property
    def prereq_decls(self) -> int:
        return sum(f.prereq_decls for f in self.files)

    @property
    def violations(self) -> list[str]:
        return self.ja + self.jc


# ---------------------------------------------------------------- 解析

def parse_prereq_refs(text: str) -> tuple[list[str], int]:
    """返回 (引用到的项号列表, 引用处数)。`前置 1.5/1.6` ＝ 一处、两个项号。"""
    ids: list[str] = []
    n = 0
    for m in PREREQ_RE.finditer(text):
        n += 1
        ids.extend(PREREQ_SPLIT_RE.split(m.group(1).strip()))
    return ids, n


def parse_tasks(text: str, pkg: str, rel_path: str) -> FileReport:
    rep = FileReport(pkg=pkg, rel_path=rel_path)
    stack: list[Section] = []          # 标题栈（按 level 单调）
    in_fence = False
    for lineno, raw in enumerate(text.splitlines(), 1):
        if FENCE_RE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        h = HEADING_RE.match(raw)
        if h:
            level, title = len(h.group(1)), h.group(2)
            while stack and stack[-1].level >= level:
                stack.pop()
            own, n = parse_prereq_refs(title)
            rep.prereq_refs += n
            inherited = list(stack[-1].inherited) if stack else []
            for p in own:
                if p not in inherited:
                    inherited.append(p)
            sec = Section(level=level, title=title, line=lineno, prereqs=own, inherited=inherited)
            stack.append(sec)
            rep.sections.append(sec)
            continue
        cb = ANY_CHECKBOX_RE.match(raw)
        if not cb:
            continue
        if cb.group(1) == " ":
            rep.unchecked_total += 1
        m = ITEM_RE.match(raw)
        if not m:
            continue                   # 不带编号的勾选框：只计未勾数，不参与判据
        _indent, mark, item_id, body = m.groups()
        body = body.strip()
        refs, n = parse_prereq_refs(body)
        rep.prereq_refs += n
        is_decl = bool(PREREQ_DECL_RE.match(body))
        if is_decl:
            rep.prereq_decls += 1
        rep.items.append(Item(
            id=item_id, checked=(mark != " "), text=body, line=lineno,
            section=(len(rep.sections) - 1) if rep.sections else -1,
            body_prereqs=refs, is_prereq_decl=is_decl,
        ))
    return rep


# ---------------------------------------------------------------- 判据

def _short(text: str, n: int = 40) -> str:
    text = re.sub(r"\s+", " ", text)
    return text if len(text) <= n else text[: n - 1] + "…"


def judge(rep: FileReport) -> None:
    by_id: dict[str, Item] = {}
    for it in rep.items:
        by_id.setdefault(it.id, it)      # 同号重复时取首个（极少见，不在此处判）

    # ---- J-A 前置矛盾（强）：已 [x] 的项，其（正文或节标题声明的）前置项仍 [ ]
    # ---- 同时收集「引用了不存在的项号」→ 可见提示、跳过、不判违规
    seen_unresolved: set[tuple[str, str]] = set()
    for it in rep.items:
        sources: list[tuple[str, str]] = [(p, f"L{it.line} 正文") for p in it.body_prereqs]
        if it.section >= 0:
            sec = rep.sections[it.section]
            sources += [(p, f"§标题 L{sec.line}「{_short(sec.title)}」") for p in sec.inherited]
        for p, src in sources:
            target = by_id.get(p)
            if target is None:
                key = (p, src)
                if key not in seen_unresolved:
                    seen_unresolved.add(key)
                    rep.unresolved.append(
                        f"{rep.pkg}: {src} 引用「前置 {p}」，但本文件不存在 {p}（已跳过，不判违规）")
                continue
            if it.checked and not target.checked:
                rep.ja.append(
                    f"{rep.pkg}: {it.id} → {p}（{it.id} 已 [x]，其前置 {p} 仍 [ ]；声明来源：{src}）")

    # ---- J-B 节内乱序（弱）：同节内靠后的项已 [x]，靠前的项仍 [ ] → 只出「请复核」清单
    # 已知边界 1：「节内最后一项 ＋ 无前置声明」这一形态本判据够不着（fi2 的 10.13），不假装覆盖。
    by_section: dict[int, list[Item]] = {}
    for it in rep.items:
        by_section.setdefault(it.section, []).append(it)
    for _sec_idx, items in by_section.items():
        last_checked_line = max((i.line for i in items if i.checked), default=-1)
        for it in items:
            if not it.checked and it.line < last_checked_line:
                later = next(i for i in items if i.checked and i.line > it.line)
                rep.jb.append(
                    f"{rep.pkg}: {it.id} 仍 [ ]，而同节靠后的 {later.id} 已 [x] —— {JB_WORDING}"
                    f"（L{it.line}「{_short(it.text)}」）")

    # ---- J-C 前置项无下游引用（强）：「前置登记」项在本文件内无任何「前置 N.M」引用它
    # 理由（spec 要求写在实现注释内）：J-A 的全部效力建立在「有人写了前置引用」之上；不写即 J-A 对该项
    # 结构性失效，且失效不产生任何信号。J-C 让这个失效变成一条可见的 CI 红。
    referenced: set[str] = set()
    for sec in rep.sections:
        referenced.update(sec.prereqs)
    for it in rep.items:
        referenced.update(it.body_prereqs)
    for it in rep.items:
        if it.is_prereq_decl and it.id not in referenced:
            rep.jc.append(
                f"{rep.pkg}: {it.id} 是「前置登记」项，但本文件无任何「前置 {it.id}」引用它"
                f"（L{it.line}）。出路：在依赖它的下游项正文或所在节标题补一句「前置 {it.id}」——"
                f"否则 J-A 对它结构性失效且无信号")


# ---------------------------------------------------------------- J-D：git 触碰日期（只读）

def git_line_dates(root: Path, rel_path: str) -> dict[int, str]:
    """`git blame --line-porcelain` 取每行的 committer 日期；任何失败都返回空 dict（显示为 `?`）。"""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "blame", "--line-porcelain", "--", rel_path],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if out.returncode != 0:
        return {}
    dates: dict[int, str] = {}
    cur_line = None
    cur_time = None
    for line in out.stdout.splitlines():
        m = re.match(r"^[0-9a-f]{40} \d+ (\d+)", line)
        if m:
            cur_line = int(m.group(1))
            cur_time = None
            continue
        if line.startswith("committer-time ") and cur_line is not None:
            cur_time = int(line.split()[1])
            dates[cur_line] = _dt.datetime.fromtimestamp(cur_time, _dt.timezone.utc).strftime("%Y-%m-%d")
    return dates


# ---------------------------------------------------------------- 扫描

def iter_task_files(root: Path):
    changes = root / CHANGES_REL
    if not changes.is_dir():
        return
    for pkg_dir in sorted(changes.iterdir()):
        if not pkg_dir.is_dir() or pkg_dir.name == ARCHIVE_DIRNAME:
            continue
        tasks = pkg_dir / "tasks.md"
        if tasks.is_file():
            yield pkg_dir.name, tasks


def scan(root: Path = REPO_ROOT, git_dates: bool = True) -> Report:
    rep = Report()
    for pkg, tasks in iter_task_files(root):
        rep.scanned_packages += 1
        rel = tasks.relative_to(root).as_posix()
        fr = parse_tasks(tasks.read_text(encoding="utf-8"), pkg, rel)
        judge(fr)
        if git_dates and fr.unchecked_total:
            dates = git_line_dates(root, rel)
            for it in fr.items:
                if not it.checked:
                    fr.jd_dates[it.line] = dates.get(it.line, "?")
        rep.files.append(fr)
    return rep


# ---------------------------------------------------------------- 输出

def render(rep: Report, jd_summary: bool = False, git_dates: bool = True) -> list[str]:
    out: list[str] = []
    out.append(f"僵尸未勾项 lint：扫描 {rep.scanned_packages} 个活跃变更包的 tasks.md"
               f"（不含 {CHANGES_REL}/{ARCHIVE_DIRNAME}/）")
    # R2 自检：N 掉到 0 本身就是一个该被看见的信号
    flag = "  🔴 N=0 ⇒ J-A 已整体失效（没有任何前置引用可判），须回头看书写约定是否变了" \
        if rep.prereq_refs == 0 else ""
    out.append(f"  本次扫描共发现 {rep.prereq_refs} 个前置声明"
               f"（「前置 N.M」引用 {rep.prereq_refs} 处；「前置登记」项 {rep.prereq_decls} 个）{flag}")

    if rep.unresolved:
        out.append(f"  ? 引用了本文件不存在的项号 {len(rep.unresolved)}（可见提示，已跳过、不判违规）：")
        out += [f"      - {x}" for x in rep.unresolved]

    # J-D 基线回显（非判据）
    files_with_unchecked = [f for f in rep.files if f.unchecked_total]
    total_unchecked = sum(f.unchecked_total for f in rep.files)
    out.append(f"\n  · J-D 基线回显（非判据，不定性）：{len(files_with_unchecked)} 个包共 {total_unchecked} 个未勾项"
               + ("" if git_dates else "；--no-git，未取触碰日期"))
    for f in files_with_unchecked:
        dated = [(it, f.jd_dates.get(it.line, "?")) for it in f.items if not it.checked]
        known = sorted(d for _, d in dated if d != "?")
        span = f"，末次触碰 {known[0]} ～ {known[-1]}" if known else ""
        out.append(f"      - {f.pkg}：未勾 {f.unchecked_total} 项（带编号 {len(dated)}）{span}")
        if not jd_summary:
            for it, d in dated:
                out.append(f"          {d}  {it.id}  {_short(it.text, 60)}")

    # J-B（弱）：只出清单
    if rep.jb:
        out.append(f"\n  ○ J-B 节内乱序 {len(rep.jb)} 条 —— {JB_WORDING}清单（弱判据，不影响退出码；"
                   f"精度实测 4/5，其中可能有真未决项，请逐条核、不要据此勾除）：")
        out += [f"      - {x}" for x in rep.jb]

    # J-A／J-C（强）
    if rep.violations:
        out.append(f"\n  ✗ 违规 {len(rep.violations)}（J-A {len(rep.ja)} ／ J-C {len(rep.jc)}）：")
        out += [f"      - [J-A] {x}" for x in rep.ja]
        out += [f"      - [J-C] {x}" for x in rep.jc]
    else:
        out.append("\n  ✓ J-A／J-C 无违规。")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="openspec tasks.md 僵尸未勾项 lint（J-A／J-B／J-C／J-D）")
    ap.add_argument("--enforce", action="store_true",
                    help="J-A／J-C 有命中即以退出码 1 阻断（默认只告警、退出码 0）；J-B／J-D 永不影响退出码")
    ap.add_argument("--root", default=str(REPO_ROOT), help="仓库根（默认＝本脚本上一级）")
    ap.add_argument("--no-git", action="store_true", help="不取 git 触碰日期（J-D 日期显示 ?）")
    ap.add_argument("--jd-summary", action="store_true", help="J-D 只出每包一行，不逐项列日期")
    args = ap.parse_args(argv)

    rep = scan(Path(args.root), git_dates=not args.no_git)
    for line in render(rep, jd_summary=args.jd_summary, git_dates=not args.no_git):
        print(line)

    if rep.violations:
        if args.enforce:
            return 1
        print("\n  （告警模式，退出码 0；加 --enforce 阻断）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
