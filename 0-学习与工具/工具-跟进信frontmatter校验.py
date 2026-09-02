"""跟进信 frontmatter 最小 schema 校验（队列 §一 `#447` ⑴，Shao Peishen 2026-09-02 答 (b)）。

## 为什么是 schema 而不是「补一条必写 `决策点:`」

`#447` 行自陈：`决策点:` 这个字段在 64 封信里只有 18 封带，最后一封是 2026-08-10，此后归零。
泳道 B 第一段的取证（`1-转型规划/0-全景路线图/取证件-2026-09-02-跟进信元数据失血-泳道B.md`
§1.2）把根因钉死了：**它不是被人忘了写，是起草侧唯一的字段清单
（`0-学习与工具/skills源码/zhuopin-followup-letter/SKILL.md:163`）里根本没有它**——那行只写了
`title／created／status` 三个字段。起草一旦走 skill，写出来的 frontmatter 自然只有三个。

🔴 **所以「只加一条必写 `决策点:`」治不住**：该字段当初消亡的根因就是**无机器守**，
只加一条必写而不定 schema、不配可执行校验，等于再造一个没人守的字段——`#447` 行自己写着
「本行自身就是它所描述的那个病的第三个实例」，前两次都只落在文档里、没有承接载体。

## 三处失血，不是一处

字段名普查（本脚本 `--census` 可当场重跑，64 封信 28 个字段名）实测：

| # | 失血形态 | 实测 | 谁会被静默漏掉 |
|---|---|---|---|
| ⑴ | `决策点` 断供 | 18/64，2026-08-10 后归零 | 「这封信要他定什么」无机器载体 |
| ⑵ | **字段名分裂** | `收信人`(28) / `收件人`(19) | 按 `收信人` 取数的下游**静默漏掉 19 封** |
| ⑶ | **取值形态漂移** | `status` 62 次出现 **21 种取值** | 任何按 status 等值比较的判据 |

🔑 ⑵ 比「同义词」更糟：**两派的取值格式也不同**——`收信人` 写「部门 · 人名」
（`IT部 · 陈承`），`收件人` 写「人名（部门…）」（`唐燕萍（财务部 AI 专员）`）。
即便把字段名归一，两批取值仍然对不齐。故 S2 判为 violation 而非改名建议。

## 判据

- **S1 · 必写字段**：`title／status／created／收信人／编号／决策点／配套`。
  取证件 §三⑴ 提的清单，逐条有语料支撑（见 `--census`）。
  ⚠️ `决策点: 0 项` **必须合法**（通报类信的真实形态，实测 1 封），否则会逼出假数据。
  同理 `配套: 无` 合法——把「没有配套」逼成编一个出来，比字段缺失更坏。
- **S2 · 非法别名**：`收件人` ⇒ `收信人`。**取 `收信人` 为正的三条依据**：计数更高
  （28 > 19）、README 表头列名即 `收信人`、Shao Peishen 2026-09-02 点名的就是这条。
- **S3 · 取值形态**：`created` ＝ `YYYY-MM-DD`；`编号` ＝ `<部门>#<数字>`；
  `决策点` ＝ **前缀锚定** `^\\d+\\s*项`。
  🔴 **`决策点` 刻意不做全串锚定**：取证件 §三⑴ 建议的 `^\\d+ 项(（.+）)?$` 在真身上
  **会误杀 1 条真实取值**——`2 项（FO…／PO…），或告知已有的替代查询方式`（`IT部#5`）。
  一条把真实合法语料判成违规的判据，第一次跑就会被人加豁免绕开，等于没有。
- **S4 · `status` 取值漂移**：**只报 warning、不进 violations，且本脚本不定枚举。**
  定 status 的合法取值集合 ＝ 定口径（D1 🟡 `change_criteria`），且 21 种取值里
  `待发`(26)／`⏳ 待你审`(10)／`实名可发`(4) 三派各有真实来路，不是笔误。
  ⇒ 作为开放点交下一批，见产出件 §四。**本脚本只把漂移量算出来摆着。**

## 适用范围：只守新信，历史只测量

- 默认 `--since` 为空 ＝ 全量**测量**（warning 模式，退出码 0）。
- `--since YYYY-MM-DD --enforce` ＝ 只对该日之后 `created` 的信阻断。
  **历史 64 封一律不追改**（根 `CLAUDE.md` §1「历史记录不追改」；同族既例见
  `openspec/changes/followup-closure-form-survives-backfill` proposal「其余 53 行不追改」）。
- **排除 `-推送摘要.md`**：实测 `采购部-姚祖怡-跟进-2026-08-26-…-推送摘要.md` 无 `status`、
  且与正信共用 `编号: 采购部#19`——它是派生件不是信。**这条排除是从语料实测来的，不是猜的**；
  若不排除，S1 会对一个根本不该守的文件常年报违规，而这正是判据被人加豁免绕开的起点。

## 🔴 本脚本刻意不做的事

- **不动 `工具-落库sweep.py`、不动 `工具-共享文档编辑锁.py`** —— 二者属锁工具族，
  `OP-0902-A` 本批明令不入。挂 `release` 咽喉那一步的落点已写清，交下一批（产出件 §三）。
- **不改任何一封已发出的信**、**不改 README 一个字节**（`发送状态` 列是信级唯一权威源，
  2026-08-21 §四 `#85` 答 (b) 确立）。本脚本**只读**。
"""

