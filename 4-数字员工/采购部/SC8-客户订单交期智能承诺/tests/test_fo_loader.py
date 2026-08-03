"""FO API 加载器边界校验（任务 2.1 / design D3）。

FO 真实需求入口必须强 Schema 校验：脏数据/缺字段被挡、料号前缀过滤生效、
customer_id 缺省为空（API 只返回客户名）。解析与网络分离，本测试不触网。
"""
from __future__ import annotations

import pytest

from sc8.loaders import FO_LINE_STATUS_CLOSED, MVP_ITEM_PREFIXES, parse_forecast_order_rows
from sc8.models import ForecastOrder


def _row(doc="FO2026060001", code="F02N.0184", name="EQ40S", num=1000,
         ship="2026-06-15", cust="安徽某客户", line_status=None):
    # 字段名对齐 IT 正式库接口 ForecastOrderLineDTO（PascalCase）
    row = {
        "DocNo": doc, "ItemCode": code, "ItemName": name,
        "Num": num, "ShipPlanDate": ship, "CustomerName": cust,
    }
    if line_status is not None:
        row["LineStatus"] = line_status
    return row


def test_parse_valid_row_maps_to_forecast_order():
    fos = parse_forecast_order_rows([_row()])
    assert len(fos) == 1
    fo = fos[0]
    assert isinstance(fo, ForecastOrder)
    assert fo.fo_id == "FO2026060001"
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
    bad["ItemCode"] = None
    with pytest.raises(Exception):
        parse_forecast_order_rows([bad], validate=True)


def test_num_coerced_from_string():
    fos = parse_forecast_order_rows([_row(num="500.0")])
    assert fos[0].qty == 500


# ── 行级关闭过滤（队列 #173，#19 根治，IT 2026-07-30 补齐 LineStatus 字段）────────

def test_line_status_closed_excluded_when_validate():
    """LineStatus=3（关闭）在 validate=True 路径下被剔除——真实案例 FO2026070001
    行60 S02Y.0120/行230 S02Y.0166 均为此态。"""
    rows = [_row(code="S02Y.0120", line_status=3), _row(code="S02Y.0166", line_status=3),
            _row(code="S02Y.0035", line_status=2)]
    fos = parse_forecast_order_rows(rows, validate=True)
    kept = {f.item_code for f in fos}
    assert kept == {"S02Y.0035"}


def test_line_status_closed_excluded_when_not_validate():
    """LineStatus=3 在 validate=False（快速路径）下同样被剔除。"""
    rows = [_row(code="S02Y.0120", line_status=3), _row(code="S02Y.0035", line_status=2)]
    fos = parse_forecast_order_rows(rows, validate=False)
    assert {f.item_code for f in fos} == {"S02Y.0035"}


def test_line_status_missing_defaults_to_kept():
    """LineStatus 缺失（旧样本/mock 未提供该字段）视为核准，向后兼容不误伤。"""
    fos = parse_forecast_order_rows([_row(code="F02N.0001")], validate=True)
    assert len(fos) == 1
    fos2 = parse_forecast_order_rows([_row(code="F02N.0001")], validate=False)
    assert len(fos2) == 1


def test_fo_line_status_closed_constant_matches_it_semantics():
    """IT 陈承 2026-07-30 回件：LineStatus 2=核准，3=关闭。"""
    assert FO_LINE_STATUS_CLOSED == 3
