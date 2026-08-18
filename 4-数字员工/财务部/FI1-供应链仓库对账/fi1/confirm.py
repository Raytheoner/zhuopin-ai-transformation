"""FI1 L2 改判录入 CLI — 财务/供应链经理对 needs_review 差异项的人工结案入口。

用法::

    python -m fi1.confirm \\
        --period  2026-06 \\
        --item    MAT-BYD-001 \\
        --conclusion "已核实：月末 SMT 清洗超损，有领料单支撑" \\
        --reason  "清洗工艺本月用量集中在月底，下月对账恢复正常"

约束（IATF 16949 可追溯）：
- ``--reason`` 必填且不可为空，缺失或空字符串拒绝执行。
- 每次 confirm 写一条 AuditEvent 到 ``reports/fi1_audit.jsonl``（与 run.py 同源）。
- 幂等：同 period+item 已有 confirm 记录则打印警告，不重复写（exit 0）。
- confirm.py 只负责留痕；是否关闭 ComponentReconcile.needs_review 由
  后续报告/审批流处理——AI 结论永远是"建议"，结案在财务+供应链经理。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# —— 平台底座路径引导（队列 #345 收拢；唯一被允许的样板，实现见
# `5-平台底座/zhuopin_platform/zhuopin_platform/bootstrap.py`）。必须放在本文件任何
# zhuopin_platform / 场景包 import 之前。下方五行只负责让 bootstrap 自身可被 import、
# 不含任何判断分支；开发机 monorepo 与 `.51` 扁平部署两种布局的分歧由 ensure_paths 处理。——
_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, _HERE.parent.parent)  # noqa: E402

from zhuopin_platform.audit import AuditEvent, AuditLogger

_ROOT = Path(__file__).resolve().parent.parent
_AUDIT_PATH = _ROOT / "reports" / "fi1_audit.jsonl"


def _already_confirmed(audit: AuditLogger, period: str, item: str) -> bool:
    """检查同 period + item 是否已有改判记录。"""
    existing = audit.query_by(scenario="FI1", action="l2_override")
    for r in existing:
        d = r.get("decision", {})
        if d.get("period") == period and d.get("item") == item:
            return True
    return False


def confirm(
    period: str,
    item: str,
    conclusion: str,
    reason: str,
    evaluator: str = "L2",
    audit: AuditLogger | None = None,
) -> int:
    """录入 L2 改判，返回 0=成功 / 1=失败。

    供测试与 CLI 共用；``audit`` 为 None 时自动初始化至默认路径。
    """
    if not reason or not reason.strip():
        print("错误：--reason 不可为空（IATF 要求改判原因留档）", file=sys.stderr)
        return 1

    if audit is None:
        _ROOT.joinpath("reports").mkdir(exist_ok=True)
        audit = AuditLogger.jsonl(_AUDIT_PATH)

    if _already_confirmed(audit, period, item):
        print(
            f"警告：period={period!r} item={item!r} 已有改判记录，"
            "跳过重复写入（幂等）。如需修订，请联系 AI 系统管理员手工追加。"
        )
        return 0

    event = AuditEvent(
        scenario="FI1",
        action="l2_override",
        evaluator=evaluator,
        automation_level="L2",
        decision={
            "period": period,
            "item": item,
            "conclusion": conclusion,
        },
        data_sources={"input": "human"},
        override_reason=reason.strip(),
    )
    audit.record(event)
    print(f"✓ L2 改判已记录：period={period!r} item={item!r}")
    print(f"  结论：{conclusion}")
    print(f"  理由：{reason.strip()}")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(
        description="FI1 L2 改判录入 — needs_review 差异项人工结案（审计留痕）"
    )
    ap.add_argument("--period", required=True, help="对账期间，如 2026-06")
    ap.add_argument("--item", required=True, help="差异项标识（component_id 或物料描述）")
    ap.add_argument("--conclusion", required=True, help="人工结论（简短描述，入审计报告）")
    ap.add_argument("--reason", required=True, help="改判原因（必填，知识资产台账用）")
    ap.add_argument("--evaluator", default="L2", help="责任人姓名（IATF 可归责，默认'L2'）")
    args = ap.parse_args()

    sys.exit(confirm(
        period=args.period,
        item=args.item,
        conclusion=args.conclusion,
        reason=args.reason,
        evaluator=args.evaluator,
    ))


if __name__ == "__main__":
    main()
