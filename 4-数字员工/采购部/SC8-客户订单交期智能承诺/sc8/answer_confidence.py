"""
SC8 内部子模块入口（胶水层）：调用 answer_confidence_engine，写 audit 留痕。

原 SC3「供应商在途跟踪与绩效」场景入口（run_sc3），2026-07-06 v2.3 重排随
SC3 场景编号退役迁入 SC8——审计 scenario 由退役编号 "SC3" 改标存续场景
"SC8"，其余行为不变。引擎保持纯算法；审计/通知只在本文件处理。
"""
from __future__ import annotations

import sys
from datetime import date
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

from zhuopin_platform.audit import AuditLogger, AuditEvent
from zhuopin_platform.shared_tools.csv_connector import CSVConnector

from .answer_confidence_engine import SupplierRisk, analyze

_DEFAULT_AUDIT = Path(__file__).resolve().parents[1] / "reports" / "answer_confidence_audit.jsonl"


def run_answer_confidence(
    mock_dir: Path | str,
    today: date,
    planning_days: int = 14,
    srm_dates: dict[str, str] | None = None,
    audit_path: Path | str | None = None,
) -> list[SupplierRisk]:
    """
    执行供应商在途订单风险评估（答交可信度判据源），写 audit，返回风险列表。

    automation_level=L1：内部只读看板，不触发 L2 人工确认门禁。
    """
    connector = CSVConnector(mock_dir)
    results   = analyze(connector, today, planning_days=planning_days, srm_dates=srm_dates)

    high_pos   = [r.po_id for r in results if r.risk_level == "high"]
    high_count   = sum(1 for r in results if r.risk_level == "high")
    medium_count = sum(1 for r in results if r.risk_level == "medium")
    low_count    = sum(1 for r in results if r.risk_level == "low")

    log_path = Path(audit_path) if audit_path else _DEFAULT_AUDIT
    log_path.parent.mkdir(parents=True, exist_ok=True)
    audit = AuditLogger.jsonl(log_path)
    audit.record(AuditEvent(
        scenario="SC8",
        action="in_transit_risk_eval",
        evaluator="auto",
        automation_level="L1",
        decision={
            "total_pos":    len(results),
            "high_count":   high_count,
            "medium_count": medium_count,
            "low_count":    low_count,
            "high_po_ids":  high_pos,
        },
        data_sources={"purchase_orders": "CSV mock", "inventory": "CSV mock"},
    ))

    return results


def _print_report(results: list[SupplierRisk], today: date) -> None:
    icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    print(f"\nSC8 答交可信度评估报告（基准日：{today}）")
    print(f"共 {len(results)} 笔在途订单\n")
    for r in results:
        mark = icon[r.risk_level]
        print(f"{mark} {r.po_id} | {r.material_name}({r.material_id}) | "
              f"剩余{r.days_remaining}天 | DOS={r.dos_days:.1f}天 | 待收{r.qty_remaining:.0f}")
        for reason in r.risk_reasons:
            print(f"   ↳ {reason}")


if __name__ == "__main__":
    mock_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(__file__).resolve().parents[1] / "tests" / "mock_data_answer_confidence"
    )
    today = date.today()
    results = run_answer_confidence(mock_dir, today)
    _print_report(results, today)
