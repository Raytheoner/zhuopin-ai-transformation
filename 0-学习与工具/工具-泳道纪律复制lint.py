#!/usr/bin/env python3
"""泳道看护侧**纪律复制**反例守卫（变更包 `lane-watch-deploy-extension` §4；队列 §一 `#478` 期望产出 ③）。

## 它守什么

`zhuopin-lane-watch`（泳道看护）与 `zhuopin-lan-closeout`（回 LAN 收口）是收敛后的
两个 workflow。`.51` 部署的那套执行纪律**只长在收口那一侧**；`#478` 把「看护侧遇到
`.51` 项、他在环且 on-LAN 时可同 session 续做」这条时序放宽落地时，钉死的核心约束是
**指向而非复制**——看护侧只允许给出指向收口正本的指针，**不得存在那套纪律的任何一份
可执行副本**。理由是看护侧 SKILL.md 自己写过的一句话：复制护栏就是复制缺陷，而
**复制的护栏必然漂移**（同族先例：`#312` 读侧双文件解析、跟进信状态两处载体、
`#345` 35 份路径引导手抄）。

本脚本就是那条约束的机器形态。没有它，「别抄」就只是又一条人守，而本项目已反复
证明人守在这类形态上无效。

## 判据词从哪来——本脚本**不写死任何词表**

🔴 判据词**运行时从被守护关系的另一侧（收口规则正本）提取**：脚本读该正本的
「执行步骤」小节，机械抽出其步骤序列的标记词，再拿去检查看护侧载体。

**为什么不能把词表抄进本脚本**：那份手抄词表会成为第三份副本，而且是最容易被人
忘记跟着改的那一份——**用一份手抄去守「不许手抄」会让整件事变成笑话**
（design 决策点 6⑵(a)）。

🔴 **提取失败一律 fail-closed**：正本结构变化导致抽不到词时，本脚本**报错退出
（退出码 2）**，绝不「抽不到词就当没违规」——抽不到词 ⇒ 检查恒过 ⇒ 守卫静默失效，
那是本项目最熟悉的失败形态。

## 违规判据（`--threshold` 默认 4，实测校准值，见下）

以**空行分段**为扫描单元。段内先剔除**指针句**，再看剩下的文本里能否按**正本中的
原始顺序**排出 ≥ 门槛条数的标记词（子序列，允许中间夹别的字）。

- **指针句豁免**：一行同时含指向动词（`现读`／`见`／`指向`／`参见`）**与**收口正本的
  包标识（`zhuopin-lan-closeout`）时，该行不参与序列计算。豁免刻意收得很窄——
  只认「指着正本说话」的句子，不认任何注释标记或白名单文件（决策点 6⑶ 的 (b)/(c)
  两案已被否：白名单会被无限追加，注释标记等于把闸门交给被检查方）。
- **门槛 ＝ 4，是 apply 期实测校准出来的，不是拍脑袋**（design 刻意不预设数字，
  要求实测后回填本 docstring）：正本的步骤序列共 5 个标记词；看护侧现存三处载体
  里那句**警示性引用**（「…那套四步纪律只长在收口里，重新实现一遍就是复制护栏」）
  只带得动其中 3 个——它是**缩略的提及**，缺了正本里最吃重的那两个词。而一份真的
  副本必然把它们一起带过来。故 4 恰好把「提及」与「抄了」分在两边：
  - 正例（现存 `zhuopin-lane-watch/SKILL.md`、`工具-泳道看护状态机.py`、
    `lane-watch-mode/**`、本变更包自身）实测全绿；
  - 负例（人为注入一段照抄文本）实测被拦下。**只跑绿不算数**，负例验证是硬性的。

## 覆盖哪些载体

① `0-学习与工具/skills源码/zhuopin-lane-watch/**`
② `0-学习与工具/工具-泳道看护状态机.py`
③ `openspec/changes/lane-watch-mode/**`
④ `openspec/changes/lane-watch-deploy-extension/**`（**本变更包自身**——它是最有动机
   违反该约束的一次改动，把自己排除在守卫之外就是自证不可信）
⑤ 归档后的对应 specs：`openspec/specs/lane-watch*/**`

🔴 **被守护关系的另一侧（收口正本自身）刻意不在覆盖内**——那里本来就该有那套纪律，
它是唯一被允许持有它的地方。

用法：
  python 0-学习与工具/工具-泳道纪律复制lint.py            # 有违规即退出 1；抽不到判据词退出 2
  python 0-学习与工具/工具-泳道纪律复制lint.py --json
  python 0-学习与工具/工具-泳道纪律复制lint.py --threshold 4
"""
from __future__ import annotations

