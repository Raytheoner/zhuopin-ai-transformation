"""平台共享数据模型 —— 连接器返回的标准记录类型（D1 收割自 supplychain data_loader）。

边界（Paul 拍板 D1/Q1）：
  · 进平台：连接器/数据源 API 返回的「记录 shape」——BOM/库存/采购单/生产计划/供应商，
    以及携客云 SRM 返回的需求单/交付单 shape（SrmDemandOrder/SrmDeliveryOrder）。
  · 留 SC8：业务聚合概念（SalesOrder 销售订单 / ForecastOrder 预测订单），属交付域需求，
    不在平台底座，随 SC8 收割时落位。

所有连接器（CSV/SRM/zp ERP/U9C）的 get_* 方法统一返回这些 dataclass。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BomRow:
    product_id: str
    component_id: str
    component_name: str
    level: int
    qty_per_unit: float
    loss_rate: float
    unit: str


@dataclass
class InventoryRow:
    material_id: str
    material_name: str
    current_stock: int
    safety_stock: int
    unit: str
    last_updated: str


@dataclass
class PurchaseOrder:
    po_id: str
    material_id: str
    qty_ordered: int
    qty_received: int
    expected_date: str
    supplier_confirmed_date: str
    supplier_id: str
    status: str  # placed | in_transit | partial | received


@dataclass
class ProductionPlan:
    plan_id: str
    product_id: str
    product_name: str
    planned_qty: int
    planned_date: str


@dataclass
class Supplier:
    supplier_id: str
    material_id: str
    unit_price: float
    moq: int
    mpq: int
    lead_time_days: int
    is_approved: bool


# ── 携客云 SRM 返回 shape（连接器级，进平台）─────────────────────────────────

@dataclass
class SrmDemandOrder:
    """SRM 物料需求单（ERP MRP 运算后推送至携客云 SRM 的净需求）。"""
    demand_id:      str   # SRM 需求单号，如 SRM-2026-001
    material_id:    str   # 原材料编码，如 R01B.0039
    material_name:  str   # 原材料名称
    qty_required:   int   # 需求数量
    customer_order: str   # 关联客户订单号（FO/SO），用于按客户分组
    product_id:     str   # 对应成品料号，如 F02N.0184（用于 SMT 工时查询）
    required_date:  str   # 需求到货日期 YYYY-MM-DD
    status:         str   # pending（未回复）/ quoted / ordered / delivered


@dataclass
class SrmDeliveryOrder:
    """SRM 交付订单（供应商在 SRM 确认交期后生成的承诺记录）。"""
    delivery_id:    str   # SRM 交付单号
    demand_id:      str   # 关联需求单号（与 SrmDemandOrder.demand_id 对应）
    supplier_id:    str   # 供应商编码，如 ZA.0317
    material_id:    str   # 原材料编码
    qty_committed:  int   # 供应商承诺交付数量
    committed_date: str   # 供应商承诺交期 YYYY-MM-DD
    status:         str   # confirmed / at_risk / overdue
