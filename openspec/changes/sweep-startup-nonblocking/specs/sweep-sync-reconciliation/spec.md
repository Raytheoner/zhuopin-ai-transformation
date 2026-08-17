## Purpose

补齐收尾段在 `git fetch` 本身失败时的行为契约——此前该情形由 `_fetch()` 抛 `SweepAbort` 统一处理，`_fetch()` 去异常化后须由收尾段自行决定；且原行为会连带跳过其后一批**不依赖网络**的本地检测，与起跑段通则同因。

## ADDED Requirements

### Requirement: 收尾段 fetch 失败时降级而非中止本轮

收尾段 `_reconcile_with_origin_and_push` 的 `git fetch` 失败时 MUST NOT 中止本轮：SHALL 记录一行日志，说明本轮跳过与 `origin/master` 的对齐与推送，并在存在未推送的本地提交时于日志中给出其数量与"待下一轮推送"的明确表述；随后 MUST 正常返回，使其后的本地检测（常驻服务部署提示、部署留痕检查、openspec 覆盖与滞留检测）照常执行——这些检测均只读本地仓库，不依赖网络可用性。

本轮 SHALL 以退出码 0 结束（与本次修法前 `_fetch` 抛出的 `SweepAbort` 默认退出码一致，对外语义不变）；本地提交 MUST NOT 被撤销。

#### Scenario: 收尾段 fetch 失败时本地检测仍执行

- **WHEN** 收尾段执行 `git fetch origin master` 因网络故障失败
- **THEN** sweep 记录跳过对齐与推送的原因后正常返回，其后的部署提示、部署留痕检查与 openspec 覆盖/滞留检测照常执行，本轮以退出码 0 结束

#### Scenario: 收尾段 fetch 失败且存在未推送提交时日志显式点名

- **WHEN** 收尾段 fetch 失败，且本轮已产生 N 个尚未推送的本地提交
- **THEN** 日志中明确记录存在 N 个本地提交本轮未能推送、将由下一轮重试，而不是只记录一句 fetch 失败

#### Scenario: fetch 成功时行为不变

- **WHEN** 收尾段 `git fetch` 正常成功
- **THEN** 纯落后 / 纯领先 / 相等 / 已分叉四种关系的分派、rebase 冲突回滚与告警、末尾统一推送等既有行为完全不变
