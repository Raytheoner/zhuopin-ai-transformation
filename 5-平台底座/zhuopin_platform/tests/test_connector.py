"""DataConnector 抽象 + CSVConnector 测试（第 3 组）。

验证：
  1. DataConnector 是抽象基类，未实现 5 个方法不可实例化。
  2. CSVConnector 实现统一接口，从脱敏夹具读出 5 类数据。
  3. 不同数据源遵循同一抽象接口（上层无需按数据源分支）。
"""
from pathlib import Path

import pytest

from zhuopin_platform.shared_tools.connector import DataConnector
from zhuopin_platform.shared_tools.csv_connector import CSVConnector
from zhuopin_platform.shared_tools import models

FIXTURES = Path(__file__).parent / "fixtures"


def test_dataconnector_is_abstract():
    """抽象基类不可直接实例化。"""
    with pytest.raises(TypeError):
        DataConnector()  # type: ignore[abstract]


def test_csv_connector_implements_interface():
    """CSVConnector 是 DataConnector 的具体实现。"""
    conn = CSVConnector(FIXTURES)
    assert isinstance(conn, DataConnector)


def test_csv_connector_reads_all_five():
    conn = CSVConnector(FIXTURES)
    assert all(isinstance(x, models.BomRow) for x in conn.get_bom())
    assert all(isinstance(x, models.InventoryRow) for x in conn.get_inventory())
    assert all(isinstance(x, models.PurchaseOrder) for x in conn.get_purchase_orders())
    assert all(isinstance(x, models.ProductionPlan) for x in conn.get_production_plan())
    assert all(isinstance(x, models.Supplier) for x in conn.get_suppliers())
    assert len(conn.get_bom()) > 0


def test_uniform_interface_contract():
    """任一连接器都暴露同一组 get_* 方法 —— 上层面向接口编程。"""
    conn = CSVConnector(FIXTURES)
    for method in ("get_bom", "get_inventory", "get_purchase_orders",
                   "get_production_plan", "get_suppliers"):
        assert callable(getattr(conn, method))
