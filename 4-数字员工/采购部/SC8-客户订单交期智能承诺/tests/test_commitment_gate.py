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
    """给 audit 注入该客户一次成功外发，使其后续不再算'首次承诺'。"""
    notifier = build_notifier(queue, audit=audit, send_fn=lambda url, body: None)
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


# ── 低风险（高置信 + 非首次 + 准时）→ 自动放行外发 ──────────────────────────────
def test_low_risk_auto_sends(queue, audit):
    sends: list[str] = []
    _seed_prior_send(queue, audit, "比亚迪")
    notifier = build_notifier(queue, audit=audit, send_fn=lambda url, body: sends.append(body))
    res = submit_commitment(_forecast("比亚迪", confidence=CONFIDENCE_HIGH, delay=-5, risk="🟢"),
                            notifier, audit)
    assert res.requires_confirmation is False
    assert res.sent is True
    assert len(sends) == 1


# ── 拦截后 approve → 放行外发（人工确认后才发）──────────────────────────────────
def test_blocked_then_approved_sends(queue, audit):
    sends: list[str] = []
    notifier = build_notifier(queue, audit=audit, send_fn=lambda url, body: sends.append(body))
    submit_commitment(_forecast("理想"), notifier, audit)     # 首次 → 拦截
    assert sends == []
    item_id = queue.list_pending()[0]["id"]
    assert queue.approve(item_id, confirmed_by="Paul", notifier=notifier) is True
    assert len(sends) == 1                                    # 确认后才外发


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
