"""数据模型层测试（D1：models.py + csv_loaders.py）。

验证：
  1. 平台 models.py 只含「连接器返回 shape」类型，不含 SC8 业务聚合（SalesOrder/ForecastOrder）。
  2. csv_loaders.py 能从脱敏夹具读出 5 类数据，类型正确。
全程使用 tests/fixtures/ 脱敏 CSV，不触真实数据源。
"""
from pathlib import Path

import pytest

from zhuopin_platform.shared_tools import models
from zhuopin_platform.shared_tools import csv_loaders

FIXTURES = Path(__file__).parent / "fixtures"


# ── 1. models.py：边界 —— 连接器返回 shape 进平台，业务聚合留 SC8 ──────────────

def test_connector_shape_types_present():
    """连接器输出的记录类型应在平台 models 中。"""
    for name in ("BomRow", "InventoryRow", "PurchaseOrder", "ProductionPlan",
                 "Supplier", "SrmDemandOrder", "SrmDeliveryOrder"):
        assert hasattr(models, name), f"平台 models 缺少连接器返回 shape：{name}"


def test_business_aggregate_types_absent():
    """SalesOrder / ForecastOrder 是 SC8 业务概念，不应进平台底座。"""
    for name in ("SalesOrder", "ForecastOrder"):
        assert not hasattr(models, name), f"业务聚合 {name} 不应进平台 models（应留 SC8）"


# ── 2. csv_loaders.py：从脱敏夹具读 5 类数据 ──────────────────────────────────

def test_load_bom_from_fixtures():
    rows = csv_loaders.load_bom(FIXTURES)
    assert len(rows) > 0
    r = rows[0]
    assert isinstance(r, models.BomRow)
    assert isinstance(r.level, int)
    assert isinstance(r.qty_per_unit, float)


def test_load_inventory_from_fixtures():
    rows = csv_loaders.load_inventory(FIXTURES)
    assert len(rows) > 0
    assert isinstance(rows[0], models.InventoryRow)
    assert isinstance(rows[0].current_stock, int)


def test_load_purchase_orders_from_fixtures():
    rows = csv_loaders.load_purchase_orders(FIXTURES)
    assert len(rows) > 0
    assert isinstance(rows[0], models.PurchaseOrder)


def test_load_production_plan_from_fixtures():
    rows = csv_loaders.load_production_plan(FIXTURES)
    assert len(rows) > 0
    assert isinstance(rows[0], models.ProductionPlan)


def test_load_suppliers_from_fixtures():
    rows = csv_loaders.load_suppliers(FIXTURES)
    assert len(rows) > 0
    s = rows[0]
    assert isinstance(s, models.Supplier)
    assert isinstance(s.is_approved, bool)


def test_loaders_only_cover_connector_shapes():
    """csv_loaders 只暴露连接器需要的 5 个加载函数，不含业务聚合加载（FO/SO）。"""
    for fn in ("load_bom", "load_inventory", "load_purchase_orders",
               "load_production_plan", "load_suppliers"):
        assert hasattr(csv_loaders, fn)
    for fn in ("load_sales_orders", "load_forecast_orders_from_excel",
               "load_forecast_orders_from_api"):
        assert not hasattr(csv_loaders, fn), f"{fn} 属 SC8，不应进平台 csv_loaders"
