## MODIFIED Requirements

### Requirement: 起跑段无条件补推未推送提交
sweep MUST 在每轮起跑时无条件检查本地 `HEAD` 相对 `origin/master` 是否存在未推送提交（`git rev-list --count origin/master..HEAD`），不得仅在"§二 有无待处理批次"为真时才检查；存在且可快进时 SHALL 先补推成功后再继续本轮其余流程；不可快进（已分叉）时 MUST NOT 在此处 `SweepAbort` 整轮中止——SHALL 记录一行日志说明本轮不在此处提前中止，并继续执行本轮其余流程（含 §二 批次处理），把分叉的最终判定、自动对齐尝试与告警职责统一移交给收尾段（`sweep-sync-reconciliation` capability 定义的 `_reconcile_with_origin_and_push`）。

#### Scenario: 提交成功推送失败，下一轮自动补推
- **WHEN** 上一轮 sweep 已在本地完成 commit 但 push 因网络等原因失败
- **THEN** 下一轮 sweep 起跑时必须检测到该未推送提交并尝试补推，补推成功后继续正常批次处理

#### Scenario: 非快进时不强推
- **WHEN** 本地 HEAD 与 origin/master 已分叉（互不为祖先）
- **THEN** sweep 不得在 `_push_any_unpushed_commits` 处强推或 `SweepAbort`，MUST 记录日志后继续执行本轮其余流程（含 §二 批次处理），分叉是否最终导致本轮以非 0 退出码结束，由收尾段的对齐尝试结果决定，而不是在此处一律以非 0 退出码结束

#### Scenario: 分叉但可自动对齐时批次仍正常落库
- **WHEN** 本地 HEAD 与 origin/master 已分叉，且本轮存在待处理的 §二 批次，且分叉双方的改动互不冲突
- **THEN** sweep 完成批次本地提交后，由收尾段自动 `git rebase origin/master` 对齐并统一推送成功，本轮以退出码 0 结束，不触发分叉告警

#### Scenario: 分叉且真实冲突时仍以既有告警语义结束
- **WHEN** 本地 HEAD 与 origin/master 已分叉，且分叉双方的改动存在真实内容冲突（无法自动合并）
- **THEN** 收尾段执行 `git rebase --abort` 回滚，sweep 以 `is_fork=True`、`FORK_EXIT_CODE` 结束本轮，触发既有 webhook 分叉告警通道与连续轮次持久化，语义与本次修法前完全一致
