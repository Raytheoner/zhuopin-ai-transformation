"""portal_gateway.sso 单测——覆盖 spec portal-wecom-sso 全部 Scenario。"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from portal_gateway import sso

SECRET = "test-secret-value"


# ── 会话 Cookie 签发/校验 ────────────────────────────────────────────


def test_make_and_verify_session_cookie_roundtrip():
    now = 1_000_000
    value = sso.make_session_cookie_value(SECRET, "YaoZuYi", days=30, now=now)
    userid = sso.verify_session_cookie_value(SECRET, value, now=now + 10)
    assert userid == "YaoZuYi"


def test_verify_session_cookie_expired_rejected():
    now = 1_000_000
    value = sso.make_session_cookie_value(SECRET, "YaoZuYi", days=1, now=now)
    # 超过 1 天后校验
    userid = sso.verify_session_cookie_value(SECRET, value, now=now + 2 * 86400)
    assert userid is None


def test_verify_session_cookie_tampered_signature_rejected():
    now = 1_000_000
    value = sso.make_session_cookie_value(SECRET, "YaoZuYi", days=30, now=now)
    userid_part, exp_part, _sig = value.split(".")
    tampered = f"{userid_part}.{exp_part}.deadbeef"
    assert sso.verify_session_cookie_value(SECRET, tampered, now=now) is None


def test_verify_session_cookie_wrong_secret_rejected():
    now = 1_000_000
    value = sso.make_session_cookie_value(SECRET, "YaoZuYi", days=30, now=now)
    assert sso.verify_session_cookie_value("other-secret", value, now=now) is None


@pytest.mark.parametrize("bad_value", [None, "", "no-dots-at-all", "a.b", "a.b.c.d"])
def test_verify_session_cookie_malformed_rejected(bad_value):
    assert sso.verify_session_cookie_value(SECRET, bad_value) is None


def test_make_session_cookie_rejects_empty_userid():
    with pytest.raises(ValueError):
        sso.make_session_cookie_value(SECRET, "")


# ── 真实企微 OAuth2 ──────────────────────────────────────────────────


def test_load_wecom_oauth_config_missing_returns_none(monkeypatch):
    monkeypatch.delenv("WECOM_GATEWAY_CORP_ID", raising=False)
    monkeypatch.delenv("WECOM_GATEWAY_AGENT_ID", raising=False)
    monkeypatch.delenv("WECOM_GATEWAY_SECRET", raising=False)
    assert sso.load_wecom_oauth_config() is None


def test_load_wecom_oauth_config_partial_still_none(monkeypatch):
    monkeypatch.setenv("WECOM_GATEWAY_CORP_ID", "corp1")
    monkeypatch.delenv("WECOM_GATEWAY_AGENT_ID", raising=False)
    monkeypatch.delenv("WECOM_GATEWAY_SECRET", raising=False)
    assert sso.load_wecom_oauth_config() is None


def test_load_wecom_oauth_config_complete(monkeypatch):
    monkeypatch.setenv("WECOM_GATEWAY_CORP_ID", "corp1")
    monkeypatch.setenv("WECOM_GATEWAY_AGENT_ID", "agent1")
    monkeypatch.setenv("WECOM_GATEWAY_SECRET", "sec1")
    cfg = sso.load_wecom_oauth_config()
    assert cfg == sso.WecomOAuthConfig(corp_id="corp1", agent_id="agent1", secret="sec1")


def test_build_wecom_authorize_url_contains_required_params():
    url = sso.build_wecom_authorize_url(
        corp_id="corp1", agent_id="agent1",
        redirect_uri="http://192.168.100.51:8090/portal/_sso/callback", state="xyz",
    )
    assert url.startswith(sso.WECOM_AUTHORIZE_BASE)
    assert "appid=corp1" in url
    assert "agentid=agent1" in url
    assert "state=xyz" in url
    assert "response_type=code" in url
    assert url.endswith("#wechat_redirect")


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_exchange_code_for_userid_success():
    cfg = sso.WecomOAuthConfig(corp_id="corp1", agent_id="agent1", secret="sec1")
    responses = [
        _FakeResponse({"errcode": 0, "access_token": "TOKEN123"}),
        _FakeResponse({"errcode": 0, "UserId": "YaoZuYi"}),
    ]
    with patch("portal_gateway.sso.requests.get", side_effect=responses):
        userid = sso.exchange_code_for_userid(cfg, "CODE123")
    assert userid == "YaoZuYi"


def test_exchange_code_for_userid_token_fetch_fails():
    cfg = sso.WecomOAuthConfig(corp_id="corp1", agent_id="agent1", secret="sec1")
    with patch("portal_gateway.sso.requests.get", return_value=_FakeResponse({"errcode": 40001})):
        assert sso.exchange_code_for_userid(cfg, "CODE123") is None


def test_exchange_code_for_userid_userinfo_fails():
    cfg = sso.WecomOAuthConfig(corp_id="corp1", agent_id="agent1", secret="sec1")
    responses = [
        _FakeResponse({"errcode": 0, "access_token": "TOKEN123"}),
        _FakeResponse({"errcode": 0, "OpenId": "some-external-guest"}),  # 无 UserId=外部访客
    ]
    with patch("portal_gateway.sso.requests.get", side_effect=responses):
        assert sso.exchange_code_for_userid(cfg, "CODE123") is None


# ── mock 登录开关 ────────────────────────────────────────────────────


@pytest.mark.parametrize("raw,expected", [
    (None, False), ("", False), ("0", False), ("false", False), ("False", False),
    ("1", True), ("true", True), ("yes", True),
])
def test_mock_login_enabled(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("PORTAL_GATEWAY_MOCK_LOGIN", raising=False)
    else:
        monkeypatch.setenv("PORTAL_GATEWAY_MOCK_LOGIN", raw)
    assert sso.mock_login_enabled() is expected


# ── 应急本地口令通道 ─────────────────────────────────────────────────


def test_emergency_login_disabled_by_default(monkeypatch):
    monkeypatch.delenv("PORTAL_GATEWAY_EMERGENCY_PASSWORD", raising=False)
    assert sso.emergency_login_enabled() is False
    assert sso.verify_emergency_password("anything") is False


def test_emergency_login_enabled_and_password_verified(monkeypatch):
    monkeypatch.setenv("PORTAL_GATEWAY_EMERGENCY_PASSWORD", "s3cr3t")
    assert sso.emergency_login_enabled() is True
    assert sso.verify_emergency_password("s3cr3t") is True
    assert sso.verify_emergency_password("wrong") is False
    assert sso.verify_emergency_password(None) is False


def test_emergency_userid_default_and_override(monkeypatch):
    monkeypatch.delenv("PORTAL_GATEWAY_EMERGENCY_USERID", raising=False)
    assert sso.emergency_userid() == "ShaoPeiShen"
    monkeypatch.setenv("PORTAL_GATEWAY_EMERGENCY_USERID", "OpsAlice")
    assert sso.emergency_userid() == "OpsAlice"
