"""QD-B 轻量访问日志接入测试（队列 #112）。

只验证 create_app() 接线正确——落盘/中间件逻辑由平台
`zhuopin_platform/tests/test_access_log.py` 覆盖，此处不重复。
"""
from __future__ import annotations

import json

from qd_b_gate.webapp import create_app


def _client(tmp_path, **kw):
    app = create_app(upload_dir=tmp_path / "uploads", audit_path=tmp_path / "audit.jsonl", **kw)
    app.config["TESTING"] = True
    return app, app.test_client()


def test_no_access_log_file_when_path_not_given(tmp_path):
    _, c = _client(tmp_path)
    c.get("/")
    assert not (tmp_path / "access.jsonl").exists()


def test_access_log_records_index_hit(tmp_path):
    log_path = tmp_path / "access.jsonl"
    _, c = _client(tmp_path, access_log_path=log_path)
    c.get("/")
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["path"] == "/" and rec["service"] == "QD-B 立项审核门禁"


def test_access_log_exempts_api_ping(tmp_path):
    log_path = tmp_path / "access.jsonl"
    _, c = _client(tmp_path, access_log_path=log_path)
    c.get("/api/ping")
    assert not log_path.exists()
