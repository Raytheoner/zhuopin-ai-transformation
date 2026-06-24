"""保供案例 AI 草稿（case_draft）测试 —— 无 API key 走模板；对客草稿落闸不外发。"""
from __future__ import annotations

from sc8 import config
from sc8.case_draft import generate
from sc8.case_store import CaseStore


def _case():
    store = CaseStore(":memory:")
    c, _ = store.create_case(item_code="S02Y.0188", fo_id="FO-1", customer_name="比亚迪",
                             ship_date="2026-06-10", confirmed_gap_days=61,
                             bottleneck_material="S02Y.0188")
    return c


def test_internal_expedite_template(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = generate(_case(), [], kind="expedite", api_key=None)
    assert r.used_ai is False and r.is_customer is False and r.gated is False
    assert "催货" in r.text and "S02Y.0188" in r.text
    assert r.sent is False


def test_internal_coordinate_template(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = generate(_case(), [], kind="coordinate", api_key=None)
    assert "协调" in r.text and r.sent is False


def test_customer_draft_is_gated_and_not_sent(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # 红线：对客闸全程 False
    assert config.CUSTOMER_OUTBOUND_ENABLED is False
    r = generate(_case(), [], kind="customer", api_key=None)
    assert r.is_customer is True
    assert r.gated is True          # 闸生效
    assert r.sent is False          # 绝不自动外发
    assert "FO-1" in r.text
