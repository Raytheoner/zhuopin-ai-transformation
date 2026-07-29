"""保供看板共享口令门禁接入测试（跨桌任务队列 #10 临时止血）。

全 mock 不触网。只验证 create_app() 接线正确——门禁本身的签名/校验逻辑由平台
`zhuopin_platform/tests/test_simple_gate.py` 覆盖，此处不重复。
"""
from __future__ import annotations

from zhuopin_platform.shared_tools import simple_gate as gate

from sc8 import webapp
from sc8.baoguan_service import SnapshotStore
from sc8.case_store import CaseStore

SECRET = "sc8-test-secret"


def _client(monkeypatch):
    app = webapp.create_app(snapshot_store=SnapshotStore(None),
                            case_store=CaseStore(":memory:"),
                            audit=None, ops_webhook_url=None)
    app.config.update(TESTING=True)
    return app, app.test_client()


def test_gate_noop_without_password_env(monkeypatch):
    monkeypatch.delenv("ZP_GATE_PASSWORD", raising=False)
    _, c = _client(monkeypatch)
    assert c.get("/").status_code == 200


def test_ping_exempt_even_with_gate_enabled(monkeypatch):
    monkeypatch.setenv("ZP_GATE_PASSWORD", SECRET)
    _, c = _client(monkeypatch)
    r = c.get("/api/ping")
    assert r.status_code == 200 and r.get_json()["status"] == "ok"


def test_dashboard_blocked_without_credentials(monkeypatch):
    monkeypatch.setenv("ZP_GATE_PASSWORD", SECRET)
    _, c = _client(monkeypatch)
    r = c.get("/")
    assert r.status_code == 302
    assert gate.LOGIN_PATH in r.headers["Location"]


def test_dashboard_allowed_with_auth_token_header(monkeypatch):
    monkeypatch.setenv("ZP_GATE_PASSWORD", SECRET)
    _, c = _client(monkeypatch)
    r = c.get("/", headers={"X-Auth-Token": SECRET})
    assert r.status_code == 200


def test_login_then_dashboard_and_cases_unlocked(monkeypatch):
    monkeypatch.setenv("ZP_GATE_PASSWORD", SECRET)
    _, c = _client(monkeypatch)
    login = c.post(gate.LOGIN_PATH, data={"password": SECRET, "next": "/"})
    assert login.status_code == 302
    assert c.get("/").status_code == 200
    assert c.get("/cases").status_code == 200
