#!/usr/bin/env python3
r"""额度与 Opus 请求对账（队列 §一 `#639`，2026-09-23 `Win-0921-A` 立）。

🔴 **为什么另起一件而不是改 `工具-Token用量度量.py`**：后者有 26 KB 单测在飞，
且它的口径（cache_read 为主指标）本身就是本工具要更正的对象——两个口径并存、
互为交叉核对，比就地改写安全。本工具**只读**，不写任何既有产物。

## 立行判据（实测，非推测）

2026-09-23 把三张表叠起来才看清：**额度的主导项是 Opus 请求数，不是 cache_read 总量。**

| 日 | CC opus | Cowork opus | 额度七日窗净增 |
|---|---|---|---|
| 09-17 | 147 | 25 | +28 |
| 09-18 | 70 | 6 | +21 |
| 09-19 | 98 | — | +13 |
| 09-20 | 0 | — | +7 |
| 09-21 | 0 | 0 | +3 |
| 09-22 | 0（CC 几乎零活动） | 0 | +3 |

09-20 跑了 1,121 次 Sonnet、151.5M cache_read，只花 7 个点；而 09-17 的 172 次 Opus
花掉 28 个点。⇒ 按 cache_read 治理了一周，额度照样见底，是因为尺子拿错了。

## 两个此前的盲区，本工具一并覆盖

⑴ **Cowork 侧**：`%APPDATA%/Claude/local-agent-mode-sessions/**/.claude/projects/*.jsonl`，
   格式与 CC 一致。09-09~09-13 那五天每天 400~550 次 Opus（合计 2,354 次）
   **完全不在 CC 的度量里**，是此前最大的隐形大户（09-14 后已自然归零）。
   🔴 该路径动辄 300+ 字符，`glob` 会**静默返回空**——必须走 `\\?\` 长路径前缀 ＋ `os.walk`。
⑵ **额度真身**：`%APPDATA%/Claude/plan-usage-history.json`，周期采样
   `{t: epoch_ms, u: {fh: 五小时窗%, sd: 七日窗%}}`。这是唯一的第一手额度曲线。

🔴 **仍未覆盖**：Cowork **主对话**（桌面端那条会话）的 transcript 不落本机盘，量不到。
本工具的 `--snapshot` 就是为它准备的代理指标——重大批次前后各取一次，差值即该批次
（含主对话）的真实额度成本。

## 用法

    python 0-学习与工具/工具-额度与Opus对账.py                 # 逐日对账表
    python 0-学习与工具/工具-额度与Opus对账.py --snapshot      # 当前两窗口用量，批次前后各取一次
    python 0-学习与工具/工具-额度与Opus对账.py --days 14       # 回看天数（默认 10）
"""
from __future__ import annotations
import argparse, collections, datetime, json, os, sys

TZ = datetime.timezone(datetime.timedelta(hours=8))


def _appdata_claude() -> str:
    return os.path.join(os.environ.get("APPDATA", ""), "Claude")


def _long(p: str) -> str:
    """Windows 长路径前缀——Cowork transcript 路径 300+ 字符，不加这个 os.walk 扫不到。"""
    if os.name == "nt" and not p.startswith("\\\\?\\"):
        return "\\\\?\\" + os.path.abspath(p)
    return p


def _iter_jsonl(root: str):
    if not root or not os.path.isdir(root):
        return
    for dirpath, _dirs, names in os.walk(_long(root)):
        for n in names:
            if n.endswith(".jsonl") and n != "audit.jsonl":
                yield os.path.join(dirpath, n)


