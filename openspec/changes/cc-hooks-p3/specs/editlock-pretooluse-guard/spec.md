## ADDED Requirements

### Requirement: PreToolUse SHALL 拦截无有效锁的队列/接力卡写入

当 `PreToolUse` 事件的 `tool_name` 为 `Edit`／`Write`／`MultiEdit`，且 `tool_input.file_path`（或 `notebook_path`）解析后的绝对路径命中以下清单任一项时，钩子 SHALL 检查队列编辑锁（`工具-共享文档编辑锁.py` 的锁文件）是否存在**有效（未陈旧）**记录；不存在或已陈旧 MUST `exit 2` 拒绝本次调用，反馈提示先执行 `acquire`。

受保护清单：
- `1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md`
- `1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md`
- `1-转型规划/0-全景路线图/跨桌任务队列.md`
- `1-转型规划/0-全景路线图/session接力-Phase1收口.md`
- `1-转型规划/0-全景路线图/session接力-业务总线.md`

"陈旧"的判定阈值 MUST 与 `工具-共享文档编辑锁.py::STALE_MINUTES` 保持一致（读取同一常量或同一份锁文件的 `held_since` 字段自行计算，MUST NOT 硬编码第二份数值）。

判定 MUST NOT 校验锁的持有者身份（`who`）与当前会话是否一致——只判"是否存在任一有效锁"（见 design 决策点 3，身份匹配需要跨进程状态、成本与收益不成比例）。

#### Scenario: 无锁时编辑队列文件被拦
- **WHEN** `Edit` 目标为机制环境队列文件，且锁文件不存在
- **THEN** `exit 2`，反馈含"先执行 acquire"字样

#### Scenario: 锁陈旧时仍视为无效
- **WHEN** 锁文件存在但 `held_since` 距今超过 `STALE_MINUTES`
- **THEN** `exit 2`

#### Scenario: 有效锁存在时放行
- **WHEN** 锁文件存在且未陈旧（不论 `who` 是否为当前会话）
- **THEN** 放行，`exit 0`

#### Scenario: 非受保护文件不拦
- **WHEN** `Edit` 目标是任意场景 `CLAUDE.md` 或其它非清单内文件
- **THEN** 放行，不检查锁

### Requirement: 钩子 SHALL fail-open 且留痕

锁文件读取或解析异常 MUST 视为"无法判定"，MUST `exit 0` 放行（不得因钩子自身故障阻塞正常编辑），并将异常摘要写入 `reports/hooks-audit.jsonl`。

每次触发（含放行、含拦截）SHALL 追加一行审计记录，含 `verdict`（`pass`／`violation`／`error`）、`tool`、`target`、`sessionId`。

#### Scenario: 锁文件损坏
- **WHEN** 锁文件内容不是合法 JSON
- **THEN** `exit 0` 放行，审计记录 `verdict=error`

#### Scenario: 拦截留痕可核验
- **WHEN** 一次调用被 `exit 2` 拦截
- **THEN** `reports/hooks-audit.jsonl` 新增一行 `verdict=violation`，含目标路径
