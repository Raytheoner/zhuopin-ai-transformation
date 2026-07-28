"""队列 #140 验收：FI2 最小 Web 服务（跑三单匹配 → 六段式报告页）。"""
from __future__ import annotations

import shutil

import pytest

from fi2.webapp import create_app


@pytest.fixture()
def client(tmp_path):
    app = create_app(reports_dir=tmp_path / "reports")
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
    assert "未过账" in body
    assert "不写回 ERP" in body
    assert "<form" in body


def test_run_rejects_unknown_data_source(client):
    r = client.post("/run", data={"data_source": "oracle"})
    assert r.status_code == 400
    assert "未知数据源" in r.get_data(as_text=True)


def test_run_csv_mode_requires_dir(client):
    r = client.post("/run", data={"data_source": "csv"})
    assert r.status_code == 400
    assert "csv 模式需填写数据目录路径" in r.get_data(as_text=True)


def test_run_csv_mode_missing_directory(client):
    r = client.post("/run", data={"data_source": "csv", "csv_dir": "no/such/dir"})
    assert r.status_code == 400
    assert "数据目录不存在" in r.get_data(as_text=True)


def test_run_u9c_mode_requires_selector(client):
    r = client.post("/run", data={"data_source": "u9c"})
    assert r.status_code == 400
    assert "AP 单号清单" in r.get_data(as_text=True)
    assert "供应商代码清单" in r.get_data(as_text=True)


def test_run_u9c_mode_missing_credentials_surfaces_error(client, monkeypatch):
    """u9c 凭据未配置（本机测试环境无 U9C_* env）时，如实回显而非空白 500。"""
    for k in ("U9C_API_BASE", "U9C_USER_CODE", "U9C_ENT_CODE",
              "U9C_ORG_CODE", "U9C_CLIENT_ID", "U9C_CLIENT_SECRET"):
        monkeypatch.delenv(k, raising=False)
    r = client.post("/run", data={"data_source": "u9c", "ap_doc_nos": "AP-1"})
    assert r.status_code == 500
    assert "U9C 连接构造失败" in r.get_data(as_text=True)


class TestRunMockMode:
    """mock 演示数据全链路：报告页六段式渲染 + 已知料品分布到位（工程细节由 test_golden.py 覆盖，
    本处只验证 Web 层正确透传 recon_report 输出，不重复验证引擎判定逻辑本身）。"""

    def test_mock_run_produces_six_section_report(self, client):
        r = client.post("/run", data={"data_source": "mock", "evaluator": "唐燕萍"})
        assert r.status_code == 200
        body = r.get_data(as_text=True)
        assert "① 总判定" in body
        assert "② 完全匹配 / L3 建议通过" in body
        assert "③ 需人工确认" in body
        assert "④ L2 自行消化" in body
        assert "⑤ AP-PO 单价强制比对" in body
        assert "⑥ 孤立发票" in body
        assert "AI 建议通过/预警，未过账" in body

    def test_mock_run_total_matches_fixture(self, client):
        r = client.post("/run", data={"data_source": "mock"})
        body = r.get_data(as_text=True)
        # data/mock 五表固定含 11 个料品（AP 明细行数），断言与 test_golden.py 口径一致
        assert ">11<" in body

    def test_mock_run_shows_known_full_match_and_price_alert(self, client):
        """AP-1000/A001 数量金额税额与发票精确一致 → 完全匹配；AP-8000/H001 单价 10.6 vs PO 10（+6%>2%）→ 超差。"""
        r = client.post("/run", data={"data_source": "mock"})
        body = r.get_data(as_text=True)
        assert "AP-1000" in body and "A001" in body
        assert "AP-8000" in body
        assert "单价超差" in body

    def test_mock_run_shows_orphaned_invoice(self, client):
        """invoice.csv 里 INV-9 挂载 AP-9999，AP 明细行不存在该单号 → 孤立发票。"""
        r = client.post("/run", data={"data_source": "mock"})
        body = r.get_data(as_text=True)
        assert "INV-9" in body
        assert "AP-9999" in body

    def test_mock_run_r7_note_reflects_current_config(self, client):
        r = client.post("/run", data={"data_source": "mock"})
        body = r.get_data(as_text=True)
        assert "±2.0%" in body
        assert "ZA0066" in body
        assert "不代表一定是记账错误" in body


def test_csv_mode_reuses_mock_fixture_directory(client, tmp_path):
    """csv 应急桥接模式：把既有 mock 五表拷到临时目录当"人工誊录后的快照目录"，验证纯走
    Web 表单 csv_dir 字段即可跑通，不新增任何引擎逻辑（沿用既有 data_source=csv 路径）。"""
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "data" / "mock"
    dst = tmp_path / "real_round1_like"
    shutil.copytree(src, dst)

    r = client.post("/run", data={"data_source": "csv", "csv_dir": str(dst)})
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "① 总判定" in body
    assert ">11<" in body
