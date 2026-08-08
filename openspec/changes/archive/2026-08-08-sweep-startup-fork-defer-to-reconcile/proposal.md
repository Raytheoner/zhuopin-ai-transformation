# sweep-startup-fork-defer-to-reconcile Proposal

## Why

`工具-落库sweep.py::main()` 起跑段②调用的 `_push_any_unpushed_commits`（队列 #194）在发现"本地领先且不可快进"（已分叉）时，直接 `SweepAbort(is_fork=True, exit_code=FORK_EXIT_CODE)`——该检查排在 §二 批次处理（main() 主体）与收尾段 `_reconcile_with_origin_and_push`（队列 #288 新增、自带 `git rebase origin/master` 能力）**之前**，整轮在此处退出，批次处理与收尾对齐都走不到。

这与队列 #288 当初治的 `_sync_master_if_behind_origin`（旧代码，排在批次处理之前、`git merge --ff-only` 要求工作区干净）是**完全同构的错误**：一个排在批次处理之前、发现"需要对齐"就整轮退出的前置检查，挡住了排在批次处理之后、真正有能力完成对齐的收尾逻辑。#288 只修复了自己撞见的那一处（`_sync_master_if_behind_origin`），没有把"起跑段检查不得整轮 return"立为通则，导致同一形态在 `_push_any_unpushed_commits` 上复发。

2026-08-08 02:35 UTC 起，本地（环境总线的队列文档提交）与 origin（CC 平台 #300 修复推送）两侧均改了 `跨桌任务队列.md`，sweep 连续 4 轮在此处整轮跳过、连发 4 条分叉告警，期间已登记的 §二 批次（含本次故障自身的登记批次）始终落不了库，需人工介入（手工 commit + rebase + push）解卡。详见跨桌任务队列 #309 子项 F。

## What Changes

- **`_push_any_unpushed_commits` 发现分叉时不再 `SweepAbort`**：改为记录一行日志（说明本轮不在此处提前中止，对齐交给收尾段）后直接 `return`，让 `main()` 继续往下走完批次处理（§二 待 commit 批次照常提交）。
- **分叉的最终判定与告警职责，统一收敛到收尾段 `_reconcile_with_origin_and_push`**：批次全部本地提交、工作区恢复干净后，该函数重新 `fetch` 一次并按当时的 `ahead`/`behind` 关系自动 `git rebase origin/master`；绝大多数不冲突的并发编辑（同 #288 的既有观察——队列文件是追加型文件，不同会话通常编辑不同行）可自动对齐并推送成功；只有真实内容冲突时才会走既有的 `git rebase --abort` + 分叉告警路径（`is_fork=True`／`FORK_EXIT_CODE`），语义与此前完全一致，只是判定时机从"起跑段一律拦"收窄为"收尾段确认真无法自动解决才拦"。
- **`_push_any_unpushed_commits` 在"可快进"这条既有分支上保持不变**：存在未推送提交且 origin/master 是其祖先（纯落后于 HEAD 领先关系）时，仍在起跑段直接尝试补推，成功则继续、失败则 `SweepAbort(exit_code=2)`——这条路径与本次改动的场景（已分叉）无关，不改动。
- **BREAKING**：无对外可见的破坏性变化。对使用方（值周巡检读 `reports/sweep-commit.log`、企微 webhook 告警）而言，唯一可观察差异是：此前"起跑即发现分叉"必然导致本轮零批次处理、退出码固定 `FORK_EXIT_CODE`；此后同一起始状态下，只要新增的批次改动与 origin 侧改动不冲突，本轮会正常完成批次落库、退出码为 0，分叉告警不再触发（因为它已被自动解决，不再是需要人工介入的情形）。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `sweep-startup-resilience`：「起跑段无条件补推未推送提交」Requirement 下的「非快进时不强推」Scenario，其描述的"发现分叉即以非 0 退出码结束本轮"这一行为，改为"发现分叉时记录日志并继续本轮其余流程，最终是否以非 0 退出码结束交由收尾段 `_reconcile_with_origin_and_push`（`sweep-sync-reconciliation` capability，2026-08-06 已定义，不改）判定"。`sweep-sync-reconciliation`／`sweep-fork-alert` 两个既有 capability 的 REQUIREMENTS 本身不改变（分叉告警的触发条件、文案、退出码语义均沿用其既有定义，只是触发时机的落点从"起跑段"部分场景收窄为"收尾段"）。

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

