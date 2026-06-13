"""对客通报路由（design D5 / 红线 §7.4）—— L2 真阻塞，绝不自动外发客户。

铁律（切真实后比 mock 严）：
  1. **real 模式对客外发路径直接禁用**：不依赖人不犯错，代码层强制只入待审批队列；
  2. 对客外发总开关 `config.CUSTOMER_OUTBOUND_ENABLED` 全程关闭（SRM 联调通过 + 门禁
     6 项全勾前），即便 mock 模式也不自动外发；
  3. 门禁 fail-closed：低置信/延期/首次承诺 → requires_confirmation；
  4. 全链审计记录置信度分类（高/低）+ 是否触发人工确认 + 客户隔离键。

CRM 层结构性无「发客户」函数（仅 draft 草稿）；真正外发由 L2 责任人经
FilePendingQueue.approve 二次放行（人工手发），本模块永不直接发客户。
"""
from __future__ import annotations

from zhuopin_platform.audit import AuditEvent, AuditLogger

from . import config
from .gate import evaluate
from .models import DeliveryForecast
from .notify import build_customer_draft
from .pending_queue import FilePendingQueue

ROUTE_QUEUED = "queued"          # 入待审批队列（未外发）
ROUTE_BLOCKED = "blocked"        # 异常拦截（无草稿入队）
ACTION_QUEUED = "customer_notice_queued"


def route_forecast(
    fc: DeliveryForecast,
    *,
    queue: FilePendingQueue,
    first_commitment: bool,
    mode: str = "real",
    audit: AuditLogger | None = None,
    allow_customer_outbound: bool = False,
    api_key: str | None = None,
) -> tuple[str, str]:
    """把一条交付预测路由为对客通报草稿，入待审批队列（绝不自动外发客户）。

    Returns:
        (outcome, item_id) —— outcome=ROUTE_QUEUED；item_id 为队列项 id。
    """
    # 红线①：real 模式强制关闭对客外发，无视调用方误传
    if mode == "real":
        allow_customer_outbound = False
    # 红线②：总开关全程关闭 → 当前 customer_send_open 恒为 False
    customer_send_open = config.CUSTOMER_OUTBOUND_ENABLED and allow_customer_outbound

    requires_confirmation, reasons, severity = evaluate(fc, first_commitment=first_commitment)
    draft = build_customer_draft(
        fc, requires_confirmation=requires_confirmation,
        severity=severity, extra_reasons=reasons, api_key=api_key,
    )
    # B3：标注所需审批级别（重点客户/首次承诺 → VP），approve 时校验确认人级别。
    draft.required_level = config.required_approval_level(
        fc.customer_name, first_commitment=first_commitment)

    # 永不自动外发客户：一律入待审批队列（人工经 queue.approve 二次放行后手发）。
    # customer_send_open 当前恒 False；保留判定为将来 SRM 联调通过 + 门禁全勾后的低风险直发留位。
    item_id = queue.enqueue(
        draft,
        reason="; ".join(reasons) if reasons else "internal_review",
    )

    if audit is not None:
        audit.record(AuditEvent(
            scenario="SC8",
            action=ACTION_QUEUED,
            evaluator="",                       # 外发确认人在 approve 阶段记录
            automation_level="L2",
            decision={
                "so_id": fc.so_id,
                "customer_key": config.customer_isolation_key(fc),   # D4 客户隔离键
                "recipient": fc.customer_name,
                "confidence": fc.confidence,                          # 置信度分类入审计
                "requires_confirmation": requires_confirmation,
                "severity": severity,
                "reasons": reasons,
                "sent": False,                                        # 绝不自动外发
                "customer_outbound_open": customer_send_open,         # 恒 False（留痕）
                "queue_item_id": item_id,
            },
        ))

    return ROUTE_QUEUED, item_id
