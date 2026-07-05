"""fi1/confirm.py 单测 — L2 改判录入与审计留痕。"""
import pytest

from zhuopin_platform.audit import AuditLogger


def _make_audit(tmp_path):
    return AuditLogger.jsonl(tmp_path / "fi1_audit.jsonl")


def test_confirm_writes_audit_event(tmp_path):
    """正常改判 → AuditEvent 落 JSONL，override_reason 非空。"""
    from fi1.confirm import confirm

    audit = _make_audit(tmp_path)
    rc = confirm(
        period="2026-06",
        item="MAT-BYD-001",
        conclusion="已核实：月末清洗超损，有领料单支撑",
        reason="清洗工艺集中月底，下月恢复正常",
        evaluator="财务张工",
        audit=audit,
    )
    assert rc == 0

    records = audit.query_by(scenario="FI1", action="l2_override")
    assert len(records) == 1
    r = records[0]
    assert r["override_reason"] == "清洗工艺集中月底，下月恢复正常"
    assert r["evaluator"] == "财务张工"
    assert r["decision"]["period"] == "2026-06"
    assert r["decision"]["item"] == "MAT-BYD-001"
    assert r["automation_level"] == "L2"


def test_confirm_empty_reason_rejected(tmp_path):
    """--reason 空字符串 → 拒绝执行，返回 1，不写 audit。"""
    from fi1.confirm import confirm

    audit = _make_audit(tmp_path)
    rc = confirm(
        period="2026-06",
        item="MAT-BYD-001",
        conclusion="已核实",
        reason="",          # 空 reason
        audit=audit,
    )
    assert rc == 1
    records = audit.query_by(scenario="FI1", action="l2_override")
    assert len(records) == 0, "空 reason 不应写入 audit"


def test_confirm_idempotent(tmp_path):
    """同 period+item 重复 confirm → 第二次 warn 不重复写（幂等）。"""
    from fi1.confirm import confirm

    audit = _make_audit(tmp_path)
    confirm(
        period="2026-06", item="MAT-BYD-001",
        conclusion="第一次结案", reason="有凭证",
        audit=audit,
    )
    rc2 = confirm(
        period="2026-06", item="MAT-BYD-001",
        conclusion="尝试再次结案", reason="别的理由",
        audit=audit,
    )
    assert rc2 == 0
    records = audit.query_by(scenario="FI1", action="l2_override")
    assert len(records) == 1, "幂等：重复 confirm 不应产生第二条记录"
