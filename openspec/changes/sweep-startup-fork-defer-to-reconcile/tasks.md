## 1. 单测先行（须含真实故障场景复现）

- [x] 1.1 新增复现用例：本地已有一个此前提交但未推送的提交，且 origin 同期被推进（两侧改动互不冲突），同时本轮存在一条真正待处理的 §二 批次——验证 sweep 不在起跑段整轮中止，批次正常本地提交，收尾段自动 `git rebase` 对齐并统一推送成功，退出码 0（`StartupGuardDoesNotBlockBatchProcessingTests.test_divergent_startup_state_does_not_abort_before_batch_processing`）。
- [x] 1.2 新增 `--dry-run` 场景：同上前提，验证 dry-run 模式下同样只记录日志、不提前中止（`StartupGuardDoesNotBlockBatchProcessingTests.test_dry_run_still_reports_divergence_without_aborting`）。
- [x] 1.3 更新既有 `ForkAlertTests._diverge()`：此前两侧改动落在各自独立文件（互不冲突），在新逻辑下会被收尾段自动 rebase 解决、不再触发本告警族要验证的路径；改为两侧冲突同一份文件的同一处内容，确保 rebase 必然失败、告警族仍能验证到"真正无法自动解决"分支。
- [x] 1.4 更新既有 `SyncBehindOriginTests.test_diverged_from_origin_master_skips_without_forcing`：同 1.3 的理由，改用真实冲突构造；用例改名为 `test_diverged_with_genuine_conflict_still_ends_in_fork_alert_via_reconcile`，断言与文案同步更新为收尾段的失败措辞（"自动 rebase 失败"），如实记录触发路径已变化（起跑段直接中止 → 收尾段 rebase 失败后中止），但最终可观察结果（`FORK_EXIT_CODE`、本地 HEAD 与 origin 均不变）与此前等价。
- [x] 1.5 回归既有测试：确认 `sweep-fork-alert`（告警发送/连续升级/解除重置）、`sweep-sync-reconciliation`（#288 的 ff-only/纯领先/rebase 三分支）、`sweep-batch-status-classification`（#248 状态列判据）在本次改动下行为不变。

## 2. 实现

- [x] 2.1 `_push_any_unpushed_commits` 分叉分支改为记录日志后 `return`，不再 `SweepAbort`；日志文案须明确说明"本轮不在此处提前中止，继续处理待落库批次，分叉对齐交给收尾段统一处理"。
- [x] 2.2 "可快进"分支（存在未推送提交且 origin/master 是 HEAD 祖先）保持不变，仍在起跑段直接尝试补推。
- [x] 2.3 更新函数 docstring，补充队列 #309 子项 F 背景与"与 #288 同构复发"的说明，指针指向本变更包 design.md。

## 3. 文档

- [x] 3.1 `工具-落库sweep.py` 文件头部机制说明按既有体例追加本次修法段落（背景、根因、修法、与 #288 的关系）。
- [x] 3.2 队列 #309 行子项 F 回填：修法定案、被否方案（B/C）及理由指针、测试数、真实验证证据。

## 4. 验证

- [x] 4.1 全量回归：`工具-落库sweep.py` 自身既有测试套件全绿，零漂移（125 passed，含 4 个新增/改写用例）。
- [x] 4.2 真实主工作区验证：见下方「真实验证」节。

## 5. 收工

- [x] 5.1 `/opsx:archive sweep-startup-fork-defer-to-reconcile -y`（tasks 全部勾选后当场归档，不拖延）。
- [x] 5.2 队列 §二 登记待 commit 批次，文件清单含队列文件自身。
- [x] 5.3 commit + push；收工重跑一次文档台账。
- [x] 5.4 worktree 收工自删；删不掉则 `git worktree prune` 并如实登记待清。

## 真实验证（如实记录）

主工作区 2026-08-08 当日已发生一次真实故障（本地 `e3e7f34` ／ origin `2ae585f` 分叉，sweep 连续 4 轮整轮跳过），本次修法上线前已由本 session 在主工作区手工解卡（commit + rebase + push，见队列 #309 主行）——**该次解卡发生在本修法之前，不构成对本修法本身的验证**。本修法合入主工作区后，额外用一个真实的临时旁路 clone 向 origin 推送一个非冲突的真实小改动，制造"主工作区本地已有未推送提交 + origin 同期被推进"的真实分叉状态，随后在主工作区触发一次真实（非 `--repo-root` 覆盖）的 `python 0-学习与工具/工具-落库sweep.py`，验证其不再在起跑段整轮中止、批次/台账改动正常本地提交并由收尾段自动 rebase 对齐推送成功，退出码 0，无需人工介入——过程与结果见 CLAUDE.md 队列 #309 行回填。真实冲突（无法自动解决）这一子场景本次未在主工作区额外构造真实案例（同 #288 4.3 的既有权衡：需要精确控制两个 checkout 同时改动同一行文本、且会产生一次真实分叉告警 webhook 推送，风险大于收益），该分支已由单测（`ForkAlertTests`／`SyncBehindOriginTests.test_diverged_with_genuine_conflict_still_ends_in_fork_alert_via_reconcile`，真实 git 子进程、真实临时仓库，非 mock）完整覆盖。
