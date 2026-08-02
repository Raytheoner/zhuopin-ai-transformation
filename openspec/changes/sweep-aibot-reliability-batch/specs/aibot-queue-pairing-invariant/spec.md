## Purpose

定义企微机器人锁忙推迟补录事件与 #107 哨兵（`find_unreconciled_archives`）配对判据之间必须保持一致的不变式，确保"每条 `archived` 事件必有配对的写队列成功事件"这一断言在补录路径下同样成立。

## ADDED Requirements

### Requirement: 补录成功事件必须被哨兵识别为已配对
当消息因编辑锁占用被推迟、其内容通过 `pending_queue_lock_appends.jsonl` 补录成功写入队列文件后，哨兵 `find_unreconciled_archives` MUST 能够将该补录成功事件识别为与对应的 `archived` 事件配对，不得将其判定为"未配对"。

#### Scenario: 推迟补录后哨兵零误报
- **WHEN** 一条消息先产生 `archived` 事件（归档成功），随后因编辑锁占用被推迟写队列、暂存进 `pending_queue_lock_appends.jsonl`，再经 sweep 下一轮 flush 补录成功（写入 `queue_append_pending_flushed` 事件）
- **THEN** 哨兵扫描审计流时必须将该 `archived` 事件识别为已配对，不得将其计入"未配对"清单

### Requirement: 配对判据变更需回归既有正常路径
恢复配对不变式的实现方式（无论是让补录事件额外记一条 `queue_appended`，还是让哨兵直接识别 `queue_append_pending_flushed` 为配对事件之一）SHALL NOT 改变现有"正常写入（未经推迟）→ `archived` + `queue_appended` 配对"路径的既有行为与既有测试断言。

#### Scenario: 未经推迟的正常路径不受影响
- **WHEN** 一条消息正常写队列成功（未触发编辑锁占用推迟）
- **THEN** 哨兵对该消息的配对判定结果与本变更实施前完全一致
