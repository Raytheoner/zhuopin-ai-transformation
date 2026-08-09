## ADDED Requirements

### Requirement: 反引号感知切列
`queue_table` SHALL 提供 `split_row_cells(line)` 函数，把一行 Markdown 表格文本切分为单元格列表；反引号跨度（`` `...` ``）内出现的竖线 `|` SHALL NOT 被当作列分隔符。行文本不以 `|` 开头时 SHALL 返回 `None`；行文本不以 `|` 结尾（含反引号内容尚未被切开、或行结构本身被截断）SHALL NOT 导致函数返回 `None`——该情形 SHALL 仍返回切出的单元格列表，交调用方通过列数校验发现异常，不得在切分这一步静默丢弃该行。

#### Scenario: 反引号内竖线不算列分隔符
- **WHEN** 调用 `split_row_cells("| 1 | 说明 `a|b` | 状态 |")`
- **THEN** 返回 3 个单元格（`1`／`说明 `a|b``／`状态`），反引号内的 `|` 不产生额外切分

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
