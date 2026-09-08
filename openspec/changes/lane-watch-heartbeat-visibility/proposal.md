# lane-watch-heartbeat-visibility Proposal

> 归属：队列 §一 `#504`（2026-09-08 立行，Cowork 业务总线 `OP-0908-A`，立行依据＝Shao Peishen 当日答 **13a**）；本轮由批次 `B-0908_四泳道机制根治` 泳道 `504-heartbeat-vis`（派单件 `OP-0908-R`）起草。
> 类别：**机制/环境类变更包**（守护本仓库泳道看护工具自身），受 `openspec/config.yaml` 两条 MANDATORY 约束，见下文。
> 🔴 **本轮范围＝propose ＋ design 起草，不 apply**：`工具-泳道看护状态机.py`／`test_工具-泳道看护状态机.py`／`zhuopin-lane-watch/SKILL.md`／`lane-watch-mode` 的 design 与 spec，本轮**一行未动**——那是 design 审过之后 apply 阶段的事（`tasks.md` §2–§5）。
> ⚠️ **过渡期口径（本包落地前一律照此）**：看门狗 🐕 告警**继续**按现行人守处理——看到超时先核心跳文件 mtime，多半是误报，`resume` 撤销即可（`看护件-泳道看护批B-0908_四泳道机制根治-2026-09-08.md` 第 28 行原文）。不得因本包已起草就提前当作已修。

## Why（为什么做）

**一句话**：看门狗读心跳的位置（主 checkout）和泳道写心跳的位置（各自 worktree）**不是同一个地方**，于是它把**每一条健康泳道**都判成失联——本变更修的是这条读写口径不统一，**不是再加一层告警**（队列 `#504` 行内原文：「看门狗本身就是守」）。

### 成因：两个来源，同一个误判

**成因半 ⑴ · 读写不同锚（物理成因，已实测坐实）**

| | 现行行为 | 证据（本泳道现取，非推断） |
|---|---|---|
| **读侧** | `check_heartbeat()` 解析 `REPO_ROOT / heartbeat_file`；`REPO_ROOT` 复用 `工具-共享文档编辑锁.py::_resolve_repo_root()`，按 `git rev-parse --git-common-dir` 定位，**不论在主工作区还是任一 linked worktree 里跑都解到主 checkout** | 在本泳道 worktree（`C:\Dev\zhuopin-ai\.claude\worktrees\agent-a86aabc0d6b801f3b`）内按文件路径加载该模块，打印 `REPO_ROOT` ＝ `C:\Dev\zhuopin-ai`（主 checkout）——**读侧本身没有 `#488` 那种解析偏移，这一点先澄清，免得 apply 期修错地方** |
| **写侧** | **根本没有工具入口**。泳道写心跳靠的是 opener／看护件正文里的一句散文约定「心跳落 `reports/lane-heartbeat/<泳道>.md`」——**相对路径，由泳道自己的 CWD 解析** ⇒ Task/Agent `isolation: "worktree"` 起的泳道，CWD ＝它自己的 worktree | `git check-ignore -v reports/lane-heartbeat/504-heartbeat-vis.md` → `.gitignore:50:**/reports/`；该文件实存于本 worktree，主 checkout 无此文件 |

**成因半 ⑵ · 它是 v2.0 架构收敛带进来的回归，不是一直如此**

`zhuopin-lane-watch/SKILL.md` v2.0 步骤 4 把**默认起泳道方式**从 `工具-opener批处理执行v2.ps1`（无头 CC，CWD ＝主 checkout）改成了**看护者用 Task/Agent 扇出、`isolation: "worktree"`**——**心跳路径的那句散文一字未动**。于是同一句约定在新旧两种起法下解析到两个不同的地方。

实测（本泳道现取，`ls` 主 checkout 与全部 worktree 的 `reports/lane-heartbeat/`）：

