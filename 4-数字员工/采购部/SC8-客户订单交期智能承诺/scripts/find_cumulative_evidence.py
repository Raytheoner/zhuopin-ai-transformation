"""为判例 2／判例 3 补一条**真实**的多笔累计案例（队列 #344 行内并入的待办）。

背景：采购部#16 的判例 3 整条、判例 2 的需求量，都是**假设数**——违反「判例包不得
使用虚构数据」这条既有硬约束。Shao Peishen 2026-08-20 答 §四 #70 选 (c)：签认认定
有效、瑕疵留痕不重问，**改为补一条真实的多笔累计案例作事后佐证**。

为什么以前找不到：全库 8 处真实留档逐份核过，**无一合格**——「缺口量」与「逐笔答交」
从未在同一份快照里配过对，据旧表编的判例今天复现不出来（真实答交按月滚动）。

省事路径（队列 #344 行内已核实）：`material_board.build_material_board` 的每一行**已经
同时携带** `total`（窗口合计缺口）与 `cb`（按 `total` 累计截断的逐笔答交），筛
`len(cb)>=2 且 cb[0].q < total 且 sum(q) >= total` 即得真实候选，**无需新写取数逻辑**。

数据源＝**生产 `.51:8091` 的 `/api/materials` 实时载荷**（不是本机重算）：一来那才是
姚祖怡打开看板看到的同一份数字，二来零额外 ERP 请求（1600 次 HTTP／约 2 分钟的开销
不该为找一条判例再付一遍）。

用法：
    python scripts/find_cumulative_evidence.py [--top 5] [--out <md路径>]
"""
from __future__ import annotations

import argparse
import json
import os

import sys
import urllib.error

import urllib.request
from pathlib import Path

_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, _HERE.parent.parent)  # noqa: E402

from zhuopin_platform.env_anchor import parse_env_file, resolve_env_file  # noqa: E402

BOARD_URL = "http://192.168.100.51:8091"


def _gate_password() -> str:
    """门禁口令（队列 #160 共享口令 + Cookie 门禁）。

    🔴 **取不到就抛，绝不用空串继续**：`install_flask_gate` 对未授权请求返回的是
    **HTTP 200 + 登录页 HTML**，不是 401 —— 空口令跑下去只会在 `json.loads` 那里
    炸出一句莫名其妙的 `JSONDecodeError`，而真正的原因（没带口令）被埋掉。
    这正是"工具静默回退"那一族：请求看起来成功了，拿到的却根本不是那个对象。

    ⚠️ 口令**只在 `.51` 的 `C:\\baoguan\\.env` 里**，仓库根 `.env` 没有这个键
    （同"开关类环境变量只在 .51 不在仓库根"）。故须显式传入：
        ZP_GATE_PASSWORD=... python scripts/find_cumulative_evidence.py
    """
    if os.environ.get("ZP_GATE_PASSWORD"):
        return os.environ["ZP_GATE_PASSWORD"]
    # 凭据锚定收拢（队列 #354）：原写法是「向上逐级找最近的 `.env`、逐行前缀匹配」，从
    # linked worktree 跑时会命中该 worktree 的陈旧副本且不报错。改走唯一解析入口；
    # 解析口径（首个 `=` 切分、去一层引号）也随之与其余 12 处一致——原先的
    # `line.split("=", 1)[1]` 不去引号，`.env` 里若给这个键加了引号就会带着引号去撞登录页。
    hit = resolve_env_file(__file__).path
    if hit is not None:
        password = parse_env_file(hit).get("ZP_GATE_PASSWORD")
        if password:
            return password
    raise RuntimeError(
        "未取到 ZP_GATE_PASSWORD —— 它只在 .51 的 C:\\baoguan\\.env 里，仓库根没有。"
        "请显式设环境变量再跑，不要让脚本带空口令去撞登录页。")


