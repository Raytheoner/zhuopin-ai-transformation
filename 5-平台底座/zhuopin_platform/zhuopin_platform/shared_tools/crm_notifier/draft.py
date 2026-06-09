"""CRM 延期通报草稿生成器（收割自 supplychain src/crm_notifier.py，D3 解耦）。

改造：原依赖 SC8 业务模型 DelayCase/CaseEvent，现改为只读 DelayNoticeInput Protocol 字段，
不 import delay_case。生成结果为 NotificationDraft（满足 NotificationMessage Protocol），
默认 requires_confirmation=True（推客户需 L2 人工确认）。

两种模式：
  1. generate_draft()  — 调 Claude API（默认 claude-sonnet-4-6），生成更自然的邮件文本
  2. template_draft()  — 纯模板，无 API 依赖（测试 / 降级 / 离线）
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date

from .contracts import DelayNoticeInput

# D6：CRM 草稿默认模型（可配置常量）。无 ANTHROPIC_API_KEY 时降级模板。
DEFAULT_MODEL = "claude-sonnet-4-6"


@dataclass
class NotificationDraft:
    """通知草稿（满足 NotificationMessage Protocol）。

    requires_confirmation 默认 True —— 推客户属高风险，须 L2 人工确认后才可外发。
    """

    recipient: str
    title: str
    body: str
    severity: str = "warning"
    requires_confirmation: bool = True
    confirmed_by: str = ""


def _subject(notice: DelayNoticeInput) -> str:
    return f"主题：关于订单 {notice.so_id} / {notice.product_id} 交货日期调整的通知"


def build_prompt(notice: DelayNoticeInput) -> str:
    """组装发给 Claude 的提示词（只读 Protocol 字段）。"""
    new_date = notice.new_date or "待定"
    reasons = list(notice.reasons) if notice.reasons else ["供应商原材料短缺，交期顺延"]
    reasons_block = "\n".join(f"  - {r}" for r in reasons)

    return f"""你是一家 SMT 电子制造工厂的供应链协调专员。
请根据以下延期案例信息，帮我起草一封中文客户延期通知邮件。

【延期案例信息】
- 销售订单号：{notice.so_id}
- 产品料号：{notice.product_id}
- 客户名称：{notice.customer_name}
- 原承诺交货日：{notice.target_date}
- 新预计交货日：{new_date}
- 延期天数：约 {notice.delay_days} 天

【延期原因（内部处置记录）】
{reasons_block}

【邮件要求】
1. 格式：标准商务邮件，含主题行、正文、落款（落款公司名留空，写"[公司名称]"）
2. 语气：专业、诚恳，表达歉意但不过分卑微
3. 内容：说明延期原因（用客户友好的语言），给出新交货日，承诺跟进
4. 长度：正文 150–250 字，简洁不啰嗦
5. 语言：中文

只输出邮件正文，不要解释或说明。"""


def template_draft(notice: DelayNoticeInput) -> NotificationDraft:
    """不依赖 Claude API 的模板版本（测试 / 降级 / 离线）。"""
    new_date  = notice.new_date or "待定"
    orig_date = notice.target_date or "原承诺日期"
    subject = _subject(notice)

    body = f"""尊敬的{notice.customer_name}，

您好！感谢您长期以来对我司的支持与信任。

现就贵司订单（订单号：{notice.so_id}，产品：{notice.product_id}）的交货安排\
向您作出说明：

由于上游供应商物料交期顺延，原定于 {orig_date} 交货的本批订单，\
预计将于 {new_date} 完成交付，较原计划延期约 {notice.delay_days} 天。\
对此给您带来的不便，我们深表歉意。

我司将持续跟进物料到货及生产进度，如有任何变化将第一时间向您通报。\
如贵司对交期调整有特殊要求，欢迎随时与我们沟通协商。

再次为本次延期向您致歉，感谢您的理解与支持！

此致
敬礼

[公司名称]
供应链管理部
{date.today().strftime("%Y年%m月%d日")}"""

    return NotificationDraft(
        recipient=notice.customer_name,
        title=subject,
        body=f"{subject}\n\n{body}",
        severity="warning",
        requires_confirmation=True,   # 推客户：默认需 L2 确认
    )


def generate_draft(
    notice: DelayNoticeInput,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
) -> NotificationDraft:
    """生成客户延期通报草稿。

    优先调 Claude API（默认 claude-sonnet-4-6）；无 key 或调用失败自动降级模板。
    返回 NotificationDraft（requires_confirmation=True，待 L2 确认后方可外发）。
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return template_draft(notice)

    try:
        import anthropic  # 仅需要时 import，避免测试依赖

        client = anthropic.Anthropic(api_key=key)
        message = client.messages.create(
            model=model,
            max_tokens=800,
            messages=[{"role": "user", "content": build_prompt(notice)}],
        )
        draft_text = message.content[0].text.strip()
        subject = _subject(notice)
        if "主题" not in draft_text[:30] and "Subject" not in draft_text[:30]:
            draft_text = subject + "\n\n" + draft_text

        return NotificationDraft(
            recipient=notice.customer_name,
            title=subject,
            body=draft_text,
            severity="warning",
            requires_confirmation=True,
        )
    except Exception:
        # 任何异常都降级模板，保证可用
        return template_draft(notice)
