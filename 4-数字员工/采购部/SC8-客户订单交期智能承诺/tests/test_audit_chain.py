"""全链审计可追溯（spec「全链审计」/ 门禁文档 §1.4）。

原预测（含置信度/参数版本/瓶颈物料/so_id）→ 更正（关联原记录）→ 客户确认，
三链均写平台 audit，可由 so_id 串起；原预测记录不删（append-only）。
"""
from __future__ import annotations

from datetime import date

from sc8.commitment import build_notifier, record_correction, submit_commitment
from sc8.models import DeliveryForecast
from sc8.pipeline import compute_forecasts


def _fc(customer="理想", so_id="SO2026060002"):
    return DeliveryForecast(
        so_id=so_id, product_id="F02N.0184", customer_id="Z2", customer_name=customer,
        target_date=date(2026, 7, 5), smt_complete_date=date(2026, 8, 11),
        logistics_days=1, forecast_date=date(2026, 8, 12), delay_days=38, risk_level="🔴",
        bottleneck="延期", confidence="低", confidence_reason="含无反馈物料",
        bottleneck_material="R02.B", param_version="sc8-params-v0",
    )


def test_forecast_audit_carries_full_decision(sales_orders, bom, srm_deliveries, lead_time, params, outsource_ids, audit):
    compute_forecasts(sales_orders, bom, srm_deliveries, lead_time, params,
                      audit=audit, outsource_ids=outsource_ids)
    recs = audit.query_by(scenario="SC8", action="delivery_forecast")
    assert len(recs) == 3
    one = next(r for r in recs if r["decision"]["product_id"] == "F02N.0184")
    d = one["decision"]
    # 预测审计须含：置信度 / 参数版本 / 瓶颈物料 / so_id
    assert d["confidence"] == "低"
    assert d["param_version"] == "sc8-params-v0"
    assert d["bottleneck_material"] == "R02.B"
    assert d["so_id"] == "SO2026060002"


def test_correction_links_original_and_keeps_append_only(audit, queue):
    notifier = build_notifier(queue, audit=audit, send_fn=lambda url, body: None)
    fc = _fc()

    # 1) 原预测外发（首次拦截 → 放行）
    submit_commitment(fc, notifier, audit)
    item_id = queue.list_pending()[0]["id"]
    queue.approve(item_id, confirmed_by="Paul", notifier=notifier)

    # 2) 发现算错 → 更正事件，关联原 so_id
    record_correction(audit, original_so_id=fc.so_id, fc=fc,
                      reason="供应商交期变更", trigger_signal="SRM 承诺交期更新",
                      evaluator="张采购")

    corrections = audit.query_by(scenario="SC8", action="delivery_forecast_correction")
    assert len(corrections) == 1
    assert corrections[0]["decision"]["original_so_id"] == fc.so_id
    assert corrections[0]["decision"]["reason"] == "供应商交期变更"
    assert corrections[0]["evaluator"] == "张采购"

    # 3) 全链可由 so_id 串起：确认外发 + 更正 均在审计中，原记录保留
    sends = [r for r in audit.query_by(scenario="SC8", action="notification_send")
             if r["decision"].get("sent") is True]
    assert len(sends) == 1
    assert sends[0]["decision"]["confirmed_by"] == "Paul"
    # append-only：更正未删除任何既有记录
    all_recs = audit.query_by(scenario="SC8")
    assert len(all_recs) >= 3   # 拦截 blocked + 放行 send + 更正 correction
