"""黄金基准回归 — 确定性逻辑零偏差（门禁文档 §2.3 / spec「确定性逻辑零偏差」）。

期望值来自 data/golden/golden_expected.md 人工核对。任一确定性字段（齐料日、SMT 完工、
预测交付、延期天数、瓶颈物料）与人工计算不一致 → 测试红，阻断上线。
"""
from __future__ import annotations

from datetime import date

from sc8.pipeline import compute_forecasts

# 人工核对基准（golden_expected.md），逐项零偏差比对
GOLDEN = {
    "F02N.0040": dict(
        smt_complete=date(2026, 6, 30), forecast=date(2026, 7, 1),
        delay=-9, risk="🟢", confidence="高", bottleneck_material="R01.B",
    ),
    "F02N.0184": dict(
        smt_complete=date(2026, 8, 11), forecast=date(2026, 8, 12),
        delay=38, risk="🔴", confidence="低", bottleneck_material="R02.B",
    ),
    "X05A.0001": dict(
        smt_complete=date(2026, 7, 13), forecast=date(2026, 7, 14),
        delay=-6, risk="🟢", confidence="低", bottleneck_material="R03.A",
    ),
}


def test_golden_zero_deviation(sales_orders, bom, srm_deliveries, lead_time, params, outsource_ids):
    forecasts = compute_forecasts(
        sales_orders, bom, srm_deliveries, lead_time, params,
        outsource_ids=outsource_ids,
    )
    by_product = {f.product_id: f for f in forecasts}

    for product_id, exp in GOLDEN.items():
        fc = by_product[product_id]
        assert fc.smt_complete_date == exp["smt_complete"], f"{product_id} SMT 完工偏差"
        assert fc.forecast_date == exp["forecast"], f"{product_id} 预测交付偏差"
        assert fc.delay_days == exp["delay"], f"{product_id} 延期天数偏差"
        assert fc.risk_level == exp["risk"], f"{product_id} 三色风险偏差"
        assert fc.confidence == exp["confidence"], f"{product_id} 置信度标注错误"
        assert fc.bottleneck_material == exp["bottleneck_material"], f"{product_id} 瓶颈物料错误"
        assert fc.param_version == "sc8-params-v0"
