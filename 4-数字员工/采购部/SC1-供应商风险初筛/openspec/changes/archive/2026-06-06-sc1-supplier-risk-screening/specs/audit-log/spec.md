## ADDED Requirements

### Requirement: 评估结果写入审计日志
系统 SHALL 在每次评估完成后，将评估结果写入 JSON Lines 格式的审计日志文件 `audit_log.jsonl`。

每条审计记录 SHALL 包含以下字段：
- `timestamp`：ISO 8601 格式的评估完成时间（UTC）
- `evaluator`：操作人姓名
- `supplier_name`：供应商名称
- `supplier_code`：供应商编码（可为空字符串）
- `scores`：各维度评分对象（delivery、iqc、financial、single_source）
- `weights`：各维度权重对象（固定值，用于审计时验证计算）
- `composite_score`：综合评分（浮点数，两位小数）
- `risk_level`：风险等级（1-5 整数）
- `data_sources`：各维度数据来源标注对象
- `report_path`：生成的报告文件路径
- `ai_text_hash`：AI 生成文本（风险描述+建议）的 SHA-256 哈希值（用于追溯，不存原始文本）

#### Scenario: 正常评估后写入日志
- **WHEN** 一次完整评估完成，报告文件生成成功
- **THEN** 系统在 `audit_log.jsonl` 末尾追加一条 JSON 记录，写入操作原子性完成

#### Scenario: 报告生成失败时仍写入日志
- **WHEN** 报告生成过程中发生错误（如磁盘空间不足）
- **THEN** 系统仍写入审计记录，`report_path` 字段标注为 "FAILED"，`error` 字段记录错误信息

### Requirement: 审计日志不包含原始财务数据
系统 SHALL 确保审计日志文件中不存储供应商的原始注册资本数值和 IQC 合格率原始数值（红色数据保护）。

审计日志只记录：
- 各维度的最终评分（1-5 分）
- 数据来源类型标注
- AI 文本哈希值（非原文）

#### Scenario: 财务数据不落盘
- **WHEN** 操作人录入注册资本和 IQC 合格率
- **THEN** 这些原始数值仅存在于内存中用于评分计算，不写入 `audit_log.jsonl`，不写入任何持久化文件

### Requirement: 审计日志文件管理
系统 SHALL 提供查询审计日志的能力，支持按供应商名称和时间范围筛选。

#### Scenario: 按供应商查询历史记录
- **WHEN** 操作人执行查询命令并指定供应商名称
- **THEN** 系统输出该供应商所有历史评估记录的摘要（时间、风险等级、评估人）

#### Scenario: 日志文件不存在
- **WHEN** 系统首次运行，`audit_log.jsonl` 不存在
- **THEN** 系统自动创建空日志文件，首次评估记录正常写入

#### Scenario: 日志文件损坏（部分行无效）
- **WHEN** `audit_log.jsonl` 中存在格式错误的行
- **THEN** 系统跳过损坏行并提示警告，继续读取有效记录，不中断查询操作

### Requirement: 审计日志完整性校验
系统 SHALL 提供日志完整性自检命令，用于 IATF 16949 内审时验证日志未被篡改。

自检项目：
- 验证所有记录的 JSON 格式合法性
- 统计总记录数、时间跨度、涉及供应商数量
- 输出最新 10 条记录摘要

#### Scenario: 完整性自检通过
- **WHEN** 操作人执行自检命令且日志文件格式完整
- **THEN** 系统输出统计摘要，最后一行显示"✓ 审计日志完整性校验通过"

#### Scenario: 发现格式异常记录
- **WHEN** 自检过程中发现 JSON 解析失败的行
- **THEN** 系统输出异常行号和内容预览，最后一行显示"⚠ 发现 N 条异常记录，请检查"