- 主 checkout `C:\Dev\zhuopin-ai\reports\lane-heartbeat\` 共 **26 份**，批次前缀全部是 `B-0902_*`／`B-0903_*`／`B-0904_*`——**无头 ps1 时代的产物**；
- 本批 `B-0908_四泳道机制根治` 九条泳道的心跳（`#439`／`#491`／`#500`／`#476`／`#503`／`#501`／`#358`／`#440`／`#504`）**在主 checkout 一份都没有**，全部散落在各自 worktree 内；
- 更糟的一处：`491-general-collections-readonly.md` **同时存在于三个不同 worktree**（`agent-a2a4c26267941e248`／`agent-a642d712931407732`／`agent-ae29f8b38319182d4`）——同一条泳道的心跳被切成了三份互不相见的副本。**这条实测直接否掉了「让读侧去各 worktree 里搜一遍」这个看似省事的解法**（见 design 决策点 1 的 (c) 项）。

**成因半 ⑶ · 「已 DONE 被判失联」是同一个误判的另一半，必须同批修**

`工具-泳道看护状态机.py` 的泳道状态只有 `running`／`paused`／`resumed` **三态，没有任何「已完成」概念**（现取：全文 `status` 赋值处仅此三值，无 `done`/`completed`），而 `check_heartbeat` 只跳过 `paused` 的泳道。⇒ 一条正常收工、按约定写完 `DONE ｜ 产出落点` 后自然静默的泳道，30 分钟后照样被判失联、照样落 `pause`、照样推「等人」。

🔑 **这一半此前是 skill 侧「知道有这么回事」的人守**（引用式装载器自陈的「已知缺陷⑵」）；`#504` 把它从「知道」变成「坐实」，**且发现真因不止这一半**。⑴⑵ 两半是同一个误判的两个来源，**分开修会留下另一半**（`#504` 行内 MUST）。

### 为什么必须走 openspec（门槛判定）

命中 `.claude/rules/场景建造与合规.md` §21 **① 改变全项目口径**（「什么算失联」这条判据本身要改——加一条「已 DONE 不算失联」的豁免）＋ **③ 改变既有模块对外语义**（`check_heartbeat` 新增非 stale 的返回分支；新增写侧子命令）。两条命中任一即必走，本件两条都命中。

### 守卫退休问答（MANDATORY · 协议〇.9 措施 B / one-in-one-out）

**本次退休两条既有的「人守」，各以一道机器行为取代，无一条是空退。**

**退休对象一**：「看到 🐕 超时先核 mtime，多半是误报、`resume` 撤销即可」——这条今天写在**每一份看护件里**（`看护件-泳道看护批B-0908_四泳道机制根治-2026-09-08.md` 第 28 行是本批的那一份），属「靠起草者每批记得写一句 ＋ 看护者每次记得核一遍」这一已被反复证伪的防线（同族＝队列 `#284` 计数⑦⑧⑨）。
**取代物**：读写同锚之后**误报本身不再产生**——没有误报，就没有要人工核对的东西。这不是"加一道守去挡误报"，是**把产生误报的那个错误消掉**。

**退休对象二**：「心跳落 `reports/lane-heartbeat/<泳道>.md`」这句**路径级散文约定**——它今天分散在 `zhuopin-lane-watch/SKILL.md` 步骤 4、`zhuopin-lane-clearpool/SKILL.md` 第 23 行、历次看护件与每一份 opener 正文里，是典型的手抄形态（同族＝`#345` 35 份路径引导手抄）。
**取代物**：泳道改为**跑一条命令**，路径由工具内部按 `REPO_ROOT` 解析，**成为工具实现细节而不再是要每份 opener 复述一遍的口径**；读写两侧从此共用同一个锚的同一处表达式，**漂移的物理可能性被消除**（同 `criteria` 子命令"现取而非手抄"的既有手法）。

**为什么不是"新增一道守卫、没退任何东西"**：本包**不新增任何检查器**。它新增的是一个**写侧入口**（把已存在的写动作从散文约定收敛成工具调用）与一条**豁免分支**（已 DONE 不判失联）。判据轴上守卫的数量是**减一**：原先「看门狗告警 → 人核 mtime → 人判误报 → 人 resume」这条四步人链，收敛成「看门狗告警 ⇒ 真的失联」。

原文一律保留、标注取代关系，**不删一字**（历史记录不追改）。

### 伴生文件的 .gitignore 覆盖问答（MANDATORY · 队列 #328 子项②）

