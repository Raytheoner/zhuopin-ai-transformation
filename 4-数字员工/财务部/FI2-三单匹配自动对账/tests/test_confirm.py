"""fi2/confirm.py 单测 — L3 改判录入与审计留痕（spec: fi2-recon-report）。"""
from __future__ import annotations

from zhuopin_platform.audit import AuditLogger


def _make_audit(tmp_path):
    return AuditLogger.jsonl(tmp_path / "fi2_audit.jsonl")


def test_confirm_writes_audit_event(tmp_path):
    from fi2.confirm import confirm

    audit = _make_audit(tmp_path)
    rc = confirm(
        po_no="PO-2000",
        line_no="10",
        conclusion="已核实：供应商折让未及时录入 PO，发票金额正确",
        reason="对照供应商折让通知单核实，金额差异属正常业务调整",
        evaluator="财务王工",
        audit=audit,
    )
    assert rc == 0

    records = audit.query_by(scenario="FI2", action="l3_override")
    assert len(records) == 1
    r = records[0]
    assert r["override_reason"] == "对照供应商折让通知单核实，金额差异属正常业务调整"
    assert r["evaluator"] == "财务王工"
    assert r["decision"]["po_no"] == "PO-2000"
    assert r["decision"]["line_no"] == "10"
    assert r["automation_level"] == "L3"


def test_confirm_empty_reason_rejected(tmp_path):
    from fi2.confirm import confirm

    audit = _make_audit(tmp_path)
    rc = confirm(
        po_no="PO-2000", line_no="10",
        conclusion="已核实", reason="",
        audit=audit,
    )
    assert rc == 1
    records = audit.query_by(scenario="FI2", action="l3_override")
    assert len(records) == 0, "空 reason 不应写入 audit"


def test_confirm_idempotent(tmp_path):
    from fi2.confirm import confirm

    audit = _make_audit(tmp_path)
    confirm(
        po_no="PO-2000", line_no="10",
        conclusion="第一次结案", reason="有凭证",
        audit=audit,
    )
    rc2 = confirm(
        po_no="PO-2000", line_no="10",
        conclusion="尝试再次结案", reason="别的理由",
        audit=audit,
    )
    assert rc2 == 0
    records = audit.query_by(scenario="FI2", action="l3_override")
    assert len(records) == 1, "幂等：重复 confirm 不应产生第二条记录"
