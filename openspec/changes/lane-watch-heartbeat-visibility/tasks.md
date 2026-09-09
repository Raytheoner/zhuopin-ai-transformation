# tasks · lane-watch-heartbeat-visibility

> 队列 §一 `#504`。**§1 是本轮（`OP-0908-R`，🟢 档 openspec 起草）的全部范围；§2 起一律 MUST NOT 在 design 审过之前动手。**
> 🔴 档位说明：**起草 ＝ 🟢，design 审 ＝ 🟡，合入 master ＝ 🟡**。本泳道做到 §1 完即停。

## 1. propose ＋ design 起草（本轮，🟢）

- [x] 1.1 读队列 §一 `#504` 全行（`工具-队列查询.py --row 504 --field all`），不 Read/grep 队列真身
- [x] 1.2 成因取证（**实测，非推断**）：
  - [x] 1.2.1 读侧 `REPO_ROOT` 实测——在 linked worktree 内加载 `工具-共享文档编辑锁.py`，打印得 `C:\Dev\zhuopin-ai`（主 checkout）⇒ **读侧无 `#488` 那种偏移**
  - [x] 1.2.2 写侧实测——`git check-ignore -v reports/lane-heartbeat/504-heartbeat-vis.md` → `.gitignore:50:**/reports/`；该文件实存本 worktree、主 checkout 无
  - [x] 1.2.3 全机心跳分布实测——主 checkout 26 份全为 `B-0902/03/04_*`（无头 ps1 时代）；本批九条泳道零命中；`491-general-collections-readonly.md` 散在三个 worktree
  - [x] 1.2.4 半 ⑵ 坐实——状态机全文 `status` 仅 `running`/`paused`/`resumed` 三值，**无终态概念**
  - [x] 1.2.5 期望产出 ④ 的载体核实——`zhuopin-lane-watch/SKILL.md` **全文无「已知缺陷」段**；该段实际在 claude.ai 侧引用式装载器与历次看护件里
- [x] 1.3 `proposal.md`（含两条 MANDATORY 节、one-in-one-out 退休问答、`.gitignore` 覆盖问答）
- [x] 1.4 `design.md`（决策点 1–7 ＋ schema/接口 ＋ 关系表 ＋ Non-Goals ＋ §五 两项无默认未决）
- [x] 1.5 `specs/lane-watch/spec.md` MODIFIED delta（基线依赖已在文件顶部注明）
- [x] 1.6 `openspec validate --strict` 本包自身
- [x] 1.7 🟡 **design 审 —— 待 Shao Peishen 裁定**（决策点 1–7 取值 ＋ §五 两项明答）。**起草方 MUST NOT 自审自过**

## 2. apply · 工具侧（design 审过后，🟢 建造）

- [x] 2.1 `工具-泳道看护状态机.py` 新增 `write_heartbeat()` ＋ `heartbeat` 子命令（`--lane` / `--text` / `--done`）
  - 🔴 MUST 复用模块级 `REPO_ROOT`；MUST NOT `os.getcwd()`、MUST NOT 自行 `git rev-parse`、MUST NOT 提供 `--repo-root` 覆盖
  - 目录不存在自建；追加写；行首带本机时刻
- [x] 2.2 新增泳道终态 `done`（`status` / `done_at` / `done_note`），由 `--done` 唯一写入
- [x] 2.3 `check_heartbeat()` 加终态豁免分支 ＋ `skipped_reason` 返回字段（决策点 3/4/5 取值）
  - 🔴 阈值 `HEARTBEAT_STALE_MINUTES_DEFAULT = 30.0` **不动**
  - 🔴 豁免时 MUST NOT 落 `pause`、MUST NOT 推通知
- [x] 2.4 `summary` 接入终态与豁免计数（同 `count_lock_hits` 模式）
- [x] 2.5 CLI 输出分支（终态豁免打印可区分文案）

## 3. apply · 单测（`#504` 期望产出 ③，🟢）

- [x] 3.1 **态一**：worktree 内写、主 checkout 读得到（模拟 linked worktree CWD）
- [x] 3.2 **态二**：已 DONE 不被判失联（状态权威源 ＋ 哨兵回落源各一例）
- [x] 3.3 读写同锚断言：写侧解出的绝对路径 == 读侧解出的绝对路径
- [x] 3.4 `STOPPED ｜` 分支（按决策点 4 裁定结果写；**审前不预写**）
- [x] 3.5 终态豁免与健康运行返回可区分（决策点 5）
- [x] 3.6 既有 5 例 `check_heartbeat` 单测零漂移 ＋ 全量回归零回归
  - **零漂移手段**：`git diff -U0 0-学习与工具/test_工具-泳道看护状态机.py | grep "^-"` ⇒ 全文件唯一被删行 ＝ `from contextlib import redirect_stdout`（改为 `redirect_stderr, redirect_stdout`），**5 例既有 `check_heartbeat` 用例一行未动**。

