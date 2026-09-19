"""Q2 门户页 `/quality/q2`（队列 §一 `#612` tasks 5.1）：路由前缀／mock 标注／网关接入点空壳三件。"""
from __future__ import annotations

from q2_8d_verdict import config
from q2_8d_verdict.webapp import GATEWAY_IDENTITY_HEADER, create_app, default_identity_resolver


def _client(**kw):
    app = create_app(audit_path="reports/test_q2_web_audit.jsonl", **kw)
    return app.test_client()


def test_ping_is_exempt_and_prefixed():
    client = _client()
    resp = client.get(f"{config.ROUTE_PREFIX}/api/ping")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok", "service": config.SERVICE_NAME}


def test_index_renders_mock_banner_and_summary_tables():
    client = _client()
    resp = client.get(f"{config.ROUTE_PREFIX}/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "mock" in body
    assert "并非真实 8D 评审结论" in body
    assert config.SERVICE_NAME in body
    assert "七维得分" in body
    assert "分级分布" in body
    assert "D1" in body and "D7" in body


def test_root_without_prefix_is_404():
    client = _client()
    assert client.get("/").status_code == 404
    assert client.get("/api/ping").status_code == 404


def test_default_identity_resolver_reads_gateway_header():
    app = create_app(audit_path="reports/test_q2_web_audit.jsonl")
    with app.test_request_context("/", headers={GATEWAY_IDENTITY_HEADER: "ShaoPeiShen"}):
        assert default_identity_resolver() == "ShaoPeiShen"
    with app.test_request_context("/"):
        assert default_identity_resolver() is None


def test_identity_resolver_is_injectable_and_does_not_block_readonly_page():
    calls = []

    def _resolver():
        calls.append(1)
        return None

    client = _client(identity_resolver=_resolver)
    resp = client.get(f"{config.ROUTE_PREFIX}/")
    assert resp.status_code == 200
    assert calls == [1]


def test_gate_is_noop_without_env_var(monkeypatch):
    monkeypatch.delenv("ZP_GATE_PASSWORD", raising=False)
    client = _client()
    assert client.get(f"{config.ROUTE_PREFIX}/").status_code == 200


def test_gate_activates_when_env_var_set(monkeypatch):
    monkeypatch.setenv("ZP_GATE_PASSWORD", "test-secret")
    client = _client()
    resp = client.get(f"{config.ROUTE_PREFIX}/")
    assert resp.status_code == 302  # 未带 cookie/token，被门禁重定向到登录页
    assert client.get(f"{config.ROUTE_PREFIX}/api/ping").status_code == 200  # 健康检查仍豁免
