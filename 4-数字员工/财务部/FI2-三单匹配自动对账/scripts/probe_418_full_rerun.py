"""#418 第③件：全量重跑 ＋ 四类分布对比（只读，不写任何生产文件）。

🔴 只读：AP/PO 走 `AP/Query`／`Purchase/Query` 两个只读端点；发票只**读**给定目录下的
`invoice.csv`（`--invoice-dir`），不写、不改、不重建。产出只有 stdout ＋ `--dump` 指定
的一份本地 JSON（默认不落盘）。

口径（与面板 `webapp._run_with_detail` 一致，避免「换了口径的对比」）：
  · AP 范围 ＝ `invoice.csv` 里出现过的全部 `ap_no` 去重 —— 这正是 2026-08-24 那次
    「640 单」基线的取数方式（当时 640 张，今天会更多，因为摄取每天在长）。
  · 分类 ＝ `partition_invoices` → `classify_all`，四类分布只统计 `items`（**不含孤立
    发票**）—— 基线 2497/883/204/1 也是这么数的（合计 3,585 ＝ items 数）。
  · `ap_no_po_link="divert"`（队列 #390）：无 PO 关联行分流留痕，否则一行打挂整批。
    分流条数**如实打印**，不静默。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, _HERE.parent.parent)  # noqa: E402

from zhuopin_platform.env_anchor import load_env as _resolve_and_load_env  # noqa: E402

REQUIRED_ENV_KEYS: tuple[str, ...] = (
    "U9C_API_BASE", "U9C_USER_CODE", "U9C_ENT_CODE",
    "U9C_ORG_CODE", "U9C_CLIENT_ID", "U9C_CLIENT_SECRET",
)

#: 2026-08-24 基线（唐燕萍补件《R5分母全量实测》第五节），用于逐档打差值。
BASELINE = {"完全匹配": 2497, "无发票支撑": 883, "数量金额不符": 204, "金额微差": 1}


def _ap_nos_from_invoice_csv(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return sorted({(r.get("ap_no") or "").strip()
                       for r in csv.DictReader(f) if (r.get("ap_no") or "").strip()})


def main() -> int:
    ap = argparse.ArgumentParser(description="#418 第③件全量重跑（只读）")
    ap.add_argument("--invoice-dir", required=True,
                    help="含 invoice.csv 的目录（传给 FeedSource 的 invoice_sample_dir）")
    ap.add_argument("--label", default="", help="本次跑动的标签，只用于打印")
    ap.add_argument("--ap-nos-from", default=None,
                    help="AP 取数范围改从**另一份** invoice.csv 取（做 like-for-like 对比："
                         "AP 范围钉死不变，只换发票侧，把发票侧的变化单独隔出来）")
    ap.add_argument("--dump", default=None, help="把逐项判定落一份本地 JSON（供两次跑动 diff）")
    args = ap.parse_args()

    print(_resolve_and_load_env(__file__, required=REQUIRED_ENV_KEYS).describe())

    from fi2.feed_source import FeedSource, partition_invoices
    from fi2.result_classify import classify_all
    from zhuopin_platform.audit.sinks import JsonlSink
    from zhuopin_platform.shared_tools.connector_audit import ConnectorAudit
    from zhuopin_platform.shared_tools.erp_connector import ZpConnector

    invoice_dir = Path(args.invoice_dir).resolve()
    scope_csv = Path(args.ap_nos_from).resolve() if args.ap_nos_from else invoice_dir / "invoice.csv"
    ap_nos = _ap_nos_from_invoice_csv(scope_csv)
    print(f"\n══ 跑动「{args.label or invoice_dir.name}」══")
    print(f"  发票目录        : {invoice_dir}")
    print(f"  AP 取数范围来自  : {scope_csv}")
    print(f"  AP 单数（取数范围）: {len(ap_nos)}")

    reports = _HERE.parent.parent / "reports"
    reports.mkdir(exist_ok=True)
    conn = ZpConnector.from_env(
        audit=ConnectorAudit(sink=JsonlSink(reports / "fi2_access_trace.jsonl")))

    fs = FeedSource("u9c", u9c_connector=conn, ap_doc_nos=ap_nos,
                    invoice_sample_dir=invoice_dir, ap_no_po_link="divert")
    ap_lines = fs.load_ap_lines()
    invoice_rows = fs.load_invoice()
    linked, orphaned = partition_invoices(ap_lines, invoice_rows)
    items = classify_all(ap_lines, linked)

    dist = Counter(it.classification for it in items)
    print(f"  AP 明细行        : {len(ap_lines)}"
          f"（无 PO 关联被分流 {len(fs.ap_no_po_link_rows)} 行）")
    print(f"  发票行          : {len(invoice_rows)}  可挂上 {len(linked)} / 孤立 {len(orphaned)}")
    print(f"  料品项（items）  : {len(items)}")
    print("\n  判定档            本次    2026-08-24 基线    差")
    print("  " + "-" * 48)
    for cls in ("完全匹配", "无发票支撑", "数量金额不符", "金额微差"):
        now, base = dist.get(cls, 0), BASELINE[cls]
        print(f"  {cls:<12}{now:>8}{base:>16}{now - base:>+8}")
    other = {k: v for k, v in dist.items() if k not in BASELINE}
    if other:
        print(f"  ⚠️ 基线之外的档: {other}")
    n_review = sum(1 for it in items if it.needs_review)
    print(chr(10) + f"  needs_review     : {n_review}"
          "   ⚠️ 仅五类判定口径，**不含 R7 单价超差的合并**"
          "（R7 在 recon_report 层才并进来，见 result_classify 模块 docstring）")
    print(f"  孤立发票另计     : {len(orphaned)} 行"
          "   ← 面板 KPI 会把这个数加进「项料品」总数与 BLOCK"
          "（webapp._report_page 749-750 行；队列 §四 #131 那个 3390 就是这么来的）")

    if args.dump:
        Path(args.dump).write_text(json.dumps(
            {"label": args.label, "ap_nos": len(ap_nos), "items": len(items),
             "dist": dict(dist), "orphaned": len(orphaned),
             "per_item": [{"ap_no": it.ap_no, "item_code": it.item_code,
                           "classification": it.classification} for it in items]},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  已落 dump: {args.dump}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
