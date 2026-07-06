"""SC7 采购建议引擎单测（迁自 SC5 test_purchase_engine.py，2026-07-06 v2.3 重排）。

TestCalcPurchaseQty    — MOQ/MPQ 约束（对照 supplychain 黄金值）
TestSelectSupplier     — 最低价已认证供应商选择
TestCalcOrderDate      — 最迟下单日计算
TestBusinessRulePolicy — R1/R2 审核规则
TestGoldenBaseline     — 端到端 5 条建议/金额汇总
TestUnapprovedSupplier — 无认证供应商场景
"""
from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import pytest

from sc7_inventory.business_rules import BusinessRulePolicy
from sc7_inventory.purchase_engine import (
    build_recommendations,
    calc_cost_summary,
    calc_material_earliest_dates,
    calc_order_date,
    calc_purchase_qty,
    select_supplier,
)
from zhuopin_platform.agents.kit_engine import calc_shortage, explode_bom
from zhuopin_platform.shared_tools import csv_loaders
from zhuopin_platform.shared_tools.models import Supplier

MOCK_DATA = Path(__file__).parent / "mock_data"


# ── helpers ──────────────────────────────────────────────────────────────────

def _supplier(supplier_id, material_id, unit_price, moq, mpq, lead_time, approved=True):
    return Supplier(
        supplier_id=supplier_id,
        material_id=material_id,
        unit_price=unit_price,
        moq=moq,
        mpq=mpq,
        lead_time_days=lead_time,
        is_approved=approved,
    )


# ── 1. calc_purchase_qty ──────────────────────────────────────────────────────

class TestCalcPurchaseQty:
    def test_m002_moq_dominates(self):
        # ceil(8660/5000)×5000=10000，MOQ=10000 → 10000
        assert calc_purchase_qty(shortage=8660, mpq=5000, moq=10000) == 10000

    def test_m003_mpq_ceil(self):
        # ceil(720/100)×100=800，MOQ=500 → 800
        assert calc_purchase_qty(shortage=720, mpq=100, moq=500) == 800

    def test_m006_mpq_ceil(self):
        # ceil(605/100)×100=700，MOQ=200 → 700
        assert calc_purchase_qty(shortage=605, mpq=100, moq=200) == 700

    def test_m010_mpq_ceil(self):
        # ceil(523/50)×50=550，MOQ=50 → 550
        assert calc_purchase_qty(shortage=523, mpq=50, moq=50) == 550

    def test_m015_mpq_ceil_moq_check(self):
        # ceil(754.5/50)×50 = ceil(15.09)×50 = 800，MOQ=100 → 800
        assert calc_purchase_qty(shortage=754.5, mpq=50, moq=100) == 800

    def test_moq_dominates_when_shortage_tiny(self):
        assert calc_purchase_qty(shortage=1, mpq=10, moq=100) == 100

    def test_exact_multiple_no_rounding(self):
        assert calc_purchase_qty(shortage=500, mpq=100, moq=100) == 500


# ── 2. select_supplier ────────────────────────────────────────────────────────

class TestSelectSupplier:
    def setup_method(self):
        self.suppliers = csv_loaders.load_suppliers(MOCK_DATA)

    def test_m002_cheapest_approved_is_s001(self):
        s = select_supplier("M002", self.suppliers)
        assert s.supplier_id == "S001"
        assert s.unit_price == pytest.approx(0.05)

    def test_m015_single_supplier(self):
        s = select_supplier("M015", self.suppliers)
        assert s.supplier_id == "S015"
        assert s.unit_price == pytest.approx(800.0)

    def test_no_approved_supplier_returns_none(self):
        unapproved = [_supplier("S999", "M999", 10.0, 50, 10, 14, approved=False)]
        assert select_supplier("M999", unapproved) is None

    def test_unknown_material_returns_none(self):
        assert select_supplier("M_UNKNOWN", self.suppliers) is None


# ── 3. calc_order_date ────────────────────────────────────────────────────────

class TestCalcOrderDate:
    def test_m002_order_date(self):
        # P001 最早日 2026-05-10，lead=14，安全期 3 → 2026-04-23
        result = calc_order_date(planned_date=date(2026, 5, 10), lead_time_days=14)
        assert result == date(2026, 4, 23)

    def test_m015_order_date(self):
        # P002 最早日 2026-05-15，lead=60，安全期 3 → 2026-03-13
        result = calc_order_date(planned_date=date(2026, 5, 15), lead_time_days=60)
        assert result == date(2026, 3, 13)

    def test_safety_days_applied(self):
        result = calc_order_date(planned_date=date(2026, 6, 1), lead_time_days=0)
        assert result == date(2026, 5, 29)  # 0 + 3 天安全期


# ── 4. BusinessRulePolicy ─────────────────────────────────────────────────────

