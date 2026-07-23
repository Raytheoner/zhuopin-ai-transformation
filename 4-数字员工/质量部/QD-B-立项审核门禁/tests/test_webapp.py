"""任务 9.1 验收：QD-B 最小 Web 服务（上传 xlsx → 报告页）。"""
from __future__ import annotations

from io import BytesIO

import pytest

from qd_b_gate.webapp import create_app


@pytest.fixture()
def client(tmp_path):
    app = create_app(upload_dir=tmp_path / "uploads", audit_path=tmp_path / "audit.jsonl")
    app.config["TESTING"] = True
    return app.test_client()


def test_ping(client):
    r = client.get("/api/ping")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_index_shows_disclaimer_and_trial_badge(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "试用版" in body
    assert "评审委员会" in body
    assert "<form" in body


def test_evaluate_rejects_missing_file(client):
    r = client.post("/evaluate", data={}, content_type="multipart/form-data")
    assert r.status_code == 400
    assert "请选择" in r.get_data(as_text=True)


def test_evaluate_rejects_non_xlsx(client):
    data = {"proposal": (BytesIO(b"not an excel file"), "proposal.txt")}
    r = client.post("/evaluate", data=data, content_type="multipart/form-data")
    assert r.status_code == 400
    assert "仅支持 .xlsx" in r.get_data(as_text=True)


def test_evaluate_surfaces_exception_instead_of_blank_500(client):
    """损坏的 xlsx（非真实 Excel 格式）应如实回显错误，而非空白 500。"""
    data = {"proposal": (BytesIO(b"garbage-not-a-real-xlsx"), "broken.xlsx")}
    r = client.post("/evaluate", data=data, content_type="multipart/form-data")
    assert r.status_code == 500
    assert "评估失败" in r.get_data(as_text=True)


class TestEvaluateWithHuafeng:
    """真实黄金样本端到端：上传→报告页，判定与黄金基准一致（不需要 mock）。"""

    def test_huafeng_upload_produces_expected_verdict(self, client, huafeng_path):
        with open(huafeng_path, "rb") as fh:
            data = {"proposal": (fh, "华丰天然气发动机EPA认证服务咨询项目立项申请书.xlsx")}
            r = client.post("/evaluate", data=data, content_type="multipart/form-data")
        assert r.status_code == 200
        body = r.get_data(as_text=True)
        assert "不合格" in body  # 华丰黄金基准真值 = 不合格
        assert "AI 预审建议" in body
        assert "跨模块校验尚未实现" in body  # ④段如实标注未实现（report.py::CROSS_MODULE_NOTE），不空着不说明
        assert "转人工待办项" in body