**不适用（不新增文件名形态），但须写明一处**：本变更让心跳文件的**产生位置**从各 worktree 收敛到主 checkout，**文件名形态完全不变**（`reports/lane-heartbeat/<泳道标识>.md`，主 checkout 下已实存 26 份同形态文件）。

**核实方式（实测，非推断）**：

```
$ git check-ignore -v reports/lane-heartbeat/504-heartbeat-vis.md
.gitignore:50:**/reports/	reports/lane-heartbeat/504-heartbeat-vis.md
```

命中 `.gitignore:50` 的 `**/reports/`。写入位置改变不改变文件名形态，忽略规则沿用现状、不受影响。

⚠️ **一处须在 design 审时确认的反向边界**：正因为 `**/reports/` 覆盖，心跳件**从不随分支流转**——这既是本缺陷的物理成因，**也是本包刻意不动的一条**。「把 `reports/lane-heartbeat/` 从忽略名单里放出来、让心跳随 git 流转」是一个看似更彻底的解法，**本包明确否掉**（理由见 design 决策点 1 的 (d) 项：心跳一入库，每写一行就脏一次索引，与「看护者不 commit」「撞 `.git/index.lock` 不重试」（`#487`）正面冲突）。

## What Changes（改什么）

**① `0-学习与工具/工具-泳道看护状态机.py`**（本轮不动，apply 阶段做）

- **新增写侧子命令 `heartbeat`** ＋ `write_heartbeat()`：追加一行到 `REPO_ROOT / reports/lane-heartbeat/<lane>.md`，**复用读侧同一个 `REPO_ROOT` 常量**（🔴 MUST 复用，MUST NOT 另写一遍解析逻辑——那正是本包要消灭的形态）；`--done` 标记收工。目录不存在时自建。
- **`check_heartbeat()` 新增「已 DONE 不判失联」分支**：判定来源与优先级见 design 决策点 3；命中时 `stale=False`、**MUST NOT** 落 `pause`、**MUST NOT** 推通知，且返回值里 MUST 带可区分的原因字段（不得与「健康」返回得一模一样——只读结果太干净先怀疑没读到对象）。
- 新增泳道终态 `done`（状态文件字段），并接入 `summary` 现取。
- 🔴 **30 分钟阈值不动**（`HEARTBEAT_STALE_MINUTES_DEFAULT` 保持 30.0）——本包改的是「什么算失联」的**覆盖范围**，不是「多久算超时」的**数值**。

**② `0-学习与工具/test_工具-泳道看护状态机.py`**（本轮不动）

- 新增至少两态（`#504` 期望产出 ③）：**「worktree 内写、主 checkout 读得到」**与**「已 DONE 不被判失联」**；另加一例守住 `REPO_ROOT` 读写同锚（写侧与读侧解析出的绝对路径逐字相等）。
- 既有 5 例 `check_heartbeat` 单测零漂移。

**③ `0-学习与工具/skills源码/zhuopin-lane-watch/SKILL.md`**（本轮不动）

- 步骤 4 的心跳约定：由「往 `reports/lane-heartbeat/<...>.md` 写」改为「跑 `... heartbeat --lane <泳道> --text "..."`」，路径退为工具实现细节；旧版原文原样保留、标注取代关系（同「推送目标」节 2026-09-06 与红线节 2026-09-07 两次改判的既有手法）。
- 5.6 看门狗节：补一句「已 DONE 泳道不判失联」的豁免与其判定来源指针。
- 🔴 **新增「已知缺陷」段**——现取实证：**该文件今天根本没有这一段**（全文 grep `已知缺陷` 零命中）。`#504` 期望产出 ④ 说的「回改『已知缺陷』段」在本仓库侧**无对象可改**，须先建再改；本条与下面 ④ 是同一件事的两半，**不得只做一半**。

**④ 引用式装载器（claude.ai 侧 `zhuopin-lane-watch`，skill id `skill_01GsmGMFZdgiXknSA3FKeqch`）**（本轮不动，且 **CC 侧做不了**）

