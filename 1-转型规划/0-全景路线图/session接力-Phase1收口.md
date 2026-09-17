# session 接力 · Phase1 收口卡

> 覆盖不追加，6 块，8 KB 上限。最近一次改写：2026-09-17 08:2x（Cowork 环境总线 `OP-0917-E`）。

## 一、本轮已收口的（他答甲a／乙a／丙c）

- **甲**：巡检真跑一轮，`pending-ff.jsonl` **16 行全销并归档**到 `pending-ff.done-20260917.jsonl`（含 `op0916y-lane-isolate-600`，现取已是 master 祖先，非误销）。
- **乙**：`claude/op0913t-worktree-guard-576` 已经 `工具-泳道分支合入.ps1` 合入 **`edf7fa3`**（rebase 零冲突、测试全绿、四 ref 对齐）。随后清掉 10 条「仅缺文件」worktree，**23 条 → 10 条**。
- **丙**：桌面端「全天每 15 分钟」任务已由他重新 Active（保底那条腿）。另一条腿见第三块。

## 二、✅ 全部字母都收完了（甲a／乙a／丙c／丁a）

`claude/op0917a-wt-del-fallback-576` 已合入 master **`edd2957`**（rebase 零冲突、三份单测全绿、四 ref 对齐）。一个分支三处修：体检工具「目录已消失」不再崩、git 删不动时回退 `Remove-Item`、轮询守包装脚本取不到退出码即 exit 8。

🔴 **只剩他一步**：提权重跑一次 `工具-注册轮询守计划任务.ps1`，新模板才会烘进包装脚本。验收判据见第四块。

两处过程教训（均无承接行）：① 合入脚本 L72 的 `git worktree add` 失败被 `| Out-Null` 吃掉，报出来的是下一行 `Push-Location` 的「路径不存在」——**报的不是真因**；② 后台起合入会开一个可见控制台窗口，看护者当垃圾窗关掉就把 finally 掐了（本轮真发生，留痕与临时 worktree 已手工补）。

## 三、🔴 本轮最硬的一条发现

本仓里 **`git worktree remove --force` 与 `git worktree prune` 一律 `Permission denied`**，而同一个 shell 里 PowerShell 的 `Remove-Item -Recurse -Force` 删得掉同样的路径（两条独立的 git 路径都败、PowerShell 同路径成功）。巡检的 worktree 清理长期空转、`[WT-BLOCKED]` 天天报却一条也没删成，就栽在这里。

**原因未查明**：`core.longpaths` 未设、系统 `LongPathsEnabled=1`，但失败路径并不长，所以**不把长路径当因果**。修法与原因无关：git 删不动即回退。

## 四、轮询守 `#575`：已收，且拓扑变了

2026-09-17 11:03 三条判据全过：`LastTaskResult=0`、Operational 63 秒（不再是 1 秒）、留痕出真行（`probe{NO-SIGNAL,197ms}`／`patrol{WL-NO-ACTION,NO-PENDING,WT-NO-ACTION,59706ms}`／`woke:false`）。当日稳定跑满 22 轮，每轮 60–90 秒。行已翻 `[S:done]`。

🔴 **真因是机器自己写出来的**：10:40 那轮留痕里是 `wrapper_error: pwsh 不存在：C:\Program Files\WindowsApps\...\pwsh.exe` —— S4U 上下文里那个 Store 封装路径连 `Test-Path` 都为假。解法是换非 Store 的 zip 版真身 `C:\Tools\pwsh7\pwsh.exe`（301,368 B、属性 Archive），提权重跑注册脚本传 `-PwshExe` 烘入。

🔴 **拓扑已变，别再照旧卡片行事**：Cowork 桌面端「全天每 15 分钟」任务**已由他删除**（2026-09-17）。探针＋巡检两件现在**只由本机 `ZhuopinPollGuard` 一条腿承担**。以前卡上那句「桌面端 15 分钟任务不得停」已作废。

➕ **残留风险，无承接行**：单腿之后没有第二条腿兜底。它现在失败会叫（exit 8／exit 9 ＋ 留痕），但**没有任何人或机器在看 `LastTaskResult`**——会叫而没人听，等于半个守卫。下一个 session 若要补，最省的做法是让 sweep 或收工探针每轮顺带核一次「当天留痕文件的最新行时间距今是否超过 30 分钟」。

## 五、下个 session 开头

1. 拿他对第二块的字母，走 `工具-泳道分支合入.ps1` 合入（永不手工 merge）。
2. 合入后提醒他重跑注册脚本，并按第四块的新判据验收。
3. `#600`（无头泳道隔离）是别的线在推，别插手；`#595`（企微断连）仍 open。

## 六、常备纪律

- **相关不是因果。** 断言前先问「有没有一个反例能推翻它」。
- **单测证明代码对，第一轮真跑才证明环境对。** 本轮两处缺陷都是首轮真跑当场暴露的。
- **只会报成功的守卫等于没有守卫。**
- **预授权是对具名分支的，不是对「这类活」的。**
- 队列真身禁裸 `Read`/`grep`，只走 `工具-队列查询.py --row/--digest`；状态前缀只能写合法机器字段（`[S:open]`/`[S:done]`）。
- 回写优先用 `工具-共享文档编辑锁.py commit-edit/commit-append`（取锁→改→释放→提交一次完成）；等泳道用 `工具-泳道看护等待.py wait`，别逐轮自查。
- 代码块只留给要他手工粘贴执行的东西；凡需他定夺，写全「是什么／选项＋代价／答复模板」三件套。
