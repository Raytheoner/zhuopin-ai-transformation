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
    sequence: str = ""          # BOM 项次（m_sequence）；同 product_id 下同项次的行互为替代关系候选
    is_substitute: bool = False  # True=替代料（m_componentType==2）；False=主料/常规子件


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
    # 行号（队列 #173，#139④ 根治，2026-08-03）：来自 ZpViewPurOrder.erpLineNo，
    # 与 Purchase/Query 的 DocLineNo 一一对应，供跨端点按行 JOIN 行级关闭状态
    # （LineStatus）。缺省空串保持向后兼容（旧 mock/CSV 夹具不受影响）。
    line_no: str = ""
    # ── 以下四项为 SC2 采购周报新增（2026-08-18，纯新增字段，全部带缺省值）──
    # `expected_date` 在无 deliveryDate 时会降级自 makeDate，故它**不等于制单日**；
    # 周报的「本周下单」必须按真实制单日落窗口，因此单列 make_date。
    make_date: str = ""          # 制单日期，来自 ZpViewPurOrder.makeDate
    unit_price: float = 0.0      # 含税单价，来自 ZpViewPurOrder.finallyPriceTC
    supplier_name: str = ""      # 供应商名称，来自 ZpViewPurOrder.supplyName
    buyer: str = ""              # 制单人（采购员），来自 ZpViewPurOrder.makeEmpName
    # ── 以下一项为 SC2 判例回灌新增（2026-08-22，纯新增字段，带缺省值）────────
    # 单据类型码，来自 ZpViewPurOrder.erpTypeCode（PO01/PO22/PO23 标准订单、
    # PO14/PO16/PO17 全程委外、PO03 固定资产、PO20/PO21 费用采购）。采购口径的
    # 「下单行数」不含全程委外，故调用方需要这一维度才能按其口径过滤。
    # ⚠️ 缺省空串意味着「未知类型」，**调用方不得把空串当成"非委外"直接放行**——
    # 那正是 2026-08-18 踩过的坑（旧缓存缺新字段 ⇒ 取到缺省值而报表看上去正常）。
    # 缓存侧已由 schema 版本号封住（见 connector `_PO_CACHE_SCHEMA`）。
    doc_type: str = ""


@dataclass
class ReceiptLine:
    """采购收货行（ERP `GR/Query`）。

    🔴 **它是「本周实际收货」唯一的真实来源**：`ZpViewPurOrder` 只有累计收货量
    `rcvQtyTU`、不带收货日期，无法按周归属；`GR/Query` 的 `BusinessDate` 才是
    入库过账日。（2026-08-18 SC2 建造时实测确认，见 SC2 场景 CLAUDE.md。）

    ⚠️ 该端点**不支持任何服务端日期过滤**——实测 `startDate`/`endDate`/
    `businessDate`/`beginDate` 以及一个故意拼错的参数名，五者返回的 Total 全部
    等于无过滤基线（27,785），即 F14 那类「静默返回全表」。故只能整表分页拉取
    后在客户端按 `receipt_date` 过滤，不得信任服务端过滤。
    """

    receipt_doc_no: str          # 收货单号 RcvDocNo
    line_no: str                 # 收货单行号 DocLineNo
    po_id: str                   # 来源采购单号 SrcDocNo
    po_line_no: str              # 来源采购单行号 SrcDocLineNo
    material_id: str             # ItemCode
    material_name: str           # ItemName
    qty_received: float          # RcvQtyTU
    receipt_date: str            # BusinessDate（YYYY-MM-DD）
    supplier_name: str = ""      # SupplierName
    unit_price: float = 0.0      # FinalPriceTC


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
