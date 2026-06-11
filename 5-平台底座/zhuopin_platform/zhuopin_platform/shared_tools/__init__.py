"""通用共享工具层 —— 所有数字员工场景共用，一份代码处处复用。

已收割（supplychain 真连接器，已真实数据验证）：
  - models / csv_loaders : 连接器返回 shape 数据模型 + CSV 加载与回退
  - connector            : DataConnector 抽象（5 类业务数据统一接口）
  - csv_connector        : CSVConnector（脱敏/离线/回退数据源）
  - connector_audit      : ConnectorAudit 轻量访问痕迹 + DebugLog（D2：合规分离、默认关全文）
  - srm_connector        : 携客云 SRM 只读（承诺交期 / 供应计划看板）
  - erp_connector        : U9C/ERP **唯一规范连接器**（ZpConnector：OAuth2 + U9C webapi BOM
                           + zp REST PO/物料/供应商；U9C_DATA_SOURCE 开关，real 模式 fail-loud）
                           〔已退役重复的 u9c_connector 骨架，见连接器收敛设计 md〕
  - crm_notifier         : CRM 延期通报草稿（D3：Protocol 解耦，不依赖 DelayCase）
  - notifiers            : 企微推送 + L2 门禁派发器（推客户须人工确认 + 审计留痕）

待建（按 Phase 1 解依赖进度）：
  - doc_parser           : 统一文档解析（SC4 合同 / Q4 PPAP / R1 需求 / R5 文档）
  - external_apis        : 芯片 EOL/供货、物流、市场情报（待 8 月选型）

注：审计统一接 zhuopin_platform.audit；OEM 隔离接口预留在 data_isolation_layer，
采购连接器（SRM/ERP/CRM）不强加 OEM 路由（仅研发/知识库场景使用）。
"""
