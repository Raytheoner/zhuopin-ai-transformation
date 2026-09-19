# session 接力 · Phase1 收口卡

> 覆盖不追加，8 KB 上限。最近改写：2026-09-19 20:0x 本地（Cowork 泳道看护 `OP-0919-K` 三次收工）。
> 🔴 **新接棒的第一件事**：读本卡全文 ＋ `CLAUDE.md`，然后跑 `python 0-学习与工具/工具-队列查询.py --digest --actionable` 扫池（**新参数，只出能动的行，22 KB→8.6 KB；要全池去掉它**），核触碰区无重叠再动手。

## 一、正在跑的

🚀 **CC 无头批 `B-0919_解冻三条推进` 在跑**（看护件 `1-转型规划/0-全景路线图/看护件-【CC】解冻三条推进-2026-09-19.md`）：三条泳道并行——`ledger`·A1 §一 `#439`｜`evalsuite`·A2 §一 `#440`｜`openerdual`·A3 §一 `#503`，OP 分别 `OP-0919-M`／`-N`／`-P`。**三条一律止步 design 可审态、不 apply**，收工以 `OPENER_PARTIAL: 停在 🟡 design 审` 收尾。触碰区已现取核过互不重叠。
🔴 **接棒先探哨兵**：`reports/opener-batch/<批目录>/exit.txt` 与 `summary.txt`，**不要 tail 日志**。

编辑锁已放。master `09b153d0`。

## 二、机制类可动 WIP：**25 → 16**（上限 22），十天来第一次回到限内

他 2026-09-19 答 `1a`／`2b` 后当场落地。**根因不是做得慢**：现取拆解（判据用工具自己的 `_mechanism_wip_counted_rows`）25 条里**有人在办只有 13 条，待领／未领 12 条**——🔑 **WIP 数的不是「在办」，是「开着且没挂 🛑 的机制行」**。

- `1a`：9 条从未解冻、至今无人领的行（`#337`／`#462`／`#504`／`#570`／`#571`／`#574`／`#576`／`#582`／`#587`）**回挂 🛑**，25 → 16。回挂不关行、不降优先级、不改排序，谁要领摘掉那段即可。
- `2b`：`#439`／`#440`／`#503`（他 09-06／09-07／09-08 亲手「去 🛑」解冻、之后十天没人动）保持解冻，起上面那个批推进。
- 📌 **两条口径观察（只记不改）**：带「WIP豁免：」的 7 条**豁免只免立行被拦、不免计数**；**「去 🛑」解冻若不与派工同时发生，解冻本身就是在推高 WIP**。

## 三、本日 master 走了四步：`9cc4dab3 → cbae2199 → 9cb533e9 → 20034eb9 → 09b153d0`

- `cbae2199` **开场 token 三处瘦身**：`--digest --actionable`（22.0→8.6 KB）；新建 `工具-main-leak回放.py`（`cat` 补丁 69.7 KB → 全量表 1.8 KB，白名单**现取** v2.ps1、解析不到即 fail-loud）；分诊加「自身留痕」两级降档（强档 9→3，sweep 告警噪音同降）。
- `9cb533e9` **`happy-thompson-017679` ff**（`#398`⑹ sweep 提交信息静默截断）。rebase 一处冲突已**零丢弃**解开：master 侧三元组解包＋`_mark_step`＋`coverage_note=` 全留，分支侧「空信息 fail-loud 跳过」守卫原样并入循环体开头。
- `09b153d0` **`#611` 第三道闸方案 D ff**（白名单一次补齐三类＋竞态单测）。
- 分支池 `claude/*` **28 → 27**，注册 worktree **14 → 12**；`op0906i`／`op0822c`／`queue-315` 三条 ref 已删（各自先补 `backup/<名>-pre-delete-op0919k`，origin 未动）。

## 四、仍开的与待他一字母

🔴 **`#611` 没销号**：白名单那一半已合入并独立复核过（`reports/_op0919k/verify611.py`：分支侧白名单 0/13 → **12/13**，ff 后 master 侧重跑同为 12/13）；**剩下那一面白名单永远治不了**——`20260919-075655/q2-A1` 的泄漏清单只有看护者自己写的取证件，文件名任意，须换判法（按泳道 worktree 实际触碰过的文件归属，或按提交作者／时间窗）。**形态未定、🟡 档，待他一字母后另派。不得表述为「第三道闸已根治」。**

