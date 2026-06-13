"""OEM 隔离违规留痕（B5 / 审计报告 §2.3 P1 · 先写测试）。

CrossOEMAccessError 抛出前写 cross_oem_access_denied 审计；无 audit 时仅抛错。
"""
from __future__ import annotations

import pytest

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.data_isolation_layer.router import (
    ACTION_CROSS_OEM_DENIED,
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


def test_no_audit_still_raises():
    """未注入 audit → 仍抛错（向后兼容，不因缺 audit 放行）。"""
    router = OEMRouter()
    with pytest.raises(CrossOEMAccessError):
        router.guard(oem="比亚迪", collection="oem_saic")


def test_allowed_access_not_audited(tmp_path):
    """合法访问（本客户库 / 通用库）不写违规审计。"""
    audit = AuditLogger.jsonl(tmp_path / "iso.jsonl")
    router = OEMRouter(audit=audit)
    assert router.guard(oem="比亚迪", collection="oem_byd").allowed is True
    assert router.guard(oem="比亚迪", collection="kb_supplier").allowed is True
    assert audit.query_by(scenario="DATA_ISOLATION") == []
