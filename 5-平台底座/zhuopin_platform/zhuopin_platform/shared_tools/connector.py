"""DataConnector 抽象接口（收割自 supplychain src/data/connector.py）。

定义采购/运营场景所需的 5 类业务数据访问契约。所有具体数据源
（CSV 回退 / 携客云 SRM / zp ERP / U9C）实现这一组方法，返回平台 models
中的标准 dataclass。上层数字员工业务逻辑只面向本接口编程，不关心数据源。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .models import (
    BomRow,
    InventoryRow,
    ProductionPlan,
    PurchaseOrder,
    Supplier,
)


class DataConnector(ABC):
    """数据访问统一接口。

    实现类负责把底层数据（CSV / ERP API / 数据库）映射成标准 dataclass 列表。
    """

    @abstractmethod
    def get_bom(self) -> list[BomRow]:
        """获取 BOM 物料清单（含子件层级）。"""

    @abstractmethod
    def get_inventory(self) -> list[InventoryRow]:
        """获取实时库存快照（含安全库存）。"""

    @abstractmethod
    def get_purchase_orders(self) -> list[PurchaseOrder]:
        """获取在途采购订单（已下达/未全部到货）。"""

    @abstractmethod
    def get_production_plan(self) -> list[ProductionPlan]:
        """获取当前生产计划。"""

    @abstractmethod
    def get_suppliers(self) -> list[Supplier]:
        """获取物料-供应商价格表。"""