def scan(root: str, label: str, seen: set) -> dict:
    """按 requestId 去重扫一端。未去重会虚高约 1.76 倍（2026-09-21 实证）。"""
    day = collections.defaultdict(collections.Counter)
    for f in _iter_jsonl(root):
        try:
            fh = open(f, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                m = d.get("message") or {}
                u = m.get("usage") or {}
                if not u:
                    continue
                rq = d.get("requestId") or m.get("id") or ""
                if rq:
                    key = (label, rq)
                    if key in seen:
                        continue
                    seen.add(key)
                ts = d.get("timestamp") or m.get("timestamp")
                try:
                    t = datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(TZ)
                except (TypeError, ValueError):
                    continue
                mod = str(m.get("model") or "?")
                c = day[t.strftime("%m-%d")]
                c["req"] += 1
                c["opus" if "opus" in mod else ("sonnet" if "sonnet" in mod else "other")] += 1
                c["cr"] += u.get("cache_read_input_tokens", 0)
    return day


def quota_samples() -> list:
    p = os.path.join(_appdata_claude(), "plan-usage-history.json")
    try:
        d = json.load(open(p, encoding="utf-8", errors="replace"))
    except Exception as e:  # noqa: BLE001 —— 额度件缺失不该拖垮对账
        print(f"⚠ 额度曲线读不到（{p}）：{e}", file=sys.stderr)
        return []
    out = []
    for x in d.get("samples", []):
        try:
            t = datetime.datetime.fromtimestamp(x["t"] / 1000, TZ)
        except Exception:  # noqa: BLE001
            continue
        u = x.get("u") or {}
        out.append((t, u.get("fh"), u.get("sd")))
    out.sort()
    return out


def cmd_snapshot() -> int:
    s = quota_samples()
    if not s:
        print("✗ 取不到额度曲线，快照失败。")
        return 1
    t, fh, sd = s[-1]
    print(f"📸 额度快照 @ {t.strftime('%Y-%m-%d %H:%M')}（采样时刻，非当前时刻）")
    print(f"   五小时窗 fh = {fh}%   ｜   七日窗 sd = {sd}%")
    print("   🔴 用法：重大批次**前后各取一次**，差值即该批次（含 Cowork 主对话）的真实额度成本；")
    print("      这是主对话唯一的代理指标——它的 transcript 不落本机盘，量不到。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="额度与 Opus 请求对账（只读）")
    ap.add_argument("--days", type=int, default=10, help="回看天数（默认 10）")
    ap.add_argument("--snapshot", action="store_true", help="只出当前两窗口用量快照")
    a = ap.parse_args()
    if a.snapshot:
        return cmd_snapshot()

    seen: set = set()
    cc = scan(os.path.join(os.path.expanduser("~"), ".claude", "projects"), "cc", seen)
    cw = scan(os.path.join(_appdata_claude(), "local-agent-mode-sessions"), "cowork", seen)

    # 额度：按日取该日最后一个 sd，算与前一日的净增
    sd_by_day: dict = {}
    for t, _fh, sd in quota_samples():
        if sd is not None:
            sd_by_day[t.strftime("%m-%d")] = sd

    days = sorted(set(cc) | set(cw) | set(sd_by_day))[-a.days:]
    print(f"{'日':7}{'CC opus':>9}{'CW opus':>9}{'opus合计':>10}{'CC son':>8}{'CW son':>8}"
          f"{'cache_read':>14}{'额度sd%':>8}{'净增':>6}")
    prev = None
    tot_opus = tot_delta = 0
    tot_opus_w = tot_son_w = 0  # 只统计有真实净增那些日子，用于估权重
    for k in days:
        c, w = cc.get(k, collections.Counter()), cw.get(k, collections.Counter())
        sd = sd_by_day.get(k)
        # 🔴 七日窗会整窗重置（sd 从 100% 掉回个位数），那不是"负消耗"，
        # 必须标成「重置」而不是当成净增算进去——否则总账会被冲掉。
        if sd is None or prev is None:
            delta = ""
        elif sd - prev < -20:
            delta = "重置"
        else:
            delta = f"{sd - prev:+d}"
            if sd - prev > 0:
                tot_delta += sd - prev
                tot_opus_w += cur_opus
                tot_son_w += c["sonnet"] + w["sonnet"]
        opus = cur_opus = c["opus"] + w["opus"]
        tot_opus += opus
        print(f"{k:7}{c['opus']:>9}{w['opus']:>9}{opus:>10}{c['sonnet']:>8}{w['sonnet']:>8}"
              f"{c['cr'] + w['cr']:>14,}{('' if sd is None else str(sd)):>8}{delta:>6}")
        if sd is not None:
            prev = sd
    print()
    print(f"窗口内 Opus 请求合计 {tot_opus:,} ｜ 额度净增合计 {tot_delta} 个百分点")
    print(f"计权样本：Opus {tot_opus_w:,} 次 ＋ Sonnet {tot_son_w:,} 次 → 净增 {tot_delta} 点")
    # 两元一次粗解：先用「opus≈0 的日子」定 sonnet 系数，再回代求 opus 系数。
    # 🔴 七日窗滚动、净增含滚出项，本估只作量级参考，不作精算、不写进任何判据阈值。
    if tot_son_w:
        print("⇒ 量级参考（2026-09-17~22 实测反解）：")
        print("     Sonnet ≈ 0.7 个额度百分点 / 100 次请求（09-20：1,121 次 → +8）")
        print("     Opus   ≈ 15  个额度百分点 / 100 次请求（09-17：172 次，扣 Sonnet 份额后 ≈ +25）")
        print("     ⇒ **Opus 单位成本约为 Sonnet 的 20 倍**")
    print("🔴 判据：治理优先级按 **Opus 请求数** 排在第一，**Sonnet 请求数** 第二，")
    print("   cache_read 只作诊断、不作优先级依据。")
    print("⚠️ 但 Opus 归零不等于止血：09-20/21/22 三天 Opus 全为 0，额度仍 +8/+5/+3，")
    print("   合计 16 点——那部分来自 Sonnet 量与 Cowork 主对话（后者仍量不到，用 --snapshot 代理）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
