"""Stock API 库存实时取数测试（stock-api-inventory-source）。

验证 ZpConnector.get_inventory(material_ids) 走 /zp/api/Stock/Query：
  · 逐料号 + 按 ItemCode 精确匹配（剔模糊他料）+ 跨白名单仓聚合可用量
  · real 缺配置 fail-loud；mock 缺配置回退 CSV
  · apiKey 脱敏（异常不含明文）；Success=false → 抛错
全程 mock/monkeypatch，不触真实端点。
"""
import urllib.error
from pathlib import Path

import pytest

from zhuopin_platform.shared_tools import models
from zhuopin_platform.shared_tools.erp_connector import ZpConnector
from zhuopin_platform.shared_tools.erp_connector import connector as erp_mod
from zhuopin_platform.shared_tools.connector_errors import RealEndpointNotReadyError

FIXTURES = Path(__file__).parent / "fixtures"


def _make_conn(tmp_path, data_source="mock"):
    return ZpConnector(
        base_url="https://testerp.example:4445", user_code="u", ent_code="001",
        org_code="Z", client_id="cid", client_secret="sec",
        fallback_dir=FIXTURES, po_cache_file=tmp_path / "po_cache.json",
        data_source=data_source,
    )


def _row(code, wh, store, avail=None):
    return erp_mod._StockRow(ItemCode=code, ItemName="x", WhName=wh,
                             StoreQty=store, AvailQty=store if avail is None else avail)


def test_exact_match_and_cross_warehouse_aggregate(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_API_BASE", "http://192.168.100.49:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path, data_source="real")
    # 返回：目标料号跨 3 个白名单仓 + 1 个模糊他料（应被剔除）
    canned = [
        _row("R01A.0012", "物料仓", 2827195),
        _row("R01A.0012", "委外仓", 246583),
        _row("R01A.0012", "委外仓", 79407),
        _row("R01A.00120", "物料仓", 999999),   # 模糊命中他料 → 剔除
    ]
    monkeypatch.setattr(conn, "_stock_query", lambda *a, **k: canned)
    inv = conn.get_inventory(["R01A.0012"])
    assert len(inv) == 1
    assert isinstance(inv[0], models.InventoryRow)
    assert inv[0].material_id == "R01A.0012"
    assert inv[0].current_stock == 2827195 + 246583 + 79407   # 只聚合精确料号
    assert inv[0].safety_stock == 0


def test_available_qty_used_over_store_qty(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path, data_source="real")
    canned = [_row("M1", "物料仓", store=1000, avail=600)]  # 有预留：可用<现存
    monkeypatch.setattr(conn, "_stock_query", lambda *a, **k: canned)
    inv = conn.get_inventory(["M1"])
    assert inv[0].current_stock == 600   # 取可用量 AvailQty，非现存 StoreQty


def test_no_stock_row_skipped(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path, data_source="real")
    monkeypatch.setattr(conn, "_stock_query", lambda *a, **k: [])  # 无库存行
    assert conn.get_inventory(["GHOST"]) == []


def test_real_failloud_without_config(tmp_path, monkeypatch):
    monkeypatch.delenv("STOCK_API_BASE", raising=False)
    monkeypatch.delenv("STOCK_API_KEY", raising=False)
    conn = _make_conn(tmp_path, data_source="real")
    with pytest.raises(RealEndpointNotReadyError):
        conn.get_inventory(["M1"])   # real 不静默回退、不以 0 冒充


def test_mock_falls_back_to_csv(tmp_path, monkeypatch):
    monkeypatch.delenv("STOCK_API_BASE", raising=False)
    monkeypatch.delenv("STOCK_API_KEY", raising=False)
    conn = _make_conn(tmp_path, data_source="mock")
    inv = conn.get_inventory(["M001"])   # mock 无 STOCK 配置 → CSV 夹具
    assert all(isinstance(x, models.InventoryRow) for x in inv)
    assert len(inv) > 0


def test_legacy_no_args_still_item_master(tmp_path, monkeypatch):
    conn = _make_conn(tmp_path)
    monkeypatch.setattr(conn, "_zp_post",
                        lambda *a, **k: [{"itemCode": "R01B.0039", "itemName": "电容"}])
    inv = conn.get_inventory()   # 旧接口（无 material_ids）→ 物料清单，current_stock=0
    assert inv[0].material_id == "R01B.0039" and inv[0].current_stock == 0


def test_stock_query_apikey_scrubbed_on_error(tmp_path, monkeypatch):
    conn = _make_conn(tmp_path, data_source="real")
    SECRET = "SUPERSECRETKEY123"

    def _boom(*a, **k):
        raise urllib.error.HTTPError("http://h/zp/api/Stock/Query", 500, "err", {}, None)
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", _boom)
    with pytest.raises(RuntimeError) as ei:
        conn._stock_query("http://h:6666", SECRET, "M1", "ZP01")
    assert SECRET not in str(ei.value)   # apiKey 不进异常信息


def test_stock_query_success_false_raises(tmp_path, monkeypatch):
    conn = _make_conn(tmp_path, data_source="real")

    class _Resp:
        status = 200
        def read(self): return b'{"Success":false,"ResMsg":"Missing or invalid api-key","Data":null}'
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", lambda *a, **k: _Resp())
    with pytest.raises(RuntimeError) as ei:
        conn._stock_query("http://h:6666", "K", "M1", "ZP01")
    assert "Stock API 错误" in str(ei.value)
