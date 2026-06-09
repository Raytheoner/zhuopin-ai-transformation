"""CSVConnector：基于脱敏/回退 CSV 的 DataConnector 实现（收割自 supplychain）。

用途：
  · 平台默认/离线数据源；
  · 主数据源（SRM/zp ERP/U9C）不可用或处于 mock/脱敏模式时的回退源。
内部复用 csv_loaders 的 load_* 函数，通过 mock_dir 支持自定义目录（便于测试与环境隔离）。
"""
from __future__ import annotations

from pathlib import Path

from .connector import DataConnector
from .connector_audit import ConnectorAudit
from .models import (
    BomRow,
    InventoryRow,
    ProductionPlan,
    PurchaseOrder,
    Supplier,
)
from .csv_loaders import (
    load_bom,
    load_inventory,
    load_production_plan,
    load_purchase_orders,
    load_suppliers,
)


class CSVConnector(DataConnector):
    """从指定目录读取 5 类 CSV 的 DataConnector 实现。

    Args:
        mock_dir: CSV 文件所在目录。默认 None → 使用 csv_loaders 内置默认目录
                  （平台 tests/fixtures 脱敏 CSV）。可传 str 或 Path。
        audit:    ConnectorAudit 轻量痕迹记录器（None 则不留痕）。
                  作回退连接器时由主连接器传入，保证**回退路径也留痕**（High5）。
    """

    def __init__(self, mock_dir: Path | str | None = None,
                 audit: ConnectorAudit | None = None):
        self._mock_dir = mock_dir
        self._audit = audit

    def _trace(self, action: str) -> None:
        if self._audit is not None:
            self._audit.trace(source="CSV", action=action)

    def get_bom(self) -> list[BomRow]:
        self._trace("get_bom")
        return load_bom(self._mock_dir)

    def get_inventory(self) -> list[InventoryRow]:
        self._trace("get_inventory")
        return load_inventory(self._mock_dir)

    def get_purchase_orders(self) -> list[PurchaseOrder]:
        self._trace("get_purchase_orders")
        return load_purchase_orders(self._mock_dir)

    def get_production_plan(self) -> list[ProductionPlan]:
        self._trace("get_production_plan")
        return load_production_plan(self._mock_dir)

    def get_suppliers(self) -> list[Supplier]:
        self._trace("get_suppliers")
        return load_suppliers(self._mock_dir)
