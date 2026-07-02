# srm-rate-limiting Specification

## Purpose
TBD - created by archiving change platform-hardening-p2. Update Purpose after archive.
## Requirements
### Requirement: 进程级令牌桶限流（1 req/30s per endpoint）
`XkySrmConnector` SHALL 对每个 API endpoint 维护进程级令牌桶（类变量，多实例共享），速率上限 1 token/30s（与携客云"同账号 30s 内不重复"限制对齐）。`_post()` 在发送请求前 MUST 消耗令牌；无令牌时阻塞等待至令牌恢复，不抛异常，不立即重发。

#### Scenario: 首次请求立即通过
- **WHEN** 桶初始满，调用 `_post(path, body)`
- **THEN** 请求立即发出，无等待

#### Scenario: 30s 内重复请求被限速
- **WHEN** 同 endpoint 在 30s 内发出第二次请求
- **THEN** 第二次请求等待至令牌恢复后才发出（不提前发送）

#### Scenario: 多实例共享同一桶
- **WHEN** 同进程内创建两个 `XkySrmConnector` 实例并并发调用同一 endpoint
- **THEN** 两次调用合计遵守 1 req/30s 限制，不出现并发超限

### Requirement: 900301 错误码指数退避重试
`XkySrmConnector._post()` SHALL 在收到错误码 `900301`（携客云限流）时触发指数退避：额外 sleep `30 * 2^(attempt-1)` 秒（attempt 从 1 开始），最多重试 3 次，超限后抛 `RateLimitError`，不静默丢失请求。

#### Scenario: 900301 触发退避重试
- **WHEN** SRM 返回错误码 `900301`
- **THEN** 连接器等待退避时长后重试，退避时长逐次翻倍

#### Scenario: 三次重试后抛出 RateLimitError
- **WHEN** 连续三次 900301 后仍失败
- **THEN** 抛出 `RateLimitError`，不返回 None / 不静默

### Requirement: 查询跨度不超过 60 天
`XkySrmConnector.get_receive_board()` SHALL 在传入 `start_date`/`end_date` 时校验日期跨度 ≤60 天（携客云硬性限制），超限时抛 `ValueError` 而非静默截断或发出必定失败的请求。

#### Scenario: 跨度超限时抛 ValueError
- **WHEN** `end_date - start_date > 60 天`
- **THEN** 抛出 `ValueError("SRM 查询跨度超过 60 天限制")`，不发出 HTTP 请求

#### Scenario: 跨度恰好 60 天时正常通过
- **WHEN** `end_date - start_date == 60 天`
- **THEN** 正常发出请求，无异常

