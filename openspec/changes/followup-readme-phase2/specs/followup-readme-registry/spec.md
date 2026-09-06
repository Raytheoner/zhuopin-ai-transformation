## Purpose

跟进信 README 主表的登记与状态更新 SHALL 只经由一条受编辑锁保护、带字段长度上限与写后校验的命令行入口完成，取代裸手 Read 全文再 Edit 的写入方式。

## ADDED Requirements

### Requirement: 登记新行走 append 子命令
登记 CLI SHALL 提供 `append` 子命令，接受编号（按收信人所属部门计数器自动取号，未成功发出的信不占号）、日期、收信人、主要事项、交期要点、发送状态六个字段；写入前 SHALL 获取 `工具-共享文档编辑锁.py --file <README>` 的锁，写入完成后 SHALL 立刻释放。

#### Scenario: append 成功新增一行
- **WHEN** 调用方以合法字段值调用 `append` 且当前无其他会话持有 README 编辑锁
- **THEN** CLI 取得锁、在主表追加一行、释放锁，新行编号取自其部门计数器当前值 +1

#### Scenario: 编辑锁被他人持有时 append 被拒绝
- **WHEN** 调用 `append` 时 README 编辑锁已被其他调用方持有
- **THEN** CLI 拒绝写入、不追加任何行、提示当前持锁方

### Requirement: 改状态走 set-status 子命令且状态值受枚举校验
登记 CLI SHALL 提供 `set-status` 子命令，按编号定位已存在的行并整格改写「发送状态」列；写入值经 `followup_gate.normalize_status` 归一化后 MUST 命中 `followup_gate` 权威判据集合已知的某个状态前缀（`CLOSED_STATUS_PREFIXES`／`IN_FLIGHT_STATUS_PREFIXES`／`REPLY_ARRIVED_STATUS`），允许在前缀后追加自由文本后缀（如追加时间戳/说明）；`classify_status` 归类为 `"unknown"` 的值 MUST 被拒绝、不修改文件。CLI MUST NOT 自行维护一份独立于 `followup_gate` 的状态字面量清单，以免与权威判据漂移。

#### Scenario: 合法状态值写入成功
- **WHEN** 调用 `set-status` 指定的编号存在，且提供的状态值归一化后命中 `followup_gate` 已知状态前缀之一
- **THEN** CLI 原子改写该行「发送状态」列为新值

#### Scenario: 非法状态值被拒绝
- **WHEN** 调用 `set-status` 提供的状态值归一化后被 `followup_gate.classify_status` 判为 `"unknown"`
- **THEN** CLI 拒绝执行、不修改文件、报错说明已知状态前缀集合

#### Scenario: 目标编号不存在
- **WHEN** 调用 `set-status` 指定的编号在主表与归档件中均不存在
- **THEN** CLI 拒绝执行、报错说明编号未找到

### Requirement: 写前列数校验与写后回读
登记 CLI 的 `append` 与 `set-status` SHALL 在写入前校验表头本身可解析，且**本次待写入/待改写的那一行**列数与表头列数一致，列数不符 MUST 拒绝写入；写入完成后 SHALL 立即回读刚写入的行并比对，回读结果与预期不一致 MUST 报错并保留锁供人工排查（不自动重试、不自动回滚）。**校验范围限定为本次触碰的行，MUST NOT 因主表中其它历史行的既有列数异常而拒绝本次写入**——2026-09-06 实测主表 `采购部#14` 行因「发送状态」历史回写段内含未转义的 `|` 字符而被朴素分列解析为 7 列（表头 6 列），该行早于本能力存在、不属本次写入触碰范围，不应阻塞其它行的正常登记；此类历史行的修复属另一件事，不在本能力范围内静默处理。

#### Scenario: 待写入行列数校验失败阻止写入
- **WHEN** 本次待追加或待改写的行，其列数与表头列数不一致
- **THEN** CLI 拒绝本次写入、不改动文件、报错说明列数不一致

