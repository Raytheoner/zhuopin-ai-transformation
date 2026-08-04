"""portal_gateway.webapp 集成测试——串联 SSO/权限/路由/日志全链路。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from zhuopin_platform.audit import AuditLogger

from portal_gateway.permissions import PermissionTier
from portal_gateway.routing import Route
from portal_gateway.webapp import create_app

SECRET = "test-webapp-secret"


class _FakeBackendResponse:
    def __init__(self, *, status_code=200, body=b"<html>ok</html>", headers=None):
        self.status_code = status_code
        self._body = body
        self.raw = MagicMock()
        self.raw.headers = headers or {"Content-Type": "text/html"}

    def iter_content(self, chunk_size=8192):
        yield self._body


def _routes():
    return [
        Route(prefix="/", backend_base_url="http://127.0.0.1:8092", domain="portal",
              required_tier=PermissionTier.PUBLIC_READ),
        Route(prefix="/finance/fi2", backend_base_url="http://127.0.0.1:8094", domain="finance",
              required_tier=PermissionTier.DOMAIN_ADMIN),
    ]


def _mapping():
    return {
        "YaoZuYi": [{"domain": "procurement", "tier": PermissionTier.DOMAIN_ADMIN}],
        "SomeFinanceMember": [{"domain": "finance", "tier": PermissionTier.DOMAIN_MEMBER}],
        "tangyanping": [{"domain": "finance", "tier": PermissionTier.DOMAIN_ADMIN}],
    }


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.delenv("PORTAL_GATEWAY_MOCK_LOGIN", raising=False)
    monkeypatch.delenv("PORTAL_GATEWAY_EMERGENCY_PASSWORD", raising=False)
    monkeypatch.delenv("WECOM_GATEWAY_CORP_ID", raising=False)
    monkeypatch.delenv("WECOM_GATEWAY_AGENT_ID", raising=False)
    monkeypatch.delenv("WECOM_GATEWAY_SECRET", raising=False)
    return create_app(secret=SECRET, routes=_routes(), mapping=_mapping(),
                       audit_path=tmp_path / "portal_access.jsonl")


@pytest.fixture
def client(app):
    return app.test_client()


def _login_cookie(client, userid):
    from portal_gateway import sso
    client.set_cookie(sso.COOKIE_NAME, sso.make_session_cookie_value(SECRET, userid))


# ── 健康检查豁免鉴权 ──────────────────────────────────────────────────


def test_ping_exempt_no_auth_needed(client):
    resp = client.get("/api/ping")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


# ── 会话过期后重新引导登录 / 未登录跳转 ─────────────────────────────────


def test_root_path_unauthenticated_redirects_to_login(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/portal/_sso/login" in resp.headers["Location"]


def test_unknown_path_returns_404_when_no_catchall_route(tmp_path, monkeypatch):
    monkeypatch.delenv("PORTAL_GATEWAY_MOCK_LOGIN", raising=False)
    routes_without_catchall = [
        Route(prefix="/finance/fi2", backend_base_url="http://127.0.0.1:8094", domain="finance",
              required_tier=PermissionTier.DOMAIN_ADMIN),
    ]
    app = create_app(secret=SECRET, routes=routes_without_catchall, mapping=_mapping(),
                      audit_path=tmp_path / "portal_access.jsonl")
    resp = app.test_client().get("/totally/unknown/path/xyz")
    assert resp.status_code == 404


def test_unmatched_path_falls_through_to_catchall_route(client):
    # 默认路由表含 "/" 兜底，未知路径会被兜底匹配、按 portal 域鉴权（未登录见 302）
    resp = client.get("/totally/unknown/path/xyz", follow_redirects=False)
    assert resp.status_code == 302


# ── 会话签发失败 fail loud ───────────────────────────────────────────


def test_create_app_without_secret_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("PORTAL_GATEWAY_SESSION_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        create_app(routes=_routes(), mapping=_mapping(), audit_path=tmp_path / "a.jsonl")


# ── mock 登录（开发/试点期） ─────────────────────────────────────────


def test_mock_login_disabled_by_default_returns_404(client):
    resp = client.get("/portal/_sso/mock-login")
    assert resp.status_code == 404


def test_mock_login_page_shows_warning_when_enabled(app, monkeypatch):
    monkeypatch.setenv("PORTAL_GATEWAY_MOCK_LOGIN", "1")
    client = app.test_client()
    resp = client.get("/portal/_sso/mock-login")
    assert resp.status_code == 200
    assert "开发/试点登录" in resp.get_data(as_text=True)


def test_mock_login_then_access_root_succeeds(app, monkeypatch):
    monkeypatch.setenv("PORTAL_GATEWAY_MOCK_LOGIN", "1")
    client = app.test_client()
    login_resp = client.post("/portal/_sso/mock-login", data={"userid": "YaoZuYi", "next": "/"},
                              follow_redirects=False)
    assert login_resp.status_code == 302
    fake = _FakeBackendResponse(body=b"<html>portal home</html>")
    with patch("portal_gateway.routing.requests.request", return_value=fake):
        resp = client.get("/")
    assert resp.status_code == 200
    assert b"portal home" in resp.data


def test_login_chooser_lists_mock_link_when_enabled(app, monkeypatch):
    monkeypatch.setenv("PORTAL_GATEWAY_MOCK_LOGIN", "1")
    client = app.test_client()
    resp = client.get("/portal/_sso/login")
    assert "mock-login" in resp.get_data(as_text=True)


def test_login_chooser_hides_oauth_link_when_not_configured(client):
    resp = client.get("/portal/_sso/login")
    assert "oauth/start" not in resp.get_data(as_text=True)


# ── 应急登录：不在任何可见页面被链接 + 未配置时 fail-closed ────────────


def test_emergency_login_page_never_linked_from_chooser(app, monkeypatch):
    monkeypatch.setenv("PORTAL_GATEWAY_MOCK_LOGIN", "1")
    client = app.test_client()
    resp = client.get("/portal/_sso/login")
    assert "emergency-login" not in resp.get_data(as_text=True)


def test_emergency_login_rejected_when_not_configured(client):
    resp = client.post("/portal/_sso/emergency-login", data={"password": "anything"})
    assert resp.status_code == 401


def test_emergency_login_success_when_configured(app, monkeypatch):
    monkeypatch.setenv("PORTAL_GATEWAY_EMERGENCY_PASSWORD", "s3cr3t")
    monkeypatch.setenv("PORTAL_GATEWAY_EMERGENCY_USERID", "tangyanping")
    client = app.test_client()
    resp = client.post("/portal/_sso/emergency-login", data={"password": "s3cr3t", "next": "/finance/fi2"},
                        follow_redirects=False)
    assert resp.status_code == 302
    fake = _FakeBackendResponse(body=b"fi2 home")
    with patch("portal_gateway.routing.requests.request", return_value=fake):
        resp2 = client.get("/finance/fi2")
    assert resp2.status_code == 200


# ── 三层权限判定：域管理员放行 / 域成员权限不足被拒 ─────────────────────


def test_domain_admin_can_access_gated_route(client):
    _login_cookie(client, "tangyanping")
    fake = _FakeBackendResponse(body=b"fi2 content")
    with patch("portal_gateway.routing.requests.request", return_value=fake):
        resp = client.get("/finance/fi2")
    assert resp.status_code == 200


def test_domain_member_insufficient_tier_rejected(client):
    _login_cookie(client, "SomeFinanceMember")
    resp = client.get("/finance/fi2")
    assert resp.status_code == 403


def test_unmapped_user_fail_closed_to_public_read(client):
    _login_cookie(client, "SomeoneUnknown")
    fake = _FakeBackendResponse(body=b"portal home")
    with patch("portal_gateway.routing.requests.request", return_value=fake):
        resp = client.get("/")  # portal 域只要求 PUBLIC_READ，未登记用户也够
    assert resp.status_code == 200


# ── OAuth：未配置 404 / state 不匹配拒绝 ────────────────────────────


def test_oauth_start_404_when_not_configured(client):
    resp = client.get("/portal/_sso/oauth/start")
    assert resp.status_code == 404


def test_oauth_callback_state_mismatch_rejected(app, monkeypatch):
    monkeypatch.setenv("WECOM_GATEWAY_CORP_ID", "corp1")
    monkeypatch.setenv("WECOM_GATEWAY_AGENT_ID", "agent1")
    monkeypatch.setenv("WECOM_GATEWAY_SECRET", "sec1")
    client = app.test_client()
    client.set_cookie("zp_portal_oauth_state", "expected-state")
    resp = client.get("/portal/_sso/oauth/callback?state=wrong-state&code=abc")
    assert resp.status_code == 400


def test_oauth_start_sets_state_cookie_and_redirects(app, monkeypatch):
    monkeypatch.setenv("WECOM_GATEWAY_CORP_ID", "corp1")
    monkeypatch.setenv("WECOM_GATEWAY_AGENT_ID", "agent1")
    monkeypatch.setenv("WECOM_GATEWAY_SECRET", "sec1")
    client = app.test_client()
    resp = client.get("/portal/_sso/oauth/start?next=/finance/fi2", follow_redirects=False)
    assert resp.status_code == 302
    assert "open.weixin.qq.com" in resp.headers["Location"]
    assert client.get_cookie("zp_portal_oauth_state") is not None


# ── 访问日志：通过/拒绝均留痕，含 userid/path/tier/allowed ──────────────


def test_access_log_records_both_allowed_and_denied(tmp_path, monkeypatch):
    monkeypatch.delenv("PORTAL_GATEWAY_MOCK_LOGIN", raising=False)
    audit_path = tmp_path / "portal_access.jsonl"
    app = create_app(secret=SECRET, routes=_routes(), mapping=_mapping(), audit_path=audit_path)
    client = app.test_client()

    # 未登录 → unauthenticated
    client.get("/")
    # 登录但权限不足 → insufficient_tier
    from portal_gateway import sso
    client.set_cookie(sso.COOKIE_NAME, sso.make_session_cookie_value(SECRET, "SomeFinanceMember"))
    client.get("/finance/fi2")
    # 登录且权限足够 → authorized
    client.set_cookie(sso.COOKIE_NAME, sso.make_session_cookie_value(SECRET, "tangyanping"))
    fake = _FakeBackendResponse(body=b"ok")
    with patch("portal_gateway.routing.requests.request", return_value=fake):
        client.get("/finance/fi2")

    logger = AuditLogger.jsonl(audit_path)
    records = logger.query_by(scenario="portal-gateway")
    auth_results = {r["decision"]["auth_result"] for r in records}
    assert auth_results == {"unauthenticated", "insufficient_tier", "authorized"}