def _fetch_materials() -> dict:
    """取生产 `/api/materials`。门禁走 `X-Auth-Token` 头（`simple_gate.install_flask_gate`
    支持的无状态入口），不落 Cookie 文件、不改服务器上任何东西。"""
    req = urllib.request.Request(
        f"{BOARD_URL}/api/materials",
        headers={"Accept": "application/json", "X-Auth-Token": _gate_password()})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode("utf-8")
    if not raw.lstrip().startswith("{"):
        # 门禁未通过时返回的是 200 + 登录页 HTML；不让它以 JSONDecodeError 的形态出现。
        raise RuntimeError("拿到的不是 JSON（多半是门禁登录页）——口令无效或未生效")
    return json.loads(raw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=5, help="最多列出几条候选")
    ap.add_argument("--out", default="", help="落盘路径（.md）；缺省只打印")
    args = ap.parse_args()

    try:
        payload = _fetch_materials()
    except urllib.error.HTTPError as e:
        print(f"🔴 取生产 /api/materials 失败：HTTP {e.code}"
              f"（门禁口令可能未取到；本脚本刻意不猜、不重试）")
        return 2
    except Exception as e:                                      # noqa: BLE001
        print(f"🔴 取生产 /api/materials 失败：{type(e).__name__}: {e}")
        return 2

    rows = payload.get("rows") or payload.get("materials") or []
    meta = payload.get("meta") or payload.get("materials_meta") or {}
    ts = payload.get("ts") or payload.get("generated_at") or "（载荷未带时间戳）"
    print(f"生产载荷：{len(rows)} 行　窗口 {meta.get('window', '?')}　快照时刻 {ts}")

    hits = []
    for r in rows:
        cb = r.get("cb") or []
        total = float(r.get("total") or 0.0)
        if len(cb) < 2 or total <= 0:
            continue
        first = float(cb[0].get("q") or 0.0)
        summed = sum(float(b.get("q") or 0.0) for b in cb)
        if first < total <= summed:
            hits.append((r, cb, total, first, summed))

    # 优先挑「第一笔就有量、且不止一笔有量」的——那才是判例 3 要问的那种形态；
    # 第一笔为 0 的虽然也满足筛选式，但它同时命中口径 ⑷，会让判例问两件事。
    hits.sort(key=lambda h: (float(h[1][0].get("q") or 0.0) <= 0,
                             -len([b for b in h[1] if float(b.get("q") or 0) > 0])))

    lines: list[str] = []
    w = lines.append
    w(f"**生产载荷时刻**：{ts}　**窗口**：{meta.get('window', '?')}　"
      f"**扫描行数**：{len(rows)}　**命中**：{len(hits)}")
    w("")
    if not hits:
        w("🔴 **本次快照下零命中** —— 不能据此断言「真实世界里没有多笔累计的案例」，"
          "只能说**这一刻的三个月窗口内没有**。答交按月滚动，换一天再跑可能就有。"
          "在拿到真实案例之前，判例 2／判例 3 的假设数瑕疵**维持留痕、不假装已补齐**。")
    else:
        w("| # | 料号 | 品名 | 三月合计缺口 | 逐笔答交（累计截断后） | 覆盖发生在 |")
        w("|---|---|---|---:|---|---|")
        for i, (r, cb, total, first, summed) in enumerate(hits[:args.top], 1):
            seq = " ＋ ".join(f"{b['d']} 给 {float(b['q']):,.0f}" for b in cb)
            w(f"| {i} | `{r['id']}` | {r.get('name', '')} | {total:,.0f} | {seq} | "
              f"**{cb[-1]['d']}**（累计 {summed:,.0f} ≥ {total:,.0f}） |")
        w("")
        r0, cb0, t0, _f0, s0 = hits[0]
        w(f"⇒ **可直接替换判例 3 的真实案例**：`{r0['id']}`——三个月合计缺口 {t0:,.0f}，"
          f"第一笔 {cb0[0]['d']} 只给 {float(cb0[0]['q']):,.0f}（**不够**），"
          f"累计到 {cb0[-1]['d']} 才够（{s0:,.0f}）⇒ 齐料日取 **{cb0[-1]['d']}**。")

    out = "\n".join(lines)
    print("\n" + out)
    if args.out:
        Path(args.out).write_text(out + "\n", encoding="utf-8")
        print(f"\n已落盘：{args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
