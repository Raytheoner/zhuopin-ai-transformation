# -*- coding: utf-8 -*-
"""SC8 真实内部验证 + 黄金基准生成器（任务：SRM 已通后内部真实验证）。

一键重跑：FO 恢复后执行本脚本，自动完成
  1. 拉真实 FO 订单 → 按三类（有反馈 / 无反馈 / 含委外）取样 5–10 张；
  2. 拉真实 U9C BOM + 真实 SRM 承诺交付（看板）；
  3. **冻结输入**到 data/golden/real_frozen/（FO/BOM/SRM 快照）→ 让回归确定性、离线可复跑；
  4. compute_forecasts（全链 audit，scenario=SC8，data_sources 按端点标 real/mock）；
  5. dispatch 路由——real 模式强制只入待审批队列、绝不外发（红线）；
  6. 产出人工交叉核对表 golden_expected_real.md（含全部中间量 + 留空手工/偏差列）
     + 机器可读 expected.json（回归断言基准）。

红线：CUSTOMER_OUTBOUND_ENABLED 全程关；real 缺真实端点 fail-loud；凭据只从 .env 读、不打印。
口径未决（等真实订单后定，见门禁 SOP §4.1）：① 置信度 2 级(高/低) vs SOP 3 级；
  ② SRM 承诺取数 = 看板(按物料) vs /purchase/answer(按 PO)。本脚本出引擎原生口径 + 全中间量,
  口径定了再叠加,不在此擅自改引擎语义。

用法：
  python scripts/build_golden_real.py                 # 真实 FO 全流程（FO 须在线）
  python scripts/build_golden_real.py --limit 8
  python scripts/build_golden_real.py --srm-mode mock # SRM 降级对照
  python scripts/build_golden_real.py --dry-run-products S02Y.0162,F02N.0184 --out-dir data/golden/_dryrun
        # FO 离线时验证脚本机理（合成订单壳，不写真实黄金目录）
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

# ── 路径与 .env 加载（连接器读 os.environ，无自动加载）──────────────────────────
HERE = Path(__file__).resolve()
SC8_DIR = HERE.parent.parent
REPO = SC8_DIR.parent.parent.parent
PLATFORM = REPO / "5-平台底座" / "zhuopin_platform"
for p in (str(PLATFORM), str(SC8_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)


def load_env() -> None:
    env = REPO / ".env"
    if not env.exists():
        raise SystemExit(f"缺少 .env：{env}（凭据须先迁入，见 U9C/SRM 凭据迁入待办）")
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def _asdict(obj) -> dict:
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return dict(obj.__dict__)


def categorize(product_id, bom, srm, demand_date, params, out_ids):
    """返回该成品的类别标签：no_bom / outsourced / partial_nofeedback / all_feedback。"""
    from sc8.config import is_outsourced
    from sc8.forecast import estimate_material_arrivals
    mat = estimate_material_arrivals(product_id, bom, srm, demand_date, params)
    outs = is_outsourced(product_id, product_ids=out_ids)
    if not mat.has_bom:
        return "no_bom", mat, outs
    if outs:
        return "outsourced", mat, outs
    if mat.no_feedback_materials:
        return "partial_nofeedback", mat, outs
    return "all_feedback", mat, outs


def select_sample(orders, bom, srm, params, out_ids, limit):
    """按三类覆盖取样（优先各类至少 1 张），不足 limit 用剩余补齐。确定性按 so_id 排序。"""
    from sc8.intake import aggregate_demand
    plans = aggregate_demand(orders)
    demand_by = {pl.product_id: date.fromisoformat(pl.planned_date) for pl in plans}
    by_cat = defaultdict(list)
    for so in sorted(orders, key=lambda o: o.so_id):
        if so.item_code not in demand_by:
            continue
        cat, _, _ = categorize(so.item_code, bom, srm, demand_by[so.item_code], params, out_ids)
        by_cat[cat].append(so)
    # 取样优先级：覆盖三类业务含义（有反馈/无反馈/委外），no_bom 兜底
    priority = ["all_feedback", "partial_nofeedback", "outsourced", "no_bom"]
    picked, seen = [], set()
    for cat in priority:                       # 先各类拿 1 张
        for so in by_cat.get(cat, []):
            if so.so_id not in seen:
                picked.append(so); seen.add(so.so_id); break
    for cat in priority:                       # 再补齐到 limit
        for so in by_cat.get(cat, []):
            if len(picked) >= limit:
                break
            if so.so_id not in seen:
                picked.append(so); seen.add(so.so_id)
    return picked[:limit], {c: len(v) for c, v in by_cat.items()}


def build(limit, srm_mode, out_dir, dry_products):
    from sc8 import config
    from sc8.config import default_params, is_outsourced
    from sc8.intake import aggregate_demand
    from sc8.forecast import estimate_material_arrivals
    from sc8.pipeline import compute_forecasts
    from sc8.sources import build_data_sources, load_real_bom, load_real_orders, load_srm_deliveries
    from sc8.dispatch import route_forecast
    from sc8.gate import is_first_commitment
    from sc8.pending_queue import FilePendingQueue
    from sc8.models import SalesOrder
    from zhuopin_platform.audit import AuditLogger, JsonlSink
    from zhuopin_platform.shared_tools.connector_audit import ConnectorAudit

    os.environ["SC8_DATA_SOURCE"] = "real"
    os.environ["U9C_DATA_SOURCE"] = "real"
    os.environ["SC8_SRM_SOURCE"] = srm_mode
    params = default_params()
    out_ids = config.outsource_ids_from_env()
    SMT_LEAD = 5  # 无工时连接器 → mock，如实标 smt_lead=mock

    # 幂等：清理上轮产物（队列/审计），使重跑的 pending 计数与审计链反映本轮真实结果。
    out = Path(out_dir)
    (out / "audit").mkdir(parents=True, exist_ok=True)
    (out / ".gitignore").write_text("# 真实客户数据，禁止入库（红线）\n*\n", encoding="utf-8")
    for rel in ("pending_approvals.jsonl", "audit/connector_access.jsonl", "audit/sc8_real_validation.jsonl"):
        (out / rel).unlink(missing_ok=True)

    # 连接器访问痕迹（IATF 可追溯红线）：注入 ConnectorAudit，落 gitignored access-trace 日志
    conn_audit = ConnectorAudit(sink=JsonlSink(out / "audit" / "connector_access.jsonl"))

    # 1. 订单来源
    if dry_products:
        target = (date.today() + timedelta(days=45)).isoformat()
        orders = [SalesOrder(f"DRY-{c}", "", "内部验证(合成壳)", c, 1, target, item_name="")
                  for c in dry_products]
        print(f"[dry-run] 合成订单壳 {len(orders)} 张（FO 离线机理验证，非真实黄金）")
    else:
        orders = load_real_orders()
        print(f"[FO] 真实订单行：{len(orders)}")

    products_all = list(dict.fromkeys(o.item_code for o in orders))
    bom = load_real_bom(products_all, audit=conn_audit)
    srm = load_srm_deliveries(srm_mode, audit=conn_audit)
    print(f"[BOM] 行数={len(bom)}  [SRM mode={srm_mode}] 记录={len(srm)}")

    sample, cat_counts = select_sample(orders, bom, srm, params, out_ids, limit)
    print(f"[取样] {len(sample)} 张；全量类别分布={cat_counts}")
    sample_products = list(dict.fromkeys(o.item_code for o in sample))
    sample_bom = [r for r in bom if r.product_id in sample_products]

    data_sources = build_data_sources(
        order_src=("mock" if dry_products else "real"),
        bom_src="real", srm_src=srm_mode, lead_src="mock",
    )

    # 2. 冻结输入（确定性回归基准）。out/.gitignore(=*) 已在前文写好，含真实客户数据绝不入库。
    (out / "frozen_orders.json").write_text(
        json.dumps([_asdict(o) for o in sample], ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "frozen_bom.json").write_text(
        json.dumps([_asdict(r) for r in sample_bom], ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "frozen_srm.json").write_text(
        json.dumps([_asdict(d) for d in srm], ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "frozen_meta.json").write_text(json.dumps({
        "srm_mode": srm_mode, "order_src": data_sources["fo"], "smt_lead_mock_days": SMT_LEAD,
        "param_version": params.param_version,
        "params": {"no_feedback_lead_days": params.no_feedback_lead_days,
                   "outsource_extra_days": params.outsource_extra_days,
                   "logistics_days": params.logistics_days},
        "note": "FO/BOM/SRM 真实快照；smt 工时 mock。口径未决见脚本头注。",
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3. 预测（全链 audit）+ 4. dispatch 真阻塞
    audit = AuditLogger.jsonl(out / "audit" / "sc8_real_validation.jsonl")
    queue = FilePendingQueue(out / "pending_approvals.jsonl")
    lead_map = {pid: SMT_LEAD for pid in sample_products}
    forecasts = compute_forecasts(
        sample, sample_bom, srm, lead_map,
        params=params, audit=audit, outsource_ids=out_ids, data_sources=data_sources,
    )
    queued = []
    for fc in forecasts:
        first = is_first_commitment(audit, fc.customer_name)
        outcome, item_id = route_forecast(fc, queue=queue, first_commitment=first,
                                          mode="real", audit=audit)
        queued.append((fc, outcome))

    # 5. 中间量重算（供核对表；与引擎同 params 确定性一致）
    plans = aggregate_demand(sample)
    demand_by = {pl.product_id: date.fromisoformat(pl.planned_date) for pl in plans}
    expected = []
    rows_md = []
    for fc in forecasts:
        mat = estimate_material_arrivals(fc.product_id, sample_bom, srm,
                                         demand_by[fc.product_id], params)
        outs = is_outsourced(fc.product_id, product_ids=out_ids)
        kit = max(mat.arrivals.values()).isoformat() if mat.arrivals else "—"
        srm_used = {m: a.isoformat() for m, a in mat.arrivals.items()
                    if m not in mat.no_feedback_materials}
        exp = {
            "so_id": fc.so_id, "product_id": fc.product_id, "customer_name": fc.customer_name,
            "target_date": fc.target_date.isoformat(),
            "forecast_date": fc.forecast_date.isoformat() if fc.forecast_date else None,
            "delay_days": fc.delay_days, "risk_level": fc.risk_level,
            "confidence": fc.confidence, "bottleneck_material": fc.bottleneck_material,
            "kit_date": kit, "n_components": len(mat.arrivals),
            "n_srm_committed": len(srm_used), "n_no_feedback": len(mat.no_feedback_materials),
            "outsourced": outs, "smt_lead_days": SMT_LEAD,
            "param_version": fc.param_version,
        }
        expected.append(exp)
        rows_md.append(
            f"| {fc.so_id} | {fc.customer_name} | {fc.product_id} | {fc.target_date.isoformat()} "
            f"| {kit} | {fc.bottleneck_material or '—'} | {len(srm_used)}/{len(mat.arrivals)} "
            f"| {'是' if outs else '否'} | {SMT_LEAD} | "
            f"{fc.smt_complete_date.isoformat() if fc.smt_complete_date else '—'} "
            f"| {fc.forecast_date.isoformat() if fc.forecast_date else '—'} | {fc.delay_days} "
            f"| {fc.risk_level} | {fc.confidence} |  |  |"
        )

    (out / "expected.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# SC8 真实内部验证 — 人工交叉核对表" + ("（DRY-RUN 机理验证，非真实黄金）" if dry_products else ""),
        "",
        f"> 数据源：FO={data_sources['fo']} / BOM=real / SRM={srm_mode} / SMT工时=mock({SMT_LEAD}天)。",
        f"> 参数版本 {params.param_version}：无反馈+{params.no_feedback_lead_days} / 委外+{params.outsource_extra_days} / 物流+{params.logistics_days}。",
        "> 校验标准（SOP §2.3）：确定性逻辑（齐料日=关键路径最晚子件到货、日期加减）与手工核算偏差=0。",
        "> 置信度列为引擎原生 2 级（高/低）；SOP §4.1 的 3 级(高/中/低)口径待裁决后叠加。",
        "> 对客外发全程关闭（CUSTOMER_OUTBOUND_ENABLED=False）；下列全部只入待审批队列、未外发。",
        "",
        "| SO | 客户 | 成品 | 客户目标日 | 齐料日(关键路径) | 瓶颈物料 | SRM承诺/子件数 | 委外 | SMT工时 | SMT完工 | 预测交付 | 延期 | 风险 | 置信(引擎) | 手工核算 | 偏差 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        *rows_md,
        "",
        f"**入待审批队列**：{len(queue.list_pending())} 张（全部未外发）。",
        "**手工核算/偏差**两列留给 PMC 逐张手算填写；确定性逻辑应偏差=0。",
    ]
    (out / "golden_expected_real.md").write_text("\n".join(md), encoding="utf-8")

    print(f"[产出] 冻结输入 + expected.json + golden_expected_real.md → {out}")
    print(f"[队列] pending={len(queue.list_pending())}（未外发）")
    print("[预测摘要]")
    for e in expected:
        print(f"  {e['so_id']} {e['customer_name']} {e['product_id']} 目标{e['target_date']} "
              f"→ 预测{e['forecast_date']} 延{e['delay_days']} {e['risk_level']} "
              f"置信={e['confidence']} 瓶颈={e['bottleneck_material']} "
              f"SRM承诺{e['n_srm_committed']}/{e['n_components']}")
    return expected


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--srm-mode", default="real", choices=["real", "mock"])
    ap.add_argument("--out-dir", default=str(SC8_DIR / "data" / "golden" / "real_frozen"))
    ap.add_argument("--dry-run-products", default="")
    args = ap.parse_args()
    load_env()
    dry = [x.strip() for x in args.dry_run_products.split(",") if x.strip()]
    build(args.limit, args.srm_mode, args.out_dir, dry)


if __name__ == "__main__":
    main()
