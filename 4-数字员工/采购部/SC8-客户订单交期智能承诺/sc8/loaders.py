"""订单加载（收割 SO/FO 加载的 SC8 部分）。

mock 路径：CSV 夹具（`load_sales_orders_csv`）。
真实路径（任务 2.1，收割自 supplychain data_loader）：`load_forecast_orders_from_api`
命中 FO 预测订单 API（ZpViewSO），对响应做 **Pydantic 边界校验**（缺 DocNo/ItemCode/
ShipPlanDate 或类型不符 → 显式报错挡脏数据），按 MVP 料号前缀（F/S/Y/X）过滤。
"""
from __future__ import annotations

import csv
import json
import os
import urllib.request
from pathlib import Path
from typing import Optional as _Opt

from pydantic import BaseModel, field_validator

from .models import ForecastOrder, SalesOrder

# MVP 生产物料前缀：F 成品 / S 半成品 / Y / X（委外）；R 等原材料过滤掉（收割自 supplychain）
MVP_ITEM_PREFIXES: tuple[str, ...] = ("F", "S", "Y", "X")


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


class _FoApiRow(BaseModel):
    """FO 预测订单 API（ZpViewSO）行的 Pydantic 边界校验。

    缺 DocNo / ItemCode / ShipPlanDate 或类型不符 → ValidationError，脏数据不进下游。
    """
    DocNo:               str
    ItemInfo_ItemCode:   str
    ItemInfo_ItemName:   _Opt[str] = ""
    Num:                 _Opt[float] = 0
    ShipPlanDate:        str
    Customer_Name:       _Opt[str] = ""

    @field_validator("DocNo", "ItemInfo_ItemCode", "ShipPlanDate", mode="before")
    @classmethod
    def _require_nonempty(cls, v, info):
        if v is None or str(v).strip() == "":
            raise ValueError(f"{info.field_name} 不能为 None 或空")
        return str(v).strip()

    @field_validator("Num", mode="before")
    @classmethod
    def _coerce_num(cls, v):
        try:
            return float(v or 0)
        except (ValueError, TypeError):
            return 0.0


def parse_forecast_order_rows(rows: list[dict], *, validate: bool = True) -> list[ForecastOrder]:
    """把 FO API 返回的原始行解析为 ForecastOrder（与网络分离，便于测试）。

    - 按 MVP 料号前缀（F/S/Y/X）过滤，跳过原材料/非生产物料。
    - validate=True 时走 Pydantic 边界校验，脏数据/缺字段显式报错。
    - customer_id 缺省为空：FO API 仅返回 Customer_Name（隔离键见 config.customer_isolation_key）。
    """
    result: list[ForecastOrder] = []
    for raw in rows:
        if validate:
            # 先校验（缺 DocNo/ItemCode/ShipPlanDate 或类型不符 → 显式报错挡脏数据），
            # 再按校验后的料号前缀过滤（原材料等非 MVP 料号静默跳过）。
            row = _FoApiRow.model_validate(raw)
            code = row.ItemInfo_ItemCode
            if code[:1].upper() not in MVP_ITEM_PREFIXES:
                continue
            doc_no, name, num, ship = row.DocNo, row.ItemInfo_ItemName or "", row.Num or 0, row.ShipPlanDate
        else:
            code = str(raw.get("ItemInfo_ItemCode") or "").strip()
            if not code or code[:1].upper() not in MVP_ITEM_PREFIXES:
                continue
            doc_no = str(raw.get("DocNo") or "").strip()
            name, num = str(raw.get("ItemInfo_ItemName") or "").strip(), raw.get("Num") or 0
            ship = str(raw.get("ShipPlanDate") or "")
        result.append(ForecastOrder(
            fo_id=         doc_no,
            item_code=     code,
            item_name=     str(name).strip(),
            qty=           int(float(num)),
            ship_date=     str(ship)[:10],          # 取 YYYY-MM-DD 部分
            customer_id=   "",                      # FO API 不返回客户编码
            customer_name= str(raw.get("Customer_Name") or "").strip(),
        ))
    return result


def load_forecast_orders_from_api(
    api_base: str | None = None, *, validate: bool = True, page_size: int = 2000,
    audit=None,
) -> list[ForecastOrder]:
    """从 FO 预测订单 API（ZpViewSO）加载真实预测订单（任务 2.1，收割自 supplychain）。

    api_base 优先级：参数 > 环境变量 FO_API_BASE > 内网默认 http://localhost:8800。
    只读 GET；响应行经 Pydantic 边界校验 + MVP 前缀过滤。
    B4（审计报告 §3.2）：FO 访问层补轻量审计痕迹（source=FO）；audit=None 则不留痕。
    """
    base = (api_base or os.environ.get("FO_API_BASE", "http://localhost:8800")).rstrip("/")
    url = f"{base}/api/forecast-orders?page_size={page_size}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        raise RuntimeError(f"无法连接预测订单 API ({url})：{e}") from e
    finally:
        if audit is not None:
            audit.trace(source="FO", action="forecast-orders")
    return parse_forecast_order_rows(data.get("rows", []), validate=validate)


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
