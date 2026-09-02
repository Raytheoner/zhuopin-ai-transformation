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

### Requirement: 反引号感知切列
`queue_table` SHALL 提供 `split_row_cells(line)` 函数，把一行 Markdown 表格文本切分为单元格列表；反引号跨度（按 CommonMark code span 规则识别——反引号**游程**开合，闭合游程须与开启游程长度完全一致）内出现的竖线 `|` SHALL NOT 被当作列分隔符。行文本不以 `|` 开头时 SHALL 返回 `None`；行文本不以 `|` 结尾（含反引号内容尚未被切开、或行结构本身被截断）SHALL NOT 导致函数返回 `None`——该情形 SHALL 仍返回切出的单元格列表，交调用方通过列数校验发现异常，不得在切分这一步静默丢弃该行。

#### Scenario: 反引号内竖线不算列分隔符
- **WHEN** 调用 `split_row_cells("| 1 | 说明 `a|b` | 状态 |")`
- **THEN** 返回 3 个单元格（`1`／`说明 `a|b``／`状态`），反引号内的 `|` 不产生额外切分

#### Scenario: 双反引号游程包裹含单反引号的内容
- **WHEN** 调用 `split_row_cells("| 1 | `` `f|g `` | 状态 |")`（CommonMark 标准写法，双反引号游程用于包裹"内容本身含单个反引号"的文本）
- **THEN** 返回 3 个单元格，双反引号游程内的竖线不产生额外切分——单反引号正则会把游程内每个反引号误当独立配对边界，本场景是队列 #314 apply 阶段对真实生产队列文件 §二 批次 `B-0809_312可Open池立行与接力收工` 跑新旧切列 diff 时真实命中的缺陷复现，不是假设场景

#### Scenario: 行首无竖线判为非表格行
- **WHEN** 调用 `split_row_cells("普通段落文字")`
- **THEN** 返回 `None`

#### Scenario: 行尾被截断仍原样返回单元格供列数校验发现
- **WHEN** 调用 `split_row_cells("| 313 | 任务 | ...到此为止没有收尾")`（模拟队列 #313 行结尾两列被外部工具吞掉的真实破损）
- **THEN** 返回切出的单元格列表（非 `None`），单元格数量少于该行所属分区的标准列数

### Requirement: 列数不变式收进解析入口
`queue_table` SHALL 提供 `parse_section_rows(section_text, section)` 函数，对给定分区正文逐行调用 `split_row_cells`，跳过表头/分隔行后，为每条数据行返回 `(原始行文本, 单元格列表, 列数是否符合该分区标准列数的布尔值)` 三元组；SHALL 复用 `column_count_ok` 完成列数判定，不得重新实现列数比较逻辑。

#### Scenario: 混合正常行与列数异常行
- **WHEN** 对含 1 条 8 列正常行与 1 条因反引号外裸竖线导致 9 列的行的 §一 分区正文调用 `parse_section_rows(text, "一")`
- **THEN** 返回 2 条结果，前者列数校验为 `True`，后者为 `False`

#### Scenario: 反引号内裸竖线不再被误判为列数异常
- **WHEN** 对含 1 条状态列引用 `` `from zhuopin_platform|import zhuopin_platform` `` 这类反引号包裹竖线的 8 列合法行的 §一 分区正文调用 `parse_section_rows(text, "一")`
- **THEN** 该行列数校验为 `True`（与真实队列 #313 行的破损成因相反：本场景验证"反引号内竖线不应造成列偏移"这一修复目标本身）

### Requirement: 各分区列名为权威模块登记的单一事实
权威模块 SHALL 登记各分区按列序的表头列名，并提供"列名 → 列下标"的解析函数，使消费者按列名定位单元格、**永不需要自己数列下标**。未知分区或未知列名 MUST fail-loud 并列出该分区的合法列名，MUST NOT 猜测或静默回退到某个下标。模块 SHALL 另外提供一个判定函数，用于把"文件实际表头与模块登记列名是否一致"这件事变成机器可守——一旦生产文件改了表头而模块未跟进，按列名写入会静默写进错误的列，该风险 MUST NOT 依赖人工记忆同步。

#### Scenario: 按列名解析出正确列下标
- **WHEN** 消费者以某分区的合法列名（含已登记别名）请求列下标
- **THEN** 返回该列在该分区列序中的下标

#### Scenario: 未知列名 fail-loud
- **WHEN** 消费者请求某分区不存在的列名
- **THEN** 抛出错误并列出该分区全部合法列名与已登记别名

#### Scenario: 表头与模块登记不一致时可被检出
- **WHEN** 文件实际表头列名与模块登记的列名不完全一致
- **THEN** 判定函数返回不一致说明，指出按列名写入会写进错误的列

### Requirement: 全部写盘路径共用同一套单元格校验
权威模块 SHALL 提供一个供**所有**队列写盘路径共用的单元格校验函数，使守卫不依赖"调用方走了哪条入口"。该函数 SHALL 区分写侧与读侧两种调用口径，且该区分 MUST 只作用于竖线一项：写侧（待写入的字段值）竖线一律拒绝且反引号包裹不豁免；读侧（已按反引号感知规则切分出的单元格）跳过竖线检查——格内被反引号正当保护的竖线是合法内容，读侧若照搬写侧口径会把结构完全正常的行报成违规。

#### Scenario: 读侧不误报反引号内的竖线
- **WHEN** 对一条列数正确、但某格内含被反引号包裹的竖线的已解析行执行读侧校验
- **THEN** 不产生任何违规

#### Scenario: 写侧仍拒绝同样的值
- **WHEN** 对同一段含竖线的文本执行写侧校验
- **THEN** 报出竖线违规

#### Scenario: 未知调用口径 fail-loud
- **WHEN** 调用方传入既非写侧亦非读侧的口径取值
- **THEN** 抛出错误，MUST NOT 静默按默认口径处理