- 🔴 **如实说明的一处实现限制**：`#504` 期望产出 ④ 要求「回改装载器指针的『已知缺陷』段」——**该装载器不是仓库文件**，它是 Cowork/claude.ai 侧 `save_skill` 装的引用式指针（`lane-watch-mode/tasks.md` 2.2 记有其 skill id），**CC 工具清单里没有对应能力**。故本包把它拆成一条独立的 **【Cowork】** 任务（`tasks.md` §5.2），**不得在 CC 侧假装闭合**——同 `lane-watch-mode` SKILL.md 文末对 `save_skill` 那两条的处理手法。
- ⚠️ **另一处载体明确不改**：历次看护件里那句「已知缺陷，本批照旧适用」是**带日期的历史快照件**，按 CLAUDE.md「历史记录不追改」**一字不动**。

**⑤ `openspec/changes/lane-watch-mode/specs/lane-watch/spec.md`**（本轮已出 delta，见本包 `specs/`）

- 「波间 SHALL 监测心跳」这条 requirement 属**真实改写**（新增两条约束：读写同锚、已 DONE 豁免），走 MODIFIED 块，不靠新增一份 spec 绕过。

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

1. **本流程哪些判断是人脑默会经验？**
   - **「🐕 告警要不要当真」**：今天完全靠看护者的默会经验——看到告警先去核心跳文件 mtime，凭「这条泳道刚才还在动」的印象判成误报。这条经验**没有任何字段承载**，换一个看护者、或同一个看护者在长批次末尾疲劳时，就会失效（而失效的方向是**把真失联当误报放过去**，比误报本身更危险）。
   - **「一条泳道到底算不算完了」**：今天没有终态字段，全靠人看心跳文件最后一行是不是 `DONE ｜`。这个判断的**尺度**（`DONE` 之后又追加了一行怎么算？`STOPPED ｜` 算不算终态？）从未被显性化——design 决策点 3 即处理这一点。
   - **阈值/尺度类**：30 分钟阈值本包**不改**（显性声明，见 What Changes ①）；须裁的是「终态的判定来源与优先级」与「`STOPPED` 是否与 `DONE` 同等豁免」两项尺度，均列为 design 决策点，**不由起草方自行拍**。
2. **由谁显性化？** 持有人 **Shao Peishen**（`#504` 立行依据＝其 2026-09-08 答 13a；「什么算失联」是看护机制自身的判据，归他）；backup **孙涛**（其缺席时的代理人，范围见 `.claude/rules/场景建造与合规.md`）。
3. **用什么方法提取？** **历史案例反推 ＋ AI起草·专家批改**——反推依据＝本 proposal「成因」节三组实测（主 checkout 26 份心跳的批次前缀分布／本批九条泳道零命中／`#491` 心跳散在三个 worktree），以及 `#488` 记录的 `REPO_ROOT` 解析同族坑；起草由 CC 出 design 决策点，**由 Shao Peishen 逐条批改后方可 apply**（本包命中 🟡 档 ③ openspec design 审）。

## 验收与晋档条件（强制，四档口径）

- **本变更包交付后场景所处档位**：**档 1（mock 验证）**。本包全部单测走临时夹具（`REPO_ROOT` 指向 tmp、模拟 linked worktree 的 CWD），**不发真实网络请求、不连 `.51`、不推企微**。
- **晋下一档的条件**：
  1. 🔴 **一次真实批次验证**：下一个泳道看护批（≥3 条并行泳道、含至少一条正常收工的泳道）跑完，看护者从主 checkout 跑 `check-heartbeat`，**误报次数 ＝ 0**——判据取自 `reports/lane-watch-state.json` 里该批 `heartbeat_stale` 记录数与实际失联数之差，**不许会话自算**。
     ⚠️ **验收样例的硬约束**：**不得拿单条泳道的批次当样例**——单条泳道跑在哪个 worktree 都不影响结论，用它验收等于用一个不会触发缺陷的场景证明缺陷已修。样例批次 MUST 含 ≥2 条并行 worktree 泳道。
  2. 「已 DONE 不判失联」在真实批次里被触发过至少一次（某泳道收工后静默 >30 分钟而未被 pause），且 `summary` 现取能报出该泳道为终态而非暂停态。
  3. `openspec validate --strict` 全绿（本包自身）；`工具-泳道看护状态机.py` 既有单测零漂移。
  4. 上述 ④ 那条 **【Cowork】** 装载器回改已实做（不是"已登记"就算）——**缺陷修了而装载器仍写着「已知缺陷」，下一棒会继续按人守绕路**（`#504` 行内原文）。
