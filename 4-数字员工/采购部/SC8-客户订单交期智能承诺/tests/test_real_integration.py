"""真实数据集成测试（任务 4.1，FO+BOM 真实）。

默认跳过：仅当显式置 SC8_RUN_REAL=1 且凭据就位时运行（凭据从 supplychain/.env 注入）。
CI / 普通 pytest 不触网；本地小样本真实验证时手动开启。
SRM 本期降级 mock，不在此测真实 SRM（阻塞于携客云 OpenAPI 开通）。
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("SC8_RUN_REAL") != "1",
    reason="真实集成测试：置 SC8_RUN_REAL=1 且凭据就位才运行",
)


def test_real_fo_orders_schema():
    """FO API 拉真实订单，字段映射到 SalesOrder 正确。"""
    from sc8.sources import load_real_orders
    orders = load_real_orders(limit=2)
    assert orders, "应拉到真实预测订单"
    for so in orders:
        assert so.so_id and so.item_code and so.required_date
        assert so.item_code[:1].upper() in ("F", "S", "Y", "X")
        assert so.customer_name           # 客户名非空（隔离键）


def test_real_bom_schema():
    """真实 FO 料号查 U9C BOM，BomRow 字段正确。"""
    from sc8.sources import load_real_bom, load_real_orders
    orders = load_real_orders(limit=1)
    assert orders
    bom = load_real_bom([orders[0].item_code])
    assert bom, "应拉到真实 BOM 直接子件"
    for r in bom:
        assert r.product_id and r.component_id
        assert r.level == 1