from __future__ import annotations

import argparse
import collections
import os
import re
import sys

FOLLOWUP_DIR = "6-人才与组织/部门AI专员跟进"

# S1 必写字段。清单来自取证件 §三⑴，逐条有语料支撑。
REQUIRED_FIELDS = ("title", "status", "created", "收信人", "编号", "决策点", "配套")

# S2 非法别名 ⇒ 正字段。取 `收信人` 为正：计数 28>19、README 表头即此名。
ILLEGAL_ALIASES = {"收件人": "收信人"}

# S4 只观测、不判违规的字段（定枚举＝定口径，须另行签认）。
DRIFT_WATCH_FIELDS = ("status",)

# 派生件后缀：不是信，不参与 S1-S3。实测依据见模块 docstring。
DERIVED_SUFFIXES = ("-推送摘要.md",)

RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RE_LETTER_NO = re.compile(r"^\S+#\d+$")
# 🔴 前缀锚定，非全串锚定——理由见 docstring S3。
RE_DECISION = re.compile(r"^\d+\s*项")
RE_FM_KEY = re.compile(r"^([^\s:#][^:]*):(.*)$")


class Letter:
    """一封跟进信的 frontmatter 解析结果。"""

    def __init__(self, path: str, fields: dict[str, str], order: list[str]):
        self.path = path
        self.name = os.path.basename(path)
        self.fields = fields
        self.order = order

    @property
    def created(self) -> str:
        return self.fields.get("created", "")

    @property
    def is_derived(self) -> bool:
        return self.name.endswith(DERIVED_SUFFIXES)


def parse_frontmatter(text: str) -> tuple[dict[str, str], list[str]] | None:
    """取首个 `---` 块。非 frontmatter 开头返回 None（不猜、不回退）。"""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    fields: dict[str, str] = {}
    order: list[str] = []
    for line in text[3:end].split("\n"):
        m = RE_FM_KEY.match(line)
        if not m:
            continue
        key = m.group(1).strip()
        if key not in fields:
            order.append(key)
        fields[key] = m.group(2).strip()
    return fields, order


def collect_letters(repo_root: str) -> tuple[list[Letter], list[str]]:
    """扫 `跟进-` 形态的 .md。返回（可解析的信, 无 frontmatter 的文件名）。"""
    directory = os.path.join(repo_root, FOLLOWUP_DIR)
    letters: list[Letter] = []
    headless: list[str] = []
    if not os.path.isdir(directory):
        return letters, headless
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".md") or "跟进-" not in name:
            continue
        path = os.path.join(directory, name)
        with open(path, encoding="utf-8") as fh:
            parsed = parse_frontmatter(fh.read())
        if parsed is None:
            headless.append(name)
            continue
        letters.append(Letter(path, parsed[0], parsed[1]))
    return letters, headless


def check_letter(letter: Letter) -> tuple[list[str], list[str]]:
    """对一封信跑 S1-S3。返回（violations, warnings）。"""
    violations: list[str] = []
    warnings: list[str] = []
    if letter.is_derived:
        return violations, warnings

    # S2 先于 S1：别名存在时，S1 不应再重复报「缺 收信人」。
    aliased_to: set[str] = set()
    for alias, canonical in ILLEGAL_ALIASES.items():
        if alias in letter.fields:
            aliased_to.add(canonical)
            violations.append(
                f"S2 非法别名 `{alias}:` ⇒ 应写 `{canonical}:`"
                f"（取值格式亦不同，须一并归一，非单纯改名）"
            )

    for field in REQUIRED_FIELDS:
        if field in letter.fields:
            if not letter.fields[field]:
                violations.append(f"S1 必写字段 `{field}:` 取值为空")
            continue
        if field in aliased_to:
            continue  # 已由 S2 报出，不重复计数
        violations.append(f"S1 缺必写字段 `{field}:`")

    created = letter.fields.get("created", "")
    if created and not RE_DATE.match(created):
        violations.append(f"S3 `created` 非 YYYY-MM-DD 形态：{created!r}")

    no = letter.fields.get("编号", "")
    if no and not RE_LETTER_NO.match(no):
        violations.append(f"S3 `编号` 非 `<部门>#<数字>` 形态：{no!r}")

    decision = letter.fields.get("决策点", "")
    if decision and not RE_DECISION.match(decision):
        violations.append(f"S3 `决策点` 未以 `<数字> 项` 起首：{decision[:40]!r}")

    for field in DRIFT_WATCH_FIELDS:
        # S4 只观测，逐封不判——漂移是集合层面的性质，单封看不出来。
        _ = letter.fields.get(field)
    return violations, warnings


