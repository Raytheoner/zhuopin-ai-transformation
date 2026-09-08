"""通用库写入侧只读闸（D5=(a)，Shao Peishen 本人 2026-09-02 裁决；队列 §一 #491）。

`GENERAL_COLLECTIONS` 的写入侧「无 OEM 信息」校验入口尚未建成 ⇒ 通用库整体置为只读：
已有内容不受影响，禁止任何新写入。写入企图属违规企图，拒绝前必须留痕
（隔离规范 §3.2）；审计通道不可用时同样 fail-closed（沿用 #466 D2=(a) 的通道）。

读取侧语义**不变**——通用库仍无条件放行（本包不扩大到读取侧，见变更包 design 决策 4）。
"""
from __future__ import annotations

import pytest

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.data_isolation_layer import (
    CrossOEMAccessError,
    GeneralCollectionReadOnlyError,
    OEMRouter,
)
from zhuopin_platform.data_isolation_layer.router import (
    ACTION_CROSS_OEM_DENIED,
    ACTION_GENERAL_WRITE_DENIED,
    DEFAULT_AUDIT_LOG_PATH,
    GENERAL_COLLECTIONS,
)


@pytest.mark.parametrize("collection", sorted(GENERAL_COLLECTIONS))
def test_write_to_every_general_collection_is_denied_and_audited(tmp_path, collection):
    """三个通用库逐个覆盖（不抽样）：写入被拒 ＋ 拒绝前写 audit。"""
    audit = AuditLogger.jsonl(tmp_path / "iso.jsonl")
    router = OEMRouter(audit=audit)
    with pytest.raises(GeneralCollectionReadOnlyError):
        router.guard_write(oem="比亚迪", collection=collection)
    recs = audit.query_by(scenario="DATA_ISOLATION", action=ACTION_GENERAL_WRITE_DENIED)
    assert len(recs) == 1
    assert recs[0]["decision"]["collection"] == collection
    assert recs[0]["decision"]["oem"] == "比亚迪"
    assert "只读" in recs[0]["decision"]["reason"]
    assert recs[0]["oem_context"] == "比亚迪"


def test_readonly_gate_applies_to_every_oem_context(tmp_path):
    """只读闸不因客户上下文而豁免——已注册的三家与未注册上下文一律拒绝。"""
    audit = AuditLogger.jsonl(tmp_path / "iso.jsonl")
    router = OEMRouter(audit=audit)
    for oem in ("比亚迪", "上汽", "理想", "未知客户", ""):
        with pytest.raises(GeneralCollectionReadOnlyError):
            router.guard_write(oem=oem, collection="kb_quality_cases")
    recs = audit.query_by(scenario="DATA_ISOLATION", action=ACTION_GENERAL_WRITE_DENIED)
    assert len(recs) == 5


def test_readonly_error_is_not_cross_oem_error():
    """异常类刻意分离：`except CrossOEMAccessError` MUST NOT 顺手吞掉只读闸。"""
    assert not issubclass(GeneralCollectionReadOnlyError, CrossOEMAccessError)
    assert not issubclass(CrossOEMAccessError, GeneralCollectionReadOnlyError)
    assert issubclass(GeneralCollectionReadOnlyError, PermissionError)


def test_write_to_own_collection_allowed_and_not_audited(tmp_path):
    """本客户专属库写入照常放行，且不写违规审计（fail-closed 只覆盖拒绝路径）。"""
    audit = AuditLogger.jsonl(tmp_path / "iso.jsonl")
    router = OEMRouter(audit=audit)
    decision = router.guard_write(oem="比亚迪", collection="oem_byd")
    assert decision.allowed is True
    assert decision.collection == "oem_byd"
    assert audit.query_by(scenario="DATA_ISOLATION") == []


def test_write_to_other_oem_collection_still_cross_oem_denied(tmp_path):
    """跨客户专属库写入仍走既有跨 OEM 判定与留痕，本包不另立一套规则。"""
    audit = AuditLogger.jsonl(tmp_path / "iso.jsonl")
    router = OEMRouter(audit=audit)
    with pytest.raises(CrossOEMAccessError):
        router.guard_write(oem="比亚迪", collection="oem_saic")
    recs = audit.query_by(scenario="DATA_ISOLATION", action=ACTION_CROSS_OEM_DENIED)
    assert len(recs) == 1
    assert recs[0]["decision"]["reason"] == "跨客户专属库访问"


