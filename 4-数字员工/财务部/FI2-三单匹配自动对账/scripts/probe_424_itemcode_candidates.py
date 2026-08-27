"""#424 只读取证：摄取层 `resolve_item_code` 那道行匹配闸，各候选口径分别能捞回多少。

🔴 **只读**。只调 `AP/Query`（`get_ap_lines` / `get_ap_lines_by_invoice_no`）两个只读
端点，只**读** `--export-dir` 下的 xlsx 与 `--invoice-csv`。**不写 `invoice.csv`、不写
ledger、不碰生产任何文件**；产出只有 stdout ＋ `--dump` 指定的一份本地 JSON。

回答的是队列 #424 里那句「放宽到什么程度分别能捞回多少张」——两条轴分开量，因为它们
的答案很可能相反：

  · **轴 A：放宽容差**（`_QTY_REL_TOL`／`_PRICE_REL_TOL`）——不换钥匙，只把锁放松。
  · **轴 B：换匹配键**（⒜ 金额／⒝ 单料号回落／⒞ 组合求和）——换一把钥匙。

🔑 **为什么必须两条轴都量**：唐燕萍四组举证里那两组失败案，一组是「20 支 × 310ML ＝
6200」的**计量单位换算**（数量差 310 倍），一组是「发票按合计开票、AP 按行拆分」——
**两者都不是浮点噪声**。若实测证实轴 A 收成接近 0，那么「先把容差调大一点看看」这条
最省事的路就该当场排除，而不是先试一轮再说。

━━━ 两种跑法（成本差一个数量级，先跑第一种）━━━

**① 复用模式（默认，`--reuse-ap-no-only`）**：`ap_no` 只从 `--invoice-csv` 的
`inv_no → ap_no` 反推 —— 一张发票只要有**任意一行**曾摄取成功，它的 `ap_no` 就是已知
的，而它**其余那些被行匹配闸挡掉的行**正是本次要量的对象。网络调用只剩「按 ap_no 取
AP 明细」（数百次、带缓存）。
🔴 **覆盖面必须如实说**：这条路量不到「整张发票一行都没进过库」的那些（#418 ⑺ 实测
421 张里有 221 张属此类）。**故本模式的数是一个下界，不是全量**，输出里会明写。

**② 全量模式（`--resolve-ap-no`）**：对导出文件里每一个数电发票号码都真反查一次
`ap_no`（#418 ⑺ 实测约 1.5 万张），覆盖面完整但是数万次网络调用。缓存落 `--cache`
指定的 JSON，**可中断可续跑**。

用法（在 `.51` 本机跑，数据不出机器）：
    python scripts/probe_424_itemcode_candidates.py \\
        --export-dir D:\\airead --invoice-csv C:\\fi2\\app\\data\\tax_export\\invoice.csv \\
        --dump C:\\fi2\\_probe424\\out.json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
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

#: 轴 A：容差放宽档位（(数量相对容差, 含税单价相对容差)）。第一档＝现值。
_TOL_LADDER: tuple[tuple[float, float], ...] = (
    (1e-6, 1e-4),   # 现状
    (1e-4, 1e-3),
    (1e-3, 1e-2),
    (1e-2, 1e-2),
    (5e-2, 5e-2),   # ±5%，已远超任何「浮点噪声」的合理解释
)

#: 轴 B：换匹配键的候选（逐条对应队列 #424 的 ⒜⒝⒞）。
_STRATEGIES: tuple[str, ...] = (
    "qty_price",                    # 现状，作对照组
    "qty_price_then_amount",        # ⒜
    "qty_price_then_single_item",   # ⒝
    "qty_price_then_subset_sum",    # ⒞
)


def _load_env() -> None:
    print(_resolve_and_load_env(__file__, required=REQUIRED_ENV_KEYS).describe())


def _invoice_csv_index(path: Path) -> tuple[dict[str, str], dict[str, int]]:
    """`invoice.csv` → (`inv_no → ap_no`, `inv_no → 已入库行数`)。只读。"""
    ap_of: dict[str, str] = {}
    rows_of: dict[str, int] = defaultdict(int)
    if not path.is_file():
        return ap_of, dict(rows_of)
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            inv = str(row.get("inv_no") or "").strip()
            if not inv:
                continue
            ap_of.setdefault(inv, str(row.get("ap_no") or "").strip())
            rows_of[inv] += 1
    return ap_of, dict(rows_of)


def main() -> int:  # noqa: C901 —— 探针，线性流程，拆开反而更难对着输出读
    _load_env()
    ap = argparse.ArgumentParser(description="#424 item_code 匹配闸候选口径影响面（只读）")
    ap.add_argument("--export-dir", required=True, help="税务导出 Excel 目录（如 D:\\airead）")
    ap.add_argument("--invoice-csv", required=True, help="生产 invoice.csv（只读）")
    ap.add_argument("--cache", default=None, help="ap_no 反查缓存 JSON（可中断续跑）")
    ap.add_argument("--dump", default=None, help="逐行候选判定落一份本地 JSON")
    ap.add_argument("--resolve-ap-no", action="store_true",
                     help="全量模式：对每个数电发票号码真反查 ap_no（数万次调用）")
    ap.add_argument("--max-ap-no-lookups", type=int, default=0,
                     help="全量模式下本次最多做多少次 ap_no 反查（0＝不限，配合 --cache 分次跑完）")
    args = ap.parse_args()

    from fi2.tax_export_ingest import (
        _AMOUNT_ABS_TOL,
        _f,
        _match_by_amount,
        _match_by_subset_sum,
        _parse_tax_rate,
        _single_item_code,
        parse_export_workbook,
        resolve_ap_no,
        resolve_item_code,
    )
    from zhuopin_platform.audit.sinks import JsonlSink
    from zhuopin_platform.shared_tools.connector_audit import ConnectorAudit
    from zhuopin_platform.shared_tools.erp_connector import ZpConnector

    reports_dir = _HERE.parent.parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    # IATF 可追溯：连接器访问必须留痕，只读探针也不例外。
    conn = ZpConnector.from_env(
        audit=ConnectorAudit(sink=JsonlSink(reports_dir / "fi2_access_trace.jsonl")))

    export_dir = Path(args.export_dir)
    ap_of_inv, rows_in_csv = _invoice_csv_index(Path(args.invoice_csv))
    print(f"生产 invoice.csv：{len(ap_of_inv)} 张发票 / {sum(rows_in_csv.values())} 行（只读）")

    cache_path = Path(args.cache) if args.cache else None
    ap_cache: dict[str, str] = {}
    if cache_path and cache_path.is_file():
        ap_cache = json.loads(cache_path.read_text(encoding="utf-8"))
        print(f"ap_no 缓存已载入：{len(ap_cache)} 条")

    # ── ① 解析全部导出文件（离线）────────────────────────────────────────
    all_rows: list[tuple[str, int, dict]] = []
    for p in sorted(export_dir.glob("*.xlsx")):
        try:
            rows = parse_export_workbook(p)
        except ValueError as e:
            print(f"  ⚠️ 解析失败（如实记账，不跳过统计）：{p.name} —— {e}")
            continue
        all_rows.extend((p.name, idx, raw) for idx, raw in enumerate(rows, start=2))
    print(f"导出明细行总数：{len(all_rows)}（{len(set(f for f, _, _ in all_rows))} 份文件）")

    # ── ② 定 ap_no ───────────────────────────────────────────────────────
    lookups = 0
    t0 = time.time()
    resolved_ap: dict[str, str] = {}
    for _f_name, _idx, raw in all_rows:
        digital_no = str(raw.get("数电发票号码") or "").strip()
        if not digital_no or digital_no in resolved_ap:
            continue
        if digital_no in ap_of_inv:
            resolved_ap[digital_no] = ap_of_inv[digital_no]        # 免费：已入库行反推
            continue
        if digital_no in ap_cache:
            if ap_cache[digital_no]:
                resolved_ap[digital_no] = ap_cache[digital_no]
            continue
        if not args.resolve_ap_no:
            continue
        if args.max_ap_no_lookups and lookups >= args.max_ap_no_lookups:
            continue
        ap_no, _reason, _detail = resolve_ap_no(conn, digital_no)
        lookups += 1
        ap_cache[digital_no] = ap_no or ""
        if ap_no:
            resolved_ap[digital_no] = ap_no
        if cache_path and lookups % 200 == 0:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(ap_cache, ensure_ascii=False), encoding="utf-8")
            print(f"    ...ap_no 反查 {lookups} 次，用时 {time.time() - t0:.0f}s（缓存已存盘）")
    if cache_path and lookups:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(ap_cache, ensure_ascii=False), encoding="utf-8")
    print(f"可定 ap_no 的发票：{len(resolved_ap)} 张"
          f"（本次新做 {lookups} 次反查，用时 {time.time() - t0:.0f}s）")
    if not args.resolve_ap_no:
        print("  ⚠️ 复用模式：ap_no 只来自已入库行反推 ⇒ **量不到「整张发票一行都没进过库」的那些**"
              "（#418 ⑺ 实测 421 张里有 221 张属此类）。下面的数是**下界**，不是全量。")

    # ── ③ 取 AP 明细（按 ap_no 缓存）──────────────────────────────────────
    need_aps = sorted({resolved_ap[d] for d in resolved_ap})
    ap_lines: dict[str, list[dict]] = {}
    t1 = time.time()
    for i, ap_no in enumerate(need_aps, 1):
        ap_lines[ap_no] = conn.get_ap_lines(ap_no)
        if i % 100 == 0:
            print(f"    ...AP 明细 {i}/{len(need_aps)}，用时 {time.time() - t1:.0f}s")
    print(f"已取 AP 明细：{len(ap_lines)} 张单，用时 {time.time() - t1:.0f}s")

    # ── ④ 逐行跑两条轴 ───────────────────────────────────────────────────
    tol_rows = {tol: 0 for tol in _TOL_LADDER}
    tol_invs: dict[tuple, set[str]] = {tol: set() for tol in _TOL_LADDER}
    strat_rows = {s: 0 for s in _STRATEGIES}
    strat_invs: dict[str, set[str]] = {s: set() for s in _STRATEGIES}
    strat_amb: dict[str, int] = {s: 0 for s in _STRATEGIES}
    dropped_rows = 0
    dropped_invs: set[str] = set()
    dropped_aps: set[str] = set()
    shape: dict[str, int] = defaultdict(int)
    dump: list[dict] = []

    for file_name, idx, raw in all_rows:
        digital_no = str(raw.get("数电发票号码") or "").strip()
        ap_no = resolved_ap.get(digital_no)
        if not ap_no:
            continue
        rows = ap_lines.get(ap_no) or []
        qty = float(raw.get("数量") or 0)
        unit_price = float(raw.get("单价") or 0)
        tax_rate = _parse_tax_rate(raw.get("税率"))
        untaxed_amount = _f(raw.get("金额"))
        tax_amount = _f(raw.get("税额"))
        kw = dict(qty=qty, untaxed_unit_price=unit_price, tax_rate=tax_rate,
                   untaxed_amount=untaxed_amount, tax_amount=tax_amount)

        code_now, reason_now, _d = resolve_item_code(rows, strategy="qty_price", **kw)
        if code_now is not None:
            continue    # 现状口径已能解开，不是本次要量的对象
        dropped_rows += 1
        dropped_invs.add(digital_no)
        dropped_aps.add(ap_no)

        # 轴 A：容差
        for tol in _TOL_LADDER:
            c, _r, _dd = resolve_item_code(
                rows, strategy="qty_price", qty_rel_tol=tol[0], price_rel_tol=tol[1], **kw)
            if c is not None:
                tol_rows[tol] += 1
                tol_invs[tol].add(digital_no)

        # 轴 B：换键
        row_dump = {"file": file_name, "row_index": idx, "inv_no": digital_no,
                     "ap_no": ap_no, "reason_now": reason_now,
                     "ap_line_count": len(rows), "solved_by": []}
        for s in _STRATEGIES:
            c, r, _dd = resolve_item_code(rows, strategy=s, **kw)
            if c is not None:
                strat_rows[s] += 1
                strat_invs[s].add(digital_no)
                row_dump["solved_by"].append(s)
            elif r == "item_code_ambiguous":
                strat_amb[s] += 1

        # 形态分类（只看形状，不看金额——同 `_item_match_diagnosis` 的边界）
        if len(_match_by_amount(rows, untaxed_amount=untaxed_amount,
                                 tax_amount=tax_amount, abs_tol=_AMOUNT_ABS_TOL)) == 1:
            shape["金额唯一可解（计量单位/包装换算形态）"] += 1
        elif len(_single_item_code(rows)) == 1:
            shape["AP 单只有一个料号（可由单料号回落解开）"] += 1
        else:
            sub = _match_by_subset_sum(rows, qty=qty,
                                        taxed_unit_price=unit_price * (1 + tax_rate),
                                        price_rel_tol=1e-4)
            if len(sub) == 1:
                shape["组合求和唯一可解（同料号多行合计开票）"] += 1
            elif len(sub) > 1:
                shape["组合求和跨多料号（须接受发票行拆分才解得开）"] += 1
            else:
                shape["四种候选口径全都解不开"] += 1
        dump.append(row_dump)

    # ── ⑤ 输出 ───────────────────────────────────────────────────────────
    print("\n══ 现状口径挡掉的量（在本次可定 ap_no 的范围内）══")
    print(f"  行数 {dropped_rows} ／ 发票 {len(dropped_invs)} 张 ／ 涉 AP 单 {len(dropped_aps)} 张")
    csv_zero = sum(1 for i in dropped_invs if i not in rows_in_csv)
    print(f"  其中「该发票在生产 invoice.csv 里一行都没有」：{csv_zero} 张"
          "（面板此刻正把它们对应的 AP 单报成「无发票支撑」）")

    print("\n══ 轴 A：放宽容差能捞回多少 ══")
    for tol in _TOL_LADDER:
        tag = "（现状）" if tol == _TOL_LADDER[0] else ""
        print(f"  数量±{tol[0]:g} 单价±{tol[1]:g}{tag}："
              f"捞回 {tol_rows[tol]} 行 / {len(tol_invs[tol])} 张发票")

    print("\n══ 轴 B：换匹配键能捞回多少 ══")
    for s in _STRATEGIES:
        tag = "（现状，对照组，应为 0）" if s == "qty_price" else ""
        print(f"  {s}{tag}：捞回 {strat_rows[s]} 行 / {len(strat_invs[s])} 张发票"
              f"（另有 {strat_amb[s]} 行变成歧义、仍不入库）")

    print("\n══ 被挡掉的行都长什么样（形态分布）══")
    for k, v in sorted(shape.items(), key=lambda kv: -kv[1]):
        print(f"  · {k}：{v} 行")

    if args.dump:
        p = Path(args.dump)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(dump, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n逐行判定已落盘：{p}（{len(dump)} 行；不含金额与数量原始值以外的任何单据内容）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
