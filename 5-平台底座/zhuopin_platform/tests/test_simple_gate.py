"""共享口令门禁测试（跨桌任务队列 #10 临时止血，见 shared_tools/simple_gate.py 顶部说明）。

覆盖：cookie 签发/校验/过期/篡改、X-Auth-Token 校验、Flask 集成（含 /api/ping 豁免、
密码未配置时门禁自动跳过——保证既有 create_app() 调用点/测试零回归）。
"""
from __future__ import annotations

import flask
import pytest

from zhuopin_platform.shared_tools import simple_gate as gate

SECRET = "correct-horse-battery-staple"


# ── cookie 签发/校验 ─────────────────────────────────────────────────────────

def test_valid_cookie_round_trips():
    value = gate.make_cookie_value(SECRET, now=1_000_000)
    assert gate.verify_cookie_value(SECRET, value, now=1_000_000)


def test_cookie_rejected_after_expiry():
    value = gate.make_cookie_value(SECRET, days=30, now=1_000_000)
    just_before_expiry = 1_000_000 + 30 * 86400 - 1
    just_after_expiry = 1_000_000 + 30 * 86400 + 1
    assert gate.verify_cookie_value(SECRET, value, now=just_before_expiry)
    assert not gate.verify_cookie_value(SECRET, value, now=just_after_expiry)


def test_cookie_rejected_with_wrong_secret():
    value = gate.make_cookie_value(SECRET, now=1_000_000)
    assert not gate.verify_cookie_value("wrong-secret", value, now=1_000_000)


def test_cookie_tampering_rejected():
    value = gate.make_cookie_value(SECRET, now=1_000_000)
    exp_str, _, sig = value.partition(".")
    tampered = f"{int(exp_str) + 3600}.{sig}"          # 试图延长过期时间但签名对不上
    assert not gate.verify_cookie_value(SECRET, tampered, now=1_000_000)


@pytest.mark.parametrize("bad", [None, "", "no-dot-here", "abc.def"])
def test_cookie_malformed_rejected(bad):
    assert not gate.verify_cookie_value(SECRET, bad)


# ── X-Auth-Token（程序化访问）───────────────────────────────────────────────

def test_auth_token_exact_match_ok():
    assert gate.verify_auth_token(SECRET, SECRET)


def test_auth_token_mismatch_rejected():
    assert not gate.verify_auth_token(SECRET, "not-the-secret")
    assert not gate.verify_auth_token(SECRET, None)
    assert not gate.verify_auth_token(SECRET, "")


# ── cookie header 解析（供 http.server 等非 Flask 场景使用）─────────────────

def test_parse_cookie_header_extracts_named_cookie():
    header = f"other=1; {gate.COOKIE_NAME}=abc123; another=x"
    assert gate.parse_cookie_header(header, gate.COOKIE_NAME) == "abc123"


def test_parse_cookie_header_missing_returns_none():
    assert gate.parse_cookie_header("other=1", gate.COOKIE_NAME) is None
    assert gate.parse_cookie_header(None, gate.COOKIE_NAME) is None


def test_is_authorized_via_token_or_cookie():
    now = 1_000_000
    cookie_val = gate.make_cookie_value(SECRET, now=now)
    header = f"{gate.COOKIE_NAME}={cookie_val}"
    assert gate.is_authorized(SECRET, cookie_header=header, auth_token=None, now=now)
    assert gate.is_authorized(SECRET, cookie_header=None, auth_token=SECRET, now=now)
    assert not gate.is_authorized(SECRET, cookie_header=None, auth_token=None, now=now)
    assert not gate.is_authorized(SECRET, cookie_header="junk=1", auth_token="wrong", now=now)


# ── 开放重定向防护 ────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad_next,expected", [
    ("//evil.com/phish", "/"),
    ("http://evil.com", "/"),
    ("", "/"),
    (None, "/"),
    ("/cases?closed=1", "/cases?closed=1"),
])
def test_safe_next_blocks_open_redirect(bad_next, expected):
    assert gate._safe_next(bad_next) == expected


