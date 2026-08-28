"""opener 代码块 lint —— 一次收两个失效形态（队列 §一 `#284`，OP-0828-Y）。

本脚本是**规则退休制**（根 `CLAUDE.md` §5）欠下的对价：`专线opener模板库.md` §〇
补充三那条人守规则 **2026-08-27 一天被违反 17 次**，远超「人守违反 3 次即须机制化或
删除」的阈值；补充三之三又在 2026-08-28 撞出第二个形态。退休制要求二选一——机制化，
或删除。**本脚本就是「机制化」那一半。**

## 两个形态（判据正本＝`1-转型规划/0-全景路线图/专线opener模板库.md` §〇 补充三／补充三之三）

| | 守什么 | 生效日 | 成因 |
|---|---|---|---|
| 形态① | **CC 侧** opener 块含 `【设置】` 而**无** `set_session_title` | 2026-08-26（补充一） | session 名丢编号，2026-08-27 一天欠 17 次 |
| 形态② | 块内**有** `set_session_title` 而**无**子任务例外句 | 2026-08-28（补充三之三） | Task/Agent 子任务执行它时 `"self"` 解析到**父** session，把调度它的那条会话改名；**调用成功、无报错** |

形态②与「工具静默回退」同族：它没错，只是解析到了另一个对象 —— 没有任何一层会报错，
故只能靠结构检测拦，靠人读输出拦不住。

## 🔴 形态①**只对 CC 侧成立**——这是与 `#284` 需求原文的一处刻意收窄（实测依据）

`#284` 与补充三的原话是「块内含 `【设置】` 而无 `set_session_title` ⇒ 告警」，未分执行环境。
**但补充一白纸黑字写着：`set_session_title` 这个工具在 Cowork 侧根本不存在**（本方 2026-08-27
在 Cowork 会话内实测查找，`mcp__ccd_session_mgmt__*` 一个都没有），且原文明写「**把 CC 的做法
抄给 Cowork 会写出一个不存在的工具调用**」；Cowork 侧的等价要求是「开场词首行自带编号」。
⇒ **若不收窄，本 lint 会对 108 个 Cowork 块中的 78 个报警，而按规则去修它们全都是错的**
——那正是「关不掉的告警等于噪音」，本项目已有先例。故：

- `执行环境：CC` ⇒ 判形态①；
- `执行环境：Cowork` ⇒ **结构性排除**（不是豁免清单，是判据本身不覆盖）；
- `执行环境` 缺失／两者都不是 ⇒ **不猜**，单列 `env-unknown` 桶，计数并打印，但不判违规。

形态②不分执行环境：Cowork 块若真写了那一行，例外句同样必要（那一行会被原样传给子任务）。

## opener 块的识别（结构锚，不用裸子串）

只看 **markdown 围栏代码块**（``` 或 ~~~，≥3 个同字符，缩进 ≤3 空格；闭合围栏须同字符、
长度 ≥ 开启且无 info string）。块内**有一行 strip 后以 `【设置】` 开头** ⇒ 判为 opener 块。

🔴 **必须是「行首」而不是「块内任意位置出现 `【设置】`」**：`memory索引收割对账-2026-08-21.md`
第 30 行那个 ```markdown 块里有一行散文「- [CC 开场词带【设置】行](...)」，裸子串判据会把它
点亮。同族＝`工具-引导样板lint.py` 判据二那条「讲解反范式的散文一律不命中」。

另有一类**裸 `set_session_title` 块**（无 `【设置】`，如模板库补充三之三的「标准写法」单行块）
——它只参与形态②，不参与形态①。

## 「当前在用件」vs「历史件」的区分判据（🔴 三层，任一命中即历史；**不靠目录名猜**）

- **H1 · 归档物理落点**：路径含 `z-已执行归档/` **目录段**。这是文档治理规范 R3 生命周期
  定义的归档目的地，不是从文件名推断的。
- **H2 · 状态头**：frontmatter `status` 归入 `{已执行归档, 已作废, 历史快照}`。判定**复用**
  `工具-文档台账生成.py::status_bucket()`（R1 机制守的六枚举 ＋ 同义词表），**不自造第二套**
  ——本项目已有「同一判据两处各自实现然后漂移」的成例。
- **H3 · 规则生效后是否还被编辑过**：`git log -1 --format=%cI -- <file>` 的**提交时刻**早于
  该形态所属规则的生效日 ⇒ 历史件。语义是「**规则生效后没有任何人再动过这份件**，追改它
  就是违反『历史记录不追改』」。
  🔴 **用 git 提交时刻，不用文件 mtime**（mtime 会被 checkout／同步／台账重跑刷新，而
  「这份件有没有被人再编辑过」问的是版本历史，不是磁盘时间戳）。
  🔴 **不用 `git blame -L`**：那是按行号定位，而块的行号随上方增删漂移，会静默给出另一段
  的历史（根 `CLAUDE.md` §5 已记过这一条）。

**当前在用件 ＝ 三条都不命中。**

⚠️ **H2 单独用不住，这是实测结论、如实登记**：`本周计划-2026-08-03.md` 的状态头至今写着
`在办`（R3 回填是季度批量做的，日期型件的状态头天然滞后），只有 H3 能把它判成历史件。
反过来 `专线opener模板库.md`（`status: 生效`、2026-08-28 仍在改）三条都不命中 ⇒ 当前在用，
而它里面第二/三/四节那三个 CC 模板确实缺 `set_session_title` —— **那正是 17 次违反的源头**，
本 lint 报出来是对的。**⇒ 三层缺一不可，任何单层都会漏判或误判。**

🔴 **git 历史取不到时（浅克隆、未跟踪文件）不静默回退**：该文件标 `history-unavailable`，
H3 判不了 ⇒ 按「当前在用」保守计入，并在报告里显式打印这一桶的数量与文件名。
（CI 里请配 `fetch-depth: 0`，否则整库都会落进这一桶——那不是「突然多了几十处违规」。）

## 两侧都能关掉（本脚本的验收判据，见单测）

- 写对的 opener 块（含 `【设置】` ＋ `set_session_title` ＋ 子任务例外句）**不报**；
- 把一个报警的块补上缺失的那一句之后，**该告警自动消失**（无豁免清单、无 baseline，
  判据本身是可满足的）。
  🔴 **刻意不设 baseline**：`队列结构lint` 的称呼判据用 baseline 冻结存量是对的（那些存量
  按「历史不追改」永远不该被修）；**本件不同——当前在用件里的命中是真该修的**，尤其模板库
  那三处。冻结它们等于把最该修的三处永久隐身。

## 退休了什么（协议〇.9 措施 B · one-in-one-out）

退休的是**人守规则**，不是既有守卫代码：`专线opener模板库.md` §〇 补充三「起草期自检：
每写完一个 opener 代码块，回头看它第 3 行」这条人守，及补充三之三的机制守待建项。
本脚本上线后该自检降为一行指针（正文按 #206 先例可保留，不必删）。
**本次不退休任何既有守卫代码**——理由：现有五个 `工具-*lint.py` 各守一个互不重叠的域
（`.py` 引导／`.py` 凭据锚定／队列表格／`CLAUDE.md` 进度段／凭据串），**没有一个覆盖
`.md` 里的 opener 代码块**，退掉任何一个都会开一个新口子。

## 用法

    python 0-学习与工具/工具-opener块lint.py             # 告警模式（退出码恒 0）
    python 0-学习与工具/工具-opener块lint.py --enforce    # 阻断模式（当前在用件有违规即 1）
    python 0-学习与工具/工具-opener块lint.py --show-historical   # 连历史件命中一起列明细

**`--enforce` 只对「当前在用件」阻断**；历史件恒不阻断（「历史记录不追改」）。
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# ── 两条规则各自的生效日（H3 的时间边界）──────────────────────────────────────
#: 形态① ＝ 模板库 §〇「补充一」第 2 条（Shao Peishen 2026-08-26 定）。
RULE_EFFECTIVE_FORM1 = date(2026, 8, 26)
#: 形态② ＝ 模板库 §〇「补充三之三」（2026-08-28 实撞后当日定）。
RULE_EFFECTIVE_FORM2 = date(2026, 8, 28)

#: R3 生命周期的归档物理落点（目录段，非文件名关键词）。
ARCHIVE_DIR_SEGMENT = "z-已执行归档"

#: H2：判定为历史件的状态桶（`工具-文档台账生成.py::STATUS_ORDER` 后三枚举）。
HISTORICAL_STATUS_BUCKETS = frozenset({"已执行归档", "已作废", "历史快照"})

# 🔴 **没有豁免清单，这是刻意的**：扫描面只有 `.md`，而本脚本与其单测都是 `.py`
# （两者文中都带两个形态的反例原文作夹具），天然不在扫描面内 —— 不需要靠豁免躲开。
# 豁免一多门禁就名存实亡（`工具-引导样板lint.py` 已记过这一条），能不设就不设。

FENCE_RE = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})\s*(?P<info>.*?)\s*$")
SETTINGS_LINE_RE = re.compile(r"^\s*(?:>\s*)?\*{0,2}【设置】")
SESSION_TITLE_RE = re.compile(r"set_session_title")
#: 执行环境字段（硬规则「执行环境标注」，`【设置】` 行标准四字段之一）。加粗星号先剥掉。
ENV_RE = re.compile(r"执行环境\s*[:：]\s*\**\s*(Cowork|CC)", re.IGNORECASE)

#: 子任务例外句：要求「子任务/Task/Agent」与「例外/跳过本行」同现于同一个块。
#: 🔴 只判「有没有」、判不了「对不对」——这类弱校验在本项目已被反复证明有效
#: （#225 列数校验／#258 release 校验两天内各拦下一次），它拦不住写错，但拦得住压根没写。
SUBTASK_TOKEN_RE = re.compile(r"子任务|Task/Agent|Task／Agent")
EXCEPTION_TOKEN_RE = re.compile(r"例外|跳过本行")

_LEDGER_SCRIPT = REPO_ROOT / "0-学习与工具" / "工具-文档台账生成.py"


def _load_status_bucket():
    """复用 `工具-文档台账生成.py` 的权威状态归桶实现（含六枚举与同义词表）。

    🔴 取不到就 fail-loud，不回退成本地简化版——两处各自实现同一判据然后悄悄漂移，
    正是本项目反复踩过的形态。
    """
    spec = importlib.util.spec_from_file_location("_zp_doc_ledger", _LEDGER_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载状态归桶权威实现：{_LEDGER_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.status_bucket, module.parse_frontmatter


# ── 围栏代码块切分 ───────────────────────────────────────────────────────────

class Block:
    """一个围栏代码块：`start_line` 为块**首行正文**的 1-based 行号。"""

    __slots__ = ("start_line", "lines", "info")

    def __init__(self, start_line: int, lines: list[str], info: str) -> None:
        self.start_line = start_line
        self.lines = lines
        self.info = info

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def iter_fenced_blocks(text: str) -> list[Block]:
    """切出全部围栏代码块。闭合围栏须同字符、长度 ≥ 开启、且不带 info string。"""
    lines = text.splitlines()
    blocks: list[Block] = []
    i = 0
    while i < len(lines):
        m = FENCE_RE.match(lines[i])
        if not m:
            i += 1
            continue
        fence = m.group("fence")
        char, width = fence[0], len(fence)
        body_start = i + 1
        j = body_start
        while j < len(lines):
            m2 = FENCE_RE.match(lines[j])
            if (m2 and m2.group("fence")[0] == char
                    and len(m2.group("fence")) >= width and not m2.group("info")):
                break
            j += 1
        blocks.append(Block(body_start + 1, lines[body_start:j], m.group("info")))
        i = j + 1
    return blocks


# ── 单块判定 ────────────────────────────────────────────────────────────────

def settings_line(block: Block) -> str | None:
    """块内第一条「行首 `【设置】`」的行；没有则该块不是 opener 块。"""
    for ln in block.lines:
        if SETTINGS_LINE_RE.match(ln):
            return ln
    return None


def block_env(block: Block) -> str | None:
    """块的执行环境：`"CC"` / `"Cowork"` / `None`（未标或不可判，**不猜**）。

    先看 `【设置】` 行，取不到再看整块——两种写法在库里都真实存在。
    """
    line = settings_line(block)
    for scope in ([line] if line else []) + [block.text]:
        if not scope:
            continue
        m = ENV_RE.search(scope)
        if m:
            token = m.group(1)
            return "Cowork" if token.lower() == "cowork" else "CC"
    return None


def check_block(block: Block) -> list[tuple[str, str]]:
    """返回该块命中的 `(形态代码, 说明)` 列表。形态代码 ∈ {"F1", "F2"}。"""
    problems: list[tuple[str, str]] = []
    is_opener = settings_line(block) is not None
    has_title_call = bool(SESSION_TITLE_RE.search(block.text))

    # 形态① —— 只对 CC 侧 opener 块成立（Cowork 与未标环境结构性排除，见 docstring）
    if is_opener and not has_title_call and block_env(block) == "CC":
        problems.append((
            "F1",
            "CC opener 块缺 `set_session_title` 那一行 ⇒ session 名会丢编号"
            "（模板库 §〇 补充一第 2 条／补充三；标题行以 `[…]` 开头不会自动变成 session 名）",
        ))

    # 形态② —— 只要块里出现了 set_session_title，就必须带子任务例外句
    if has_title_call:
        has_exception = bool(SUBTASK_TOKEN_RE.search(block.text)
                             and EXCEPTION_TOKEN_RE.search(block.text))
        if not has_exception:
            problems.append((
                "F2",
                "块内有 `set_session_title` 却无子任务例外句 ⇒ 被 Task/Agent 起的子任务执行它时，"
                '`"self"` 会解析到父 session、把调度它的那条会话改名（调用成功、无报错）'
                "（模板库 §〇 补充三之三）",
            ))
    return problems


# ── 当前在用 vs 历史 ─────────────────────────────────────────────────────────

def _last_commit_date(rel_path: str) -> date | None:
    """该文件最后一次提交的**提交时刻**（本地日期）；取不到返回 None（不静默当成很早）。"""
    try:
        out = subprocess.run(
            ["git", "-c", "core.quotepath=false", "log", "-1", "--format=%cI", "--", rel_path],
            cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    if not out:
        return None
    try:
        return date.fromisoformat(out[:10])
    except ValueError:
        return None


def classify_carrier(rel_path: str, status_raw: str, form: str,
                     last_commit: date | None) -> tuple[str, str]:
    """判「当前在用件 / 历史件 / 历史判不了」。返回 `(bucket, 判据)`。

    bucket ∈ {"current", "historical", "unknown-history"}。
    """
    norm = rel_path.replace("\\", "/")
    if ARCHIVE_DIR_SEGMENT in norm.split("/"):
        return "historical", f"H1 路径含 `{ARCHIVE_DIR_SEGMENT}/` 目录段"
    if status_raw in HISTORICAL_STATUS_BUCKETS:
        return "historical", f"H2 状态头归桶 = {status_raw}"
    if last_commit is None:
        return "unknown-history", "H3 判不了：git 历史取不到（浅克隆或未跟踪）"
    cutoff = RULE_EFFECTIVE_FORM1 if form == "F1" else RULE_EFFECTIVE_FORM2
    if last_commit < cutoff:
        return "historical", f"H3 最后提交 {last_commit.isoformat()} 早于规则生效日 {cutoff.isoformat()}"
    return "current", f"三层均不命中（最后提交 {last_commit.isoformat()}）"


# ── 扫描 ────────────────────────────────────────────────────────────────────

def _tracked_md_files() -> list[str]:
    # `-c core.quotepath=false`：git 默认把中文路径八进制转义，本项目路径几乎全是中文
    # （同 `工具-引导样板lint.py` / `工具-密钥扫描lint.py`）。
    out = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files", "*.md"],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout
    return [ln for ln in out.splitlines() if ln.strip()]


class Finding:
    __slots__ = ("rel", "line", "form", "detail", "bucket", "reason", "env")

    def __init__(self, rel, line, form, detail, bucket, reason, env):
        self.rel, self.line, self.form, self.detail = rel, line, form, detail
        self.bucket, self.reason, self.env = bucket, reason, env

    def render(self) -> str:
        env = self.env or "环境未标"
        return f"{self.rel}:{self.line}（{env}）[{self.form}] {self.detail}　← {self.reason}"


def scan(files: list[str]) -> tuple[list[Finding], dict[str, int]]:
    status_bucket, parse_frontmatter = _load_status_bucket()
    findings: list[Finding] = []
    stats = {"files": 0, "opener_blocks": 0, "cc": 0, "cowork": 0, "env_unknown": 0,
             "title_blocks": 0}
    commit_cache: dict[str, date | None] = {}

    for rel in files:
        try:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "【设置】" not in text and "set_session_title" not in text:
            continue

        blocks = iter_fenced_blocks(text)
        candidates = [b for b in blocks
                      if settings_line(b) is not None or SESSION_TITLE_RE.search(b.text)]
        if not candidates:
            continue
        stats["files"] += 1
        status_raw = status_bucket(parse_frontmatter(text).get("status", ""))

        for block in candidates:
            env = block_env(block)
            if settings_line(block) is not None:
                stats["opener_blocks"] += 1
                stats["cc" if env == "CC" else "cowork" if env == "Cowork" else "env_unknown"] += 1
            if SESSION_TITLE_RE.search(block.text):
                stats["title_blocks"] += 1

            for form, detail in check_block(block):
                if rel not in commit_cache:
                    commit_cache[rel] = _last_commit_date(rel)
                bucket, reason = classify_carrier(rel, status_raw, form, commit_cache[rel])
                findings.append(
                    Finding(rel, block.start_line, form, detail, bucket, reason, env))
    return findings, stats


FORM_TITLE = {
    "F1": "形态① · CC opener 块缺 set_session_title（规则生效日 2026-08-26）",
    "F2": "形态② · 有 set_session_title 缺子任务例外句（规则生效日 2026-08-28）",
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="opener 代码块 lint（队列 #284，两个失效形态一处守）")
    ap.add_argument("--enforce", action="store_true",
                    help="当前在用件有违规即以退出码 1 阻断（默认只告警、退出码 0）")
    ap.add_argument("--show-historical", action="store_true",
                    help="连历史件命中一起列明细（默认只给计数，因其按「历史记录不追改」不该修）")
    args = ap.parse_args(argv)

    files = _tracked_md_files()
    findings, stats = scan(files)

    cur = [f for f in findings if f.bucket == "current"]
    hist = [f for f in findings if f.bucket == "historical"]
    unk = [f for f in findings if f.bucket == "unknown-history"]

    print(f"扫描面：{len(files)} 份已跟踪 `.md`（`git ls-files \"*.md\"`），"
          f"其中 {stats['files']} 份含候选块；"
          f"opener 块 {stats['opener_blocks']} 个"
          f"（CC {stats['cc']} ／ Cowork {stats['cowork']}〔形态①结构性排除〕／"
          f"执行环境未标 {stats['env_unknown']}〔不猜，不判形态①〕）；"
          f"含 set_session_title 的块 {stats['title_blocks']} 个。")
    print(f"命中合计 {len(findings)} 处：当前在用件 {len(cur)} ／ 历史件 {len(hist)}"
          + (f" ／ 历史判不了 {len(unk)}" if unk else ""))
    print("  区分判据：H1 路径含 `z-已执行归档/` 目录段 ｜ H2 状态头归桶∈{已执行归档,已作废,历史快照}"
          "（复用 `工具-文档台账生成.py::status_bucket`）｜ H3 该文件最后一次 git 提交早于该形态规则生效日。")

    if unk:
        print(f"\n⚠ 有 {len(unk)} 处的 git 历史取不到（浅克隆或未跟踪），H3 判不了，"
              "已保守计入「当前在用」之外单列——这不是「突然多了违规」，CI 请配 fetch-depth: 0：")
        for rel in sorted({f.rel for f in unk}):
            print(f"  - {rel}")

    for form in ("F1", "F2"):
        sel = [f for f in cur if f.form == form]
        if not sel:
            continue
        print(f"\n── 当前在用件 · {FORM_TITLE[form]}，{len(sel)} 处 ──")
        for f in sel:
            print(f"  - {f.render()}")

    if hist:
        print(f"\n── 历史件命中 {len(hist)} 处（F1 {sum(1 for f in hist if f.form == 'F1')} ／ "
              f"F2 {sum(1 for f in hist if f.form == 'F2')}）：**按「历史记录不追改」不修、不阻断** ──")
        if args.show_historical:
            for f in hist:
                print(f"  - {f.render()}")
        else:
            print("  （加 --show-historical 看明细）")

    blocking = cur + unk
    if not blocking:
        print("\n✓ 当前在用件零违规。")
        return 0
    mode = "阻断" if args.enforce else "告警（不阻断）"
    print(f"\n✗ 当前在用件 {len(blocking)} 处待修【{mode}】。"
          "标准写法见 `1-转型规划/0-全景路线图/专线opener模板库.md` §〇 补充三「标准写法」块（全文照抄）。")
    return 1 if args.enforce else 0


if __name__ == "__main__":
    sys.exit(main())
