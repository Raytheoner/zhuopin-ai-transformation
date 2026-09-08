"""opener 代码块 lint —— 一次收七个失效形态（队列 §一 `#284`／`#381`⑸ⓖ／`#487`，OP-0828-Y／OP-0904-A／OP-0905-C／OP-0906-I）。

本脚本是**规则退休制**（根 `CLAUDE.md` §5）欠下的对价：`专线opener模板库.md` §〇
补充三那条人守规则 **2026-08-27 一天被违反 17 次**，远超「人守违反 3 次即须机制化或
删除」的阈值；补充三之三又在 2026-08-28 撞出第二个形态。退休制要求二选一——机制化，
或删除。**本脚本就是「机制化」那一半。**

**2026-09-04 扩三形态（队列 §一 `#381`⑸ⓖ，Shao Peishen 原话「每天碰到几十次，必须
就地解决且根治」）**：判据正本自此改为 `1-转型规划/0-全景路线图/opener骨架.md`（唯一可照抄骨架；
2026-09-04 A2 由模板库 §〇.00 拆出独立成件，模板库 §〇 此后只留判据，§〇.00 仅存一句指针）。

## 七个形态（判据正本＝`1-转型规划/0-全景路线图/opener骨架.md`；判据说明＝`专线opener模板库.md` §〇.0／§〇.00）

| | 守什么 | 生效日 | 成因 |
|---|---|---|---|
| 形态① | **CC 侧** opener 块含 `【设置】` 而**无** `set_session_title` | 2026-08-26（补充一） | session 名丢编号，2026-08-27 一天欠 17 次 |
| 形态② | 块内**有** `set_session_title` 而**无**子任务例外句 | 2026-08-28（补充三之三） | Task/Agent 子任务执行它时 `"self"` 解析到**父** session，把调度它的那条会话改名；**调用成功、无报错** |
| 形态③ | **CC 侧**块有 `set_session_title` 调用，但标题值不匹配 `[Win]MMDDX-<短名>` | 2026-09-04（骨架件） | 标题格式三次改定才终稿（模板库 §〇.0），旧格式/漏填占位符不会报错 |
| 形态④ | `【设置】` 行六字段（`执行环境｜分支｜worktree｜工作区｜session｜派出线`）缺失或顺序错 | 2026-09-04（骨架件） | §〇.1 曾把六字段错写成「标准四字段」，字段顺序漂移无任何一层会报错 |
| 形态⑤ | opener 块**首行**不匹配 `[OP-MMDD-X]【CC／Cowork】<短名≤12字>` | 2026-09-04（骨架件） | 编号是跨会话世界唯一身份，首行缺编号时收工报告/队列回写/CC transcript 目录无法对齐 |
| 形态⑥ | **看护者用 Task/Agent 派发的子任务泳道 opener**（文件含 `## 三bis` 看护opener 小节、块出现在该节之前）**含** `set_session_title` 调用 | 2026-09-05（队列 §一 `#487`） | 形态②的「子任务例外句」是文本层面的自我约束，2026-08-28／2026-09-05 两次实撞证明**子 agent 不一定会照做**——判据升级为源头不放：这类块本就不该出现这一行 |
| 形态⑦ | opener 块有 `做什么：` 段标题独立行、却**无** `不做什么：` 段标题独立行 | 2026-09-06（队列 §一 `#487` 子项／`OP-0906-I`） | 【Cowork】骨架此前根本没有「不做什么」段，`工具-opener生成.py --env Cowork --dont "…"` 传进来的硬约束被**静默丢弃**（不报错、不出现在成品里，起草者以为传达到了；2026-09-06 实撞一次）——同族＝「参数被接受却不生效，比被拒绝更危险」 |

形态②③与「工具静默回退」同族：它没错，只是解析到了另一个对象 —— 没有任何一层会报错，
故只能靠结构检测拦，靠人读输出拦不住。

## 🔴 形态⑥ 与形态②的关系——「文本例外句」被证明不可靠，改为「源头不放」（2026-09-05）

形态②（子任务例外句）解决的是「块里已经有 `set_session_title`，那就必须带一句『你若是子任务
就跳过』」——但这句例外句能不能被子 agent **真的执行到**，是另一回事：2026-08-28 与
2026-09-05 各实撞一次，**两次例外句文本都完整合规**（形态②不报警），子 agent 仍然把
`set_session_title("self")` 执行了，"self" 解析到父 session、把看护者的标题顶掉。

Shao Peishen 2026-09-05 现场拍板 (甲)：**看护者用 Task/Agent 派发的泳道 opener 正文里，
从源头就不放这一行**——子任务从未被单独粘贴进独立 CC 会话，天生不需要也不该设自己的
session 标题；只有真正会被粘贴进一个新 CC 会话的 opener（§三bis 看护者自己的开场词，
或不用看护者模式、直接单条粘贴/无头派发的 §三 lane opener）才需要它。

**判据（结构锚，不猜语义）**：文件内出现 `## 三bis` 标题 ⇒ 该文件采用「CC 看护者单粘贴、
Task/Agent 内部扇出」模式；出现在该标题**之前**的围栏块（即 §三 各 `### A<N>` 泳道 opener）
一律不该含 `set_session_title`——含了就是形态⑥。`## 三bis` 标题**之后**的块（看护者自己的
开场词）不受形态⑥约束，仍按形态①②③走原判据（它才是真正被粘贴进新 CC 会话的那一份）。

🔴 **没有 `## 三bis` 小节的文件（如单泳道无头派发批次）不受形态⑥约束**——那类文件里每条
`### A<N>` opener 都会被 headless 执行器当独立 `claude -p` 会话拉起，是真正的顶层会话，
仍然需要 `set_session_title`，形态①②③原判据照常生效。

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

## 🔴 格式正本 `opener骨架.md` 自身：形态①②③⑤ 换判据（队列 §一 `#493`，2026-09-07）

**立项形态＝判据把自己的格式正本判成违规**（2026-09-06 15:53 UTC 主仓实跑坐实，
`OP-0906-AA`）：骨架件一旦处于脏改动中，release 侧 opener 守卫就拿 `check_block` 去判
它，它自己的占位符（`MMDDX`／`[OP-MMDD-X]`）当场命中 8 处 ⇒ release 被拒、锁保持占用。
**这就是 `#398` ⑺「sweep 自撞锁」当天四轮的触发源**；且它**间歇性**——只在骨架件脏着
时发作，这正是它此前没被定位到的原因。同族＝「恒真判据」「守卫自己瞎了」那一族。

**处置不是关掉，是换判据**（`#493` 期望产出原文：不得靠把守卫关掉了事）：

| 在正本内 | 处置 | 换成什么 |
|---|---|---|
| 形态①②③⑤（**占位符敏感**：问的都是「占位符填对了没有」） | 不判 | `check_canon_file` 的 `C1`/`C2` ＋ `check_block` 的 `C3`/`C5` |
| 形态④⑥⑦（与占位符无关） | **照常生效** | —— |

**⇒ 修好后它在什么情况下发信号（四条，全部有单测钉死）**：

- `C1` —— 正本里再没有任何一个带 `set_session_title` 的【CC】块 ⇒ 它不再教形态①，
  此后每个照抄者都会漏写那一行（而形态①只在成品上一个一个报，报不到源头）；
- `C2` —— 正本里再没有任何一句子任务例外句 ⇒ 它不再教形态②；
- `C3` —— 正本的标题占位符不再是 `[Win]MMDDX-…`（被填成了某个具体值，或写法漂了）；
- `C5` —— 正本的首行占位符不再是 `[OP-MMDD-X]【CC／Cowork】…`；
- 外加形态④⑥⑦ 照常：六字段顺序坏了／子任务泳道块混进 title／有「做什么」缺「不做什么」。

🔴 **排除是按路径判的，且刻意不做 basename 匹配**（`is_format_canon`）——归档目录里另有
同名历史副本，basename 匹配会把它们一并静默排除。🔴 **排除不外溢**：同一段占位符文本换
一个路径（任何普通派单件／看护件）照样命中 F3/F5 ——「照抄骨架却漏填占位符」正是形态③
建来要抓的东西，把它一起放掉就等于白建。

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
    python 0-学习与工具/工具-opener块lint.py --file <路径>       # 单文件自检模式（见下）

**`--enforce` 只对「当前在用件」阻断**；历史件恒不阻断（「历史记录不追改」）。

**`--file <路径>` 单文件自检模式（2026-09-04 新增，队列 §一 `#381`⑸ⓖ）**：供任何 session
在把 opener 块粘进聊天交付前，先写进一份临时 `.md`、跑本模式自检。与主扫描路径的三处区别：
① **不跑 git、不判「当前在用 vs 历史」**——自检对象通常是尚未提交甚至未跟踪的草稿，套用
H1-H3 三层判据没有意义，全部命中一律按「当前」处理；② **不受 `--enforce` 支配**——自检的
存在意义就是「过不了就别发」，故有命中恒以退出码 1 收尾，干净则 0；③ **只读一份文件**，
不跑 `git ls-files`，可在非 git 目录、未跟踪文件上使用。
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

#: `工具-文档台账生成.py::parse_frontmatter` 的惰性缓存（`_frontmatter_of` 用）。
#: 🔴 缓存的是**解析器函数**、不是解析结果——每份件的 frontmatter 仍逐份现读。
_FRONTMATTER_PARSER = None

# ── 各条规则各自的生效日（H3 的时间边界）──────────────────────────────────────
#: 形态① ＝ 模板库 §〇「补充一」第 2 条（Shao Peishen 2026-08-26 定）。
RULE_EFFECTIVE_FORM1 = date(2026, 8, 26)
#: 形态② ＝ 模板库 §〇「补充三之三」（2026-08-28 实撞后当日定）。
RULE_EFFECTIVE_FORM2 = date(2026, 8, 28)
#: 形态③④⑤ ＝ 模板库 §〇.00（队列 §一 #381⑸ⓖ，2026-09-04 追加）。
RULE_EFFECTIVE_FORM3 = date(2026, 9, 4)
RULE_EFFECTIVE_FORM4 = date(2026, 9, 4)
RULE_EFFECTIVE_FORM5 = date(2026, 9, 4)
#: 形态⑥ ＝ 队列 §一 `#487`（Shao Peishen 2026-09-05 现场拍板 (甲)）。
RULE_EFFECTIVE_FORM6 = date(2026, 9, 5)
#: 形态⑦ ＝ 队列 §一 `#487` 子项（`OP-0906-I`，2026-09-06「`--dont` 静默丢弃」实撞后定）。
RULE_EFFECTIVE_FORM7 = date(2026, 9, 6)
#: 正本自检 C1/C2/C3/C5 ＝ 队列 §一 `#493`（2026-09-07，形态①②③⑤ 在格式正本内的换判据版）。
RULE_EFFECTIVE_CANON = date(2026, 9, 7)
#: 正本角色声明自检 C0 ＝ 队列 §一 `#489` ⑴（2026-09-08，路径名单改自声明式判据时的防外溢条）。
RULE_EFFECTIVE_CANON_CLAIM = date(2026, 9, 8)

#: 各形态代码 → 生效日，`classify_carrier` 按此查表（替代此前的二选一分支）。
RULE_EFFECTIVE_BY_FORM = {
    "F1": RULE_EFFECTIVE_FORM1,
    "F2": RULE_EFFECTIVE_FORM2,
    "F3": RULE_EFFECTIVE_FORM3,
    "F4": RULE_EFFECTIVE_FORM4,
    "F5": RULE_EFFECTIVE_FORM5,
    "F6": RULE_EFFECTIVE_FORM6,
    "F7": RULE_EFFECTIVE_FORM7,
    "C0": RULE_EFFECTIVE_CANON_CLAIM,
    "C1": RULE_EFFECTIVE_CANON,
    "C2": RULE_EFFECTIVE_CANON,
    "C3": RULE_EFFECTIVE_CANON,
    "C5": RULE_EFFECTIVE_CANON,
}

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

#: 形态③：标题值须为 `[Win]MMDDX-<短名>`（真实日期数字，不是字面占位符 `MMDDX`）。
#: 🔴 `\d{4}` 要求四个真数字——照抄骨架却漏填占位符时，`MMDDX` 五个字母不会命中，
#: 这正是本判据要抓的形态（漏填与格式错都表现为「没有匹配」，无需区分）。
TITLE_VALUE_RE = re.compile(r"\[Win\]\d{4}[A-Za-z]+-\S")

#: 形态④：`【设置】` 六字段固定顺序（§〇.00，2026-09-02 `OP-0902-X` 勘误后终稿）。
#: 🔴 用子串定位＋位置比大小判序，不做完整解析——同 F2 的弱校验哲学：判不了「值对不对」，
#: 判「字段在不在、序对不对」已能拦住 §〇.1 曾把它错写成「标准四字段」这一族漂移。
SETTINGS_FIELD_ORDER = ("执行环境", "分支", "worktree", "工作区", "session", "派出线")

#: 形态⑤：opener 块首行 `[OP-MMDD-X]【CC／Cowork】<短名，≤12字>`。
FIRST_LINE_RE = re.compile(r"^\[OP-\d{4}-[A-Za-z]+\]【(CC|Cowork)】(.{1,12})$")

#: 形态⑥：标志「本文件采用 CC 看护者单粘贴、Task/Agent 内部扇出子任务」模式的小节标题。
#: 出现在该标题**之前**的围栏块＝ §三 各 `### A<N>` 泳道 opener（会被当子任务 prompt 用，
#: 不该含 `set_session_title`）；之后的块＝看护者自己的开场词（真正的顶层会话，仍需要它）。
WATCHER_SECTION_RE = re.compile(r"^##\s*三bis\b", re.MULTILINE)

#: 形态⑦：「做什么：」／「不做什么：」两个**段标题独立行**（队列 §一 `#487` 子项／`OP-0906-I`）。
#: 🔴 **必须行锚、且必须要求行尾无正文**——两条理由，都不是风格选择：
#:   ① 子串 `"做什么："` 天然出现在 `"不做什么："` 里面，裸 `in` 判据会把「已经写了
#:      不做什么段」误判成「写了做什么段」；行锚 `^` 让 `不做什么：` 那一行不命中 `DO`。
#:   ② 库里大量 opener 正文把「做什么：建造到底。」写成**一整行的散文**（非段标题），
#:      不要求行尾为空就会把这些块也拖进形态⑦——它们本来就没有分段结构，补一个
#:      「不做什么：」空段毫无意义。**判据只管「已经采用了分段写法的块」。**
#: 加粗星号允许（`**做什么：**`），与 `SETTINGS_LINE_RE` 同款容忍。
DO_SECTION_RE = re.compile(r"^\s*\*{0,2}做什么\*{0,2}\s*[：:]\s*\*{0,2}\s*$")
DONT_SECTION_RE = re.compile(r"^\s*\*{0,2}不做什么\*{0,2}\s*[：:]\s*\*{0,2}\s*$")

# ── 格式正本自身的结构性排除（队列 §一 `#493`，2026-09-07）────────────────────
#: 🔴 **判据把自己的格式正本判成违规** —— 2026-09-06 15:53 UTC 主仓实跑坐实
#: （`OP-0906-AA`）：只要本件处于脏改动中，release 侧 opener 守卫就拿 `check_block`
#: 去判它，它自己的占位符（`MMDDX`／`[OP-MMDD-X]`）当场命中 8 处，于是 release 被拒、
#: 锁保持占用 —— 这正是 `#398` ⑺「sweep 自撞锁」当天四轮的触发源。
#:
#: 🔴 **这不是豁免清单，是判据本身不覆盖**（同 `执行环境：Cowork` 那条收窄的性质）：
#: 本件不是一份 opener，它是**「opener 长什么样」的定义**。拿「成品该长什么样」去判
#: 「定义本身」，是把判据套用在它自己的来源上 —— 同族＝模块 docstring 里那句「本脚本
#: 与其单测都是 `.py`，天然不在扫描面内，不需要靠豁免躲开」：`.py` 白拿到的这层豁免，
#: `.md` 的格式正本拿不到，得显式给。
#:
#: 🔴 **给的是「换判据」，不是「关掉」**（队列 `#493` 期望产出原文：不得靠把守卫关掉
#: 了事）：形态①②③⑤ 在本件内换成下方 `check_canon_file` ／ `C3`/`C5` 四条**正本自检**
#: （见 `CANON_*` 常量与 `check_canon_file` 文档字符串），形态④⑥⑦ 与占位符无关、**照常
#: 生效**。⇒ 修好后它仍在下列情况下发信号：正本的占位符本身漂了、正本不再教
#: `set_session_title`、正本不再教子任务例外句、正本的六字段/不做什么段写坏了。
SKELETON_CANON_REL = "1-转型规划/0-全景路线图/opener骨架.md"

# ── 队列 §一 `#489` ⑴：判据正本的识别从「写死路径」改为「件自己声明角色」 ─────────
#
# 🔴 **为什么必须改**（`#489` 期望产出原文：**不得写死文件名清单**）：`#493` 只把
# `opener骨架.md` 一条路径挖了出去，`专线opener模板库.md` 没在名单里 ⇒ 它的 5 个填空
# 模板恒报 13 处（F3×3 ＋ F4×5 ＋ F5×5），每次触碰都被迫写一次 `opener豁免：`，
# **豁免用滥则守卫失效**。而按路径续加第二条、第三条，就是在建那份被明令禁止的清单。
#
# 🔴 **判据换成什么**：件在 frontmatter 里**自己声明**它是 opener 的定义物
# （`opener正本: 骨架` / `opener正本: 模板库`），而不是由 lint 侧维护一张名单。
# 这与「执行环境：Cowork ⇒ 结构性排除」同性质——**判据本身不覆盖**，判据面来自被判
# 对象自己的声明，不是来自判据方的例外表。
#
# 🔴 **声明不是免死金牌，是换一套义务**（同 `#493`「换判据、不是关掉」）：
#   - 声明后只让掉**占位符/版式敏感**的那几条（见 `CANON_SWAPPED_FORMS_*`）；
#   - 同时**换上** `C0`/`C1`/`C2`/`C3`/`C5` 正本自检——正本若不再教
#     `set_session_title`、不再教子任务例外句、占位符被填成具体值，照样报；
#   - `F6`（子任务泳道不放 title）／`F7`（不做什么段）**任何角色都照常生效**。
#
# 🔴 **防外溢：`C0` 把「随手加一行 frontmatter 就能躲开」这条路堵上**——正本/模板库
# 按定义是**多份范例的集合**（骨架 4 块、模板库 5 块），而一份成品 opener 件只有 1 块。
# 故声明了角色却只有 <2 个 opener 块 ⇒ **声明不成立、按普通件照判**，并报 `C0`。
# 这不是万无一失（照抄两块再加声明仍可绕），但它把「顺手绕开」变成「明知故犯的
# 三处改动」，且改动全部落在 diff 里可见——与本项目既有 `豁免：` 标记同一执行层级。
CANON_ROLE_KEY = "opener正本"
CANON_ROLE_SKELETON = "骨架"      # 格式唯一可照抄物 = `opener骨架.md`
CANON_ROLE_LIBRARY = "模板库"     # 填空模板集 = `专线opener模板库.md`
VALID_CANON_ROLES = (CANON_ROLE_SKELETON, CANON_ROLE_LIBRARY)

#: 声明角色所需的最少 opener 块数（`C0` 的阈值，见上）。
CANON_MIN_BLOCKS = 2

#: 在**格式正本（骨架）**内被「换成正本自检」而非「关掉」的四个形态。
#: 🔴 判据：**该形态问的是「占位符填对了没有」** ⇒ 对定义占位符的那份件无意义。
#: F4（六字段顺序）／F6／F7 与占位符无关，**不在此列、在骨架内照常生效**
#: （实测：这三条在骨架上本来就零命中）。
CANON_SWAPPED_FORMS = frozenset({"F1", "F2", "F3", "F5"})

#: 在**模板库**内被换掉的形态：F3（标题占位符）／F4（六字段）／F5（首行编号）。
#: 🔴 **与骨架不同的那一条是 F4，理由不是「模板库更宽松」，而是它压根不是格式来源**：
#: 根 `CLAUDE.md` §3 白纸黑字——「先 Read `opener骨架.md` 逐字套用……**不凭模板库
#: 重建**（模板库 §〇 是判据、不是格式）」。模板库的块是**「说什么」的内容草稿**，
#: 不是「长什么样」的版式范例；拿版式判据（F3/F4/F5）判内容草稿，与 `#493` 修掉的
#: 「拿成品判据判定义本身」是同一个类型错误。
#: 🔴 **F1/F2 反而在模板库内照常生效、刻意不换**：它俩问的是「这份模板还教不教
#: `set_session_title` 与子任务例外句」——那正是 2026-08-27 一天 17 次违反的源头，
#: 是模板库最该守住的东西（实测：模板库三个 CC 模板当前全部带这两样，零命中）。
CANON_SWAPPED_FORMS_LIBRARY = frozenset({"F3", "F4", "F5"})

#: 角色 → 该角色内被换掉的形态集合。
CANON_SWAPPED_BY_ROLE = {
    CANON_ROLE_SKELETON: CANON_SWAPPED_FORMS,
    CANON_ROLE_LIBRARY: CANON_SWAPPED_FORMS_LIBRARY,
}

#: 正本自检 C5：正本里 opener 块首行必须仍是**占位符原形** `[OP-MMDD-X]【CC／Cowork】…`。
#: 它漂了 ⇒ 所有照抄者的首行都会跟着漂，而 F5 只在成品上报、报不到源头。
CANON_FIRST_LINE_RE = re.compile(r"^\[OP-MMDD-X\]【(?:CC|Cowork)】.+$")

#: 正本自检 C3：正本里 `set_session_title` 的标题值必须仍是占位符原形 `[Win]MMDDX-…`。
CANON_TITLE_VALUE_RE = re.compile(r"\[Win\]MMDDX-\S")


#: 兜底路径专用：只在 frontmatter 块内认**本键这一行**。见 `_declared_role_raw`。
CANON_ROLE_LINE_RE = re.compile(
    r"^\s*" + re.escape(CANON_ROLE_KEY) + r"\s*[:：]\s*(.+?)\s*$", re.MULTILINE)


def _declared_role_raw(text: str) -> str:
    """取 frontmatter 里 `opener正本` 的**原始值**（未做合法性判定）。

    🔴 **两条路径，主路径复用权威解析器**：正常情况下走
    `工具-文档台账生成.py::parse_frontmatter`（与 H2 状态归桶同一份实现，不自造第二份）。

    🔴 **兜底路径只在权威解析器加载不上时启用，且只认本键一行**（`#489` ⑵ 同批修）：
    release 侧 opener 守卫此前**不依赖**台账脚本，改成声明式判据后凭空多出一条硬依赖
    ——实测 6 个 CLI 用例（最小临时仓库里没有台账脚本）当场以 `FileNotFoundError`
    **崩掉整个 release**。「判据多了一条依赖」不该把 release 从「拒绝」变成「崩溃」。
    🔴 **这不是那条被禁止的「回退成本地简化版」**：被禁的是 `status_bucket` 那种
    **判断**（六枚举＋同义词表，两处各自实现必然漂移）；这里读的是**我们自己新定义的
    一个字面量键**，值域就 `VALID_CANON_ROLES` 两个词，没有可漂移的判断成分。
    🔴 **兜底也不静默**：走了兜底就往 stderr 说一句（每进程只说一次），
    不让「判据换了个实现」这件事无声发生。
    """
    global _FRONTMATTER_PARSER
    if _FRONTMATTER_PARSER is None:
        try:
            _FRONTMATTER_PARSER = _load_status_bucket()[1]
        except Exception as exc:                      # noqa: BLE001 —— 见下方说明
            _FRONTMATTER_PARSER = _fallback_frontmatter_parser
            print(f"ℹ opener-lint：权威 frontmatter 解析器加载不上（{exc.__class__.__name__}），"
                  f"本进程改用只认 `{CANON_ROLE_KEY}` 一行的最小解析（队列 §一 `#489` ⑴）。",
                  file=sys.stderr, flush=True)
    return (_FRONTMATTER_PARSER(text).get(CANON_ROLE_KEY) or "").strip()


def _fallback_frontmatter_parser(text: str) -> dict[str, str]:
    """兜底解析：只在开头的 `---` 块内找 `opener正本:` 那一行，别的键一概不认。"""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    m = CANON_ROLE_LINE_RE.search(text[3:end])
    return {CANON_ROLE_KEY: m.group(1).strip().strip('"')} if m else {}


def declared_canon_role(text: str) -> str | None:
    """件在 frontmatter 里**自己声明**的 opener 正本角色；未声明或值非法返回 `None`。

    队列 §一 `#489` ⑴：这是「不得写死文件名清单」的落点——判据面由被判对象自己声明，
    lint 侧不维护名单。值必须是 `VALID_CANON_ROLES` 之一（写错 ⇒ 当作没声明，
    由 `check_canon_claim` 的 `C0` 报出来，**不静默当成已豁免**）。
    """
    raw = _declared_role_raw(text)
    return raw if raw in VALID_CANON_ROLES else None


def _opener_block_count(text: str) -> int:
    return sum(1 for b in iter_fenced_blocks(text) if settings_line(b) is not None)


def canon_role(text: str) -> str | None:
    """**生效**角色 ＝ 声明了合法角色 **且** 过了 `C0` 块数门槛；否则 `None`（照普通件判）。

    🔴 **fail-closed**：声明不成立时不是「宽进」而是「按普通件全判」——想靠加一行
    frontmatter 绕开 F3/F4/F5 的，什么也拿不到，还多一条 `C0` 告警。
    """
    role = declared_canon_role(text)
    if role is None:
        return None
    return role if _opener_block_count(text) >= CANON_MIN_BLOCKS else None


def check_canon_claim(text: str) -> list[tuple[str, str]]:
    """`C0`：角色声明本身立不立得住（队列 §一 `#489` ⑴ 防外溢条）。

    两种命中：① 声明了 `{key}` 但值不在 `{roles}` 里（typo ⇒ 本以为豁免了、其实没有，
    属「参数被接受却不生效」同族）；② 值合法但 opener 块数 < `{n}` ⇒ 这是一份成品件
    冒充正本，声明不予承认。
    """
    fm_raw = _declared_role_raw(text)
    if not fm_raw:
        return []
    if fm_raw not in VALID_CANON_ROLES:
        return [(
            "C0",
            f"frontmatter `{CANON_ROLE_KEY}: {fm_raw[:40]}` 不是合法角色"
            f"（只接受 {'／'.join(VALID_CANON_ROLES)}）⇒ **本次声明不生效、按普通件全判**。"
            "写错一个字就静默变成「以为豁免了其实没有」，同族＝参数被接受却不生效"
            "（队列 §一 `#489` ⑴）",
        )]
    n = _opener_block_count(text)
    if n < CANON_MIN_BLOCKS:
        return [(
            "C0",
            f"本件声明 `{CANON_ROLE_KEY}: {fm_raw}`，但只有 {n} 个 opener 块"
            f"（< {CANON_MIN_BLOCKS}）⇒ **声明不予承认、按普通件全判**。正本/模板库按定义是"
            "多份范例的集合；单块件＝成品 opener，不得靠加一行 frontmatter 绕开 F3/F4/F5"
            "（队列 §一 `#489` ⑴ 防外溢条）",
        )]
    return []


def is_format_canon(rel_path: str | Path) -> bool:
    """（保留兼容）该**路径**是否为格式正本 `opener骨架.md`。

    🔴 **判据主线已不走本函数**（队列 §一 `#489` ⑴ 起改为 `canon_role(text)` 的声明式
    判据，理由见 `CANON_ROLE_KEY` 上方大段注释）。本函数留着只为两件事：① 既有单测
    与外部调用点不因改判据而炸；② `#493` 那条「不做 basename 匹配」的实测结论仍然
    成立、值得留证——归档目录里另有同名历史副本，basename 匹配会把它们一并静默排除。
    """
    norm = str(rel_path).replace("\\", "/")
    return norm == SKELETON_CANON_REL or norm.endswith("/" + SKELETON_CANON_REL)


def check_canon_file(text: str, role: str | None = None) -> list[tuple[str, str]]:
    """正本/模板库的**文件级**自检（队列 §一 `#493`；`#489` ⑴ 起按角色分流）。

    这两条是「换判据」的另一半 —— 形态①②在骨架内被换掉之后，**谁来保证正本还在教
    这两件事**？答案就是这里：正本若哪天不再包含任何一个带 `set_session_title` 的
    【CC】块（C1）、或不再包含任何一句子任务例外句（C2），此后每一个照抄它的人都会
    漏写这两行，而 F1/F2 只能在成品上一个一个报、报不到源头。

    `role` 缺省 `None` ⇒ 沿用 `#489` 之前的口径（按骨架判），既有调用点行为不变。
    模板库角色同样跑这两条：它是 Shao Peishen 选模板的入口，**丢了这两样比骨架丢了
    更直接**（骨架还有人逐字读，模板库是照单抓药）。
    """
    problems: list[tuple[str, str]] = []
    label = SKELETON_CANON_REL if role != CANON_ROLE_LIBRARY else "opener 模板库"
    blocks = iter_fenced_blocks(text)
    candidates = [b for b in blocks
                  if settings_line(b) is not None or SESSION_TITLE_RE.search(b.text)]

    teaches_title = any(
        SESSION_TITLE_RE.search(b.text) and block_env(b) == "CC" for b in candidates)
    if not teaches_title:
        problems.append((
            "C1",
            f"格式正本 `{label}` 里已找不到任何一个带 `set_session_title` 的"
            "【CC】opener 块 ⇒ 正本不再教形态①，此后每个照抄者都会漏写那一行"
            "（队列 §一 `#493`；形态①在正本内已换成本条）",
        ))

    teaches_exception = any(
        SESSION_TITLE_RE.search(b.text)
        and SUBTASK_TOKEN_RE.search(b.text) and EXCEPTION_TOKEN_RE.search(b.text)
        for b in candidates)
    if not teaches_exception:
        problems.append((
            "C2",
            f"格式正本 `{label}` 里已找不到任何一句子任务例外句"
            "（`子任务/Task/Agent` ＋ `例外/跳过本行` 同现于同一个带 title 的块）"
            "⇒ 正本不再教形态②（队列 §一 `#493`；形态②在正本内已换成本条）",
        ))

    return problems


def _watcher_section_line(text: str) -> int | None:
    """返回文件内 `## 三bis` 看护 opener 小节标题所在行号（1-based）；未出现则 `None`。"""
    for i, line in enumerate(text.splitlines(), start=1):
        if re.match(r"^##\s*三bis\b", line):
            return i
    return None


def _is_subtask_lane_block(block: "Block", watcher_line: int | None) -> bool:
    """该块是否为「看护者用 Task/Agent 派发的子任务泳道 opener」（形态⑥的适用范围）。

    判据只看结构位置，不猜语义：文件含 `## 三bis` 小节 ＋ 该块出现在其之前。
    没有 `## 三bis` 小节的文件（如单泳道无头派发批次，每条 opener 都是真正的顶层
    `claude -p` 会话）一律返回 `False`，不受形态⑥约束。
    """
    if watcher_line is None:
        return False
    return block.start_line < watcher_line


def _settings_field_order_problems(line: str) -> tuple[list[str], list[str]]:
    """返回 `(缺失字段列表, 顺序颠倒的相邻字段对列表)`。

    判据：六个字段标签逐个在 `line` 内 `str.find`；缺失即记入第一项；
    对**找到的**字段按标签出现位置两两比较相邻对，位置颠倒即记入第二项
    （形如 `"worktree→分支"` 表示 `worktree` 出现在 `分支` 之前，与骨架顺序相反）。
    """
    positions: dict[str, int] = {}
    for field in SETTINGS_FIELD_ORDER:
        idx = line.find(field)
        if idx != -1:
            positions[field] = idx
    missing = [f for f in SETTINGS_FIELD_ORDER if f not in positions]
    found_in_order = [f for f in SETTINGS_FIELD_ORDER if f in positions]
    out_of_order = [
        f"{a}→{b}" for a, b in zip(found_in_order, found_in_order[1:])
        if positions[a] > positions[b]
    ]
    return missing, out_of_order

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


def check_block(block: Block, *, is_subtask_lane: bool = False,
                is_format_canon_file: bool = False,
                canon_role: str | None = None) -> list[tuple[str, str]]:
    """返回该块命中的 `(形态代码, 说明)` 列表。形态代码 ∈ {"F1".."F7", "C3", "C5"}。

    `is_subtask_lane`：该块是否为「看护者用 Task/Agent 派发的子任务泳道 opener」
    （见 `_is_subtask_lane_block`）。默认 `False`——不传时行为与形态⑥引入前完全一致，
    调用方（`scan`/`scan_single_file`）按文件结构算好后再传入。

    `is_format_canon_file`：该块是否位于 opener **格式正本** `opener骨架.md`（队列
    §一 `#493`）。默认 `False`——不传时行为与本项引入前完全一致。为 `True` 时形态
    ①②③⑤ 换成正本自检 `C3`/`C5`（＋文件级 `check_canon_file` 的 `C1`/`C2`），形态
    ④⑥⑦ 照常生效。**不是关掉，是换成对这份件成立的那条判据**，见 `SKELETON_CANON_REL`。
    """
    problems: list[tuple[str, str]] = []
    is_opener = settings_line(block) is not None
    has_title_call = bool(SESSION_TITLE_RE.search(block.text))
    env = block_env(block)

    # 队列 §一 `#489` ⑴：角色优先；`canon_role` 未传时回落到旧布尔参数（＝骨架角色），
    # 两个既有调用点与既有单测行为逐字不变。
    role = canon_role if canon_role is not None else (
        CANON_ROLE_SKELETON if is_format_canon_file else None)
    swapped = CANON_SWAPPED_BY_ROLE.get(role, frozenset())

    if role is not None:
        # 正本自检 C5：首行仍须是占位符原形（F5 的源头版）。
        # 🔴 **只对骨架角色成立**：模板库的块本来就不带首行编号（它不是版式来源，
        # 见 `CANON_SWAPPED_FORMS_LIBRARY`），对它要求「首行须是占位符原形」等于
        # 换个马甲把 F5 又装回去。
        if is_opener and role == CANON_ROLE_SKELETON:
            first_line = block.lines[0].strip() if block.lines else ""
            if not CANON_FIRST_LINE_RE.match(first_line):
                problems.append((
                    "C5",
                    f"格式正本块首行未匹配占位符原形 `[OP-MMDD-X]【CC／Cowork】…`"
                    f"（实为 `{first_line[:60]}`）⇒ 照抄者的首行会跟着漂，而形态⑤"
                    "只在成品上报、报不到源头（队列 §一 `#493`）",
                ))
        # 正本自检 C3：标题值仍须是占位符原形（F3 的源头版）。
        if has_title_call and not CANON_TITLE_VALUE_RE.search(block.text):
            problems.append((
                "C3",
                "格式正本块内 `set_session_title` 的标题值未匹配占位符原形 "
                "`[Win]MMDDX-<短名>` ⇒ 照抄者的标题会跟着漂，而形态③只在成品上报、"
                "报不到源头（队列 §一 `#493`）",
            ))

    # 形态① —— 只对 CC 侧 opener 块成立（Cowork 与未标环境结构性排除，见 docstring）；
    # 子任务泳道 opener 结构性排除在外——它本就不该有这一行，缺失不是问题（形态⑥的镜像）。
    if (is_opener and not has_title_call and env == "CC" and not is_subtask_lane
            and "F1" not in swapped):
        problems.append((
            "F1",
            "CC opener 块缺 `set_session_title` 那一行 ⇒ session 名会丢编号"
            "（模板库 §〇 补充一第 2 条／补充三；标题行以 `[…]` 开头不会自动变成 session 名）",
        ))

    # 形态⑥ —— 子任务泳道 opener 不该含 set_session_title（源头不放，见模块 docstring）：
    # 形态②的文本例外句被 2026-08-28／2026-09-05 两次实撞证明子 agent 不一定照做。
    if is_subtask_lane and has_title_call:
        problems.append((
            "F6",
            "子任务泳道 opener（看护者用 Task/Agent 派发）不应包含 `set_session_title` 调用——"
            '`"self"` 会解析到父 session、把看护者的标题顶掉（2026-08-28／2026-09-05 两次实撞，'
            "例外句文本不可靠，改为源头不放；队列 §一 `#487`）",
        ))

    # 形态② —— 只要块里出现了 set_session_title，就必须带子任务例外句
    if has_title_call and "F2" not in swapped:
        has_exception = bool(SUBTASK_TOKEN_RE.search(block.text)
                             and EXCEPTION_TOKEN_RE.search(block.text))
        if not has_exception:
            problems.append((
                "F2",
                "块内有 `set_session_title` 却无子任务例外句 ⇒ 被 Task/Agent 起的子任务执行它时，"
                '`"self"` 会解析到父 session、把调度它的那条会话改名（调用成功、无报错）'
                "（模板库 §〇 补充三之三）",
            ))

    # 形态③ —— CC 侧且真调用了 set_session_title 时，标题值须匹配 [Win]MMDDX-<短名>
    #（is_opener 未作为门槛：裸标准写法块同样受本形态约束，同 F2 既有先例）
    if (has_title_call and env == "CC" and "F3" not in swapped
            and not TITLE_VALUE_RE.search(block.text)):
        problems.append((
            "F3",
            "块内 `set_session_title` 的标题值未匹配 `[Win]MMDDX-<短名>`"
            "（骨架占位符 `MMDDX` 须替换为真实四位日期＋字母，未替换或格式错均命中；"
            "模板库 §〇.00）",
        ))

    # 形态④ —— 【设置】六字段缺失或顺序错（仅 opener 块适用，Cowork 同受约束）
    if is_opener and "F4" not in swapped:
        settings_text = settings_line(block) or ""
        missing, out_of_order = _settings_field_order_problems(settings_text)
        if missing or out_of_order:
            parts = []
            if missing:
                parts.append(f"缺字段 {'、'.join(missing)}")
            if out_of_order:
                parts.append(f"顺序颠倒 {'、'.join(out_of_order)}")
            problems.append((
                "F4",
                f"`【设置】` 六字段（{'｜'.join(SETTINGS_FIELD_ORDER)}）{'；'.join(parts)}"
                "（模板库 §〇.00；§〇.1 曾把六字段错写成「标准四字段」，此前无任何一层会报错）",
            ))

    # 形态⑤ —— opener 块首行须为 [OP-MMDD-X]【CC／Cowork】<短名，≤12字>
    if is_opener and "F5" not in swapped:
        first_line = block.lines[0].strip() if block.lines else ""
        if not FIRST_LINE_RE.match(first_line):
            problems.append((
                "F5",
                "opener 块首行未匹配 `[OP-MMDD-X]【CC／Cowork】<短名，≤12字>`"
                "（编号是跨会话世界唯一身份，缺它收工报告/队列回写/CC transcript 目录"
                "无法对齐；模板库 §〇.00）",
            ))

    # 形态⑦ —— 块有「做什么：」段却无「不做什么：」段（队列 §一 `#487` 子项／`OP-0906-I`）：
    # 【Cowork】骨架此前压根没有这一段，`工具-opener生成.py --env Cowork --dont "…"`
    # 传进来的硬约束被静默丢弃（不报错、不出现在成品里）。判据对 CC／Cowork 一视同仁，
    # 不做环境分流——CC 侧现存 28 个分段写法的块全部已带「不做什么」，零回归。
    if is_opener:
        has_do = any(DO_SECTION_RE.match(ln) for ln in block.lines)
        has_dont = any(DONT_SECTION_RE.match(ln) for ln in block.lines)
        if has_do and not has_dont:
            problems.append((
                "F7",
                "opener 块有「做什么：」段却无「不做什么：」段 ⇒ 硬约束无处可写，"
                "`工具-opener生成.py --dont` 传进来会被静默丢弃（参数被接受却不生效，"
                "比被拒绝更危险；2026-09-06 实撞一次，队列 §一 `#487` 子项）",
            ))

    return problems


# ── 当前在用 vs 历史 ─────────────────────────────────────────────────────────

def _last_commit_date(rel_path: str) -> date | None:
    """该文件最后一次提交的**提交时刻**（本地日期）；取不到返回 None（不静默当成很早）。"""
    try:
        out = subprocess.run(
            ["git", "-c", "core.quotepath=false", "log", "-1", "--format=%cI", "--", rel_path],
            cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
            timeout=GIT_TIMEOUT_SECONDS,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        # `SubprocessError` 覆盖 `CalledProcessError` 与 `TimeoutExpired`（`#489` ⑵：
        # 单个 git 卡死不许拖垮全量）。
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
    cutoff = RULE_EFFECTIVE_BY_FORM[form]
    if last_commit < cutoff:
        return "historical", f"H3 最后提交 {last_commit.isoformat()} 早于规则生效日 {cutoff.isoformat()}"
    return "current", f"三层均不命中（最后提交 {last_commit.isoformat()}）"


# ── 扫描 ────────────────────────────────────────────────────────────────────

#: 单次 git 子进程的墙钟上限（秒）。队列 §一 `#489` ⑵：**一个卡住的 git 调用
#: 不许把整轮全量拖死**——超时即当作「取不到」，该文件落 `unknown-history` 桶
#: （保守按「当前在用」计入并显式打印），不静默当成很早、也不中断全量。
GIT_TIMEOUT_SECONDS = 60


def _last_commit_dates_batch(rel_paths: list[str]) -> dict[str, date | None]:
    """一次 `git log` 走完全历史，取每个路径**最后一次提交**的日期。

    队列 §一 `#489` ⑵ 的主修：原实现对每个有命中的文件各跑一次
    `git log -1 --format=%cI -- <path>`，**每次都要走一遍历史**——本仓库实测
    115 个命中文件耗时 **151.8s（均值 1.32s/文件）**，而纯解析只要 19.4s，
    即 89% 的墙钟耗在这一处；文件再多就是线性恶化（`#489` 立行时记录的
    「22:05 起跑、07:24 进程消失、输出 0 字节」即此形态叠加缓冲导致）。

    改成**一次全历史 `--name-only` 扫描**：`git log` 默认 newest-first，
    故某路径**首次出现**的那个提交就是它最后一次被改动 ⇒ 同一遍历史拿到全部
    1613 个路径的日期。实测 **2.76s**（3001 个提交），且与逐文件口径
    **1613/1613 逐个比对完全一致**（校验脚本见 `#489` 收工汇总）。

    🔴 `--no-renames`：`git log -1 -- <path>` 不开 `--follow` 时同样不跟改名，
    两侧口径必须一致，否则会对改过名的件给出更早的日期、把它误判成历史件。
    🔴 取不到（git 不可用／超时／非仓库）返回**空字典**，调用方逐个回落到
    `_last_commit_date`——**不静默当成「都没有历史」**，那会把全库打成
    `unknown-history` 并全部按「当前在用」阻断。
    """
    if not rel_paths:
        return {}
    try:
        out = subprocess.run(
            ["git", "-c", "core.quotepath=false", "log", "--format=%x00%cI",
             "--name-only", "--no-renames"],
            cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
            check=True, timeout=GIT_TIMEOUT_SECONDS,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    wanted = set(rel_paths)
    result: dict[str, date | None] = {}
    current: date | None = None
    for line in out.splitlines():
        if line.startswith("\x00"):
            try:
                current = date.fromisoformat(line[1:11])
            except ValueError:
                current = None
            continue
        rel = line.strip()
        # 首次出现 ＝ 最新一次提交（newest-first），后续更早的提交不覆盖。
        if rel and current is not None and rel in wanted and rel not in result:
            result[rel] = current
    return result


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


def _progress(msg: str) -> None:
    """进度写 **stderr** 并立刻 flush（队列 §一 `#489` ⑵）。

    🔴 **为什么非要有这一行**：`#489` 立行时的实证是「起跑 22:05、07:24 进程消失，
    输出文件始终 0 字节」——**0 字节不等于挂死**，本工具此前把全部输出攒到最后一次
    性打印，`> out.txt` 期间那个文件本来就会是 0 字节。没有进度输出时，
    「跑得慢」与「卡死了」在观测上完全同形，只能靠猜。
    🔴 走 stderr 不走 stdout：`> out.txt` 只重定向 stdout，进度不会污染结果文件，
    同时在终端里仍看得见。
    """
    print(msg, file=sys.stderr, flush=True)


def scan(files: list[str]) -> tuple[list[Finding], dict[str, int]]:
    status_bucket, parse_frontmatter = _load_status_bucket()
    findings: list[Finding] = []
    stats = {"files": 0, "opener_blocks": 0, "cc": 0, "cowork": 0, "env_unknown": 0,
             "title_blocks": 0}

    # 队列 §一 `#489` ⑵：一次全历史取完所有 last-commit-date（实测 2.76s），
    # 取代此前「每个有命中的文件各跑一次 `git log -1`」（实测 1613 个文件 1057.3s）。
    # 🔴 批量取不到时 `commit_cache` 为空 ⇒ 下面 `_emit` 逐个回落到 `_last_commit_date`，
    # 行为与本项引入前逐字一致，**不是静默降级成「没有历史」**。
    _progress(f"[opener-lint] 取 {len(files)} 个 .md 的最后提交日期（一次全历史扫描）…")
    commit_cache: dict[str, date | None] = dict(_last_commit_dates_batch(files))
    _progress(f"[opener-lint] 已取到 {len(commit_cache)} 个；开始逐文件解析…")

    for idx, rel in enumerate(files, start=1):
        if idx % 200 == 0:
            _progress(f"[opener-lint] …{idx}/{len(files)}，累计命中 {len(findings)} 处")
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
        watcher_line = _watcher_section_line(text)
        # 队列 §一 `#489` ⑴：角色来自件自己的 frontmatter 声明，不是 lint 侧名单。
        role = canon_role(text)

        def _emit(line_no, form, detail, env):
            if rel not in commit_cache:
                commit_cache[rel] = _last_commit_date(rel)
            bucket, reason = classify_carrier(rel, status_raw, form, commit_cache[rel])
            findings.append(Finding(rel, line_no, form, detail, bucket, reason, env))

        # 队列 §一 `#489` ⑴：`C0` —— 角色声明本身立不立得住（防「加一行 frontmatter
        # 就能躲开 F3/F4/F5」）。🔴 声明不成立时 `role` 已是 `None`，下面照普通件全判。
        for form, detail in check_canon_claim(text):
            _emit(1, form, detail, None)

        # 队列 §一 `#493`：正本/模板库的文件级自检（C1/C2）——形态①②在骨架内被
        # 换掉之后，由这两条保证「它还在教这两件事」。**换判据，不是关掉。**
        if role is not None:
            for form, detail in check_canon_file(text, role):
                _emit(1, form, detail, None)

        for block in candidates:
            env = block_env(block)
            if settings_line(block) is not None:
                stats["opener_blocks"] += 1
                stats["cc" if env == "CC" else "cowork" if env == "Cowork" else "env_unknown"] += 1
            if SESSION_TITLE_RE.search(block.text):
                stats["title_blocks"] += 1

            is_subtask = _is_subtask_lane_block(block, watcher_line)
            for form, detail in check_block(block, is_subtask_lane=is_subtask,
                                            canon_role=role):
                _emit(block.start_line, form, detail, env)
    return findings, stats


def scan_single_file(path: Path) -> list[Finding]:
    """`--file` 单文件自检：不跑 git、不分「当前在用 vs 历史」，全部按「当前」处理。

    自检对象通常是尚未提交甚至未跟踪的草稿（供发出前自查），套用 H1-H3 三层判据
    没有意义——那三层问的是「规则生效后这份件有没有被人再动过」，对一份从未提交过
    的临时件天然无法回答，也不该回答（不是「历史记录」，谈不上「不追改」）。
    """
    text = path.read_text(encoding="utf-8")
    findings: list[Finding] = []
    watcher_line = _watcher_section_line(text)
    # 队列 §一 `#489` ⑴：与主扫描同一条声明式判据（`canon_role`），不按路径。
    # ⇒ 把骨架/模板库复制到任意临时路径做 `--file` 自检，结论与在库内一致。
    role = canon_role(text)
    for form, detail in check_canon_claim(text):
        findings.append(Finding(str(path), 1, form, detail,
                                "current", "--file 自检模式：不判历史", None))
    if role is not None:
        for form, detail in check_canon_file(text, role):
            findings.append(Finding(str(path), 1, form, detail,
                                    "current", "--file 自检模式：不判历史", None))
    for block in iter_fenced_blocks(text):
        if settings_line(block) is None and not SESSION_TITLE_RE.search(block.text):
            continue
        env = block_env(block)
        is_subtask = _is_subtask_lane_block(block, watcher_line)
        for form, detail in check_block(block, is_subtask_lane=is_subtask,
                                        canon_role=role):
            findings.append(Finding(str(path), block.start_line, form, detail,
                                    "current", "--file 自检模式：不判历史", env))
    return findings


FORM_TITLE = {
    "F1": "形态① · CC opener 块缺 set_session_title（规则生效日 2026-08-26）",
    "F2": "形态② · 有 set_session_title 缺子任务例外句（规则生效日 2026-08-28）",
    "F3": "形态③ · 标题值不匹配 [Win]MMDDX-<短名>（规则生效日 2026-09-04）",
    "F4": "形态④ · 【设置】六字段缺失或顺序错（规则生效日 2026-09-04）",
    "F5": "形态⑤ · 首行不匹配 [OP-MMDD-X]【CC／Cowork】<短名≤12字>（规则生效日 2026-09-04）",
    "F6": "形态⑥ · 子任务泳道 opener 含 set_session_title（规则生效日 2026-09-05）",
    "F7": "形态⑦ · 有「做什么：」段却缺「不做什么：」段（规则生效日 2026-09-06）",
    "C0": "正本自检C0 · opener正本 角色声明不成立（队列 #489，2026-09-08）",
    "C1": "正本自检C1 · 格式正本不再教 set_session_title（队列 #493，2026-09-07）",
    "C2": "正本自检C2 · 格式正本不再教子任务例外句（队列 #493，2026-09-07）",
    "C3": "正本自检C3 · 格式正本标题占位符 [Win]MMDDX- 漂了（队列 #493，2026-09-07）",
    "C5": "正本自检C5 · 格式正本首行占位符 [OP-MMDD-X] 漂了（队列 #493，2026-09-07）",
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="opener 代码块 lint（队列 #284／#381⑸ⓖ／#487，六个失效形态一处守）")
    ap.add_argument("--enforce", action="store_true",
                    help="当前在用件有违规即以退出码 1 阻断（默认只告警、退出码 0）")
    ap.add_argument("--show-historical", action="store_true",
                    help="连历史件命中一起列明细（默认只给计数，因其按「历史记录不追改」不该修）")
    ap.add_argument("--file", metavar="路径", type=Path, default=None,
                    help="单文件自检模式：只查这一份文件，不跑 git、不分当前/历史，"
                         "有命中恒退出码 1（不受 --enforce 支配）")
    args = ap.parse_args(argv)

    if args.file is not None:
        if not args.file.is_file():
            print(f"✗ --file 指向的路径不存在或不是文件：{args.file}")
            return 1
        findings = scan_single_file(args.file)
        if not findings:
            print(f"✓ {args.file}：opener 块自检零违规。")
            return 0
        print(f"✗ {args.file}：opener 块自检命中 {len(findings)} 处：")
        for f in findings:
            print(f"  - {f.render()}")
        print("\n标准写法见 `1-转型规划/0-全景路线图/专线opener模板库.md` §〇.00（唯一可照抄骨架）。")
        return 1

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

    # 🔴 **明细分组直接遍历 `FORM_TITLE`，不再手维护第二份形态清单**（队列 §一 `#489`
    # 顺带修，2026-09-08 实测发现）：此处原本写死 `("F1","F2","F6","F7","C1","C2","C3","C5")`
    # ——**漏了 F3/F4/F5**。后果是这三个形态的命中**计入「N 处待修【阻断】」却一行明细
    # 都不打印**：`--enforce` 说「36 处待修」，人照着输出去找，只找得到其中一部分，
    # 剩下的凭空消失。`#489` ⑵ 记的「验收命令拿不到结论」有本条的一份。
    # 同族＝本文件开头那句「连回显都没有时，无法区分『没问题』与『没跑』」——
    # 这里是它的变体：**回显有，但少了一截，而少的那截不会报错**。
    # ⇒ 根因是「同一份形态清单存在两处、只有一处会被新增形态改到」，故直接取消第二处。
    for form in FORM_TITLE:
        sel = [f for f in cur if f.form == form]
        if not sel:
            continue
        print(f"\n── 当前在用件 · {FORM_TITLE[form]}，{len(sel)} 处 ──")
        for f in sel:
            print(f"  - {f.render()}")

    # 兜底：形态代码没登记进 `FORM_TITLE` 时也必须打印，不许静默吞掉。
    leftover = [f for f in cur if f.form not in FORM_TITLE]
    if leftover:
        print(f"\n── 当前在用件 · 未登记标题的形态，{len(leftover)} 处"
              "（`FORM_TITLE` 缺条目，请补；此处兜底打印，不静默吞）──")
        for f in leftover:
            print(f"  - {f.render()}")

    if hist:
        print(f"\n── 历史件命中 {len(hist)} 处（F1 {sum(1 for f in hist if f.form == 'F1')} ／ "
              f"F2 {sum(1 for f in hist if f.form == 'F2')} ／ "
              f"F6 {sum(1 for f in hist if f.form == 'F6')} ／ "
              f"F7 {sum(1 for f in hist if f.form == 'F7')}）：**按「历史记录不追改」不修、不阻断** ──")
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
