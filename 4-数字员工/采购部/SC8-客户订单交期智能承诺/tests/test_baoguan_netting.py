"""SC8 保供现货净额（SC8_NET_INVENTORY）测试（stock-api-inventory-source 任务 4）。

验证：
  · 开关 OFF（默认）→ inventory 被忽略、四色零漂移
  · 开关 ON → 现货可用量≥毛需求的直接子件退出待催/催货（消除 P0 误判）
  · 全覆盖 → 🟢 现货齐备；现货不足 → 仍待催
"""
from __future__ import annotations

from datetime import date

from zhuopin_platform.shared_tools.models import BomRow, SrmDeliveryOrder

from sc8.baoguan import RISK_GAP, RISK_GREEN, assess_supply_risk
from sc8.models import SalesOrder

TODAY = date(2026, 8, 1)


def _so(qty=1000, ship="2026-09-01"):
    return SalesOrder(so_id="FO-1", customer_id="", customer_name="某OEM",
                      item_code="P1", qty=qty, required_date=ship,
                      doc_type="预测订单", item_name="ECU")


def _bom(*components):
    return [BomRow(product_id="P1", component_id=c, component_name=c,
                   level=1, qty_per_unit=1.0, loss_rate=0.0, unit="PCS")
            for c in components]


def _srm(material, committed):
    return SrmDeliveryOrder(delivery_id=f"SRM-{material}", demand_id="", supplier_id="",
                            material_id=material, qty_committed=0,
                            committed_date=committed, status="confirmed")


# A 有按期承诺、B 无答复 → 基线 🟠 待催（B 驱动）
def _scenario():
    return _so(), _bom("A", "B"), [_srm("A", "2026-08-15")]


def test_netting_off_is_zero_drift(monkeypatch):
    monkeypatch.delenv("SC8_NET_INVENTORY", raising=False)   # 默认 OFF
    so, bom, srm = _scenario()
    base = assess_supply_risk(so, bom, srm, today=TODAY)
    # 即便传了能覆盖 B 的现货，OFF 时必须被忽略、结果与不传完全一致
    withinv = assess_supply_risk(so, bom, srm, today=TODAY, inventory={"B": 100000})
    assert base.risk == RISK_GAP == withinv.risk
    assert base.no_feedback_materials == withinv.no_feedback_materials == ["B"]


def test_netting_on_covered_component_exits_gap(monkeypatch):
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so, bom, srm = _scenario()
    # B 现货可用量 1000 ≥ 毛需求 1000 → B 退出待催；只剩 A（按期）→ 🟢
    r = assess_supply_risk(so, bom, srm, today=TODAY, inventory={"B": 1000})
    assert "B" not in r.no_feedback_materials
    assert r.risk == RISK_GREEN


def test_netting_on_all_covered_is_green_ready(monkeypatch):
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so, bom, srm = _scenario()
    r = assess_supply_risk(so, bom, srm, today=TODAY, inventory={"A": 1000, "B": 1000})
    assert r.risk == RISK_GREEN
    assert r.component_count == 0
    assert "现货齐备" in r.action


def test_netting_on_insufficient_stock_not_covered(monkeypatch):
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so, bom, srm = _scenario()
    # B 现货 500 < 毛需求 1000 → 不覆盖，仍 🟠 待催
    r = assess_supply_risk(so, bom, srm, today=TODAY, inventory={"B": 500})
    assert r.risk == RISK_GAP
    assert "B" in r.no_feedback_materials
