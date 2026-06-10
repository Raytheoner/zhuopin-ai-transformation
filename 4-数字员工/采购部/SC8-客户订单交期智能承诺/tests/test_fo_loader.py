"""FO API 加载器边界校验（任务 2.1 / design D3）。

FO 真实需求入口必须强 Schema 校验：脏数据/缺字段被挡、料号前缀过滤生效、
customer_id 缺省为空（API 只返回客户名）。解析与网络分离，本测试不触网。
"""
from __future__ import annotations

import pytest

from sc8.loaders import MVP_ITEM_PREFIXES, parse_forecast_order_rows
from sc8.models import ForecastOrder


def _row(doc="FO2026050001", code="F02N.0184", name="EQ40S", num=1000,
         ship="2026-06-15", cust="安徽某客户"):
    return {
        "DocNo": doc, "ItemInfo_ItemCode": code, "ItemInfo_ItemName": name,
        "Num": num, "ShipPlanDate": ship, "Customer_Name": cust,
    }


def test_parse_valid_row_maps_to_forecast_order():
    fos = parse_forecast_order_rows([_row()])
    assert len(fos) == 1
    fo = fos[0]
    assert isinstance(fo, ForecastOrder)
    assert fo.fo_id == "FO2026050001"
    assert fo.item_code == "F02N.0184"
    assert fo.qty == 1000
    assert fo.ship_date == "2026-06-15"
    assert fo.customer_name == "安徽某客户"
    assert fo.customer_id == ""          # FO API 不返回 customer_id → 空


def test_prefix_filter_drops_non_mvp_items():
    # R 前缀 = 原材料，应被过滤；F/S/Y/X 保留
    rows = [_row(code="F02N.0001"), _row(code="R01B.0854"),
            _row(code="S02Y.0162"), _row(code="X05A.0001"), _row(code="Y01.0009")]
    fos = parse_forecast_order_rows(rows)
    kept = {f.item_code[:1] for f in fos}
    assert kept == {"F", "S", "X", "Y"}          # R 原材料被过滤
    assert all(f.item_code[:1].upper() in MVP_ITEM_PREFIXES for f in fos)
    assert "R01B.0854" not in {f.item_code for f in fos}


def test_ship_plan_date_truncated_to_date():
    fos = parse_forecast_order_rows([_row(ship="2026-06-15T00:00:00")])
    assert fos[0].ship_date == "2026-06-15"


def test_missing_doc_no_rejected_when_validate():
    bad = _row()
    del bad["DocNo"]
    with pytest.raises(Exception):
        parse_forecast_order_rows([bad], validate=True)


def test_missing_item_code_rejected_when_validate():
    bad = _row()
    bad["ItemInfo_ItemCode"] = None
    with pytest.raises(Exception):
        parse_forecast_order_rows([bad], validate=True)


def test_num_coerced_from_string():
    fos = parse_forecast_order_rows([_row(num="500.0")])
    assert fos[0].qty == 500
