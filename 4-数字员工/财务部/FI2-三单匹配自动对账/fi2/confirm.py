"""FI2 L3 改判录入 CLI — 财务人员对 needs_review 匹配项的人工结案入口。

用法::

    python -m fi2.confirm \\
        --po-no   PO-2026-0001 \\
        --line-no 10 \\
        --conclusion "已核实：供应商折让未及时录入 PO，发票金额正确" \\
        --reason  "对照供应商折让通知单核实，金额差异属正常业务调整"

约束（IATF 16949 可追溯）：
- ``--reason`` 必填且不可为空，缺失或空字符串拒绝执行。
- 每次 confirm 写一条 AuditEvent 到 ``reports/fi2_audit.jsonl``（与 run.py 同源）。
- 幂等：同 po_no+line_no 已有 confirm 记录则打印警告，不重复写（exit 0）。
- confirm.py 只负责留痕；AI 结论永远是"建议"，结案在财务人员——L3 阶段不实现自动过账。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from zhuopin_platform.audit import AuditEvent, AuditLogger

_ROOT = Path(__file__).resolve().parent.parent
_AUDIT_PATH = _ROOT / "reports" / "fi2_audit.jsonl"


def _already_confirmed(audit: AuditLogger, po_no: str, line_no: str) -> bool:
    """检查同 po_no + line_no 是否已有改判记录。"""
    existing = audit.query_by(scenario="FI2", action="l3_override")
    for r in existing:
        d = r.get("decision", {})
        if d.get("po_no") == po_no and d.get("line_no") == line_no:
            return True
    return False


def confirm(
    po_no: str,
    line_no: str,
    conclusion: str,
    reason: str,
    evaluator: str = "L3",
    audit: AuditLogger | None = None,
) -> int:
    """录入 L3 改判，返回 0=成功 / 1=失败。

    供测试与 CLI 共用；``audit`` 为 None 时自动初始化至默认路径。
    """
    if not reason or not reason.strip():
        print("错误：--reason 不可为空（IATF 要求改判原因留档）", file=sys.stderr)
        return 1

    if audit is None:
        _ROOT.joinpath("reports").mkdir(exist_ok=True)
        audit = AuditLogger.jsonl(_AUDIT_PATH)

    if _already_confirmed(audit, po_no, line_no):
        print(
            f"警告：po_no={po_no!r} line_no={line_no!r} 已有改判记录，"
            "跳过重复写入（幂等）。如需修订，请联系 AI 系统管理员手工追加。"
        )
        return 0

    event = AuditEvent(
        scenario="FI2",
        action="l3_override",
        evaluator=evaluator,
        automation_level="L3",
        decision={
            "po_no": po_no,
            "line_no": line_no,
            "conclusion": conclusion,
        },
        data_sources={"input": "human"},
        override_reason=reason.strip(),
    )
    audit.record(event)
    print(f"✓ L3 改判已记录：po_no={po_no!r} line_no={line_no!r}")
    print(f"  结论：{conclusion}")
    print(f"  理由：{reason.strip()}")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(
        description="FI2 L3 改判录入 — needs_review 匹配项人工结案（审计留痕）"
    )
    ap.add_argument("--po-no", required=True, help="PO 号")
    ap.add_argument("--line-no", required=True, help="PO 行号")
    ap.add_argument("--conclusion", required=True, help="人工结论（简短描述，入审计报告）")
    ap.add_argument("--reason", required=True, help="改判原因（必填，知识资产台账用）")
    ap.add_argument("--evaluator", default="L3", help="责任人姓名（IATF 可归责，默认'L3'）")
    args = ap.parse_args()

    sys.exit(confirm(
        po_no=args.po_no,
        line_no=args.line_no,
        conclusion=args.conclusion,
        reason=args.reason,
        evaluator=args.evaluator,
    ))


if __name__ == "__main__":
    main()
