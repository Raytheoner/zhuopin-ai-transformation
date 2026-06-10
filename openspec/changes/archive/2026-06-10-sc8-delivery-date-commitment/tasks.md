# Tasks — SC8 客户订单交期智能承诺（收割式 MVP）

> 工作流：先写测试再实现（SuperPowers）。本批只到 **mock 端到端 + 黄金基准框架 + L2 门禁代码生效**；
> 不连真实 zp/SRM（真实切换 = 任务 9，6/12 后过《SC8 上线前置门禁》6 项检查表）。
> 平台底座只消费不改契约。design D1–D7 已 Paul 拍板放行。

## 1. 工程骨架与底座接线
- [x] 1.1 建 `4-数字员工/采购部/SC8-客户订单交期智能承诺/`：`pyproject.toml`（`pip install -e` 平台底座）、`sc8/` 包、`tests/`、`data/golden/`。
- [x] 1.2 冒烟 import：`from zhuopin_platform.shared_tools.notifiers.dispatch import Notifier`、`...crm_notifier.draft import generate_draft`、`...audit import AuditLogger` 均可导入。
- [x] 1.3 `config.py`：D2 可配常量 `PARAM_VERSION` / `NO_FEEDBACK_LEAD_DAYS=30` / `OUTSOURCE_EXTRA_DAYS=10` / `LOGISTICS_DAYS=1` / `DEVIATION_ALERT_DAYS=3`；D3 委外识别 `OUTSOURCE_PRODUCT_IDS`（维护清单）+ `OUTSOURCE_PREFIXES`（料号规则）+ `is_outsourced(product_id)`。

## 2. 收割数据模型与加载（留 SC8 层）
- [x] 2.1 `models.py`：收割 `SalesOrder` / `ForecastOrder`（自 supplychain data_loader）；`DeliveryForecast` **扩展**新增字段：`confidence`（"高"/"低"）、`confidence_reason`、`bottleneck_material`、`param_version`。平台 `ProductionPlan` / `SrmDeliveryOrder` / `SrmDemandOrder` 从底座 import，不重建。
- [x] 2.2 `loaders.py`：收割 SO/FO 加载（CSV mock 优先；ERP 导出 / FO API 留接口）+ `fo_to_sales_orders`。本批只接 mock 夹具，不触真实端点。

## 3. 收割三引擎 + 编排（确定性逻辑）
- [x] 3.1 `intake.py`：收割 `aggregate_demand`（同料号聚合、交期取最早）。
- [x] 3.2 `scheduling.py`：收割 `schedule_smt` + `load_smt_lead_time`（齐料日=最晚物料到货 + SMT 工时）。
- [x] 3.3 `forecast.py`（**核心增量**）：物料到货估算（SRM 承诺日→关键路径），补 **置信度**（D1）+ **启发式**（D2：无反馈 +NO_FEEDBACK_LEAD_DAYS；委外 +OUTSOURCE_EXTRA_DAYS）；产出扩展版 `DeliveryForecast`（带 confidence/瓶颈物料/param_version）。
- [x] 3.4 `pipeline.py`：`compute_forecasts` 编排（订单→聚合→SRM 承诺/关键路径→SMT→预测），每条预测记录所用 `PARAM_VERSION`。

## 4. 置信度与正交风险（D1 澄清）
- [x] 4.1 置信度判定：**高** = 成品全部直接子件有 SRM 承诺交期；**低** = 含任一无反馈（走 +30）或委外估算。
- [x] 4.2 正交性测试：与三色风险解耦——"有反馈但晚于目标日" = 高置信 + 🔴 红风险（不折进置信度）。

## 5. CRM 适配 + L2 门禁接线（fail-closed）
- [x] 5.1 `notify.py`：`forecast_to_notice(DeliveryForecast)` 适配为平台 `DelayNoticeInput`（D4，不收割 DelayCase）；SC8 专属对客 prompt 注入（D7）。
- [x] 5.2 门禁判定 `gate.py`：低置信 / 首次给某客户承诺（查 audit 历史）/ 预期晚于客户目标日 → `requires_confirmation=True`、经平台 `Notifier` 拦截、入待审批队列、不外发。缺 `requires_confirmation` 字段默认被拦（fail-closed 复用平台语义）。
- [x] 5.3 `pending_queue.py`：`FilePendingQueue`（落 `data/pending_approvals.jsonl`，复用平台 JsonlSink 加锁写法）实现平台 `PendingApprovalSink.enqueue`；`approve(id, confirmed_by)` 触发 `Notifier.send(confirmed_by=...)`。

## 6. 幂等（关键）
- [x] 6.1 `approve→send` 成功后队列项**原子标记 `'sent'`**；重复点确认/重试 → 直接返回，**绝不重复外发客户**。
- [x] 6.2 幂等测试：同一 approve 重复触发，`send_fn` 只被调用一次。

## 7. 全链审计
- [x] 7.1 预测事件写平台 `audit`：含 confidence、param_version、bottleneck_material、so_id、automation_level=L2。
- [x] 7.2 更正事件（D4）：用 `audit` + `so_id` 关联原预测记录，写明原因/触发信号/责任人/时间；原记录不删（append-only）。
- [x] 7.3 客户确认事件：approve 外发后记录 confirmed_by。
- [x] 7.4 审计可追溯测试：原预测 → 更正 → 确认 三链可由 so_id 串起。

## 8. 黄金基准回归框架
- [x] 8.1 `data/golden/`：mock 样本（覆盖三类：有反馈 / 无反馈 / 含委外）+ 人工核对期望值（确定性逻辑）。
- [x] 8.2 回归测试：确定性逻辑（关键路径、日期加减）对黄金基准 **零偏差**；置信度标注正确。
- [x] 8.3 端到端 mock 跑通：订单→预测→门禁→（拦截/确认外发）闭环，无真实网络调用。

## 9. （移交）真实切换 — 任务 N.1，6/12 后 → 已另起新独立变更
- [x] 9.1 **本 MVP 范围不含真实切换；移交新独立变更 `sc8-real-data-cutover`**。前置：加固清单 P2（Pydantic 校验 / SRM 限流退避 900301 / 凭证管理 / hash-chain 审计）+ 真实数据黄金基准（采购经理核对真实订单零偏差）+ 委外维护清单填真实料号 → 过《SC8 上线前置门禁》6 项检查表，才允许真实客户外发。

---
**完成定义（本批）**：1–8 全绿；门禁场景（低置信/首次/晚于目标日必拦、确认才发、缺字段被拦、幂等只发一次）有测试覆盖；审计全链可追溯；黄金基准确定性零偏差。停下报 Paul，先不进真实外发、先不 push。