import argparse
import fnmatch
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

#: 被指向方＝纪律唯一正本。判据词从这里现取，本脚本一个词都不自带。
SOURCE_OF_TRUTH_REL = "0-学习与工具/skills源码/zhuopin-lan-closeout/SKILL.md"
#: 正本里承载步骤序列的小节标题（只锚标题、不锚行号——行号会漂）。
SOURCE_SECTION_TITLE = "执行步骤"

#: 受守护载体（glob，仓库根相对；`git ls-files` 的结果按此过滤）。
GUARDED_GLOBS = (
    "0-学习与工具/skills源码/zhuopin-lane-watch/*",
    "0-学习与工具/skills源码/zhuopin-lane-watch/**/*",
    "0-学习与工具/工具-泳道看护状态机.py",
    "openspec/changes/lane-watch-mode/*",
    "openspec/changes/lane-watch-mode/**/*",
    "openspec/changes/lane-watch-deploy-extension/*",
    "openspec/changes/lane-watch-deploy-extension/**/*",
    "openspec/specs/lane-watch/**/*",
    "openspec/specs/lane-watch-deploy-authorization/**/*",
)

#: 指针句的指向动词（豁免的**必要**条件之一；另一半是同行出现正本包标识）。
POINTER_VERBS = ("现读", "参见", "指向", "见")
#: 正本的包标识——指针句必须真的指着它，才算指针句。
POINTER_TARGET = "zhuopin-lan-closeout"

DEFAULT_THRESHOLD = 4

#: 「固定N步＝A→B→C→D」——正本里承载步骤序列的那一句。
_STEP_SEQUENCE_RE = re.compile(r"固定[一二三四五六七八九十\d]+步[＝=]([^；;。\n]+)")
#: 「…不过即X…」——序列之后那半句里的兜底动作，与序列同源，一并作为标记词。
_FALLBACK_ACTION_RE = re.compile(r"不过即([一-龥]{2,4}?)(?=停|即|退|回|，|,|；|;|。|\s|$)")
#: 标记词清洗：去掉 markdown 强调/反引号/空白，只留正文。
_CLEAN_RE = re.compile(r"[*`_\s「」【】\[\]（）()]+")


class CriteriaExtractionFailed(RuntimeError):
    """判据词抽取失败——fail-closed 的载体，绝不降级成「视为通过」。"""


def extract_section(text: str, title: str) -> str:
    """取出 `## <title>` 到下一个同级标题之间的正文。"""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(rf"^#{{1,6}}\s*{re.escape(title)}\s*$", line.strip()):
            start = i + 1
            break
    if start is None:
        raise CriteriaExtractionFailed(
            f"在 `{SOURCE_OF_TRUTH_REL}` 里找不到标题为「{title}」的小节——"
            "正本结构已变，判据词无法提取。"
        )
    body = []
    for line in lines[start:]:
        if re.match(r"^#{1,6}\s", line):
            break
        body.append(line)
    return "\n".join(body)


def extract_markers(source_text: str) -> list:
    """从正本「执行步骤」小节里现取标记词序列（**顺序即正本里的顺序**）。

    抽两部分：⑴ 「固定N步＝A→B→C→D」箭头串；⑵ 紧随其后的「不过即X」兜底动作。
    任一环节抽不出、或总数不足 4 个，一律 raise —— fail-closed。"""
    section = extract_section(source_text, SOURCE_SECTION_TITLE)
    m = _STEP_SEQUENCE_RE.search(section)
    if not m:
        raise CriteriaExtractionFailed(
            f"在 `{SOURCE_OF_TRUTH_REL}`「{SOURCE_SECTION_TITLE}」里找不到"
            "「固定N步＝…→…」形态的步骤序列——正本表述已变，判据词无法提取。"
        )
    markers = []
    for raw in m.group(1).split("→"):
        token = _CLEAN_RE.sub("", raw).strip()
        if token:
            markers.append(token)
    tail = _FALLBACK_ACTION_RE.search(section)
    if tail:
        token = _CLEAN_RE.sub("", tail.group(1)).strip()
        if token and token not in markers:
            markers.append(token)
    if len(markers) < 4:
        raise CriteriaExtractionFailed(
            f"从 `{SOURCE_OF_TRUTH_REL}` 只抽到 {len(markers)} 个标记词（{markers}），"
            "少于 4 个——判据不成立，拒绝在这种状态下判定通过。"
        )
    return markers


