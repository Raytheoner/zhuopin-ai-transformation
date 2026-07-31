"""队列 #140/#182/#183 验收：FI2 最小 Web 服务 v8 核对面板（结论看板 + 展开/并拢主表）。"""
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


class TestRunMockModeV8Panel:
    """mock 演示数据全链路：v8 结论看板 + 并拢主表 + 展开详情（工程细节由 test_golden.py 覆盖，
    本处只验证 Web 层正确透传 recon_report 输出并按 v8 规格重新排布，不重复验证引擎判定逻辑本身）。"""

    def test_mock_run_produces_v8_panel_structure(self, client):
        r = client.post("/run", data={"data_source": "mock", "evaluator": "唐燕萍"})
        assert r.status_code == 200
        body = r.get_data(as_text=True)
        assert "FI2 三单匹配核对面板" in body
        assert "kpi-pass" in body and "kpi-l2" in body and "kpi-block" in body
        assert "本次共" in body and "项自动通过" in body and "项微差消化" in body and "项BLOCK退回" in body
        assert 'class="path-badge po-ap"' in body and 'class="path-badge ap-inv"' in body
        assert "四维匹配：料品名称·数量·未税金额·税额" in body
        assert "PO↔AP(单价)" in body and "AP↔发票" in body
        assert "税率合规" in body and "重复检测" in body and "OCR" in body
        assert "判定/状态" in body
        assert "BLOCK处理流程" in body
        assert "AI 建议" in body

    def test_disclaimer_183_present_with_exact_text_and_position(self, client):
        """#183：结论看板下方、主表上方，浅黄底加粗，三种判定均需写明"需财务确认后操作"。"""
        r = client.post("/run", data={"data_source": "mock"})
        body = r.get_data(as_text=True)
        disclaimer = (
            "⚠️ 本报告所有判定均为 AI 建议，不构成过账依据。"
            "自动通过/微差消化/BLOCK 退回均需财务确认后操作。"
        )
        assert disclaimer in body
        assert 'class="disclaimer-183"' in body
        kpi_pos = body.index("kpi-block")
        table_pos = body.index('class="v8"')
        disclaimer_pos = body.index(disclaimer)
        assert kpi_pos < disclaimer_pos < table_pos

    def test_mock_run_total_matches_fixture_plus_orphan(self, client):
        """data/mock 五表固定含 11 个料品 + 1 条孤立发票，v8 主表把孤立发票并入同一张表
        （规格 3.8），总行数=12，与 test_golden.py 的 11 items + 1 orphaned 口径一致。"""
        r = client.post("/run", data={"data_source": "mock"})
        body = r.get_data(as_text=True)
        assert "本次共 12 项料品" in body
        assert "2 项自动通过" in body
        assert "1 项微差消化" in body
        assert "9 项BLOCK退回" in body  # 8 needs_review + 1 orphaned invoice 并入 BLOCK（规格 3.1）

    def test_mock_run_shows_known_full_match_and_price_alert(self, client):
        """AP-1000/A001 数量金额税额与发票精确一致 → PO↔AP/AP↔发票均一致；
        AP-8000/H001 单价 10.6 vs PO 10（+6%>2%）→ PO↔AP 超差。"""
        r = client.post("/run", data={"data_source": "mock"})
        body = r.get_data(as_text=True)
        assert "AP-1000" in body and "A001" in body
        assert "AP-8000" in body
        assert "单价+6.00%（超差）" in body

    def test_mock_run_shows_orphaned_invoice_as_main_table_row(self, client):
        """invoice.csv 里 INV-9 挂载 AP-9999，AP 明细行不存在该单号 → 孤立发票并入主表一行
        （规格 3.8：不再单列一个区），判定强制 BLOCK退回。"""
        r = client.post("/run", data={"data_source": "mock"})
        body = r.get_data(as_text=True)
        assert "INV-9" in body
        assert "AP-9999" in body
        assert "（无AP）" in body
        assert "① 完全匹配" not in body  # 旧六段式区块标题不应再出现
        assert "⑥ 孤立发票" not in body

    def test_mock_run_r7_tip_attached_to_four_dim_block_only_on_diff(self, client):
        """规格 3.2/唐燕萍 07-31 口头指令（#175⑤）：⑤提示语不再单列一段，改为跟随
        "四维匹配"校验块，仅当 PO↔AP 有差异（价格超差）时才在该行详情底部带出。"""
        r = client.post("/run", data={"data_source": "mock"})
        body = r.get_data(as_text=True)
        assert "不代表一定是记账错误" in body
        assert "① 四维匹配" in body
        tip_pos = body.index("不代表一定是记账错误")
        four_dim_positions = [i for i in range(len(body)) if body.startswith("① 四维匹配", i)]
        assert any(p < tip_pos for p in four_dim_positions)
        assert "⑤ AP-PO 单价强制比对" not in body  # 旧独立第五段标题不应再出现

    def test_mock_run_new_dimensions_honestly_stubbed_not_fabricated(self, client):
        """OCR/重复检测/税率合规/PO变更检测四项引擎未实现，须如实标注"二期未接入"，
        不得伪装出 ✅/❌ 判定结果（FI2 一贯红线：结果分类如实标注，不伪装已判定）。"""
        r = client.post("/run", data={"data_source": "mock"})
        body = r.get_data(as_text=True)
        assert body.count("🔷 二期未接入") >= 3 * 12  # 税率合规/重复检测/OCR 三列 × 12 行
        assert "已评估暂不实现（队列 #80）" in body  # PO变更检测：已评估不采纳，非"未做"

    def test_mock_run_expand_collapse_scaffolding_present(self, client):
        """并拢默认收起（display:none）+ 点击行号展开：三张单据卡片 + 六个校验块。"""
        r = client.post("/run", data={"data_source": "mock"})
        body = r.get_data(as_text=True)
        assert 'id="detail-0"' in body and 'style="display:none"' in body
        assert 'onclick="toggleRow(0)"' in body
        assert body.count('class="doc-card po"') >= 11
        assert body.count('class="doc-card ap"') >= 11
        assert body.count('class="doc-card inv"') >= 11
        assert "① 四维匹配" in body
        assert "② OCR 字段校验" in body
        assert "③ 税率合规" in body
        assert "④ 重复发票检测" in body
        assert "⑤ PO 变更检测" in body
        assert "⑥ 行级映射" in body

    def test_mock_run_block_action_buttons_per_spec_3_6(self, client):
        """BLOCK退回（初始态）只给"退回原因"信息按钮，无操作功能；
        自动通过/微差消化为灰色不可操作按钮，均不应出现"确认通过"/"退回"可操作按钮
        （规格 3.6："已补充待审核"态不存在于本引擎真实计算结果中，见 webapp.py 模块 docstring）。"""
        r = client.post("/run", data={"data_source": "mock"})
        body = r.get_data(as_text=True)
        assert "📋 退回原因" in body
        assert "已通过" in body and "已消化" in body
        assert 'op-btn go' not in body and 'op-btn back' not in body


def test_csv_mode_reuses_mock_fixture_directory(client, tmp_path):
    """csv 应急桥接模式：把既有 mock 五表拷到临时目录当"人工誊录后的快照目录"，验证纯走
    Web 表单 csv_dir 字段即可跑通，不新增任何引擎逻辑（沿用既有 data_source=csv 路径），
    并按 v8 面板重新排布。"""
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "data" / "mock"
    dst = tmp_path / "real_round1_like"
    shutil.copytree(src, dst)

    r = client.post("/run", data={"data_source": "csv", "csv_dir": str(dst)})
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "本次共 12 项料品" in body
    assert "kpi-pass" in body
