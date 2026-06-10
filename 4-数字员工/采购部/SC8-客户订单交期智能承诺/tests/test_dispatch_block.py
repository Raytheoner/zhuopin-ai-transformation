"""对客路由真阻塞（任务 3.2/3.3/3.4，红线 §7.4 / design D5）。

铁律（切真实后比 mock 严）：
  · real 模式对客外发路径**直接禁用**——一律入待审批队列，绝不自动外发客户；
  · 门禁 fail-closed：低置信/延期/首次承诺 → requires_confirmation；
  · 审计记录置信度分类（高/低）+ 是否触发人工确认。
CRM 层结构性无「发客户」函数（仅草稿）——见 test_no_customer_send_function。
"""
from __future__ import annotations

import json
from datetime import date

from zhuopin_platform.audit import AuditLogger

from sc8 import dispatch
from sc8.models import CONFIDENCE_LOW, DeliveryForecast


def _low_conf_forecast(customer="理想"):
    """无反馈低置信 + 延期的真实型预测（SRM 降级下的典型形态）。"""
    return DeliveryForecast(
        so_id="FO2026050001", product_id="F02N.0184",
        customer_id="", customer_name=customer,
        target_date=date(2026, 6, 15), smt_complete_date=date(2026, 8, 11),
        logistics_days=1, forecast_date=date(2026, 8, 12), delay_days=58,
        risk_level="🔴", bottleneck="无反馈物料",
        confidence=CONFIDENCE_LOW, confidence_reason="含无 SRM 承诺交期物料",
        bottleneck_material="R02.B", param_version="sc8-params-v0",
    )


def test_real_mode_always_queues_never_sends(tmp_path, queue):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    outcome, item_id = dispatch.route_forecast(
        _low_conf_forecast(), queue=queue, first_commitment=True,
        mode="real", audit=audit,
    )
    assert outcome == dispatch.ROUTE_QUEUED          # 入队，未外发
    pend = queue.list_pending()
    assert len(pend) == 1
    assert pend[0]["id"] == item_id
    assert pend[0]["status"] == "pending"
    assert pend[0]["requires_confirmation"] is True


def test_real_mode_forces_customer_outbound_off_even_if_caller_asks(tmp_path, queue):
    # 调用方误传 allow_customer_outbound=True，real 模式仍强制关闭
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    outcome, _ = dispatch.route_forecast(
        _low_conf_forecast(), queue=queue, first_commitment=False,
        mode="real", audit=audit, allow_customer_outbound=True,
    )
    assert outcome == dispatch.ROUTE_QUEUED
    assert queue.list_pending()[0]["requires_confirmation"] is True


def test_audit_records_confidence_classification(tmp_path, queue):
    audit_path = tmp_path / "audit.jsonl"
    audit = AuditLogger.jsonl(audit_path)
    dispatch.route_forecast(_low_conf_forecast(), queue=queue,
                            first_commitment=True, mode="real", audit=audit)
    recs = [json.loads(l) for l in audit_path.read_text(encoding="utf-8").splitlines() if l]
    assert recs
    rec = recs[-1]
    assert rec["decision"]["confidence"] == CONFIDENCE_LOW   # 置信度分类入审计
    assert rec["decision"]["requires_confirmation"] is True
    assert rec["decision"]["sent"] is False                  # 未外发
    assert rec["scenario"] == "SC8"


def test_no_customer_send_function_in_crm_layer():
    # 结构性红线：CRM 层只生成草稿，不得存在任何「发客户」函数
    from zhuopin_platform.shared_tools.crm_notifier import draft as crm_draft
    names = dir(crm_draft)
    for forbidden in ("send", "send_to_customer", "email", "smtp", "deliver"):
        assert not any(forbidden in n.lower() for n in names), \
            f"CRM 草稿层不应有外发函数: {forbidden}"


def test_isolation_no_cross_customer_in_queue(tmp_path, queue):
    # A/B 客户各自入队，收件人不串
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    dispatch.route_forecast(_low_conf_forecast("比亚迪"), queue=queue,
                            first_commitment=True, mode="real", audit=audit)
    dispatch.route_forecast(_low_conf_forecast("理想"), queue=queue,
                            first_commitment=True, mode="real", audit=audit)
    recipients = {p["recipient"] for p in queue.list_pending()}
    assert recipients == {"比亚迪", "理想"}
