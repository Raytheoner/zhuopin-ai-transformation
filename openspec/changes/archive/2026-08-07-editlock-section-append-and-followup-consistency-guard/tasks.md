## 1. Design 审核（阻塞后续所有任务）

- [x] 1.1 提交 design.md 五个决策点给 Shao Peishen 审核——2026-08-07 本 session 对话内直接答复"按默认执行"，五点均 (a)
- [x] 1.2 记录审核结果到 design.md「审批记录」小节

## 2. `append-row` 子命令（决策点 1/2，需求见 `specs/editlock-section-append-guard`）

- [x] 2.1 新增 `cmd_append_row`：接受 `--section`、`--number`（§一/§四）或首个 `--cell` 即为批次号（§二）、若干 `--cell` 重复参数；按分区列序拼装
- [x] 2.2 新增插入位置定位函数（`_section_bounds`/`_last_table_line_end_offset`），复用 `_split_live_sections`/`_table_data_rows` 同一套判据（独立实现，不 import），定位目标分区表格真实末行并插入（覆盖空分区场景）
- [x] 2.3 写入前校验：字段数量与分区预期列数一致；拼装后按 `|` 切分列数与预期一致
- [x] 2.4 裸竖线检测：字段值中含任何 `|`（**不论是否被反引号包裹**，apply 阶段修正见 design.md）即触发拒绝，错误信息含字段序号与内容预览
- [x] 2.5 新增/更新单测（`AppendRowTests`，10 个）：结构化字段拼装成功、字段数不符拒绝、非末尾分区插入位置正确（§一/§四 互不干扰）、空分区插入（§二）、裸竖线拒绝（含反引号包裹场景，验证同样拒绝）、编号字段缺失/多余拒绝、无分区标题拒绝

## 3. release 一致性校验（决策点 3/4/5，需求见 `specs/editlock-followup-hold-consistency-guard`）

- [x] 3.1 独立实现 README 目标文件标注提取正则（`FOLLOWUP_TARGET_FILE_RE`，不 import `aibot_service`，同既有惯例），复用 `_followup_readme_rows`/`FOLLOWUP_FINALIZED_STATUS`
- [x] 3.2 `_validate_release_structure` 新增第⑥项：对本次持锁期间新增/修改的 §一/§四 行检测"暂缓关键词+反引号 `.md` 文件名引用"共现（§一：状态列cells[5]查关键词、cells[3]+cells[6]查文件名；§四：事项列cells[1]查两者，无独立状态列）
- [x] 3.3 正向校验：匹配到的 README 行「发送状态」为 `🆕 待发` 时拒绝 release
- [x] 3.4 反向校验：匹配到的 README 行「发送状态」已是终态"已推送"类值（非 `FOLLOWUP_NON_TERMINAL_STATUSES`）而队列行仍含暂缓字样时，告警不阻断
- [x] 3.5 新增/更新单测（`HoldConsistencyValidationTests`，8 个）：正向拒绝、README已同步非待发时放行、未匹配到README行时不拒绝、反向告警放行、仅关键词无文件名不触发、仅文件名无关键词不触发、§四回落事项列

## 4. 历史兼容核对固化

- [x] 4.1 用 #150 真实事故场景（真实文件名/真实收信人/真实事故文本）重建为固定用例 `test_150_real_incident_row_recreated_triggers_reverse_warning_not_block`，验证 design.md「历史兼容核对」结论：不触发正向拒绝、触发反向告警（README 当前已是终态"已推送"）

## 5. 真实验证

- [x] 5.1 用 `append-row` 真实追加一行到 §一/§四/§二 各分区（`AppendRowTests`，走真实 subprocess CLI + 真实文件读写，非 mock），确认插入位置正确、列数正确、不同分区互不干扰
- [x] 5.2 `HoldConsistencyValidationTests` 全部用例走真实 `cmd_acquire`/`cmd_release`（生产代码路径，非 mock，对真实临时队列文件+真实临时 README 文件+真实 `.editlock` 锁文件操作），确认正向场景真实被拒绝、反向场景真实告警放行。**额外真实手工验证**：`append-row` 对一份手写临时队列文件（含 §一/§二/§四 三分区）真实运行四种场景——正常插入（不同分区互不干扰）、空 §二 分区插入、裸竖线拒绝、反引号包裹裸竖线同样拒绝——均与预期一致

## 6. 验收与收尾

- [x] 6.1 全量回归（`test_工具-共享文档编辑锁.py`）零漂移——94 passed（原 76 + 新增 18：`AppendRowTests` 10 个、`HoldConsistencyValidationTests` 8 个）
- [x] 6.2 `工具-共享文档编辑锁.py` 文件头部说明段补充本次两项加固的背景
- [x] 6.3 `专线opener模板库.md` 新增 §〇.7 补充 `append-row` 用法说明
- [x] 6.4 队列 §一 #258 行回填：状态、产出路径、单测清单、真实验证记录、历史兼容核对结果；已核对 #294 完工状态（`⏸ 暂缓` 已落地，本设计判据无需改动，见 design.md 风险节）
- [x] 6.5 `/opsx:archive` 归档本变更包
- [x] 6.6 收工重跑文档台账
