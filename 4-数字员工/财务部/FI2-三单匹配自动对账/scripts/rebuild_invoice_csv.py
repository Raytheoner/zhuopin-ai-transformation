"""按发票号重建 `invoice.csv`，清除跨文件重复行（队列 #371，2026-08-24）。

为什么需要这个脚本 —— **重跑修不好这个错**
─────────────────────────────────────────
唐燕萍 2026-08-21 举证面板发票数字翻倍，她自己的归因是「共享目录里有重复文件」，
并已把重复文件删掉、请我方重跑。**但重跑不解决问题**，三条实测坐实：

  ⑴ 重复行**早已写进** `invoice.csv`（`write_invoice_csv` 是追加写）；
  ⑵ 被删那份文件的 SHA256 **仍在** `.processed_exports.json` 里，重跑只会 skip；
  ⑶ 故重跑后面板依旧翻倍 —— 她会第二次看到同一个错。

`tax_export_ingest` 已加发票级幂等闸（防**再次**发生），但它管不了**已经在库里**
的那 706 组重复。本脚本就是把存量清掉的那一次性动作。

怎么判断哪一行是重复的 —— **不看行内容，看它来自哪个文件**
──────────────────────────────────────────────────────────
🔴 **按行内容去重会删掉合法数据**：真实数据里同一张发票出现同料品、同数量、同单价
的多行是合法的（实测 `26942000000588188581` 单张发票 60 行、其中一组签名重复 6 次，
全部来自同一份源文件）。

正确判据＝**同一张发票是否被两份不同的源文件各贡献了一次**。`invoice.csv` 本身没有
「来源文件」列，但可以精确重建出来：`write_invoice_csv` 按文件处理顺序追加，
`.processed_exports.json` 逐文件记了 `row_count` 与 `processed_at`
⇒ 按 `(processed_at, 文件名)` 排序后累加 `row_count`，即可把每一行切回它的源文件。

**这个重建不是推测，本脚本会当场验证它**：对每一份仍在盘上的源文件，重建出的那一段
里每个发票号的行数**必须 ≤** 该源文件里该发票号的真实行数。2026-08-24 在 `.51` 实测
17/17 份文件全部通过、0 违例，累加行数与 CSV 行数精确相等（3409）。

三道安全闸（任一不过即中止，不写任何文件）
──────────────────────────────────────────
  ① **累加校验**：ledger 各文件 `row_count` 之和必须等于 CSV 行数，否则归属重建
     不成立 —— 此时**中止**，不猜。
  ② **源文件比对**：仍在盘的源文件逐一验证（见上）；有违例即中止。
     `--skip-source-check` 可跳过（源文件已全部删除时），但会显式警告。
  ③ 🔴 **被删行必须是精确重复**：每一条拟删除的行，其全部字段必须与同发票号下被保留
     的某一行逐字段相同。**只要有一行不是精确重复就中止** —— 那意味着两份文件对同一
     张发票给出了**不同**的数字，那是另一个问题（源数据不一致），绝不能由本脚本按
     「留一个删一个」草草了事。

用法（在 `.51` 本机跑）：
    python scripts\\rebuild_invoice_csv.py --data-dir C:\\fi2\\app\\data\\tax_export
    python scripts\\rebuild_invoice_csv.py --data-dir ... --apply    # 真写盘

**默认是 dry-run**：不加 `--apply` 只报告将要发生什么，不动任何文件。
`--apply` 会先把原文件备份为 `invoice.csv.bak-<UTC时间戳>` 再覆盖，并把 ledger 各
文件的 `row_count` 同步改为去重后的实际贡献行数（否则再跑一次本脚本会因闸 ① 失败）。
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import shutil
import sys
from collections import OrderedDict
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

_ROOT = Path(__file__).resolve().parent.parent

_FIELDS = ["inv_no", "ap_no", "item_code", "unit", "unit_price",
           "inv_qty", "untaxed_amount", "tax_rate", "tax_amount", "inv_date"]


class RebuildAborted(RuntimeError):
    """安全闸未过——中止且不写任何文件。"""


def _row_sig(row: dict) -> tuple:
    return tuple(str(row.get(f, "")) for f in _FIELDS)


def partition_by_ledger(rows: list[dict], ledger: dict) -> list[tuple[str, list[dict]]]:
    """把 CSV 行切回「每个源文件贡献了哪一段」（见模块 docstring）。

    闸 ①：ledger 的 `row_count` 之和必须精确等于 CSV 行数，否则中止。

    ⚠️ **一份文件可能贡献不止一段**（队列 #418 未解析行重试：某文件此前未解开的行，
    后续批次解开后会追加到 `invoice.csv` 尾部，与它最初那段并不相邻）。故次序以
    ledger 条目的 `segments[].seq`（全局追加序号）为准；老 ledger 没有 `segments`
    时按原 `(processed_at, 文件名)` 次序补齐，与本字段引入前逐行等价。
    """
    entries = sorted(ledger.items(), key=lambda kv: (kv[1].get("processed_at", ""),
                                                     kv[1].get("file", "")))
    total = sum(int(v.get("row_count", 0)) for _h, v in entries)
    if total != len(rows):
        raise RebuildAborted(
            f"闸①未过：ledger row_count 合计 {total} ≠ invoice.csv 行数 {len(rows)}。"
            "归属重建不成立（ledger 与 CSV 已分叉），已中止、未写任何文件。"
        )

    # (seq, 文件名, 段行数) —— 老条目按 entries 次序补 seq，新条目用自己的 segments。
    segments: list[tuple[int, str, int]] = []
    fallback_seq = -len(entries)     # 保证补出来的 seq 全部排在真实 seq（≥0）之前
    for _h, v in entries:
        fname = v.get("file", "<unknown>")
        segs = v.get("segments") or []
        if segs:
            for s in segs:
                segments.append((int(s.get("seq", 0)), fname, int(s.get("row_count", 0))))
        else:
            segments.append((fallback_seq, fname, int(v.get("row_count", 0))))
        fallback_seq += 1
    segments.sort(key=lambda t: t[0])

    blocks: list[tuple[str, list[dict]]] = []
    cursor = 0
    for _seq, fname, n in segments:
        blocks.append((fname, rows[cursor:cursor + n]))
        cursor += n
    return blocks


def verify_against_sources(blocks, export_dir: Path) -> tuple[int, int]:
    """闸 ②：仍在盘的源文件逐一验证归属重建（见模块 docstring）。返回 (已验, 已跳过)。"""
    from fi2.tax_export_ingest import parse_export_workbook

    disk = {p.name: p for p in export_dir.glob("*.xlsx")} if export_dir.is_dir() else {}
    checked = skipped = 0
    cache: dict[str, dict | None] = {}
    for fname, seg in blocks:
        if fname not in disk:
            skipped += 1
            continue
        if fname not in cache:
            try:
                src = parse_export_workbook(disk[fname])
            except ValueError:
                cache[fname] = None
            else:
                counts: dict[str, int] = {}
                for r in src:
                    d = str(r.get("数电发票号码") or "").strip()
                    if d:
                        counts[d] = counts.get(d, 0) + 1
                cache[fname] = counts
        src_counts = cache[fname]
        if src_counts is None:
            skipped += 1
            continue
        seg_counts: dict[str, int] = {}
        for r in seg:
            seg_counts[r["inv_no"]] = seg_counts.get(r["inv_no"], 0) + 1
        for inv, n in seg_counts.items():
            if n > src_counts.get(inv, 0):
                raise RebuildAborted(
                    f"闸②未过：重建出的「{fname}」段里发票 {inv} 有 {n} 行，"
                    f"而该源文件里只有 {src_counts.get(inv, 0)} 行。"
                    "归属重建与源数据矛盾，已中止、未写任何文件。"
                )
        checked += 1
    return checked, skipped


def dedup_by_invoice(blocks) -> tuple[list[dict], list[tuple[str, dict]]]:
    """按「发票号首个文件胜出」去重。返回 (保留行, [(来源文件, 被删行)])。

    闸 ③：每条被删行必须与同发票号下某条被保留行逐字段相同，否则中止。
    """
    kept: list[dict] = []
    kept_sigs: dict[str, set] = {}
    dropped: list[tuple[str, dict]] = []
    seen_inv: set[str] = set()

    for fname, seg in blocks:
        by_inv: OrderedDict[str, list[dict]] = OrderedDict()
        for r in seg:
            by_inv.setdefault(r["inv_no"], []).append(r)
        for inv, rs in by_inv.items():
            if inv in seen_inv:
                for r in rs:
                    if _row_sig(r) not in kept_sigs.get(inv, set()):
                        raise RebuildAborted(
                            f"闸③未过：发票 {inv} 在「{fname}」里有一行与此前文件给出的"
                            f"任何一行都不逐字段相同（{dict(r)}）。两份源文件对同一张发票"
                            "给出了不同数字 —— 这不是简单重复，须人工核对，已中止、未写任何文件。"
                        )
                    dropped.append((fname, r))
            else:
                for r in rs:
                    kept.append(r)
                    kept_sigs.setdefault(inv, set()).add(_row_sig(r))
        seen_inv |= set(by_inv.keys())
    return kept, dropped


def main() -> int:
    ap = argparse.ArgumentParser(description="按发票号重建 invoice.csv（队列 #371）")
    ap.add_argument("--data-dir", default=str(_ROOT / "data" / "tax_export"),
                    help="invoice.csv 与 .processed_exports.json 所在目录")
    ap.add_argument("--export-dir", default="D:/airead", help="税务导出 Excel 源目录（闸②用）")
    ap.add_argument("--skip-source-check", action="store_true",
                    help="跳过闸②（源文件已全部删除时）——会显式警告")
    ap.add_argument("--apply", action="store_true", help="真写盘（默认 dry-run 只报告）")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    csv_path = data_dir / "invoice.csv"
    ledger_path = data_dir / ".processed_exports.json"

    if not csv_path.exists():
        print(f"invoice.csv 不存在：{csv_path}", file=sys.stderr)
        return 1
    if not ledger_path.exists():
        print(f"已处理清单不存在：{ledger_path}", file=sys.stderr)
        return 1

    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))

    print(f"invoice.csv 行数：{len(rows)}")
    print(f"已处理清单条目：{len(ledger)}")

    try:
        blocks = partition_by_ledger(rows, ledger)
        print(f"闸①通过：归属重建累加行数 == CSV 行数（{len(rows)}）")

        if args.skip_source_check:
            print("⚠️ 闸②已按 --skip-source-check 跳过——归属重建未经源文件交叉验证。")
        else:
            checked, skipped = verify_against_sources(blocks, Path(args.export_dir))
            print(f"闸②通过：{checked} 份源文件逐一验证 0 违例"
                  f"（另有 {skipped} 份文件已不在盘上/不可解析，无法验证）")

        kept, dropped = dedup_by_invoice(blocks)
        print(f"闸③通过：{len(dropped)} 条待删行全部是同发票号下的逐字段精确重复")
    except RebuildAborted as e:
        print(f"\n🔴 {e}", file=sys.stderr)
        return 1

    print()
    print(f"保留 {len(kept)} 行，删除 {len(dropped)} 行（重复发票）")
    dup_invs = sorted({r["inv_no"] for _f, r in dropped})
    print(f"涉及 {len(dup_invs)} 张重复发票")
    for inv in dup_invs[:20]:
        print(f"  {inv}")
    if len(dup_invs) > 20:
        print(f"  ...另有 {len(dup_invs) - 20} 张")

    if not dropped:
        print("\n无重复行，无需重建。")
        return 0

    if not args.apply:
        print("\n[dry-run] 未写任何文件。确认无误后加 --apply 执行。")
        return 0

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = csv_path.with_suffix(f".csv.bak-{stamp}")
    shutil.copy2(csv_path, backup)
    print(f"\n原文件已备份：{backup}")

    tmp = csv_path.with_suffix(".csv.tmp")
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_FIELDS)
        w.writeheader()
        for r in kept:
            w.writerow({k: r.get(k, "") for k in _FIELDS})
    tmp.replace(csv_path)
    print(f"已重建：{csv_path}（{len(kept)} 行）")

    # ledger 的 row_count 同步改为去重后的实际贡献行数——否则再跑一次本脚本会因闸①失败。
    dropped_per_file: dict[str, int] = {}
    for fname, _r in dropped:
        dropped_per_file[fname] = dropped_per_file.get(fname, 0) + 1
    if dropped_per_file:
        for _h, v in ledger.items():
            n = dropped_per_file.get(v.get("file", ""), 0)
            if n:
                v["row_count"] = max(0, int(v.get("row_count", 0)) - n)
        ledger_backup = ledger_path.with_suffix(f".json.bak-{stamp}")
        shutil.copy2(ledger_path, ledger_backup)
        ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2),
                               encoding="utf-8")
        print(f"已处理清单 row_count 已同步（备份：{ledger_backup}）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