1. **本流程哪些判断是人脑默会经验？** 一处：判断"一个前置检查该不该在发现异常时整轮 SweepAbort"这一设计模式是否安全，依赖的默会经验是"检查排在能修复该异常的逻辑之前，就会把修复逻辑挡住"——这条经验在 #288 已被应用过一次（`_sync_master_if_behind_origin`），本次是**同一条经验被重新应用到第二个具体位置**，不是新发现的经验，而是"经验未被泛化为通则、需要人在每个新位置重新想起"这一遗留问题的直接体现。
2. **由谁显性化？** CC 建造车间（独立 worktree `sweep-startup-guard-fix`，队列 #309 子项 F 授权"具体方案交 CC 定"）；backup/仲裁 = Shao Peishen（design.md 已完整记录判断依据与被否选项，供事后审核；因本次是对已获批准的 #288 设计决策的直接同构延伸、且属队列 #309 明确授权 CC 自行判断具体实现方案的范围，未额外发起新一轮 design 审批等待，事后如实登记供复核）。
3. **用什么方法提取？** 直接复用 #288 design.md 已完成的分析（三个候选修法的取舍、"打破自锁循环 vs 止血少数情形"的结论），本次不重新做候选枚举——因为要解决的问题结构与 #288 完全相同（前置检查 vs 后置修复的位置关系），候选空间与结论也必然相同，重新枚举只会得到同一组候选与同一个选择，属实质重复。

## 验收与晋档条件（强制，四档口径）

- **本变更包交付后场景所处档位**：跨项目治理机制（同 #288，不适用四档"对客交付"口径）；套用最接近的档位描述 = **档2 真实数据跑通**（design 已定案、代码与单测完成、且已具备真实场景端到端验证条件——2026-08-08 02:35 UTC 起的连续 4 轮真实故障即为本次修法要解决的真实场景，主工作区解分叉本身已是一次真实验证前提；本次修法上线后下一次真实分叉即是持续验证）。
- **晋下一档的条件**：晋**档3 稳定运行** —— 观察至少一次真实生产环境下的分叉场景（不冲突可自动解决 或 真实冲突需人工介入两类之一），确认新逻辑按预期分派，且未引入新的静默失败模式。
- **价值指标**（风险型）：消除"起跑段前置检查在能自动解决的场景下也整轮拦截批次处理"这一故障——基线 = 2026-08-08 当日连续 4 轮真实整轮跳过（队列 #309 子项 F），目标 = 同形态状态下大多数场景（不冲突并发编辑）批次正常落库、退出码 0，真实冲突场景仍安全退化为既有分叉告警，不丢数据、不劣于现状。
- **LLM 判据黄金集**：不适用（本变更不含 LLM 运行时判断，纯 git 操作控制流）。

## Impact

- 受影响代码：`0-学习与工具/工具-落库sweep.py`（`_push_any_unpushed_commits` 分叉分支的处理方式）。
- 受影响测试：`0-学习与工具/test_工具-落库sweep.py`（新增 `StartupGuardDoesNotBlockBatchProcessingTests` 复现"分叉但不冲突、有待处理批次"场景；`ForkAlertTests._diverge()` 与 `SyncBehindOriginTests.test_diverged_from_origin_master_skips_without_forcing` 两处既有真分叉断言改用"两侧冲突同一处内容"构造，确保在新的分派时机下仍能验证到真正的"无法自动解决"分支）。
- 受影响文档：`工具-落库sweep.py` 文件头部说明段按既有体例追加本次背景；根 `CLAUDE.md` 队列 #309 行回填。
- 红线核对：mock 先行——不适用（无新数据源接入）；audit 留痕——不适用（纯 git 操作控制流修法）；OEM 隔离——不适用；L2 人工确认门禁——不适用（sweep 是内部机制工具）；ISO 26262——不适用（非车规安全相关代码）。
