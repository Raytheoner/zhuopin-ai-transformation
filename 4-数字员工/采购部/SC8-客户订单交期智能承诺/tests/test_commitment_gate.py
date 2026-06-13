"""L2 对客门禁 fail-closed 端到端（spec delivery-commitment-gate）。

覆盖：低置信 / 首次承诺 / 晚于目标日 → 必拦入队、不外发；approve 后才发；
缺 requires_confirmation 字段默认被拦（平台 fail-closed）。
"""
from __future__ import annotations

from datetime import date

from sc8.commitment import build_notifier, submit_commitment
from sc8.models import CONFIDENCE_HIGH, CONFIDENCE_LOW, DeliveryForecast


def _forecast(customer="比亚迪", *, confidence=CONFIDENCE_HIGH, delay=-5,
              forecast=date(2026, 7, 1), risk="🟢", so_id="SO1"):
    return DeliveryForecast(
        so_id=so_id, product_id="F02N.0040", customer_id="Z1", customer_name=customer,
        target_date=date(2026, 7, 10), smt_complete_date=date(2026, 6, 30),
        logistics_days=1, forecast_date=forecast, delay_days=delay, risk_level=risk,
        bottleneck="按期或提前", confidence=confidence, confidence_reason="测试",
        bottleneck_material="R01.B", param_version="sc8-params-v0",
    )


def _seed_prior_send(queue, audit, customer):
    """给 audit 注入该客户一次成功外发，使其后续不再算'首次承诺'。

    A2：放行机制本身需总开关开启才会真发，故此处显式 outbound_enabled=True
    （验证业务规则用，不依赖生产恒关的 CUSTOMER_OUTBOUND_ENABLED）。
    """
    notifier = build_notifier(queue, audit=audit, send_fn=lambda url, body: None,
                              outbound_enabled=True)
    fc = _forecast(customer, so_id="SO-SEED")
    res = submit_commitment(fc, notifier, audit)          # 首次必拦入队
    item_id = queue.list_pending()[-1]["id"]
    queue.approve(item_id, confirmed_by="Paul", notifier=notifier)  # 放行 → 记录 sent


# ── 首次给某客户承诺 → 拦截入队，不外发 ─────────────────────────────────────────
def test_first_commitment_blocked(queue, audit):
    sends: list[str] = []
    notifier = build_notifier(queue, audit=audit, send_fn=lambda url, body: sends.append(body))
    res = submit_commitment(_forecast("理想"), notifier, audit)
    assert res.sent is False
    assert "首次给该客户做交付承诺" in res.reasons
    assert sends == []
    assert len(queue.list_pending()) == 1


# ── 低置信 → 拦截入队 ──────────────────────────────────────────────────────────
def test_low_confidence_blocked(queue, audit):
    sends: list[str] = []
    _seed_prior_send(queue, audit, "比亚迪")              # 排除"首次"因素，单独验证低置信
    notifier = build_notifier(queue, audit=audit, send_fn=lambda url, body: sends.append(body))
    res = submit_commitment(_forecast("比亚迪", confidence=CONFIDENCE_LOW), notifier, audit)
    assert res.sent is False
    assert any("低置信" in r for r in res.reasons)
    assert sends == []


# ── 晚于目标日 → 拦截入队（即便高置信、非首次）──────────────────────────────────
def test_late_forecast_blocked(queue, audit):
    sends: list[str] = []
    _seed_prior_send(queue, audit, "比亚迪")
    notifier = build_notifier(queue, audit=audit, send_fn=lambda url, body: sends.append(body))
    late = _forecast("比亚迪", confidence=CONFIDENCE_HIGH, delay=8,
                     forecast=date(2026, 7, 18), risk="🔴")
    res = submit_commitment(late, notifier, audit)
    assert res.sent is False
    assert any("晚于客户目标日" in r for r in res.reasons)
    assert sends == []


# ── 低风险（高置信 + 非首次 + 准时）→ A2 修复后也入队，绝不自动外发 ──────────────
def test_low_risk_also_queues(queue, audit):
    """A2 / 审计报告 P0-A：删除低风险自动外发旁路——首道一律入队、不外发。

    门禁真实风险仍如实记录（res.requires_confirmation is False），但 res.sent 必为 False、
    底层发送函数未被调用、草稿入待审批队列。
    """
    sends: list[str] = []
    _seed_prior_send(queue, audit, "比亚迪")
    pending_before = len(queue.list_pending())
    notifier = build_notifier(queue, audit=audit, send_fn=lambda url, body: sends.append(body))
    res = submit_commitment(_forecast("比亚迪", confidence=CONFIDENCE_HIGH, delay=-5, risk="🟢"),
                            notifier, audit)
    assert res.requires_confirmation is False                 # 门禁真实风险仍为低
    assert res.sent is False                                  # 但绝不自动外发
    assert sends == []
    assert len(queue.list_pending()) == pending_before + 1    # 低风险也入队


# ── 拦截后 approve → 放行外发（人工确认 + 总开关开启后才发）──────────────────────
def test_blocked_then_approved_sends(queue, audit):
    sends: list[str] = []
    # A2：验证 approve→放行机制需显式开启总开关（生产恒关，机制本身正确性单独验证）
    notifier = build_notifier(queue, audit=audit, send_fn=lambda url, body: sends.append(body),
                              outbound_enabled=True)
    submit_commitment(_forecast("理想"), notifier, audit)     # 首次 → 拦截
    assert sends == []
    item_id = queue.list_pending()[0]["id"]
    assert queue.approve(item_id, confirmed_by="Paul", notifier=notifier) is True
    assert len(sends) == 1                                    # 确认后才外发


# ── A2：总开关关闭时，即便人工 approve 也不外发（第二道结构性闸门）─────────────────
def test_outbound_switch_blocks_even_approved(queue, audit):
    sends: list[str] = []
    # 默认 build_notifier 接 config.CUSTOMER_OUTBOUND_ENABLED（生产恒 False）
    notifier = build_notifier(queue, audit=audit, send_fn=lambda url, body: sends.append(body))
    submit_commitment(_forecast("理想"), notifier, audit)     # 首次 → 拦截入队
    item_id = queue.list_pending()[0]["id"]
    # 带确认人 approve，但总开关关闭 → 仍不外发
    assert queue.approve(item_id, confirmed_by="Paul", notifier=notifier) is False
    assert sends == []


# ── 缺 requires_confirmation 字段 → 平台 fail-closed 默认拦截 ───────────────────
def test_missing_requires_confirmation_field_blocked(queue, audit):
    sends: list[str] = []
    notifier = build_notifier(queue, audit=audit, send_fn=lambda url, body: sends.append(body))

    class _NoFieldMsg:
        recipient = "上汽"
        title = "交付承诺"
        body = "正文"
        severity = "warning"
        # 故意不定义 requires_confirmation

    assert notifier.send(_NoFieldMsg()) is False             # fail-closed：未知即拦
    assert sends == []
    assert len(queue.list_pending()) == 1
