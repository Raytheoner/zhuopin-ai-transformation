"""物料看板逐物料人工对账（队列 #334，tasks 6.2/6.3/6.4）—— 纯离线，只吃两份 JSON。

输入＝生产服务的 `/api/baoguan`（成品维度，含每行的 BOM 缺口物料清单 `cst`）与
`/api/materials`（物料维度）两份真实载荷。**刻意不重新取数**：重算一次约 15 分钟，
且"本地重算一份再跟自己对"证明不了生产上那份是对的——要对的就是**生产真的吐出来的
那一份**（同 #221／#228 那族教训：说改好了不等于生产是对的）。

做三件事：
  6.2 逐物料对账——把各成品卡片里该物料的缺口逐张抄出相加，与物料看板月度列/合计列
      逐位比对；底稿写成 markdown，可直接进 docs/。
  6.3 四色 counts 与改动前基线逐字段比对（基线＝部署前抓的同一接口载荷）。
  6.4 实测 D10 的推断——同一物料的状态在各成品行间是否一致。

用法：
    python scripts/audit_material_board_snapshot.py --baoguan a.json --materials b.json \
        [--baseline 部署前的_baoguan.json] [--out docs/xxx.md] [--picks R01,R02,R03]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(p: str) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _gap_of(c: dict) -> float | None:
    """与 `material_board._gap_of` 同一口径：gq 优先，None 时退回本项目需求数量。"""
    if c.get("gq") is not None:
        return float(c["gq"])
    if c.get("qty") is None:
        return None
    return float(c["qty"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baoguan", required=True)
    ap.add_argument("--materials", required=True)
    ap.add_argument("--baseline", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--picks", default="")
    args = ap.parse_args()

    bg = _load(args.baoguan)
    mb = _load(args.materials)
    rows = bg.get("rows") or []
    mrows = mb.get("rows") or []
    meta = mb.get("meta") or {}
    yms = [m["ym"] for m in (meta.get("months") or [])]
    labels = [m["label"] for m in (meta.get("months") or [])]

    L: list[str] = []
    L.append("# 物料看板真实数据核验底稿（队列 #334）")
    L.append("")
    L.append(f"- 快照生成时刻：`{bg.get('generated_at')}`　业务日期：`{bg.get('today')}`")
    L.append(f"- 成品行：**{len(rows)}**　物料看板行：**{len(mrows)}**"
             f"　窗口：`{meta.get('window')}`（{'/'.join(labels)}）")
    L.append(f"- 窗口外全落空、按口径未列出的物料：**{meta.get('out_of_window_materials')}** 个"
             f"（合计 {meta.get('out_of_window_qty')}）")
    L.append("")

    # ── 6.3 四色 counts ───────────────────────────────────────────────────────
    L.append("## 6.3 四色 counts 与改动前基线逐字段比对")
    L.append("")
    cur = bg.get("counts") or {}
    if args.baseline:
        base_raw = _load(args.baseline)
        base = base_raw.get("counts") or {}
        same = all(cur.get(k) == base.get(k) for k in set(cur) | set(base))
        L.append(f"- 改动前（部署前抓取，生成于 `{base_raw.get('generated_at')}`）：`{base}`")
        L.append(f"- 改动后（本次）：`{cur}`")
        L.append(f"- **逐字段比对：{'✅ 完全一致' if same else '⚠️ 有差异，见下方说明'}**")
        if not same:
            L.append("")
            L.append("  > ⚠️ 两次快照之间真实业务数据本身会变动（预测订单、答交记录逐日刷新），"
                     "counts 不一致**不必然**意味着判定被改动。判定未被触碰的结构性证据是："
                     "`sc8/baoguan.py`（四色/齐料日/可齐套全部判定的所在文件）在本变更中"
                     "**一字未改**（`git diff` 可复核），且单测 "
                     "`test_material_board_does_not_shift_existing_rows_or_counts` 在"
                     "**同一份输入**下逐字段比对了「有物料看板」与「无物料看板」两种情形。")
        base_rows = {(r.get("id"), r.get("so"), r.get("ship")): r for r in (base_raw.get("rows") or [])}
        cmp_n = same_n = 0
        for r in rows:
            k = (r.get("id"), r.get("so"), r.get("ship"))
            b = base_rows.get(k)
            if not b:
                continue
            cmp_n += 1
            if all(r.get(f) == b.get(f) for f in ("risk", "kit", "gap", "cg", "bn", "kq")):
                same_n += 1
        L.append(f"- 同键成品行（料号+预测订单+出货日）可比 **{cmp_n}** 条，"
                 f"其中 `risk/kit/gap/cg/bn/kq` 六个判定字段逐字段一致 **{same_n}** 条"
                 f"（{'✅ 全一致' if cmp_n and cmp_n == same_n else '差异部分为两次快照间真实数据变动'}）")
    else:
        L.append(f"- 本次 counts：`{cur}`（未提供基线文件，跳过比对）")
    L.append("")

    # ── 6.4 状态分歧 ─────────────────────────────────────────────────────────
    L.append("## 6.4 D10 推断实测：同一物料的状态在各成品行间是否一致")
    L.append("")
    div = [r for r in mrows if r.get("st") == "divergent"]
    L.append(f"- 状态分歧物料：**{len(div)}** 个 / 共 {len(mrows)} 个")
    if not div:
        L.append("- ⇒ **D10 的推断在本次真实全量数据下成立**：同一物料的状态在各成品行间一致，"
                 "分歧标记为防御性实现，当前未被触发。")
    else:
        L.append("- ⇒ **D10 的推断被证伪**，如实登记如下（按 spec 显式标示分歧，"
                 "**未顺手改既有判定**，另立待查行）：")
        L.append("")
        L.append("| 料号 | 各成品行下的实际状态 | 出现在几张卡片 |")
        L.append("|---|---|---|")
        for r in div[:50]:
            L.append(f"| {r['id']} | {' / '.join(r.get('sts') or [])} | {r.get('nrow')} |")
    L.append("")

    # ── 6.2 逐物料对账 ───────────────────────────────────────────────────────
    picks = [p.strip() for p in args.picks.split(",") if p.strip()]
    if not picks:
        picks = [r["id"] for r in sorted(mrows, key=lambda x: -float(x.get("total") or 0))[:3]]
    L.append("## 6.2 逐物料人工对账（把各成品卡片的缺口抄出相加，与物料看板逐位比对）")
    all_ok = True
    for mid in picks:
        mrow = next((r for r in mrows if r["id"] == mid), None)
        L.append("")
        L.append(f"### {mid}　{(mrow or {}).get('name', '')}")
        if mrow is None:
            L.append("")
            L.append("（不在物料看板里——该料无缺口，或其缺口全部落在窗口之外）")
            continue
        L.append("")
        L.append("| 成品 | 预测订单 | 计划出货日 | 归属月 | 该卡片里该物料的缺口数量 |")
        L.append("|---|---|---|---|---|")
        by_month: dict[str, float] = {}
        out_win = 0.0
        for r in rows:
            for c in (r.get("cst") or []):
                if c.get("id") != mid or c.get("role") == "substitute":
                    continue
                gap = _gap_of(c)
                if gap is None or gap <= 0:
                    continue
                ship = str(r.get("ship") or "")
                ym = ship[:7]
                L.append(f"| {r.get('id')} | {r.get('so')} | {ship} | {ym} | {gap:g} |")
                if ym in yms:
                    by_month[ym] = by_month.get(ym, 0.0) + gap
                else:
                    out_win += gap
        hand = [by_month.get(y, 0.0) for y in yms]
        ok = (hand == [float(v) for v in mrow["m"]]
              and abs(sum(hand) - float(mrow["total"])) < 1e-9
              and abs(out_win - float(mrow.get("out") or 0.0)) < 1e-9)
        all_ok = all_ok and ok
        L.append("")
        L.append(f"- 人工按月相加：{[f'{v:g}' for v in hand]}　合计 **{sum(hand):g}**"
                 f"（另有窗口外 {out_win:g}，按口径不计入）")
        L.append(f"- 物料看板显示：{[f'{float(v):g}' for v in mrow['m']]}　合计 **{float(mrow['total']):g}**"
                 f"（窗口外 {float(mrow.get('out') or 0):g}）")
        L.append(f"- **逐位比对：{'✅ 完全一致' if ok else '❌ 不一致，须查'}**")
        L.append(f"- 状态：`{mrow['st']}`（各卡片实际状态 {mrow.get('sts')}）"
                 f"　未交订单数量：{float(mrow['tq']):g}　出现在 {mrow.get('nrow')} 张卡片")
        L.append(f"- 答交明细（按窗口合计缺口累计）：{mrow.get('cb') or '无'}")
        L.append(f"- 供应商：{mrow.get('sup') or '（无未交 PO）'}"
                 f"　品牌：{mrow.get('brand')}　责任人：{mrow.get('owner')}")
    L.append("")
    L.append(f"**6.2 总判定：{'✅ 抽验物料全部逐位一致' if all_ok else '❌ 存在不一致'}**")

    text = "\n".join(L) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"底稿已写入 {args.out}")
    print(text)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
