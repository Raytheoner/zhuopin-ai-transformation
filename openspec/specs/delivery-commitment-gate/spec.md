# delivery-commitment-gate Specification

## Purpose
SC8 交付承诺对客通报门禁：交付预期适配 CRM 草稿、L2 人工确认（fail-closed，复用平台 Notifier）、
偏差监控/更正流程、全链审计与黄金基准回归。守住"未过门禁不对真实客户自动外发"的合规红线。

## Requirements
### Requirement: 交付预期适配为 CRM 通报草稿
SC8 SHALL 把交付预期（`DeliveryForecast`）适配为平台 `crm_notifier` 的 `DelayNoticeInput`，对延期/有风险的订单生成面向客户的通报草稿，复用平台草稿生成器（不重建）。

#### Scenario: 延期订单生成草稿
- **WHEN** 某订单预测交付日晚于客户目标日
- **THEN** 适配为 DelayNoticeInput 并经平台 crm_notifier 生成延期通报草稿，状态「待人工确认」

### Requirement: 对客通报前置 L2 人工门禁（fail-closed，复用平台 Notifier）
对客户的交付承诺/通报 SHALL 经平台 `Notifier`（FAIL-CLOSED）外发。以下情形 MUST 强制人工确认、不自动外发：低置信、关键路径物料无反馈、预期交付晚于客户目标日、首次给某客户做交付承诺。未确认的草稿 MUST 入 `PendingApprovalSink` 待审批队列。

#### Scenario: 低置信/首次承诺拦截入队
- **WHEN** 交付预期为低置信，或为首次给该客户的交付承诺，且无人工确认
- **THEN** 平台 Notifier 拦截、不外发，草稿入待审批队列，审计标注未确认

#### Scenario: 人工确认后放行
- **WHEN** L2 责任人对草稿确认（提供 confirmed_by）
- **THEN** 通报经渠道外发，审计记录确认人

### Requirement: 偏差监控与重算触发
SC8 SHALL 在以下信号出现时触发重算：SRM 供应商交期更新、齐套日变化、委外排期变化、实际到货与预测偏差超阈值（默认 3 天，可配）。偏差超阈值 SHALL 告警给 PMC/采购。

#### Scenario: 偏差超阈值告警
- **WHEN** 实际进展与预测交付日偏差超过阈值
- **THEN** 触发重算并向 PMC/采购告警，不静默

### Requirement: 推送后更正流程
交付预期推客户后若发现算错，SC8 SHALL 用平台 `crm_notifier` 生成"更正通知"草稿，同样经 L2 门禁人工确认后外发，草稿注明更正原因，并同步通知销售/PMC/采购。

#### Scenario: 更正通知走同一门禁
- **WHEN** 已推送的交付预期被判定需更正
- **THEN** 生成更正草稿，经 L2 人工确认后才外发，不自动外发

### Requirement: 全链审计（含更正关联原记录）
SC8 SHALL 把预测/更正/客户确认全链写平台 `audit`（append-only）。更正事件 MUST 关联原预测记录 ID，写明原因、触发信号、责任人、时间；原记录不删除。

#### Scenario: 更正事件关联原记录
- **WHEN** 生成一条交付预期更正
- **THEN** 审计新增一条更正事件，含原预测记录 ID 与更正原因，原预测记录保留

### Requirement: 黄金基准回归与上线门禁
SC8 SHALL 沉淀黄金基准（人工核对的真实订单样本）作回归测试基准。真实客户自动通报 SHALL 在《SC8 上线前置门禁》检查表全部勾选后方可开启；任一未过，只出草稿/内部看板，不对真实客户自动外发。

#### Scenario: 门禁未过只出草稿
- **WHEN** 黄金基准或错误/回滚 SOP 门禁未全部通过
- **THEN** SC8 仅产出草稿/内部看板，不对真实客户自动外发

#### Scenario: 确定性逻辑零偏差
- **WHEN** 对黄金基准样本运行 SC8 的确定性逻辑（关键路径、日期加减）
- **THEN** 与人工计算偏差为 0
