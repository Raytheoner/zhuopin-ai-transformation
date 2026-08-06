## Purpose

定义落库 sweep 在"本地批次已提交、准备与 `origin/master` 对齐"这一时刻的行为契约：先提交后同步的顺序保证、纯落后/纯领先/已分叉三种关系各自的对齐策略、分叉时的安全回滚与告警复用、末次统一推送的原子性边界——确保"工作区必然处于待提交状态"这一 sweep 自身的核心工作前提，不再成为它对齐 `origin/master` 的阻塞源。

## ADDED Requirements

### Requirement: 批次提交先于对齐 origin/master
sweep MUST 先把本轮已判定可安全落库的批次（含遗留尾巴批次与文档台账重跑）逐个完成 `git add` 与 `git commit`（不在此阶段执行 `git push`），再尝试与 `origin/master` 对齐；MUST NOT 在任何批次提交之前尝试需要更新工作区文件的 `git merge`（含 `--ff-only`）。

#### Scenario: 队列文件同时是待提交批次的一部分与对齐目标
- **WHEN** 主工作区存在未提交的队列文件改动，且该改动已被某个 §二 批次的文件清单声明为可安全落库
- **THEN** sweep 先完成该批次的 `git commit`，使队列文件恢复"相对 HEAD 无未提交差异"，再进入对齐 `origin/master` 的步骤

### Requirement: 按本地与 origin/master 的关系分派对齐策略
sweep 在完成本轮批次提交后 SHALL 依据本地 `HEAD` 相对 `origin/master` 的关系选择对齐策略：纯落后（`HEAD` 是 `origin/master` 的祖先且不相等）时执行 `git merge --ff-only origin/master`；纯领先（`origin/master` 是 `HEAD` 的祖先且不相等）时跳过合并直接进入推送；两者相等时不执行任何合并或推送；已分叉（互不为对方祖先）时执行 `git rebase origin/master`。

#### Scenario: 纯落后时用 ff-only 合并追上
- **WHEN** 本轮批次提交完成后，本地 `HEAD` 是 `origin/master` 的祖先（纯落后）
- **THEN** sweep 执行 `git merge --ff-only origin/master` 追上，不进入 rebase 分支

#### Scenario: 纯领先时跳过合并直接推送
- **WHEN** 本轮批次提交完成后，`origin/master` 是本地 `HEAD` 的祖先（纯领先，origin 无新提交）
- **THEN** sweep 不执行任何合并操作，直接进入推送步骤

#### Scenario: 已分叉时改用 rebase
- **WHEN** 本轮批次提交完成后，本地 `HEAD` 与 `origin/master` 互不为对方祖先（已分叉）
- **THEN** sweep 执行 `git rebase origin/master`，而不是重试 `git merge --ff-only`

### Requirement: rebase 冲突时安全回滚且不丢失本地提交
`git rebase origin/master` 失败（存在无法自动合并的冲突）时，sweep MUST 执行 `git rebase --abort` 使仓库回到 rebase 前的本地提交状态（本轮已完成的批次提交必须完整保留，不被撤销、不丢失内容），MUST NOT 尝试自动解决冲突或强制推送；随后 MUST 复用既有分叉告警机制（`is_fork` 标记、`FORK_EXIT_CODE`、webhook 通知、连续轮次持久化）以本轮结束。

#### Scenario: rebase 冲突后本地提交完整保留
- **WHEN** `git rebase origin/master` 因真实内容冲突失败
- **THEN** sweep 执行 `git rebase --abort`，本轮批次提交（`git log` 可见的 commit）保持完整存在，不被回滚或丢弃

#### Scenario: rebase 冲突复用既有分叉告警
- **WHEN** `git rebase origin/master` 失败且已执行 `git rebase --abort`
- **THEN** sweep 以携带 `is_fork=True` 的方式结束本轮，触发既有 webhook 分叉告警通道与连续轮次持久化，退出码使用既有 `FORK_EXIT_CODE`

### Requirement: 本轮末尾统一推送一次
sweep SHALL 在对齐步骤（ff-only 合并或 rebase）成功后，把本轮全部新增的本地提交（批次提交、遗留尾巴批次提交、文档台账重跑提交）合并为一次 `git push`，MUST NOT 为每个批次或台账重跑各自单独推送。

#### Scenario: 多个批次一次性推送
- **WHEN** 本轮处理了多个 §二 批次且均已在本地提交成功
- **THEN** sweep 在对齐 `origin/master` 成功后只执行一次 `git push`，覆盖本轮全部批次的提交

#### Scenario: 推送失败不撤销已完成的提交
- **WHEN** 对齐成功后的统一推送因网络或权限原因失败
- **THEN** sweep 不撤销本轮已完成的本地提交，以既有"本地提交不会被撤销，需人工核查"语义结束本轮
