"""
数据获取层 — DataProvider 抽象接口 + SRMProvider + ManualProvider。

设计决策 D5：抽象接口预留 ERP 适配层，ERP 接通后新增 ERPProvider 无需改动上层代码。
SRMProvider 复用携客云 SRM Connector（XkySrmConnector）计算历史交付准时率。
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import sys
from pathlib import Path


@dataclass
class DeliveryData:
    """交付数据：准时率（0-100）或 None（不可用）"""
    rate: Optional[float]
    source: str  # "SRM自动" | "人工录入" | "人工覆盖" | "数据不足"


class DataProvider(ABC):
    """供应商数据获取抽象接口。"""

    @abstractmethod
    def get_delivery_rate(self, supplier_name: str, supplier_code: str = "") -> DeliveryData:
        """获取供应商历史交付准时率。"""
        ...


class SRMProvider(DataProvider):
    """从携客云 SRM 计算供应商历史交付准时率。

    计算方式：从供应计划看板拉取近 60 天数据，统计 delivered 订单占总订单的比例。
    若 SRM 无该供应商数据或 API 异常，raise RuntimeError 由调用层决定是否回退。
    """

    def __init__(self, connector=None):
        self._connector = connector  # 注入 XkySrmConnector，为 None 时延迟构造

    def _get_connector(self):
        if self._connector is None:
            # 动态导入，避免未配置 SRM 时启动失败
            srm_path = Path(__file__).parent.parent.parent.parent.parent / \
                       "supplychain" / "src" / "data"
            if str(srm_path) not in sys.path:
                sys.path.insert(0, str(srm_path.parent.parent))
            try:
                from src.data.xky_srm_connector import XkySrmConnector
                self._connector = XkySrmConnector.from_env()
            except Exception as e:
                raise RuntimeError(f"SRM 连接器初始化失败: {e}")
        return self._connector

    def get_delivery_rate(self, supplier_name: str, supplier_code: str = "") -> DeliveryData:
        """查询 SRM 近 60 天交付看板，计算准时率。"""
        try:
            connector = self._get_connector()
            orders = connector.get_delivery_orders()
        except Exception as e:
            raise RuntimeError(f"SRM API 调用失败: {e}")

        # 按供应商过滤（innerVendorCode 或模糊匹配名称）
        vendor_orders = [
            o for o in orders
            if (supplier_code and o.supplier_id == supplier_code)
            or (not supplier_code and supplier_name.lower() in str(o.supplier_id).lower())
        ]

        if not vendor_orders:
            raise RuntimeError(f"SRM 中未找到供应商 '{supplier_name}' 的交付记录")

        total = len(vendor_orders)
        delivered = sum(1 for o in vendor_orders if o.status == "delivered")
        rate = round(delivered / total * 100, 1) if total > 0 else None
        return DeliveryData(rate=rate, source="SRM自动")


class ManualProvider(DataProvider):
    """持有 CLI 录入的数据，实现 DataProvider 接口。"""

    def __init__(self, delivery_rate: Optional[float], source: str = "人工录入"):
        self._rate = delivery_rate
        self._source = source if delivery_rate is not None else "数据不足"

    def get_delivery_rate(self, supplier_name: str = "", supplier_code: str = "") -> DeliveryData:
        return DeliveryData(rate=self._rate, source=self._source)


def get_delivery_data(
    supplier_name: str,
    supplier_code: str = "",
    override_rate: Optional[float] = None,
    override_source: str = "人工覆盖",
) -> DeliveryData:
    """
    智能获取交付数据：优先 SRM，失败时回退人工录入。
    override_rate 不为 None 时直接返回（人工覆盖场景）。
    """
    if override_rate is not None:
        return DeliveryData(rate=override_rate, source=override_source)

    try:
        srm = SRMProvider()
        return srm.get_delivery_rate(supplier_name, supplier_code)
    except RuntimeError:
        return DeliveryData(rate=None, source="数据不足")
