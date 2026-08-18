"""交付层单测（spec: sc2-report-delivery）。对应 tasks 7.1-7.6。"""
from __future__ import annotations

import json
import re
from datetime import date

import pytest

from sc2 import config, notify
from sc2.review import PublishState, ReviewStore, UnconfirmedError, status_of
from sc2.webapp import GATEWAY_IDENTITY_HEADER, create_app, default_identity_resolver

BASE = date(2026, 8, 19)
PREFIX = "/procurement/sc2"


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("SC2_REPORTS_DIR", str(tmp_path))
    monkeypatch.delenv("ZP_GATE_PASSWORD", raising=False)
    yield


@pytest.fixture()
def client():
    app = create_app(base_date=BASE, mode="mock")
    app.config["TESTING"] = True
    return app.test_client()


# ── 7.1 路由前缀 ────────────────────────────────────────────────────────────

def test_所有路由位于统一门户前缀之下():
    """design D2/D9：自首版即为目标态，网关落地后只改映射、不改场景代码。"""
    app = create_app(base_date=BASE, mode="mock")
    rules = [str(r) for r in app.url_map.iter_rules()
             if r.endpoint != "static" and not r.endpoint.startswith("_zp_gate")]
    assert rules
    for rule in rules:
        assert rule.startswith(PREFIX), f"路由 {rule} 未落在 {PREFIX} 前缀下"


def test_周报页可访问(client):
    r = client.get(f"{PREFIX}/")
    assert r.status_code == 200
    assert "采购周报" in r.get_data(as_text=True)


def test_ping在前缀下且可用(client):
    r = client.get(f"{PREFIX}/api/ping")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_页内链接与静态资源不使用根路径绝对引用(client):
    """spec 场景：页内引用须基于前缀，否则网关落地时会全部指错。"""
    html = client.get(f"{PREFIX}/").get_data(as_text=True)
    for href in re.findall(r'(?:href|action|src)="([^"]+)"', html):
        if href.startswith("/"):
            assert href.startswith(PREFIX), f"根路径绝对引用：{href}"


# ── 7.2 门禁与访问日志 ──────────────────────────────────────────────────────

def test_设置口令后无口令请求被拒且不返回业务数据(monkeypatch):
    monkeypatch.setenv("ZP_GATE_PASSWORD", "s3cret")
    app = create_app(base_date=BASE, mode="mock")
    app.config["TESTING"] = True
    r = app.test_client().get(f"{PREFIX}/")
    assert r.status_code in (302, 401)
    body = r.get_data(as_text=True)
    assert "下单行数" not in body, "未通过门禁却泄露了业务数据"


def test_确认接口在门禁下也不得被未鉴权调用(monkeypatch):
    monkeypatch.setenv("ZP_GATE_PASSWORD", "s3cret")
    app = create_app(base_date=BASE, mode="mock")
    app.config["TESTING"] = True
    r = app.test_client().post(f"{PREFIX}/api/confirm", json={"confirmed_by": "x"})
    assert r.status_code == 401


def test_访问被记录(client, tmp_path):
    client.get(f"{PREFIX}/")
    assert config.access_log_path().exists()


# ── 7.3 网关鉴权接入点 ──────────────────────────────────────────────────────

def test_默认接入点为空壳不阻断():
    from flask import Flask
    app = Flask(__name__)
    with app.test_request_context("/"):
        assert default_identity_resolver() is None


def test_替换接入点即可改变身份来源而不动业务路由():
    """网关落地后只换这一个实现，路由与页面代码不动。"""
    app = create_app(base_date=BASE, mode="mock",
                     identity_resolver=lambda: "gw:姚祖怡")
    app.config["TESTING"] = True
    c = app.test_client()
    c.post(f"{PREFIX}/api/confirm", json={})       # 不传 confirmed_by，走网关身份
    store = ReviewStore()
    period = c.get(f"{PREFIX}/api/report").get_json()["period"]
    entry = store.get(period)
    assert entry.confirmed_by == "gw:姚祖怡"


def test_网关身份头常量已定义():
    """接入点必须存在（过渡期可空壳，但不得缺席）。"""
    assert GATEWAY_IDENTITY_HEADER


# ── 7.4 确认发布按钮 ────────────────────────────────────────────────────────

def test_周报页含确认发布按钮(client):
    html = client.get(f"{PREFIX}/").get_data(as_text=True)
    assert "确认发布" in html


def test_确认接口把该期转为已确认(client):
    period = client.get(f"{PREFIX}/api/report").get_json()["period"]
    assert status_of(ReviewStore(), period) == PublishState.PENDING
    r = client.post(f"{PREFIX}/api/confirm", json={"confirmed_by": "姚祖怡"})
    assert r.status_code == 200
    assert status_of(ReviewStore(), period) == PublishState.CONFIRMED


def test_确认人缺失且无网关身份时拒绝(client):
    r = client.post(f"{PREFIX}/api/confirm", json={})
    assert r.status_code == 400


def test_异常项在页面上被标出(client):
    html = client.get(f"{PREFIX}/").get_data(as_text=True)
    assert "阈值未经确认" in html or "未经专员确认" in html


# ── 7.5 推送范围 ────────────────────────────────────────────────────────────

def test_推送对象仅采购部群与采购部AI专员():
    assert set(notify.RECIPIENTS) == {"采购部群", "姚祖怡"}


def test_推送范围不含管理层():
    joined = "".join(notify.RECIPIENTS)
    for banned in ("管理层", "总经理", "CEO", "VP"):
        assert banned not in joined


def test_未确认时推送被拒(client):
    period = client.get(f"{PREFIX}/api/report").get_json()["period"]
    with pytest.raises(UnconfirmedError):
        notify.push(period, text="正文", store=ReviewStore())


def test_确认后推送一次且重复调用不再发(client, monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "_send", lambda url, text: sent.append(text))
    monkeypatch.setenv("SC2_WECOM_WEBHOOK_URL", "https://example.invalid/hook")
    period = client.get(f"{PREFIX}/api/report").get_json()["period"]
    client.post(f"{PREFIX}/api/confirm", json={"confirmed_by": "姚祖怡"})
    store = ReviewStore()
    assert notify.push(period, text="正文", store=store) is True
    assert notify.push(period, text="正文", store=store) is False
    assert len(sent) == 1


def test_扩大推送范围须显式变更而非运行时推断(monkeypatch):
    """spec：MUST NOT 由配置默认值或运行时推断实现。"""
    monkeypatch.setenv("SC2_EXTRA_RECIPIENTS", "管理层")
    import importlib
    importlib.reload(notify)
    assert set(notify.RECIPIENTS) == {"采购部群", "姚祖怡"}
    importlib.reload(notify)


# ── 7.6 服务入口路径引导 ────────────────────────────────────────────────────

def test_服务入口顶部含worktree路径引导():
    """队列 #300：入口脚本不得依赖全局 editable 指针指向谁。"""
    entry = config.SCENE_ROOT / "run_sc2.py"
    head = entry.read_text(encoding="utf-8")[:2000]
    assert "5-平台底座" in head and "sys.path.insert" in head


def test_端口默认为过渡期豁免端口():
    assert config.DEFAULT_PORT == 8095


def test_生成物均落reports目录(client, tmp_path):
    client.get(f"{PREFIX}/")
    client.post(f"{PREFIX}/api/confirm", json={"confirmed_by": "姚祖怡"})
    produced = list(tmp_path.iterdir())
    assert produced
    for p in produced:
        assert p.parent == tmp_path
