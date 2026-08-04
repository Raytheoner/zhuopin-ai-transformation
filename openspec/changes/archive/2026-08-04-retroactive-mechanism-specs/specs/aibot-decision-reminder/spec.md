## ADDED Requirements

### Requirement: 判据仅为"新增"或"超期"，禁止"存在即提醒"
`evaluate_candidates` SHALL 仅在候选项满足以下条件之一时生成提醒：① 该项此前从未被记录为"已见过"（首次出现）；② 该项已达"超期"判据——队列 §四行超过其 `deadline_cell` 标明的日期仍未标注 `✅`，或队列 §一 P0/P1 待领行的登记日期距今已超过 `min_priority_pending_age_days` 天。对"一直存在、状态无变化"的项 MUST NOT 重复生成提醒。

#### Scenario: 首次出现的候选立即提醒
- **WHEN** 队列 §四新增一行开放项，此前未被记录在已见集合中
- **THEN** `evaluate_candidates` 将其纳入本轮候选，`reason` 标注为"新增"

#### Scenario: 长期存在但未超期且非首见的项不重复提醒
- **WHEN** 某 §四开放行此前已被记录为"已见过"，且未超过其截止日期
- **THEN** `evaluate_candidates` 不将其纳入本轮候选

#### Scenario: 超过截止日期的§四行触发提醒
- **WHEN** 某 §四开放行的 `deadline_cell` 日期早于今天且未标注 `✅`
- **THEN** `evaluate_candidates` 将其纳入候选，`reason` 标注为"已过截止"

### Requirement: 按递减间隔升级去重，同一项不重复轰炸
同一提醒项（以 `§四#<row_id>` 或 `§一#<row_id>` 为键）SHALL 按 `ESCALATION_INTERVALS_DAYS`（0/3/7 天）确定下一次允许再次提醒的最早时间：首次提醒后至少间隔 3 天才允许第二次，第二次后至少间隔 7 天才允许第三次及以后。在未达间隔前 MUST NOT 重复发送同一项的提醒。

#### Scenario: 同一项在去重窗口内不重复发送
- **WHEN** 某提醒项已在今天被提醒过一次
- **THEN** 同一天内再次评估该项不会重复生成提醒

#### Scenario: 超过当前间隔后允许再次提醒
- **WHEN** 某提醒项自上次提醒已过去的天数达到或超过其当前档位对应的间隔天数
- **THEN** 该项可再次被纳入候选并生成提醒，随后升级到下一档间隔

### Requirement: 主通道失败降级独立 webhook，不阻断调用方流程
`send_decision_reminder` SHALL 在主通道（企微机器人私信）发送失败时，若调用方提供了 `fallback_send`，尝试经独立群 webhook 通道兜底发送一次。无论主通道、备用通道是否成功，本函数 MUST NOT 向调用方抛出未捕获异常，以保证巡逻收工流程或每日定时任务不因告警发送本身失败而中断。

#### Scenario: 主通道失败时走 webhook 兜底成功
- **WHEN** 企微机器人私信发送抛出异常，且提供了有效的 `fallback_send`
- **THEN** 函数改为调用 `fallback_send` 发送，不向调用方抛出异常

#### Scenario: 主备双失败仍不阻断调用方流程
- **WHEN** 企微机器人私信发送与 `fallback_send` 均抛出异常
- **THEN** 函数正常返回（不抛出异常），调用方可继续其后续流程