#### Scenario: 历史行列数异常不阻塞本次写入
- **WHEN** 主表中存在与本次操作无关的历史行，其列数因既有数据问题与表头不一致
- **THEN** CLI 仍正常完成本次写入，不因该历史行报错

#### Scenario: 写后回读比对失败
- **WHEN** 写入操作完成后，CLI 回读刚写入的行内容与预期值不一致
- **THEN** CLI 报错、保留编辑锁不自动释放、提示人工排查

### Requirement: 字段长度上限与外置提示
`append` 与 `set-status` 写入的「主要事项」列 MUST NOT 超过 600 字节，「交期要点」列 MUST NOT 超过 400 字节；超限 MUST 被拒绝，并提示改用外置行日志（`followup-readme-row-length-guard` 能力）后以摘要形式登记。

#### Scenario: 主要事项超限被拒绝
- **WHEN** `append` 或 `set-status` 提供的「主要事项」字段内容超过 600 字节
- **THEN** CLI 拒绝写入、提示该字段超限及外置建议

#### Scenario: 交期要点超限被拒绝
- **WHEN** `append` 或 `set-status` 提供的「交期要点」字段内容超过 400 字节
- **THEN** CLI 拒绝写入、提示该字段超限及外置建议

### Requirement: append 前置串行闸检查
`append` SHALL 在写入前对目标收信人调用与 `工具-跟进闸查询.py` 同一份判据（`followup_gate.classify_status`）算闸；该收信人当前闸锁（最新一封未闭环）时 MUST 拒绝新增草稿行，并提示先处理在途信或改走队列登记「待前信闭环后发」，不得进入写入流程。**本要求于 2026-09-06 实现过程中发现补入**：编辑锁 release 时已有「跟进信串行原则」结构校验会在写入之后拒绝这种情形，但那是事后拦截——写已经发生、锁仍占用待人工处理；本要求把同一判据前移到写入前，避免留下「文件已改、release 被拒、锁未释放」的中间态。

#### Scenario: 闸锁时 append 被拒绝
- **WHEN** 调用 `append` 的收信人最新一封信未闭环（闸锁）
- **THEN** CLI 拒绝执行、不获取编辑锁、不写入文件，提示当前在途信编号及处理建议

#### Scenario: 闸开时 append 正常进行
- **WHEN** 调用 `append` 的收信人当前无在途信或最新一封已闭环（闸开）
- **THEN** CLI 继续后续校验与写入流程

### Requirement: 编辑锁 release 失败不得报告为成功
`append` 与 `set-status` 写入并回读通过后，SHALL 尝试释放编辑锁；若 `release` 被拒绝（如触发既有的「跟进信串行原则」等结构校验），CLI MUST NOT 打印成功结论或以退出码 0 返回——MUST 原样输出 release 的拒绝原因，并明确告知调用方文件已写入但锁仍被占用，需人工核实解决（补写闭环状态、加逃生阀标记，或人工 release）。

#### Scenario: release 被拒绝时不得报告成功
- **WHEN** 写入与回读均已成功，但 `release` 返回非零退出码
- **THEN** CLI 以非零退出码结束，输出内容明确说明「已写入但锁未释放」及 release 拒绝原因，不输出 `[OK]` 类成功字样

### Requirement: 新增行遵循既有起草状态约束
`append` 子命令新增一行时，「发送状态」列 SHALL 且仅 SHALL 允许写入 `⏳ 待你审`，MUST NOT 在同一次调用中直接写入其他任意状态值（含终态标记），以复用 `wecom-followup-review-state` 能力既有的「起草只能写入待审草稿态」与「authorship-agnostic」约束，不新开一条绕开该约束的写入通道。

#### Scenario: append 试图直接写入终态被拒绝
- **WHEN** 调用 `append` 时提供的发送状态字段值不是 `⏳ 待你审`
- **THEN** CLI 拒绝执行、不追加行、提示新增行只能是待审草稿态
