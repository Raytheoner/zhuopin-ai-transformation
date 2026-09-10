"""opener 生成器 —— 按 `opener骨架.md` 唯一格式来源，参数化拼出成品 opener（队列 §一 `#461`）。

## 背景与取号

队列 `#461`（`OP-0902-X2` 立行，2026-09-02）委托本工具承接"格式＋编号两件同源解决"——
此前手写 opener 反复漏字段（`工具-opener块lint.py` 记录的形态①~⑤），本工具把拼装步骤
机制化，缺字段直接报错退出、不出半成品。

🔴 **格式正本的时效说明（本次建造实测发现，写入供后续核对）**：`#461` 行原文写
"§〇.00 骨架本批同时落档，生成器可直接以它为唯一格式来源"——这句在 2026-09-02 写下时
准确，但 `专线opener模板库.md` 已于 **2026-09-04 A2 瘦身**把骨架正文迁出（该库 §〇.00
现在只剩一句指针）。当前唯一可照抄物是 `1-转型规划/0-全景路线图/opener骨架.md`
（根 `CLAUDE.md` §3 与模板库 §〇.00 均已指向这里）。本工具的 CC/Cowork 模板即按该文件
2026-09-04 生效版逐字对齐，**不从模板库 §〇 任一节重建**。

## 判据复用（不写第二份）

拼装结果自检复用 `工具-opener块lint.py::check_block`（同一份判据实现），不再自造第二套
"opener 块合不合格"的规则——理由与该 lint 脚本本身"不写第二份"的告诫一致：两处各自
实现同一判据、然后悄悄漂移，是本项目已反复踩过的坑。

## P7① 撞号查重（构建环境瘦身第三轮方案-2026-09-05 P7；队列 §一 `#487`）

`OP-0904-E` 曾撞号——两条互不知情的线各自取了同一个编号。取号规则本身写在
`opener骨架.md` 文末（人守 `grep`），但人守就会漏跑。本工具在 `generate_opener`
内加一道机器守：按 `--op-id` 的 `MMDD` 部分，扫 `1-转型规划/` 全树 `.md`，收集当日
已出现过的编号后缀——**全称**（`OP-MMDD-X`）与**短形**（`[Win]MMDDX-`，仅认这个
锚点，不做全文裸子串扫描，见 `opener骨架.md`「短形 MMDDX 只用于 session 名」）
两种形态皆计入。命中即拒绝，报错信息里直接给出当日下一个未用的空号，不需要
调用方自己再算一遍。

## 取号即声明——占位台账（队列 §一 `#549` ⑶／`#531` 子项；openspec `opener-id-claim-semantics`，2026-09-10）

P7① 查重只看得见**已落档**的号（`_scan_used_suffixes` 的射程自陈见其文档字符串）。
2026-09-10 当日实证正好界定这条边界：`OP-0910-H` 撞号被拦（对方已落档），`OP-0910-I`／
`OP-0910-J` 撞号**未被拦**（两边都在起草期、都没落档，靠读对方锁 note 才发现）。
⇒ 出件成功即在 `<主工作区>/reports/op-id-claims.jsonl` 写一条**有时效的机器占位**
（`_claim_op_id`）；查重同时扫已落档文件与未过期占位；落档后（`used` 命中）或超过
`CLAIM_TTL_MINUTES` 自动清理。**语义边界**：永久占用仍只认「已落档」（design ①(a)），
占位只覆盖「取号→落档」那段真空、到期即作废＝「未派出即作废」的机器实现；它**不是**
人手把号写进 `.md` 的占位登记（spec 明令禁止的那种）。台账读写失败 ⇒ fail-closed 不出件。
🔴 **台账必须落主工作区**（`git rev-parse --git-common-dir`），否则各 worktree 各写一份、
互相看不见——「不可见的占号台账等于没占」。

## variant：三种骨架变体（构建环境瘦身第三轮方案 P2/P4；队列 §一 `#487`）

- `standard`（默认）：骨架【CC】／【Cowork】标准变体，含 `set_session_title` 行。
- `subtask_lane`：骨架【CC · 子任务泳道】变体——**不含** `set_session_title` 行
  （2026-09-05 队列 §一 `#487`／(甲) 拍板：源头不放，不指望子任务读懂例外句），
  收尾无条件追加 P4 两条默认口径（并行上限 4／错峰 ≥90 秒；只 push 分支不 ff）
  ＋ **收工哨兵一条**（队列 §一 `#550`，2026-09-10：`OPENER_DONE`／`OPENER_PARTIAL` 是
  `工具-opener批处理执行v2.ps1` 判成败的双指标之一，此前正文一个字没提，四条泳道活全做了
  却全被判 `NO-SENTINEL`；机器守＝`工具-opener块lint.py` 形态⑨）。
  🔴 **未传 `--do`／`--dont` 时不拼「做什么／不做什么」两段**（队列 §一 `#487`
  2026-09-09 apply）：骨架【CC · 子任务泳道】节明写「本变体恒为三行，不多写一行」，
  做什么／不做什么／收工一律写进**队列行**。此前无条件硬塞 `1. …／- …` 两段占位，
  与本行既有子项**同源而镜像**——既有子项是「一个参数被接受却不生效」（`--dont`
  静默丢弃），这一处是「**一个参数没传却仍产出内容**」；根因都是生成器与格式正本
  各自演进、其间无机器守。传了 `--do`／`--dont` 则照拼（`BODY_PARAM_SUPPORT` 登记
  本组合两个都支持，调用方明确要写就不拦）。机器守＝`工具-opener块lint.py` 形态⑧
  ＋ 单测 `骨架与生成器契约`（读骨架原文比对，不靠人每次肉眼核）。
- `guardian`：骨架 §三bis 看护者开场词变体——含 `set_session_title`（它是本批
  唯一真正被粘贴进独立 CC 会话的一份），分支字段是固定字面量（看护者本身不建
  分支），正文追加同一条 P4 默认口径（这次是讲给看护者听，指导它怎么起子任务）。

## `--do` / `--dont` 的静默丢弃守卫（队列 §一 `#487` 子项／`OP-0906-M`，2026-09-06）

2026-09-06 实撞：`--env Cowork --dont "<三条硬约束>"` **既不生效也不报错**——不是工具
bug，是当时【Cowork】骨架本身只有「做什么／收工」两段。判据：**一个参数被接受却不
生效，比它被拒绝更危险。**

Shao Peishen 2026-09-06 裁 **(c) 甲＋精简版乙**，两个洞分别用两种手法堵：

- **Cowork ⇒ 让它生效（方案甲）**：骨架【Cowork】节补「不做什么」段、本工具 Cowork
  分支拼 `dont_block`、`工具-opener块lint.py` 形态⑦机器守。**Cowork 不再被本守卫拦。**
- **`--variant guardian` ⇒ fail-loud（精简版乙）**：§三bis 看护者开场词是固定形态
  （四行 ＋ P4 扇出口径），正文既不拼 `--do` 也不拼 `--dont`，且**不该**为它补段
  （看护者的任务正本在看护件全文里）。这个洞补段补不掉，只能报错退出（退出码 1），
  并在报错信息里给出该走哪条承接路径。

`BODY_PARAM_SUPPORT` 白名单登记每个「环境×变体」真的会拼进成品的正文参数；
🔴 **白名单而非黑名单**——黑名单忘登记 ⇒ 回到静默丢弃（fail-open，看不见），
白名单忘登记 ⇒ 该组合所有可选正文参数一律被拒（fail-closed，噪音大但当场看得见）。

## 用法

    python 0-学习与工具/工具-opener生成.py --env CC \\
        --op-id OP-0905-A --short-name 示例任务 \\
        --branch demo-slug --worktree "☑（demo-wt，新 worktree，收工自删）" \\
        --workspace 无 --session 新开 --line 环境总线 \\
        --input-pointer "1-转型规划/0-全景路线图/示例派单件.md" --task-class A \\
        --do "第一步" --do "第二步" --dont "不做的事"

任一必填字段缺失／不合骨架硬规则 ⇒ 抛错退出（退出码 1），不打印半成品。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import string
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
#: 骨架正本（唯一可照抄物，2026-09-04 由模板库 §〇.00 拆出独立成件）。
SKELETON_FILE = REPO_ROOT / "1-转型规划" / "0-全景路线图" / "opener骨架.md"
#: `check_block` 判据实现的物理落点（复用，不第二次实现）。
LINT_SCRIPT = REPO_ROOT / "0-学习与工具" / "工具-opener块lint.py"

#: 子任务例外句——那一行的一部分，不得删、不得简写（骨架「三处最常丢的结构」表）。
SUBTASK_EXCEPTION = (
    "🔴 例外：你若是被 Task/Agent 起的子任务，跳过本行不要执行——子任务没有自己的 session，"
    '"self" 会解析到父 session、把调度你的那条会话改名（2026-08-28 实撞）。'
)

#: 「环境×变体」→ 该组合的成品**真的会拼进去**的可选正文参数（队列 §一 `#487` 子项／
#: `OP-0906-M`，Shao Peishen 2026-09-06 裁 (c) 甲＋精简版乙）。不在名单里的参数一旦
#: 传入即 **fail-loud 报错退出**，不静默丢弃。
#:
#: 🔴 **为什么是白名单而不是黑名单**：黑名单要求「每加一个变体就记得去登记它不支持什么」，
#: 忘了登记 ⇒ 回到静默丢弃（fail-open，看不见）。白名单忘了登记 ⇒ 该组合所有可选正文参数
#: 一律被拒（fail-closed，噪音大但当场看得见），下一个人两分钟就能补上。
#: **判据：一个参数被接受却不生效，比它被拒绝更危险。**
#:
#: 🔴 **本表登记的是「拼装函数的事实」，不是「骨架应该长什么样」**——改了
#: `generate_opener` 的任一 `body_lines` 分支，必须同步改这里，否则表本身就成了第二份
#: 会漂移的判据。当前事实（2026-09-06 逐行核过 `generate_opener`，含本批方案甲改动）：
#:   - CC/standard、CC/subtask_lane：拼 do_block ＋ dont_block ⇒ 两个都支持；
#:   - Cowork/standard：方案甲 2026-09-06 补段后同样拼 do_block ＋ dont_block ⇒ 两个都支持
#:     （🔴 **此前只拼 do_block，是本行实撞的那个洞；甲已让 `--dont` 生效，故本守卫
#:     对 Cowork 自动失效——不要再在这里拦 Cowork，会与甲互相打架**）；
#:   - CC/guardian：§三bis 看护者开场词固定四行 ＋ P4 口径，**do/dont 都不拼**，且不该补段
#:     （看护者的任务正本在看护件全文里）⇒ 唯一仍需 fail-loud 的组合。
BODY_PARAM_SUPPORT = {
    ("CC", "standard"): {"do_items", "dont_items"},
    ("CC", "subtask_lane"): {"do_items", "dont_items"},
    ("CC", "guardian"): set(),
    ("Cowork", "standard"): {"do_items", "dont_items"},
    # 队列 §一 `#489` 步骤 5：引用版正文**在派单件里**，本变体不拼任何正文段 ⇒
    # `--do`／`--dont` 传进来一律 fail-loud（同 guardian 的处置，理由见下方替代建议）。
    ("CC", "reference"): set(),
    ("Cowork", "reference"): set(),
}

#: 参数名 → CLI 旗标，用于报错信息里直接点名调用方敲的那个旗标。
_BODY_PARAM_FLAG = {"do_items": "--do", "dont_items": "--dont"}

#: `reference` 变体被拒时的替代承接建议（CC／Cowork 同文）。
_REFERENCE_ALTERNATIVE_TEXT = (
    "引用版（`--variant reference`）只出四行：标题行 ＋ `【设置】` 六字段 ＋ "
    "`set_session_title` 行（Cowork 无此行）＋ 一句「读 <派单件> 全文」。"
    "**正文（做什么／不做什么）在派单件里，不在开场词里**——这正是引用版存在的理由："
    "把 >500 字的正文从聊天里挪进可版本化、可 lint、可回溯的文件。"
    "要加做什么／不做什么请写进 `--ref-file` 指向的那份派单件；"
    "确需把正文写进开场词请改用 `--variant standard`。"
)

#: 各组合被拒时给的**替代承接建议**——只报错不给出路会让调用方改去写更糟的形态
#: （把硬约束塞进 `--do` 的某一条尾巴，读者当成待办而不是禁令）。
_BODY_PARAM_ALTERNATIVE = {
    ("CC", "guardian"): (
        "§三bis 看护者开场词是固定形态（四行 ＋ P4 扇出口径），正文不拼 `做什么／不做什么` "
        "——看护者的任务正本在**看护件全文**里，`--input-pointer` 已指向它。"
        "要给看护者加约束请改看护件，不要走本工具的正文参数。"
    ),
    ("CC", "reference"): _REFERENCE_ALTERNATIVE_TEXT,
    ("Cowork", "reference"): _REFERENCE_ALTERNATIVE_TEXT,
}

VALID_ENVS = ("CC", "Cowork")
VALID_TASK_CLASSES = ("A", "B")
#: 四种骨架变体（模块文档「variant」节）；`subtask_lane`／`guardian` 只对 CC 有意义，
#: `reference`（队列 §一 `#489` 步骤 5／`#284` 退休制阈值触发）CC 与 Cowork 皆可。
VALID_VARIANTS = ("standard", "subtask_lane", "guardian", "reference")

#: `reference` 变体：CC 与 Cowork 都成立（引用版就是「正文在派单件里」的那种形态，
#: 两桌都要用），故不受 `_validate_spec` 里「非 standard 只对 CC 有意义」那条约束。
ENV_AGNOSTIC_VARIANTS = frozenset({"standard", "reference"})

#: 队列 #461 明文列出的十个必填字段；任一缺失即报错退出、不出件。
REQUIRED_FIELDS = (
    "op_id", "env", "short_name", "branch", "worktree", "workspace",
    "session", "line", "input_pointer", "task_class",
)

OP_ID_RE = re.compile(r"^OP-\d{4}-[A-Za-z0-9]+$")
#: worktree 字段必须以勾选符号开头，不是裸名字（骨架「三处最常丢的结构」表第一条）。
CHECKBOX_RE = re.compile(r"^[☑☐]")
#: CC 侧分支短横线名（骨架 `<短横线名>` 占位符的字面约束）。
BRANCH_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
#: 🔴 **`--branch` 只收「前缀之后」那一截**（队列 §一 `#487` 2026-09-09 追记⑵）：
#: `_settings_line` 自己会拼 `claude/op{MMDD}{X}-`，调用方再把 OP 短号写进 slug
#: 就成了 `claude/op0909b-op0909b-docx-481`。**这条原本不是 bug 是用法**——但
#: `--help` 只写「短横线 slug」、没写「勿含 OP 短号」，按直觉传全名必踩，
#: 且成品是一个**看起来正常的分支名、不报错**，与本行既有子项同族（错得无声）。
#: 故按「拒含 `opNNNN[a-z]` 形态前缀的 slug」显式化。`\d{4}` 要四个真数字 ⇒
#: `opener-gen`／`ops-fix` 这类真实 slug 不会误伤。
BRANCH_SLUG_OP_PREFIX_RE = re.compile(r"^op\d{4}[a-z]?(?=-|$)")
#: 路径纪律：仓库根相对路径，不接受本机绝对路径（根 CLAUDE.md §5「路径写仓库根相对路径」）。
WINDOWS_ABS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")

# ── P7① 撞号查重（模块文档同节）────────────────────────────────────────────
#: 全称形态：`OP-0905-A`。捕获 `(mmdd, suffix)`。
USED_ID_FULL_RE = re.compile(r"OP-(\d{4})-([A-Za-z0-9]+)")
#: 短形形态：只认 `[Win]MMDDX-` 这个锚点（骨架「短形 MMDDX 只用于 session 名」），
#: 不做全文裸子串扫描——避免把正文里纯数字巧合误判为已用编号。
USED_ID_SHORT_RE = re.compile(r"\[Win\](\d{4})([A-Za-z0-9]+)-")

# ── 取号即声明（队列 §一 `#549` ⑶／`#531` 子项，2026-09-10）──────────────────
#: 占位台账：`<主工作区>/reports/op-id-claims.jsonl`，一行一条 JSON。🔴 **按
#: `git rev-parse --git-common-dir` 定位主工作区**（同 `工具-共享文档编辑锁.py`
#: `_resolve_repo_root` 手法）——Cowork 在主 checkout、CC 泳道各在自己的
#: worktree 里跑本工具，若按 `REPO_ROOT`（本文件所在 worktree）各算各的，就会
#: 写出 N 份互相看不见的台账，「不可见的占号台账等于没占」（`opener-id-claim-
#: semantics` design 对 `reports/` 变体的原话；`#504` 心跳件同坑）。
CLAIMS_FILE_REL = "reports/op-id-claims.jsonl"
#: 测试覆盖点：不为 `None` 时直接用它，不再走 git 解析（同 `REPO_ROOT` 的 monkeypatch 手法）。
CLAIMS_FILE: Path | None = None
#: 占位时效（分钟）。**Shao Peishen 2026-09-10 答 `1a` 定为 120 分钟**（追认建造方 `OP-0910-R`
#: 初值；措辞由 `OP-0910-S` 同日清掉「待答」）——依据＝根 `CLAUDE.md` §5 记的 `OP-0909-P`
#: 实证「派单件起草到复核 80 分钟」，取其 1.5 倍留余量；过短 ⇒ 起草期未结束
#: 号就被别人取走（等于没建）；过长 ⇒ 未派出的号挡别人两小时以上（当日 26 个
#: 字母不够用时才成问题，2026-09-10 实测当日用到 `R`）。改这个数只改这里。
CLAIM_TTL_MINUTES = 120
#: 台账写侧互斥锁的陈旧阈值／等待上限（秒）。写一次只有毫秒级，30 s 未释放即视为
#: 持锁进程已死；等 10 s 仍拿不到锁 ⇒ **fail-closed 不出件**（不能验证占位就不算取到号）。
CLAIMS_LOCK_STALE_SECONDS = 30
CLAIMS_LOCK_TIMEOUT_SECONDS = 10

#: P4 默认口径（构建环境瘦身第三轮方案 P4；队列 §一 `#487`）——生成子任务泳道／
#: 看护者开场词时无条件写入，不由调用方每次手打、防止漏写。
SUBTASK_PARALLEL_NOTE = "🔴 并行上限 4，超出排下一波，错峰 ≥90 秒（构建环境瘦身第三轮方案 P4）。"
SUBTASK_PUSH_NOTE = (
    "🔴 收工只 push 本泳道分支，不碰主仓、不 ff master——主仓 ff 由 sweep 收尾段"
    "或看护者收工时串行做（构建环境瘦身第三轮方案 P4）。"
)
#: 收工哨兵（队列 §一 `#550`，2026-09-10）——`工具-opener批处理执行v2.ps1` 判成败靠
#: `claude` 退出码 ＋ 顶格一行 `OPENER_DONE`／`OPENER_PARTIAL` 两个指标，缺哨兵即判
#: `NO-SENTINEL` 并中断本泳道。2026-09-10 四条泳道（`507`／`529`／`544`／`k2-externalize`）
#: **活全做了、无一 `OPENER_DONE`**——因为子任务泳道 opener 此前一个字没提哨兵。
#: 🔴 **修法必须落在这里（生成器强制注入），不能只改骨架文字**：`#487` 已证明「正文里写
#: 一句」拦不住，本次更前一步——不是没被遵守，是压根没生成。**一个把成功报成失败的判据
#: 比没有判据更糟，它会训练下一个人忽略 summary。** 机器守＝`工具-opener块lint.py` 形态⑨。
#: 🔴 与骨架【CC · 子任务泳道】块末行**逐字相同**（单测「骨架与生成器契约」比对）。
SUBTASK_SENTINEL_NOTE = (
    "🔴 收工以顶格一行 `OPENER_DONE` 收尾；命中 🟡/🔴 决策点则以 "
    "`OPENER_PARTIAL: 停在<档位>决策点——<在等什么>` 收尾"
    "（`工具-opener批处理执行v2.ps1` 判成败双指标之一，缺它做完的活也会被判 NO-SENTINEL；"
    "队列 §一 `#550`）。"
)
GUARDIAN_PARALLEL_NOTE = (
    "🔴 用 Task/Agent 起子任务时并行上限 4，超出排下一波，错峰 ≥90 秒；"
    "各子任务收工只 push 自己分支，不碰主仓、不 ff master（构建环境瘦身第三轮方案 P4）。"
)


def _scan_used_suffixes(mmdd: str) -> set[str]:
    """扫 `1-转型规划/` 全树 `.md`，收集当日（`mmdd`）已出现过的编号后缀（大写）。

    🔴 **射程自陈（openspec `opener-id-claim-semantics`「撞号查重须自陈其射程」；`#487` 裁定 ⑵）**：
    本查重只认**已落盘痕迹**——取号与落盘之间存在一段真空，查重是取号那一刻的快照、
    **不是锁**；未落盘的号按未占用处理（永久占用的唯一语义＝「已落进仓库某份 `.md`」，
    design ①(a)）。接力卡「⏳ 本线在跑会话」表在 `1-转型规划/` 树内，登进去的号**会**被
    本函数扫到、**会**挡号——这是可见性的副作用，design ②(a) 明知并接受，不跳过。
    真空期由 `_claim_op_id` 的**有时效机器占位**补（队列 §一 `#549` ⑶，2026-09-10 追加），
    不由本函数消除；占位到期未落档即作废。

    🔴 读 `REPO_ROOT` 走模块全局、不做默认参数——测试靠 monkeypatch
    `模块.REPO_ROOT` 指向临时夹具目录（同 `test_工具-泳道看护状态机.py`
    既定手法），默认参数会在定义时就把旧值绑死，测试改不动它。
    """
    used: set[str] = set()
    search_root = REPO_ROOT / "1-转型规划"
    if not search_root.is_dir():
        return used
    for path in search_root.rglob("*.md"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in USED_ID_FULL_RE.finditer(text):
            if m.group(1) == mmdd:
                used.add(m.group(2).upper())
        for m in USED_ID_SHORT_RE.finditer(text):
            if m.group(1) == mmdd:
                used.add(m.group(2).upper())
    return used


def _next_free_suffix(used: set[str]) -> str:
    """按字母表找下一个当日未用的单字母后缀；26 个用尽再兜底双字母（本项目至今
    未出现过单日超 26 个任务的极端情形，双字母只是不留死角，不特别优化）。"""
    for ch in string.ascii_uppercase:
        if ch not in used:
            return ch
    for c1 in string.ascii_uppercase:
        for c2 in string.ascii_uppercase:
            cand = c1 + c2
            if cand not in used:
                return cand
    raise OpenerGenError("当日编号后缀已耗尽（含双字母兜底），需人工介入")


def _check_op_id_not_reused(spec: "OpenerSpec") -> set[str]:
    """已落档撞号即拒；返回当日已落档后缀集合（供 `_claim_op_id` 复用，不扫第二遍）。"""
    mmdd, suffix = _mmdd_and_suffix(spec.op_id)
    used = _scan_used_suffixes(mmdd)
    if suffix.upper() in used:
        # 下一个空号同时避开未过期的占位（只读，不上锁）——推荐一个已被别人声明的号等于
        # 让调用方再撞一次。
        next_free = _next_free_suffix(used | _live_claimed_suffixes(mmdd))
        raise OpenerGenError(
            f"编号 {spec.op_id} 当日（{mmdd}）已被使用（撞号，队列 #461／#487 P7① 查重，"
            f"命中全称或 `[Win]{mmdd}{suffix}-` 短形；射程见 `_scan_used_suffixes` 文档字符串：只认已落档痕迹）；"
            f"下一个空号：OP-{mmdd}-{next_free}"
        )
    return used


class OpenerGenError(ValueError):
    """字段缺失或不合骨架硬规则 ⇒ 报错退出、不出件（队列 #461 明文要求）。"""


