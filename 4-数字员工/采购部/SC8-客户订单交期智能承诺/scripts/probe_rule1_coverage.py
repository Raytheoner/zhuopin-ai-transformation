"""实测现行程序是否已覆盖姚祖怡的规则 1／2／3（队列 #344 行内并入的待办，**只测不改**）。

来源＝采购部#15 正文对他的书面承诺原话：「确认之后，我们会实测现在的程序是不是已经
覆盖了规则 1，没覆盖就改」。他已于 2026-08-18 确认「20 日 ＝ 那个自然月的 20 号」。

> **规则 1（出货日不在三个月内）**：无答交按出货日往前推 3 个月的 **20 日**起、再往后推 90 天。
> **规则 2（出货日在三个月内）**：无答交按此时此刻起往后推 90 天。
> **规则 3（同一项目既有答交又有无答交）**：取两者中**更晚**的那一个作齐套日期。

🔴 **本脚本只做测量，不改任何判定**——规则 1／2 改的是**无答交启发式的起算点**，与
队列 #344 改的**有答交累计取值**是两层不同的判据；混进同一个变更包会让「修复前后对照
表」同时含两个自变量，谁也说不清哪一行是被哪一条改动搬动的。

离线跑，吃 `compare_kit_date_cumulative.py --cache` 冻结下来的那份真实输入，零网络请求。

用法：
    python scripts/probe_rule1_coverage.py --cache <冻结的 inputs.json>
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, _HERE.parent.parent)  # noqa: E402

NO_FEEDBACK_LEAD_DAYS = 90


def _minus_3_months_20th(ship: date) -> date:
    """规则 1 的起算点：出货日往前推 3 个月的那个自然月的 20 号（他 08-18 确认的读法）。"""
    idx = ship.month - 1 - 3
    yy = ship.year + (idx // 12)
    mm = idx % 12 + 1
    return date(yy, mm, 20)


def _within_three_months(today: date, ship: date) -> bool:
    """「出货日在三个月内」——按自然月推 3 个月，与规则 1 的推法互为反面，口径一致。"""
    idx = today.month - 1 + 3
    yy = today.year + (idx // 12)
    mm = idx % 12 + 1
    day = min(today.day, 28)      # 避免 31 号推到不存在的日期；边界差一天不影响结论量级
    return ship <= date(yy, mm, day)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True, help="冻结的真实输入 JSON")
    ap.add_argument("--out", default="", help="落盘路径（.md）")
    args = ap.parse_args()

    p = json.loads(Path(args.cache).read_text(encoding="utf-8"))
    orders = p["orders"]
    today = date.today()

    lines: list[str] = []
    w = lines.append
    w(f"**业务日期**：{today.isoformat()}（本机本地日）　**预测订单行**：{len(orders)}")
    w("")
    w("### 结论速览")
    w("")
    w("| 规则 | 现行代码 | 是否已覆盖 | 差异方向 |")
    w("|---|---|---|---|")
    w("| **规则 3**（有答交／无答交取更晚） | `kit_date = max(mat.arrivals.values())`，"
      "而 `arrivals` 同时含「已答交的到货日」与「无答交的估算日」 | **✅ 已覆盖** | 无 |")
    w("| **规则 2**（出货日在三个月内 ⇒ 此刻 +90） | "
      "`effective_demand = max(出货日, 今天)` 再 +90 | **⚠️ 部分覆盖** | "
      "出货日**已过期**时 ＝ 今天+90，**与规则 2 逐字一致**；出货日在未来但仍在三个月内时 "
      "＝ 出货日+90，**比规则 2 晚**（偏保守，不会低估） |")
    w("| **规则 1**（出货日在三个月外 ⇒ 前推 3 个月的 20 日 +90） | 同上，仍是出货日 +90 | "
      "**❌ 未覆盖** | 现行**比规则 1 晚得多**（偏保守，不会低估） |")
    w("")

    far, near, past = [], [], []
    for o in orders:
        ship = date.fromisoformat(o["required_date"])
        (past if ship <= today else (near if _within_three_months(today, ship) else far)).append(o)

    w("### 影响面（本次真实快照）")
    w("")
    w(f"- 出货日**已过期**（≤ 今天）：**{len(past)}** 行 ⇒ 现行 ＝ 今天+90，**与规则 2 逐字一致**，无差异。")
    w(f"- 出货日在**未来、且在三个月内**：**{len(near)}** 行 ⇒ 规则 2 适用，现行比规则 2 晚。")
    w(f"- 出货日在**三个月之外**：**{len(far)}** 行 ⇒ 规则 1 适用，现行比规则 1 晚。")
    w("")

    if far:
        w("#### 规则 1 适用行的逐行差值（现行 vs 规则 1，仅无答交子件才用得上这个估算日）")
        w("")
        w("| 预测单 | 成品 | 出货日 | 现行估算日 | 规则 1 估算日 | 差（天） |")
        w("|---|---|---|---|---|---:|")
        rows = []
        for o in far:
            ship = date.fromisoformat(o["required_date"])
            cur = max(ship, today) + timedelta(days=NO_FEEDBACK_LEAD_DAYS)
            r1 = _minus_3_months_20th(ship) + timedelta(days=NO_FEEDBACK_LEAD_DAYS)
            rows.append((o["so_id"], o["item_code"], ship, cur, r1, (cur - r1).days))
        rows.sort(key=lambda r: -r[5])
        for so, item, ship, cur, r1, diff in rows[:15]:
            w(f"| {so} | {item} | {ship} | {cur} | {r1} | {diff:+d} |")
        if len(rows) > 15:
            w(f"| … | 另 {len(rows)-15} 行 | | | | |")
        diffs = [r[5] for r in rows]
        w("")
        w(f"差值范围 **{min(diffs):+d} ~ {max(diffs):+d}** 天，"
          f"中位 **{sorted(diffs)[len(diffs)//2]:+d}** 天。"
          f"**全部为正 ⇒ 现行一律比规则 1 晚**（保守方向）。" if all(d > 0 for d in diffs)
          else f"差值范围 **{min(diffs):+d} ~ {max(diffs):+d}** 天，**存在负值 ⇒ 现行有比规则 1 更早的行**。")

    w("")
    w("### 🔴 为什么本变更包不顺手把规则 1 一起改掉")
    w("")
    w("1. **方向与 #344 相反。** #344 修的是「齐料日被低估」（红的会变多）；规则 1 会把无答交"
      "子件的估算日**往前挪**（红的会变少）。两者塞进同一次上线，看板上一行由绿转红或由红转绿，"
      "**没有人能说清是被哪一条改动搬动的**——包括我们自己。")
    w("2. **现行是偏保守的一侧。** 上表全部差值为正，说明现行估得比他的规则更晚、更悲观。"
      "先修「会让人低估风险」的那一条，再谈「让人不必过度悲观」的这一条，次序对得起"
      "「先修错的、再加新的」。")
    w("3. **它是一条独立的判据，值一个自己的变更包。** 规则 1 引入了「出货日是否在三个月内」"
      "这个此前完全不存在的分支，还带着一个「20 日」的魔法常量——它该有自己的 design 审、"
      "自己的判例佐证、自己的前后对照表。")
    w("")
    w("**⇒ 建议另立队列行排期。本项无默认，须 Shao Peishen 决定。**"
      "他 2026-08-18 的确认只覆盖了「20 日怎么读」，**没有覆盖「什么时候做」**。")

    out = "\n".join(lines)
    print(out)
    if args.out:
        Path(args.out).write_text(out + "\n", encoding="utf-8")
        print(f"\n已落盘：{args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