def is_pointer_line(line: str) -> bool:
    """指针句：既有指向动词、又真的指着收口正本。两个条件缺一不豁免。"""
    return POINTER_TARGET in line and any(v in line for v in POINTER_VERBS)


def _paragraphs(text: str):
    """空行分段，返回 `(起始行号, [行…])`。"""
    para: list = []
    start = 1
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            if not para:
                start = lineno
            para.append(line)
        elif para:
            yield start, para
            para = []
    if para:
        yield start, para


def ordered_marker_run(text: str, markers: list) -> tuple:
    """按 `markers` 的原始顺序，求文本里能排出的最长子序列长度及所用的词。"""
    INF = 1 << 30
    best = [-1] + [INF] * len(markers)
    used = [[] for _ in range(len(markers) + 1)]
    for m in markers:
        occ = [mo.start() for mo in re.finditer(re.escape(m), text)]
        if not occ:
            continue
        for c in range(len(markers), 0, -1):
            prev = best[c - 1]
            if prev >= INF:
                continue
            nxt = next((o for o in occ if o > prev), None)
            if nxt is not None and nxt < best[c]:
                best[c] = nxt
                used[c] = used[c - 1] + [m]
    length = max((c for c in range(len(markers) + 1) if best[c] < INF), default=0)
    return length, used[length]


def check_file(rel: str, text: str, markers: list, threshold: int) -> list:
    violations = []
    for start, lines in _paragraphs(text):
        kept = [ln for ln in lines if not is_pointer_line(ln)]
        if not kept:
            continue
        run, words = ordered_marker_run("\n".join(kept), markers)
        if run >= threshold:
            violations.append({
                "file": rel, "line": start, "matched": run,
                "words": words,
                "excerpt": kept[0][:80],
            })
    return violations


def guarded_files() -> list:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    rels = [line.strip() for line in out.stdout.splitlines() if line.strip()]
    picked = []
    for rel in rels:
        if rel == SOURCE_OF_TRUTH_REL:
            continue  # 正本自身刻意不在覆盖内——那里本来就该有它
        if any(fnmatch.fnmatch(rel, g) for g in GUARDED_GLOBS):
            picked.append(rel)
    return picked


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="泳道看护侧纪律复制反例守卫（判据词从收口正本现取）。")
    ap.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                    help=f"序列门槛条数（默认 {DEFAULT_THRESHOLD}，实测校准值，见模块 docstring）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    source_path = REPO_ROOT / SOURCE_OF_TRUTH_REL
    try:
        source_text = source_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"✗ fail-closed：读不到判据正本 `{SOURCE_OF_TRUTH_REL}`（{exc}）——"
              "拒绝在取不到判据词的状态下判定通过。")
        return 2
    try:
        markers = extract_markers(source_text)
    except CriteriaExtractionFailed as exc:
        print(f"✗ fail-closed：{exc}")
        print("  处置：先修正正本结构或本脚本的抽取式，再重跑；**不得**把词表抄进本脚本。")
        return 2

    files = guarded_files()
    violations = []
    for rel in files:
        try:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        violations.extend(check_file(rel, text, markers, args.threshold))

    if args.json:
        print(json.dumps(
            {"markers": markers, "threshold": args.threshold,
             "scanned": len(files), "violations": violations},
            ensure_ascii=False, indent=2,
        ))

    if not violations:
        if not args.json:
            print(f"✓ 泳道纪律复制 lint 通过（受守护载体 {len(files)} 个，判据词 "
                  f"{len(markers)} 个自 `{SOURCE_OF_TRUTH_REL}` 现取，门槛 {args.threshold}）。")
        return 0

    if not args.json:
        print(f"✗ 泳道纪律复制 lint 发现 {len(violations)} 处违规——看护侧出现了收口纪律的副本：")
        for v in violations:
            print(f"  - {v['file']}:{v['line']} 命中 {v['matched']} 个判据词"
                  f"（{'／'.join(v['words'])}）｜段首：{v['excerpt']}")
        print(f"  唯一正确写法＝指针：一句同时含指向动词与 `{POINTER_TARGET}` 正本路径的话，")
        print("  由执行方现读那一份照做。复制的护栏必然漂移——这正是本守卫存在的理由。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
