# platform-notification-channels Specification

## Purpose
TBD - created by archiving change platform-harvest-connectors. Update Purpose after archive.
## Requirements
### Requirement: CRM 延期通报草稿生成器
平台 SHALL 提供 CRM 延期通报草稿生成能力，根据交付/延期信息生成面向客户的通报草稿。该能力 MUST 仅生成草稿，不得在无人工确认的情况下直接对客户外发。

#### Scenario: 生成延期通报草稿
- **WHEN** 场景传入某客户订单的延期信息
- **THEN** 生成器返回结构化的 CRM 通报草稿文本，状态标记为「待人工确认」，未触发任何外发动作

### Requirement: 企业微信推送通道
平台 SHALL 提供企业微信（企微）推送通道，作为通用内部通知出口。推送凭据/Webhook MUST 从环境变量注入，不得硬编码。

#### Scenario: 内部企微推送
- **WHEN** 场景请求向指定企微群/机器人推送一条内部通知
- **THEN** 通道经企微 Webhook（或测试夹具）发送消息，凭据来自环境注入；测试模式下不触达真实端点

### Requirement: 外发动作前置 L2 人工门禁（FAIL-CLOSED）
凡涉及交付预测推送客户、采购金额 > 50 万、新供应商等高风险通报，外发动作 SHALL 前置 L2 人工确认，平台 MUST NOT 自动外发此类内容。门禁 SHALL 采用 **FAIL-CLOSED** 语义：当通知对象的 `requires_confirmation` 字段缺失/未知，或严重度未知时，MUST 一律按"高风险·需确认·不外发"处理，绝不默认放行。`NotificationMessage` Protocol MUST 显式声明 `requires_confirmation` 为强约束字段。

#### Scenario: 高风险通报需人工确认
- **WHEN** 待外发内容命中高风险条件（推客户/采购额>50万/新供应商）
- **THEN** 系统仅产出草稿并要求 L2 人工确认，确认前不执行外发

#### Scenario: 缺字段时默认拦截（fail-closed）
- **WHEN** 通知对象未声明 `requires_confirmation`（或严重度未知）且未提供人工确认
- **THEN** 门禁默认判为高风险并拦截，不外发，绝不因字段缺失而默认放行

#### Scenario: 拦截草稿入待审批队列（持久化钩子）
- **WHEN** 高风险通报被门禁拦截且配置了待审批队列持久化钩子（`PendingApprovalSink`）
- **THEN** 被拦截的草稿经钩子入队待人工审批，审计记录标注 `queued_for_approval`

### Requirement: 通用通知输入契约（Protocol）
平台通知通道供多个场景复用，其输入 SHALL 定义为结构化 `Protocol`，而非耦合任一场景的业务模型（如 SC8 的 `DelayCase`）。该 Protocol MUST 至少声明：收件人/通报对象、标题、正文、严重度等必需字段；通知器只读取这些字段，不依赖契约外的具体类型。

#### Scenario: 任意满足 Protocol 的对象均可被通知器消费
- **WHEN** 任一场景传入满足该 Protocol 必需字段（收件人/标题/正文/严重度）的对象
- **THEN** 通知器正常生成草稿/推送，不要求该对象是某特定业务类（如 DelayCase）

### Requirement: 通知动作审计留痕
所有通知器的草稿生成与外发动作 SHALL 通过平台既有 `zhuopin_platform.audit.AuditLogger` 留痕，复用已有审计骨架，不得重建。

#### Scenario: 通知动作写入审计日志
- **WHEN** 通知器生成草稿或执行一次推送
- **THEN** 平台审计日志新增一条只追加记录，包含场景、动作类型、目标渠道与人工确认状态

