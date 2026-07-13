"""kit_engine 新增纯函数：A1 在途到货日过滤 + A2 追料 L/T 分桶
（shortage-baoguan-criteria-v3，2026-07-10 会议定稿）。

两者均为调用层纯函数，不改 calc_shortage/explode_bom 签名或行为——
本文件只测新函数本身；calc_shortage 现有测试覆盖零回归见别处（平台/O2/SC7 全量回归）。
"""
from __future__ import annotations

from datetime import date

from zhuopin_platform.agents.kit_engine import (
    bucket_shortage_by_lead_time,
    filter_transit_by_arrival,
)
from zhuopin_platform.shared_tools.models import PurchaseOrder


def _po(po_id, material_id, expected="", confirmed="") -> PurchaseOrder:
    return PurchaseOrder(
        po_id=po_id, material_id=material_id, qty_ordered=10, qty_received=0,
        expected_date=expected, supplier_confirmed_date=confirmed,
        supplier_id="V1", status="in_transit",
    )


class TestFilterTransitByArrival:

    def test_overdue_po_excluded(self):
        """超期未到的在途单不计入可用（A1 核心场景）。"""
        pos = [_po("PO1", "M1", confirmed="2026-08-01")]
        kept = filter_transit_by_arrival(pos, cutoff_date=date(2026, 7, 20))
        assert kept == []

    def test_on_time_po_kept(self):
        """到货日 ≤ 截止日的在途单正常保留。"""
        pos = [_po("PO1", "M1", confirmed="2026-07-15")]
        kept = filter_transit_by_arrival(pos, cutoff_date=date(2026, 7, 20))
        assert [p.po_id for p in kept] == ["PO1"]

    def test_confirmed_date_preferred_over_expected(self):
        """supplier_confirmed_date 有值时优先用它（即便 expected_date 会得出不同结论）。"""
        po = _po("PO1", "M1", expected="2026-06-01", confirmed="2026-08-01")  # 预期早、确认晚
        kept = filter_transit_by_arrival([po], cutoff_date=date(2026, 7, 20))
        assert kept == [], "应按 confirmed(8/1，超期) 判定，不是 expected(6/1，未超期)"

    def test_falls_back_to_expected_date_when_confirmed_empty(self):
        """confirmed 为空（如 O2/SC7 尚未接真实 SRM 的 mock PO）→ 退回 expected_date。"""
        po = _po("PO1", "M1", expected="2026-07-15", confirmed="")
        kept = filter_transit_by_arrival([po], cutoff_date=date(2026, 7, 20))
        assert [p.po_id for p in kept] == ["PO1"]

    def test_no_date_at_all_excluded(self):
        """两个日期字段都为空 → 无法确认到货，保守剔除（不计入可用）。"""
        po = _po("PO1", "M1", expected="", confirmed="")
        kept = filter_transit_by_arrival([po], cutoff_date=date(2026, 7, 20))
        assert kept == []

    def test_not_calling_function_means_zero_impact(self):
        """不调用本函数、直接把原始列表传给 calc_shortage（O2/SC7 现有方式）——
        本测试只验证函数本身是纯增量、无副作用（不修改传入列表）。"""
        pos = [_po("PO1", "M1", confirmed="2026-08-01")]
        original = list(pos)
        filter_transit_by_arrival(pos, cutoff_date=date(2026, 7, 20))
        assert pos == original


class TestBucketShortageByLeadTime:

    def test_urgent_when_within_lead_time(self):
        """需求日-今天 < L/T → 临近，归入 urgent。"""
        shortages = {"M1": 50.0}
        demand_dates = {"M1": date(2026, 7, 15)}
        lead_times = {"M1": 10}
        urgent, observe = bucket_shortage_by_lead_time(
            shortages, demand_dates, lead_times, today=date(2026, 7, 10))
        assert urgent == {"M1": 50.0}
        assert observe == {}

    def test_observe_when_beyond_lead_time(self):
        """需求日-今天 ≥ L/T → 未临近，归入 observe，不触发追料。"""
        shortages = {"M1": 50.0}
        demand_dates = {"M1": date(2026, 8, 15)}
        lead_times = {"M1": 10}
        urgent, observe = bucket_shortage_by_lead_time(
            shortages, demand_dates, lead_times, today=date(2026, 7, 10))
        assert urgent == {}
        assert observe == {"M1": 50.0}

    def test_missing_lead_time_falls_back_to_urgent(self):
        """缺 L/T 数据 → 兜底立即追料（净需求>0 即追，交接单口径）。"""
        shortages = {"M1": 50.0}
        demand_dates = {"M1": date(2026, 8, 15)}
        urgent, observe = bucket_shortage_by_lead_time(
            shortages, demand_dates, lead_times={}, today=date(2026, 7, 10))
        assert urgent == {"M1": 50.0}
        assert observe == {}

    def test_missing_demand_date_falls_back_to_urgent(self):
        """缺需求日数据 → 同样无法判断临近与否，保守兜底进 urgent。"""
        shortages = {"M1": 50.0}
        urgent, observe = bucket_shortage_by_lead_time(
            shortages, demand_dates={}, lead_times={"M1": 10}, today=date(2026, 7, 10))
        assert urgent == {"M1": 50.0}
        assert observe == {}

    def test_multiple_materials_split_correctly(self):
        shortages = {"M1": 10.0, "M2": 20.0}
        demand_dates = {"M1": date(2026, 7, 12), "M2": date(2026, 9, 1)}
        lead_times = {"M1": 5, "M2": 5}
        urgent, observe = bucket_shortage_by_lead_time(
            shortages, demand_dates, lead_times, today=date(2026, 7, 10))
        assert urgent == {"M1": 10.0}
        assert observe == {"M2": 20.0}
