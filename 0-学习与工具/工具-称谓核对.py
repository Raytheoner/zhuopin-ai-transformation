"""称谓核对——跟进信**发件侧**的第三人称代词守卫（队列 §一 `#566`，2026-09-12）。

## 它守的是哪一侧

`工具-共享文档编辑锁.py::_gender_pronoun_violations` 守的是**队列三分区的表格行**，
`工具-跟进信README登记.py` 守的是**README 台账的收信人格**——两处都是内部记录。
**真正寄出去的那份**（`6-人才与组织/部门AI专员跟进/` 下的 `.md` 起草稿与 `.docx`
成品）此前不在任何一条校验路径上，而已发生的那次不可撤回事故（`财务部#14`，
名录正本 §二 第 6 个易错名写「他」、信发出撤不回，CHANGELOG 附录 F）恰恰出在正文。
🔑 判据一句：**守在内部记录上、没守在寄出去的那份上；被守住的是不会伤人的那一侧。**

## 复用而非重造（`#566` 期望产出 ①）

- 名录：`editlock.PERSON_GENDER_ROSTER`（常量正本仍是
  `6-人才与组织/人员名录-称谓与性别-正本.md` ＋ 编辑锁侧既有同步单测，
  **本文件零硬编码人名与性别**——写出来就等于造出第二份名录）。
- 判据：`editlock.gender_pronoun_findings`（邻近窗口 25 字、异性名字隔断、
  `其他／他们` 遮蔽、行内豁免）——**逐字同一份**，本文件只做取材（md 逐行／
  docx 逐段）与回显措辞。
- 别名：`editlock.gender_roster_aliases(include_short_names=True)`——信里常写
  短名（正本 §二 那 7 个易错名），从名录派生、不另列。

## 判据边界（如实声明）

- 只判**名录在册人物**之后的代词；名录外人物（客户／OEM 对接人／新同事）本
  工具看不见——那一类按正本硬规则一律用「该专员／其／对方」并当场问一次。
- 名录标「未确认」者：「他」「她」都算命中，应用词＝中性表述，**不二选一猜**。
- `.md`：逐行判；代码围栏内不判（那是原样引用的命令／旧文，不是信的话）。
  块引用**照判**——信里 `>` 段落照样会被寄出去。
- `.docx`：读 `word/document.xml` **全文**，按 `<w:p>` 段落拼接 `<w:t>` 文本
  （含表格单元格、页眉页脚不含——正文才是寄出去的话），行号＝段序号。
- 行内豁免：`性别豁免：<理由>`（与队列行守卫同一标记）；`sentinel-pronoun.ps1`
  用的 `代词豁免：<理由>` 同样认——同一行不该为两道守卫写两遍。
  🔴 **只写标记不跟理由不生效**，并单独列为一处命中。

## `--all` 与历史白名单（`#566` 🔴 历史不追改）

已发出的信一个字不改。`--all` 全目录扫描时跳过
`0-学习与工具/称谓核对-历史白名单.txt` 里列出的文件（建档日按当日实扫取证，
每行 `<仓库根相对路径>\t<理由>`），回显里明写跳过了几个。**新信不得往白名单里
加**——白名单只收建档日之前已寄出的件；新信命中就改信。

## 用法

    python 0-学习与工具/工具-称谓核对.py <信件.md> [<信件.docx> …]   # 指定文件
    python 0-学习与工具/工具-称谓核对.py --dirty                      # 工作区脏的跟进信件（release 用的同一口径）
    python 0-学习与工具/工具-称谓核对.py --all                        # 全目录（白名单跳过历史件）
    加 `--json` 出机器面。

退出码：0 ＝ 核对完成且命中 0 处；1 ＝ 有命中（逐处列出行号／原句／应用词）；
2 ＝ 核对**无法执行**（名录取数异常／文件读不到／docx 解析失败）——🔴 无法执行
与「没有问题」是两回事，2 一律不得被当成 0。
🔴 无论结果如何都打印「已核对 N 个文件…命中 M 处」一行：连回显都没有时，
无法区分「没问题」与「没跑」（队列 #284 第 18 次违反的教训）。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import zipfile
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
_EDIT_LOCK_SCRIPT = _TOOLS_DIR / "工具-共享文档编辑锁.py"
# 编辑锁 release 挂载点会先把自己注册到这个名字下再加载本模块，免得 7000 行的
# 编辑锁被 exec 第二遍；独立运行时这里自己加载一份。
_EDITLOCK_MODULE_NAME = "_gender_lint_editlock_reuse"


def _load_editlock():
    existing = sys.modules.get(_EDITLOCK_MODULE_NAME)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(_EDITLOCK_MODULE_NAME, _EDIT_LOCK_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载名录与判据正本：{_EDIT_LOCK_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass 在 Python 3.14 下需要能在 sys.modules 解析到所属模块
    spec.loader.exec_module(module)
    return module


editlock = _load_editlock()

# 🔴 本工具的默认根＝**本脚本所在的 checkout**（worktree 里跑就扫该 worktree），
# 刻意不用 `editlock.REPO_ROOT`——那个按 `--git-common-dir` 解到**主工作区**（编辑锁
# 要所有 worktree 共用一把锁才那样定），拿它来扫信件会把泳道里刚起草的稿子漏掉、
# 而回显看起来完全正常。编辑锁 release 挂载点自己传 `repo_root=`。
WORK_ROOT: Path = _TOOLS_DIR.parent
# 「寄出去的信」的判别正本在编辑锁侧（`is_followup_letter_path`）：release 挂载点
# 要先用它决定要不要加载本模块，故判据只能在那边、这边复用。
LETTER_DIR_REL = editlock.FOLLOWUP_LETTER_DIR
LETTER_SUFFIXES = editlock.FOLLOWUP_LETTER_SUFFIXES
is_letter_path = editlock.is_followup_letter_path
WHITELIST_REL = "0-学习与工具/称谓核对-历史白名单.txt"
WAIVER_MARKERS = (editlock.GENDER_PRONOUN_WAIVER_MARKER, "代词豁免：")
# 名录规模下限——与 `工具-跟进信README登记.py::_ROSTER_FLOOR` 同一取值、同一理由：
# 名录突然只剩几个人，几乎必然是取数路径坏了，此时照常判定会「非常自信地判
# 每一处都没问题」。
_ROSTER_FLOOR = 15

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_DOCX_PARA_RE = re.compile(r"<w:p[ >].*?</w:p>", re.S)
_DOCX_TEXT_RE = re.compile(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", re.S)
_XML_UNESCAPE = (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&apos;", "'"), ("&amp;", "&"))


class GenderLintError(RuntimeError):
    """核对**无法执行**（退出码 2）。"""


def _roster_checked() -> dict[str, str]:
    roster = editlock.PERSON_GENDER_ROSTER
    if len(roster) < _ROSTER_FLOOR:
        raise GenderLintError(
            f"人员名录取数异常：只读到 {len(roster)} 个姓名（下限 {_ROSTER_FLOOR}）——"
            "拒绝在此基础上核对。请先查 `工具-共享文档编辑锁.py::PERSON_GENDER_ROSTER` "
            "是否被改坏。"
        )
    return roster


def _aliases() -> dict[str, str]:
    return editlock.gender_roster_aliases(_roster_checked(), include_short_names=True)


# ---------------------------------------------------------------------------
# 取材：md 逐行、docx 逐段
# ---------------------------------------------------------------------------
def md_units(text: str) -> list[tuple[int, str]]:
    """`(行号, 原句)`；代码围栏内的行不出。"""
    units: list[tuple[int, str]] = []
    in_fence = False
    for no, line in enumerate(text.split("\n"), 1):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or not line.strip():
            continue
        units.append((no, line))
    return units


def _xml_unescape(s: str) -> str:
    for src, dst in _XML_UNESCAPE:
        s = s.replace(src, dst)
    return s


def docx_units(path: Path) -> list[tuple[int, str]]:
    """`(段序号, 段落全文)`，取自 `word/document.xml` 全文（不只解析表头）。"""
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8")
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError) as exc:
        raise GenderLintError(f"docx 解析失败：{path}（{exc}）") from exc
    units: list[tuple[int, str]] = []
    for no, para in enumerate(_DOCX_PARA_RE.findall(xml), 1):
        text = _xml_unescape("".join(_DOCX_TEXT_RE.findall(para)))
        if text.strip():
            units.append((no, text))
    return units


def units_for(path: Path) -> list[tuple[int, str]]:
    if path.suffix.lower() == ".docx":
        return docx_units(path)
    try:
        return md_units(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise GenderLintError(f"文件读不到：{path}（{exc}）") from exc


# ---------------------------------------------------------------------------
# 判定
# ---------------------------------------------------------------------------
def _waiver_without_reason(text: str) -> str | None:
    """写了豁免标记却没跟理由 ⇒ 返回该标记；否则 `None`。"""
    for marker in WAIVER_MARKERS:
        idx = text.find(marker)
        if idx == -1:
            continue
        reason = text[idx + len(marker):].strip().strip("）)」』】")
        if len(reason) < 2:
            return marker
    return None


def scan_units(units: list[tuple[int, str]], *, aliases: dict[str, str] | None = None,
               roster: dict[str, str] | None = None) -> list[dict]:
    """对一组 `(行号, 文本)` 逐处列出命中（机器面字典，供人读与 `--json` 共用）。"""
    roster = _roster_checked() if roster is None else roster
    aliases = editlock.gender_roster_aliases(roster, include_short_names=True) if aliases is None else aliases
    hits: list[dict] = []
    for no, text in units:
        bare_marker = _waiver_without_reason(text)
        if bare_marker is not None:
            hits.append({
                "line": no, "kind": "waiver-without-reason", "name": "", "gender": "",
                "written": bare_marker, "expected": f"{bare_marker}<理由>",
                "sentence": text.strip(),
            })
            continue
        for f in editlock.gender_pronoun_findings(
            text, roster=roster, aliases=aliases, waiver_markers=WAIVER_MARKERS,
        ):
            hits.append({
                "line": no, "kind": "pronoun", "name": f.name, "alias": f.alias,
                "gender": f.gender, "written": f.written, "expected": f.expected,
                "sentence": text.strip(),
            })
    return hits


def scan_files(paths: list[Path], *, repo_root: Path | None = None) -> list[dict]:
    """逐文件核对；返回 `{path, line, …}` 列表。任一文件无法执行即抛 `GenderLintError`。"""
    repo_root = WORK_ROOT if repo_root is None else repo_root
    aliases = _aliases()
    roster = editlock.PERSON_GENDER_ROSTER
    results: list[dict] = []
    for path in paths:
        rel = _rel(path, repo_root)
        for hit in scan_units(units_for(path), aliases=aliases, roster=roster):
            results.append({"path": rel, **hit})
    return results


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


# ---------------------------------------------------------------------------
# 目标集合：指定／--dirty／--all
# ---------------------------------------------------------------------------
def dirty_letter_paths(repo_root: Path | None = None) -> list[str] | None:
    """工作区脏的信件（复用编辑锁那份 `git status` 取数）；取数失败返回 `None`。"""
    repo_root = WORK_ROOT if repo_root is None else repo_root
    dirty = editlock._local_git_status_paths(repo_root)
    if dirty is None:
        return None
    return sorted(
        p for p in dirty if is_letter_path(p) and (repo_root / p).is_file()
    )


def load_whitelist(repo_root: Path | None = None) -> dict[str, str]:
    repo_root = WORK_ROOT if repo_root is None else repo_root
    path = repo_root / WHITELIST_REL
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        rel, _, reason = line.partition("\t")
        out[rel.strip().replace("\\", "/")] = reason.strip()
    return out


def all_letter_paths(repo_root: Path | None = None) -> tuple[list[str], list[str]]:
    """`(要扫的, 被白名单跳过的)`。"""
    repo_root = WORK_ROOT if repo_root is None else repo_root
    whitelist = load_whitelist(repo_root)
    letters = sorted(
        _rel(p, repo_root) for p in (repo_root / LETTER_DIR_REL).iterdir()
        if p.is_file() and is_letter_path(_rel(p, repo_root))
    )
    skipped = [p for p in letters if p in whitelist]
    return [p for p in letters if p not in whitelist], skipped


# ---------------------------------------------------------------------------
# 回显
# ---------------------------------------------------------------------------
def format_hit(hit: dict) -> str:
    if hit["kind"] == "waiver-without-reason":
        return (f"{hit['path']}:{hit['line']}: 写了「{hit['written']}」却没跟理由——"
                f"只写标记不生效，应写「{hit['expected']}」｜原句：{hit['sentence']}")
    return (f"{hit['path']}:{hit['line']}: 「{hit['alias']}」（名录记「{hit['gender']}」）"
            f"之后写了「{hit['written']}」，应用「{hit['expected']}」｜原句：{hit['sentence']}")


def summary_line(n_files: int, n_md: int, n_docx: int, n_hits: int, n_skipped: int = 0) -> str:
    skipped = f"，白名单跳过历史件 {n_skipped} 个" if n_skipped else ""
    return (f"ℹ 称谓核对：已核对 {n_files} 个文件（md {n_md}／docx {n_docx}），"
            f"命中 {n_hits} 处{skipped}。")


def run(paths: list[str], *, as_json: bool = False, repo_root: Path | None = None,
        skipped: list[str] | None = None) -> int:
    repo_root = WORK_ROOT if repo_root is None else repo_root
    skipped = skipped or []
    abs_paths = [repo_root / p if not Path(p).is_absolute() else Path(p) for p in paths]
    for p in abs_paths:
        if not p.is_file():
            print(f"✗ 文件不存在：{p}", file=sys.stderr)
            return 2
        if p.suffix.lower() not in LETTER_SUFFIXES:
            print(f"✗ 只核对 .md／.docx：{p}", file=sys.stderr)
            return 2
    try:
        hits = scan_files(abs_paths, repo_root=repo_root)
    except GenderLintError as exc:
        print(f"✗ 称谓核对无法执行：{exc}", file=sys.stderr)
        return 2
    n_md = sum(1 for p in abs_paths if p.suffix.lower() == ".md")
    n_docx = len(abs_paths) - n_md
    if as_json:
        print(json.dumps({
            "files": [_rel(p, repo_root) for p in abs_paths],
            "skipped": skipped, "hits": hits,
        }, ensure_ascii=False, indent=1))
    else:
        for hit in hits:
            print("✗ " + format_hit(hit))
        print(summary_line(len(abs_paths), n_md, n_docx, len(hits), len(skipped)))
        if hits:
            print("   处置：① 按名录改正（名录标「未确认」者改中性表述，不得二选一猜）；"
                  "② 确属合法（引用旧信原文／词例引用）在该行写 "
                  f"「{editlock.GENDER_PRONOUN_WAIVER_MARKER}<理由>」。🔴 历史件不追改。")
    return 1 if hits else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", help="要核对的信件（.md／.docx，仓库根相对或绝对路径）")
    parser.add_argument("--dirty", action="store_true",
                        help=f"核对工作区脏的 `{LETTER_DIR_REL}/` 信件（编辑锁 release 用的同一口径）")
    parser.add_argument("--all", action="store_true",
                        help=f"核对 `{LETTER_DIR_REL}/` 全部信件，跳过 `{WHITELIST_REL}` 里的历史件")
    parser.add_argument("--json", action="store_true", help="机器面输出")
    args = parser.parse_args(argv)

    modes = sum([bool(args.paths), args.dirty, args.all])
    if modes != 1:
        parser.error("指定文件、--dirty、--all 三选一，必传其一")

    skipped: list[str] = []
    if args.dirty:
        paths = dirty_letter_paths()
        if paths is None:
            print("✗ 无法取得工作区脏文件状态（非 git 仓库／git 不可用／超时）——"
                  "称谓核对无法执行。", file=sys.stderr)
            return 2
        if not paths:
            print(summary_line(0, 0, 0, 0) + "（工作区没有脏的信件）")
            return 0
    elif args.all:
        paths, skipped = all_letter_paths()
    else:
        paths = args.paths
    return run(paths, as_json=args.json, skipped=skipped)


if __name__ == "__main__":
    sys.exit(main())
