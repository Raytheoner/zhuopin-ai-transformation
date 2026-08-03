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
    """FO 预测订单 API（`/zp/api/ForecastOrder/Query`）行的 Pydantic 边界校验。

    缺 DocNo / ItemCode / ShipPlanDate 或类型不符 → ValidationError，脏数据不进下游。
    字段名对齐 IT 正式库接口 ForecastOrderLineDTO（PascalCase，无 `ItemInfo_` 前缀）。

    LineStatus（队列 #173，#19 根治，IT 陈承 2026-07-30 回件补齐字段）：取自
    `SM_ForecastOrderLine.Status`，2=核准／3=关闭。此前 `status` 参数只能过滤到
    单据头审核状态（恒为 2，见 `load_forecast_orders_from_api` 旧注释），本字段是
    真正的行级关闭状态；`_Opt[int]=None` 保持向后兼容（缺字段的旧样本/mock 不受影响）。
    """
    DocNo:         str
    ItemCode:      str
    ItemName:      _Opt[str] = ""
    Num:           _Opt[float] = 0
    ShipPlanDate:  str
    CustomerName:  _Opt[str] = ""
    LineStatus:    _Opt[int] = None

    @field_validator("DocNo", "ItemCode", "ShipPlanDate", mode="before")
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


# 行级关闭状态（队列 #173，#19 根治）：SM_ForecastOrderLine.Status==3 → 该行已关闭，
# 不应再作为在办需求参与保供计算。LineStatus 缺失（None，旧样本/mock 未提供该字段）
# 视为核准，保持向后兼容——不因新字段缺失而误伤既有行为。
FO_LINE_STATUS_CLOSED = 3


def parse_forecast_order_rows(rows: list[dict], *, validate: bool = True) -> list[ForecastOrder]:
    """把 FO API 返回的原始行解析为 ForecastOrder（与网络分离，便于测试）。

    - 按 MVP 料号前缀（F/S/Y/X）过滤，跳过原材料/非生产物料。
    - 按行级 LineStatus 过滤已关闭行（队列 #173，#19 根治，见 `FO_LINE_STATUS_CLOSED`）——
      此前"只取核准状态 FO"诉求因接口无行级字段无法实现（`status` 参数只能过滤到单据头，
      恒为 2），IT 2026-07-30 已补齐 `LineStatus` 字段，本函数据此剔除行级已关闭的需求行。
    - validate=True 时走 Pydantic 边界校验，脏数据/缺字段显式报错。
    - customer_id 缺省为空：FO API 仅返回 Customer_Name（隔离键见 config.customer_isolation_key）。
    """
    result: list[ForecastOrder] = []
    for raw in rows:
        if validate:
            # 先校验（缺 DocNo/ItemCode/ShipPlanDate 或类型不符 → 显式报错挡脏数据），
            # 再按校验后的料号前缀/行级状态过滤（原材料/已关闭行静默跳过）。
            row = _FoApiRow.model_validate(raw)
            code = row.ItemCode
            if code[:1].upper() not in MVP_ITEM_PREFIXES:
                continue
            if row.LineStatus == FO_LINE_STATUS_CLOSED:
                continue
            doc_no, name, num, ship = row.DocNo, row.ItemName or "", row.Num or 0, row.ShipPlanDate
        else:
            code = str(raw.get("ItemCode") or "").strip()
            if not code or code[:1].upper() not in MVP_ITEM_PREFIXES:
                continue
            if raw.get("LineStatus") == FO_LINE_STATUS_CLOSED:
                continue
            doc_no = str(raw.get("DocNo") or "").strip()
            name, num = str(raw.get("ItemName") or "").strip(), raw.get("Num") or 0
            ship = str(raw.get("ShipPlanDate") or "")
        result.append(ForecastOrder(
            fo_id=         doc_no,
            item_code=     code,
            item_name=     str(name).strip(),
            qty=           int(float(num)),
            ship_date=     str(ship)[:10],          # 取 YYYY-MM-DD 部分
            customer_id=   "",                      # FO API 不返回客户编码
            customer_name= str(raw.get("CustomerName") or "").strip(),
        ))
    return result


def load_forecast_orders_from_api(
    api_base: str | None = None, *, validate: bool = True, page_size: int = 500,
    api_key: str | None = None, date_from: str | None = None,
    date_to: str | None = None, status: str | None = None,
    org_code: str | None = None, audit=None,
) -> list[ForecastOrder]:
    """从正式库 FO 预测订单 API 加载真实预测订单（IT 2026-06-24 交付的正式库接口）。

    接口：``GET {base}/zp/api/ForecastOrder/Query?apiKey=…&dateFrom=&dateTo=&page=&pageSize=``
    鉴权：``apiKey`` 走 URL query（**非 OAuth2**，独立于 ZpConnector）。
    响应外壳：``{Success, ResCode, ResMsg, Data:{Rows:[ForecastOrderLineDTO], Total}}``。

    优先级：参数 > 环境变量（``FO_API_BASE`` / ``FORECAST_API_KEY``）。
    只读 GET；按 Total 分页拉满；行经 Pydantic 边界校验 + MVP 前缀过滤。
    **fail-loud**：缺配置/接口失败/网络异常一律抛错，绝不回退 mock（红线）。
    安全：异常信息不带含 apiKey 的 URL（避免密钥进日志/审计）。
    B4：FO 访问层补轻量审计痕迹（source=FO）；audit=None 则不留痕。
    """
    import urllib.parse

    base = (api_base or os.environ.get("FO_API_BASE", "")).rstrip("/")
    key = api_key or os.environ.get("FORECAST_API_KEY", "")
    if not base:
        raise RuntimeError("FO_API_BASE 未配置（正式库 https://erp.equalitytec.com:4443）")
    if not key:
        raise RuntimeError("FORECAST_API_KEY 未配置（IT 提供的 FO 接口密钥，写入 .env，勿入库）")

    safe_url = f"{base}/zp/api/ForecastOrder/Query"     # 脱敏 URL（不含 apiKey），仅用于报错

    def _qs(page: int) -> str:
        p = {"apiKey": key, "page": page, "pageSize": page_size}
        if date_from: p["dateFrom"] = date_from
        if date_to:   p["dateTo"] = date_to
        if status:    p["status"] = status
        if org_code:  p["orgCode"] = org_code
        return urllib.parse.urlencode(p)

    rows: list[dict] = []
    page = 1
    try:
        while True:
            with urllib.request.urlopen(f"{safe_url}?{_qs(page)}", timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8", "replace"))
            ok = payload.get("Success", payload.get("success", True))
            if not ok:
                raise RuntimeError(
                    f"FO 接口返回失败：{payload.get('ResMsg') or payload.get('resMsg') or 'unknown'}")
            data = payload.get("Data") or payload.get("data") or {}
            batch = data.get("Rows") or data.get("rows") or []
            total = int(data.get("Total") or data.get("total") or 0)
            rows.extend(batch)
            if not batch or len(rows) >= total or page > 50:    # page>50 = 25000 行兜底闸
                break
            page += 1
    except RuntimeError:
        raise                                                   # 已是脱敏业务错误，直接抛
    except Exception as e:
        raise RuntimeError(f"无法连接预测订单 API ({safe_url})：{type(e).__name__}: {e}") from None
    finally:
        if audit is not None:
            audit.trace(source="FO", action="ForecastOrder/Query")
    return parse_forecast_order_rows(rows, validate=validate)


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
