"""判例 4（「答了、但加起来还是不够」）的**真实**案例取数器 —— 姚祖怡 2026-08-28 回件点名要的那个例子。

背景：`采购部#19` 的判例 4 他勾了 ✅ 同时写了两个字「**要例子**」。上一封没给例子，
理由是做信的机器不在厂内网上（信里已如实交代）。本脚本就是来补这一条的。

判例 4 的口径条文（他签认、但要求见真实案例才终局确认）：
    答交有几笔但**累计仍不足**本物料需求量时，判为**无答交**，到货日取
    「无答交启发式估算日」与「最晚一笔正数答交日」中**更晚**的那个。
实现处 ＝ `sc8/forecast.py::_arrival_by_cumulative_qty` 的 `positives` 分支。

━━━ 🔴 与 `find_cumulative_evidence.py` 的分工，别搞混 ━━━
那一个找的是「累计**够了**」（`first < total <= summed`，判例 3 的佐证）；
**本脚本找的是反面：`summed < total`**——累计到最后仍然不够。两者筛选式互斥。

━━━ 🔴 数据源：源系统直取，不是 `.51` 快照（2026-08-28 实测被迫改的路）━━━
`find_cumulative_evidence.py` 走 `.51:8091/api/materials`。**本脚本不能**：2026-08-28
实测 off-LAN——`ping 192.168.100.51` 不通、`:8091/api/ping` 返 502 且是本机代理给的
（`-NoProxy` 直连超时，路由被 Mihomo TUN 接管）、SMB 管理共享 `192.168.100.51\\c$` 亦不可达
（连门禁口令都取不到）。而 **ERP `erp.equalitytec.com:4443` 与携客云
`openapi.xiekeyun.com` 从公网可达、凭据实跑成功**（FO 103 行 3.3s／SRM 看板 720 行 5.8s）。
⇒ 改为**从源系统直接重算**，与 `compute_snapshot` 同源同顺序。

🔴 **一处必须写在脸上的口径缺口：本脚本不跑 `/purchase/answer`（传 `srm=[]`）。**
该端点是**进程级令牌桶 1 req/30s**，几百个 (PO, vendor) 对 ＝ 数小时，且会把携客云配额
抢光、连带拖慢 `.51` 上每小时重算的生产服务。**判例 4 本身不依赖它**——
`_arrival_by_cumulative_qty` 走 `positives` 分支时根本不读 `legacy_date`，故案例的
料号／需求量／逐笔答交／累计差额／该子件三算法到货日**全部是真数、与 srm 无关**。
**但行级齐料日与四色分布依赖它** ⇒ 那两项属**变体口径**（≈ `compare_kit_date_cumulative.py`
里量过的「变体 W」），输出里逐处标注，**不得当作对姚祖怡的承诺数字**。

用法（须显式带净额开关，与生产 `.51` 的 `C:\\baoguan\\.env` 对齐）：
    SC8_NET_INVENTORY=on python scripts/find_insufficient_cumulative_cases.py \
        --cache <仓库外.json> --out <仓库外.md> --top 5
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from datetime import date, timedelta
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

from sc8 import config, forecast  # noqa: E402
from sc8.baoguan import (RISK_GAP, RISK_GREEN, RISK_RED, RISK_YELLOW,  # noqa: E402
                         build_dashboard)
from sc8.forecast import _cumulative_confirmed_batches  # noqa: E402
from sc8.material_board import build_material_board  # noqa: E402
from sc8.sources import (_fetch_line_status, load_material_commitments,  # noqa: E402
                         load_purchase_orders_by_material,
                         load_purchase_supply_by_material, load_real_bom,
                         load_real_orders)

RISK_NAME = {RISK_RED: "🔴真延期", RISK_GAP: "🟠待催", RISK_YELLOW: "🟡偏紧", RISK_GREEN: "🟢按期"}


# ── 三种算法（只在「累计仍不足」这一支上分歧，其余分支逐字相同）────────────────
#
# 之所以用 monkeypatch 三跑同一份输入、而不是自己再写一遍取值：`estimate_material_arrivals`
# → `_arrival_by_cumulative_qty` 是**唯一**判定处，复制一份就等于造第二套口径——那正是
# 队列 #344 要消灭的病（「上面汇总数与下面清单各按各的算」）。同 `compare_kit_date_cumulative.py`
# 的既有做法，**生产代码里不留任何开关**。
def _make_variant(pick: str):
    orig = forecast._arrival_by_cumulative_qty

    def _variant(commitments, target_qty, *, fallback, legacy_date):  # noqa: ANN001
        if target_qty <= 0 or not commitments:
            return (legacy_date or fallback), legacy_date is not None
        batches = _cumulative_confirmed_batches(commitments, target_qty)
        if batches and sum(q for _, q in batches) >= target_qty:
            return batches[-1][0], True
        positives = [d for d, q in commitments if q > 0]
        if not positives:
            return fallback, False
        if pick == "earliest":     # 算法 B：取最早那笔答交日
            return min(positives), False
        if pick == "estimate":     # 算法 C：只取无答交启发式估算日
            return fallback, False
        raise ValueError(pick)     # 现行（max）由 orig 承担，不走本函数
    return orig, _variant


def _fallback_date(ship: date, today: date, p) -> date:
    """该成品行的「无答交启发式估算日」——与 `build_dashboard` 内逐字同源。

    rule1 OFF（生产现状，`SC8_KIT_DATE_RULE1` 默认 off 且 `.51` 上尚未翻开关）⇒
    起算 ＝ `max(出货日, 今天)`；ON ⇒ 由 `no_feedback_start_date` 决定。
    """
    base = (forecast.no_feedback_start_date(ship, today, p)
            if config.kit_date_rule1_enabled() else max(ship, today))
    return base + timedelta(days=p.no_feedback_lead_days)


# ── 真实输入冻结（仓库外）：同 compare_kit_date_cumulative.py 的既有思路 ──────────
def _dump_inputs(path: Path, orders, bom, inventory, purchase_orders, commitments,
                 supply_by_material) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "orders": [dataclasses.asdict(o) for o in orders],
        "bom": [dataclasses.asdict(b) for b in bom],
        "inventory": inventory,
        "purchase_orders": purchase_orders,
        "commitments": {m: [[d.isoformat(), q] for d, q in v] for m, v in commitments.items()},
        "supply_by_material": supply_by_material,
    }, ensure_ascii=False), encoding="utf-8")


def _load_inputs(path: Path):
    from zhuopin_platform.shared_tools.models import BomRow
    from sc8.models import SalesOrder
    p = json.loads(path.read_text(encoding="utf-8"))
    return (
        [SalesOrder(**o) for o in p["orders"]],
        [BomRow(**b) for b in p["bom"]],
        p["inventory"],
        p["purchase_orders"],
        {m: [(date.fromisoformat(d), q) for d, q in v] for m, v in p["commitments"].items()},
        p["supply_by_material"],
    )


def main() -> int:  # noqa: C901
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="", help="结果落盘路径（.md）；缺省只打印")
    ap.add_argument("--cache", default="", help="真实输入冻结文件（.json，仓库外）；存在则复用")
    ap.add_argument("--status", default="2", help="FO 状态过滤，默认 2=已审核")
    ap.add_argument("--top", type=int, default=5, help="案例最多列几条")
    args = ap.parse_args()

    dotenv = _resolve_env_file(__file__).path
    _resolve_and_load_env(__file__)
    today = date.today()
    p = config.default_params()

    print(f"== 凭据来源 ==\n   {dotenv or '🔴 未找到任何 .env（下游会 fail-loud）'}")
    print("== 生效开关（对照生产 .51 的 C:\\baoguan\\.env）==")
    print(f"   SC8_NET_INVENTORY   = {'on' if config.net_inventory_enabled() else 'OFF'}   ← 生产为 on")
    print(f"   SC8_PO_TRANSIT      = {'on' if config.po_transit_enabled() else 'OFF'}   ← 生产为 on（默认）")
    print(f"   SC8_KIT_DATE_RULE1  = {'on' if config.kit_date_rule1_enabled() else 'OFF'}  ← 生产为 off（开关尚未翻，等姚祖怡签认）")
    print(f"   SC8_BOM_MAX_DEPTH   = {config.bom_max_depth()}   ← 生产为 5（默认）")
    print(f"   业务日期            = {today.isoformat()}（本机本地日）")
    if not config.net_inventory_enabled():
        print("\n🔴 净额开关为 OFF —— 与生产不一致，跑出来的数字不能用于判例包。中止。")
        return 2

    cache = Path(args.cache) if args.cache else None
    if cache and cache.is_file():
        print(f"\n== 复用已冻结的真实输入：{cache} ==")
        orders, bom, inventory, purchase_orders, commitments, supply_by_material = _load_inputs(cache)
        sub_assembly_ids = {r.product_id for r in bom}
        components = {r.component_id for r in bom if r.component_id not in sub_assembly_ids}
    else:
        print("\n== 拉真实数据（与 compute_snapshot 同源同顺序；刻意跳过 /purchase/answer）==")
        orders = load_real_orders(api_base=os.environ.get("FO_API_BASE"), status=args.status)
        product_ids = list(dict.fromkeys(o.item_code for o in orders))
        bom = load_real_bom(product_ids, max_depth=config.bom_max_depth())
        sub_assembly_ids = {r.product_id for r in bom}
        components = {r.component_id for r in bom if r.component_id not in sub_assembly_ids}
        print(f"   预测订单行 {len(orders)} ／ BOM 行 {len(bom)} ／ 叶子件 {len(components)}")

        from zhuopin_platform.shared_tools.erp_connector import ZpConnector
        conn = ZpConnector.from_env()
        inventory = {r.material_id: r.current_stock for r in conn.get_inventory(sorted(components))}
        line_status = _fetch_line_status(conn, components)
        purchase_orders = load_purchase_orders_by_material(components, line_status=line_status)
        supply_by_material = load_purchase_supply_by_material(components, line_status=line_status)
        commitments = load_material_commitments("real", materials=components)
        if cache:
            _dump_inputs(cache, orders, bom, inventory, purchase_orders, commitments,
                         supply_by_material)
            print(f"   已冻结真实输入 → {cache}")
    print(f"   逐笔答交明细覆盖 {len(commitments)} 个物料 ／ 在途 PO 覆盖 {len(purchase_orders)} 个物料")

    kw = dict(today=today, inventory=inventory, purchase_orders=purchase_orders,
              material_commitments=commitments)

    # ── 六遍 build_dashboard：{规则1 OFF, ON} × {现行, 算法B, 算法C} ────────────
    # 全部吃同一份已冻结的真实输入，**零额外 API 请求**。规则 1 由 `config.kit_date_rule1_enabled()`
    # 每次现读环境变量决定，故只需在跑之前设一次 `SC8_KIT_DATE_RULE1`。
    # 🔴 姚祖怡 2026-08-28 已书面签认「按规则 1 改后的算法开起来」，故 ON 这一侧不再是假设。
    print("\n== 跑六遍 build_dashboard（规则1 OFF/ON × 现行/算法B/算法C）==")
    runs: dict[tuple[str, str], list] = {}
    for r1 in ("off", "on"):
        os.environ["SC8_KIT_DATE_RULE1"] = r1
        runs[(r1, "now")] = build_dashboard(orders, bom, [], **kw)
        for pick in ("earliest", "estimate"):
            orig, variant = _make_variant(pick)
            forecast._arrival_by_cumulative_qty = variant
            try:
                runs[(r1, pick)] = build_dashboard(orders, bom, [], **kw)
            finally:
                forecast._arrival_by_cumulative_qty = orig
    os.environ["SC8_KIT_DATE_RULE1"] = "off"      # 还原为生产现状，免得后续取值走错分支

    key = lambda r: (r.so_id, r.product_id, r.ship_date)          # noqa: E731
    maps = {k: {key(r): r for r in v} for k, v in runs.items()}
    assert len({frozenset(m) for m in maps.values()}) == 1, \
        "六遍的行集合必须完全一致，否则对照无意义"

    rows_now = runs[("off", "now")]               # 生产现状口径（规则 1 未开）
    board = build_material_board(rows_now, today=today, commitments=commitments,
                                 supply_by_material=supply_by_material)

    lines: list[str] = []
    w = lines.append
    w(f"**业务日期**：{today.isoformat()}（本机本地日，UTC+8）　**数据源**：ERP `erp.equalitytec.com:4443` ＋ "
      f"携客云 `openapi.xiekeyun.com` **直取**（非 `.51` 快照）")
    w(f"**预测订单行**：{len(rows_now)}　**叶子件**：{len(components)}　"
      f"**逐笔答交明细覆盖**：{len(commitments)} 个物料　**物料看板行**：{len(board.rows)}")
    w("")
    w("> 🔴 **口径缺口（每次引用这份数字都要连这句一起引）**：本次 **未跑 `/purchase/answer`**"
      "（1 req/30s，几百对＝数小时且会抢 `.51` 生产服务配额），故 `srm=[]`。"
      "**判例 4 的料号／需求量／逐笔答交／累计差额／该子件三算法到货日与之无关，是真数**；"
      "**行级齐料日与四色分布属变体口径**（≈ `compare_kit_date_cumulative.py` 量过的「变体 W」），"
      "不得作为对姚祖怡的承诺数字。")
    w("")

    # ── 一、判例 4 案例（物料看板粒度）──────────────────────────────────────────
    w("## 一、判例 4 真实案例（物料看板粒度 —— 三个月合计缺口 vs 逐笔答交）")
    w("")
    mat_hits = []
    for r in board.rows:
        cb = r.get("cb") or []
        total = float(r.get("total") or 0.0)
        if not cb or total <= 0:
            continue
        summed = sum(float(b.get("q") or 0.0) for b in cb)
        if summed < total:
            mat_hits.append((r, cb, total, summed))
    mat_hits.sort(key=lambda h: (-len([b for b in h[1] if float(b["q"]) > 0]),
                                 -(h[2] - h[3])))
    w(f"**命中**：{len(mat_hits)} / {len(board.rows)} 行物料看板行满足「有逐笔答交、累计仍不足三个月合计缺口」。")
    w("")
    if not mat_hits:
        w("🔴 **本次零命中** —— 只能说这一刻的三个月窗口内没有，不能断言真实世界里没有。")
    else:
        w("| # | 料号 | 品名 | 三月合计缺口 | 逐笔答交（全部） | 累计答交 | **还差** |")
        w("|---|---|---|---:|---|---:|---:|")
        for i, (r, cb, total, summed) in enumerate(mat_hits[:args.top], 1):
            seq = " ＋ ".join(f"{b['d']} 给 {float(b['q']):,.0f}" for b in cb)
            w(f"| {i} | `{r['id']}` | {r.get('name', '')} | {total:,.0f} | {seq} | "
              f"{summed:,.0f} | **{total - summed:,.0f}** |")
    w("")

    # ── 二、成品行子件粒度：三算法 × 规则1 OFF/ON ──────────────────────────────
    w("## 二、成品行子件粒度的三算法对照（齐料日真正的计算粒度）")
    w("")
    comp_hits = []
    for k, r in maps[("off", "now")].items():
        for s in r.component_status or []:
            if s.role == "substitute":
                continue
            target = s.gap_qty if s.gap_qty is not None else s.qty_needed
            cb = list(s.confirmed_batches or ())
            if not cb or target is None or target <= 0:
                continue
            summed = sum(q for _, q in cb)
            if summed >= target:
                continue
            positives = [d for d, q in (commitments.get(s.component_id) or []) if q > 0]
            if not positives:
                continue                       # 全 0 属口径 ⑷，不是判例 4
            row = {"key": k, "so": r.so_id, "pid": r.product_id, "ship": r.ship_date,
                   "mid": s.component_id, "name": s.component_name,
                   "need": s.qty_needed, "avail": s.available_qty, "target": target,
                   "cb": cb, "summed": summed, "npos": len(positives),
                   "is_bn": r.bottleneck_material == s.component_id}
            for r1 in ("off", "on"):
                os.environ["SC8_KIT_DATE_RULE1"] = r1
                fb = _fallback_date(r.ship_date, today, p)
                row[r1] = {
                    "fb": fb,
                    "d_now": max(fb, max(positives)),
                    "d_earliest": min(positives),
                    "d_estimate": fb,
                    "kit_now": maps[(r1, "now")][k].kit_date,
                    "kit_earliest": maps[(r1, "earliest")][k].kit_date,
                    "kit_estimate": maps[(r1, "estimate")][k].kit_date,
                    "risk": maps[(r1, "now")][k].risk,
                }
            os.environ["SC8_KIT_DATE_RULE1"] = "off"
            comp_hits.append(row)

    w(f"**命中**：{len(comp_hits)} 条（成品行 × 子件）满足判例 4；"
      f"涉及 {len({c['mid'] for c in comp_hits})} 个不同料号、"
      f"{len({(c['so'], c['pid'], c['ship']) for c in comp_hits})} 张成品卡片。")
    w("")
    w("📌 **一处必须一并说明的现象**：§一（物料看板粒度）与本节（成品行粒度）**命中的料号可能基本不重合**——"
      "两处的累计目标不同：物料看板按**三个月合计缺口**累计，成品卡片按**这一张单的缺口数量**累计。"
      "**同一个料在物料看板上「答了但不够」、在某张成品卡片上却可能「够了」，这是对的**，"
      "与页面「取数说明」第 3 条讲的是同一件事。")
    w("")
    # 选案：跨成品卡片去重 + 优先瓶颈 + 优先「正数答交笔数多」（他原话是「答了几笔」）
    picked = sorted(comp_hits, key=lambda c: (not c["is_bn"], -c["npos"],
                                              -(c["target"] - c["summed"])))
    show, seen_card, seen_mid = [], set(), set()
    for c in picked:
        card = (c["so"], c["pid"], c["ship"])
        if card in seen_card or c["mid"] in seen_mid:
            continue
        seen_card.add(card)
        seen_mid.add(c["mid"])
        show.append(c)
        if len(show) >= args.top:
            break
    for i, c in enumerate(show, 1):
        avail = "—（无净额数据）" if c["avail"] is None else f"{c['avail']:,.0f}"
        w(f"### 案例 {i} · `{c['mid']}`　{c['name']}")
        w("")
        w(f"- **出现在**：预测单 `{c['so']}` ／ 成品 `{c['pid']}` ／ 计划出货日 **{c['ship']}**")
        w(f"- **本行需求量（毛需求）**：{c['need']:,.0f}　**可用现货**：{avail}　"
          f"⇒ **缺口数量（累计目标）＝ {c['target']:,.0f}**")
        w("- **逐笔答交**：" + "　".join(f"`{d}` 给 **{q:,.0f}**" for d, q in c["cb"]))
        w(f"- **累计答交 {c['summed']:,.0f}，仍差 {c['target'] - c['summed']:,.0f}** ⇒ 正是判例 4 那种情形")
        w(f"- **该子件是否为本行瓶颈**：{'✅ 是' if c['is_bn'] else '否'}")
        w("")
        w("| 算法 | 规则1 **OFF**（生产现状）子件到货日 | 同左·该行齐料日 | 规则1 **ON**（他已签认要开）子件到货日 | 同左·该行齐料日 |")
        w("|---|---|---|---|---|")
        w(f"| **现行**：max(估算日, 最晚一笔正数答交日) | **{c['off']['d_now']}** | {c['off']['kit_now']} "
          f"| **{c['on']['d_now']}** | {c['on']['kit_now']} |")
        w(f"| 算法 B：取最早那笔答交日 | {c['off']['d_earliest']} | {c['off']['kit_earliest']} "
          f"| {c['on']['d_earliest']} | {c['on']['kit_earliest']} |")
        w(f"| 算法 C：只取估算日 | {c['off']['d_estimate']} | {c['off']['kit_estimate']} "
          f"| {c['on']['d_estimate']} | {c['on']['kit_estimate']} |")
        w("")
        w(f"- 无答交启发式估算日：规则1 OFF ＝ **{c['off']['fb']}**　／　规则1 ON ＝ **{c['on']['fb']}**"
          f"　（起算点 ＋{p.no_feedback_lead_days} 天）")
        w(f"- 本行四色：规则1 OFF ＝ {RISK_NAME.get(c['off']['risk'], '?')}　／　"
          f"ON ＝ {RISK_NAME.get(c['on']['risk'], '?')}")
        w("")

    # ── 三、规则 1 开关前后四色（他已签认要开）────────────────────────────────
    def _counts(rows):
        return {k: sum(1 for r in rows if r.risk == k)
                for k in (RISK_RED, RISK_GAP, RISK_YELLOW, RISK_GREEN)}
    c_off, c_on = _counts(runs[("off", "now")]), _counts(runs[("on", "now")])
    w("## 三、规则 1 开关前后四色（🔴变体口径🔴）—— 与信里给他看的那张表逐格核对")
    w("")
    w("| 风险 | 规则1 OFF | 规则1 ON | 差 | 信里给他的（2026-08-26 生产实测） |")
    w("|---|---:|---:|---:|---:|")
    letter = {RISK_RED: 71, RISK_GAP: 27, RISK_YELLOW: 7, RISK_GREEN: 0}
    for k in (RISK_RED, RISK_GAP, RISK_YELLOW, RISK_GREEN):
        w(f"| {RISK_NAME[k]} | {c_off[k]} | {c_on[k]} | {c_on[k]-c_off[k]:+d} | {letter[k]} |")
    w(f"| **合计** | **{sum(c_off.values())}** | **{sum(c_on.values())}** | — | **105** |")
    w("")
    changed = [k for k in maps[("off", "now")]
               if maps[("off", "now")][k].kit_date != maps[("on", "now")][k].kit_date
               or maps[("off", "now")][k].risk != maps[("on", "now")][k].risk]
    later = [k for k in changed
             if maps[("off", "now")][k].kit_date and maps[("on", "now")][k].kit_date
             and maps[("on", "now")][k].kit_date > maps[("off", "now")][k].kit_date]
    w(f"**逐行变动**：{len(changed)} / {len(rows_now)} 行；其中**齐料日变晚的：{len(later)} 行**"
      f"（规则 1 只应让齐料日前移，这个数**必须是 0**，否则实现有问题）。")
    w("")

    # ── 四、阈值分布 ──────────────────────────────────────────────────────────
    w("## 四、保供看板分级阈值：按姚祖怡新阈值的行数分布（🔴变体口径🔴）")
    w("")
    for r1, label in (("off", "规则1 OFF（生产现状）"), ("on", "规则1 ON（他已签认要开）")):
        rows = runs[(r1, "now")]
        n_gt14 = sum(1 for r in rows if r.gap_days is not None and r.gap_days > 14)
        n_1_14 = sum(1 for r in rows if r.gap_days is not None and 1 <= r.gap_days <= 14)
        n_le0_u = sum(1 for r in rows if r.gap_days is not None and r.gap_days <= 0
                      and r.no_feedback_materials)
        n_le0_a = sum(1 for r in rows if r.gap_days is not None and r.gap_days <= 0
                      and not r.no_feedback_materials)
        n_nobom = sum(1 for r in rows if not r.has_bom)
        n_none_bom = sum(1 for r in rows if r.has_bom and r.gap_days is None)
        cur = _counts(rows)
        w(f"### {label}")
        w("")
        w("**现行四色（同一份变体输入，供对照）**：" +
          "　".join(f"{RISK_NAME[k]} {cur[k]}" for k in (RISK_RED, RISK_GAP, RISK_YELLOW, RISK_GREEN)) +
          f"　合计 {len(rows)}")
        w("")
        w("| 桶 | 判据 | 行数 |")
        w("|---|---|---:|")
        w(f"| A | 晚 **>14 天**（晚 2 周以上）⇒ 他定的 🔴 | **{n_gt14}** |")
        w(f"| B | 晚 **1–14 天**（晚 2 周以内）⇒ 他定的 🟡 | **{n_1_14}** |")
        w(f"| C | **不晚**（≤0）且有未答复子件（现行 🟠） | {n_le0_u} |")
        w(f"| D | **不晚**（≤0）且全部已答复（现行 🟢） | {n_le0_a} |")
        w(f"| E | **无 BOM**（现行一律 🔴，与晚不晚无关） | {n_nobom} |")
        w(f"| F | 有 BOM 但无待到货子件（齐料日为空，现行落 🟢） | {n_none_bom} |")
        w("")
        w("| 落法 | 🔴 | 🟡 | 🟠 | 🟢 |")
        w("|---|---:|---:|---:|---:|")
        w(f"| ① 只保留红黄两色 | {n_gt14 + n_nobom} | {n_1_14 + n_le0_u + n_le0_a + n_none_bom} | — | — |")
        w(f"| ② 红黄按他定，橙绿维持现行 | {n_gt14 + n_nobom} | {n_1_14} | {n_le0_u} | {n_le0_a + n_none_bom} |")
        w("")
    w("🔴 **他只给了两档，橙与绿怎么落他没说 —— 本表只把两种读法各自的行数摆出来，不替他选。**")

    out = "\n".join(lines)
    print("\n" + out)
    if args.out:
        Path(args.out).write_text(out + "\n", encoding="utf-8")
        print(f"\n已落盘：{args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
