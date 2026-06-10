"""SC8 客户订单交期智能承诺（收割式 MVP）。

业务引擎与 SalesOrder/ForecastOrder/DeliveryForecast 留场景层（design D1/Q1 边界）；
平台底座（连接器/通知器/L2 门禁/审计）只 import 消费，不改契约。

模块：
  config        — D2 可配启发式参数 + D3 委外识别
  models        — SalesOrder/ForecastOrder（收割）+ DeliveryForecast（扩展置信度/参数版本）
  loaders       — SO/FO 加载（本批只接 mock 夹具）
  intake        — aggregate_demand 订单聚合
  scheduling    — schedule_smt SMT 完工
  forecast      — 物料到货估算 + 置信度 + 启发式（核心增量）
  pipeline      — compute_forecasts 编排
  gate          — L2 门禁判定（低置信/首次承诺/晚于目标日）
  notify        — forecast→DelayNoticeInput 适配 + 对客 prompt + Notifier 接线
  pending_queue — FilePendingQueue（D5 文件型 PendingApprovalSink + 幂等）
"""