其余：`#614`（四条已定，落地在他手上）、`#600`／`#595`／`#477`；`#617` 丙档 `op0910n` 待裁；§四 `#213` 七个 Owner 不代填；`#539` 与在办 `#538` 同触碰 SC2 周报页面，已判不领。

⚠️ **别再往里加字**：根 `CLAUDE.md` 现 13,148 B、阈值 12,288 B，超 860 B，而守卫是**告警型不是拒绝型**、告警没有消费者；`.claude/rules/两桌同步与取证.md` 11,461 B、超 8,192 B 更多。§一 `#454` 靠「行长豁免」过 release，下次值周巡检该外置。

## 五、常备纪律（血换的）

- 🔴 **凡触碰 git 的命令一律 Windows 侧跑**（`Windows-MCP PowerShell` ＋ `C:\Dev\zhuopin-ai`）：同一条 `git status --porcelain` **挂载侧 33.9 秒／本机侧 0.6 秒，56 倍**，而编辑锁每次 acquire／release 都跑它；挂载侧 `rm` 被沙箱拒，release 一被拒锁就清不掉。只读的 `工具-队列查询.py` 不碰 git，两侧都行。
- 🔴 **多行回写不要连发 `commit-edit`**（release 被拒时锁保持占用 ⇒ 第 2 行起必撞「占用中」）。正确形态：一次 `acquire` → 多次 `edit-row --who` → `append-row --section 二` → 一次 `release`。状态格超 4096 B 先 `工具-队列行K2外置.py --apply` 再 `edit-row --changes-json`。
- 🔴 **看护者在泳道运行期间绝不往主仓写文件**——本日实证：`#611` 泳道全程 28 分钟里本方只在 `reports/`（gitignore）备料，该泳道第三道闸**零 main-leak**、`SENTINEL_FIRST`、`OK`。
- 🔴 **`git worktree prune` 删不掉时先看 `.git/worktrees/<名>/fsmonitor--daemon`**：陈旧 daemon 目录会让 prune 报 `Permission denied`，`Remove-Item -Recurse -Force` 掉管理目录后再 prune 即通（同 `#618` 陈旧锁一族）。🔴 清 worktree 一律 `Remove-Item -Recurse -Force`＋`prune`，**禁 `git worktree remove`**（协议〇.5／`#267`）；删前三查：进程占用、tracked 改动、被忽略内容里有没有非缓存的东西。
- 🔴 **泳道收工常不自删 worktree**（`#576`）⇒ **ff 前先清 worktree**，否则 `工具-泳道分支合入.ps1` 撞 `already used by worktree` 报 exit=9（`#618` 今日合入的守会当场点名占用者）。
- 🔴 **超 60 秒的命令必须写哨兵**：`Windows-MCP PowerShell` 单次约 60 秒即断。`Start-Process` 另起、重定向日志、尾巴落 `<log>.done` 写退出码，只探哨兵、大间隔。
- 🔴 **回归 narrow 到受影响测试类**（node-id，**不得写 `-k`**）；**ff 一次只在飞一条**；**全份单测里 `ReleaseStructuralValidationTests` 两条按日历过期的 FAIL 已在纯 master `a75bebd2` 复现＝零回归**，别当成自己改坏的。
- 🔴 **判「还失不失败」只读结论性清单**：`*-main-leak.patch` 禁 `cat`，走 `python 0-学习与工具/工具-main-leak回放.py`（`--extra '<glob>'` 试算候选修法）。
- 🔴 **分诊不得凭强档直接改判**：闸会扫到自己上一轮写的留痕（已加两级降档，9→3）；剩余 3 条属「命中点在引文里」，字符串判据解决不了，必须读状态格全文复核。
- 队列真身禁裸 `Read`／`grep`，只走 `工具-队列查询.py`；opener 一律用 `工具-opener生成.py` 出（`--input-pointer` 必填）；看护件须有 `## 三bis`，`### A<N>` 须带 `§一 #<行号>`。
