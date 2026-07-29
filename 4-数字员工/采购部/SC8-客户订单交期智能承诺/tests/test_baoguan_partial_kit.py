"""C-2 部分齐套显示（sc8-baoguan-substitute-partial-kit，2026-07-15）。

口径（保供看板v2-口径定稿.md §2 C-2）：可齐套套数 = min(全部直接子件(
floor(子件可用现货 ÷ 单机用量) ))，全部直接子件参与、无例外。与净额开关同一入口
（design.md D4）：SC8_NET_INVENTORY=off 或无现货数据时恒为 None，不影响既有四色判定。
"""
from __future__ import annotations

from datetime import date

from zhuopin_platform.shared_tools.models import BomRow

from sc8.baoguan import RISK_RED, assess_supply_risk
from sc8.models import SalesOrder

TODAY = date(2026, 8, 1)


def _so(qty=1000, ship="2026-09-01"):
    return SalesOrder(so_id="FO-1", customer_id="", customer_name="某OEM",
                      item_code="P1", qty=qty, required_date=ship,
                      doc_type="预测订单", item_name="ECU")


def _row(component, *, qty_per_unit=1.0, sequence="", is_substitute=False):
    return BomRow(product_id="P1", component_id=component, component_name=component,
                 level=1, qty_per_unit=qty_per_unit, loss_rate=0.0, unit="PCS",
                 sequence=sequence, is_substitute=is_substitute)


def test_no_inventory_kittable_is_none(monkeypatch):
    """无现货数据（inventory=None）：可齐套字段恒为 None，不以 0 冒充。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(qty=1000)
    bom = [_row("A", qty_per_unit=1.0)]
    r = assess_supply_risk(so, bom, srm_deliveries=[], today=TODAY)
    assert r.kittable_qty is None
    assert r.kittable_bottleneck is None
    assert r.kittable_shortfall is None


def test_netting_off_kittable_is_none(monkeypatch):
    """净额开关 OFF：即便传了 inventory，可齐套字段仍恒为 None（与开关耦合）。"""
    monkeypatch.delenv("SC8_NET_INVENTORY", raising=False)
    so = _so(qty=1000)
    bom = [_row("A", qty_per_unit=1.0)]
    r = assess_supply_risk(so, bom, srm_deliveries=[], today=TODAY,
                          inventory={"A": 500})
    assert r.kittable_qty is None


def test_kittable_qty_from_single_bottleneck(monkeypatch):
    """单一子件决定可齐套套数：floor(现货/单机用量)。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(qty=1000)
    bom = [_row("A", qty_per_unit=2.0), _row("B", qty_per_unit=1.0)]
    # A: floor(700/2)=350；B: floor(900/1)=900 → 瓶颈是 A，可齐套 350
    r = assess_supply_risk(so, bom, srm_deliveries=[], today=TODAY,
                          inventory={"A": 700, "B": 900})
    assert r.kittable_qty == 350
    assert r.kittable_bottleneck == "A"


def test_kittable_shortfall_is_gap_to_full_order_qty(monkeypatch):
    """还差 N 件 = 凑够客户下单总量（so.qty）所需缺口（姚祖怡 2026-07-16 确认口径，
    保供看板v2-口径定稿.md §2 C-2·②+§5 裁决 5，推翻 design.md 原推荐的"凑下一整套"）。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(qty=1000)
    bom = [_row("A", qty_per_unit=2.0)]
    # floor(701/2)=350；凑够总单量 1000 套需要 2000，还差 2000-701=1299
    r = assess_supply_risk(so, bom, srm_deliveries=[], today=TODAY,
                          inventory={"A": 701})
    assert r.kittable_qty == 350
    assert r.kittable_bottleneck == "A"
    assert r.kittable_shortfall == 1299


def test_kittable_shortfall_zero_when_bottleneck_covers_full_order(monkeypatch):
    """边界：瓶颈子件现货已够撑满整张订单（kittable_qty >= so.qty）→ shortfall=0，不出现负数。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(qty=100)
    bom = [_row("A", qty_per_unit=1.0)]
    # floor(150/1)=150 >= so.qty=100 → 已够撑满整单，还差 0
    r = assess_supply_risk(so, bom, srm_deliveries=[], today=TODAY,
                          inventory={"A": 150})
    assert r.kittable_qty == 150
    assert r.kittable_shortfall == 0


def test_all_direct_components_participate_no_exception():
    pass  # 见下方 test_zero_stock_component_forces_zero_kittable，覆盖"无例外"口径


def test_zero_stock_component_forces_zero_kittable(monkeypatch):
    """无例外：任一直接子件现货为 0，也参与 min 计算，把可齐套拉到 0。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(qty=1000)
    bom = [_row("A", qty_per_unit=1.0), _row("B", qty_per_unit=1.0)]
    r = assess_supply_risk(so, bom, srm_deliveries=[], today=TODAY,
                          inventory={"A": 500, "B": 0})
    assert r.kittable_qty == 0
    assert r.kittable_bottleneck == "B"


def test_kittable_does_not_change_four_color_risk(monkeypatch):
    """部分齐套不改变既有四色判定：仍存在缺口时风险等级维持现状（不因能齐部分改判 🟢）。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(qty=1000)
    bom = [_row("A", qty_per_unit=1.0)]
    # A 无现货净额覆盖（现货远小于毛需求，A 无答复→按90天保守估算🔴），但可齐套 100 套
    r = assess_supply_risk(so, bom, srm_deliveries=[], today=TODAY,
                          inventory={"A": 100})
    assert r.kittable_qty == 100
    assert r.risk == RISK_RED, "存在缺口时不应因部分可齐改判为按期"
    assert "可先齐" in r.action


def test_substitute_stock_combined_for_kittable(monkeypatch):
    """含替代料的料位：可齐套计算也用主料+替代料合计现货（与 C-1 一致口径）。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(qty=1000)
    bom = [_row("A", qty_per_unit=1.0, sequence="10", is_substitute=False),
          _row("B", qty_per_unit=1.0, sequence="10", is_substitute=True),
          _row("C", qty_per_unit=1.0)]
    # A+B 合计 900 → floor(900/1)=900；C 单独 950 → floor=950；瓶颈是 A/B 组=900
    r = assess_supply_risk(so, bom, srm_deliveries=[], today=TODAY,
                          inventory={"A": 400, "B": 500, "C": 950})
    assert r.kittable_qty == 900
