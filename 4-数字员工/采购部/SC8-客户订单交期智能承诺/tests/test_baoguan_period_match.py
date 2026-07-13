"""baoguan.py 接入周期累计供需匹配（B2，shortage-baoguan-criteria-v3，2026-07-10 会议定稿）。

纯增量：`material_commitments` 缺省 None 时，`BaoguanRow.period_match` 恒为空
字典，不影响现有 kit_date/gap_days/risk/action 字段（零漂移）。传入时逐子件
附加周期累计匹配信息，供保供看板未来展示"哪天能齐、齐多少"。
"""
from __future__ import annotations

from datetime import date

from zhuopin_platform.shared_tools.models import BomRow

from sc8.baoguan import assess_supply_risk
from sc8.models import SalesOrder

TODAY = date(2026, 6, 22)


def _so(item="S02Y.0035", ship="2026-07-20", qty=100):
    return SalesOrder(so_id=f"FO-{item}", customer_id="", customer_name="客户A",
                      item_code=item, qty=qty, required_date=ship,
                      doc_type="预测订单", item_name="ECU")


def _bom(product, *components):
    return [BomRow(product_id=product, component_id=c, component_name=c,
                   level=1, qty_per_unit=1.0, loss_rate=0.0, unit="PCS")
            for c in components]


def test_no_material_commitments_means_empty_period_match():
    """不传 material_commitments（默认）→ period_match 恒为空，不影响现有字段。"""
    so = _so()
    bom = _bom("S02Y.0035", "R01")
    row = assess_supply_risk(so, bom, [], today=TODAY)
    assert row.period_match == {}


def test_period_match_attached_per_component_when_provided():
    """传入 material_commitments → 逐直接子件附加周期累计匹配结果。"""
    so = _so(qty=100)
    bom = _bom("S02Y.0035", "R01")
    commitments = {"R01": [(date(2026, 6, 25), 40.0), (date(2026, 7, 5), 60.0)]}
    row = assess_supply_risk(so, bom, [], today=TODAY, material_commitments=commitments)
    assert "R01" in row.period_match
    pm = row.period_match["R01"]
    assert pm.demand_qty == 100.0
    assert pm.satisfied is True


def test_period_match_reflects_insufficient_supply():
    so = _so(qty=100)
    bom = _bom("S02Y.0035", "R01")
    commitments = {"R01": [(date(2026, 6, 25), 20.0)]}  # 远不够 100
    row = assess_supply_risk(so, bom, [], today=TODAY, material_commitments=commitments)
    pm = row.period_match["R01"]
    assert pm.satisfied is False
    assert pm.available_at_demand_date == 20.0
