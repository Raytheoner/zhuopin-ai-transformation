#!/usr/bin/env python3
r"""泳道现况一屏观察器（只读，队列 §一 `#639`，2026-09-23 `Win-0921-A` 立）。

🔴 **为什么要有这一件**：观察四条并行泳道此前要连发 5 条命令（列批次目录／读
summary／读 context-meter／查 worktree／取额度快照）。在 Cowork 主对话里，
**每一条命令就是一次 API 请求**——按 2026-09-23 实测反解，Opus ≈ 15 个额度百分点
/100 次请求、Sonnet ≈ 0.7。把 5 次折叠成 1 次，本身就是本轮治理要落的东西。

只读、零副作用：不写任何文件、不碰 git、不动锁。

    python 0-学习与工具/工具-泳道观察.py
    python 0-学习与工具/工具-泳道观察.py --batches 6
"""
from __future__ import annotations
import argparse, datetime, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(p: str, limit: int | None = None) -> str:
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.read(limit) if limit else f.read()
    except OSError:
        return ""


def batches(n: int) -> list:
    d = os.path.join(ROOT, "reports", "opener-batch")
    if not os.path.isdir(d):
        return []
    items = [(os.path.getmtime(os.path.join(d, x)), x) for x in os.listdir(d)
             if os.path.isdir(os.path.join(d, x))]
    items.sort(reverse=True)
    return [x for _t, x in items[:n]]


def main() -> int:
    ap = argparse.ArgumentParser(description="泳道现况一屏观察（只读）")
    ap.add_argument("--batches", type=int, default=4, help="回看最近几个批次（默认 4）")
    a = ap.parse_args()

    now = datetime.datetime.now()
    print(f"⏱ {now.strftime('%Y-%m-%d %H:%M:%S')}  泳道现况（只读，本工具零副作用）")

    # ① 各批次状态
    bd = os.path.join(ROOT, "reports", "opener-batch")
    live_sids = {}
    for b in batches(a.batches):
        p = os.path.join(bd, b)
        ex = _read(os.path.join(p, "exit.txt")).strip()
        state = f"EXIT={ex}" if ex else "在跑"
        print(f"\n▸ {b}  [{state}]")
        summ = _read(os.path.join(p, "summary.txt"))
        if summ.strip():
            for ln in summ.splitlines():
                if ln.strip() and not ln.startswith("SENTINEL") and not ln.startswith("SKIPPED"):
                    print("   " + ln.rstrip())
        else:
            # 还没 summary：从各泳道日志首行抠 session 与起跑时刻
            for fn in sorted(os.listdir(p)):
                if not fn.endswith(".log") or fn.startswith("launcher"):
                    continue
                head = _read(os.path.join(p, fn), 2000)
                m = re.search(r"session=([0-9a-f-]{36}).*?start=(\S+)", head, re.S)
                if m:
                    sid, st = m.group(1), m.group(2)
                    live_sids[sid] = fn[:-4]
                    print(f"   {fn[:-4]:<22} session={sid[:8]}  start={st[-8:]}")

    # ② 各在跑泳道当前上下文（闸的读数，15 秒轮询、系统性偏低，见队列 #639）
    cm = os.path.join(ROOT, "reports", "context-meter")
    if os.path.isdir(cm):
        rows = []
        for fn in os.listdir(cm):
            if not fn.endswith(".json"):
                continue
            fp = os.path.join(cm, fn)
            age = (datetime.datetime.now().timestamp() - os.path.getmtime(fp)) / 60
            if age > 30:
                continue
            try:
                j = json.loads(_read(fp) or "{}")
            except ValueError:
                continue
            rows.append((fn[:8], j.get("lastContext") or 0, age))
        if rows:
            print("\n▸ 在跑泳道上下文（闸读数；15 秒轮询有系统性低估，队列 §一 `#639`）")
            for sid, ctx, age in sorted(rows, key=lambda r: -r[1]):
                lane = live_sids.get(
                    next((k for k in live_sids if k.startswith(sid)), ""), "")
                flag = "🔴越250k" if ctx >= 250000 else ("🟡越150k" if ctx >= 150000 else "🟢")
                print(f"   {sid}  {ctx:>9,}  {flag}  {lane}  （{age:.0f} 分钟前）")

    # ③ 额度快照
    print()
    try:
        out = subprocess.run(
            [sys.executable, os.path.join(ROOT, "0-学习与工具", "工具-额度与Opus对账.py"), "--snapshot"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        for ln in (out.stdout or "").splitlines()[:2]:
            print(ln)
    except Exception as e:  # noqa: BLE001
        print(f"⚠ 额度快照取不到：{e}")

    # ④ 异常 worktree（名字不像 opNNNNx-slug 的，多半是参数解析错位造出来的）
    try:
        out = subprocess.run(["git", "worktree", "list"], cwd=ROOT, capture_output=True,
                             text=True, encoding="utf-8", errors="replace", timeout=60)
        bad = []
        for ln in (out.stdout or "").splitlines()[1:]:
            name = ln.split()[0].replace("\\", "/").rsplit("/", 1)[-1]
            if not re.match(r"^(op[0-9]{4}[a-z]+-|agent-|worktree-|lan-|queue-|wecom-)", name):
                bad.append(name)
        if bad:
            print(f"\n🔴 异常 worktree 名（疑参数解析错位造出）：{', '.join(bad)}")
            print("   不要在泳道在跑时动它——等该泳道收工再按残留 worktree 三查处理。")
    except Exception:  # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