def _shared_repo_root() -> Path:
    """主工作区根（所有 worktree 共享）：`git rev-parse --git-common-dir` 的父目录；
    跑不了 git 时退回 `REPO_ROOT`（同 `工具-共享文档编辑锁.py::_resolve_repo_root`）。"""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=30,
        ).stdout.strip()
        if out:
            return Path(out).parent
    except (OSError, subprocess.SubprocessError):
        pass
    return REPO_ROOT


def _claims_file() -> Path:
    return CLAIMS_FILE if CLAIMS_FILE is not None else _shared_repo_root() / CLAIMS_FILE_REL


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _fmt_utc(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(text: str) -> datetime | None:
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


class _ClaimsLock:
    """台账写侧最小互斥（原子 `O_CREAT|O_EXCL` 建锁文件 ＋ 陈旧接管），只做互斥、
    不做内容校验——同 `工具-泳道看护状态机.py::_StateLock` 手法，不借队列的 markdown 行锁。"""

    def __init__(self, target: Path) -> None:
        self.path = target.with_name(target.name + ".lock")

    def __enter__(self) -> "_ClaimsLock":
        deadline = time.monotonic() + CLAIMS_LOCK_TIMEOUT_SECONDS
        self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode("ascii"))
                os.close(fd)
                return self
            except FileExistsError:
                try:
                    age = time.time() - self.path.stat().st_mtime
                except OSError:
                    age = 0.0
                if age > CLAIMS_LOCK_STALE_SECONDS:
                    try:
                        self.path.unlink()
                    except OSError:
                        pass
                    continue
                if time.monotonic() >= deadline:
                    raise OpenerGenError(
                        f"占位台账锁 {self.path} 等待超过 {CLAIMS_LOCK_TIMEOUT_SECONDS} s 仍被占用"
                        "⇒ 无法登记占位，按 fail-closed 不出件（队列 §一 `#549` ⑶）")
                time.sleep(0.1)

    def __exit__(self, *exc) -> None:
        try:
            self.path.unlink()
        except OSError:
            pass


