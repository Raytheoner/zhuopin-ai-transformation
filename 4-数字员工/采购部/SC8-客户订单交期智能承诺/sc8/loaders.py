"""订单加载（收割 SO/FO 加载的 SC8 部分）。

本批只接 **mock CSV 夹具**（spec「先 mock 后真实」，无真实网络调用）；
真实 ERP 导出 / FO API 切换留任务 N.1（6/12 后）。
"""
from __future__ import annotations

import csv
from pathlib import Path

from .models import ForecastOrder, SalesOrder


def load_sales_orders_csv(path: Path | str) -> list[SalesOrder]:
    """从 mock CSV 加载销售订单。

    列：so_id,customer_id,customer_name,item_code,qty,required_date[,doc_type,item_name]
    """
    rows: list[SalesOrder] = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows.append(SalesOrder(
                so_id=r["so_id"].strip(),
                customer_id=r["customer_id"].strip(),
                customer_name=r["customer_name"].strip(),
                item_code=r["item_code"].strip(),
                qty=int(r["qty"]),
                required_date=r["required_date"].strip(),
                doc_type=r.get("doc_type", "").strip(),
                item_name=r.get("item_name", "").strip(),
            ))
    return rows


def fo_to_sales_orders(fos: list[ForecastOrder]) -> list[SalesOrder]:
    """预测订单 → 销售订单（计划承诺日 ship_date 作 required_date）。"""
    return [
        SalesOrder(
            so_id=fo.fo_id,
            customer_id=fo.customer_id,
            customer_name=fo.customer_name,
            item_code=fo.item_code,
            qty=fo.qty,
            required_date=fo.ship_date,
            doc_type="预测订单",
            item_name=fo.item_name,
        )
        for fo in fos
    ]
