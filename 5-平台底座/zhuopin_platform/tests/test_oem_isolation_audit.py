"""OEM 隔离违规留痕（B5 / 审计报告 §2.3 P1 · 先写测试；D2=(a) 收紧后审计不再可选）。

CrossOEMAccessError 抛出前写 cross_oem_access_denied 审计；未显式注入 audit 时
内建平台默认 AuditLogger 留痕，默认 logger 亦不可用时直接 fail-closed 拒绝
（D2=(a)，Shao Peishen 本人 2026-09-02 裁决；队列 §一 #466）。
"""
from __future__ import annotations

import pytest

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.data_isolation_layer.router import (
    ACTION_CROSS_OEM_DENIED,
    DEFAULT_AUDIT_LOG_PATH,
    CrossOEMAccessError,
    OEMRouter,
)


def test_cross_collection_denied_is_audited(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "iso.jsonl")
    router = OEMRouter(audit=audit)
    with pytest.raises(CrossOEMAccessError):
        router.guard(oem="比亚迪", collection="oem_saic")
    recs = audit.query_by(scenario="DATA_ISOLATION", action=ACTION_CROSS_OEM_DENIED)
    assert len(recs) == 1
    assert recs[0]["decision"]["oem"] == "比亚迪"
    assert recs[0]["decision"]["collection"] == "oem_saic"
    assert recs[0]["oem_context"] == "比亚迪"


def test_unregistered_oem_denied_is_audited(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "iso.jsonl")
    router = OEMRouter(audit=audit)
    with pytest.raises(CrossOEMAccessError):
        router.resolve(oem="未知客户")
    recs = audit.query_by(scenario="DATA_ISOLATION", action=ACTION_CROSS_OEM_DENIED)
    assert len(recs) == 1
    assert recs[0]["decision"]["reason"] == "未注册的 OEM 上下文"


def test_no_audit_uses_default_logger_and_still_raises(monkeypatch, tmp_path):
    """未注入 audit → 内建平台默认 AuditLogger 写留痕后仍抛错（D2=(a) 收紧：
    审计不再可选，「无留痕地放行」与「无留痕地静默抛错」两种旧形态一并消除）。"""
    monkeypatch.chdir(tmp_path)
    router = OEMRouter()
    with pytest.raises(CrossOEMAccessError):
        router.guard(oem="比亚迪", collection="oem_saic")
    audit = AuditLogger.jsonl(tmp_path / DEFAULT_AUDIT_LOG_PATH)
    recs = audit.query_by(scenario="DATA_ISOLATION", action=ACTION_CROSS_OEM_DENIED)
    assert len(recs) == 1
    assert recs[0]["decision"]["oem"] == "比亚迪"
    assert recs[0]["decision"]["collection"] == "oem_saic"


def test_default_audit_logger_unavailable_fails_closed(monkeypatch):
    """默认 logger 亦不可用（如落盘失败）→ resolve()/guard() 直接拒绝，
    MUST NOT 无留痕放行（spec `platform-oem-isolation` Scenario：审计通道完全不可用）。"""

    class _BrokenAuditLogger:
        def record(self, event):
            raise OSError("模拟审计落盘失败")

    monkeypatch.setattr(
        "zhuopin_platform.data_isolation_layer.router._default_audit_logger",
        lambda: _BrokenAuditLogger(),
    )
    router = OEMRouter()
    with pytest.raises(CrossOEMAccessError):
        router.guard(oem="比亚迪", collection="oem_saic")
    with pytest.raises(CrossOEMAccessError):
        router.resolve(oem="未知客户")


def test_allowed_access_not_audited(tmp_path):
    """合法访问（本客户库 / 通用库）不写违规审计。"""
    audit = AuditLogger.jsonl(tmp_path / "iso.jsonl")
    router = OEMRouter(audit=audit)
    assert router.guard(oem="比亚迪", collection="oem_byd").allowed is True
    assert router.guard(oem="比亚迪", collection="kb_supplier").allowed is True
    assert audit.query_by(scenario="DATA_ISOLATION") == []
