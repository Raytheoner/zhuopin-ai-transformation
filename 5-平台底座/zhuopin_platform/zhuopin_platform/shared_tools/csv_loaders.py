"""CSV 数据加载与回退（D1 收割自 supplychain data_loader）。

职责：从指定目录读取 5 类业务 CSV，返回平台 models 的 dataclass 列表。
作为连接器的 CSV 回退数据源（主数据源 SRM/ERP 不可用或离线/脱敏模式时使用）。

边界（D1/Q1）：只保留连接器需要的 5 个加载函数；销售订单/预测订单（SalesOrder/
ForecastOrder）的加载属 SC8，不在此处。
"""
from __future__ import annotations

import csv
from pathlib import Path

from .models import (
    BomRow,
    InventoryRow,
    ProductionPlan,
    PurchaseOrder,
    Supplier,
)

# 默认夹具目录：平台仓库 tests/fixtures（脱敏 CSV）。
# 生产环境由连接器显式传入真实回退目录。
_DEFAULT_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def _resolve_dir(mock_dir: Path | str | None) -> Path:
    """统一处理目录入参：None→默认夹具目录，str→Path。"""
    return Path(mock_dir) if mock_dir is not None else _DEFAULT_DIR


def load_bom(mock_dir: Path | str | None = None) -> list[BomRow]:
    base = _resolve_dir(mock_dir)
    rows = []
    with open(base / "bom.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows.append(BomRow(
                product_id=r["product_id"],
                component_id=r["component_id"],
                component_name=r["component_name"],
                level=int(r["level"]),
                qty_per_unit=float(r["qty_per_unit"]),
                loss_rate=float(r["loss_rate"]),
                unit=r["unit"],
            ))
    return rows


def load_inventory(mock_dir: Path | str | None = None) -> list[InventoryRow]:
    base = _resolve_dir(mock_dir)
    rows = []
    with open(base / "inventory.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows.append(InventoryRow(
                material_id=r["material_id"],
                material_name=r["material_name"],
                current_stock=int(r["current_stock"]),
                safety_stock=int(r["safety_stock"]),
                unit=r["unit"],
                last_updated=r["last_updated"],
            ))
    return rows


def load_purchase_orders(mock_dir: Path | str | None = None) -> list[PurchaseOrder]:
    base = _resolve_dir(mock_dir)
    rows = []
    with open(base / "purchase_orders.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows.append(PurchaseOrder(
                po_id=r["po_id"],
                material_id=r["material_id"],
                qty_ordered=int(r["qty_ordered"]),
                qty_received=int(r["qty_received"]),
                expected_date=r["expected_date"],
                supplier_confirmed_date=r["supplier_confirmed_date"],
                supplier_id=r["supplier_id"],
                status=r["status"],
            ))
    return rows


def load_production_plan(mock_dir: Path | str | None = None) -> list[ProductionPlan]:
    base = _resolve_dir(mock_dir)
    rows = []
    with open(base / "production_plan.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows.append(ProductionPlan(
                plan_id=r["plan_id"],
                product_id=r["product_id"],
                product_name=r["product_name"],
                planned_qty=int(r["planned_qty"]),
                planned_date=r["planned_date"],
            ))
    return rows


def load_suppliers(mock_dir: Path | str | None = None) -> list[Supplier]:
    base = _resolve_dir(mock_dir)
    rows = []
    with open(base / "suppliers.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows.append(Supplier(
                supplier_id=r["supplier_id"],
                material_id=r["material_id"],
                unit_price=float(r["unit_price"]),
                moq=int(r["moq"]),
                mpq=int(r["mpq"]),
                lead_time_days=int(r["lead_time_days"]),
                is_approved=r["is_approved"].strip().lower() == "true",
            ))
    return rows