def duplicate_numbers(letters: list[Letter]) -> dict[str, list[str]]:
    """同一 `编号` 被多封正信占用（派生件已排除）。"""
    seen: dict[str, list[str]] = collections.defaultdict(list)
    for letter in letters:
        if letter.is_derived:
            continue
        no = letter.fields.get("编号")
        if no:
            seen[no].append(letter.name)
    return {k: v for k, v in seen.items() if len(v) > 1}


def census(letters: list[Letter]) -> collections.Counter:
    counter: collections.Counter = collections.Counter()
    for letter in letters:
        for field in letter.fields:
            counter[field] += 1
    return counter


def drift_report(letters: list[Letter], field: str) -> list[tuple[str, int]]:
    counter: collections.Counter = collections.Counter()
    for letter in letters:
        if letter.is_derived:
            continue
        value = letter.fields.get(field)
        if value:
            counter[value] += 1
    return counter.most_common()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="跟进信 frontmatter 最小 schema 校验（S1-S4，队列 §一 #447）"
    )
    ap.add_argument("--enforce", action="store_true",
                    help="有违规即以退出码 1 阻断（默认只告警、退出码 0）")
    ap.add_argument("--since", default=None,
                    help="只对 created 不早于该日（YYYY-MM-DD）的信判违规；"
                         "历史信一律只测量不追改")
    ap.add_argument("--census", action="store_true",
                    help="打印 frontmatter 字段名全量普查")
    ap.add_argument("--drift", action="store_true",
                    help="打印 S4 观测字段的取值漂移（不判违规）")
    ap.add_argument("--repo-root", default=None, help="覆盖仓库根（默认＝本 checkout）")
    args = ap.parse_args(argv)

    repo_root = args.repo_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    letters, headless = collect_letters(repo_root)
    if not letters:
        print(f"✗ 未找到任何跟进信（查找目录：{FOLLOWUP_DIR}）")
        return 1

    scored = [letter for letter in letters if not letter.is_derived]
    in_scope = scored
    if args.since:
        # 🔴 fail-safe：`created` 缺失或非法者**一律留在判定范围内**，不得因「日期比不过」
        # 而静默逃出 --since。实测有 2 封 2026-09-02 的在办信正是缺 `created`——
        # 若按空串参与比较，它们恒小于任何 --since 值，于是**缺字段反而免检**，
        # 错误不产生任何信号（同族教训：工具静默回退 / 判据恒真、零信息量）。
        in_scope = [letter for letter in scored
                    if not RE_DATE.match(letter.created) or letter.created >= args.since]

    all_violations: list[tuple[str, str]] = []
    measured_only = 0
    for letter in scored:
        violations, _ = check_letter(letter)
        if not violations:
            continue
        if letter in in_scope:
            all_violations.extend((letter.name, v) for v in violations)
        else:
            measured_only += len(violations)

    if args.census:
        counter = census(letters)
        print(f"📊 字段名普查：{len(letters)} 封带 frontmatter，共 {len(counter)} 个字段名")
        for field, count in counter.most_common():
            mark = ""
            if field in REQUIRED_FIELDS:
                mark = "  ← S1 必写"
            elif field in ILLEGAL_ALIASES:
                mark = f"  ← 🔴 S2 非法别名（应写 `{ILLEGAL_ALIASES[field]}`）"
            print(f"   {count:3d}  {field}{mark}")
        print()

    if args.drift:
        for field in DRIFT_WATCH_FIELDS:
            values = drift_report(scored, field)
            total = sum(c for _, c in values)
            print(f"📉 S4 取值漂移 `{field}`：{total} 次出现 / {len(values)} 种取值"
                  f"（只观测，本脚本不定枚举——定枚举＝定口径，须签认）")
            for value, count in values[:12]:
                print(f"   {count:3d}  {value[:60]!r}")
            print()

    for no, names in sorted(duplicate_numbers(scored).items()):
        print(f"⚠️  `编号: {no}` 被 {len(names)} 封正信共用：{'／'.join(names)}")
    for name in headless:
        print(f"⚠️  无 frontmatter，未参与判定：{name}")

    scope = f"（--since {args.since} 起共 {len(in_scope)} 封在判定范围内）" if args.since else \
            f"（全量 {len(scored)} 封，未限 --since ⇒ 测量模式）"
    if not all_violations:
        print(f"✓ 跟进信 frontmatter schema 校验通过 {scope}")
        if measured_only:
            print(f"  （另有 {measured_only} 处历史违规在 --since 之前，只测量不追改）")
        return 0

    mode = "阻断" if args.enforce else "告警（不阻断）"
    print(f"✗ 发现 {len(all_violations)} 处违规【{mode}】{scope}：")
    for name, violation in all_violations:
        print(f"  - {name}｜{violation}")
    if measured_only:
        print(f"  （另有 {measured_only} 处在 --since 之前，只测量不追改）")
    print("\n  判据正本见 1-转型规划/0-全景路线图/"
          "产出件-2026-09-02-跟进信元数据治理-泳道B.md §二。")
    return 1 if args.enforce else 0


if __name__ == "__main__":
    sys.exit(main())