def _load_claims(path: Path) -> list[dict]:
    """读台账；坏行跳过不崩（台账是本地高频小文件，坏一行不该让取号停摆）。"""
    if not path.is_file():
        return []
    claims: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and {"mmdd", "suffix", "claimed_at"} <= set(rec):
            claims.append(rec)
    return claims


def _write_claims(path: Path, claims: list[dict]) -> None:
    """整文件重写（先写临时件再 `os.replace`，不留半成品）。"""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in claims),
                   encoding="utf-8")
    os.replace(tmp, path)


def _claim_is_live(rec: dict, now: datetime) -> bool:
    claimed = _parse_utc(rec.get("claimed_at", ""))
    return claimed is not None and now - claimed < timedelta(minutes=CLAIM_TTL_MINUTES)


def _prune_claims(claims: list[dict], mmdd: str, used: set[str], now: datetime) -> list[dict]:
    """两条清理规则：⑴ 超时效的一律丢（不分日期）；⑵ 当日已落档（`used` 命中）的丢——
    落了档就由 `_scan_used_suffixes` 接管，占位只覆盖「取号→落档」那段真空。"""
    kept: list[dict] = []
    for rec in claims:
        if not _claim_is_live(rec, now):
            continue
        if rec.get("mmdd") == mmdd and str(rec.get("suffix", "")).upper() in used:
            continue
        kept.append(rec)
    return kept


