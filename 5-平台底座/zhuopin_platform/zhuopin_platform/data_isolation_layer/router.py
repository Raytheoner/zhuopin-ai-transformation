"""OEM 隔离路由 —— 按客户上下文路由到独立向量库，拒绝跨库访问。"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..audit import AuditEvent, AuditLogger


class CrossOEMAccessError(PermissionError):
    """检测到跨 OEM 数据访问企图时抛出（合规红线，必须审计）。"""


class GeneralCollectionReadOnlyError(PermissionError):
    """写入通用知识库被只读闸拒绝时抛出（合规红线，必须审计）。

    刻意**不**继承 `CrossOEMAccessError`：本错误不是"跨客户访问"，而是
    "写入侧校验入口尚未建成 ⇒ 通用库置为只读"（D5=(a)，Shao Peishen 2026-09-02）。
    两者的处置动作也不同——前者是调用方拿错了客户上下文，后者是整条写入通道
    尚未开放，任何客户上下文都一样被拒。把两者合并成一个异常类会让调用方
    `except CrossOEMAccessError` 顺手吞掉只读闸，是一条隐性绕过路径。
    """


ISOLATION_SCENARIO = "DATA_ISOLATION"
ACTION_CROSS_OEM_DENIED = "cross_oem_access_denied"
ACTION_GENERAL_WRITE_DENIED = "general_collection_write_denied"

# 平台默认审计落盘路径（D2=(a) 收紧，Shao Peishen 2026-09-02 裁决）——
# 与 README 快速校验示例、其余场景注入 AuditLogger 时使用的路径同构（相对 CWD，已 .gitignore）。
DEFAULT_AUDIT_LOG_PATH = "reports/audit_log.jsonl"


def _default_audit_logger() -> AuditLogger:
    """构造平台默认审计器。

    未显式注入 `audit` 的调用方不再"静默不留痕"——OEMRouter 内建这一份默认 logger。
    """
    return AuditLogger.jsonl(DEFAULT_AUDIT_LOG_PATH)


# 注册在案的 OEM 客户 → 独立 Collection 名（小写、规范化）
REGISTERED_OEMS: dict[str, str] = {
    "比亚迪": "oem_byd",
    "上汽": "oem_saic",
    "理想": "oem_lixiang",
}
# 通用（非客户专属）知识库，可被所有场景读取：供应商库/质量案例/财务规则等
GENERAL_COLLECTIONS = {"kb_supplier", "kb_quality_cases", "kb_finance_rules"}

# 🔴 通用库写入侧只读闸（D5=(a)，Shao Peishen 2026-09-02 本人裁决）——
# 隔离规范 §2.3 要求通用库写入必经三项校验（无 OEM 信息校验 / 脱敏＋质量 Champion
# 签字 / 写入写 audit）。该校验入口**至今未建成**，故通用库整体置为只读：
# 已有内容不受影响，禁止任何新写入（含"离线校准/评测语料不进生产检索路径"这类理由）。
#
# 🔑 解闸条件（唯一）：先建成 §2.3 三项校验的写入入口，且该入口本身走独立 openspec
# 变更包评审。本闸刻意**不留**任何运行期开关、环境变量或可注入的 validator 钩子——
# 那些都会变成"注入一个空校验器即可放行"的绕过路径。解闸＝改写下面的
# `OEMRouter.guard_write`，把 deny 换成对真校验入口的调用，必经 code review。


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
        router.guard(oem="比亚迪", collection="kb_supplier")        # 读：放行
        router.guard_write(oem="比亚迪", collection="kb_supplier")  # 写：抛
                                                    # GeneralCollectionReadOnlyError
    """

    def __init__(self, registered: dict[str, str] | None = None,
                 audit: AuditLogger | None = None):
        self.registered = registered or dict(REGISTERED_OEMS)
        # D2=(a) 收紧：审计不再是可选项。未显式注入时内建平台默认 AuditLogger；
        # 默认构造本身失败（极罕见，如路径不可解析）时 `_audit` 仍可能为 None，
        # 由 `_record_denied` 在拒绝前兜底 fail-closed（不放行、不静默）。
        if audit is not None:
            self._audit = audit
        else:
            try:
                self._audit = _default_audit_logger()
            except Exception:
                self._audit = None

    def _record_denied(self, oem: str, collection: str, reason: str,
                       action: str = ACTION_CROSS_OEM_DENIED,
                       error_cls: type[PermissionError] = CrossOEMAccessError) -> None:
        """访问/写入被拒前写审计（违规企图留痕，OEM隔离规范 §3.2）。

        审计通道（默认或注入）不可用时 fail-closed：MUST NOT 静默放行或静默抛错——
        本方法必抛 `error_cls`，使拒绝这一后果本身不依赖审计通道是否健康。

        `action`/`error_cls` 默认值＝跨 OEM 拒绝路径（`#466` D2=(a) 既有语义，不变）；
        通用库只读闸（`#491` D5=(a)）复用同一条 fail-closed 通道，只换审计动作名与异常类。
        """
        if self._audit is None:
            raise error_cls(
                f"审计通道不可用（无可用 AuditLogger），OEM 隔离拒绝改判 fail-closed："
                f"{oem!r} 访问 {collection!r} 已拒绝，且无法留痕。"
            )
        try:
            self._audit.record(AuditEvent(
                scenario=ISOLATION_SCENARIO,
                action=action,
                evaluator="",
                automation_level="L3",
                decision={"oem": oem, "collection": collection, "reason": reason},
                oem_context=oem,
            ))
        except Exception as exc:
            raise error_cls(
                f"审计写入失败（{exc!r}），OEM 隔离拒绝改判 fail-closed："
                f"{oem!r} 访问 {collection!r} 已拒绝，且无法留痕。"
            ) from exc

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

    def guard_write(self, oem: str, collection: str) -> IsolationDecision:
        """校验「指定 OEM 上下文」是否有权**写入**「目标 collection」。

        与只读的 `guard()` 分离：读写两侧的判定规则本就不同——通用库
        **读可写不可**（隔离规范 §2.3 「写入侧控制是这一层的全部安全性所在」）。

        允许：① 与自身 OEM 完全匹配的专属库（写入规则与读取同）。
        拒绝：② 任何通用知识库 —— 只读闸（D5=(a)，见 `GENERAL_COLLECTIONS` 上方注释），
                 抛 `GeneralCollectionReadOnlyError`，拒绝前写 audit；
              ③ 任何其它 OEM 的专属库 —— 跨客户污染，抛 `CrossOEMAccessError`（复用
                 `guard()` 的既有判定与留痕，本方法不另立一套跨客户规则）。

        ⚠️ 本闸只挡**新写入**，对通用库既有内容无任何影响（D5 裁决文本明写）。
        """
        if collection in GENERAL_COLLECTIONS:
            # 只读闸先于 OEM 上下文判定：无论上下文是否注册、是哪一家，一律拒绝——
            # 未建成校验入口时"谁都不能写"，不存在某个上下文可豁免的情形。
            self._record_denied(
                oem, collection, "通用库写入侧校验入口未建成，通用库只读（D5=(a)）",
                action=ACTION_GENERAL_WRITE_DENIED,
                error_cls=GeneralCollectionReadOnlyError,
            )
            raise GeneralCollectionReadOnlyError(
                f"通用知识库 {collection!r} 当前为只读：写入侧「无 OEM 信息」校验入口尚未建成"
                f"（OEM数据隔离规范 §2.3 ／ D5=(a) Shao Peishen 2026-09-02）。"
                f"已有内容不受影响，禁止新写入；离线校准/评测语料同样不得以"
                f"「不进生产检索路径」为由绕过本闸。"
            )
        return self.guard(oem=oem, collection=collection)

    @staticmethod
    def _normalize(oem: str) -> str:
        return re.sub(r"\s+", "", (oem or "")).strip()
