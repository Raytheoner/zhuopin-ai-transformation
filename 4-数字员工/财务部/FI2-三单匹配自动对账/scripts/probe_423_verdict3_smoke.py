# -*- coding: utf-8 -*-
"""`#423` 判例 3／判例 4 部署后行为冒烟（只读，在 `.51` 本机跑）。

**为什么要有这个脚本**：`.51` 的面板挂着共享口令门禁（`simple_gate`），从笔记本用
curl POST `/run` 拿不到 200，冒烟就只能停在 `/api/ping`。而 `/api/ping` 证明的是
「服务活着」，**不是「档位切对了」**——后者才是唐燕萍这次要看的东西。本脚本在服务器
本机直接驱动**面板自己那条管线**（`webapp._run_with_detail`，与 HTTP 请求走的是同一个
函数），于是「筛一张单、看三个数」这件事不必绕过门禁也做得成。

🔴 **它跑的是生产代码 ＋ 生产数据，只读**：不写 `invoice.csv`、不写审计、不碰 ERP 写接口。
🔴 **只打印形状与计数，不打印任何金额** —— FI2 审计口径是金额不落盘，控制台输出会被
贴进队列行长期留存，不能成为金额的第二个出口。

用法（在 `.51` 上）：
    set "PYTHONIOENCODING=utf-8" && set "PYTHONUTF8=1" && ^
    C:\\fi2\\.venv\\Scripts\\python.exe C:\\fi2\\app\\scripts\\probe_423_verdict3_smoke.py
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

REQUIRED_ENV_KEYS = (
    "U9C_API_BASE", "U9C_USER_CODE", "U9C_ENT_CODE",
    "U9C_ORG_CODE", "U9C_CLIENT_ID", "U9C_CLIENT_SECRET",
)

#: 唐燕萍原始举证那张单——`#131`/`#418`/`#423` 一路用的都是它，换单就失去可比性。
SMOKE_DOC_NO = "AP-2026080041"


def main() -> int:
    print(_resolve_and_load_env(__file__, required=REQUIRED_ENV_KEYS).describe())

    from zhuopin_platform.shared_tools.erp_connector import ZpConnector

    import fi2.webapp as webapp

    conn = ZpConnector.from_env()
    invoice_dir, label = webapp._resolve_invoice_sample()
    print(f"\n发票源：{label or '（无）'}  目录={invoice_dir}")
    print(f"生效档位：_INVOICE_SCOPE={webapp._INVOICE_SCOPE!r}  "
          f"_KPI_ORPHAN_MODE={webapp._KPI_ORPHAN_MODE!r}")

    (rep, po_lines, ap_lines, linked, orphaned, price_results,
     _ap_real_line_no, invoice_pool) = webapp._run_with_detail(
        "u9c", u9c_connector=conn, ap_doc_nos=[SMOKE_DOC_NO],
        invoice_sample_dir=invoice_dir, evaluator="部署冒烟(只读)")

    kpi = webapp.kpi_counts(rep, orphaned)
    n_out = sum(1 for _, k in invoice_pool if k == "out_of_scope")
    n_orp = sum(1 for _, k in invoice_pool if k == "orphaned")

    print(f"\n═══ 筛 {SMOKE_DOC_NO} 一张单 · 面板 KPI 三个数 ═══")
    print(f"  本次共 {kpi['total_rows']} {kpi['total_label']}")
    print(f"  ✅ 自动通过 {kpi['n_pass']}   ⚡ 微差消化 {kpi['n_l2']}   "
          f"🚫 BLOCK退回 {kpi['n_block']}")
    print(f"  孤立发票（进 KPI 提示条的那个数）：{kpi['n_orphan']}")
    print(f"\n═══ 未匹配成功的发票池（判例 4：排除 ≠ 丢掉）═══")
    print(f"  池内共 {len(invoice_pool)} 行 ＝ 不在本次 AP 范围 {n_out} ＋ 孤立发票 {n_orp}")

    # 判据：三个数必须是「引擎真判过的那几项」，而不是整池发票的行数。
    ok_kpi = kpi["total_rows"] == len(rep["items"]) and kpi["n_orphan"] == 0
    # 判据：被排除的行必须还在池里查得到——这是唯一「错了她会丢数据」的一条。
    ok_pool = n_out > 0
    print(f"\n  ⇒ KPI 只反映真判定项：{'✅' if ok_kpi else '❌'}"
          f"（total_rows={kpi['total_rows']} items={len(rep['items'])} n_orphan={kpi['n_orphan']}）")
    print(f"  ⇒ 被排除的发票行仍在池中可检索：{'✅' if ok_pool else '❌'}（{n_out} 行）")
    if not (ok_kpi and ok_pool):
        print("  🔴 冒烟不通过 —— 按 docs/回滚SOP-423-424-判例3与认领口径-2026-09-07.md 回滚")
        return 1
    print("  ✅ 冒烟通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
