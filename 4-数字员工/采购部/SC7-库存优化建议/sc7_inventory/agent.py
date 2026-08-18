"""
SC7 数字员工入口：run_sc7() 薄包装 + L1/L2 分桶审计。

承接原 SC5「采购建议与供应商遴选」引擎（2026-07-06 v2.3 重排迁移，SC5 场景编号退役）。

L1 audit — 可自动下单汇总（auto_count / auto_total）
L2 audit — 待人工审核汇总（review_count / review_total / human_required=True / triggered_rules）
IATF 16949：L2 事件 human_required=True，mock 阶段不自动执行下单。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Union

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

from zhuopin_platform.agents.kit_engine import calc_shortage, explode_bom
from zhuopin_platform.audit import AuditEvent, AuditLogger
from zhuopin_platform.shared_tools import csv_loaders

from sc7_inventory.purchase_engine import (
    build_recommendations,
    calc_cost_summary,
    calc_material_earliest_dates,
)


def run_sc7(
    mock_dir: Union[str, Path],
    today: str,
    audit_path: Union[str, Path, None] = None,
) -> list[dict]:
    """采购建议与供应商遴选主入口（SC7 库存优化建议场景）。

    参数：
        mock_dir   — mock CSV 目录（含 bom/inventory/purchase_orders/production_plan/suppliers）
        today      — 运行日期字符串 YYYY-MM-DD，用于审计时间戳
        audit_path — JSONL 审计落盘路径；None 时不落盘（方便单测）

    返回：list[dict] 采购建议清单
    """
    mock_dir = Path(mock_dir)

    bom = csv_loaders.load_bom(mock_dir)
    plans = csv_loaders.load_production_plan(mock_dir)
    inv = csv_loaders.load_inventory(mock_dir)
    pos = csv_loaders.load_purchase_orders(mock_dir)
    suppliers = csv_loaders.load_suppliers(mock_dir)

    gross = explode_bom(bom, plans)
    shortages, _missing_snapshot = calc_shortage(gross, inv, pos)
    material_dates = calc_material_earliest_dates(bom, plans, shortages)
    recs = build_recommendations(shortages, suppliers, material_dates)
    summary = calc_cost_summary(recs)

    if audit_path is not None:
        _write_audit(recs, summary, today, Path(audit_path))

    return recs


def _write_audit(recs: list[dict], summary: dict, today: str, audit_path: Path) -> None:
    audit = AuditLogger.jsonl(audit_path)

    auto_recs = [r for r in recs if r["review_status"] == "可自动下单"]
    review_recs = [r for r in recs if r["review_status"] == "待人工审核"]

    # L1 事件 — 可自动下单汇总
    if auto_recs:
        audit.record(AuditEvent(
            scenario="SC7",
            action="purchase_recommendation_eval",
            evaluator="auto",
            automation_level="L1",
            decision={
                "auto_count": len(auto_recs),
                "auto_total": summary["auto_total"],
                "materials": [r["material_id"] for r in auto_recs],
                "run_date": today,
            },
            data_sources={"bom": "mock", "inventory": "mock",
                          "purchase_orders": "mock", "suppliers": "mock"},
        ))

    # L2 事件 — 待人工审核汇总（IATF 门禁：human_required=True）
    if review_recs:
        all_triggered: list[str] = []
        for r in review_recs:
            all_triggered.extend(r.get("triggered_rules", []))
        audit.record(AuditEvent(
            scenario="SC7",
            action="purchase_recommendation_eval",
            evaluator="procurement_manager",
            automation_level="L2",
            decision={
                "review_count": len(review_recs),
                "review_total": summary["review_total"],
                "human_required": True,
                "triggered_rules": sorted(set(all_triggered)),
                "materials": [r["material_id"] for r in review_recs],
                "run_date": today,
            },
            data_sources={"bom": "mock", "inventory": "mock",
                          "purchase_orders": "mock", "suppliers": "mock"},
        ))


def _print_report(recs: list[dict], summary: dict) -> None:
    print(f"\n{'='*60}")
    print("SC7 库存优化建议 — 采购建议与供应商遴选")
    print(f"{'='*60}")
    print(f"{'物料':10} {'缺口':>8} {'采购量':>8} {'供应商':>8} {'单价':>8} {'预估金额':>12} 状态")
    print("-" * 72)
    for r in recs:
        print(
            f"{r['material_id']:10} {r['shortage']:>8.1f} {r['purchase_qty']:>8} "
            f"{r['supplier_id'] or '待指派':>8} {r['unit_price']:>8.2f} "
            f"{r['estimated_cost']:>12,.0f} {r['review_status']}"
        )
    print("-" * 72)
    print(f"可自动下单总额：{summary['auto_total']:>12,.0f} 元")
    print(f"待人工审核总额：{summary['review_total']:>12,.0f} 元")
    print(f"合计：          {summary['grand_total']:>12,.0f} 元")


if __name__ == "__main__":
    import sys
    from pathlib import Path
    from sc7_inventory.purchase_engine import calc_cost_summary

    mock_dir = Path(__file__).parent.parent / "tests" / "mock_data"
    audit_path = Path(__file__).parent.parent / "reports" / "sc7_audit.jsonl"
    audit_path.parent.mkdir(exist_ok=True)

    today = sys.argv[1] if len(sys.argv) > 1 else "2026-06-11"
    recs = run_sc7(mock_dir=mock_dir, today=today, audit_path=audit_path)
    summary = calc_cost_summary(recs)
    _print_report(recs, summary)
    print(f"\n审计日志已写入：{audit_path}")
