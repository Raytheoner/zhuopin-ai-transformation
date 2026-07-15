"""C-1 主料/替代料等价合并判缺料（sc8-baoguan-substitute-partial-kit，2026-07-15）。

口径（保供看板v2-口径定稿.md §2 C-1）：同项次(sequence)下主料+替代料视为一个"料位"，
毛需求只算一份归主料（不重复计替代料需求）；可用现货 = 主料现货 + 组内全部替代料
现货合计，组合计现货 ≥ 该组毛需求 → 判齐，否则计入缺口。等价合并，无优先级顺序。

替代料合并判齐依赖现货数据，与既有 `SC8_NET_INVENTORY` 开关同一入口（design.md D4）：
开关 OFF 时 inventory 被忽略，替代料现货合计判齐不生效（与本变更包实施前行为一致）；
毛需求去重（不因替代料重复计）与 `substitute_groups` 字段则不受开关影响，恒定生效。
"""
from __future__ import annotations

from datetime import date

from zhuopin_platform.shared_tools.models import BomRow

from sc8.baoguan import RISK_GAP, RISK_GREEN, _gross_need, assess_supply_risk
from sc8.models import SalesOrder

TODAY = date(2026, 8, 1)


def _so(qty=1000, ship="2026-09-01", item="P1"):
    return SalesOrder(so_id="FO-1", customer_id="", customer_name="某OEM",
                      item_code=item, qty=qty, required_date=ship,
                      doc_type="预测订单", item_name="ECU")


def _row(component, *, sequence="", is_substitute=False, qty=1.0, product="P1"):
    return BomRow(product_id=product, component_id=component, component_name=component,
                 level=1, qty_per_unit=qty, loss_rate=0.0, unit="PCS",
                 sequence=sequence, is_substitute=is_substitute)


def test_gross_need_not_doubled_by_substitute_row():
    """毛需求只按主料展开一份，替代料行不产生额外的独立毛需求条目。"""
    so = _so(qty=1000)
    bom = [_row("A", sequence="10", is_substitute=False, qty=1.0),
          _row("B", sequence="10", is_substitute=True, qty=1.0)]
    need = _gross_need(so, bom)
    assert need == {"A": 1000.0}, "替代料 B 不应作为独立叶子件出现在毛需求里"


def test_no_substitute_zero_drift():
    """无替代料的普通 BOM：行为与本变更包实施前完全一致（含无 inventory 场景）。"""
    so = _so(qty=1000)
    bom = [_row("A", sequence="10"), _row("C", sequence="20")]
    r = assess_supply_risk(so, bom, srm_deliveries=[], today=TODAY)
    assert r.substitute_groups == {}
    assert set(r.no_feedback_materials) == {"A", "C"}


def test_substitute_stock_covers_shortage_when_netting_on(monkeypatch):
    """净额开关 ON：主料现货不足，但组内替代料现货合计 ≥ 毛需求 → 该料位判齐，退出待催。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(qty=1000)
    bom = [_row("A", sequence="10", is_substitute=False),
          _row("B", sequence="10", is_substitute=True),
          _row("C", sequence="20")]  # C 无替代料，作为对照仍待催
    # A 现货 400 + B(替代) 现货 700 = 1100 ≥ 毛需求 1000 → 料位判齐
    r = assess_supply_risk(so, bom, srm_deliveries=[], today=TODAY,
                          inventory={"A": 400, "B": 700})
    assert "A" not in r.no_feedback_materials
    assert "B" not in r.no_feedback_materials  # 替代料本身不应单独出现在待催清单
    assert "C" in r.no_feedback_materials       # 无替代料、无现货覆盖，仍待催


def test_combined_stock_still_insufficient_stays_shortage(monkeypatch):
    """净额开关 ON：主料+替代料合计现货仍 < 毛需求 → 不判齐，仍计入缺口/待催。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(qty=1000)
    bom = [_row("A", sequence="10", is_substitute=False),
          _row("B", sequence="10", is_substitute=True)]
    # A 300 + B 200 = 500 < 1000
    r = assess_supply_risk(so, bom, srm_deliveries=[], today=TODAY,
                          inventory={"A": 300, "B": 200})
    assert "A" in r.no_feedback_materials
    assert r.risk == RISK_GAP


def test_netting_off_substitute_stock_ignored(monkeypatch):
    """净额开关 OFF（默认）：即便传了能覆盖的现货，替代料合并判齐不生效（与开关既有语义一致）。"""
    monkeypatch.delenv("SC8_NET_INVENTORY", raising=False)
    so = _so(qty=1000)
    bom = [_row("A", sequence="10", is_substitute=False),
          _row("B", sequence="10", is_substitute=True)]
    r = assess_supply_risk(so, bom, srm_deliveries=[], today=TODAY,
                          inventory={"A": 1000, "B": 1000})
    assert "A" in r.no_feedback_materials, "开关 OFF 时 inventory 恒被忽略"


def test_substitute_groups_field_populated_regardless_of_netting_switch(monkeypatch):
    """substitute_groups 字段（显示用）不受净额开关影响，只要 BOM 有替代料关系就应产出。"""
    monkeypatch.delenv("SC8_NET_INVENTORY", raising=False)   # 开关 OFF
    so = _so(qty=1000)
    bom = [_row("A", sequence="10", is_substitute=False),
          _row("B", sequence="10", is_substitute=True)]
    r = assess_supply_risk(so, bom, srm_deliveries=[], today=TODAY)
    assert r.substitute_groups == {"A": ["B"]}


def test_multiple_substitutes_all_combined(monkeypatch):
    """一个料位多条替代料：现货合计含全部替代料。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(qty=1000)
    bom = [_row("A", sequence="10", is_substitute=False),
          _row("B", sequence="10", is_substitute=True),
          _row("D", sequence="10", is_substitute=True)]
    # 300 + 300 + 400 = 1000 == 毛需求
    r = assess_supply_risk(so, bom, srm_deliveries=[], today=TODAY,
                          inventory={"A": 300, "B": 300, "D": 400})
    assert "A" not in r.no_feedback_materials
    assert r.substitute_groups == {"A": ["B", "D"]}


def test_equivalent_merge_no_priority_order(monkeypatch):
    """等价合并：主料现货为 0、全靠替代料覆盖也应判齐（无"优先主料"限制）。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(qty=1000)
    bom = [_row("A", sequence="10", is_substitute=False),
          _row("B", sequence="10", is_substitute=True)]
    r = assess_supply_risk(so, bom, srm_deliveries=[], today=TODAY,
                          inventory={"A": 0, "B": 1000})
    assert "A" not in r.no_feedback_materials
