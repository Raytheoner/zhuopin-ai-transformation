"""#418 只读取证：唐燕萍四组对照在**今天**的 U9C 里能不能反查得到。

🔴 只读。不写 invoice.csv、不写 ledger、不碰 `.51` 上任何文件。仅调用
`AP/Query`（`get_ap_lines_by_invoice_no` / `get_ap_lines`）两个只读端点。

判据：若某张发票**今天**能唯一反查到她所说的那张 AP 单，就证明 `resolve_ap_no`
当初的零命中是**时点问题**而非数据脏 —— 即队列 #418 的根因是「摄取期一次性判决 +
文件 SHA 锁进 ledger 后永不重试」，而修复（重试 pass）能把它捞回来。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, _HERE.parent.parent)  # noqa: E402

# 她 2026-08-26 回件表 1 的四组对照（AP 单号 / 数电发票号码 / 该发票所在导出文件）
EXHIBITS = [
    ("AP-2026080041", "26322000006465433531", "全量发票查询导出结果（20260801-20260817）"),
    ("AP-2026080137", "26322000003204358531", "全量发票查询导出结果（20260401-20260430）"),
    ("AP-2026080111", "26442000009515939266", "全量发票查询导出结果（20260819）"),
    ("AP-2026080110", "26322000003204768541", "全量发票查询导出结果（20260401-20260430）"),
]


def _load_env() -> None:
    for d in (_HERE.parent, *_HERE.parents):
        cand = d / ".env"
        if cand.exists():
            for line in cand.read_text(encoding="utf-8-sig").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            return


def main() -> int:
    _load_env()
    from fi2.tax_export_ingest import resolve_ap_no
    from zhuopin_platform.audit.sinks import JsonlSink
    from zhuopin_platform.shared_tools.connector_audit import ConnectorAudit
    from zhuopin_platform.shared_tools.erp_connector import ZpConnector

    # IATF 可追溯：连接器访问必须留痕，只读探针也不例外。
    reports = _HERE.parent.parent / "reports"
    reports.mkdir(exist_ok=True)
    conn = ZpConnector.from_env(
        audit=ConnectorAudit(sink=JsonlSink(reports / "fi2_access_trace.jsonl")))
    print(f"{'AP 单（她的取证）':<20} {'数电发票号码':<22} {'今天反查到的 AP 单':<20} 结论")
    print("-" * 110)
    hits = 0
    for ap_no_claimed, digital_no, src_file in EXHIBITS:
        try:
            resolved, reason, detail = resolve_ap_no(conn, digital_no)
        except Exception as e:  # noqa: BLE001
            print(f"{ap_no_claimed:<20} {digital_no:<22} {'<调用失败>':<20} {type(e).__name__}: {e}")
            continue
        if resolved is None:
            print(f"{ap_no_claimed:<20} {digital_no:<22} {'<零命中/歧义>':<20} {reason} {detail}")
            continue
        ok = resolved == ap_no_claimed
        hits += ok
        print(f"{ap_no_claimed:<20} {digital_no:<22} {resolved:<20} "
              f"{'✅ 与她的取证一致' if ok else '⚠️ 与她的取证不一致'}   源文件={src_file}")

        # item_code 侧也走一遍，确认整行确实可解（不只是 ap_no 解得开）
        try:
            ap_rows = conn.get_ap_lines(resolved)
            print(f"{'':<20} └─ 该 AP 单在 U9C 现有 {len(ap_rows)} 行明细"
                  f"（item_code 反查需导出 Excel 的数量/单价，本只读探针不读源文件，故到此为止）")
        except Exception as e:  # noqa: BLE001
            print(f"{'':<20} └─ get_ap_lines 失败：{type(e).__name__}: {e}")

    print("-" * 110)
    print(f"四组中今天可唯一反查到、且与她取证一致的：{hits}/4")
    if hits:
        print("⇒ 这些发票**当下**是解得开的。它们之所以不在 invoice.csv 里，只能是"
              "「摄取那一刻解不开、此后再没重试过」——即队列 #418 的根因。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
