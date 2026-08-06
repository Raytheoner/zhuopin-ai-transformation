"""AI 运营指挥中心 `serve.py` 轻量访问日志测试（队列 #112，自包含实现，无 Flask）。

`serve.py` 是纯标准库 `http.server.SimpleHTTPRequestHandler`（"零三方依赖"既定设计
原则，见文件顶部说明），没有类似 Flask `test_client()` 的进程内测试客户端可用——
真实起一个 `ThreadingHTTPServer`（OS 随机端口）+ 真实 HTTP 请求是标准做法。

`ACCESS_LOG_PATH` 通过 monkeypatch 重定向到 tmp_path，避免测试污染真实场景的
`reports/` 目录。
"""
from __future__ import annotations

import http.client
import json
import sys
import threading
import time
from pathlib import Path

import pytest

SCENE = Path(__file__).resolve().parent.parent
if str(SCENE) not in sys.path:
    sys.path.insert(0, str(SCENE))

import serve  # noqa: E402


@pytest.fixture
def running_server(monkeypatch, tmp_path):
    log_path = tmp_path / "access.jsonl"
    monkeypatch.setattr(serve, "ACCESS_LOG_PATH", str(log_path))
    httpd = serve.ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield port, log_path
    finally:
        httpd.shutdown()
        httpd.server_close()


def _get(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        resp.read()
        return resp.status
    finally:
        conn.close()


def _post(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("POST", path)
        resp = conn.getresponse()
        resp.read()
        return resp.status
    finally:
        conn.close()


def _wait_for_lines(log_path, n, timeout=2.0):
    """服务端在独立线程里于响应发出**之后**才落盘日志（finally 块），与客户端
    `getresponse()` 返回之间存在微小竞态——轮询等待，避免偶发计时导致的假失败。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if log_path.exists() and len(log_path.read_text(encoding="utf-8").splitlines()) >= n:
            return log_path.read_text(encoding="utf-8").splitlines()
        time.sleep(0.02)
    raise AssertionError(f"等待 {log_path} 达到 {n} 行超时")


def test_api_ping_exempt_from_access_log(running_server):
    port, log_path = running_server
    status = _get(port, "/api/ping")
    assert status == 200
    time.sleep(0.1)   # 给豁免路径一个公平的落盘窗口再断言"确实没写"
    assert not log_path.exists()


def test_real_get_route_recorded_with_status(running_server):
    port, log_path = running_server
    status = _get(port, "/_gate/login")
    assert status == 200
    rec = json.loads(_wait_for_lines(log_path, 1)[0])
    assert rec["method"] == "GET" and rec["path"] == "/_gate/login" and rec["status"] == 200
    assert rec["service"] == "AI 运营指挥中心"
    assert "source_ip" in rec and "timestamp" in rec


def test_404_status_captured_correctly(running_server):
    """确认 send_error 路径（静态文件不存在）也正确经 send_response 覆写捕获状态码。"""
    port, log_path = running_server
    status = _get(port, "/no-such-file-xyz.html")
    assert status == 404
    rec = json.loads(_wait_for_lines(log_path, 1)[0])
    assert rec["status"] == 404


def test_post_route_recorded(running_server):
    port, log_path = running_server
    status = _post(port, "/unsupported")
    assert status == 501
    rec = json.loads(_wait_for_lines(log_path, 1)[0])
    assert rec["method"] == "POST" and rec["path"] == "/unsupported" and rec["status"] == 501


def test_multiple_requests_all_recorded(running_server):
    port, log_path = running_server
    _get(port, "/api/ping")     # 豁免
    _get(port, "/_gate/login")
    _get(port, "/_gate/logout")
    lines = _wait_for_lines(log_path, 2)
    paths = [json.loads(line)["path"] for line in lines]
    assert paths == ["/_gate/login", "/_gate/logout"]
