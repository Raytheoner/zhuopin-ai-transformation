"""保供 Web 服务（webapp）测试 —— Flask test_client，全 mock 不触网。

覆盖：ping、/api/baoguan 空态、手动刷新更新缓存、并发刷新串行（不重复取数）、
壳页含 fetch 引导/刷新按钮且不嵌入真实数据、案例路由（建案/推进/草稿对客闸）。
"""
from __future__ import annotations

import threading

from sc8 import webapp
from sc8.baoguan_service import Snapshot, SnapshotStore
from sc8.case_store import CaseStore


def _snap(reds=0):
    rows = [{"id": f"R{i}", "so": f"FO-{i}", "ship": "2026-06-10", "risk": "red",
             "cg": 61, "bn": "C1", "comp": 3, "nf": 1, "cust": "比亚迪"} for i in range(reds)]
    return Snapshot(generated_at="2026-06-24T10:00:00", today="2026-06-24", rows=rows,
                    counts={"red": reds, "gap": 0, "yel": 0, "grn": 0},
                    status="2", param_version="sc8-params-v0", ok=True)


def _client(monkeypatch, *, compute=None):
    if compute is not None:
        monkeypatch.setattr(webapp, "compute_snapshot", compute)
    app = webapp.create_app(snapshot_store=SnapshotStore(None),
                            case_store=CaseStore(":memory:"),
                            audit=None, ops_webhook_url=None)
    app.config.update(TESTING=True)
    return app, app.test_client()


def test_ping(monkeypatch):
    _, c = _client(monkeypatch)
    r = c.get("/api/ping")
    assert r.status_code == 200 and r.get_json()["status"] == "ok"


def test_baoguan_empty_state(monkeypatch):
    _, c = _client(monkeypatch)
    j = c.get("/api/baoguan").get_json()
    assert j["ok"] is False and j["rows"] == [] and "尚未刷新" in j["note"]


def test_manual_refresh_updates_cache(monkeypatch):
    _, c = _client(monkeypatch, compute=lambda **kw: _snap(reds=2))
    r = c.post("/api/refresh")
    assert r.status_code == 200 and r.get_json()["ok"] is True
    assert r.get_json()["counts"]["red"] == 2
    j = c.get("/api/baoguan").get_json()
    assert j["ok"] is True and len(j["rows"]) == 2


def test_refresh_failloud_returns_502(monkeypatch):
    def _boom(**kw):
        raise RuntimeError("FO unreachable")
    _, c = _client(monkeypatch, compute=_boom)
    r = c.post("/api/refresh")
    assert r.status_code == 502 and r.get_json()["ok"] is False


def test_concurrent_refresh_is_serial(monkeypatch):
    """刷新进行中并发请求 → 不重复取数，返回 409 busy。"""
    entered = threading.Event()
    release = threading.Event()
    calls = {"n": 0}

    def _slow(**kw):
        calls["n"] += 1
        entered.set()
        release.wait(timeout=5)
        return _snap(reds=1)

    app, c = _client(monkeypatch, compute=_slow)

    def _bg():
        app.test_client().post("/api/refresh")

    t = threading.Thread(target=_bg)
    t.start()
    assert entered.wait(timeout=5)            # 第一次刷新已进入 compute（持锁）
    r2 = c.post("/api/refresh")               # 并发第二次
    assert r2.status_code == 409 and r2.get_json().get("busy") is True
    release.set()
    t.join(timeout=5)
    assert calls["n"] == 1                     # 第二次没有触发 compute


def test_shell_page_has_fetch_and_no_real_data(monkeypatch):
    _, c = _client(monkeypatch)
    html = c.get("/").get_data(as_text=True)
    assert "fetch('/api/baoguan')" in html
    assert 'id="refresh"' in html
    # 壳页本身不嵌入真实成品数据（DATA 启动为空数组）
    assert "var DATA=[]" in html
    assert "比亚迪" not in html


def test_cases_flow_and_customer_gate(monkeypatch):
    app, c = _client(monkeypatch)
    # 手动建案
    r = c.post("/cases/new", data={"item_code": "S02Y.0188", "fo_id": "FO-1",
                                   "customer_name": "比亚迪", "ship_date": "2026-06-10",
                                   "confirmed_gap_days": "61", "bottleneck_material": "S02Y.0188",
                                   "actor": "运维"}, follow_redirects=False)
    assert r.status_code in (301, 302)
    # 列表可见
    assert "S02Y.0188" in c.get("/cases").get_data(as_text=True)
    # 对客草稿落闸提示
    draft = c.get("/cases/1/draft?kind=customer").get_data(as_text=True)
    assert "CUSTOMER_OUTBOUND_ENABLED=False" in draft and "绝不自动外发" in draft
    # 推进状态
    r = c.post("/cases/1", data={"actor": "保供小王", "note": "已催", "action": "advance"})
    assert r.status_code in (301, 302)
    assert "协调" in c.get("/cases/1").get_data(as_text=True)
