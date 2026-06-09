"""U9C 骨架连接器测试（第 7 组）。

验证：
  · 接口未就绪时 5 个 get_* 全部 CSV 回退、不阻塞上层、返回同结构。
  · 与其余连接器遵循同一 DataConnector 抽象接口。
  · 保留 7/1 MCP 真实接入点（webapi_path 占位 + skeleton 标记）。
"""
from pathlib import Path

import pytest

from zhuopin_platform.shared_tools import models
from zhuopin_platform.shared_tools.connector import DataConnector
from zhuopin_platform.shared_tools.u9c_connector import U9CConnector

FIXTURES = Path(__file__).parent / "fixtures"


def _make_conn():
    return U9CConnector(
        base_url="https://testerp.example:4445/U9C", user_code="u", password="p",
        ent_code="001", org_code="Z", client_id="cid", client_secret="sec",
        fallback_dir=FIXTURES,
    )


def test_is_dataconnector():
    assert isinstance(_make_conn(), DataConnector)


def test_all_methods_fall_back_to_csv():
    """接口未就绪 → 5 类数据均经 CSV 回退、返回正确 shape、不阻塞。"""
    conn = _make_conn()
    assert all(isinstance(x, models.BomRow) for x in conn.get_bom())
    assert all(isinstance(x, models.InventoryRow) for x in conn.get_inventory())
    assert all(isinstance(x, models.PurchaseOrder) for x in conn.get_purchase_orders())
    assert all(isinstance(x, models.ProductionPlan) for x in conn.get_production_plan())
    assert all(isinstance(x, models.Supplier) for x in conn.get_suppliers())
    assert len(conn.get_bom()) > 0


def test_skeleton_marker_and_mcp_接入点():
    """保留 7/1 MCP 真实接入点：webapi_path 占位可见、repr 标记骨架态。"""
    conn = _make_conn()
    assert conn.webapi_path  # 占位路径存在，待 IT 确认替换
    assert "skeleton" in repr(conn).lower()


def test_from_env_missing_raises(monkeypatch):
    for k in ("U9C_API_BASE", "U9C_USER_CODE", "U9C_API_PASSWORD", "U9C_ENT_CODE",
              "U9C_ORG_CODE", "U9C_CLIENT_ID", "U9C_CLIENT_SECRET"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(ValueError):
        U9CConnector.from_env()