# ── Flask 集成 ───────────────────────────────────────────────────────────

def _make_app():
    app = flask.Flask(__name__)

    @app.get("/api/ping")
    def ping():
        return {"status": "ok"}

    @app.get("/")
    def index():
        return "hello"

    @app.post("/submit")
    def submit():
        return "submitted"

    return app


def test_gate_noop_when_password_unset(monkeypatch):
    monkeypatch.delenv("ZP_GATE_PASSWORD", raising=False)
    app = _make_app()
    gate.install_flask_gate(app, service_name="测试服务")
    client = app.test_client()
    # 未配置口令 → 门禁不生效，直接放行（保证既有 create_app() 调用点零回归）
    assert client.get("/").status_code == 200


def test_gate_blocks_unauthenticated_get_with_redirect(monkeypatch):
    monkeypatch.setenv("ZP_GATE_PASSWORD", SECRET)
    app = _make_app()
    gate.install_flask_gate(app, service_name="测试服务")
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 302
    assert gate.LOGIN_PATH in resp.headers["Location"]


def test_gate_blocks_unauthenticated_post_with_401(monkeypatch):
    monkeypatch.setenv("ZP_GATE_PASSWORD", SECRET)
    app = _make_app()
    gate.install_flask_gate(app, service_name="测试服务")
    client = app.test_client()
    resp = client.post("/submit")
    assert resp.status_code == 401


def test_gate_exempts_api_ping(monkeypatch):
    monkeypatch.setenv("ZP_GATE_PASSWORD", SECRET)
    app = _make_app()
    gate.install_flask_gate(app, service_name="测试服务")
    client = app.test_client()
    assert client.get("/api/ping").status_code == 200


def test_gate_allows_via_auth_token_header(monkeypatch):
    monkeypatch.setenv("ZP_GATE_PASSWORD", SECRET)
    app = _make_app()
    gate.install_flask_gate(app, service_name="测试服务")
    client = app.test_client()
    resp = client.get("/", headers={"X-Auth-Token": SECRET})
    assert resp.status_code == 200
    resp_bad = client.get("/", headers={"X-Auth-Token": "wrong"})
    assert resp_bad.status_code == 302


def test_login_flow_sets_cookie_and_unlocks(monkeypatch):
    monkeypatch.setenv("ZP_GATE_PASSWORD", SECRET)
    app = _make_app()
    gate.install_flask_gate(app, service_name="测试服务")
    client = app.test_client()

    # 错误口令：回登录页而非跳转，不设 cookie
    bad = client.post(gate.LOGIN_PATH, data={"password": "wrong", "next": "/"})
    assert bad.status_code == 200
    assert "不正确" in bad.get_data(as_text=True)

    # 正确口令：302 回 next，且后续请求带着 client 的 cookie jar 能直接通过
    ok = client.post(gate.LOGIN_PATH, data={"password": SECRET, "next": "/"})
    assert ok.status_code == 302
    assert ok.headers["Location"] in ("/", "http://localhost/")

    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == "hello"


def test_login_next_defends_open_redirect(monkeypatch):
    monkeypatch.setenv("ZP_GATE_PASSWORD", SECRET)
    app = _make_app()
    gate.install_flask_gate(app, service_name="测试服务")
    client = app.test_client()
    ok = client.post(gate.LOGIN_PATH, data={"password": SECRET, "next": "//evil.com"})
    assert ok.status_code == 302
    assert "evil.com" not in ok.headers["Location"]


def test_logout_clears_cookie(monkeypatch):
    monkeypatch.setenv("ZP_GATE_PASSWORD", SECRET)
    app = _make_app()
    gate.install_flask_gate(app, service_name="测试服务")
    client = app.test_client()
    client.post(gate.LOGIN_PATH, data={"password": SECRET, "next": "/"})
    assert client.get("/").status_code == 200

    client.get(gate.LOGOUT_PATH)
    resp = client.get("/")
    assert resp.status_code == 302
