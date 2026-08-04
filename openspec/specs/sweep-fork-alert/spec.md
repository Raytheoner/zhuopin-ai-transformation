# sweep-fork-alert Specification

## Purpose
TBD - created by archiving change retroactive-mechanism-specs. Update Purpose after archive.
## Requirements
### Requirement: 分叉检测失败标记 is_fork 且退出码非零
落库 sweep 起跑前置检查发现本地分支与 `origin/master` 发生真实分叉（而非纯粹落后、可用 fast-forward 追上）时，SHALL 抛出携带 `is_fork=True` 的 `SweepAbort` 异常；`main()` 据此 MUST 以非零的分叉专用退出码结束本轮，不得复用其他前置检查失败（如未推送提交、编辑锁占用）共用的退出码，以避免计划任务的"成功/失败"判读把真实分叉误读为正常跳过。

#### Scenario: 分叉检测失败退出码非零
- **WHEN** 起跑前置检查判定本地分支与 `origin/master` 分叉
- **THEN** sweep 以分叉专用的非零退出码结束本轮

### Requirement: 连续分叉轮次持久化，解除后自动清零
`_handle_fork_detected` SHALL 把连续检测到分叉的轮次数持久化到 `reports/sweep-fork-state.json`，每次检测到分叉即递增该计数；分叉一旦解除（某一轮前置检查转为通过）MUST 清空该持久化计数，避免陈旧的连续轮次数字污染未来一次全新、独立分叉事件的告警文案。

#### Scenario: 连续两轮分叉计数递增
- **WHEN** 连续两轮 sweep 运行均检测到分叉
- **THEN** 第二轮的连续计数比第一轮多 1

#### Scenario: 分叉解除后计数清零
- **WHEN** 某一轮分叉状态解除（前置检查通过）
- **THEN** 持久化的连续分叉计数被清空/移除，供未来独立分叉事件重新从 0 计数

### Requirement: 告警发送失败不阻塞 sweep 正常返回
分叉告警的主动推送（经企微 webhook）SHALL 在发送失败（`.env` 凭据缺失、网络异常、webhook 拒绝等）时仅降级记入运行日志，MUST NOT 向上抛出以阻塞 `main()` 正常返回其本应返回的（分叉专用非零）退出码。

#### Scenario: 告警发送失败时 sweep 仍返回预期退出码
- **WHEN** 分叉已被检测到且告警推送本身发送失败
- **THEN** sweep 仍以分叉专用的非零退出码正常结束本轮，不因告警失败而崩溃或挂起

