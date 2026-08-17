## Purpose

补齐 `工具-落库sweep.py` 起跑段的**中止判据通则**：起跑段的每一处 `SweepAbort` 位点须显式登记并按统一判据分类，默认降级为"记录后继续"，只有"仓库物理状态不可用"才允许整轮中止；并据此把网络类失败（fetch／补推）从整轮中止改为降级。

## ADDED Requirements

### Requirement: 起跑段中止位点须显式登记且默认降级

sweep 起跑段（`_heal_stale_index_lock`／`_assert_not_a_linked_worktree`／`_check_preconditions`／`_abort_if_edit_lock_held`／`_push_any_unpushed_commits`／`_fetch`，即 `main()` 内批次处理开始之前执行的全部检查）内的每一处 `raise SweepAbort` MUST 被登记进一份冻结清单，且清单内每一项 MUST 附一行判定理由。

判定 SHALL 依据统一判据：**一处起跑段检查是否该中止整轮，取决于它挡住的那些本地工作是否真的依赖它所检查的那个前提**——依赖（仓库物理状态不可用，继续会失败或有害）则 MAY 中止；不依赖（外部依赖暂时不可用，本地工作与之无关）则 MUST NOT 中止，SHALL 记录一行日志后继续本轮其余流程，并把该前提的职责移交给真正需要它的那一段。

该清单 MUST 由一条自动化检查以静态语法树（AST）解析源码得出的实际位点集合比对；实际位点与清单不一致（新增、删除或位置改动）时该检查 MUST 失败。该检查 MUST NOT 以正则匹配源码文本的方式实现——注释、字符串字面量与跨行调用会使正则给出假阴性。

#### Scenario: 新增未登记的起跑段中止位点被拦下

- **WHEN** 有人在起跑段任一函数内新增一处 `raise SweepAbort`，但未同步更新冻结清单
- **THEN** 自动化检查失败并指出该位点未登记，强制作者按统一判据显式分类为"维持拦截"或"降级"

#### Scenario: 删除已登记的中止位点同样被拦下

- **WHEN** 有人删除起跑段某处已登记的 `raise SweepAbort`，但未同步更新冻结清单
- **THEN** 自动化检查失败并指出清单中存在实际已不存在的位点

#### Scenario: 注释或字符串中出现同名文本不产生误报

- **WHEN** 起跑段函数的 docstring 或注释中出现 `raise SweepAbort` 字样，但并非真实语句
- **THEN** 自动化检查不将其计为位点，检查通过

### Requirement: 起跑段网络失败不得整轮中止

`_fetch()` MUST NOT 抛出 `SweepAbort`；`git fetch` 失败时 SHALL 记录一行含所处阶段与 git stderr 的日志并向调用方返回失败，由调用方决定后续。

起跑段 `_push_any_unpushed_commits` 内的 fetch 失败时 MUST NOT 中止本轮，SHALL 记录后跳过本次补推并继续执行本轮其余流程（含 §二 批次处理、台账重跑、锁忙暂存 flush、孤儿告警与 openspec 覆盖检测）——这些流程均不依赖网络可用性；补推职责移交收尾段 `_reconcile_with_origin_and_push`。

起跑段补推自身失败（`git push` 非零退出）时同样 MUST NOT 中止本轮，SHALL 记录后继续；本地提交 MUST NOT 被撤销，推送重试交由收尾段执行，收尾段推送失败时仍以既有"本地提交不会被撤销，需人工核查"语义与退出码收尾。

#### Scenario: 网络不可用时批次仍正常落库

- **WHEN** sweep 起跑时 `git fetch origin master` 因网络故障失败，且本轮 §二 存在待处理批次
- **THEN** sweep 记录一行 fetch 失败日志后继续本轮，待处理批次正常完成本地提交与销行，台账正常重跑，本轮不因该网络失败而以整轮跳过结束

#### Scenario: 网络不可用时孤儿告警与 openspec 检测仍执行

- **WHEN** sweep 起跑时 fetch 失败，且本轮 §二 无任何待处理批次
- **THEN** sweep 仍执行锁忙暂存 flush、孤儿脏文件追踪告警与 openspec 覆盖/滞留检测，不因该网络失败而跳过

#### Scenario: 起跑段补推失败不中止本轮

- **WHEN** 起跑段检测到存在可快进的未推送提交，但 `git push` 因网络或鉴权失败
- **THEN** sweep 记录该失败后继续本轮其余流程，本地提交完整保留，推送由收尾段重试

## MODIFIED Requirements

### Requirement: 起跑段无条件补推未推送提交

sweep MUST 在每轮起跑时无条件检查本地 `HEAD` 相对 `origin/master` 是否存在未推送提交（`git rev-list --count origin/master..HEAD`），不得仅在"§二 有无待处理批次"为真时才检查；存在且可快进时 SHALL 尝试补推。

本函数 MUST NOT 以任何路径中止整轮：不可快进（已分叉）时、fetch 失败时、补推自身失败时，均 SHALL 记录一行日志说明本轮不在此处提前中止，并继续执行本轮其余流程（含 §二 批次处理），把分叉的最终判定、自动对齐尝试、推送重试与告警职责统一移交给收尾段（`sweep-sync-reconciliation` capability 定义的 `_reconcile_with_origin_and_push`）。

fetch 失败时 SHALL 跳过本次补推尝试（不依据可能陈旧的 `origin/master` 引用做推送判断），直接继续本轮其余流程。

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

#### Scenario: fetch 失败时跳过补推判断而非依据陈旧引用

- **WHEN** 起跑段 fetch 失败，本地存在未推送提交
- **THEN** sweep 不依据未刷新的 `origin/master` 引用计算 ahead 或执行推送，记录后直接进入本轮其余流程
