"""#131 只读取证：`AP/Query` 的 `docNo` 服务端过滤到底有没有收窄。

🔴 只读。不写 `invoice.csv`、不写 ledger、不碰 `.51` 上任何文件、不改任何生产数据。
仅调 `AP/Query` 一个只读端点（`get_ap_lines(doc_no)`，`_fi_query` 单查、不分页）。

要回答的唯一问题（队列 §四 #131）：真实 u9c 全量重算报「3390 项料品全 BLOCK」，
而筛选参数只有 `AP-2026080041` 一张 AP 单 —— 这个数不像单张单的行数。

判据（三条，逐条打印，不做推断）：
  ① 请求 `docNo=X` 返回的行里，`DocNo` 有几个不同值？**>1 即服务端没按 docNo 收窄**。
  ② 换一张 AP 单再请求一次，两次返回的行数/单号集合是否相同？**相同 ⇒ 参数被忽略**
     （只看 ①「有多个单号」还不够——也可能是它做了别的形式的匹配）。
  ③ 按 `(DocNo, ItemCode)` 去重的项数是多少？**能否复现 3390** —— 这是把
     `#131` 那个数字和本探针的观测钉在一起的唯一办法。

④ 第二段（`--repro-kpi <发票目录>`）：**原样复现**那次冒烟的面板 KPI —— 同一张 AP 单
   ＋ 同一份 `invoice.csv`，走 `webapp._report_page` 的同一套计数，看 3390/0/0/3390 是
   否原样出来。**这一段才是判定的依据**；①②③ 只是把「不是过滤失效」这条排掉。
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, _HERE.parent.parent)  # noqa: E402

from zhuopin_platform.env_anchor import load_env as _resolve_and_load_env  # noqa: E402

#: 判据＝`ZpConnector.from_env()` 自己那份 keys 清单（同 `probe_418_invoice_gap.py`）。
REQUIRED_ENV_KEYS: tuple[str, ...] = (
    "U9C_API_BASE", "U9C_USER_CODE", "U9C_ENT_CODE",
    "U9C_ORG_CODE", "U9C_CLIENT_ID", "U9C_CLIENT_SECRET",
)

#: 两张真实 AP 单：第一张＝`#131` 那次冒烟用的筛选参数；第二张＝`#418` 她四组取证里
#: 的另一张，用作 ② 的对照。两张都必须是真实存在的单，否则「返回一样多」无从解释。
PROBE_DOC_NOS = ["AP-2026080041", "AP-2026080137"]

#: 那次冒烟（`env-anchor-collapse` tasks 2.3.3，2026-08-27 02:37:39Z ＝ 10:37:39 本地）
#: 在表单里填的就是这一张，web access trace 里只有一次 `AP/Query?docNo=AP-2026080041`。
SMOKE_DOC_NO = "AP-2026080041"


def _load_env() -> None:
    print(_resolve_and_load_env(__file__, required=REQUIRED_ENV_KEYS).describe())


#: `--repro-kpi` 的解析结果（`__main__` 里赋值；不给该参数时第二段整段不跑）。
class _NoArgs:
    repro_kpi = None


_ARGS = _NoArgs()


def _summarize(rows: list[dict]) -> dict:
    doc_nos = [str(r.get("DocNo") or "") for r in rows]
    items = {(str(r.get("DocNo") or ""), str(r.get("ItemCode") or "")) for r in rows}
    return {"n_rows": len(rows), "doc_nos": set(doc_nos), "n_items": len(items)}


def _repro_kpi(conn, invoice_dir: Path) -> None:
    """复现面板 KPI：`webapp._report_page` 的四个数是怎么算出来的。"""
    import fi2.webapp as webapp
    from fi2.feed_source import FeedSource, partition_invoices
    from fi2.result_classify import classify_all

    fs = FeedSource("u9c", u9c_connector=conn, ap_doc_nos=[SMOKE_DOC_NO],
                    invoice_sample_dir=invoice_dir, ap_no_po_link="divert")
    ap_lines = fs.load_ap_lines()
    invoice_rows = fs.load_invoice()
    linked, orphaned = partition_invoices(ap_lines, invoice_rows)
    items = classify_all(ap_lines, linked)

    n_pass = sum(1 for it in items if it.status == "l3_suggested_pass")
    n_l2 = sum(1 for it in items if it.status == "l2_self_resolved")
    n_review = sum(1 for it in items if it.status == "needs_review")
    # 🔴 口径**不再在本文件重写一遍**（队列 #423 已把它收进 `webapp.kpi_counts` 单一入口）。
    # 原实现是把 `_report_page` 那两行逐字抄过来——那在当时是对的（要证明「面板就是这么
    # 算的」），但抄一份就多一处会漂移的口径；现在改成直接调它，复现与生产必然同源。
    rep = {"summary": {"total": len(items), "needs_review": n_review,
                        "l3_suggested_pass": n_pass, "l2_self_resolved": n_l2}}

    print(chr(10) + f"═══ ④ 原样复现那次冒烟的面板 KPI（docNo={SMOKE_DOC_NO}）═══")
    print(f"  发票目录            : {invoice_dir}")
    print(f"  引擎真正判定的料品项 : {len(items)}")
    for it in items:
        print(f"      → {it.ap_no} / {it.item_code} / has_invoice={it.has_invoice}"
              f" / {it.classification} / {it.status}")
    print(f"  孤立发票行           : {len(orphaned)}  ← 挂载的 ap_no 不在本次 AP 范围内")

    kpi = webapp.kpi_counts(rep, orphaned)      # 现行默认口径＝生产此刻的行为
    print("  ──面板 KPI（webapp.kpi_counts 现行默认口径）──")
    print(f"    本次共 {kpi['total_rows']} {kpi['total_label']}"
          f"   ＝ items {len(items)} ＋ 孤立发票 {len(orphaned)}")
    print(f"    ✅ 自动通过 {kpi['n_pass']}   ⚡ 微差消化 {kpi['n_l2']}"
          f"   🚫 BLOCK退回 {kpi['n_block']}  ＝ needs_review {n_review} ＋ 孤立发票 {len(orphaned)}")
    ok = (kpi["total_rows"] == 3390 and kpi["n_pass"] == 0
          and kpi["n_l2"] == 0 and kpi["n_block"] == 3390)
    print(f"  ⇒ {'与 #131 记的 0/0/3390、共 3390 项**逐个数字一致** ⇒ 复现成功' if ok else '与 #131 记的数字不一致 —— 须解释差在哪，不得当作复现'}")

    # ── 队列 #423：同一份真实数据下，三档口径分别显示成什么（供唐燕萍选）──────
    print(chr(10) + "  ══ 队列 #423 各候选口径在这同一份真实数据上的显示值 ══")
    for mode, tag in ((webapp._KPI_ORPHAN_COUNT_IN, "现状（2026-07-31 v8）"),
                       (webapp._KPI_ORPHAN_SEPARATE, "⒜ 孤立发票移出 KPI，单列一条"),
                       (webapp._KPI_ORPHAN_LABELED, "⒝ 仍计入，但文案如实、两部分分开显示")):
        k = webapp.kpi_counts(rep, orphaned, mode=mode)
        print(f"    · {tag}：本次共 {k['total_rows']} {k['total_label']}，"
              f"BLOCK {k['n_block']}，另标注孤立发票 {k['n_orphan']} 行")
    scoped = webapp.scope_invoice_rows(ap_lines, invoice_rows, scope="ap_range")
    linked_c, orphaned_c = partition_invoices(ap_lines, scoped)
    items_c = classify_all(ap_lines, linked_c)
    rep_c = {"summary": {
        "total": len(items_c),
        "needs_review": sum(1 for it in items_c if it.status == "needs_review"),
        "l3_suggested_pass": sum(1 for it in items_c if it.status == "l3_suggested_pass"),
        "l2_self_resolved": sum(1 for it in items_c if it.status == "l2_self_resolved")}}
    k = webapp.kpi_counts(rep_c, orphaned_c, mode=webapp._KPI_ORPHAN_COUNT_IN)
    print(f"    · ⒞ 只装载落在本次 AP 范围内的发票：装载 {len(scoped)} 行"
          f"（原 {len(invoice_rows)} 行），本次共 {k['total_rows']} {k['total_label']}，"
          f"BLOCK {k['n_block']}，孤立发票 {k['n_orphan']} 行")
    print("      ⚠️ ⒞ 的代价：真·孤立发票（数据完整性异常）此后与「不在本次范围内」"
          "一起被滤掉，两者不再可区分。")


def main() -> int:
    _load_env()
    from zhuopin_platform.audit.sinks import JsonlSink
    from zhuopin_platform.shared_tools.connector_audit import ConnectorAudit
    from zhuopin_platform.shared_tools.erp_connector import ZpConnector

    reports = _HERE.parent.parent / "reports"
    reports.mkdir(exist_ok=True)
    conn = ZpConnector.from_env(
        audit=ConnectorAudit(sink=JsonlSink(reports / "fi2_access_trace.jsonl")))

    summaries = {}
    for doc_no in PROBE_DOC_NOS:
        rows = conn.get_ap_lines(doc_no)
        s = _summarize(rows)
        summaries[doc_no] = s
        own = sum(1 for r in rows if str(r.get("DocNo") or "") == doc_no)
        print(f"\n═══ 请求 docNo={doc_no} ═══")
        print(f"  ① 返回行数            : {s['n_rows']}")
        print(f"     其中 DocNo=={doc_no} : {own}")
        print(f"     不同 DocNo 个数      : {len(s['doc_nos'])}"
              f"   ⇒ {'服务端未按 docNo 收窄' if len(s['doc_nos']) > 1 else '已收窄到单张单'}")
        print(f"     样例 DocNo（前 8）   : {sorted(s['doc_nos'])[:8]}")
        print(f"  ③ 去重 (DocNo,ItemCode) : {s['n_items']}"
              f"   {'← 与 #131 报的 3390 一致' if s['n_items'] == 3390 else ''}")

    a, b = PROBE_DOC_NOS[0], PROBE_DOC_NOS[1]
    same_n = summaries[a]["n_rows"] == summaries[b]["n_rows"]
    same_set = summaries[a]["doc_nos"] == summaries[b]["doc_nos"]
    print("\n═══ ② 两次请求对照 ═══")
    print(f"  行数相同 : {same_n}（{summaries[a]['n_rows']} vs {summaries[b]['n_rows']}）")
    print(f"  单号集合相同 : {same_set}")
    print(f"  ⇒ {'两张不同的单拿到同一批数据 ⇒ docNo 参数被服务端忽略' if same_n and same_set else '两次结果不同 ⇒ docNo 参数确有作用，需另找解释'}")

    if _ARGS.repro_kpi:
        _repro_kpi(conn, Path(_ARGS.repro_kpi).resolve())
    return 0


if __name__ == "__main__":
    import argparse
    _ap = argparse.ArgumentParser(description="#131 只读取证")
    _ap.add_argument("--repro-kpi", default=None,
                     help="含 invoice.csv 的目录；给了就跑第二段，原样复现那次冒烟的面板 KPI")
    _ARGS = _ap.parse_args()
    raise SystemExit(main())
