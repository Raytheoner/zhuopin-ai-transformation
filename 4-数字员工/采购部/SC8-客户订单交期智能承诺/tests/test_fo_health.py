"""FO 健康告警（Task 3）—— 内部运维告警，全 mock、不触网。

覆盖：
  · FO 不可达 → 审计留痕(action=fo_unreachable, source=FO) + 内部企微告警；
  · 无 webhook 配置 → 只审计、不推送（不报错）；
  · 推送失败 → 不掩盖原始 FO 错误（alert 不抛）；
  · load_real_orders 在 FO 不可达时先告警**再 re-raise**（fail-loud，不回退 mock）。
"""
from __future__ import annotations

import pytest
from zhuopin_platform.audit import AuditLogger

from sc8 import fo_health
from sc8.fo_health import ACTION_FO_UNREACHABLE, alert_fo_unreachable, build_alert_text


def _capturing_sender():
    sent = []
    return sent, (lambda webhook, text: sent.append((webhook, text)))


def test_alert_audits_and_notifies(audit):
    sent, send = _capturing_sender()
    res = alert_fo_unreachable(
        RuntimeError("HTTP 502 Bad Gateway"),
        api_base="http://192.168.100.51:8800",
        audit=audit, webhook_url="https://qyapi.example/internal", send_fn=send,
    )
    assert res == {"audited": True, "notified": True, "webhook_configured": True}
    # 推送内容是内部运维告警
    assert len(sent) == 1
    assert sent[0][0] == "https://qyapi.example/internal"
    assert "FO 预测订单 API 不可达" in sent[0][1]
    assert "502" in sent[0][1]
    # 审计留痕：action=fo_unreachable, source=FO, reachable=False
    events = audit.query_by(action=ACTION_FO_UNREACHABLE)
    assert len(events) == 1
    assert events[0]["decision"]["source"] == "FO"
    assert events[0]["decision"]["reachable"] is False
    assert events[0]["data_sources"]["fo"] == "unreachable"


def test_no_webhook_audits_only(audit, monkeypatch):
    # 清掉环境 webhook，且不传 webhook_url → 不推送、仍审计
    for k in fo_health.OPS_WEBHOOK_ENV:
        monkeypatch.delenv(k, raising=False)
    sent, send = _capturing_sender()
    res = alert_fo_unreachable(TimeoutError("timeout"), audit=audit, send_fn=send)
    assert res["webhook_configured"] is False
    assert res["notified"] is False
    assert res["audited"] is True
    assert sent == []


def test_webhook_resolved_from_env(audit, monkeypatch):
    monkeypatch.setenv("WECOM_WEBHOOK_URL", "https://qyapi.example/env-hook")
    sent, send = _capturing_sender()
    res = alert_fo_unreachable(RuntimeError("boom"), audit=audit, send_fn=send)
    assert res["webhook_configured"] is True
    assert sent[0][0] == "https://qyapi.example/env-hook"


def test_notify_failure_does_not_raise(audit):
    def _boom(webhook, text):
        raise RuntimeError("企微推送失败")
    # 推送失败被吞（不掩盖原始 FO 错误）；audited 仍 True，notified False
    res = alert_fo_unreachable(RuntimeError("orig"), audit=audit,
                               webhook_url="https://x", send_fn=_boom)
    assert res["audited"] is True
    assert res["notified"] is False


def test_build_alert_text_contains_failloud_note():
    txt = build_alert_text(RuntimeError("502"), api_base="http://fo:8800")
    assert "未回退 mock" in txt
    assert "http://fo:8800" in txt


def test_load_real_orders_failloud_alerts_then_raises(audit, monkeypatch):
    """FO 不可达 → load_real_orders 先告警再 re-raise（fail-loud，不回退 mock）。"""
    from sc8 import sources

    def _unreachable(api_base=None, **kwargs):
        raise RuntimeError("无法连接预测订单 API: HTTP 502")
    monkeypatch.setattr(sources, "load_forecast_orders_from_api", _unreachable)

    # 经 fo_health → wecom.send_text 推送：patch send_text 捕获，env 提供 webhook
    sent, send = _capturing_sender()
    monkeypatch.setenv("WECOM_WEBHOOK_URL", "https://qyapi.example/ops")
    from zhuopin_platform.shared_tools.notifiers import wecom
    monkeypatch.setattr(wecom, "send_text", send)

    with pytest.raises(RuntimeError, match="502"):
        sources.load_real_orders(audit=audit)

    # 告警确实推送 + 审计留痕（fail-loud：异常仍抛出，上面已断言）
    assert len(sent) == 1
    assert "FO 预测订单 API 不可达" in sent[0][1]
    assert len(audit.query_by(action=ACTION_FO_UNREACHABLE)) == 1
