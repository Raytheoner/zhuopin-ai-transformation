"""FI2 三单匹配一键运行 —— FeedSource → 料品汇总归集分类 + AP-PO 价格校验 → 报告（+ 审计）。

v3 口径修正（2026-07-09）：核对对象改 AP 单 vs INV，PO 作 AP-PO 单价前置参照。

用法（默认 mock 夹具）：
    python -m fi2.run                     # 跑 data/mock，打印摘要 + 写 reports/
    FI2_DATA_SOURCE=csv python -m fi2.run --csv-dir <应急桥接目录>
    python -m fi2.run --data-source u9c --ap-doc-nos AP-1,AP-2   # 真实 PO/GR/AP（design D18-c）
    python -m fi2.run --data-source u9c --ap-supplier-codes ZA0066  # 按供应商批量（design D16）

mock/csv 安全（不连真实库）；u9c 直读端点未开放时 fail-loud（Invoice 对 u9c 源无条件
fail-loud，Attachment/OCR 未就绪，design D15-b——`--data-source u9c` 目前只能跑通
PO/GR/AP 三表，会在 load_invoice 处报错，这是预期行为）。报告 = AI 建议，未过账，非终局。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from zhuopin_platform.audit import AuditLogger

from . import config as _config
from .feed_source import FeedSource, partition_invoices
from .price_check import check_ap_po_price
from .recon_report import build_report
from .result_classify import classify_all, rule_version

_ROOT = Path(__file__).resolve().parent.parent


def run(data_source: str | None = None, *, mock_dir: Path | None = None,
        csv_dir: Path | None = None, evaluator: str = "", period: str = "",
        audit=None, u9c_connector=None, ap_doc_nos: list[str] | None = None,
        ap_supplier_codes: list[str] | None = None) -> dict:
    """跑一轮三单匹配，返回报告 dict。

    `u9c_connector`/`ap_doc_nos`/`ap_supplier_codes`（design D18-c，队列 #78）：
    `data_source="u9c"` 时驱动真实 PO/GR/AP 查询的连接器与 AP 单号/供应商清单，
    原样透传给 `FeedSource`（`FeedSource` 本身早已支持，此前 `run()` 从未接线）。
    Invoice 对 `u9c` 源仍无条件 fail-loud（Attachment/OCR 未就绪，design D15-b 既定
    行为，不因本次接线而改变）——`data_source="u9c"` 目前只能跑通 PO/GR/AP 三表。
    """
    fs = FeedSource(data_source, mock_dir=mock_dir or _ROOT / "data" / "mock", csv_dir=csv_dir,
                     u9c_connector=u9c_connector, ap_doc_nos=ap_doc_nos,
                     ap_supplier_codes=ap_supplier_codes)
    po_lines = fs.load_po_lines()
    ap_lines = fs.load_ap_lines()
    invoice_rows = fs.load_invoice()

    linked, orphaned = partition_invoices(ap_lines, invoice_rows)
    items = classify_all(ap_lines, linked)
    price_results = check_ap_po_price(ap_lines, po_lines)

    return build_report(
        items, orphaned, price_results,
        ap_lines=ap_lines, po_lines=po_lines,
        data_sources={"po": fs.data_source, "ap": fs.data_source, "invoice": fs.data_source},
        evaluator=evaluator, period=period, audit=audit,
    )


def _split_csv_arg(v: str | None) -> list[str] | None:
    if not v:
        return None
    return [s.strip() for s in v.split(",") if s.strip()]


def main() -> None:
    ap = argparse.ArgumentParser(description="FI2 三单匹配自动对账（MVP，v3 口径修正）")
    ap.add_argument("--data-source", default=_config.DATA_SOURCE_DEFAULT, choices=["mock", "csv", "u9c"])
    ap.add_argument("--csv-dir", default=None, help="应急桥接目录（data_source=csv）")
    ap.add_argument("--evaluator", default="", help="L3 复核责任人（IATF 可归责）")
    ap.add_argument("--ap-doc-nos", default=None,
                     help="data_source=u9c 时按 AP 单号驱动（逗号分隔，如 AP-1,AP-2），"
                          "与 --ap-supplier-codes 二选一（design D15-b/D18-c）")
    ap.add_argument("--ap-supplier-codes", default=None,
                     help="data_source=u9c 时按供应商批量驱动（逗号分隔），"
                          "与 --ap-doc-nos 二选一，同传时批量优先（design D16）")
    args = ap.parse_args()

    reports_dir = _ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    audit = AuditLogger.jsonl(reports_dir / "fi2_audit.jsonl")

    u9c_connector = None
    if args.data_source == "u9c":
        from zhuopin_platform.audit.sinks import JsonlSink
        from zhuopin_platform.shared_tools.connector_audit import ConnectorAudit
        from zhuopin_platform.shared_tools.erp_connector import ZpConnector
        # ZpConnector 的 audit= 期望 ConnectorAudit（轻量连接器访问痕迹），
        # 与业务判定用的 AuditLogger 物理分离（同 SC8 run_baoguan_web.py 范式）。
        trace = ConnectorAudit(sink=JsonlSink(reports_dir / "fi2_access_trace.jsonl"))
        u9c_connector = ZpConnector.from_env(audit=trace)

    rep = run(args.data_source, csv_dir=Path(args.csv_dir) if args.csv_dir else None,
              evaluator=args.evaluator, audit=audit, u9c_connector=u9c_connector,
              ap_doc_nos=_split_csv_arg(args.ap_doc_nos),
              ap_supplier_codes=_split_csv_arg(args.ap_supplier_codes))

    out_path = reports_dir / "fi2_reconcile_report.json"
    out_path.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")

    s = rep["summary"]
    print(f"FI2 三单匹配（{rep['data_sources']['po']}）规则版本 {rule_version()}")
    print(f"  料品 {s['total']}：L3建议通过 {s['l3_suggested_pass']} / L2自行消化 {s['l2_self_resolved']} / 需人工确认 {s['needs_review']}")
    print(f"  分类分布：{s['by_classification']}")
    print(f"  孤立发票：{s['orphaned_invoices']}")
    print(f"  AP-PO 价格超差告警：{s['price_check_alerts']}")
    print(f"  {rep['disclaimer']}")
    print(f"  报告 → {out_path}")


if __name__ == "__main__":
    main()
