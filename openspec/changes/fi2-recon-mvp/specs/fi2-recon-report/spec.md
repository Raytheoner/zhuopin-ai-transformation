## ADDED Requirements

### Requirement: 报告聚合与 L3 门禁

系统 SHALL 将逐行匹配分类结果聚合为对账报告，且按 L3 门禁规则路由：🟡金额微差 / 🔴明细错位 / 🔴数量金额不符 / 🔴无 GR 支撑 四类 MUST 标记为 `needs_review`（需人工确认）；🟢完全匹配类标记为 `l3_suggested_pass`（AI 建议通过）。任何结果 MUST NOT 被系统自动标记为已过账或已结案——本 MVP 不实现自动过账路径。

#### Scenario: 非完全匹配强制转人工
- **WHEN** 某 PO 行分类为"数量金额不符"
- **THEN** 该行报告状态 SHALL 为 `needs_review`

#### Scenario: 完全匹配标建议通过但不自动过账
- **WHEN** 某 PO 行分类为"完全匹配"
- **THEN** 该行报告状态 SHALL 为 `l3_suggested_pass`，报告文案 MUST 明确标注"AI 建议通过，未过账"

### Requirement: 审计留痕（金额脱敏）

系统 SHALL 为每行匹配判定写入一条平台 `AuditEvent`（`scenario="FI2"`），记录 PO 号/行号/物料编码/分类结果/差异比例/触发维度；MUST NOT 在审计记录中写入原始发票单价或含税金额的绝对值。

#### Scenario: 审计事件字段脱敏
- **WHEN** 系统为某行超容差判定写审计事件
- **THEN** 审计记录 SHALL 包含分类结果与差异比例，MUST NOT 包含该行原始发票金额或单价的绝对数值

### Requirement: L3 人工改判 CLI

系统 SHALL 提供命令行工具，供财务人员对 `needs_review` 状态的行录入人工结论；`--reason`（改判原因）MUST 为必填项，缺失或为空 MUST 拒绝执行；同一行重复提交改判 MUST 幂等（不重复写审计，提示已存在记录）。

#### Scenario: 改判原因缺失被拒绝
- **WHEN** 财务人员调用改判 CLI 但未提供 `--reason` 或提供空字符串
- **THEN** 系统 SHALL 拒绝执行并提示错误，不写入审计记录

#### Scenario: 重复改判幂等
- **WHEN** 同一 PO 行已存在改判记录，财务人员再次提交相同行的改判
- **THEN** 系统 SHALL 跳过重复写入，打印警告而非报错
