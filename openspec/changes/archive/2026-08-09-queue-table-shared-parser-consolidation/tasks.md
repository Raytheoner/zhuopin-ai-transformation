## 0. design 审前置

- [x] 0.1 范围缩窄已由 Shao Peishen 2026-08-08 拍板措施 A 定案，相关决策并入 `queue-status-machine-field` 的 design.md 决策点 4；本变更不重开审议。

## 1. 单测先行

- [x] 1.1 `queue_table.py` 单测：`SECTION_COLUMN_COUNTS` 取值、`has_bare_pipe` 正反例（含反引号包裹不豁免）、`escape_bare_pipe` 转换、`column_count_ok` 各分区正反例与未知分区。

## 2. 实现：新增权威模块

- [x] 2.1 `5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/queue_table.py`（`SECTION_COLUMN_COUNTS`/`has_bare_pipe`/`escape_bare_pipe`/`column_count_ok`）。

## 3. 消费者切换（写侧优先→高风险读侧→CI→低风险读侧→跨仓库，同 #308 design.md 决策点 4 顺序）

- [x] 3.1 `工具-共享文档编辑锁.py`：`SECTION_COLUMN_COUNTS` 委托、`_cell_has_bare_pipe` 委托 `queue_table.has_bare_pipe`；worktree 本地路径 sys.path 引导（隔离环境兜底桩，回归 `EditLockCrossWorktreeTests` 两个用例）。
- [x] 3.2 `工具-落库sweep.py`：`_parse_section_two`/`_parse_section_one` 列数校验改读 `queue_table.SECTION_COLUMN_COUNTS`。
- [x] 3.3 `工具-队列结构lint.py`：经其既有的 `importlib` 复用编辑锁 `SECTION_COLUMN_COUNTS`，随 3.1 切换自动透传，无需直接改动（已用其自身测试验证）。
- [x] 3.4 `工具-队列查询.py`：`SECTION_COLUMNS` 列名字典保留（展示用，非本变更权威化范围），新增模块级断言核对其列数与 `queue_table.SECTION_COLUMN_COUNTS` 一致。
- [x] 3.5 `工具-文档台账生成.py`：`QUEUE_EXPECTED_COLUMNS` 改读 `queue_table.SECTION_COLUMN_COUNTS["一"]`。
- [x] 3.6 `wecom-aibot-service/aibot_service/decision_reminder.py`：两处列数硬编码改读 `SECTION_COLUMN_COUNTS`；核实 `draft_gap_detection.py` 只读 README 两态语义、不碰 §一/§二/§四 表格解析，无需改动（沿用 #308 tasks.md 4.6 已有核实结论）。
- [x] 3.7 Cowork artifact `zhuopin-project-status`（JS）：如实登记为不可消除的第二实现，本次不纳入切换范围（与 #308 design.md 决策点 4 处置结论一致）。

## 4. #307：文件头指针化

- [x] 4.1 `工具-队列查询.py` 文件头"独立实现是本项目一贯做法"段改写为指向权威模块的指针，如实说明当前实际范围（列数校验已切换，表格切分/开头片段提取因 #308 大部分作废、不在本次权威化范围内，本文件按需继续本地实现）。

## 5. 验证

- [x] 5.1 全量回归：`zhuopin_platform` 277 passed+1 skip（新增 `test_queue_table.py` 11 用例）、`0-学习与工具` 五个受影响工具各自测试文件（编辑锁 128／sweep 138／队列查询 14／文档台账 7／队列结构lint 7+6 subtests）、`wecom-aibot-service` 357 passed+1 skip，均零漂移。
- [x] 5.2 `openspec validate queue-table-shared-parser-consolidation --strict` 通过；`openspec validate --all --strict` 75/75 通过。

## 6. 收工

- [ ] 6.1 队列 #306/#307 行回填完工状态（`[S:done][D:机]`，如实登记"队列文件路径解析收拢"未做，见 design.md 决策点2）。
- [ ] 6.2 `/opsx:archive queue-table-shared-parser-consolidation -y`。
