## Purpose

跨桌任务队列.md 表格解析中"转义（半角竖线↔全角替代）"与"列数校验"两类判据的权威实现——供项目内多个消费者（编辑锁/sweep/队列查询/文档台账/队列结构lint/wecom-aibot-service 等）复用，取代此前 7 处各自独立实现的历史状态（详见队列 #306）。

## Requirements

### Requirement: 权威列数常量
`zhuopin_platform.shared_tools.queue_table` SHALL 提供 `SECTION_COLUMN_COUNTS` 常量，值为 `{"一": 8, "二": 4, "四": 4}`，作为跨桌任务队列.md 各分区标准列数的唯一权威来源。

#### Scenario: 消费者读取权威列数常量
- **WHEN** 某消费者需要判断一行是否符合分区标准列数
- **THEN** 该消费者 SHALL 引用 `queue_table.SECTION_COLUMN_COUNTS[label]` 而非本地重新定义该常量

### Requirement: 裸竖线检测
`queue_table` SHALL 提供 `has_bare_pipe(cell)` 函数，检测字段值中是否含半角竖线 `|`；检测 SHALL NOT 对反引号包裹的片段做豁免。

#### Scenario: 检测未转义的裸竖线
- **WHEN** 调用 `has_bare_pipe("a|b")`
- **THEN** 返回 `True`

#### Scenario: 反引号包裹不豁免
- **WHEN** 调用 `has_bare_pipe("`a|b`")`
- **THEN** 返回 `True`（不因反引号包裹而判定为安全）

### Requirement: 转义工具函数
`queue_table` SHALL 提供 `escape_bare_pipe(text)` 函数，将半角竖线 `|` 替换为全角 `／`（与队列 #164 已确立的转义口径一致）。本函数 SHALL NOT 被用于替代 `append-row` 路径"拒绝含裸竖线字段值"的既定设计。

#### Scenario: 半角竖线转全角斜杠
- **WHEN** 调用 `escape_bare_pipe("a|b|c")`
- **THEN** 返回 `"a／b／c"`

### Requirement: 列数校验函数
`queue_table` SHALL 提供 `column_count_ok(section, cells)` 函数，判断给定分区的单元格列表是否符合该分区标准列数；对未登记的分区名 SHALL 返回 `True`（不断言未知分区）。

#### Scenario: 列数符合预期
- **WHEN** 调用 `column_count_ok("一", cells)` 且 `len(cells) == 8`
- **THEN** 返回 `True`

#### Scenario: 列数不符（如裸竖线致列偏移）
- **WHEN** 调用 `column_count_ok("一", cells)` 且 `len(cells) != 8`
- **THEN** 返回 `False`

#### Scenario: 未知分区不做断言
- **WHEN** 调用 `column_count_ok("五", cells)`（"五"不在 `SECTION_COLUMN_COUNTS` 中）
- **THEN** 返回 `True`