- **价值指标**（**风险型 ＋ 工时型**双指标）：
  - **风险型 · 基线**：本批 `B-0908_四泳道机制根治` **九条泳道心跳在主 checkout 命中 0 份**（本泳道 `ls` 实测）⇒ 看门狗对该批的误报率**结构上等于 100%**。**目标值**：误报次数 ＝ 0。
    🔑 **这条指标的真正代价不是"被误报烦到"**：一个恒为真的告警等于没有告警——看护者一旦学会"🐕 出现就当误报"，**真失联那次也会被同样地放过去**。本包保的是这个信号的可信度。
  - **工时型 · 基线**：每次 🐕 告警的人工处置 ＝ 核 mtime ＋ 判误报 ＋ `resume` 撤销（每次数分钟 × 每批每泳道可能多次）。**目标值**：降为 0（误报不产生）。
  - **基线确认人**：Shao Peishen。
- **LLM 判据黄金集**：**不适用**。本包不含任何 LLM 运行时判断，全部为确定性的路径解析、文件 mtime 读取、状态字段检查与行尾哨兵匹配。

## Impact（影响面）

**受影响 specs**：**修改** `lane-watch`（「波间 SHALL 监测心跳」这条 requirement 新增读写同锚与已 DONE 豁免两条约束）。该 capability 的 spec 目前仅以 delta 形态存在于未归档的 `lane-watch-mode` 变更包中（`openspec/specs/` 下尚无 `lane-watch/`，只有 `lane-clearpool/`）——**本包的 MODIFIED 块以 `lane-watch-mode` 的 delta 为基线**，须在 design 审时确认这条链路顺序（design 决策点 6）。

**受影响代码/文档**（全部在 apply 阶段动，本轮零改动）：`0-学习与工具/工具-泳道看护状态机.py`、`0-学习与工具/test_工具-泳道看护状态机.py`、`0-学习与工具/skills源码/zhuopin-lane-watch/SKILL.md`、`openspec/changes/lane-watch-mode/specs/lane-watch/spec.md`、claude.ai 侧引用式装载器（**Cowork 任务**）。

**明确不受影响、且刻意不动的**：

- 🔴 `.gitignore` 第 50 行 `**/reports/` —— **不动**。心跳不入库这条不变，理由见上「反向边界」。
- 🔴 `HEARTBEAT_STALE_MINUTES_DEFAULT = 30.0` —— **不动**。本包改覆盖范围，不改阈值数值。
- 🔴 `工具-共享文档编辑锁.py::_resolve_repo_root()` —— **不动**，只被复用。它今天的行为是**正确的**（实测：从 linked worktree 内解到主 checkout），本缺陷不在它身上；`#488` 那个解析偏移是另一处形态，**不要在 apply 期顺手"修"这个函数**。
- `0-学习与工具/工具-opener批处理执行v2.ps1` —— 哨兵语义与调用签名不变，本包不新增哨兵。
- `_notify_best_effort` 与 `--no-notify` 纪律 —— 不动；本包只减少**该发的告警数量**，不改发送通道与目标。
- `transfer_out_lane`／`deploy-authorize`／D1 四档判据表 —— 全不涉及。

**红线核对**：

- **mock 先行**：单测层用临时夹具与注入，**不触碰 `.51`、不发真实请求、不推企微**；真实批次验证留待下一个看护批，如实登记不假装闭合。
- **audit 留痕**：新增的 `done` 终态与心跳写入均落既有留痕载体（`reports/lane-watch-state.json` ／心跳文件），`summary` 现取报出。
- **OEM 隔离**：不涉及——不含任何 OEM 技术数据。
- **L2 门禁 / ISO 26262 / ASIL**：不涉及——非安全相关代码，🔴 档四项本包一项不放宽。
- **凭据纪律**：本包全部产出**不含任何口令、URL 值或凭据**。
