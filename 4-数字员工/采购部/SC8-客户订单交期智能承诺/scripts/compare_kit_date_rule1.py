"""队列 #401 修复前后对照 runner —— 同一份真实输入，跑两遍 `build_dashboard`。

用途：量出「无答交启发式起算点改按姚祖怡规则 1 取值」对四色判定的**真实**影响面，
出一张随采购部#19 请他复核的对照表（队列 §一 #402）。

  · **修复前** ＝ `SC8_KIT_DATE_RULE1=off`（起算点恒为 `max(出货日, 今天)`）
  · **修复后** ＝ `SC8_KIT_DATE_RULE1=on`（起算点走 `forecast.no_feedback_start_date`）

🔴 **本脚本用生产代码里那个真开关翻转，不用 monkeypatch**（与 #344 的
`compare_kit_date_cumulative.py` 刻意相反）：那次的「修复前」在生产码里不该留开关，
所以只能靠猴补；本次开关是**已批准的、要一直留着的交付物**（同 `SC8_NET_INVENTORY`，
默认 OFF、待他复核对照表后才翻 ON），对照跑的就该是它本身——否则对照的是一套代码、
上线的是另一套。

🔴 **必须用生产载荷跑**：`.51` 的 `C:\\baoguan\\.env` 里 `SC8_NET_INVENTORY=on`，
仓库根 `.env` 没有这个键、默认 OFF ⇒ 本机裸跑会静默走另一套口径、数字对不上生产。
启动时会把实际生效的开关打印出来并硬拦，不靠"我记得设过"。

⚠️ **`SC8_KIT_DATE_RULE1` 由本脚本自己两次设定，命令行上不要带它**——带了也会被覆盖，
但会让读日志的人以为跑的是单侧。

用法（笔记本 LAN 内，回网段后一条命令）：
    SC8_NET_INVENTORY=on python scripts/compare_kit_date_rule1.py \
        --cache "%TEMP%/sc8_rule1_inputs.json" \
        --srm-cache <C:\\baoguan\\app\\reports\\srm_answer_cache.json 的本地副本> \
        --out docs/queue_401_kit_date规则1修复前后对照-<日期>.md

复跑（已冻结过输入，零网络请求、秒级）：
    SC8_NET_INVENTORY=on python scripts/compare_kit_date_rule1.py \
        --cache "%TEMP%/sc8_rule1_inputs.json" --out <同上>
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

from sc8 import config, forecast  # noqa: E402
from sc8.baoguan import (RISK_GAP, RISK_GREEN, RISK_RED, RISK_YELLOW,  # noqa: E402
                         build_dashboard)
from sc8.sources import (_fetch_line_status, load_material_commitments,  # noqa: E402
                         load_purchase_orders_by_material, load_real_bom,
                         load_real_orders, load_srm_deliveries)

RISK_NAME = {RISK_RED: "🔴真延期", RISK_GAP: "🟠待催", RISK_YELLOW: "🟡偏紧", RISK_GREEN: "🟢按期"}
ENV_KEY = "SC8_KIT_DATE_RULE1"


def _find_dotenv() -> Path | None:
    """【已收拢，保留为薄封装】返回本次运行该用的那份 `.env`（解析见 `env_anchor`，#354）。

    🔴 原注释「worktree 里没有 `.env`，会一路走到主工作区」**依赖一个会变的事实**：一旦某个
    worktree 里出现 `.env` 副本（2026-08-18 真实发生过、且陈旧两代），本写法立刻命中它、
    且不报错。收拢后靠 `--git-common-dir` 规范化，与「那儿碰巧没有文件」无关。
    """
    return _resolve_env_file(__file__).path


def _load_dotenv(path: Path | None) -> None:
    """把 `.env` 读进 `os.environ`（不覆盖已设的键）——与服务进程同源凭据。

    参数保留是为了不动 `main()` 的既有调用序列；实际解析与读取都在 `env_anchor` 里完成。
    """
    _resolve_and_load_env(__file__)


def _dump_inputs(path: Path, orders, bom, srm, inventory, purchase_orders, commitments) -> None:
    """冻结一次真实取数，供复跑。格式与 `compare_kit_date_cumulative.py` **完全一致**，
    两个脚本的 `--cache` 文件可互换复用（同一份真实输入下两条改动各自的影响面才可比）。

    ⚠️ 落到**仓库外**：含真实客户名与真实料号，同 `data/golden/real_frozen/` 不入库的约定。
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