def _same_draft(rec: dict, spec: "OpenerSpec") -> bool:
    """同一份草稿的重生成（改个参数再跑一次）不该撞自己的占位：判据＝短名相同。
    🔴 刻意不看 `line`——同一条线在同一时段起两份不同的件、却传了同一个号，
    正是要拦的形态（2026-09-10 `OP-0910-I` 撞号的一半就是这样来的）。"""
    return str(rec.get("short_name", "")) == spec.short_name


def _claim_op_id(spec: "OpenerSpec", used: set[str]) -> None:
    """取号即声明（队列 §一 `#549` ⑶）：核占位 → 写占位，同一把锁内完成。

    - 当日同号已被**别的草稿**声明且未过期 ⇒ 撞号，报错并给下一个空号（空号计算
      同时避开已落档与已声明的后缀）；
    - 同一草稿（短名相同）⇒ 刷新时间戳；
    - 台账读写任一步失败 ⇒ `OpenerGenError`（fail-closed：**不能证明占到号就不算取到号**，
      与「缺字段直接报错退出、不出半成品」同一条纪律）。
    """
    mmdd, suffix = _mmdd_and_suffix(spec.op_id)
    suffix = suffix.upper()
    now = _utc_now()
    path = _claims_file()
    try:
        with _ClaimsLock(path):
            claims = _prune_claims(_load_claims(path), mmdd, used, now)
            rivals = [c for c in claims
                      if c.get("mmdd") == mmdd and str(c.get("suffix", "")).upper() == suffix
                      and not _same_draft(c, spec)]
            if rivals:
                r = rivals[0]
                claimed_suffixes = {str(c.get("suffix", "")).upper()
                                    for c in claims if c.get("mmdd") == mmdd}
                next_free = _next_free_suffix(used | claimed_suffixes)
                raise OpenerGenError(
                    f"编号 {spec.op_id} 当日（{mmdd}）已被另一份起草中的件声明占用"
                    f"（短名「{r.get('short_name', '?')}」／派出线「{r.get('line', '?')}」，"
                    f"声明于 {r.get('claimed_at', '?')} UTC，时效 {CLAIM_TTL_MINUTES} 分钟；"
                    f"台账 {path}）——对方尚未落档、`_scan_used_suffixes` 看不见它，"
                    f"这正是占位存在的理由（队列 §一 `#549` ⑶／`#531` 子项，"
                    f"2026-09-10 `OP-0910-I`／`OP-0910-J` 两次实撞）；下一个空号：OP-{mmdd}-{next_free}"
                )
            claims = [c for c in claims
                      if not (c.get("mmdd") == mmdd and str(c.get("suffix", "")).upper() == suffix)]
            claims.append({
                "op_id": spec.op_id, "mmdd": mmdd, "suffix": suffix,
                "short_name": spec.short_name, "line": spec.line, "env": spec.env,
                "claimed_at": _fmt_utc(now),
                "expires_at": _fmt_utc(now + timedelta(minutes=CLAIM_TTL_MINUTES)),
            })
            _write_claims(path, claims)
    except OpenerGenError:
        raise
    except OSError as exc:
        raise OpenerGenError(
            f"占位台账 {path} 读写失败（{exc}）⇒ 无法证明占到号，按 fail-closed 不出件"
            "（队列 §一 `#549` ⑶）") from exc

