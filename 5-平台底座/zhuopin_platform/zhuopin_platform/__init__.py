"""卓品智能 AI 转型 — 平台底座共享包。

四个子系统：
  - audit                : IATF 16949 可追溯审计（JSONL 先行，ClickHouse 9月汇聚）
  - data_isolation_layer : OEM 客户数据严格隔离（per-OEM 向量库路由，禁止跨库）
  - shared_tools         : 通用 MCP 工具（文档解析 / U9C / SRM / 外部 API）
  - agents               : 跨部门智能体逻辑

所有数字员工场景（SC*/FI*/Q*/R*/S*/O*）统一依赖本包，单一可信源。
"""

__version__ = "0.1.0"
