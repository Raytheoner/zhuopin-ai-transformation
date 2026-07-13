"""B4 PMC 优先级占用框架桩（shortage-baoguan-criteria-v3，2026-07-10 会议定稿）。

同一物料被多个成品行同时竞争时，谁先占用现货由 PMC 月度优先级决定——本次
只搭接口形状（`priority_resolver` 挂钩点），不实现真实排序/占用逻辑（无 PMC
数据源）。本测试锁定"桩"的诚实边界：即便传入一个 resolver，当前行为也不变
（因为真正调用它的排序/扣减逻辑本次未实现），避免日后误以为 B4 已生效。
"""
from __future__ import annotations

from datetime import date

from zhuopin_platform.shared_tools.models import BomRow

from sc8 import config
from sc8.baoguan import build_dashboard
from sc8.models import SalesOrder

TODAY = date(2026, 6, 22)


def _so(so_id, item="S02Y.0035", ship="2026-09-01", qty=1000):
    return SalesOrder(so_id=so_id, customer_id="", customer_name="客户A",
                      item_code=item, qty=qty, required_date=ship,
                      doc_type="预测订单", item_name="ECU")


def _bom(product, *components):
    return [BomRow(product_id=product, component_id=c, component_name=c,
                   level=1, qty_per_unit=1.0, loss_rate=0.0, unit="PCS")
            for c in components]


def test_build_dashboard_accepts_priority_resolver_param():
    """build_dashboard 接受 priority_resolver 关键字参数（接口已就绪）。"""
    orders = [_so("FO1")]
    bom = _bom("S02Y.0035", "R01")
    rows = build_dashboard(orders, bom, [], today=TODAY,
                           priority_resolver=lambda material_id, so_ids: so_ids)
    assert len(rows) == 1  # 不因传入 resolver 而报错/改变行数


def test_priority_resolver_has_no_effect_yet(monkeypatch):
    """传入非 None 的 priority_resolver，四色/缺口结果与不传时完全一致（桩未接线，诚实边界）。"""
    monkeypatch.delenv("SC8_NET_INVENTORY", raising=False)
    orders = [_so("FO1", qty=1000)]
    bom = _bom("S02Y.0035", "R01")

    without = build_dashboard(orders, bom, [], today=TODAY)
    with_resolver = build_dashboard(
        orders, bom, [], today=TODAY,
        priority_resolver=lambda material_id, so_ids: list(reversed(so_ids)),
    )
    assert [r.risk for r in without] == [r.risk for r in with_resolver]
    assert [r.gap_days for r in without] == [r.gap_days for r in with_resolver]
