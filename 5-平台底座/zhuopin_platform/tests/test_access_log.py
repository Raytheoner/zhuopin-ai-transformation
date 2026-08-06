"""轻量访问日志采集框架测试（队列 #112）。

覆盖：纯逻辑（entry 序列化/时间戳默认值）+ append 落盘 + Flask 集成
（含 /api/ping 豁免、log_path=None 时不装/零回归、并发写入不串行错乱）。
"""
from __future__ import annotations

import json
import threading

import flask

from zhuopin_platform.shared_tools import access_log


# ── 纯逻辑：AccessLogEntry ───────────────────────────────────────────────────

def test_entry_auto_fills_timestamp_when_absent():
    entry = access_log.AccessLogEntry(service="s", method="GET", path="/", status=200, source_ip="1.2.3.4")
    assert entry.timestamp  # 非空，ISO 格式
    assert "T" in entry.timestamp


def test_entry_keeps_explicit_timestamp():
    entry = access_log.AccessLogEntry(service="s", method="GET", path="/", status=200,
                                      source_ip="1.2.3.4", timestamp="2026-01-01T00:00:00+00:00")
    assert entry.timestamp == "2026-01-01T00:00:00+00:00"


def test_entry_to_dict_contains_no_extra_identity_fields():
    entry = access_log.AccessLogEntry(service="s", method="POST", path="/x", status=201, source_ip="10.0.0.1")
    d = entry.to_dict()
    assert set(d.keys()) == {"service", "method", "path", "status", "source_ip", "timestamp"}


# ── AccessLogger：落盘 ───────────────────────────────────────────────────────

def test_logger_appends_jsonl_line(tmp_path):
    path = tmp_path / "access.jsonl"
    logger = access_log.AccessLogger(path)
    logger.record(service="svc", method="GET", path="/a", status=200, source_ip="1.1.1.1")
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["service"] == "svc" and rec["path"] == "/a" and rec["status"] == 200


def test_logger_creates_parent_dir(tmp_path):
    path = tmp_path / "nested" / "dir" / "access.jsonl"
    access_log.AccessLogger(path).record(service="s", method="GET", path="/", status=200, source_ip="")
    assert path.exists()


def test_logger_concurrent_writes_do_not_interleave(tmp_path):
    path = tmp_path / "access.jsonl"
    logger = access_log.AccessLogger(path)

    def _write(n):
        for i in range(20):
            logger.record(service=f"svc{n}", method="GET", path=f"/{i}", status=200, source_ip="")

    threads = [threading.Thread(target=_write, args=(n,)) for n in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 100
    for line in lines:
        json.loads(line)  # 每行必须是合法 JSON（未被交叉写入截断）


# ── Flask 集成 ───────────────────────────────────────────────────────────────

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
        return "submitted", 201

    return app


def test_install_noop_when_log_path_none():
    app = _make_app()
    access_log.install_flask_access_log(app, service_name="测试服务", log_path=None)
    client = app.test_client()
    assert client.get("/").status_code == 200  # 装不装都能跑，零回归


def test_install_records_request(tmp_path):
    log_path = tmp_path / "access.jsonl"
    app = _make_app()
    access_log.install_flask_access_log(app, service_name="测试服务", log_path=log_path)
    client = app.test_client()

    client.get("/")
    client.post("/submit")

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    rec0, rec1 = (json.loads(line) for line in lines)
    assert rec0["method"] == "GET" and rec0["path"] == "/" and rec0["status"] == 200
    assert rec1["method"] == "POST" and rec1["path"] == "/submit" and rec1["status"] == 201
    assert rec0["service"] == "测试服务"


def test_install_exempts_api_ping(tmp_path):
    log_path = tmp_path / "access.jsonl"
    app = _make_app()
    access_log.install_flask_access_log(app, service_name="测试服务", log_path=log_path)
    client = app.test_client()

    client.get("/api/ping")
    assert not log_path.exists()  # /api/ping 全程不落盘


def test_install_records_source_ip(tmp_path):
    log_path = tmp_path / "access.jsonl"
    app = _make_app()
    access_log.install_flask_access_log(app, service_name="测试服务", log_path=log_path)
    client = app.test_client()

    client.get("/", environ_overrides={"REMOTE_ADDR": "192.168.1.50"})
    rec = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert rec["source_ip"] == "192.168.1.50"


def test_install_custom_exempt_paths(tmp_path):
    log_path = tmp_path / "access.jsonl"
    app = _make_app()
    access_log.install_flask_access_log(app, service_name="测试服务", log_path=log_path,
                                        exempt_paths=("/api/ping", "/"))
    client = app.test_client()

    client.get("/")
    client.post("/submit")
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1  # 只有 /submit 被记录，"/" 被自定义豁免
