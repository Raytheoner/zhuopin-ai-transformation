# sweep-ff-sync-batch-reorder Proposal

## Why

`工具-落库sweep.py::main()` 的执行顺序是 `_push_any_unpushed_commits` → **`_sync_master_if_behind_origin`** → `_verify_fast_forward`（分叉早检）→ 批次处理（`git add`/`_strike_off_rows`/`git commit`/`git push`）。`_sync_master_if_behind_origin` 跑 `git merge --ff-only origin/master`，而此时批次尚未提交、工作区必然是脏的（§二"待 commit 批次"的存在本身就意味着有未提交改动——这是文件头部注释里明文的设计假设）。一旦 origin 上有新提交也改了同一个文件，git 会因"本地未提交改动将被合并覆盖"而拒绝这次 ff 合并（`error: Your local changes to the following files would be overwritten by merge`），函数据此抛出 `SweepAbort`，而**批次处理排在它之后，本轮完全走不到**。

2026-08-06 实测：近 20 个提交中，触碰 `跨桌任务队列.md` 的是 20/20 ＝ 100%。`origin` 上的新提交几乎必然改这个文件，而主工作区几乎必然处于"有待 commit 批次"的脏状态——两个近乎恒真的条件合取，故障即为必然，非偶发。当日已发生两次需人工介入解卡（`git commit` + `git pull --rebase` + `git push`）。sweep 是唯一负责让主工作区跟上 `origin/master` 的机制，而它恰恰因为"脏"（这正是它存在的理由）而同步不了——形成自锁循环。

## What Changes

- **`_sync_master_if_behind_origin` 从"批次处理之前"移到"批次已在本地提交之后"**：先把当前可安全落库的批次（`_partition_pending_rows_by_batch_isolation` 判定为非歧义的 `clean_rows`）逐个 `git add` + 状态列回写 + `git commit`（**不在每个批次内单独 push**），把"脏工作区"转换成"干净工作区 + 若干本地新提交"，再尝试与 `origin/master` 对齐。
- **对齐方式从"仅 ff-only merge"升级为"能 ff 则 ff，diverged 则 rebase"**：commit 完成后 fetch 一次，按本地 `HEAD` 与 `origin/master` 的关系分三种情况处理——纯落后（ff-only merge）、纯领先（直接 push）、已分叉（`git rebase origin/master`，成功则 push，失败则 `git rebase --abort` 回滚到分叉前的本地提交状态，不丢内容，复用既有 #171 分叉告警机制发出一次 webhook 通知并以既有 `FORK_EXIT_CODE` 结束本轮）。
- **push 从"每个批次各自 push 一次 + 台账重跑再 push 一次"合并为"本轮末尾统一 push 一次"**：批次提交、遗留尾巴批次（straggler）提交、台账重跑提交全部只 `git commit` 不 `git push`，由末尾统一的对齐步骤一次性推送本轮全部新提交。
- **移除批次处理之前的第二次分叉早检（`_verify_fast_forward(refetch=False, ..., is_fork=True)`）**：该检查在现有调用顺序下，其覆盖的场景已被起跑段 `_push_any_unpushed_commits`（#194）与本次新增的末尾统一对齐步骤共同覆盖，成为死代码（见 design.md「决策点 3」的推导）；分叉判定与告警职责整体后移到末尾统一对齐步骤，告警语义（is_fork 标记、退出码、webhook 文案、连续轮次计数）不变，只是判定时机从"批次处理前的早检"改为"批次已提交、真正尝试对齐时"。
- **`_push_any_unpushed_commits`（#194，起跑段无条件补推）保持不变**：它解决的是"上一轮已提交但推送失败，遗留在本地"的独立问题，与本次改动的"批次提交前的同步顺序"是两个不同的时序点，不合并、不重写（design.md「决策点 4」记录了为何不顺带统一）。
- **BREAKING**：无对外可见的破坏性变化；`git log` 上的表现会略有不同——同一轮内的多个批次此前各自产生独立的推送记录，现在合并为一次推送（提交记录本身不变，仍是一个批次一个 commit），不影响任何下游读取队列文件或历史记录的既有逻辑。

## Capabilities

### New Capabilities

- `sweep-sync-reconciliation`：`工具-落库sweep.py` 在"本地批次已提交、准备与 `origin/master` 对齐"这一时刻的行为契约——先提交后同步的顺序保证、纯落后/纯领先/已分叉三种关系的对齐策略、分叉时的安全回滚与告警复用、末次统一 push 的原子性边界。

### Modified Capabilities

（无——`sweep-fork-alert` 的告警语义（is_fork 标记、退出码、webhook 文案、连续轮次持久化与清零）完全复用、不改变其 REQUIREMENTS；`sweep-startup-resilience` 覆盖的四个起跑段动作与常驻服务部署提示均不受本次改动影响；`sweep-batch-status-classification`（状态列判据）与本次的批次识别/提交逻辑衔接，但判据本身不变。）

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

