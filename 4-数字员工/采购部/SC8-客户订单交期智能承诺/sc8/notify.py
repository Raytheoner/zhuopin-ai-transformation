"""交付预期 → CRM 通报适配 + 对客口径 + 平台 Notifier 接线（design D4/D7）。

D4：写轻适配器 `forecast_to_notice(DeliveryForecast) -> DelayNoticeInput`，直接喂平台
    crm_notifier，MVP 不收割 DelayCase 状态机；更正流程用 audit + so_id 关联原记录。
D7：对客措辞（交付承诺口径）由 SC8 业务掌控，注入 SC8 专属 prompt 指引；平台只保留
    通用 LLM 调用 + 模板降级引擎。平台 draft.py prompt 参数化为另开小 PR（Q3，不混入本变更）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from zhuopin_platform.shared_tools.crm_notifier.draft import (
    NotificationDraft,
    generate_draft,
)

from .models import DeliveryForecast

# ── D7：SC8 对客口径（交付承诺措辞指引，业务掌控）─────────────────────────────────
# 本批先在 SC8 侧持有该口径；待平台 draft.py 支持 prompt 覆盖（Q3 另开小 PR）后注入。
# 在那之前，draft 生成复用平台通用引擎（LLM 或模板降级），门禁字段由 SC8 覆盖控制。
SC8_CUSTOMER_PROMPT_GUIDANCE = (
    "你代表卓品智能（汽车 ECU Tier 1 供应商）向 OEM 客户沟通交付承诺/调整。"
    "口径要求：① 专业诚恳、对等不卑微；② 明确给出新预计交付日与延期天数；"
    "③ 说明瓶颈原因（客户友好语言，不暴露内部料号细节）；④ 承诺持续跟进并主动通报。"
    "切忌给出未经 L2 确认的'保证'措辞。"
)


@dataclass
class NoticeAdapter:
    """满足平台 DelayNoticeInput Protocol 的适配体（D4，不耦合 DelayCase）。"""
    customer_name: str
    so_id:         str
    product_id:    str
    target_date:   str
    new_date:      str
    delay_days:    int
    reasons:       list = field(default_factory=list)


def forecast_to_notice(
    fc: DeliveryForecast,
    extra_reasons: list[str] | None = None,
) -> NoticeAdapter:
    """把交付预期适配为 CRM 延期通报输入（D4）。

    无法预测时 new_date='待定'、delay_days=0；reasons 含瓶颈描述 + 门禁触发原因。
    """
    reasons = [fc.bottleneck] if fc.bottleneck else []
    if extra_reasons:
        reasons = reasons + list(extra_reasons)
    return NoticeAdapter(
        customer_name=fc.customer_name,
        so_id=fc.so_id,
        product_id=fc.product_id,
        target_date=fc.target_date.isoformat(),
        new_date=fc.forecast_date.isoformat() if fc.forecast_date else "待定",
        delay_days=fc.delay_days if fc.delay_days is not None else 0,
        reasons=reasons,
    )


def build_customer_draft(
    fc: DeliveryForecast,
    *,
    requires_confirmation: bool,
    severity: str,
    extra_reasons: list[str] | None = None,
    api_key: str | None = None,
) -> NotificationDraft:
    """生成对客通报草稿（复用平台草稿引擎，SC8 覆盖门禁字段）。

    平台 generate_draft 默认 requires_confirmation=True；此处按门禁判定显式覆盖
    requires_confirmation 与 severity（对客口径与风险等级由 SC8 业务掌控）。
    """
    notice = forecast_to_notice(fc, extra_reasons)
    draft = generate_draft(notice, api_key=api_key)
    # SC8 门禁覆盖：推客户高风险时确保需确认；severity 反映与目标日的偏离程度
    draft.requires_confirmation = requires_confirmation
    draft.severity = severity
    return draft


def build_correction_draft(
    fc: DeliveryForecast,
    reason: str,
    *,
    api_key: str | None = None,
) -> NotificationDraft:
    """生成"交付预期更正通知"草稿（推送后发现算错，走同一 L2 门禁，D4 / SOP §1.3）。

    更正草稿强制 requires_confirmation=True、severity=critical，注明更正原因。
    """
    draft = build_customer_draft(
        fc, requires_confirmation=True, severity="critical",
        extra_reasons=[f"【更正原因】{reason}"], api_key=api_key,
    )
    draft.title = "（更正）" + draft.title
    return draft
