## 1. `queue_table` 权威模块新增能力

- [x] 1.1 在 `zhuopin_platform.shared_tools.queue_table` 新增 `split_row_cells(line)`，复用 `BACKTICK_SPAN_RE`（`` `[^`]*` ``）同款正则识别反引号跨度，反引号内的 `|` 不作为列分隔符；行不以 `|` 开头返回 `None`；行不以 `|` 结尾仍正常返回切出的单元格列表（不静默丢弃，见队列 #314① 教训）。
- [x] 1.2 新增 `parse_section_rows(section_text, section)`，逐行调用 `split_row_cells`，跳过表头/分隔行，复用 `column_count_ok` 完成列数判定，返回 `(原始行文本, 单元格列表, 列数是否符合布尔值)` 三元组列表。
- [x] 1.3 单测覆盖：反引号内单个/多个竖线、反引号未闭合、整行被反引号包裹、行首无竖线、行尾被截断（对照队列 #313 真实破损文本）、`parse_section_rows` 对混合正常/异常行的分类结果。（22 passed，`5-平台底座/zhuopin_platform/tests/test_queue_table.py`）

## 2. 消费者迁移（保留函数名与签名，只换内部实现）

- [x] 2.1 `工具-共享文档编辑锁.py::_table_data_rows` 改为委托 `queue_table.split_row_cells`（编辑锁一贯"原样返回交调用方判"的既有策略不变）。apply 阶段发现设计问题并修正：反引号跨度识别从 design.md 决策点 1 原定的单反引号正则升级为 CommonMark 反引号游程配对（`_mask_backtick_spans`），起因是真实生产文件 §二 批次 `B-0809_312...` 命中双反引号转义单反引号的写法，单反引号正则会误合并列（4 列变 3 列）——见 `queue_table.py` 模块内注释与 design.md 补记。隔离环境兜底桩仍用简化的单反引号正则（明确标注"简化近似非镜像"，理由见桩注释）。
- [x] 2.2 `工具-队列查询.py::_table_data_rows` 同款迁移。
- [x] 2.3 `工具-落库sweep.py::_parse_section_one`/`_parse_section_two` 迁移——只替换切列（`queue_table.split_row_cells`），**保留**"行首行尾都必须是 `|`"这一既有判据不变（design.md 已论证：sweep 的静默跳过是与编辑锁"原样返回"不同、都各自成立的既有取舍，#314① 只放宽了编辑锁一侧，不隐式扩散到 sweep）。
- [x] 2.4 `工具-队列结构lint.py`（经由复用编辑锁的 `_table_data_rows`）验证其两项既有检查（列数／§二状态列格式）结果不受影响，不需要改动源码——已随 2.1 的编辑锁测试套件一并验证。

## 3. 全量回归与真实数据验证

- [x] 3.1 4 处消费者各自既有测试套件全量跑通，零漂移（编辑锁/lint/队列查询共 158 passed，sweep 138 passed，`zhuopin_platform` 包自身 tests/test_queue_table.py 23 passed）；`test_bare_pipe_inside_backtick_causes_column_mismatch` 因行为预期改变（BREAKING，proposal.md 已声明）已重写为 `test_pipe_inside_backtick_no_longer_causes_column_mismatch` + 新增 `test_bare_pipe_outside_backtick_still_causes_column_mismatch` 保留原始 #164 覆盖面。
- [x] 3.2 对当前生产队列文件跑新旧切列结果 diff：239 行（含表头/分隔行）全部一致，0 差异。**过程中真实命中 1 处差异**（§二 `B-0809_312...`，4 列被错合并成 3 列），促成决策点 1 从单反引号正则升级为 CommonMark 游程配对算法，修复后归零——task 3.2 本身即是发现此缺陷的机制，非走过场。
- [x] 3.3 #313 真实历史破损文本（结尾被截断，不以 `|` 收尾）经新实现处理后仍被 `column_count_ok` 正确判定为 `False`（结构损坏未被反引号感知误放行）。#267 已在队列 #314① 阶段修复完成，当前生产文件不再处于破损状态。

## 4. 收尾

- [x] 4.1 `openspec validate queue-table-backtick-aware-split --strict` 与 `openspec validate --all --strict` 均通过（75/75）。
- [x] 4.2 确认 `has_bare_pipe`/`escape_bare_pipe` 未被本变更触碰——`git diff` 核实两函数体零改动；对应既有单测（`test_has_bare_pipe_*`／`test_escape_bare_pipe_*`）全部随 `zhuopin_platform` 全量回归（289 passed+1 skip）一并通过，实测而非只读代码确认。
- [x] 4.3 完工回写队列对应行；变更包按"完工即归档纪律"跑 `/opsx:archive`。