1. **本流程哪些判断是人脑默会经验？** 两处：① "何时用 ff-merge、何时用 rebase"——本变更用"本地是否领先"这一可机检的 commit 图关系代替人的直觉判断，但"rebase 冲突时是否值得再多等一轮重试还是应立即人工介入"这一权衡目前仍是拍板结果（选择"立即介入"，理由见 design.md），不是从第一性原理推导出的唯一正确答案；② "队列文件是追加型、大多数并发编辑不会真正冲突"这一经验判断，是本变更选择 rebase（而非更保守的"发现分叉就永远不自动处理"）的前提假设，依据是 2026-08-06 观察到的 20/20 触碰事实与队列文件历史上的编辑模式，不是形式化证明。
2. **由谁显性化？** CC 建造车间（本变更包设计与实现，独立 worktree `sweep-ffblock-fix`）；持有人 = 本次执行 session；backup/仲裁 = Shao Peishen（本变更包 design.md 须经其审核批准方可 `/opsx:apply`，per CLAUDE.md §5 固定流程第 3 步，且命中 §5"机制/工具类模块的 openspec 触发门槛"第③条"改变既有模块的对外语义"）。
3. **用什么方法提取？** 历史真实案例反推——队列 #288 记录了 2026-08-06 当日两次真实手工介入解卡的完整故障链与决定性取证（20/20 提交触碰同一文件），本变更的三种候选修法（先提交再同步再 rebase / stash 保护式 ff / 失败降级为告警但继续）均由 #288 分析产出，design.md 在其基础上选定并给出被否方案的具体理由。不涉及 LLM 判断，不适用"AI 起草·专家批改"类方法。

## 验收与晋档条件（强制，四档口径）

- **本变更包交付后场景所处档位**：本变更为**跨项目治理机制**（sweep 是全项目共用的定时任务工具，非独立业务场景），不适用四档"对客交付"口径；套用最接近的档位描述 = **档1 mock 验证**（design 审通过、代码与单测完成，但尚未经过至少一次真实主工作区端到端验证——即真实制造"本地脏队列文件 + origin 有改动同一文件的新提交"这一故障形态，确认新逻辑下 sweep 不再整轮跳过）。
- **晋下一档的条件**：晋**档2 真实数据跑通** —— ① 单测覆盖"本地脏 + origin 改动同一文件"的复现场景（含可自动 rebase 与真实冲突两种子场景）；② 在主工作区真实制造一次同形态状态，确认 sweep 正常处理批次并推送成功，不再 `SweepAbort` 整轮跳过；③ 全量回归零漂移（sweep 自身既有测试全绿，`sweep-startup-resilience`/`sweep-fork-alert`/`sweep-batch-status-classification` 三个既有 spec capability 的既有场景全部保持通过）；④ `工具-落库sweep.py` 文件头部机制说明按既有体例补充本次背景与决策，供未来维护者理解"为什么是这个顺序"。
- **价值指标**（风险型）：消除"sweep 每小时空转、队列内容持续悬空无法落库、需人工介入解卡"这一故障——基线 = 2026-08-06 当日两次真实手工介入（队列 #288，人工执行 commit+pull --rebase+push 全套操作），目标 = 同形态状态下 sweep 自动完成对齐与推送，人工介入频率降为 0（真实冲突这一少数情形除外，此时安全退化为现有分叉告警机制，不丢数据、不劣于现状）。
- **LLM 判据黄金集**：不适用（本变更不含 LLM 运行时判断，纯 git 操作控制流）。

## Impact

- 受影响代码：`0-学习与工具/工具-落库sweep.py`（`main()` 执行顺序、`_sync_master_if_behind_origin` 替换为新的对齐函数、`_process_normal_batch`/`_rerun_ledger` 拆分提交与推送职责）。
- 受影响测试：`0-学习与工具/test_工具-落库sweep.py`（新增"脏队列文件 + origin 同文件新提交"复现用例，覆盖可自动 rebase 与真实冲突两种子场景；既有测试预期全部保持通过）。
- 受影响文档：本变更包归档后，`工具-落库sweep.py` 文件头部说明段按既有体例补充本次背景；根 `CLAUDE.md` 队列 #288 行回填。
- 红线核对：mock 先行——不适用（无新数据源接入）；audit 留痕——不适用（纯 git 操作控制流修法，不涉及新增 audit 事件）；OEM 隔离——不适用；L2 人工确认门禁——不适用（sweep 是内部机制工具，不涉及对客/采购金额相关自动执行）；ISO 26262——不适用（非车规安全相关代码）。
