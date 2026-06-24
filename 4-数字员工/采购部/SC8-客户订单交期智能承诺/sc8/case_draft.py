"""保供案例 AI 草稿（capability: baoguan-case-management，design D8）。

三类草稿：
  · kind="expedite"   催供应商答交/到货（内部用，直接生成展示）
  · kind="coordinate" 内部协调（插单/替代料/改期评估）（内部用）
  · kind="customer"   对客改期通知（**对客**）—— MUST 落对客闸 CUSTOMER_OUTBOUND_ENABLED
                       （全程 False）：仅生成草稿态，绝不自动外发客户（红线）。

有 ANTHROPIC_API_KEY 则调 Claude（最新模型）生成更自然文本；否则模板降级（参考 crm_notifier）。
本模块**只生成文本、不含任何发送路径**——对客闸由调用方/本模块 generate 的返回结构体现。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date

from . import config
from .case_store import CaseEvent, SupplyCase

_KIND_LABEL = {"expedite": "催供应商答交", "coordinate": "内部协调", "customer": "对客改期通知"}


@dataclass
class DraftResult:
    """一份草稿的结果。customer 类受对客闸约束：gated=True 时 sent 恒 False。"""
    kind:   str
    text:   str
    used_ai: bool
    is_customer: bool = False
    gated:  bool = False     # 对客闸是否生效（customer 且 CUSTOMER_OUTBOUND_ENABLED=False）
    sent:   bool = False     # 是否已外发——本模块永远 False（无发送路径）


# ── 模板降级 ──────────────────────────────────────────────────────────────────

def _template(case: SupplyCase, kind: str) -> str:
    new_date = case.new_confirmed_date or "待确认"
    if kind == "expedite":
        return (f"【催货】供应商您好：\n"
                f"我司成品 {case.item_code}（预测订单 {case.fo_id}）计划出货日 {case.ship_date}，"
                f"其子件 {case.bottleneck_material or '（见清单）'} 目前确定齐料晚约 "
                f"{case.confirmed_gap_days} 天，已影响成品保供。\n"
                f"请尽快确认该子件的最新到货/承诺交期，如可提前请协助加急。盼复，谢谢！")
    if kind == "coordinate":
        return (f"【内部协调】保供案例 {case.case_no}\n"
                f"成品 {case.item_code} / 单 {case.fo_id}，计划出货 {case.ship_date}，"
                f"瓶颈子件 {case.bottleneck_material or '—'} 确定延期约 {case.confirmed_gap_days} 天。\n"
                f"待协调项：① 能否插单/替代料；② 是否需与客户沟通改期；③ 物流加急可行性。"
                f"请相关同事评估反馈。")
    # customer —— 对客改期通知（落闸，仅草稿）
    return (f"主题：关于订单 {case.fo_id} / {case.item_code} 交货安排的说明\n\n"
            f"尊敬的{case.customer_name or '客户'}：\n"
            f"您好！就贵司订单（{case.fo_id}，产品 {case.item_code}）的交货安排向您说明："
            f"因上游子件交期顺延，本批原计划 {case.ship_date} 出货，"
            f"预计调整至 {new_date} 前后。我司正全力协调加快到货，"
            f"如有进展将第一时间向您通报。给您带来不便，深表歉意。\n\n"
            f"[公司名称] 供应链管理部\n{date.today().strftime('%Y年%m月%d日')}")


def _build_prompt(case: SupplyCase, events: list[CaseEvent], kind: str) -> str:
    notes = "\n".join(f"  - [{e.actor}] {e.note}" for e in events if e.note) or "  -（无）"
    return (f"你是汽车 Tier1 工厂的供应链保供协调专员。请根据以下保供案例，"
            f"用中文起草一段「{_KIND_LABEL.get(kind, kind)}」文本。\n\n"
            f"【案例】成品 {case.item_code} / 预测订单 {case.fo_id} / 客户 {case.customer_name}\n"
            f"计划出货日 {case.ship_date}，确定瓶颈子件 {case.bottleneck_material}，"
            f"确定延期约 {case.confirmed_gap_days} 天。\n【处置记录】\n{notes}\n\n"
            f"要求：专业、简洁（150 字内）；只输出正文，不要解释。")


def generate(case: SupplyCase, events: list[CaseEvent] | None = None, *,
             kind: str = "expedite", api_key: str | None = None) -> DraftResult:
    """生成草稿。kind=customer 时落对客闸：gated 标记 + sent 恒 False（绝不外发）。"""
    events = events or []
    is_customer = (kind == "customer")
    gated = is_customer and not config.CUSTOMER_OUTBOUND_ENABLED

    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    used_ai = False
    text = _template(case, kind)
    if key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=key)
            msg = client.messages.create(
                model="claude-opus-4-8", max_tokens=600,
                messages=[{"role": "user", "content": _build_prompt(case, events, kind)}])
            text = msg.content[0].text.strip()
            used_ai = True
        except Exception:
            text, used_ai = _template(case, kind), False   # 降级模板，保证可用

    return DraftResult(kind=kind, text=text, used_ai=used_ai,
                       is_customer=is_customer, gated=gated, sent=False)
