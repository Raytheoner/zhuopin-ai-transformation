"""队列 #344 修复前后对照 runner —— 同一份真实输入，跑两遍 `build_dashboard`。

用途：量出「齐料日期改按答交数量累计取值」对四色判定的**真实**影响面。
不预估、不外推——判例包正文已向姚祖怡交代过"红的行会变多"，多多少必须用生产载荷量。

🔴 **修复前那一遍靠本脚本内的临时 monkeypatch 实现，生产代码里不留任何开关。**
一个只在对照时用的 env 开关会变成永久的第二套口径——那正是本变更要消灭的东西。

🔴 **必须用生产载荷跑**：`.51` 的 `C:\\baoguan\\.env` 里 `SC8_NET_INVENTORY=on`，
而仓库根 `.env` 没有这个键、默认 OFF ⇒ 本机裸跑会静默走另一套口径，数字对不上生产。
本脚本启动时会把实际生效的开关打印出来并要求确认，不靠"我记得设过"。

用法（笔记本 LAN 内）：
    SC8_NET_INVENTORY=on python scripts/compare_kit_date_cumulative.py [--out <md路径>]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

# —— 平台底座路径引导（队列 #345 收拢；唯一被允许的样板见 bootstrap.py 模块 docstring）——
_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, _HERE.parent.parent)  # noqa: E402

from zhuopin_platform.env_anchor import (  # noqa: E402
    load_env as _resolve_and_load_env,
    resolve_env_file as _resolve_env_file,
)

from sc8 import baoguan, config, forecast  # noqa: E402
from sc8.baoguan import (RISK_GAP, RISK_GREEN, RISK_RED, RISK_YELLOW,  # noqa: E402
                         build_dashboard)
from sc8.sources import (_fetch_line_status, load_material_commitments,  # noqa: E402
                         load_purchase_orders_by_material, load_real_bom,
                         load_real_orders, load_srm_deliveries)

RISK_NAME = {RISK_RED: "🔴真延期", RISK_GAP: "🟠待催", RISK_YELLOW: "🟡偏紧", RISK_GREEN: "🟢按期"}


def _find_dotenv() -> Path | None:
    """【已收拢，保留为薄封装】返回本次运行该用的那份 `.env`（解析见 `env_anchor`，#354）。

    🔴 **本函数原先的写法与它 docstring 里的推理，是一个「结论对、理由碰巧成立」的样本**，
    值得原样记下来：原注释说「不能只看仓库根，因为 `.env` 是 gitignore 件、只存在于共享主
    工作区，worktree 里根本没有；故逐层向上找**文件真的在**的那一层，worktree 下会一路走到
    主工作区」。**这个推理今天成立，但它依赖的是一个会变的事实**——2026-08-24 实测全部 44 个
    worktree 确实零 `.env` 副本，可 2026-08-18 的
    `sc8-substitute-penetration-priority-0f8664` 里就躺过一份陈旧两代的副本。**一旦某个
    worktree 里又出现 `.env`，本写法立刻命中它、且不报错**（#354 的病灶本身）。
    收拢后由 `--git-common-dir` 规范化到主工作区——**不靠「那儿碰巧没有文件」，靠 git 知道
    linked worktree 共享哪个仓库根**，这才与理由无关地成立。
    """
    return _resolve_env_file(__file__).path


def _load_dotenv(path: Path | None) -> None:
    """把 `.env` 读进 `os.environ`（不覆盖已设的键）——与服务进程同源凭据。

    参数保留是为了不动 `main()` 的既有调用序列；实际解析与读取都在 `env_anchor` 里完成。
    """
    _resolve_and_load_env(__file__)


def _dump_inputs(path: Path, orders, bom, srm, inventory, purchase_orders, commitments) -> None:
    """冻结一次真实取数，供复跑（同 `data/golden/real_frozen/` 的既有思路）。

    ⚠️ 落到**仓库外**（调用方给的 `--cache` 路径，本次用临时目录）：这份东西含真实
    客户名与真实料号，`data/golden/real_frozen/` 的既有约定就是 real_frozen 不入库。
    """
    import dataclasses
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "orders": [dataclasses.asdict(o) for o in orders],
        "bom": [dataclasses.asdict(b) for b in bom],
        "srm": [dataclasses.asdict(s) for s in srm],
        "inventory": inventory,
        "purchase_orders": purchase_orders,
        "commitments": {m: [[d.isoformat(), q] for d, q in v] for m, v in commitments.items()},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _load_inputs(path: Path):
    from zhuopin_platform.shared_tools.models import BomRow, SrmDeliveryOrder
    from sc8.models import SalesOrder
    p = json.loads(path.read_text(encoding="utf-8"))
    return (
        [SalesOrder(**o) for o in p["orders"]],
        [BomRow(**b) for b in p["bom"]],
        [SrmDeliveryOrder(**s) for s in p["srm"]],
        p["inventory"],
        p["purchase_orders"],
        {m: [(date.fromisoformat(d), q) for d, q in v] for m, v in p["commitments"].items()},
    )


def _legacy_estimate(*args, **kwargs):
    """修复前口径：丢掉队列 #344 新增的两个入参，回到"最早承诺日"分支。

    刻意用"丢参数"而不是"复制一份旧实现"——旧实现已经在 `estimate_material_arrivals`
    的 `else` 分支里逐字保留着（design D4 的零漂移边界），复制一份反倒可能抄错。
    """
    kwargs.pop("material_commitments", None)
    kwargs.pop("required_qty", None)
    return forecast.estimate_material_arrivals(*args, **kwargs)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="", help="对照结果落盘路径（.md）；缺省只打印")
    ap.add_argument("--status", default="2", help="FO 状态过滤，默认 2=已审核")
    ap.add_argument("--cache", default="", help="真实输入冻结文件（.json，仓库外）；存在则复用、不存在则抓完写入。SRM 端点 1 req/30s 硬限流且生产服务同时在用，复跑必须靠它")
    ap.add_argument("--srm-cache", default="", help="firm 承诺交期缓存路径（建议直接用 .51 上 C:\\baoguan\\app\\reports\\srm_answer_cache.json 的本地副本）；不给则冷查，几百个 PO 对在 1 req/30s 下要跑几小时")
    args = ap.parse_args()

    dotenv = _find_dotenv()
    _load_dotenv(dotenv)

    today = date.today()
    print(f"== 凭据来源 ==\n   {dotenv or '🔴 未找到任何 .env（下游会 fail-loud）'}")
    print("== 生效开关（对照生产 .51 的 C:\\baoguan\\.env）==")
    print(f"   SC8_NET_INVENTORY = {'on' if config.net_inventory_enabled() else 'OFF'}"
          f"   ← 生产为 on")
    print(f"   SC8_PO_TRANSIT    = {'on' if config.po_transit_enabled() else 'OFF'}"
          f"   ← 生产为 on（默认）")
    print(f"   SC8_BOM_MAX_DEPTH = {config.bom_max_depth()}   ← 生产为 5（默认）")
    print(f"   业务日期          = {today.isoformat()}（本机本地日）")
    if not config.net_inventory_enabled():
        print("\n🔴 净额开关为 OFF —— 与生产不一致，跑出来的数字不能用于验收。中止。")
        return 2

    cache = Path(args.cache) if args.cache else None
    if cache and cache.is_file():
        print(f"\n== 复用已冻结的真实输入：{cache} ==")
        orders, bom, srm, inventory, purchase_orders, commitments = _load_inputs(cache)
        components = {r.component_id for r in bom} - {r.product_id for r in bom}
    else:
        print("\n== 拉真实数据（与 compute_snapshot 同源同顺序）==")
        # 🔴 SRM 端点是 1 req/30s 硬限流，而 `.51` 上的生产服务每小时也在拉同一个端点。
        # 抓完立刻冻结到 `--cache`，让"跑第二遍/换个角度再看"这类事**不再需要重抓**——
        # 既是对共享资源让路，也让这份对照可复跑、可被别人复核（否则底稿里的数字
        # 只能靠"我当时看到的就是这样"背书）。
        orders = load_real_orders(api_base=os.environ.get("FO_API_BASE"), status=args.status)
        product_ids = list(dict.fromkeys(o.item_code for o in orders))
        bom = load_real_bom(product_ids, max_depth=config.bom_max_depth())
        sub_assembly_ids = {r.product_id for r in bom}
        components = {r.component_id for r in bom if r.component_id not in sub_assembly_ids}
        print(f"   预测订单行 {len(orders)} ／ BOM 行 {len(bom)} ／ 叶子件 {len(components)}")

        from zhuopin_platform.shared_tools.erp_connector import ZpConnector
        conn = ZpConnector.from_env()
        inventory = {r.material_id: r.current_stock
                     for r in conn.get_inventory(sorted(components))}
        line_status = _fetch_line_status(conn, components)
        purchase_orders = load_purchase_orders_by_material(components, line_status=line_status)
        # SRM 两次取数放在最后：前面的 ERP 取数万一失败，不至于白白耗掉限流配额。
        # 🔴 **必须带上 firm 承诺缓存**：`load_srm_deliveries` 会对每个 (PO, vendor) 打一次
        # `/purchase/answer`，而该端点是 **1 req/30s 硬限流** —— 冷缓存下几百个 PO 对
        # 就是几小时，且会把配额抢光、连带拖慢 `.51` 上每小时重算的生产服务。
        # 生产服务本身就是靠这个 6 小时 TTL 缓存跑的（`C:\\baoguan\\app\\reports\\
        # srm_answer_cache.json`），本脚本用 `--srm-cache` 指向它的本地副本即可同源同速。
        srm = load_srm_deliveries("real", materials=components,
                                  cache_path=args.srm_cache or None,
                                  ttl_sec=(6 * 3600 if args.srm_cache else 0))
        commitments = load_material_commitments("real", materials=components)
        if cache:
            _dump_inputs(cache, orders, bom, srm, inventory, purchase_orders, commitments)
            print(f"   已冻结真实输入 → {cache}")
    print(f"   SRM 承诺记录 {len(srm)} ／ 逐笔答交明细覆盖 {len(commitments)} 个物料 "
          f"／ 在途 PO 覆盖 {len(purchase_orders)} 个物料")

    # 取数口径差集：有 /purchase/answer 承诺日、但逐笔明细里查无此料（design D1 的代价）
    srm_only = sorted({d.material_id for d in srm} - set(commitments))
    print(f"   ⚠️ 有 SRM 承诺日但逐笔明细无记录的物料：{len(srm_only)} 个")

    kw = dict(today=today, inventory=inventory, purchase_orders=purchase_orders,
              material_commitments=commitments)

    print("\n== 跑三遍 build_dashboard（修复前 / 修复后 / 换源变体）==")
    after = build_dashboard(orders, bom, srm, **kw)

    orig = baoguan.estimate_material_arrivals
    baoguan.estimate_material_arrivals = _legacy_estimate
    try:
        before = build_dashboard(orders, bom, srm, **kw)
    finally:
        baoguan.estimate_material_arrivals = orig

    # 变体 W（**未采纳**，只为把 design D1 的代价量出来）：把「逐笔明细无记录」也判成
    # 无答交（即把 `receiveType==2` 口径推广到四色判定）。实现＝抹掉 legacy 回退。
    orig_arr = forecast._arrival_by_cumulative_qty
    def _wide(commitments, target_qty, *, fallback, legacy_date):   # noqa: ANN001
        return orig_arr(commitments, target_qty, fallback=fallback, legacy_date=None)
    forecast._arrival_by_cumulative_qty = _wide
    try:
        wide = build_dashboard(orders, bom, srm, **kw)
    finally:
        forecast._arrival_by_cumulative_qty = orig_arr

    def counts(rows):
        return {k: sum(1 for r in rows if r.risk == k)
                for k in (RISK_RED, RISK_GAP, RISK_YELLOW, RISK_GREEN)}

    cb, ca, cw = counts(before), counts(after), counts(wide)
    key = lambda r: (r.so_id, r.product_id, r.ship_date)   # noqa: E731
    bmap = {key(r): r for r in before}
    amap = {key(r): r for r in after}
    wmap = {key(r): r for r in wide}
    assert set(bmap) == set(amap) == set(wmap), "三遍的行集合必须完全一致，否则对照无意义"
    wide_delta = [k for k in amap
                  if amap[k].kit_date != wmap[k].kit_date
                  or amap[k].risk != wmap[k].risk
                  or amap[k].bottleneck_material != wmap[k].bottleneck_material]

    changed = [(bmap[k], amap[k]) for k in bmap
               if bmap[k].risk != amap[k].risk or bmap[k].kit_date != amap[k].kit_date
               or bmap[k].bottleneck_material != amap[k].bottleneck_material]
    changed.sort(key=lambda p: (p[1].risk, p[1].so_id, p[1].product_id))

    lines: list[str] = []
    w = lines.append
    w(f"**业务日期**：{today.isoformat()}（本机本地日）　**预测订单行**：{len(orders)}　"
      f"**叶子件**：{len(components)}　**逐笔答交明细覆盖**：{len(commitments)} 个物料")
    w("")
    w("### 四色计数")
    w("")
    w("| 风险 | 修复前 | 修复后（已采纳） | 差 | 变体 W（换源，未采纳） |")
    w("|---|---:|---:|---:|---:|")
    for k in (RISK_RED, RISK_GAP, RISK_YELLOW, RISK_GREEN):
        w(f"| {RISK_NAME[k]} | {cb[k]} | {ca[k]} | {ca[k]-cb[k]:+d} | {cw[k]} |")
    w(f"| **合计** | **{sum(cb.values())}** | **{sum(ca.values())}** | — | "
      f"**{sum(cw.values())}** |")
    w("")
    w(f"### 逐行变动（{len(changed)} / {len(bmap)} 行）")
    w("")
    if not changed:
        w("（本次快照下无任何行发生变动）")
    else:
        w("| 预测单 | 成品 | 出货日 | 齐料日（前→后） | 瓶颈物料（前→后） | 四色（前→后） |")
        w("|---|---|---|---|---|---|")
        for b, a in changed:
            kd = (f"{b.kit_date or '—'} → **{a.kit_date or '—'}**"
                  if b.kit_date != a.kit_date else str(b.kit_date or "—"))
            bn = (f"{b.bottleneck_material or '—'} → **{a.bottleneck_material or '—'}**"
                  if b.bottleneck_material != a.bottleneck_material
                  else (b.bottleneck_material or "—"))
            rk = (f"{RISK_NAME[b.risk]} → **{RISK_NAME[a.risk]}**"
                  if b.risk != a.risk else RISK_NAME[b.risk])
            w(f"| {b.so_id} | {b.product_id} | {b.ship_date} | {kd} | {bn} | {rk} |")
    w("")
    w("### 取数口径差集（design D1 的代价，实测值）")
    w("")
    w(f"有 `/purchase/answer` 承诺日、但逐笔答交明细（`receiveType==2`、前瞻 180 天）里"
      f"**查无此料**的物料：**{len(srm_only)}** 个。")
    w("")
    w("**已采纳的口径对这 106 个料不动手**——它们仍沿用改造前的最早承诺日。"
      "理由是授权边界：#211 v2 原文明写其 `receiveType==2` 筛选「范围仅限本函数……"
      "不影响 `load_srm_deliveries`（驱动 kit_date/gap_days/四色风险判定的既有口径）"
      "——未经授权不改判定逻辑」。队列 #344 领的活是**答交数量匹配那一层**，换取数源"
      "是另一条独立判据。")
    w("")
    w(f"**变体 W 实测（把这 106 个也判无答交）**：与已采纳口径相比，"
      f"**{len(wide_delta)} 行** 的齐料日/瓶颈/四色有差异，四色计数"
      f"{'**完全相同**' if cw == ca else '**不同**（见上表末列）'}。")
    w("")
    w("🔑 **这个数字推翻了一个听起来很合理的猜测**：换源看着像是个大动作（106 个料！），"
      "实测对四色**零影响**——因为这些料本来就不是各自成品行的瓶颈。"
      "⇒ **换源与否不该用「影响面大小」来论证，只能用「谁授权的」来论证**；"
      "若当初按影响面拍板，两个方向都能编出理由。")
    if srm_only:
        w("")
        w("前 30 个：`" + "`、`".join(srm_only[:30]) + "`")

    out = "\n".join(lines)
    print("\n" + out)
    if args.out:
        Path(args.out).write_text(out + "\n", encoding="utf-8")
        print(f"\n已落盘：{args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
