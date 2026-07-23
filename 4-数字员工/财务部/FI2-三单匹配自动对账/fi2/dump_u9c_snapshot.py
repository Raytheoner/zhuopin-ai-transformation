"""真实 u9c 数据落 CSV 快照（design D18-b，队列 #78）——round-1 真实验证用。

PO/GR/AP 三表已支持真实 `u9c` 源（design D15/D16），但 `load_invoice()` 对 `u9c` 源
无条件 fail-loud（Attachment/OCR 未就绪，design D15-b 既定行为，本工具不改变这条
不变量）。本工具只落 PO/GR/AP 三表快照 + 一个仅 header 的空 `payment.csv`（`run()`
不消费 Payment），INV 侧由人工誊录另行补齐同目录 `invoice.csv`（见 D18-a）。

产出目录默认 `data/real_round1/`，已被 `.gitignore` 的 `data/real_*` 规则覆盖，不入库
（真实供应商名/单价/金额，财务红色数据）。

用法：
    python -m fi2.dump_u9c_snapshot --ap-doc-nos AP-1,AP-2 --out-dir data/real_round1
    python -m fi2.dump_u9c_snapshot --ap-supplier-codes ZA0066 --out-dir data/real_round1
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .feed_source import FeedSource
from .models import APLine, GRNLine, POLine

_ROOT = Path(__file__).resolve().parent.parent

_PO_FIELDS = ["po_no", "line_no", "item_code", "qty", "unit_price", "tax_rate", "amount", "supplier", "po_date"]
_AP_FIELDS = ["ap_no", "po_no", "line_no", "item_code", "qty", "unit_price", "untaxed_amount", "tax_amount", "ap_date"]
_GRN_FIELDS = ["grn_no", "po_no", "line_no", "item_code", "recv_qty", "recv_date"]
_INVOICE_FIELDS = ["inv_no", "ap_no", "item_code", "unit", "unit_price", "inv_qty", "untaxed_amount", "tax_rate", "tax_amount", "inv_date"]
_PAYMENT_FIELDS = ["pay_no", "inv_no", "pay_amount", "pay_date"]


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def dump_snapshot(
    u9c_connector, out_dir: Path | str, *,
    ap_doc_nos: list[str] | None = None,
    ap_supplier_codes: list[str] | None = None,
) -> dict[str, int]:
    """拉取真实 PO/GR/AP 落 CSV 快照，返回各表行数（供调用方核对/打印）。"""
    out = Path(out_dir)
    fs = FeedSource("u9c", u9c_connector=u9c_connector,
                     ap_doc_nos=ap_doc_nos, ap_supplier_codes=ap_supplier_codes)

    po_lines: list[POLine] = fs.load_po_lines()
    ap_lines: list[APLine] = fs.load_ap_lines()
    grn: list[GRNLine] = fs.load_grn()

    _write_csv(out / "po_lines.csv", _PO_FIELDS, [
        dict(po_no=r.po_no, line_no=r.line_no, item_code=r.item_code, qty=r.qty,
             unit_price=r.unit_price, tax_rate=r.tax_rate, amount=r.amount,
             supplier=r.supplier, po_date=r.po_date)
        for r in po_lines
    ])
    _write_csv(out / "ap_lines.csv", _AP_FIELDS, [
        dict(ap_no=r.ap_no, po_no=r.po_no, line_no=r.line_no, item_code=r.item_code,
             qty=r.qty, unit_price=r.unit_price, untaxed_amount=r.untaxed_amount,
             tax_amount=r.tax_amount, ap_date=r.ap_date)
        for r in ap_lines
    ])
    _write_csv(out / "grn.csv", _GRN_FIELDS, [
        dict(grn_no=r.grn_no, po_no=r.po_no, line_no=r.line_no, item_code=r.item_code,
             recv_qty=r.recv_qty, recv_date=r.recv_date)
        for r in grn
    ])
    # payment.csv：run() 不消费 load_payment()，落仅 header 空表保持 csv loader 完整性。
    if not (out / "payment.csv").exists():
        _write_csv(out / "payment.csv", _PAYMENT_FIELDS, [])
    # invoice.csv：本工具不生成（人工誊录，见 D18-a），若不存在先占位空表避免 csv loader 报错，
    # 后续人工誊录会覆盖此文件。
    if not (out / "invoice.csv").exists():
        _write_csv(out / "invoice.csv", _INVOICE_FIELDS, [])

    return {"po_lines": len(po_lines), "ap_lines": len(ap_lines), "grn": len(grn)}


def main() -> None:
    ap = argparse.ArgumentParser(description="真实 u9c PO/GR/AP 落 CSV 快照（design D18-b）")
    ap.add_argument("--ap-doc-nos", default=None, help="逗号分隔 AP 单号清单")
    ap.add_argument("--ap-supplier-codes", default=None, help="逗号分隔供应商清单（批量）")
    ap.add_argument("--out-dir", default=str(_ROOT / "data" / "real_round1"))
    args = ap.parse_args()

    from zhuopin_platform.audit.sinks import JsonlSink
    from zhuopin_platform.shared_tools.connector_audit import ConnectorAudit
    from zhuopin_platform.shared_tools.erp_connector import ZpConnector

    reports_dir = _ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    # ZpConnector 的 audit= 期望 ConnectorAudit（轻量连接器访问痕迹），非业务判定用
    # 的 AuditLogger（同 run.py::main()/SC8 run_baoguan_web.py 范式）。
    trace = ConnectorAudit(sink=JsonlSink(reports_dir / "fi2_access_trace.jsonl"))
    conn = ZpConnector.from_env(audit=trace)

    doc_nos = [s.strip() for s in args.ap_doc_nos.split(",") if s.strip()] if args.ap_doc_nos else None
    supplier_codes = [s.strip() for s in args.ap_supplier_codes.split(",") if s.strip()] if args.ap_supplier_codes else None

    counts = dump_snapshot(conn, args.out_dir, ap_doc_nos=doc_nos, ap_supplier_codes=supplier_codes)
    print(f"快照已写入 {args.out_dir}：{counts}")


if __name__ == "__main__":
    main()
