"""FI2 轻量访问日志接入测试（队列 #112）。

只验证 create_app() 接线正确——落盘/中间件逻辑由平台
`zhuopin_platform/tests/test_access_log.py` 覆盖，此处不重复。FI2 的 `create_app`
只接受 `reports_dir`（无独立 access_log_path 参数），故访问日志恒接入
`reports_dir / "fi2_http_requests.jsonl"`，与既有 `fi2_web_access_trace.jsonl`
（连接器访问痕迹，语义不同）命名区分。
"""
from __future__ import annotations

import json

from fi2.webapp import create_app


def _client(tmp_path):
    app = create_app(reports_dir=tmp_path / "reports")
    app.config["TESTING"] = True
    return app, app.test_client()


def test_access_log_records_index_hit(tmp_path):
    _, c = _client(tmp_path)
    c.get("/")
    log_path = tmp_path / "reports" / "fi2_http_requests.jsonl"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["path"] == "/" and rec["service"] == "FI2 三单匹配自动对账"


def test_access_log_exempts_api_ping(tmp_path):
    _, c = _client(tmp_path)
    c.get("/api/ping")
    log_path = tmp_path / "reports" / "fi2_http_requests.jsonl"
    assert not log_path.exists()


def test_access_log_distinct_from_connector_trace_file(tmp_path):
    """确认新文件名与既有 `fi2_web_access_trace.jsonl`（连接器痕迹，语义不同）不冲突。"""
    _, c = _client(tmp_path)
    c.post("/run", data={"data_source": "mock"})
    reports = tmp_path / "reports"
    assert (reports / "fi2_http_requests.jsonl").exists()
    # 连接器 access_trace 文件只在 u9c 模式下才会被写入，mock 模式不产生
    assert not (reports / "fi2_web_access_trace.jsonl").exists()
