"""OEM 隔离路由 —— 按客户上下文路由到独立向量库，拒绝跨库访问。"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..audit import AuditEvent, AuditLogger


class CrossOEMAccessError(PermissionError):
    """检测到跨 OEM 数据访问企图时抛出（合规红线，必须审计）。"""


ISOLATION_SCENARIO = "DATA_ISOLATION"
ACTION_CROSS_OEM_DENIED = "cross_oem_access_denied"


# 注册在案的 OEM 客户 → 独立 Collection 名（小写、规范化）
REGISTERED_OEMS: dict[str, str] = {
    "比亚迪": "oem_byd",
    "上汽": "oem_saic",
    "理想": "oem_lixiang",
}
# 通用（非客户专属）知识库，可被所有场景读取：供应商库/质量案例/财务规则等
GENERAL_COLLECTIONS = {"kb_supplier", "kb_quality_cases", "kb_finance_rules"}


@dataclass
class IsolationDecision:
    oem: str
    collection: str
    allowed: bool
    reason: str = ""


class OEMRouter:
    """把「OEM 上下文 + 目标 Collection」解析成一个受控的访问决策。

    用法::

        router = OEMRouter()
        col = router.resolve(oem="比亚迪")          # -> "oem_byd"
        router.guard(oem="比亚迪", collection="oem_saic")  # 抛 CrossOEMAccessError
    """

    def __init__(self, registered: dict[str, str] | None = None,
                 audit: AuditLogger | None = None):
        self.registered = registered or dict(REGISTERED_OEMS)
        self._audit = audit

    def _record_denied(self, oem: str, collection: str, reason: str) -> None:
        """跨 OEM 访问被拒前写审计（违规企图留痕，B5 / OEM隔离规范 §3.2）。"""
        if self._audit is None:
            return
        self._audit.record(AuditEvent(
            scenario=ISOLATION_SCENARIO,
            action=ACTION_CROSS_OEM_DENIED,
            evaluator="",
            automation_level="L3",
            decision={"oem": oem, "collection": collection, "reason": reason},
            oem_context=oem,
        ))

    def resolve(self, oem: str) -> str:
        """返回该 OEM 的专属 Collection；未注册客户拒绝。"""
        key = self._normalize(oem)
        if key not in self.registered:
            self._record_denied(oem, "", "未注册的 OEM 上下文")
            raise CrossOEMAccessError(f"未注册的 OEM 上下文：{oem!r}，禁止访问任何客户数据。")
        return self.registered[key]

    def guard(self, oem: str, collection: str) -> IsolationDecision:
        """校验「指定 OEM 上下文」是否有权访问「目标 collection」。

        允许：① 通用知识库；② 与自身 OEM 完全匹配的专属库。
        拒绝：③ 任何其它 OEM 的专属库（跨客户污染）。
        """
        if collection in GENERAL_COLLECTIONS:
            return IsolationDecision(oem=oem, collection=collection, allowed=True,
                                     reason="通用知识库")
        own = self.resolve(oem)  # 未注册 OEM 在此即被拒（resolve 内已留痕）
        if collection == own:
            return IsolationDecision(oem=oem, collection=collection, allowed=True,
                                     reason="本客户专属库")
        self._record_denied(oem, collection, "跨客户专属库访问")
        raise CrossOEMAccessError(
            f"OEM 上下文 {oem!r}（={own}）试图访问 {collection!r} —— 跨客户访问被拒绝。"
        )

    @staticmethod
    def _normalize(oem: str) -> str:
        return re.sub(r"\s+", "", (oem or "")).strip()
