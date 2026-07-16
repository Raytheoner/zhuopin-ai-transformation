"""真实数据集成测试（任务 4.1，FO+BOM 真实；2026-07-15 补充 SRM 真实）。

默认跳过：仅当显式置 SC8_RUN_REAL=1 且凭据就位时运行（凭据从根 `.env` 注入）。
CI / 普通 pytest 不触网；本地小样本真实验证时手动开启。
SRM：2026-07-15 起携客云 OpenAPI 900401 阻塞已解除，`get_receive_board`/
`get_confirmed_dates` 均真实实测可用，本文件新增 `test_real_srm_schema` 覆盖；
`SC8_SRM_SOURCE` 默认已改 real（唯一消费方 `sc8/run.py` 里 FO/BOM 本就无条件
真实，SRM 继续默认 mock 只会制造不一致）；仍可显式置 `mock` 临时脱敏验证。
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


def test_real_srm_schema():
    """真实 FO+BOM 料号查携客云 SRM 承诺交期（2026-07-15：900401 阻塞已解除）。

    SRM 承诺记录随真实业务情况变化（不保证每次都非空），本测试只断言调用
    本身成功（不抛错、不再被 900401 挡）且返回结构正确；非空时逐条校验字段。
    """
    from sc8.sources import load_real_bom, load_real_orders, load_srm_deliveries
    orders = load_real_orders(limit=1)
    assert orders
    bom = load_real_bom([orders[0].item_code])
    materials = {r.component_id for r in bom}
    deliveries = load_srm_deliveries("real", materials=materials)
    for d in deliveries:
        assert d.material_id in materials
        assert d.committed_date
        assert d.status in ("confirmed", "planned")
