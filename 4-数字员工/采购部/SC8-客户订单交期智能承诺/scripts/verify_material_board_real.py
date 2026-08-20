"""物料看板真实数据核验 runner（队列 #334，tasks 6.1-6.4）—— 一次取数，两处核对。

为什么不直接调 `compute_snapshot`：本脚本要做的第一件事是**逐物料人工对账**（把各成品
卡片里该物料的缺口抄出来相加，与物料看板的月度列/合计列逐位比对）——那需要拿到
`build_dashboard` 输出的 `BaoguanRow` 对象本身，而 `compute_snapshot` 只吐序列化后的
dict。故本脚本原样复刻 `compute_snapshot` 的取数与调用序列（**逐行对照，不得漂移**），
把中间结果留在手上，再分别喂给两条路径核对。

一次全量取数约 15 分钟（携客云 SRM 1 req/30s 限流），**这一段会比较久，不是卡死**。

红线：含真实客户名/供应商名的产物只写 `reports/`（已 gitignore），绝不入库；
      对客闸 CUSTOMER_OUTBOUND_ENABLED 全程 False，本脚本不触发任何对客动作。

用法（仓库根 .env 提供凭据）：
    SC8_DATA_SOURCE=real python scripts/verify_material_board_real.py [--audit-materials A,B,C]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
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

SCENE = _HERE.parent.parent


def load_env() -> None:
    """从本脚本向上逐级找到最近的 `.env` 读入（布局无关）。凭据只在 .env，不入库、不打印。"""
    for d in [_HERE.parent, *_HERE.parents]:
        env = d / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8-sig").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            print(f"· .env 已读入：{env.parent.name}/.env（值不回显）")
            return
    print("✗ 未找到 .env", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-materials", default="",
                    help="逗号分隔的料号，逐物料人工对账明细（缺省＝自动取合计缺口最大的 3 个）")
    args = ap.parse_args()
    load_env()

    from sc8 import config
    if config.data_source_mode() != "real":
        print("✗ 需 SC8_DATA_SOURCE=real（红线 §7.1：真实库须显式开启）", file=sys.stderr)
        return 2

    from zhuopin_platform.audit import AuditLogger
    from zhuopin_platform.audit.sinks import JsonlSink
    from zhuopin_platform.shared_tools.connector_audit import ConnectorAudit

    reports = SCENE / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    trace = ConnectorAudit(sink=JsonlSink(reports / "baoguan_access_trace.jsonl"))
    audit = AuditLogger(sink=JsonlSink(reports / "baoguan_audit.jsonl"))

    from sc8.baoguan import (RISK_GAP, RISK_GREEN, RISK_RED, RISK_YELLOW,
                             build_dashboard)
    from sc8.baoguan_service import _prefetch_line_status
    from sc8.material_board import build_material_board
    from sc8.sources import (load_material_commitments,
                             load_purchase_orders_by_material,
                             load_purchase_supply_by_material, load_real_bom,
                             load_real_orders, load_srm_deliveries)

    today = date.today()
    fo_base = os.environ.get("FO_API_BASE")
    fo_status = os.environ.get("SC8_FO_STATUS", "2")
    fo_status = None if fo_status.lower() == "all" else fo_status

    print("① FO 预测订单…", flush=True)
    orders = load_real_orders(api_base=fo_base, audit=trace, status=fo_status)
    print(f"   {len(orders)} 条（status={fo_status or 'all'}）", flush=True)

    print("② U9C BOM 多层展开…", flush=True)
    product_ids = list(dict.fromkeys(o.item_code for o in orders))
    bom = load_real_bom(product_ids, max_depth=config.bom_max_depth(), audit=trace)
    sub_assembly_ids = {r.product_id for r in bom}
    components = {r.component_id for r in bom if r.component_id not in sub_assembly_ids}
    print(f"   成品 {len(product_ids)} 个 → 叶子件 {len(components)} 个（BOM 行 {len(bom)}）",
          flush=True)

    print("③ 携客云承诺交期（限流 1 req/30s，这一段最慢）…", flush=True)
    srm = load_srm_deliveries("real", materials=components, audit=trace)
    print(f"   命中 {len(srm)} / {len(components)}", flush=True)

    inventory = None
    if config.net_inventory_enabled():
        print("⑤ 现货净额…", flush=True)
        from zhuopin_platform.shared_tools.erp_connector import ZpConnector
        conn = ZpConnector.from_env(audit=trace)
        inventory = {r.material_id: r.current_stock
                     for r in conn.get_inventory(sorted(components))}
        print(f"   {len(inventory)} 个料号", flush=True)

    purchase_orders = None
    supply_by_material = None
    if config.po_transit_enabled():
        # 行级关闭状态预取一次、⑥⑧ 共用（与 compute_snapshot 同一手法；该查询按料号逐个
        # 打 ERP、无缓存，约 1600 次 HTTP／约 2 分钟，让物料看板再跑一遍就是白翻一倍）
        print("⑥₀ 采购订单行级关闭状态（⑥⑧ 共用，约 2 分钟）…", flush=True)
        line_status = _prefetch_line_status(components, audit=trace)
        print(f"   {len(line_status)} 条行级状态", flush=True)
        print("⑥ PO 在途未清量…", flush=True)
        purchase_orders = load_purchase_orders_by_material(
            components, audit=trace, line_status=line_status)
        print(f"   {len(purchase_orders)} 个料号有未交订单", flush=True)
        print("⑧ 未交 PO 供应商/制单人（物料看板新增，复用同一份行级状态）…", flush=True)
        supply_by_material = load_purchase_supply_by_material(
            components, audit=trace, line_status=line_status)
        print(f"   {len(supply_by_material)} 个料号有供应商信息", flush=True)

    print("⑦ 物料逐笔答交承诺…", flush=True)
    material_commitments = load_material_commitments("real", materials=components)
    print(f"   {len(material_commitments)} 个料号有答交记录", flush=True)

    # ── 既有判定（本变更一字未动 `sc8/baoguan.py`，可用 git diff 复核）────────────
    rows = build_dashboard(orders, bom, srm, today=today, inventory=inventory,
                           purchase_orders=purchase_orders,
                           material_commitments=material_commitments)
    counts = {"red": sum(1 for r in rows if r.risk == RISK_RED),
              "gap": sum(1 for r in rows if r.risk == RISK_GAP),
              "yel": sum(1 for r in rows if r.risk == RISK_YELLOW),
              "grn": sum(1 for r in rows if r.risk == RISK_GREEN)}
    print(f"\n【6.3】四色 counts（由未改动的 build_dashboard 直接产出）：{counts}")

    # ── 物料看板派生 ────────────────────────────────────────────────────────────
    board = build_material_board(rows, today=today, commitments=material_commitments,
                                 supply_by_material=supply_by_material)
    print(f"【6.1】物料看板：{len(board.rows)} 个缺料物料"
          f"　窗口 {board.meta()['window']}"
          f"　窗口外全落空的物料 {board.out_of_window_materials} 个"
          f"（合计 {board.out_of_window_qty:g}）")

    # ── 6.4：实测 D10 的推断（同一物料的状态在各成品行间是否一致）────────────────
    divergent = [r for r in board.rows if r["st"] == "divergent"]
    print(f"【6.4】状态分歧物料：{len(divergent)} 个"
          + ("（D10 推断成立：全量下同一物料状态在各成品行间一致）" if not divergent else ""))
    for r in divergent[:20]:
        print(f"        · {r['id']}  {r['sts']}  出现在 {r['nrow']} 张卡片")

    # ── 6.2：逐物料人工对账底稿 ─────────────────────────────────────────────────
    picks = [m.strip() for m in args.audit_materials.split(",") if m.strip()]
    if not picks:
        picks = [r["id"] for r in board.rows[:3]]
    audit_lines: list[str] = []
    for mid in picks:
        mrow = next((r for r in board.rows if r["id"] == mid), None)
        audit_lines.append(f"\n### {mid}　{(mrow or {}).get('name', '')}")
        if mrow is None:
            audit_lines.append("（不在物料看板里——该料无缺口，或缺口全部落在窗口之外）")
            continue
        audit_lines.append("")
        audit_lines.append("| 成品 | 预测订单 | 计划出货日 | 归属月 | 该卡片里该物料的缺口数量 |")
        audit_lines.append("|---|---|---|---|---|")
        by_month: dict[str, float] = {}
        out_win = 0.0
        yms = [m.ym for m in board.months]
        for r in rows:
            for c in r.component_status:
                if c.component_id != mid or c.role == "substitute":
                    continue
                gap = c.gap_qty if c.gap_qty is not None else c.qty_needed
                if gap is None or gap <= 0:
                    continue
                ym = f"{r.ship_date.year:04d}-{r.ship_date.month:02d}"
                audit_lines.append(
                    f"| {r.product_id} | {r.so_id} | {r.ship_date.isoformat()} | {ym} | {gap:g} |")
                if ym in yms:
                    by_month[ym] = by_month.get(ym, 0.0) + gap
                else:
                    out_win += gap
        hand = [by_month.get(y, 0.0) for y in yms]
        audit_lines.append("")
        audit_lines.append(f"- 人工按月相加：{[f'{v:g}' for v in hand]}　合计 {sum(hand):g}"
                           f"（另有窗口外 {out_win:g}，按口径不计入）")
        audit_lines.append(f"- 物料看板显示：{[f'{v:g}' for v in mrow['m']]}　合计 {mrow['total']:g}"
                           f"（窗口外 {mrow['out']:g}）")
        ok = (hand == list(mrow["m"])) and abs(sum(hand) - mrow["total"]) < 1e-9 \
            and abs(out_win - mrow["out"]) < 1e-9
        audit_lines.append(f"- **逐位比对：{'✅ 完全一致' if ok else '❌ 不一致，须查'}**")
        audit_lines.append(f"- 状态：{mrow['st']}（各卡片实际状态 {mrow['sts']}）"
                           f"　未交订单数量：{mrow['tq']:g}")
        audit_lines.append(f"- 答交明细（按三月合计缺口累计）：{mrow['cb'] or '无'}")
        audit_lines.append(f"- 供应商：{mrow['sup'] or '（无未交 PO，取数缺口）'}"
                           f"　品牌：{mrow['brand']}　责任人：{mrow['owner']}")
        audit_lines.append(f"- 〔仅供排障，不上页面〕未交 PO 制单人：{mrow['buyers']}")
    print("\n".join(audit_lines))

    # ── 产出落 reports/（含真实客户名/供应商名，git-ignored）────────────────────
    from sc8.baoguan import row_to_dict
    from sc8.baoguan_service import Snapshot
    from datetime import datetime
    snap = Snapshot(generated_at=datetime.now().isoformat(timespec="seconds"),
                    today=today.isoformat(), rows=[row_to_dict(r) for r in rows],
                    counts=counts, status=fo_status, param_version=config.PARAM_VERSION,
                    components=len(components), srm_hit=len(srm),
                    materials=board.rows, materials_meta=board.meta())
    out = reports / "baoguan_snapshot.json"
    out.write_text(json.dumps(snap.to_dict(), ensure_ascii=False), encoding="utf-8")
    print(f"\n· 快照已写入 {out}（git-ignored）")
    (reports / "material_board_audit_raw.md").write_text(
        "\n".join(audit_lines), encoding="utf-8")
    from zhuopin_platform.audit import AuditEvent
    audit.record(AuditEvent(
        scenario="SC8", action="material_board_real_verify", evaluator="system",
        automation_level="L1",
        decision={"rows": len(rows), **counts, "materials": len(board.rows),
                  "divergent": len(divergent),
                  "out_of_window_materials": board.out_of_window_materials},
        data_sources={"fo": "real", "bom": "real", "srm_committed": "real"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
