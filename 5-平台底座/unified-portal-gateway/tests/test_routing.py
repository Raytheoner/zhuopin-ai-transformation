"""portal_gateway.routing 单测——覆盖 spec portal-gateway-routing 全部 Scenario。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from portal_gateway.permissions import PermissionTier
from portal_gateway.routing import (
    Route,
    build_forward_headers,
    default_route_table,
    forward_request,
    match_route,
    resolve_backend_gate_password,
)


@pytest.fixture
def routes():
    return [
        Route(prefix="/", backend_base_url="http://127.0.0.1:8092", domain="portal",
              required_tier=PermissionTier.PUBLIC_READ),
        Route(prefix="/procurement/baoguan", backend_base_url="http://127.0.0.1:8091",
              domain="procurement", required_tier=PermissionTier.DOMAIN_MEMBER,
              backend_gate_password_env="BAOGUAN_GATE_PASSWORD"),
    ]


# ── 路由匹配（统一路由映射） ──────────────────────────────────────────


def test_match_route_specific_prefix_wins_over_catchall(routes):
    route = match_route(routes, "/procurement/baoguan/api/cases")
    assert route.domain == "procurement"


def test_match_route_falls_back_to_catchall(routes):
    route = match_route(routes, "/data/sales_dashboard_data.json")
    assert route.domain == "portal"


def test_match_route_root_path(routes):
    route = match_route(routes, "/")
    assert route.domain == "portal"


def test_default_route_table_home_pilot():
    table = default_route_table()
    assert len(table) == 1
    assert table[0].prefix == "/"
    assert table[0].domain == "portal"
    assert table[0].required_tier == PermissionTier.PUBLIC_READ


def test_default_route_table_honors_backend_override(monkeypatch):
    monkeypatch.setenv("PORTAL_GATEWAY_HOME_BACKEND", "http://127.0.0.1:9999")
    table = default_route_table()
    assert table[0].backend_base_url == "http://127.0.0.1:9999"


# ── 转发头处理（决策6：simple_gate 后端注入 X-Auth-Token 避免双重拦截） ──


def test_build_forward_headers_strips_hop_by_hop():
    headers = build_forward_headers(
        {"Host": "portal:8090", "Cookie": "zp_portal_sso=abc", "Accept": "text/html",
         "Content-Length": "123", "Connection": "keep-alive"},
        backend_gate_password=None,
    )
    assert "Host" not in headers
    assert "Cookie" not in headers
    assert "Content-Length" not in headers
    assert "Connection" not in headers
    assert headers["Accept"] == "text/html"


def test_build_forward_headers_injects_auth_token_when_backend_gate_configured():
    headers = build_forward_headers({"Accept": "text/html"}, backend_gate_password="secret123")
    assert headers["X-Auth-Token"] == "secret123"


def test_build_forward_headers_no_token_when_backend_gate_not_configured():
    headers = build_forward_headers({"Accept": "text/html"}, backend_gate_password=None)
    assert "X-Auth-Token" not in headers


def test_resolve_backend_gate_password_reads_env(monkeypatch):
    route = Route(prefix="/x", backend_base_url="http://x", domain="x",
                   required_tier=PermissionTier.PUBLIC_READ, backend_gate_password_env="MY_GATE_PW")
    monkeypatch.setenv("MY_GATE_PW", "hunter2")
    assert resolve_backend_gate_password(route) == "hunter2"


def test_resolve_backend_gate_password_none_when_env_unset(monkeypatch):
    route = Route(prefix="/x", backend_base_url="http://x", domain="x",
                   required_tier=PermissionTier.PUBLIC_READ, backend_gate_password_env="MY_GATE_PW_UNSET")
    monkeypatch.delenv("MY_GATE_PW_UNSET", raising=False)
    assert resolve_backend_gate_password(route) is None


def test_resolve_backend_gate_password_none_when_route_has_no_env():
    route = Route(prefix="/x", backend_base_url="http://x", domain="x",
                   required_tier=PermissionTier.PUBLIC_READ)
    assert resolve_backend_gate_password(route) is None


# ── 请求转发（新增路由映射后端零改动即生效 / 单个后端异常不影响其他路由） ─


def test_forward_request_builds_correct_url_and_calls_requests():
    route = Route(prefix="/", backend_base_url="http://127.0.0.1:8092", domain="portal",
                   required_tier=PermissionTier.PUBLIC_READ)
    fake_response = MagicMock(status_code=200)
    with patch("portal_gateway.routing.requests.request", return_value=fake_response) as mock_req:
        resp = forward_request(route, "/index.html", method="GET", headers={"Accept": "text/html"})
    assert resp is fake_response
    args, kwargs = mock_req.call_args
    assert args[0] == "GET"
    assert args[1] == "http://127.0.0.1:8092/index.html"
    assert kwargs["stream"] is True
    assert kwargs["allow_redirects"] is False


def test_forward_request_appends_raw_query_string():
    route = Route(prefix="/", backend_base_url="http://127.0.0.1:8092", domain="portal",
                   required_tier=PermissionTier.PUBLIC_READ)
    fake_response = MagicMock(status_code=200)
    with patch("portal_gateway.routing.requests.request", return_value=fake_response) as mock_req:
        forward_request(route, "/search", method="GET", headers={}, query_string="q=a+b&q=c")
    args, _kwargs = mock_req.call_args
    assert args[1] == "http://127.0.0.1:8092/search?q=a+b&q=c"


def test_forward_request_single_backend_failure_is_isolated():
    route = Route(prefix="/procurement/baoguan", backend_base_url="http://127.0.0.1:8091",
                   domain="procurement", required_tier=PermissionTier.DOMAIN_MEMBER)
    with patch("portal_gateway.routing.requests.request", side_effect=ConnectionError("backend down")):
        with pytest.raises(ConnectionError):
            forward_request(route, "/", method="GET", headers={})
    # 该异常应由 webapp.py 层面捕获转 502，不在本层吞掉——这里只验证异常
    # 不会误伤其他 route 对象的转发调用（各自独立函数调用，无共享可变状态）。
    other_route = Route(prefix="/", backend_base_url="http://127.0.0.1:8092", domain="portal",
                         required_tier=PermissionTier.PUBLIC_READ)
    fake_response = MagicMock(status_code=200)
    with patch("portal_gateway.routing.requests.request", return_value=fake_response):
        resp = forward_request(other_route, "/", method="GET", headers={})
    assert resp.status_code == 200
