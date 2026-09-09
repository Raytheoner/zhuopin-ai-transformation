"""取证件**判绿断言**回显守卫（队列 §一 `#530`，两道判据一处守）。

> 🔴 **文件名只说了一半，是刻意的**（同 `工具-引导样板lint.py` 的处置）：本脚本守两族——
> 判据一＝取证件写「✅ 已修／转绿」却没留下命令＋回显；判据二＝对着一个守 ≥2 族判据的
> 门禁工具判绿，却只核了其中一族。**改名不如把范围写死在 docstring 里**——本 docstring
> 即适用范围正本，`门禁判据族清单.json` 是它的机器可读投影。

## 两族判据（一处守，账最清楚）

| | 守什么 | 判据正本 | 来源 |
|---|---|---|---|
| 判据一 | 取证件里的 `✅ 已修／转绿` 必须同段附命令＋回显 | `.claude/rules/两桌同步与取证.md` §三 | Shao Peishen 2026-09-09 答 `1a` |
| 判据二 | 门禁工具守 ≥2 族判据时，判绿必须复跑整套 | 同上 ＋ `0-学习与工具/门禁判据族清单.json` | Shao Peishen 2026-09-09 答 `2a` |

两族**同源＝结论与手段脱钩**：一条是「写了 ✅ 却没留下能证伪它的东西」，一条是「只核了
工具所守判据族里的一族就判绿」。故 one-in-one-out 落在同一个文件里。

## 为什么要有这道门禁（实证，不是预防性设计）

`1-转型规划/0-全景路线图/CI长期红-逐job根因取证-2026-09-06.md` 把
`引导样板lint::test_存量已清零` 记为 2026-09-06「本日转绿·已修」，**实测转绿只维持
3 小时 28 分**（`3c091c9` 19:02:51 判据二转绿 → 同日 `1ea9ac8` 22:30:38 判据一被新退化
打红；`git log -1 --format='%H %ad %s' --date=iso`，本地 UTC+8 已标基准）。此后一直红着、
**挂了 3 天无人能证伪**，直到 2026-09-09 一次全量回归偶然撞见（`OP-0909-T`，队列 §一
`#520`）。**原记录只有结论、没有回显 ⇒ 谁也没法在读它的时候当场证伪它。**

靠人守会归零：取证件由不同会话轮流写，换一个会话就没人记得复跑整套（同族＝`#487`
「格式正本与生成器之间没有机器守，全靠人每次比对」）。本脚本就是那条对价。

## 扫哪些文件（窄而准，宁可漏也不逼人加豁免）

只扫 `1-转型规划/0-全景路线图/` 下的**已跟踪 `.md`**，且文件名同时满足：
- 命中任一取证词：`取证`／`根因`／`复盘`／`实测结果`；
- 不命中任一排除前缀：`opener`／`开场prompt-`／`派单件-`／`看护件-`／`session接力`／
  `跨桌任务队列`／`专线opener`——这些是**派工与流水载体**，不是取证件；队列真身另有
  `工具-队列结构lint.py` 守，两处判据不重叠。

另有两个逐文件开关（写在文件任意位置的 HTML 注释里，`git diff` 里看得见）：
`<!-- 取证件: 是 -->` 强制纳入、`<!-- 取证件: 否 -->` 强制排除。

## 判据一 · 断言与证据的配对

**段**＝从一个 markdown 标题行（`#`～`######`）到下一个标题行之间的全部内容（首个标题
之前的前言算 `（前言）` 段）。断言与证据必须落在**同一段**——跨段的「见 §七」不算：
2026-09-06 那次失实，恰恰是速览表里写结论、证据在别处（当时连别处也没有）。

**判绿断言**（行内命中即算）：`✅ 已修`／`✅ 已修复`／`✅ 已修正`／`✅ 已解决`／
`✅ 已清零`／`转绿`（含「本日转绿」「已转绿」）。

**行级豁免**（这些不是断言，是撤回或引述，命中即跳过该行）：
`失实`／`原记`／`原文为`／`据称`／`未取证`／`勘误`／`改判`／`不得写`／`必须附`／
`本条纪律`／`<!-- 取证豁免:`。

**证据**（同段内需**两样都有**，缺哪样报哪样）：
- **命令**：`python <路径>.py`／`python -m <模块>`／`pytest <参数>`／
  `git log|show|diff|status|rev-parse|ls-files|fsck|…`／`npm run|install|ci|test`／
  `openspec validate|list|show`／`Get-Xxx`／`$ `／`PS>` 起首；
- **回显**：`<数字> passed|failed|skipped|error`／`AssertionError`／`Traceback`／
  `退出码`／`exit code`／`回显`／`输出为|输出＝|输出即`／行首 `✓ `/`✗ `／
  `<数字> 处|个|条|行|件 命中|违规|通过|失败|已跟踪`。

🔴 **两个指纹都刻意写窄**：`git 历史`／`python 脚本`／`⇒`／`OK` 这类散文用词在本仓库
遍地都是，认了等于不认——门禁若因「几乎每段都提到过 git」而永远不响，那就是白建。宁可
偶尔要求写得更实一点，也不要建一道从不响的门。

## 判据二 · 多族判绿必须复跑整套

对每个含判绿断言的段：找出段内提到的、登记在 `门禁判据族清单.json` 里的门禁工具
（按 `id`／`别名` 匹配）。凡提到的工具守 ≥2 族，则该段的证据必须满足其一：
- 证据里出现该工具的 `整套复跑命令` 任一子串（跑脚本本体或它的整套单测 ⇒ 必然过全部族）；
- 或段内把**每一族**都点到名（按各族 `别名` 匹配）。
否则违规，报文里写清「只核了 M/N 族，缺 X、Y」。

## 清单自洽（每次跑都校，不是可选项）

`门禁判据族清单.json` 的每条都要过：路径存在、每族 `docstring锚` 逐字出现在该工具
docstring 里、`族命名模式` 在 docstring 上的**全部命中集合**与声明的锚集合**逐字相等**、
族数 ≥2。最后一条是**漂移守**——工具长出第三族而清单没跟上时当场红，而不是等到下一次
判绿出错。清单自洽失败一律 fail-closed（退出码 2），不降级为告警：判据源坏了还照跑，
出来的绿是假绿（同根 `CLAUDE.md` §5「工具静默回退」）。

## baseline（必须带）

判据上线时存量非零，无 baseline 直接开门禁会让 CI 长期红、然后被习惯性忽略（同
`工具-队列结构lint.py` 称呼判据的处置）。baseline＝**计数棘轮**：键为
`<相对路径>::<段标题>`，值为该段的违规数；当前数 > 冻结数才算违规。刻意**不**记断言原文
哈希——那样在已冻结的段里改动离断言很远的正文也会失配，报出纯噪音，而修它最省事的办法
就是重刷 baseline ⇒ 门禁自废。

🔴 刻意不提供一键写盘：`--emit-baseline` 只往 stdout 打，重刷必须经过一次显式重定向
＋ 一次 commit，好让它在 diff 里被人看见。

用法：
  python 0-学习与工具/工具-取证件回显lint.py             # 告警模式（退出码恒 0，清单自洽失败仍 2）
  python 0-学习与工具/工具-取证件回显lint.py --enforce    # 阻断模式（有违规即 1）
  python 0-学习与工具/工具-取证件回显lint.py --json       # 结构化输出
  python 0-学习与工具/工具-取证件回显lint.py --emit-baseline > 0-学习与工具/取证件回显lint-baseline.json
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    """主工作区根（同族工具一致：走 `git rev-parse`，不按 `__file__` 数层数）。"""
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=Path(__file__).resolve().parent, capture_output=True, text=True, check=True,
    )
    return Path(out.stdout.strip())


REPO_ROOT = _repo_root()

#: 门禁判据族清单（判据二的机器可读判据源；正本仍是各工具自己的 docstring）。
MANIFEST_PATH = Path(__file__).resolve().with_name("门禁判据族清单.json")
#: baseline（计数棘轮，冻结上线当日存量）。
BASELINE_PATH = Path(__file__).resolve().with_name("取证件回显lint-baseline.json")

#: 扫描范围：只在这个目录下找取证件。
SCAN_DIR_REL = "1-转型规划/0-全景路线图"
#: 取证词（文件名命中任一即候选）。
EVIDENCE_NAME_WORDS = ("取证", "根因", "复盘", "实测结果")
#: 排除前缀（派工与流水载体，不是取证件）。
EXCLUDED_NAME_PREFIXES = (
    "opener", "开场prompt-", "派单件-", "看护件-", "session接力",
    "跨桌任务队列", "专线opener",
)
#: 逐文件强制开关（写在文件任意位置的 HTML 注释里）。
OPT_IN_MARKER = "<!-- 取证件: 是 -->"
OPT_OUT_MARKER = "<!-- 取证件: 否 -->"

#: 判绿断言。`✅` 与词之间允许空格/加粗星号。
ASSERTION_RE = re.compile(
    r"(?:✅\s*\**\s*(?:已修复|已修正|已修|已解决|已清零))|(?:转绿)"
)
#: 行级豁免词——撤回、引述、纪律正文本身，都不是「在断言绿」。
ASSERTION_WAIVER_WORDS = (
    "失实", "原记", "原文为", "据称", "未取证", "勘误", "改判",
    "不得写", "必须附", "本条纪律", "<!-- 取证豁免:",
)

#: 命令指纹（同段内出现任一即算「有命令」）。
#: 🔴 刻意写窄：`git 历史`／`python 脚本` 这类**散文里的工具名**不该算命令证据，
#: 否则门禁会因为「几乎每段都提到过 git」而永远不响——那就是白建。故每一条都要求
#: 出现真实的子命令、`-m`、或 `.py` 路径。
COMMAND_RE = re.compile(
    r"(?:^|[\s`(（>|])(?:"
    r"\$\s"
    r"|PS[ ]?>"
    r"|python3?\s+(?:-m\s+\S+|[^\s`）]*\.py)"
    r"|(?:pytest|py\.test)\s+[-\"'\w/]"
    r"|git\s+(?:log|show|diff|status|rev-parse|ls-files|fsck|branch|commit|cat-file|blame|stash)\b"
    r"|npm\s+(?:run|install|ci|test)\b"
    r"|npx\s+\S"
    r"|openspec\s+(?:validate|list|show)\b"
    r"|Get-[A-Z]\w+"
    r")",
    re.MULTILINE,
)
#: 回显指纹（同段内出现任一即算「有回显」）。同样刻意写窄：只认**真实输出的指纹**，
#: 不认 `⇒`／`OK` 这类通用箭头与口头语（本仓库散文里遍地都是，认了等于不认）。
ECHO_RE = re.compile(
    r"(?:\d+\s*(?:passed|failed|skipped|error|errors|warning|warnings)\b"
    r"|\bAssertionError\b|\bTraceback\b|\bSyntaxError\b"
    r"|退出码|exit\s*code"
    r"|回显|输出为|输出＝|输出即|输出:|输出："
    r"|^\s*[✓✗]\s|[（(]输出[)）]"
    r"|\d+\s*(?:处|个|条|行|件)(?:命中|违规|通过|失败|已跟踪))",
    re.IGNORECASE | re.MULTILINE,
)
#: 围栏代码块。
FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
#: markdown 标题。
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")

PRELUDE_TITLE = "（前言）"


class ManifestError(RuntimeError):
    """清单自洽校验失败——fail-closed，不降级为告警。"""


# ---------------------------------------------------------------- 清单

def load_manifest(path: Path | None = None) -> dict:
    target = path or MANIFEST_PATH
    if not target.exists():
        raise ManifestError(
            f"门禁判据族清单不存在：{target}"
            "（判据二靠它才知道哪些工具守 ≥2 族；缺它则无法区分『复跑了整套』与"
            "『只核了一族』，故 fail-closed 而不是当作零条清单静默放行）"
        )
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"门禁判据族清单无法解析：{target}（{exc!r}）") from exc


def _tool_docstring(rel_path: str) -> str:
    src_path = REPO_ROOT / rel_path
    if not src_path.exists():
        raise ManifestError(f"清单登记的门禁工具不存在：{rel_path}")
    try:
        tree = ast.parse(src_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        raise ManifestError(f"清单登记的门禁工具无法解析：{rel_path}（{exc!r}）") from exc
    return ast.get_docstring(tree) or ""


def 校验清单自洽(manifest: dict) -> list[str]:
    """逐条校清单与工具 docstring 的一致性，返回问题列表（空＝自洽）。

    这一步是**漂移守**：工具长出第三族而清单没跟上时当场红，而不是等到下一次
    判绿出错才发现。故它必须每次都跑，且失败即 fail-closed。
    """
    problems: list[str] = []
    tools = manifest.get("门禁工具")
    if not isinstance(tools, list) or not tools:
        return ["清单里 `门禁工具` 缺失或为空——本判据没有判据源可用"]

    for tool in tools:
        tid = tool.get("id", "<无 id>")
        rel = tool.get("路径")
        families = tool.get("判据族") or []
        if not rel:
            problems.append(f"{tid}：缺 `路径`")
            continue
        if len(families) < 2:
            problems.append(
                f"{tid}：只声明了 {len(families)} 族——本清单**只登记守 ≥2 族的工具**，"
                "只守一族的工具没有『只核一族』这个失效面，登记进来只会让清单变噪音"
            )
        try:
            doc = _tool_docstring(rel)
        except ManifestError as exc:
            problems.append(str(exc))
            continue

        anchors = []
        for fam in families:
            anchor = fam.get("docstring锚")
            if not anchor:
                problems.append(f"{tid}：有一族缺 `docstring锚`")
                continue
            anchors.append(anchor)
            if anchor not in doc:
                problems.append(
                    f"{tid}：族锚 `{anchor}` 未逐字出现在 {rel} 的模块 docstring 里"
                    "——清单必须是工具自陈的投影，不能自己发明族"
                )

        pattern = tool.get("族命名模式")
        if pattern:
            try:
                found = set(re.findall(pattern, doc))
            except re.error as exc:
                problems.append(f"{tid}：`族命名模式` 不是合法正则（{exc!r}）")
                continue
            declared = set(anchors)
            missing = sorted(found - declared)
            extra = sorted(declared - found)
            if missing:
                problems.append(
                    f"{tid}：docstring 里出现了未登记的判据族 {missing}"
                    f"——工具长出新族而本清单没跟上（漂移守命中）"
                )
            if extra:
                problems.append(
                    f"{tid}：清单声明了 docstring 里找不到的族 {extra}"
                    "——工具已退役该族、或清单写错"
                )
        if not tool.get("整套复跑命令"):
            problems.append(f"{tid}：缺 `整套复跑命令`，判据二无法判定『复跑了整套』")
    return problems


# ---------------------------------------------------------------- 取件

def _tracked_md_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "--", f"{SCAN_DIR_REL}/*.md"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def 是取证件(rel: str, text: str) -> bool:
    """判一个 md 是不是取证件。逐文件开关优先于文件名判据。"""
    if OPT_OUT_MARKER in text:
        return False
    if OPT_IN_MARKER in text:
        return True
    name = Path(rel).name
    if any(name.startswith(p) for p in EXCLUDED_NAME_PREFIXES):
        return False
    return any(w in name for w in EVIDENCE_NAME_WORDS)


def guarded_files() -> list[tuple[str, str]]:
    """返回 [(相对路径, 全文)]，只含真正入守的取证件。"""
    picked = []
    for rel in _tracked_md_files():
        try:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if 是取证件(rel, text):
            picked.append((rel, text))
    return picked


# ---------------------------------------------------------------- 分段

def split_segments(text: str) -> list[dict]:
    """按 markdown 标题切段。围栏代码块内的 `#` 不当标题（否则注释行会切碎段）。"""
    segments: list[dict] = []
    cur = {"title": PRELUDE_TITLE, "start_line": 1, "lines": []}
    in_fence = False
    for idx, line in enumerate(text.splitlines(), start=1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            cur["lines"].append((idx, line))
            continue
        m = None if in_fence else HEADING_RE.match(line)
        if m:
            if cur["lines"] or cur["title"] != PRELUDE_TITLE:
                segments.append(cur)
            cur = {"title": m.group(2).strip(), "start_line": idx, "lines": []}
        else:
            cur["lines"].append((idx, line))
    segments.append(cur)
    return [s for s in segments if s["lines"] or s["title"] != PRELUDE_TITLE]


def segment_text(seg: dict) -> str:
    return "\n".join(line for _, line in seg["lines"])


def find_assertions(seg: dict) -> list[tuple[int, str]]:
    """段内的判绿断言行 [(行号, 原文)]，已扣掉行级豁免。"""
    hits = []
    in_fence = False
    for lineno, line in seg["lines"]:
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            # 围栏块里的 `转绿` 多半是被引用的回显原文，不是本件的断言。
            continue
        if not ASSERTION_RE.search(line):
            continue
        if any(w in line for w in ASSERTION_WAIVER_WORDS):
            continue
        hits.append((lineno, line.strip()))
    return hits


def evidence_of(seg: dict) -> dict:
    """段内证据体检：命令有没有、回显有没有。"""
    body = segment_text(seg)
    return {
        "有命令": bool(COMMAND_RE.search(body)),
        "有回显": bool(ECHO_RE.search(body)),
    }


# ---------------------------------------------------------------- 判据

def _excerpt(line: str, width: int = 60) -> str:
    flat = re.sub(r"\s+", " ", line).strip()
    return flat if len(flat) <= width else flat[: width - 1] + "…"


def check_segment(rel: str, seg: dict, manifest: dict) -> list[dict]:
    """对一个段跑两族判据，返回违规记录列表。"""
    assertions = find_assertions(seg)
    if not assertions:
        return []

    violations: list[dict] = []
    ev = evidence_of(seg)
    body = segment_text(seg)
    key = f"{rel}::{seg['title']}"

    # ── 判据一：断言必须同段附命令＋回显 ──────────────────────────
    if not (ev["有命令"] and ev["有回显"]):
        missing = []
        if not ev["有命令"]:
            missing.append("命令")
        if not ev["有回显"]:
            missing.append("回显")
        for lineno, line in assertions:
            violations.append({
                "判据": "判据一",
                "file": rel,
                "line": lineno,
                "段": seg["title"],
                "key": key,
                "缺": missing,
                "说明": f"判绿断言缺{'＋'.join(missing)}（同段内找不到）",
                "excerpt": _excerpt(line),
            })

    # ── 判据二：多族门禁判绿必须复跑整套 ──────────────────────────
    for tool in manifest.get("门禁工具", []):
        names = [tool.get("id", "")] + list(tool.get("别名") or [])
        if not any(n and n in body for n in names):
            continue
        families = tool.get("判据族") or []
        if len(families) < 2:
            continue
        full_rerun = any(
            cmd and cmd in body for cmd in (tool.get("整套复跑命令") or [])
        )
        if full_rerun:
            continue
        covered, uncovered = [], []
        for fam in families:
            aliases = [fam.get("docstring锚", "")] + list(fam.get("别名") or [])
            (covered if any(a and a in body for a in aliases) else uncovered).append(
                fam.get("名称") or fam.get("docstring锚", "?")
            )
        if not uncovered:
            continue
        lineno, line = assertions[0]
        violations.append({
            "判据": "判据二",
            "file": rel,
            "line": lineno,
            "段": seg["title"],
            "key": key,
            "工具": tool.get("id"),
            "覆盖": f"{len(covered)}/{len(families)}",
            "缺族": uncovered,
            "说明": (
                f"对 `{tool.get('id')}`（守 {len(families)} 族）判绿，"
                f"但只核到 {len(covered)}/{len(families)} 族，缺：{'／'.join(uncovered)}；"
                f"段内也没有整套复跑命令（{'／'.join(tool.get('整套复跑命令') or [])}）"
            ),
            "excerpt": _excerpt(line),
        })
    return violations


def scan(manifest: dict, files: list[tuple[str, str]] | None = None) -> list[dict]:
    todo = files if files is not None else guarded_files()
    found: list[dict] = []
    for rel, text in todo:
        for seg in split_segments(text):
            found.extend(check_segment(rel, seg, manifest))
    return found


# ---------------------------------------------------------------- baseline

def load_baseline(path: Path | None = None) -> tuple[dict[str, int], str | None]:
    """读 baseline，返回 (段键→冻结数, 错误说明)。

    缺文件不静默当空——那会让「存量全成违规」被误读成「判据突然变严」，
    同根 `CLAUDE.md` §5「工具静默回退」。
    """
    target = path or BASELINE_PATH
    if not target.exists():
        return {}, (
            f"baseline 文件不存在：{target}"
            "（本判据以 baseline 冻结存量、只拦新增，缺它则无法区分历史与新增）"
        )
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"baseline 文件无法解析：{target}（{exc!r}）"
    hits = data.get("命中", {})
    return {str(k): int(v) for k, v in hits.items()}, None


def apply_baseline(
    violations: list[dict], baseline: dict[str, int]
) -> tuple[list[dict], list[str]]:
    """计数棘轮：某段当前违规数 > 冻结数，超出的那几条才算违规。

    返回 (仍算违规的记录, baseline 漂移说明)。漂移＝冻结时有、如今变少或归零，
    只提示不拦（那是好事，但要让人看见 baseline 该瘦了）。
    """
    by_key: dict[str, list[dict]] = {}
    for v in violations:
        by_key.setdefault(v["key"], []).append(v)

    live: list[dict] = []
    for key, items in by_key.items():
        frozen = baseline.get(key, 0)
        if len(items) > frozen:
            for v in items[frozen:]:
                v = dict(v)
                v["baseline冻结数"] = frozen
                live.append(v)

    drift = []
    for key, frozen in baseline.items():
        now = len(by_key.get(key, []))
        if now < frozen:
            drift.append(f"{key}（baseline {frozen} → 现 {now}）")
    return live, drift


def emit_baseline(violations: list[dict]) -> str:
    counts: dict[str, int] = {}
    for v in violations:
        counts[v["key"]] = counts.get(v["key"], 0) + 1
    payload = {
        "说明": (
            "取证件判绿回显 lint 的 baseline（队列 §一 `#530`）：冻结判据上线当日的存量违规，"
            "只拦新增。键＝`<相对路径>::<段标题>`，值＝该段的违规数（计数棘轮，不记断言原文"
            "哈希——那会让同段内无关正文的改动报出纯噪音，逼人重刷 baseline ⇒ 门禁自废）。"
            "🔴 历史记录不追改：本文件的存在正是这条纪律的机器表达，不得为了让数字好看而去"
            "改历史取证件的正文。"
        ),
        "重刷方式": (
            "python 0-学习与工具/工具-取证件回显lint.py --emit-baseline > "
            "0-学习与工具/取证件回显lint-baseline.json"
            "（刻意没有一键写盘开关：重刷必须经过一次显式重定向 + 一次 commit，"
            "好让它在 diff 里被人看见）"
        ),
        "命中": dict(sorted(counts.items())),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="取证件判绿断言回显守卫（队列 #530，两道判据一处守）",
    )
    parser.add_argument("--enforce", action="store_true",
                        help="阻断模式：有违规即退出码 1（默认只告警，退出码 0）")
    parser.add_argument("--json", action="store_true", help="结构化输出")
    parser.add_argument("--emit-baseline", action="store_true",
                        help="把当前违规集按 baseline 格式打到 stdout（不写盘）")
    parser.add_argument("--no-baseline", action="store_true",
                        help="忽略 baseline，报出全部违规（用于人工盘存量）")
    args = parser.parse_args(argv)

    try:
        manifest = load_manifest()
        problems = 校验清单自洽(manifest)
    except ManifestError as exc:
        print(f"✗ fail-closed：{exc}")
        return 2
    if problems:
        print("✗ fail-closed：门禁判据族清单与工具 docstring 不自洽——")
        for p in problems:
            print(f"  - {p}")
        print("  处置：先让 `0-学习与工具/门禁判据族清单.json` 与各工具 docstring 对齐，再重跑。")
        return 2

    files = guarded_files()
    all_violations = scan(manifest, files)

    if args.emit_baseline:
        print(emit_baseline(all_violations))
        return 0

    drift: list[str] = []
    if args.no_baseline:
        violations = all_violations
        baseline_error = None
    else:
        baseline, baseline_error = load_baseline()
        violations, drift = apply_baseline(all_violations, baseline)

    if args.json:
        print(json.dumps({
            "扫描件数": len(files),
            "清单工具数": len(manifest.get("门禁工具", [])),
            "全部命中": len(all_violations),
            "扣除baseline后": len(violations),
            "baseline漂移": drift,
            "baseline错误": baseline_error,
            "violations": violations,
        }, ensure_ascii=False, indent=2))

    if baseline_error and not args.json:
        print(f"⚠️ {baseline_error}")

    if not violations:
        if not args.json:
            print(
                f"✓ 取证件判绿回显 lint 通过（受守取证件 {len(files)} 件，"
                f"清单登记多族门禁工具 {len(manifest.get('门禁工具', []))} 个，"
                f"存量已由 baseline 冻结 {len(all_violations)} 处）。"
            )
            for d in drift:
                print(f"  ℹ️ baseline 漂移（已修好、可瘦 baseline）：{d}")
        return 0

    if not args.json:
        print(f"✗ 取证件判绿回显 lint 发现 {len(violations)} 处违规：")
        for v in violations:
            print(f"  - [{v['判据']}] {v['file']}:{v['line']}｜段「{v['段']}」")
            print(f"      {v['说明']}")
            print(f"      断言原文：{v['excerpt']}")
        print("  判据正本＝`.claude/rules/两桌同步与取证.md` §三；")
        print("  处置：把当时那条完整命令＋真实回显补进**同一段**；")
        print("        确实没取证的，把 ✅ 改成「据称已修·未取证」——降级措辞本身不算违规。")
        for d in drift:
            print(f"  ℹ️ baseline 漂移（已修好、可瘦 baseline）：{d}")
    return 1 if args.enforce else 0


if __name__ == "__main__":
    sys.exit(main())