def _run_with_switch(value: str, orders, bom, srm, kw):
    """在指定开关位置下跑一遍 `build_dashboard`，跑完把环境恢复原样。"""
    prev = os.environ.get(ENV_KEY)
    os.environ[ENV_KEY] = value
    try:
        assert config.kit_date_rule1_enabled() is (value == "on"), \
            f"{ENV_KEY}={value} 未生效——开关读取路径变了，对照无意义"
        return build_dashboard(orders, bom, srm, **kw)
    finally:
        if prev is None:
            os.environ.pop(ENV_KEY, None)
        else:
            os.environ[ENV_KEY] = prev


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
    print(f"   SC8_NET_INVENTORY = {'on' if config.net_inventory_enabled() else 'OFF'}   ← 生产为 on")
    print(f"   SC8_PO_TRANSIT    = {'on' if config.po_transit_enabled() else 'OFF'}   ← 生产为 on（默认）")
    print(f"   SC8_BOM_MAX_DEPTH = {config.bom_max_depth()}   ← 生产为 5（默认）")
    print(f"   {ENV_KEY} = 本脚本自行两次翻转（off / on），命令行传值无效")
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
        srm = load_srm_deliveries("real", materials=components,
                                  cache_path=args.srm_cache or None,
                                  ttl_sec=(6 * 3600 if args.srm_cache else 0))
        commitments = load_material_commitments("real", materials=components)
        if cache:
            _dump_inputs(cache, orders, bom, srm, inventory, purchase_orders, commitments)
            print(f"   已冻结真实输入 → {cache}")
    print(f"   SRM 承诺记录 {len(srm)} ／ 逐笔答交明细覆盖 {len(commitments)} 个物料 "
          f"／ 在途 PO 覆盖 {len(purchase_orders)} 个物料")

    kw = dict(today=today, inventory=inventory, purchase_orders=purchase_orders,
              material_commitments=commitments)

    print(f"\n== 跑两遍 build_dashboard（{ENV_KEY} off ／ on）==")
    before = _run_with_switch("off", orders, bom, srm, kw)
    after = _run_with_switch("on", orders, bom, srm, kw)

    def counts(rows):
        return {k: sum(1 for r in rows if r.risk == k)
                for k in (RISK_RED, RISK_GAP, RISK_YELLOW, RISK_GREEN)}

    cb, ca = counts(before), counts(after)
    key = lambda r: (r.so_id, r.product_id, r.ship_date)   # noqa: E731
    bmap = {key(r): r for r in before}
    amap = {key(r): r for r in after}
    assert set(bmap) == set(amap), "两遍的行集合必须完全一致，否则对照无意义"

    # 规则 1／规则 2 各自的适用面（口径与引擎同一函数，不在这里另写一遍判断）
    p = config.default_params()
    rule1_keys, rule2_future, rule2_past = [], [], []
    for k, row in amap.items():
        ship = row.ship_date if isinstance(row.ship_date, date) else date.fromisoformat(str(row.ship_date))
        if not forecast.ship_within_horizon(today, ship, p):
            rule1_keys.append(k)
        elif ship > today:
            rule2_future.append(k)
        else:
            rule2_past.append(k)

    changed = [(bmap[k], amap[k]) for k in bmap
               if bmap[k].risk != amap[k].risk or bmap[k].kit_date != amap[k].kit_date
               or bmap[k].bottleneck_material != amap[k].bottleneck_material]
    changed.sort(key=lambda pair: (pair[1].risk, pair[1].so_id, pair[1].product_id))
    lines: list[str] = []
    w = lines.append
    w(f"**业务日期**：{today.isoformat()}（本机本地日）　**预测订单行**：{len(orders)}　"
      f"**叶子件**：{len(components)}　**逐笔答交明细覆盖**：{len(commitments)} 个物料")
    w("")
    w("### 分支适用面")
    w("")
    w("| 分支 | 判据 | 行数 | 本次是否改动 |")
    w("|---|---|---:|---|")
    w(f"| **规则 1** | 出货日**不在**三个月内 ⇒ 起算＝出货日前推 3 个月那月 20 日 | "
      f"{len(rule1_keys)} | ✅ **本次改的就是这一支** |")
    w(f"| 规则 2（未来） | 出货日在三个月内且晚于今天 ⇒ 现行仍取出货日（比规则 2 逐字更晚、偏保守） | "
      f"{len(rule2_future)} | ❌ 本次不动（见下方「本次刻意没改什么」）|")
    w(f"| 规则 2（已过期） | 出货日 ≤ 今天 ⇒ 起算＝今天，与规则 2 逐字一致 | "
      f"{len(rule2_past)} | ❌ 本次不动（本就一致）|")
    w("")
    w("### 四色计数")
    w("")
    w("| 风险 | 修复前 | 修复后 | 差 |")
    w("|---|---:|---:|---:|")
    for k in (RISK_RED, RISK_GAP, RISK_YELLOW, RISK_GREEN):
        w(f"| {RISK_NAME[k]} | {cb[k]} | {ca[k]} | {ca[k]-cb[k]:+d} |")
    w(f"| **合计** | **{sum(cb.values())}** | **{sum(ca.values())}** | — |")
    w("")
    w(f"### 逐行变动（{len(changed)} / {len(bmap)} 行）")
    w("")
    if not changed:
        w("（本次快照下无任何行发生变动）")
    else:
        w("| 预测单 | 成品 | 出货日 | 齐料日（前→后） | 提前天数 | 瓶颈物料（前→后） | 四色（前→后） |")
        w("|---|---|---|---|---:|---|---|")
        for b, a in changed:
            adv = ((b.kit_date - a.kit_date).days
                   if b.kit_date and a.kit_date else None)
            kd = (f"{b.kit_date or '—'} → **{a.kit_date or '—'}**"
                  if b.kit_date != a.kit_date else str(b.kit_date or "—"))
            bn = (f"{b.bottleneck_material or '—'} → **{a.bottleneck_material or '—'}**"
                  if b.bottleneck_material != a.bottleneck_material
                  else (b.bottleneck_material or "—"))
            rk = (f"{RISK_NAME[b.risk]} → **{RISK_NAME[a.risk]}**"
                  if b.risk != a.risk else RISK_NAME[b.risk])
            w(f"| {b.so_id} | {b.product_id} | {b.ship_date} | {kd} | "
              f"{'' if adv is None else f'{adv:+d}'} | {bn} | {rk} |")
    w("")
    w("### 🔴 不变式自检（这三条若有一条不成立，本次改动就是错的）")
    w("")
    off_rule1 = [key(a) for _, a in changed if key(a) not in set(rule1_keys)]
    later = [key(a) for b, a in changed
             if b.kit_date and a.kit_date and a.kit_date > b.kit_date]
    w(f"1. **只有规则 1 适用行会变**：变动行中落在规则 1 之外的 —— **{len(off_rule1)} 行**"
      f"{'（✅ 符合预期）' if not off_rule1 else '　🔴 **不符合预期，须查**：`' + '`、`'.join(map(str, off_rule1[:10])) + '`'}")
    w(f"2. **齐料日只会前移、不会后移**：变动行中齐料日变晚的 —— **{len(later)} 行**"
      f"{'（✅ 符合预期）' if not later else '　🔴 **不符合预期，须查**'}")
    w(f"3. **红只会变少、不会变多**：🔴 计数 {cb[RISK_RED]} → {ca[RISK_RED]}"
      f"（{ca[RISK_RED]-cb[RISK_RED]:+d}）"
      f"{'　✅ 符合预期' if ca[RISK_RED] <= cb[RISK_RED] else '　🔴 **不符合预期，须查**'}")
    w("")
    w("### 本次刻意没改什么")
    w("")
    w("**规则 2 的「部分覆盖」原样保留**：出货日在未来但仍在三个月内的那批行，现行起算点是"
      "**出货日**、而他的规则 2 逐字是**此时此刻**，现行更晚、偏保守。§四 #111 拍板 (a) 的"
      "标的是**规则 1**；顺手把规则 2 一起改，这张对照表就同时含两个自变量，"
      "**哪一行是被哪一条搬动的谁也说不清**——那正是 #344 当初拒绝顺手改规则 1 的理由，"
      "不能反过来自己犯。已登记为独立待办（队列 §一 #401 收工回写）。")

    out = "\n".join(lines)
    print("\n" + out)
    if args.out:
        Path(args.out).write_text(out + "\n", encoding="utf-8")
        print(f"\n已落盘：{args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
