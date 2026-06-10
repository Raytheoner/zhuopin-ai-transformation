"""核心引擎测试：确定性逻辑 / 置信度 / 置信度⊥风险正交 / 启发式取自 config。"""
from __future__ import annotations

from datetime import date

from sc8.config import ForecastParams
from sc8.forecast import estimate_material_arrivals, forecast_for_order
from sc8.models import SalesOrder


# ── 确定性：关键路径齐料日 = 最晚到货物料 ───────────────────────────────────────
def test_critical_path_is_latest_material(bom, srm_deliveries, params):
    mat = estimate_material_arrivals("F02N.0040", bom, srm_deliveries, date(2026, 7, 10), params)
    assert mat.arrivals["R01.A"] == date(2026, 6, 20)
    assert mat.arrivals["R01.B"] == date(2026, 6, 25)
    assert mat.bottleneck_material == "R01.B"          # 最晚到货 = 关键路径
    assert mat.no_feedback_materials == []


# ── 置信度：全部子件有 SRM 承诺 = 高 ────────────────────────────────────────────
def test_high_confidence_all_feedback(bom, srm_deliveries, lead_time, params):
    mat = estimate_material_arrivals("F02N.0040", bom, srm_deliveries, date(2026, 7, 10), params)
    so = SalesOrder("SO1", "Z1", "比亚迪", "F02N.0040", 100, "2026-07-10")
    fc = forecast_for_order(so, mat, lead_time, params, outsourced=False)
    assert fc.confidence == "高"
    assert fc.smt_complete_date == date(2026, 6, 30)   # 06-25 + 5
    assert fc.forecast_date == date(2026, 7, 1)        # + 1 物流


# ── 置信度：含无反馈物料 = 低，且 +30 天启发式生效 ──────────────────────────────
def test_low_confidence_no_feedback_applies_30(bom, srm_deliveries, lead_time, params):
    mat = estimate_material_arrivals("F02N.0184", bom, srm_deliveries, date(2026, 7, 5), params)
    assert "R02.B" in mat.no_feedback_materials
    assert mat.arrivals["R02.B"] == date(2026, 8, 4)   # 07-05 + 30
    so = SalesOrder("SO2", "Z2", "理想", "F02N.0184", 50, "2026-07-05")
    fc = forecast_for_order(so, mat, lead_time, params, outsourced=False)
    assert fc.confidence == "低"
    assert fc.bottleneck_material == "R02.B"


# ── 置信度：委外 = 低，且 +10 天启发式生效 ─────────────────────────────────────
def test_low_confidence_outsourced_applies_10(bom, srm_deliveries, lead_time, params):
    mat = estimate_material_arrivals("X05A.0001", bom, srm_deliveries, date(2026, 7, 20), params)
    so = SalesOrder("SO3", "Z3", "上汽", "X05A.0001", 30, "2026-07-20")
    fc_plain = forecast_for_order(so, mat, lead_time, params, outsourced=False)
    fc_out   = forecast_for_order(so, mat, lead_time, params, outsourced=True)
    # 委外比非委外晚整 10 天
    assert (fc_out.smt_complete_date - fc_plain.smt_complete_date).days == 10
    assert fc_out.confidence == "低"
    assert fc_plain.confidence == "高"                  # 同物料非委外则高置信


# ── 正交性：有反馈但晚于目标日 = 高置信 + 红风险（不折进置信度）──────────────────
def test_confidence_orthogonal_to_risk(bom, srm_deliveries, lead_time, params):
    mat = estimate_material_arrivals("F02N.0040", bom, srm_deliveries, date(2026, 6, 1), params)
    # 客户目标日 2026-06-01，预测 07-01 → 大幅延期（红），但全部子件有反馈（高置信）
    so = SalesOrder("SO9", "Z1", "比亚迪", "F02N.0040", 100, "2026-06-01")
    fc = forecast_for_order(so, mat, lead_time, params, outsourced=False)
    assert fc.confidence == "高"        # 置信度看"预测确定性"
    assert fc.risk_level == "🔴"        # 风险看"vs 目标日"
    assert fc.delay_days > 3


# ── 启发式取自 config：改 config 即改行为 ──────────────────────────────────────
def test_heuristic_driven_by_config(bom, srm_deliveries, lead_time):
    base = ForecastParams(no_feedback_lead_days=30)
    bumped = ForecastParams(no_feedback_lead_days=45)   # 仅改参数
    mat30 = estimate_material_arrivals("F02N.0184", bom, srm_deliveries, date(2026, 7, 5), base)
    mat45 = estimate_material_arrivals("F02N.0184", bom, srm_deliveries, date(2026, 7, 5), bumped)
    assert mat30.arrivals["R02.B"] == date(2026, 8, 4)   # +30
    assert mat45.arrivals["R02.B"] == date(2026, 8, 19)  # +45（行为随 config 变）


# ── 无法排产：无工时配置 → 🔴 + 无法预测 + 低置信 ──────────────────────────────
def test_unschedulable_when_no_lead_time(bom, srm_deliveries, params):
    mat = estimate_material_arrivals("F02N.0040", bom, srm_deliveries, date(2026, 7, 10), params)
    so = SalesOrder("SO1", "Z1", "比亚迪", "F02N.0040", 100, "2026-07-10")
    fc = forecast_for_order(so, mat, {}, params, outsourced=False)   # 空工时表
    assert fc.forecast_date is None
    assert fc.risk_level == "🔴"
    assert fc.confidence == "低"
