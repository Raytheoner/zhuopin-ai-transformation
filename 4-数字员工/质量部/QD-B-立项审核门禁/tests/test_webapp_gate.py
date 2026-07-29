"""QD-B 共享口令门禁接入测试（跨桌任务队列 #10 临时止血）。

只验证 create_app() 接线正确——门禁签名/校验逻辑由平台
`zhuopin_platform/tests/test_simple_gate.py` 覆盖，此处不重复。
"""
from __future__ import annotations

from zhuopin_platform.shared_tools import simple_gate as gate

from qd_b_gate.webapp import create_app

SECRET = "qdb-test-secret"


def _client(tmp_path):
    app = create_app(upload_dir=tmp_path / "uploads", audit_path=tmp_path / "audit.jsonl")
    app.config["TESTING"] = True
    return app, app.test_client()


def test_gate_noop_without_password_env(monkeypatch, tmp_path):
    monkeypatch.delenv("ZP_GATE_PASSWORD", raising=False)
    _, c = _client(tmp_path)
    assert c.get("/").status_code == 200


def test_ping_exempt_even_with_gate_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("ZP_GATE_PASSWORD", SECRET)
    _, c = _client(tmp_path)
    r = c.get("/api/ping")
    assert r.status_code == 200 and r.get_json()["status"] == "ok"


def test_index_blocked_without_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("ZP_GATE_PASSWORD", SECRET)
    _, c = _client(tmp_path)
    r = c.get("/")
    assert r.status_code == 302
    assert gate.LOGIN_PATH in r.headers["Location"]


def test_index_allowed_with_auth_token_header(monkeypatch, tmp_path):
    monkeypatch.setenv("ZP_GATE_PASSWORD", SECRET)
    _, c = _client(tmp_path)
    r = c.get("/", headers={"X-Auth-Token": SECRET})
    assert r.status_code == 200


def test_login_then_index_unlocked(monkeypatch, tmp_path):
    monkeypatch.setenv("ZP_GATE_PASSWORD", SECRET)
    _, c = _client(tmp_path)
    login = c.post(gate.LOGIN_PATH, data={"password": SECRET, "next": "/"})
    assert login.status_code == 302
    assert c.get("/").status_code == 200
