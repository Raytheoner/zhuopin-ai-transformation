"""平台底座冒烟测试 —— 验证审计写读 + OEM 隔离红线。"""
from pathlib import Path

import pytest

from zhuopin_platform.audit import AuditLogger, AuditEvent
from zhuopin_platform.data_isolation_layer import OEMRouter, CrossOEMAccessError


def test_audit_roundtrip(tmp_path: Path):
    audit = AuditLogger.jsonl(tmp_path / "audit_log.jsonl")
    audit.record(AuditEvent(
        scenario="SC1", action="supplier_risk_eval",
        evaluator="张采购", automation_level="L2",
        decision={"risk_level": 4, "composite_score": 3.6},
        data_sources={"delivery": "SRM", "iqc": "人工录入"},
        content_hash="abc123",
    ))
    assert audit.query_by(scenario="SC1")[0]["evaluator"] == "张采购"
    info = audit.verify_integrity()
    assert info["total"] == 1 and info["scenarios"] == ["SC1"]


def test_audit_no_raw_red_data(tmp_path: Path):
    """红色数据保护：事件结构里没有原始注册资本/IQC 数值字段。"""
    e = AuditEvent(scenario="SC1", action="x", evaluator="y", automation_level="L2")
    assert "registered_capital" not in e.to_dict()
    assert "iqc_raw" not in e.to_dict()


def test_isolation_allows_own_and_general():
    r = OEMRouter()
    assert r.resolve("比亚迪") == "oem_byd"
    assert r.guard(oem="比亚迪", collection="oem_byd").allowed
    assert r.guard(oem="上汽", collection="kb_supplier").allowed  # 通用库放行


def test_isolation_blocks_cross_oem():
    r = OEMRouter()
    with pytest.raises(CrossOEMAccessError):
        r.guard(oem="比亚迪", collection="oem_saic")   # 跨客户，拒绝
    with pytest.raises(CrossOEMAccessError):
        r.resolve("某未注册客户")                        # 未注册，拒绝