## 4. apply · 执行指引改口（🟢）

- [x] 4.1 `zhuopin-lane-watch/SKILL.md` 步骤 4：心跳约定由「写文件」改为「跑命令」；**旧版原文原样保留、标注取代关系**
- [x] 4.2 同文件 5.6 节：补终态豁免说明与判定来源指针
- [x] 4.3 opener 模板库 / 看护件模板里的心跳段同步改口（🔴 **只改活件里当下生效的指引；带日期的历史看护件一字不动**）
  - **现取核实结论＝活件里没有第二处要改**（手段：`grep -rln "lane-heartbeat"` 全仓 ＋ `grep -n "心跳" opener骨架.md`）。命中 30 处，逐类判：① `zhuopin-lane-watch/SKILL.md` ＝ 4.1／4.2 已改；② `zhuopin-lane-clearpool/SKILL.md` ＝ 退休件，见 4.4；③ **17 份 `看护件-*.md` 全部带日期** ⇒ 历史快照件，一字不动；④ 两份队列真身与 `队列行日志/#N.md` ＝ 历史登记，不追改；⑤ `opener骨架.md` **唯一一处「心跳」在第 74 行**（收工汇总须含「心跳全文」），**不含写入路径口径** ⇒ 无需改。⑥ `工具-opener批处理执行v2.ps1` 与 `工具-落库sweep.py` 的「心跳」全为**另一个对象**（写入时刻哨兵心跳 / 服务验活心跳），不涉本包。
- [x] 4.4 `zhuopin-lane-clearpool/SKILL.md` 第 23 行的同款路径散文——该 skill 已退休，**核实后按"退休件不追改"处理或加一行指针，二选一在 apply 期定，不在本轮预设**
  - **apply 期裁定＝取「退休件不追改」，一字不动。** 判据（现取该文件 frontmatter 与首段原文）：`status: 🔴 已退休（2026-09-02）`，且文首明写「下文正文按『历史记录不追改』原样保留，作为 `zhuopin-lane-watch` 执行步骤 1-2（**扫池／排波**）的判据引用来源」——**被引用的是步骤 1-2，不是步骤 4-5**，那句心跳散文不在任何活路径的引用面上；且该 skill 已不能独立触发（口令「offlan清池」现指向 `zhuopin-lane-watch`）。**往退休件里加指针只会让「已退休、按原样保留」这条承诺多一个例外**，而当下生效的口径已由 `zhuopin-lane-watch/SKILL.md` 步骤 4 承载。

## 5. apply · 「已知缺陷」段回改（决策点 7，🟢＋【Cowork】）

- [x] 5.1 `zhuopin-lane-watch/SKILL.md` **新建**「已知缺陷与其状态」节，把本缺陷以**已修（指向本变更包）**形态写入
- [ ] 5.2 🔴 **【Cowork】** claude.ai 侧引用式装载器（`skill_01GsmGMFZdgiXknSA3FKeqch`）的「已知缺陷⑵」回改——**CC 无 `save_skill` 能力，做不了**；须由 Cowork 侧执行。归属与时序按 design §五 第 2 项的裁定结果办，**MUST NOT 在 CC 侧勾掉冒充闭合**
  - **本泳道（`OP-0909-M`）跳过，如实留空。** Shao Peishen 2026-09-09 已答 `2a` ＝ (x)，🔴 **归属＝Cowork，不进 CC 泳道**，派单件「不做什么」写死「已答2a，归 Cowork，勿重做」；🔴 **同一题不得两端各答一次**。**硬前置已由本泳道满足**：载体①（SKILL.md「已知缺陷与其状态」节）本次已建成（5.1），装载器可指向的锚已存在——待本包 ff 入 master 后由 Cowork 执行。承接＝队列 §一 `#504`，不另立行。
- [x] 5.3 历次看护件里那句「已知缺陷，本批照旧适用」：🔴 **一字不动**（历史记录不追改）——本项为"确认不做"，勾选即表示已核实未动

## 6. 收口（🟡，本泳道不做）

- [ ] 6.1 🟡 合入 master —— 本泳道 MUST NOT 自行合入
- [ ] 6.2 🔴 归档顺序：本包 MUST 在 `lane-watch-mode` 归档之后归档（design 决策点 6(a)）
- [ ] 6.3 队列 §一 `#504` 状态回写 ＋ §二 批次登记
- [ ] 6.4 晋档 2 验证：下一个 ≥2 条并行 worktree 泳道的看护批，误报次数 ＝ 0；且终态豁免被真实触发过一次