class TestBusinessRulePolicy:
    def setup_method(self):
        self.policy = BusinessRulePolicy()

    def test_r1_amount_threshold_triggers(self):
        d = self.policy.evaluate(qty=800, unit_price=800.0, supplier_id="S015")
        assert d.status == "待人工审核"
        assert "R1_amount_threshold" in d.triggered_rules

    def test_r2_unapproved_supplier_triggers(self):
        d = self.policy.evaluate(qty=100, unit_price=1.0, supplier_id=None)
        assert d.status == "待人工审核"
        assert "R2_unapproved_supplier" in d.triggered_rules

    def test_both_rules_can_trigger_simultaneously(self):
        # 金额 ≥ 50 万且无认证供应商 → 两条规则同时触发
        d = self.policy.evaluate(qty=1000, unit_price=600.0, supplier_id=None)
        assert "R1_amount_threshold" in d.triggered_rules
        assert "R2_unapproved_supplier" in d.triggered_rules

    def test_auto_when_under_threshold_and_approved(self):
        d = self.policy.evaluate(qty=1000, unit_price=10.0, supplier_id="S001")
        assert d.status == "可自动下单"
        assert d.triggered_rules == []

    def test_amount_just_below_threshold_is_auto(self):
        d = self.policy.evaluate(qty=1, unit_price=499_999.0, supplier_id="S001")
        assert d.status == "可自动下单"

    def test_amount_at_exact_threshold_triggers_r1(self):
        d = self.policy.evaluate(qty=1, unit_price=500_000.0, supplier_id="S001")
        assert d.status == "待人工审核"
        assert "R1_amount_threshold" in d.triggered_rules


# ── 5. Golden Baseline (端到端 pipeline) ─────────────────────────────────────

class TestGoldenBaseline:
    def setup_method(self):
        bom = csv_loaders.load_bom(MOCK_DATA)
        plans = csv_loaders.load_production_plan(MOCK_DATA)
        inv = csv_loaders.load_inventory(MOCK_DATA)
        pos = csv_loaders.load_purchase_orders(MOCK_DATA)
        suppliers = csv_loaders.load_suppliers(MOCK_DATA)

        gross = explode_bom(bom, plans)
        self.shortages, _missing = calc_shortage(gross, inv, pos)
        self.material_dates = calc_material_earliest_dates(bom, plans, self.shortages)
        self.recs = build_recommendations(self.shortages, suppliers, self.material_dates)
        self.summary = calc_cost_summary(self.recs)

    def test_five_recommendations(self):
        assert len(self.recs) == 5

    def test_auto_total(self):
        # M002(500) + M003(9600) + M006(17500) + M010(8250) = 35850
        # B6：黄金值为整数和，精确相等（去掉 rel=0.01 容差，对齐"零偏差"口径）
        assert self.summary["auto_total"] == 35850

    def test_review_total(self):
        # M015: 800 × 800 = 640000
        assert self.summary["review_total"] == 640000

    def test_grand_total(self):
        assert self.summary["grand_total"] == 675850

    def test_m015_in_review_bucket(self):
        m015 = next(r for r in self.recs if r["material_id"] == "M015")
        assert m015["review_status"] == "待人工审核"
        assert m015["supplier_id"] == "S015"
        assert m015["purchase_qty"] == 800

    def test_m002_selects_cheapest_s001(self):
        m002 = next(r for r in self.recs if r["material_id"] == "M002")
        assert m002["supplier_id"] == "S001"
        assert m002["purchase_qty"] == 10000
        assert m002["review_status"] == "可自动下单"

    def test_m015_latest_order_date(self):
        m015 = next(r for r in self.recs if r["material_id"] == "M015")
        assert m015["latest_order_date"] == date(2026, 3, 13)

    def test_m002_latest_order_date(self):
        m002 = next(r for r in self.recs if r["material_id"] == "M002")
        assert m002["latest_order_date"] == date(2026, 4, 23)


# ── 6. 无认证供应商场景 ────────────────────────────────────────────────────────

class TestUnapprovedSupplierScenario:
    def setup_method(self):
        self.shortages = {"M999": 100.0}
        self.suppliers = [
            _supplier("S999A", "M999", 10.0, 50, 10, 14, approved=False),
            _supplier("S999B", "M999", 8.0, 50, 10, 14, approved=False),
        ]
        self.material_dates = {"M999": date(2026, 6, 1)}
        self.recs = build_recommendations(
            self.shortages, self.suppliers, self.material_dates
        )

    def test_material_appears_in_recommendations(self):
        assert len(self.recs) == 1
        assert self.recs[0]["material_id"] == "M999"

    def test_marked_for_review(self):
        assert self.recs[0]["review_status"] == "待人工审核"

    def test_r2_rule_triggered(self):
        assert "R2_unapproved_supplier" in self.recs[0]["triggered_rules"]

    def test_no_supplier_assigned(self):
        r = self.recs[0]
        assert r["supplier_id"] is None
        assert r["purchase_qty"] == 0
        assert r["estimated_cost"] == 0
        assert r["latest_order_date"] is None

    def test_review_reason_contains_chinese(self):
        assert "无认证供应商" in self.recs[0]["review_reason"]
