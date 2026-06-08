"""OEM 客户数据隔离层 —— 法律合规红线（全景规划 4.3）。

铁律：不同 OEM 客户（比亚迪/上汽/理想…）的技术数据严格隔离，禁止交叉污染。
实现：每个 OEM 一个独立的向量库 Collection；查询必须显式带 OEM 上下文，
由 OEMRouter 路由到对应 Collection，任何跨 OEM 访问直接拒绝并审计。
"""

from .router import OEMRouter, CrossOEMAccessError

__all__ = ["OEMRouter", "CrossOEMAccessError"]
