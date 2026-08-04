## ADDED Requirements

### Requirement: 固定周期覆写独立存活戳，与审计事件流物理隔离
`run_liveness_heartbeat` SHALL 每 `interval_seconds`（默认 300 秒）覆写一次独立的存活戳文件（单文件整体覆写，非追加），内容为写入时刻的 UTC 时间戳；新进程启动时 MUST 立即写一次，不必等满一个完整周期。该心跳 MUST NOT 写入审计 JSONL 哈希链——运行状态心跳与 IATF 可追溯的 AI 决策审计是两类不同性质的记录，物理隔离存放。

#### Scenario: 心跳周期性覆写存活戳文件
- **WHEN** `run_liveness_heartbeat` 已运行超过一个 `interval_seconds` 周期
- **THEN** 存活戳文件的 `alive_at` 字段被更新为最近一次写入时刻

#### Scenario: 心跳不出现在审计文件中
- **WHEN** 心跳运行任意时长
- **THEN** 审计 JSONL 文件中不出现由心跳产生的记录

### Requirement: 存活戳读取失败静默降级，不抛出异常
`read_liveness` SHALL 在存活戳文件不存在、内容无法解析为 JSON、或缺少必需字段/时间格式非法时返回 `None`，MUST NOT 抛出异常。调用方（如断连时长判据）据此视同"无存活戳可比对"，回落到相应的首次运行处理逻辑。

#### Scenario: 存活戳文件不存在时返回 None
- **WHEN** 存活戳文件路径不存在
- **THEN** `read_liveness` 返回 `None`，不抛出异常

#### Scenario: 存活戳内容损坏时返回 None
- **WHEN** 存活戳文件内容不是合法 JSON，或缺少 `alive_at` 字段，或该字段不是合法的 ISO 时间格式
- **THEN** `read_liveness` 返回 `None`，不抛出异常

### Requirement: 心跳写入失败不中断服务主流程
心跳写入失败（如磁盘满、权限不足）MUST NOT 中断长连接等服务主流程；调用方提供 `audit` 实例时，`run_liveness_heartbeat` SHALL 记一条 `liveness_heartbeat_write_failed` 事件留痕，随后继续下一轮心跳循环。

#### Scenario: 写入失败时服务继续运行并留痕
- **WHEN** 某一轮心跳写入抛出 `OSError`，且提供了 `audit` 实例
- **THEN** 记录一条 `liveness_heartbeat_write_failed` 审计事件，心跳循环不中断、继续下一轮
