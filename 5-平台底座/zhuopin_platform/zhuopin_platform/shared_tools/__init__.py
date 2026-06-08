"""通用 MCP 工具层 —— 所有场景共用，避免重复开发（审查报告遗漏C）。

子模块（Phase 1 起逐步充实）：
  - doc_parser    : 统一文档解析（SC4 合同 / Q4 PPAP / R1 需求 / R5 文档）
  - srm_connector : 携客云 SRM（从 SC1 抽取复用；SC1 已生产验证）
  - u9c_connector : U9C ERP MCP 客户端（待 7/1 接口申请就绪）
  - external_apis : 芯片 EOL/供货、物流、市场情报（待 8 月选型）

当前为占位骨架，按 Phase 1 解依赖进度逐个实现。
"""
