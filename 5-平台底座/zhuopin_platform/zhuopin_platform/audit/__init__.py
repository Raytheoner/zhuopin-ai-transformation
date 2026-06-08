"""IATF 16949 可追溯审计 — 跨场景统一接口。

设计：写入路径与存储后端解耦（C3 冲突消除方案）。
  - 现在    : JsonlSink —— append-only，单一可信源，零外部依赖（SC1 已在用）
  - 9月迁移 : ClickHouseSink —— 汇聚查询，append-only + 3年保留（全景规划 4.2）
两者同实现一个 AuditSink 接口；切换后端不动业务代码。

红色数据保护：审计记录只存「决策结果 + 数据来源 + 内容哈希」，
不落盘原始敏感数值（注册资本、IQC 原始合格率、财务红色数据等）。
"""

from .events import AuditEvent
from .logger import AuditLogger
from .sinks import AuditSink, JsonlSink

__all__ = ["AuditEvent", "AuditLogger", "AuditSink", "JsonlSink"]
