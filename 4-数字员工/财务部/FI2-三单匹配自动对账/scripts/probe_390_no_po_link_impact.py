"""#390 只读取证：`ap_supplier_codes` 批量真实全量跑通一次 ＋ ⒜／⒝ 两个候选口径的影响面量化。

🔴 **只读**。只调 `AP/Query`（`get_ap_lines_by_supplier`，经 `FeedSource.load_ap_lines()`）
一个只读端点，**不写 `invoice.csv`、不写 ledger、不碰生产任何文件**；产出只有 stdout ＋
`--dump` 指定的一份本地 JSON。

回答的是队列 #390 期望产出①③（②「不因单行失败而打挂整批」这一层与其单测已在
`fi2/feed_source.py::parse_ap_lines(no_po_link="divert")` 完成，本脚本不重做）：

  · **③ 批量模式真实全量验证**——`ap_supplier_codes` 驱动的批量取数至今零次在真实数据
    规模上跑过（本行 2026-08-24/08-26/08-27/08-28 历次会话均如实记录"仍未做"）。本脚本
    用 `ap_no_po_link="divert"` 实际跑一次 `FeedSource.load_ap_lines()`，证明"一行无 PO
    关联不再打挂整批"这件事在真实数据规模、真实脏数据分布下依然成立——不只是单测里
    构造的单行 fixture。若真实数据里还有**另一类**未预期的脏数据导致 fail-loud（本脚本
    未改 `parse_ap_lines` 对"真正脏数据"照旧报错的行为），会原样抛出并如实打印，
    **不吞、不静默重试**——那本身就是一个值得记的新发现，不是脚本故障。

  · **① ⒜／⒝ 两个候选口径的影响面**——队列 #390 原文：
      ⒜ 归为一类新的诊断留痕，该单其余行照常参与核对（＝现有 `"divert"` 模式的行为）；
      ⒝ 整单标记为「不适用三单核对」单列（该单**全部**行，含本来干净的那些，一并退出）；
      ⒞ 维持现状（批量模式实际不可用，已由③证伪其可行性，不需要再量）。
    ⒜ 的代价 = 被分流的行数本身；⒝ 的代价 = 这些行所在**全部单据**的**全部行数**
    （诊断行 + 该单其余本来正常的行）。**⒝ 恒 ≥ ⒜**，差值就是"⒝ 比 ⒜ 多排除多少本来
    干净的行"——这正是判例材料要交给唐燕萍看的那个数。**本脚本只量数字，不选口径。**

用法（在具备真实 U9C 凭据、可访问 `AP/Query` 的机器上跑，数据不出机器）：
    python scripts/probe_390_no_po_link_impact.py \\
        --supplier-codes SUP001,SUP002 \\
        --dump C:\\fi2\\_probe390\\out.json

🔴 供应商编码清单未内置默认值——本脚本不猜测生产要对账的供应商范围，调用方须显式传入
（同 `fi2/run.py --ap-supplier-codes` 的既有约定，见该文件）。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
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


def _load_env() -> None:
    print(_resolve_and_load_env(__file__, required=REQUIRED_ENV_KEYS).describe())


def _split_csv_arg(v: str | None) -> list[str] | None:
    if not v:
        return None
    return [s.strip() for s in v.split(",") if s.strip()]


def main() -> int:
    _load_env()
    ap = argparse.ArgumentParser(
        description="#390 无PO关联行——批量真实全量验证 + ⒜/⒝ 候选口径影响面（只读）")
    ap.add_argument("--supplier-codes", required=True,
                     help="供应商编码清单（逗号分隔），驱动 ap_supplier_codes 批量取数")
    ap.add_argument("--dump", default=None, help="逐单据影响面判定落一份本地 JSON")
    args = ap.parse_args()

    from fi2.feed_source import FeedSource
    from zhuopin_platform.audit.sinks import JsonlSink
    from zhuopin_platform.shared_tools.connector_audit import ConnectorAudit
    from zhuopin_platform.shared_tools.erp_connector import ZpConnector

    supplier_codes = _split_csv_arg(args.supplier_codes)
    reports_dir = _HERE.parent.parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    # IATF 可追溯：连接器访问必须留痕，只读探针也不例外（同 probe_424 惯例）。
    conn = ZpConnector.from_env(
        audit=ConnectorAudit(sink=JsonlSink(reports_dir / "fi2_access_trace.jsonl")))

    fs = FeedSource("u9c", u9c_connector=conn, ap_supplier_codes=supplier_codes,
                     ap_no_po_link="divert")

    print(f"供应商范围：{supplier_codes}")
    print("开始批量取数并解析（no_po_link='divert'）——"
          "若命中其它类别的脏数据仍会 fail-loud 中止，如实抛出，不吞。")
    lines = fs.load_ap_lines()   # 真实网络调用；"divert" 下不会因无 PO 关联而中止批量
    diverted = fs.ap_no_po_link_rows

    print(f"\n══ ③ 批量真实全量验证结果 ══")
    print(f"  批量加载**未中止**：{len(lines)} 行正常解析 ＋ {len(diverted)} 行分流（无 PO 关联）"
          f"，合计 {len(lines) + len(diverted)} 行——若无本脚本的 divert 修复，"
          f"现状 raise 默认值下任一分流行都会让这整批当场中止、零产出。")

    if not diverted:
        print("\n  本次批量范围内**零行**命中「无 PO 关联」——⒜/⒝ 在本次范围内无差异可量，"
              "如实记录，不外推到其它供应商范围。")
        if args.dump:
            Path(args.dump).write_text(json.dumps({
                "supplier_codes": supplier_codes, "total_rows": len(lines),
                "diverted_rows": 0, "affected_docs": [],
            }, ensure_ascii=False, indent=1), encoding="utf-8")
        return 0

    # ── ⒜/⒝ 影响面 ──────────────────────────────────────────────────────
    # 按 ap_no 汇总：该单一共多少行（正常 + 分流）、其中分流几行。
    rows_per_doc: dict[str, int] = defaultdict(int)
    diverted_per_doc: dict[str, int] = defaultdict(int)
    for line in lines:
        rows_per_doc[line.ap_no] += 1
    for row in diverted:
        rows_per_doc[row.ap_no] += 1
        diverted_per_doc[row.ap_no] += 1

    affected_docs = sorted(diverted_per_doc)     # 至少一行无 PO 关联的单据
    a_cost_rows = len(diverted)                                    # ⒜：只排除坏行本身
    b_cost_rows = sum(rows_per_doc[ap_no] for ap_no in affected_docs)  # ⒝：整单一并排除
    b_extra_over_a = b_cost_rows - a_cost_rows   # ⒝ 比 ⒜ 多排除多少本来干净的行

    total_docs = len({line.ap_no for line in lines} | set(affected_docs))

    print(f"\n══ ① ⒜/⒝ 候选口径影响面（同一份真实数据，本脚本不选口径）══")
    print(f"  涉及单据：{len(affected_docs)} / {total_docs} 张单命中「至少一行无 PO 关联」")
    print(f"  ⒜（只排除坏行本身，该单其余行照常参与核对）：排除 {a_cost_rows} 行")
    print(f"  ⒝（该单命中即整单退出核对）：排除 {b_cost_rows} 行"
          f"（其中 {b_extra_over_a} 行本身并无 PO 关联问题，是被同单里的坏行连带排除的）")
    if a_cost_rows:
        print(f"  ⇒ ⒝ 相对 ⒜ 多排除 {b_extra_over_a} 行，"
              f"放大倍数 ×{b_cost_rows / a_cost_rows:.2f}")

    # 单据级别的分布：每张受影响单据「脏行占比」——供她判断"这是整单几乎全脏"还是
    # "混了一两行脏的正常单"，两种形态对该不该整单排除的判断分量不同。
    print(f"\n══ 受影响单据的脏行占比分布 ══")
    for ap_no in affected_docs:
        total = rows_per_doc[ap_no]
        dirty = diverted_per_doc[ap_no]
        print(f"  {ap_no}：{dirty}/{total} 行无 PO 关联"
              f"（{dirty/total:.0%}）")

    if args.dump:
        p = Path(args.dump)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({
            "supplier_codes": supplier_codes,
            "total_rows": len(lines) + len(diverted),
            "total_docs": total_docs,
            "affected_docs": len(affected_docs),
            "option_a_rows_excluded": a_cost_rows,
            "option_b_rows_excluded": b_cost_rows,
            "option_b_extra_over_a": b_extra_over_a,
            "per_doc": [{"ap_no": ap_no, "total_rows": rows_per_doc[ap_no],
                        "diverted_rows": diverted_per_doc[ap_no]}
                       for ap_no in affected_docs],
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n逐单据影响面已落盘：{p}（不含金额/数量，同 FI2 审计脱敏口径）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
