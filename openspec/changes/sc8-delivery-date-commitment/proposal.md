## Why

SC8（客户订单交期智能承诺）是 Phase 1 两个能上线场景之一、采购线核心价值——把"成品交付预期"算出来推给客户（比亚迪/上汽/理想）。supplychain 已用真实数据验证过这条链路的核心引擎（订单聚合→SRM 承诺交期→物料齐套→SMT 完工→交付日预测，267 测试全绿），现在收割进 SC8 数字员工工程，复用已建好的平台底座（连接器/通知器/L2 门禁/审计），是"收割式 MVP"，不从零搭。现在做，是因为 7-8 月要交付 MVP，且 6/12 真实需求+供应商反馈到位后即可切真实。

## What Changes

- 新建 SC8 数字员工工程 `4-数字员工/采购部/SC8-客户订单交期智能承诺/`，`pip install -e` 平台底座，import 平台连接器/通知器/审计。
- **收割三引擎 + 编排**（业务逻辑进场景，不进平台底座）：
  - `sales_order_intake`（订单→按产品聚合需求）
  - `smt_scheduling`（齐料日 + SMT 工时 → 完工日）
  - `delivery_forecast`（完工日 + 物流 → 交付日 + 三色风险）
  - 编排管线 `compute_forecasts`（SRM 承诺交期 → 物料到货 → BOM 关键路径 → SMT → 预测）
- **收割 SC8 专属数据模型**（D1/Q1 留 SC8 的部分）：`SalesOrder`/`ForecastOrder` + 对应加载（CSV/Excel/ERP 导出/FO API），`DeliveryForecast` 结果类型。
- **新增门禁文档要求、收割代码尚无的能力**：
  - **置信度标注**（高=有供应商承诺交期；低=默认假设/估算）
  - **启发式补全**：无供应商反馈物料 → 需求日 +30 天（低置信）；委外加工 → 齐套日 +10 天；成品齐套日 = 最晚到货物料日（关键路径）
  - **L2 门禁接线**：低置信/关键路径无反馈/预期晚于客户目标日/首次给某客户承诺 → 经平台 `Notifier` 拦截，只出草稿、入 `PendingApprovalSink` 待审批队列，绝不自动外发
  - **交付预期 → CRM 通报**：`DeliveryForecast` 适配为平台 `crm_notifier` 的 `DelayNoticeInput`，生成延期/更正通报草稿
  - **偏差监控/重算触发**（信号：SRM 交期更新、齐套日变化、实际偏差超阈值）
  - **全链审计**：预测/更正/客户确认写平台 `audit`，更正事件关联原记录 ID（append-only）
  - **黄金基准回归框架**：`data/golden/` 存人工核对基准，作回归测试防退化
- 先 mock/脱敏跑通逻辑与门禁；真实切换（zp ERP BOM + 携客云 SRM 承诺交期）留任务 N.1，6/12 数据到位后做。

## Capabilities

### New Capabilities
- `delivery-date-forecast`: 交付日预测引擎——订单聚合、SRM 承诺交期→物料到货、BOM 关键路径齐套、SMT 完工、交付日与三色风险、置信度标注与启发式补全。
- `delivery-commitment-gate`: 交付承诺对客通报门禁——交付预期适配 CRM 草稿、L2 人工确认（fail-closed，复用平台 Notifier）、偏差监控/更正流程、全链审计与黄金基准回归。

### Modified Capabilities
<!-- 复用 platform-data-connectors / platform-notification-channels（已上线），本变更不改其需求契约，仅消费。 -->

## Impact

- **新增工程**：`4-数字员工/采购部/SC8-客户订单交期智能承诺/`（独立 Python 工程 + 测试 + golden 基准）。
- **依赖平台底座**：`shared_tools.{erp_connector,srm_connector,csv_connector,models}`、`crm_notifier`（DelayNoticeInput/generate_draft）、`notifiers.{Notifier,PendingApprovalSink}`、`audit`。
- **不进平台底座**：SC8 业务引擎与 `SalesOrder`/`ForecastOrder`/`DeliveryForecast` 留场景层（符合 D1 边界）。
- **门禁约束**：受《SC8 上线前置门禁》约束——黄金基准 + 错误/回滚 SOP 两道闸未过，只出草稿/内部看板，不对真实客户自动外发。
- **合规**：所有 AI 决策写 audit；推客户 L2 人工确认；先 mock 后真实；交付承诺属采购/交付域，不涉 OEM 技术数据隔离。