def test_unregistered_oem_write_to_oem_collection_denied(tmp_path):
    """未注册上下文写专属库：仍在 `resolve()` 处被拒并留痕。"""
    audit = AuditLogger.jsonl(tmp_path / "iso.jsonl")
    router = OEMRouter(audit=audit)
    with pytest.raises(CrossOEMAccessError):
        router.guard_write(oem="未知客户", collection="oem_byd")
    recs = audit.query_by(scenario="DATA_ISOLATION", action=ACTION_CROSS_OEM_DENIED)
    assert len(recs) == 1
    assert recs[0]["decision"]["reason"] == "未注册的 OEM 上下文"


def test_write_denied_uses_default_logger_when_audit_not_injected(monkeypatch, tmp_path):
    """未注入 audit：经平台默认 AuditLogger 留痕后仍拒绝（沿用 #466 D2=(a) 通道）。"""
    monkeypatch.chdir(tmp_path)
    router = OEMRouter()
    with pytest.raises(GeneralCollectionReadOnlyError):
        router.guard_write(oem="上汽", collection="kb_supplier")
    audit = AuditLogger.jsonl(tmp_path / DEFAULT_AUDIT_LOG_PATH)
    recs = audit.query_by(scenario="DATA_ISOLATION", action=ACTION_GENERAL_WRITE_DENIED)
    assert len(recs) == 1
    assert recs[0]["decision"]["collection"] == "kb_supplier"


def test_write_denied_fails_closed_when_audit_unavailable(monkeypatch):
    """审计通道坏掉时 MUST NOT 无留痕放行——仍抛 GeneralCollectionReadOnlyError。"""

    class _BrokenAuditLogger:
        def record(self, event):
            raise OSError("模拟审计落盘失败")

    monkeypatch.setattr(
        "zhuopin_platform.data_isolation_layer.router._default_audit_logger",
        lambda: _BrokenAuditLogger(),
    )
    router = OEMRouter()
    with pytest.raises(GeneralCollectionReadOnlyError):
        router.guard_write(oem="理想", collection="kb_finance_rules")


def test_write_denied_fails_closed_when_no_logger_at_all(monkeypatch):
    """默认 logger 构造失败（`_audit is None`）时同样 fail-closed 拒绝。"""
    monkeypatch.setattr(
        "zhuopin_platform.data_isolation_layer.router._default_audit_logger",
        lambda: (_ for _ in ()).throw(RuntimeError("模拟构造失败")),
    )
    router = OEMRouter()
    assert router._audit is None
    with pytest.raises(GeneralCollectionReadOnlyError):
        router.guard_write(oem="比亚迪", collection="kb_supplier")


def test_read_side_unchanged_general_collections_still_pass(tmp_path):
    """回归护栏：本包 MUST NOT 改动读取侧——通用库读取仍无条件放行、不留痕。"""
    audit = AuditLogger.jsonl(tmp_path / "iso.jsonl")
    router = OEMRouter(audit=audit)
    for collection in sorted(GENERAL_COLLECTIONS):
        assert router.guard(oem="比亚迪", collection=collection).allowed is True
        assert router.guard(oem="未知客户", collection=collection).allowed is True
    assert audit.query_by(scenario="DATA_ISOLATION") == []


def test_no_runtime_switch_or_validator_hook_exists(monkeypatch, tmp_path):
    """闸不得留运行期开关/可注入 validator——那是"注入空校验器即绕过"的路径。

    本用例是**架构约束**的机器守：若日后有人加回开关，须先来这里删掉断言，
    从而在 code review 里显形（解闸的正确做法是改写 `guard_write` 调真校验入口）。
    """
    monkeypatch.chdir(tmp_path)  # 默认构造会解析 reports/ 相对路径，隔离到临时目录
    from zhuopin_platform.data_isolation_layer import router as router_mod

    forbidden = [
        name for name in dir(router_mod)
        if any(k in name.upper() for k in ("WRITABLE", "ALLOW_WRITE", "WRITE_ENABLED"))
    ]
    assert forbidden == []
    assert not hasattr(OEMRouter(), "write_validator")