def _live_claimed_suffixes(mmdd: str) -> set[str]:
    """当日未过期占位的后缀集合（只读、不上锁、不清理；供推荐空号用）。"""
    now = _utc_now()
    try:
        claims = _load_claims(_claims_file())
    except OSError:
        return set()
    return {str(c.get("suffix", "")).upper() for c in claims
            if c.get("mmdd") == mmdd and _claim_is_live(c, now)}


def _load_lint_module():
    """复用 `工具-opener块lint.py` 的 `check_block`／`iter_fenced_blocks`，不写第二份判据。"""
    spec = importlib.util.spec_from_file_location("_zp_opener_lint_reuse", LINT_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 opener 块判据实现：{LINT_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mmdd_and_suffix(op_id: str) -> tuple[str, str]:
    """`OP-0904-M` → `("0904", "M")`。"""
    _, mmdd, suffix = op_id.split("-", 2)
    return mmdd, suffix


#: 十项必填字段 ＋ 五项可选补充字段——`OpenerSpec.__init__` 的关键字参数名单一可信源。
_OPENER_SPEC_FIELDS = REQUIRED_FIELDS + (
    "claude_section", "do_items", "dont_items", "title_call_override", "variant",
)


class OpenerSpec:
    """字段容器（**不用 `@dataclass`**：本模块经 `importlib.util.module_from_spec` 跨文件
    加载时不会注册进 `sys.modules`，而 Python 3.14 的 dataclass 处理需要
    `sys.modules[cls.__module__]` 可解析——两者组合会在 import 时直接抛
    `AttributeError`，手写 `__init__` 绕开这条依赖，不是风格选择）。
    """

    __slots__ = _OPENER_SPEC_FIELDS

    def __init__(
        self, *, op_id: str, env: str, short_name: str, branch: str, worktree: str,
        workspace: str, session: str, line: str, input_pointer: str, task_class: str,
        claude_section: str = "", do_items: list[str] | None = None,
        dont_items: list[str] | None = None, title_call_override: str | None = None,
        variant: str = "standard",
    ) -> None:
        self.op_id, self.env, self.short_name = op_id, env, short_name
        self.branch, self.worktree, self.workspace = branch, worktree, workspace
        self.session, self.line, self.input_pointer, self.task_class = (
            session, line, input_pointer, task_class)
        self.claude_section = claude_section
        self.do_items = list(do_items) if do_items else ["…"]
        self.dont_items = list(dont_items) if dont_items else ["…"]
        self.title_call_override = title_call_override
        self.variant = variant


def _require_all_fields(values: dict) -> None:
    missing = [f for f in REQUIRED_FIELDS if not str(values.get(f, "")).strip()]
    if missing:
        raise OpenerGenError(
            f"缺失必填字段：{'、'.join(missing)}"
            "（编号／执行环境／短名／分支／worktree情形／工作区情形／session／派出线／"
            "输入指针／A或B类，十项任一不能省，队列 #461 明文要求）"
        )


def _validate_spec(spec: OpenerSpec) -> None:
    if spec.env not in VALID_ENVS:
        raise OpenerGenError(f"执行环境须为 CC 或 Cowork，收到：{spec.env!r}")
    if spec.variant not in VALID_VARIANTS:
        raise OpenerGenError(f"variant 须为 {VALID_VARIANTS} 之一，收到：{spec.variant!r}")
    if spec.variant not in ENV_AGNOSTIC_VARIANTS and spec.env != "CC":
        raise OpenerGenError(
            f"variant={spec.variant!r} 只对 CC 有意义（骨架【CC · 子任务泳道】／§三bis "
            f"均无 Cowork 对应形态），收到 env={spec.env!r}"
        )
    if spec.task_class not in VALID_TASK_CLASSES:
        raise OpenerGenError(f"A或B类须为 'A' 或 'B'，收到：{spec.task_class!r}")
    if not OP_ID_RE.match(spec.op_id):
        raise OpenerGenError(f"编号须匹配全称 `OP-MMDD-X` 形式（如 OP-0905-A），收到：{spec.op_id!r}")
    label_len = len(spec.short_name) + (2 if spec.variant == "guardian" else 0)
    if label_len > 12:
        raise OpenerGenError(
            f"短名须 ≤12 字（guardian 变体首行拼「看护」+短名，须一并 ≤12），"
            f"收到 {label_len} 字：{spec.short_name!r}"
        )
    if not CHECKBOX_RE.match(spec.worktree):
        raise OpenerGenError(
            "worktree 字段须以勾选符号 ☑／☐ 开头，不是裸名字"
            f"（骨架「三处最常丢的结构」表第一条），收到：{spec.worktree!r}"
        )
    if spec.session != "新开":
        raise OpenerGenError(
            f"session 字段骨架固定字面为「新开」（骨架未定义其他取值），收到：{spec.session!r}"
        )
    if spec.env == "Cowork" and spec.branch != "master":
        raise OpenerGenError(f"Cowork 侧分支固定为 master（骨架【Cowork】骨架），收到：{spec.branch!r}")
    if spec.env == "CC" and spec.variant != "guardian" and not BRANCH_SLUG_RE.match(spec.branch):
        # guardian 的分支字段是骨架 §三bis 固定字面量「master（看护者本身不建分支，
        # 不改代码）」，不是短横线 slug——调用方须整段传入，不受本条约束。
        raise OpenerGenError(
            "CC 侧分支须传短横线 slug（骨架 `<短横线名>` 占位符，如 'opener-gen'，"
            f"小写字母数字与连字符），收到：{spec.branch!r}"
        )
    if (spec.env == "CC" and spec.variant != "guardian"
            and BRANCH_SLUG_OP_PREFIX_RE.match(spec.branch)):
        # 队列 §一 `#487` 追记⑵：本工具自己会拼 `claude/opMMDDX-` 前缀，slug 里
        # 再带一次 ⇒ `claude/op1231r-op0909b-docx-481`，**不报错**、成品看着正常。
        mmdd, suffix = _mmdd_and_suffix(spec.op_id)
        stripped = BRANCH_SLUG_OP_PREFIX_RE.sub("", spec.branch).lstrip("-")
        raise OpenerGenError(
            f"`--branch` 只收 OP 短号**之后**那一截：本工具会自动拼上 "
            f"`claude/op{mmdd}{suffix.lower()}-`，slug 里再带一次 OP 短号会拼成 "
            f"`claude/op{mmdd}{suffix.lower()}-{spec.branch}`（前缀重复、且**不报错**，"
            f"成品是个看起来正常的分支名）。收到：{spec.branch!r}，"
            f"应传：{stripped!r}" + ("" if stripped else "（去掉短号后为空，请另起语义名）")
        )
    if WINDOWS_ABS_PATH_RE.match(spec.input_pointer):
        raise OpenerGenError(
            "输入指针须写仓库根相对路径，不接受本机绝对路径"
            f"（根 CLAUDE.md §5「路径写仓库根相对路径」），收到：{spec.input_pointer!r}"
        )


def _body_params_given(kwargs: dict) -> bool:
    """调用方**真的传了**任一正文参数（`--do`／`--dont`）？

    🔴 **只看 `kwargs`，不看 `spec`**——同 `_reject_silently_dropped_body_params`：
    `OpenerSpec.__init__` 会把 `None` 兜成 `["…"]` 占位，读 `spec` 分不出
    「没传」与「传了」，判据必须站在兜底之前。
    """
    return any(kwargs.get(k) for k in _BODY_PARAM_FLAG)


def _reject_silently_dropped_body_params(kwargs: dict, spec: OpenerSpec) -> None:
    """调用方传了「这个环境×变体根本不会拼进成品」的正文参数 ⇒ 报错退出（fail-loud）。

    🔴 **本函数解决的不是「参数写错了」，而是「参数写对了却没生效」**：
    2026-09-06 实撞——`--env Cowork --dont "<三条硬约束>"` 被静默丢弃，不报错、
    不出现在成品里，起草者以为约束传达到了（当次靠那三条本来也写在接力卡里侥幸兜住，
    属侥幸不属机制）。同族＝`acquire --domain` 漏传是「静默少算」而不是被拦下。

    🔴 **Cowork 已由方案甲让 `--dont` 真的生效，不由本函数拦**（两者同落会互相打架）；
    本函数落地后只剩 `--variant guardian` 一个洞在守——那个洞补段补不掉。

    🔴 **判「传没传」只看 `kwargs`，不看 `spec`**：`OpenerSpec.__init__` 会把
    `do_items`／`dont_items` 的 `None` 兜成 `["…"]` 占位，读 `spec` 分不出
    「没传」与「传了空」——判据必须站在兜底之前。
    """
    supported = BODY_PARAM_SUPPORT.get((spec.env, spec.variant))
    if supported is None:
        # 白名单没登记这个组合 ⇒ fail-closed（宁可全拒也不静默丢），见常量表注释。
        supported = set()
    passed = {k for k in _BODY_PARAM_FLAG if kwargs.get(k)}
    dropped = sorted(passed - supported, key=lambda k: _BODY_PARAM_FLAG[k])
    if not dropped:
        return
    flags = "、".join(f"`{_BODY_PARAM_FLAG[k]}`" for k in dropped)
    alt = _BODY_PARAM_ALTERNATIVE.get(
        (spec.env, spec.variant),
        "该组合的成品形态不含这些段，请改用 `--input-pointer` 指向的派单件承接。",
    )
    raise OpenerGenError(
        f"{flags} 传入了内容，但 env={spec.env}／variant={spec.variant} 的成品**不会包含**"
        f"它们——若不报错就会被静默丢弃（参数被接受却不生效，比被拒绝更危险；"
        f"2026-09-06 实撞一次，队列 §一 `#487` 子项／`OP-0906-M`）。{alt}"
    )


def _title_call_line(op_id: str, short_name: str) -> str:
    mmdd, suffix = _mmdd_and_suffix(op_id)
    return (
        f'开工第一件事：调 mcp__ccd_session_mgmt__set_session_title（session_id 传字面量 "self"），'
        f"标题：[Win]{mmdd}{suffix}-{short_name}。{SUBTASK_EXCEPTION}"
    )


def _title_call_line_guardian(op_id: str, short_name: str) -> str:
    """骨架 §三bis 看护者开场词的 `set_session_title` 行——它是本批唯一真正被
    粘贴进独立 CC 会话的一份，仍需要标题；措辞与标准句不同（强调"你自己不属于
    子任务跳过例外"），故不复用 `_title_call_line`。"""
    mmdd, suffix = _mmdd_and_suffix(op_id)
    return (
        f'开工第一件事：调 mcp__ccd_session_mgmt__set_session_title（session_id 传字面量 "self"），'
        f"标题：[Win]{mmdd}{suffix}-看护{short_name}。🔴 你是本批唯一真正被粘贴进独立 CC 会话的一份"
        "（其余泳道均由你用 Task/Agent 派发，正文里已不再放这一行——2026-09-05 队列 §一 `#487`／(甲)："
        "源头不放，不再指望子任务的文本例外句被真正遵守），本条对你适用，正常执行即可，"
        "标题设定后不要再被子任务顶掉，你自己不属于「跳过本行」的例外范围。"
    )


def _settings_line(spec: OpenerSpec) -> str:
    if spec.env == "CC":
        if spec.variant == "guardian":
            # 骨架 §三bis 固定字面量：看护者本身不建分支、不改代码——调用方
            # 须整段传入 `branch`（如 "master（看护者本身不建分支，不改代码）"），
            # 不套用标准变体「从 master 起 claude/opMMDDx-<slug>」的拼装模板。
            branch_field = spec.branch
        else:
            mmdd, suffix = _mmdd_and_suffix(spec.op_id)
            branch_field = f"master（从 master 起 `claude/op{mmdd}{suffix.lower()}-{spec.branch}`）"
    else:
        branch_field = "master"
    return (
        f"【设置】执行环境：{spec.env} ｜ 分支：{branch_field} ｜ worktree：{spec.worktree} ｜ "
        f"工作区：{spec.workspace} ｜ session：{spec.session} ｜ 派出线：{spec.line}"
    )


def _read_line(spec: OpenerSpec) -> str:
    section = f" §{spec.claude_section}" if spec.claude_section else ""
    if spec.env == "CC":
        clause = (
            "A 类（口径已定、判据已写死），无需再问澄清，直接开工"
            if spec.task_class == "A" else "B 类，开工前问我 2-3 个澄清"
        )
        return (
            f"读 ① `{spec.input_pointer}` → ② `CLAUDE.md`{section} 恢复上下文，"
            f"按下述执行。本件为 {clause}。"
        )
    return (
        f"读 ① `{spec.input_pointer}` → ② `CLAUDE.md`{section} 恢复上下文，"
        f"按下述执行。本件为 {spec.task_class} 类。"
    )


def generate_opener(**kwargs) -> str:
    """按十项必填字段拼出成品 opener 文本；缺字段或违反骨架硬规则 ⇒ 抛 `OpenerGenError`。"""
    _require_all_fields(kwargs)
    known = set(_OPENER_SPEC_FIELDS)
    spec = OpenerSpec(**{k: v for k, v in kwargs.items() if k in known})
    _validate_spec(spec)
    # 🔴 顺序刻意：先 `_validate_spec` 定下合法的 env／variant，本条判据才有意义；
    # 放在 `_check_op_id_not_reused` 之前——撞号查重要扫全树 `.md`（秒级），
    # 而「参数会被丢掉」是纯本地判断，没理由让调用方先等一次全树扫描才被告知。
    _reject_silently_dropped_body_params(kwargs, spec)
    used = _check_op_id_not_reused(spec)  # P7①：当日已落档撞号即拒，见模块文档

    do_block = "\n".join(f"{i + 1}. {item}" for i, item in enumerate(spec.do_items))
    dont_block = "\n".join(f"- {item}" for item in spec.dont_items)

    if spec.variant == "reference":
        # 队列 §一 `#489` 步骤 5（Shao Peishen 2026-09-08 答 1a，`#284` 退休制阈值
        # 触发，并入 `#461` 生成器）：**引用版**——只出四行，正文在派单件里。
        # 🔴 为什么要它：`#284` 那条「聊天里给他的开场词一律引用版、禁手抄」是**人守**，
        # 2026-09-08 已计到第三犯 ⇒ 退休制要求二选一（机制化或删除）。本变体就是
        # 「机制化」那一半：手抄四行容易漏 `【设置】` 某一字段或写错标题占位符，
        # 而拼装＋`check_block` 自检不会漏。
        body_lines = [f"[{spec.op_id}]【{spec.env}】{spec.short_name}", _settings_line(spec)]
        if spec.env == "CC":
            # 🔴 Cowork 侧不放这一行：`set_session_title` 在 Cowork 桌根本不存在
            # （2026-08-27 补充一实测），放了就是教人写一个不存在的工具调用。
            body_lines.append(
                spec.title_call_override if spec.title_call_override is not None
                else _title_call_line(spec.op_id, spec.short_name))
        section = f" §{spec.claude_section}" if spec.claude_section else ""
        body_lines.append(
            f"读 `{spec.input_pointer}` 全文＋ `CLAUDE.md`{section} 恢复上下文，"
            f"按该件执行。本件为 {spec.task_class} 类。")
    elif spec.variant == "guardian":
        title_line = f"[{spec.op_id}]【{spec.env}】看护{spec.short_name}"
        title_call = spec.title_call_override if spec.title_call_override is not None \
            else _title_call_line_guardian(spec.op_id, spec.short_name)
        body_lines = [
            title_line,
            _settings_line(spec),
            title_call,
            f"读 `{spec.input_pointer}` 全文＋ `CLAUDE.md` 恢复上下文。",
            "",
            "你是本批的**看护者**，不是执行者。用 Task/Agent 工具为各条泳道各起一个子任务，"
            '`isolation: "worktree"`，把对应【CC · 子任务泳道】opener 的正文原样作为子任务 prompt。'
            "🔴 不要改写 opener 正文。",
            "",
            GUARDIAN_PARALLEL_NOTE,
        ]
    else:
        title_line = f"[{spec.op_id}]【{spec.env}】{spec.short_name}"
        if spec.env == "CC" and spec.variant == "standard":
            title_call = spec.title_call_override if spec.title_call_override is not None \
                else _title_call_line(spec.op_id, spec.short_name)
            body_lines = [
                title_line,
                _settings_line(spec),
                title_call,
                _read_line(spec),
                "",
                "做什么：",
                do_block,
                "",
                "不做什么：",
                dont_block,
            ]
        elif spec.env == "CC" and spec.variant == "subtask_lane":
            # 骨架【CC · 子任务泳道】变体：不放 set_session_title 行（源头不放，
            # 见模块文档「variant」节），收尾无条件追加 P4 两条默认口径。
            # 🔴 **正文两段只在调用方真的传了 `--do`／`--dont` 时才拼**
            #（队列 §一 `#487` 2026-09-09 apply）：骨架该节明写「恒为三行，不多写
            # 一行」——做什么／不做什么／收工一律写进队列行。无条件硬塞占位
            # 等于把「没填的模板」当成品发出去，是既有子项的镜像形态。
            body_lines = [
                title_line,
                _settings_line(spec),
                _read_line(spec),
            ]
            if _body_params_given(kwargs):
                body_lines += ["", "做什么：", do_block, "", "不做什么：", dont_block]
            # 🔴 队列 §一 `#550`：收工哨兵**由生成器注入**、不依赖起草人记得写（见常量注释）。
            body_lines += [SUBTASK_PARALLEL_NOTE, SUBTASK_PUSH_NOTE, SUBTASK_SENTINEL_NOTE]
        else:
            body_lines = [
                title_line,
                _settings_line(spec),
                _read_line(spec),
                "",
                "做什么：",
                do_block,
                "",
                # 🔴 2026-09-06 补（队列 §一 `#487` 子项／`OP-0906-I`）：此前 Cowork 分支
                # 不拼「不做什么」段，`--dont` 传进来被**静默丢弃**——不报错、不出现在
                # 成品里，起草者以为约束传达到了（2026-09-06 实撞一次）。骨架
                # 【Cowork】节已同步补段，`工具-opener块lint.py` 形态⑦机器守。
                "不做什么：",
                dont_block,
                "",
                "收工：产出登记 §二 待 commit 批次（走 `0-学习与工具/工具-共享文档编辑锁.py`，"
                "勿裸改、勿自行 commit），由落库 sweep 取活。",
            ]

    opener_block = "```\n" + "\n".join(body_lines) + "\n```"

    # 自校验：复用既有 `check_block` 判据，产出必须自己先过自己定的门（模板库 §〇.0 同款约束）。
    # `is_subtask_lane`：subtask_lane 变体天生不含 set_session_title，须告知 lint
    # 这是形态⑥要求的那类块，否则会被形态①误判为"CC opener 缺 set_session_title"。
    lint = _load_lint_module()
    blocks = lint.iter_fenced_blocks(opener_block)
    if not blocks:
        raise OpenerGenError("生成物未能被识别为围栏代码块（内部拼装错误）")
    problems = lint.check_block(blocks[0], is_subtask_lane=(spec.variant == "subtask_lane"))
    if problems:
        detail = "；".join(f"[{code}] {msg}" for code, msg in problems)
        raise OpenerGenError(f"生成物未通过 `工具-opener块lint.py::check_block` 自检：{detail}")

    # 取号即声明（队列 §一 `#549` ⑶）：自检通过、确定要出件了才写占位——同一把锁内
    # 先核别人的占位再写自己的；撞上未落档的对方即在这里拒绝，出件＝占位已落。
    _claim_op_id(spec, used)

    return opener_block


def _build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="opener 生成器（队列 #461）：按 opener骨架.md 唯一格式来源拼出成品 opener。"
    )
    ap.add_argument("--op-id", required=True, help="全称编号，如 OP-0905-A")
    ap.add_argument("--env", required=True, choices=VALID_ENVS, help="执行环境")
    ap.add_argument("--short-name", required=True, help="短名，≤12 字")
    ap.add_argument("--branch", required=True,
                    help="CC：短横线 slug（如 opener-gen）——🔴 只传 OP 短号**之后**那一截，"
                         "本工具会自动拼 `claude/opMMDDX-` 前缀，slug 里勿再含 "
                         "`opNNNN[a-z]` 形态的 OP 短号（传 `op0909b-docx-481` 会拼成 "
                         "`claude/op0909b-op0909b-docx-481`，现已 fail-loud 拒绝）；"
                         "Cowork：固定传 master")
    ap.add_argument("--worktree", required=True, help="worktree 情形，须以 ☑／☐ 开头")
    ap.add_argument("--workspace", required=True, help="工作区情形（§〇.1 四种填法之一或「无」）")
    ap.add_argument("--session", required=True, help="骨架固定为「新开」")
    ap.add_argument("--line", required=True, help="派出线名")
    # 🔴 `--input-pointer` 由 argparse 必填改为**解析后校验**（队列 §一 `#489` 步骤 5）：
    # `--variant reference` 用 `--ref-file` 提供同一个指针，两个旗标都必填会逼调用方
    # 把同一条路径敲两遍——**同一事实两处来源，迟早对不上**。缺失仍然 fail-loud，
    # 只是报错点从 argparse 移到 `_resolve_input_pointer`，措辞更具体。
    ap.add_argument("--input-pointer", default=None, help="首要输入的仓库根相对路径"
                                                         "（`--variant reference` 请改用 --ref-file）")
    ap.add_argument("--ref-file", default=None,
                    help="引用版专用：派单件的仓库根相对路径（`--variant reference` 必填）")
    ap.add_argument("--task-class", required=True, choices=VALID_TASK_CLASSES, help="A 或 B 类")
    ap.add_argument("--claude-section", default="", help="CLAUDE.md 相关节号（可选）")
    ap.add_argument("--do", dest="do_items", action="append", default=None, help="做什么条目，可重复")
    ap.add_argument("--dont", dest="dont_items", action="append", default=None, help="不做什么条目，可重复")
    ap.add_argument("--variant", default="standard", choices=VALID_VARIANTS,
                    help="骨架变体：standard（默认）／subtask_lane（子任务泳道）／guardian（§三bis 看护者开场词）")
    return ap


def _resolve_input_pointer(args) -> str:
    """定下 `input_pointer` 的唯一来源，并对两个旗标的误用 fail-loud（`#489` 步骤 5）。

    四条判据，每条都宁可报错也不猜：
      ① `reference` 缺 `--ref-file` ⇒ 报错（引用版的全部意义就是指向那份件）；
      ② `reference` 同时给了 `--input-pointer` 且**与 `--ref-file` 不一致** ⇒ 报错
         （同一事实两处来源、且已经对不上，猜哪个都是错）；一致则放行，不为难调用方；
      ③ 非 `reference` 却给了 `--ref-file` ⇒ 报错（参数被接受却不生效＝静默丢弃同族，
         正是 `#487` 子项付过学费的形态）；
      ④ 非 `reference` 缺 `--input-pointer` ⇒ 报错（原 argparse `required=True` 的等价物）。
    """
    if args.variant == "reference":
        if not args.ref_file:
            raise OpenerGenError(
                "`--variant reference` 必须给 `--ref-file <派单件仓库根相对路径>`"
                "——引用版四行里那句「读 <派单件> 全文」就是它的正文，缺了它这份开场词"
                "什么也没说（队列 §一 `#489` 步骤 5）。")
        if args.input_pointer and args.input_pointer != args.ref_file:
            raise OpenerGenError(
                "`--variant reference` 下 `--input-pointer` 与 `--ref-file` 同指一份件，"
                f"两者不得给出不同的值：--input-pointer={args.input_pointer!r} "
                f"vs --ref-file={args.ref_file!r}。只给 `--ref-file` 即可。")
        return args.ref_file
    if args.ref_file:
        raise OpenerGenError(
            f"`--ref-file` 只对 `--variant reference` 生效，当前 variant={args.variant!r} "
            "⇒ 它会被静默丢弃，故在此拒绝（参数被接受却不生效，比被拒绝更危险；"
            "队列 §一 `#487` 子项）。要指定输入请用 `--input-pointer`。")
    if not args.input_pointer:
        raise OpenerGenError("缺必填参数 `--input-pointer`（首要输入的仓库根相对路径）。")
    return args.input_pointer


def main(argv: list[str] | None = None) -> int:
    ap = _build_arg_parser()
    args = ap.parse_args(argv)
    try:
        args.input_pointer = _resolve_input_pointer(args)
    except OpenerGenError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    kwargs = {
        "op_id": args.op_id, "env": args.env, "short_name": args.short_name,
        "branch": args.branch, "worktree": args.worktree, "workspace": args.workspace,
        "session": args.session, "line": args.line, "input_pointer": args.input_pointer,
        "task_class": args.task_class, "claude_section": args.claude_section,
        "variant": args.variant,
    }
    if args.do_items:
        kwargs["do_items"] = args.do_items
    if args.dont_items:
        kwargs["dont_items"] = args.dont_items
    try:
        print(generate_opener(**kwargs))
    except OpenerGenError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
