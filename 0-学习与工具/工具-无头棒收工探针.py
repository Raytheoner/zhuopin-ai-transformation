#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""无头棒收工探针 —— 把「无头 CC 泳道批跑完了」从人守转成机器守。

承接：队列 §一 `#551`／根 `CLAUDE.md` §5 `UPS5:7`（会话不自醒；说「自动」
必须当场指名机器规则）。**本文件就是 `UPS5:7` 判据里那条「能当场指名的
机器规则」的实现**，配套定时任务 `taskId = poll-opener-batch`。

成因（2026-09-10 实证，不复述细节，原文见 `#551` 与 `UPS5:7`）：
  - 15:0x 本方承诺「盯着 summary.txt，一出来就自动起下一棒」；两批 14:47
    即收工，**16:18 他主动问才被发现，空转 90 分钟**。
  - 同日 17:1x 自查发现 `UPS5:7` 原文「本方无轮询、没有定时器」是错的：
    Cowork 侧一直有 `mcp__scheduled-tasks__*`。**缺的从来不是能力，是没
    把这条规则建出来。** 本文件即为把它建出来。

判据（三态，互斥）：
  [SIGNAL]    有新收工批或新停滞批 —— 已推企微，且把详情打到 stdout。
  [NO-SIGNAL] 无新事 —— 立即退出，调用方（定时任务会话）不必再读任何文件。
  [BASELINE]  首跑基线化 —— 把现存批一次性记为「已知」，**不推送**，
              免得装上去的那一刻把历史批全喷一遍。

🔴 **fail-open 取向**：探针自身出错一律按 [SIGNAL] 报出并写明原因——
   「用来发现问题的东西自己坏了」必须可见（同队列 §一 `#398`）。宁可多
   吵一次，不可静默漏一次；本探针存在的全部意义就是不漏。

🔴 **只读 + 一个状态文件**：除 `reports/opener-batch-notified.json` 外不
   写任何东西，不碰队列真身、不碰 git、不碰 `.51`。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import importlib.util
import json
import re
import sys
import traceback
from pathlib import Path
from typing import Callable, Optional

# --------------------------------------------------------------------------
# 常量
# --------------------------------------------------------------------------

_THIS = Path(__file__).resolve()
_TOOLS_DIR = _THIS.parent
DEFAULT_REPO_ROOT = _TOOLS_DIR.parent

BATCH_ROOT_REL = Path("reports") / "opener-batch"
STATE_REL = Path("reports") / "opener-batch-notified.json"

#: 批目录名形态：`YYYYMMDD-HHMMSS`（`工具-opener批处理执行v2.ps1` 所建）。
BATCH_DIR_RE = re.compile(r"^(\d{8})-(\d{6})$")

#: summary.txt 里 `Format-Table Lane, Id, Status, Minutes` 的状态字面量。
STATUS_RE = re.compile(r"\b(OK|PARTIAL|NO-SENTINEL|FAIL\(\d+\))")

#: 无 summary.txt 且批内所有文件静默超过本阈值 ⇒ 报「疑似停滞」。
#: 🔴 取 90 分钟而非 45：一条泳道可能长时间安静地干活（agent 不写 stdout），
#: 阈值太短会把正常长跑误报成停滞，而**误报会训练人忽略推送**（同 `#398`）。
DEFAULT_STALL_MINUTES = 90

#: 只看最近这么多小时内起的批；更老的即便没 summary 也不再吵（早已过时）。
DEFAULT_LOOKBACK_HOURS = 24


# --------------------------------------------------------------------------
# 企微推送（复用既有实现，不抄第三份键名）
# --------------------------------------------------------------------------

def _load_ops_sender() -> Optional[Callable[[str], None]]:
    """复用 `工具-泳道看护状态机.py::_load_wecom_sender`。

    🔴 **刻意不在本文件出现 `WECOM_WEBHOOK_URL_OPS` 字面量**——该键名在
    状态机模块里注明「本模块内只此一份，其余位置一律派生」（队列 `#492`
    两次真实事故：推送打错群）。本文件若抄一份，就成了第三处可漂移点。
    找不到实现时返回 `None`，调用方降级为「只打 stdout 不推送」，
    **绝不回落默认业务群**（fail-closed，同 `#492` ⑶）。
    """
    target = _TOOLS_DIR / "工具-泳道看护状态机.py"
    if not target.exists():
        return None
    spec = importlib.util.spec_from_file_location("_probe_lane_watch_reuse", target)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    loader = getattr(module, "_load_wecom_sender", None)
    if loader is None:
        return None
    return loader()


# --------------------------------------------------------------------------
# 状态文件
# --------------------------------------------------------------------------

def _read_state(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        # 🔴 状态文件坏了 ⇒ 当成没有，走基线化重来。绝不因为它坏了就
        #    静默什么都不报（那正是 fail-open 取向要防的）。
        return None


def _write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


# --------------------------------------------------------------------------
# 批目录判读
# --------------------------------------------------------------------------

def _batch_started_at(name: str) -> Optional[_dt.datetime]:
    m = BATCH_DIR_RE.match(name)
    if not m:
        return None
    try:
        return _dt.datetime.strptime(name, "%Y%m%d-%H%M%S")
    except ValueError:
        return None


def _parse_summary(text: str) -> list:
    """从 summary.txt 抽 (泳道, 状态) 对。

    容错解析：`Format-Table` 的表头/分隔线/空行一律跳过，只认**行内出现
    已知状态字面量**的行，泳道取该行第一个 token。
    🔴 不做严格列宽解析——列宽随泳道名长度变化，硬编码列位必炸（同族＝
    队列 §一 `#535` 夹具硬编码）。
    """
    rows = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("-") or s.startswith("Lane"):
            continue
        m = STATUS_RE.search(s)
        if not m:
            continue
        lane = s.split()[0]
        rows.append((lane, m.group(1)))
    return rows


def _latest_mtime(d: Path) -> Optional[_dt.datetime]:
    newest = None
    for p in d.rglob("*"):
        if not p.is_file():
            continue
        ts = _dt.datetime.fromtimestamp(p.stat().st_mtime)
        if newest is None or ts > newest:
            newest = ts
    return newest


# --------------------------------------------------------------------------
# 主判读
# --------------------------------------------------------------------------

def scan(
    repo_root: Path,
    *,
    now: Optional[_dt.datetime] = None,
    stall_minutes: int = DEFAULT_STALL_MINUTES,
    lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
) -> dict:
    """只读扫描，返回判读结果；不写状态、不推送（便于单测与 --dry-run）。"""
    now = now or _dt.datetime.now()
    batch_root = repo_root / BATCH_ROOT_REL
    state = _read_state(repo_root / STATE_REL)
    first_run = state is None
    known = (state or {}).get("batches", {})

    done, stalled, running, baseline = [], [], [], []

    if batch_root.exists():
        for d in sorted(batch_root.iterdir()):
            if not d.is_dir():
                continue
            started = _batch_started_at(d.name)
            if started is None:
                continue
            age_h = (now - started).total_seconds() / 3600.0
            if age_h > lookback_hours:
                continue

            entry = known.get(d.name, {})
            summary = d / "summary.txt"

            if summary.exists():
                if first_run:
                    # 🔴 基线化只压「装探针那一刻**已经收工**的批」。装的时候
                    #    还在跑的批**不压**，否则它收工时会被自己的基线记录
                    #    静默掉——本探针存在的理由就是不漏那一次。
                    #    （2026-09-10 首版实撞：基线化对所有批一律写
                    #    done_notified，正在跑的 `OP-0910-R` 当场被埋掉。）
                    baseline.append({"batch": d.name, "had_summary": True, "was_stalled": False})
                elif not entry.get("done_notified"):
                    try:
                        lanes = _parse_summary(summary.read_text(encoding="utf-8", errors="replace"))
                    except Exception as exc:  # noqa: BLE001
                        lanes = [("<读 summary 失败>", str(exc))]
                    done.append({
                        "batch": d.name,
                        "dir": str((BATCH_ROOT_REL / d.name).as_posix()),
                        "lanes": lanes,
                        "finished_at": _dt.datetime.fromtimestamp(summary.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    })
                continue

            # 无 summary.txt ＝ 还没收工（或夭折）
            newest = _latest_mtime(d) or started
            silent_min = (now - newest).total_seconds() / 60.0
            if first_run:
                baseline.append({"batch": d.name, "had_summary": False,
                                 "was_stalled": silent_min >= stall_minutes})
            elif silent_min >= stall_minutes and not entry.get("stall_notified"):
                stalled.append({
                    "batch": d.name,
                    "dir": str((BATCH_ROOT_REL / d.name).as_posix()),
                    "silent_minutes": round(silent_min, 1),
                    "last_write": newest.strftime("%Y-%m-%d %H:%M:%S"),
                })
            else:
                running.append({"batch": d.name, "silent_minutes": round(silent_min, 1)})

    if first_run:
        verdict = "BASELINE"
    elif done or stalled:
        verdict = "SIGNAL"
    else:
        verdict = "NO-SIGNAL"

    return {
        "verdict": verdict,
        "now": now.strftime("%Y-%m-%d %H:%M:%S"),
        "done": done,
        "stalled": stalled,
        "running": running,
        "baseline": baseline,
        "first_run": first_run,
    }


#: 推送落款。🔴 **不得写死成「本条由定时任务推送」**——2026-09-10 17:36 的
#: 自检消息就是本方**手工**跑脚本推的，正文却硬写着「由定时任务
#: poll-opener-batch 推送」，当场造出一条假落款。**同族＝贯穿全项目的
#: 「写进文本的状态不会自己过期」，只是这次是刚写就已经过期。**
#: ⇒ 落款一律由调用方现给，缺省按「手工」，**绝不缺省按定时任务**
#: （猜错的方向要选代价小的那个：把定时任务说成手工只是少一句话，
#: 反过来会让人以为机器守在跑，而它可能根本没跑）。
INVOKER_MANUAL = "手工运行 `0-学习与工具/工具-无头棒收工探针.py`"
INVOKER_SCHEDULED = "定时任务 `poll-opener-batch`"


def format_message(result: dict, invoked_by: str = INVOKER_MANUAL) -> str:
    """企微 markdown 正文。**明确交回**，不写「我会自动接着做」。"""
    lines = ["**无头棒收工探针 · 有新事**", f"探测时刻：{result['now']}"]
    for b in result["done"]:
        stats = "／".join(f"`{lane}`＝{st}" for lane, st in b["lanes"]) or "（summary 无可解析行）"
        lines.append(f"✅ **批 `{b['batch']}` 已收工**（{b['finished_at']}）：{stats}")
        lines.append(f"　日志：`{b['dir']}`")
        bad = [l for l, s in b["lanes"] if s != "OK"]
        if bad:
            lines.append(f'　<font color="warning">非 OK 泳道 {len(bad)} 条：{"／".join(bad)}</font>')
    for b in result["stalled"]:
        lines.append(
            f'⏳ <font color="warning">批 `{b["batch"]}` 疑似停滞</font>'
            f'：无 summary.txt，已静默 {b["silent_minutes"]} 分钟（末次写盘 {b["last_write"]}）'
        )
        lines.append(f"　日志：`{b['dir']}`")
    lines.append("> 请回 Cowork 说一句「**棒已完工**」以接续——**本会话不会自己醒**"
                 f"（根 `CLAUDE.md` §5 UPS5:7）。本条推送来源：{invoked_by}。")
    return "\n".join(lines)


def _commit(repo_root: Path, result: dict) -> None:
    """把本次报出的批记进状态文件，避免下一轮重复吵。"""
    path = repo_root / STATE_REL
    state = _read_state(path) or {"batches": {}}
    batches = state.setdefault("batches", {})
    stamp = result["now"]
    for item in result["baseline"]:
        name = item["batch"] if isinstance(item, dict) else item
        rec = batches.setdefault(name, {})
        rec["baselined"] = stamp
        # 🔴 只压基线那一刻**已经成立**的事实：已收工的压 done，已停滞的压
        #    stall。**在跑的批两样都不压**——它之后收工／停滞时照常报出。
        if not isinstance(item, dict) or item.get("had_summary"):
            rec["done_notified"] = stamp
        if not isinstance(item, dict) or item.get("was_stalled"):
            rec["stall_notified"] = stamp
    for b in result["done"]:
        batches.setdefault(b["batch"], {})["done_notified"] = stamp
    for b in result["stalled"]:
        batches.setdefault(b["batch"], {})["stall_notified"] = stamp
    state["last_run"] = stamp
    _write_state(path, state)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="无头棒收工探针（承接 #551／UPS5:7）")
    ap.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT),
                    help="仓库根；仅供单测与临时取证，日常不传")
    ap.add_argument("--dry-run", "--peek", dest="dry_run", action="store_true",
                    help="只判读打印，**不写状态、不推送** —— 人工核查一律用这个。"
                         "`--peek` 是同一开关的别名：`--dry-run` 这个名字看不出「不会吃掉信号」，"
                         "而那正是它与 `--no-notify` 的关键差别（2026-09-10 本方就是选错了那一个）")
    ap.add_argument("--no-notify", action="store_true",
                    help="🔴 **写状态但不推企微** —— 它会把信号标记为「已报」，"
                         "于是定时任务此后不再报它。**人工核查请用 `--peek`，不要用它。**")
    ap.add_argument("--stall-minutes", type=int, default=DEFAULT_STALL_MINUTES)
    ap.add_argument("--lookback-hours", type=int, default=DEFAULT_LOOKBACK_HOURS)
    ap.add_argument("--json", action="store_true", help="附带打印判读结果 JSON")
    ap.add_argument("--via-scheduled-task", action="store_true",
                    help="由定时任务 poll-opener-batch 调用时传；只影响推送落款。"
                         "🔴 缺省按「手工」，不得反过来")
    args = ap.parse_args(argv)
    invoked_by = INVOKER_SCHEDULED if args.via_scheduled_task else INVOKER_MANUAL

    repo_root = Path(args.repo_root).resolve()

    try:
        result = scan(repo_root, stall_minutes=args.stall_minutes,
                      lookback_hours=args.lookback_hours)
    except Exception:  # noqa: BLE001
        # 🔴 fail-open：探针自己坏了必须可见，不得静默当无事发生。
        print("[SIGNAL] 探针自身异常——请人工核 reports/opener-batch/：")
        traceback.print_exc()
        return 0

    if result["verdict"] == "BASELINE":
        print(f"[BASELINE] 首跑基线化：记下 {len(result['baseline'])} 个现存批，本次不推送。")
        if not args.dry_run:
            _commit(repo_root, result)
        return 0

    if result["verdict"] == "NO-SIGNAL":
        running = result["running"]
        tail = f"（在跑 {len(running)} 批）" if running else ""
        print(f"[NO-SIGNAL] 无新收工、无新停滞{tail}。")
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    message = format_message(result, invoked_by)
    print("[SIGNAL]")
    print(message)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.dry_run:
        return 0

    if not args.no_notify:
        sender = _load_ops_sender()
        if sender is None:
            print("⚠ 未取到企微发送器，已降级为仅打印；fail-closed，不回落默认群。",
                  file=sys.stderr)
        else:
            try:
                sender(message)
                print("✓ 已推运维群。")
            except Exception as exc:  # noqa: BLE001
                print(f"⚠ 企微推送失败（{exc}），已降级为仅打印；不回落默认群。",
                      file=sys.stderr)
    else:
        # 🔴 **不许静默吃掉信号**（2026-09-10 23:17 实撞）：本方手工核查时习惯性带
        #    `--no-notify`，它**照样写状态**，于是波 1 收工那条推送**永远不会发**——
        #    当时他在场、由本方口头转达才没损失，机制上那条通知是被吞掉的。
        # 🔑 **一个「安静地少做一件事」的开关，必须自己喊出来它少做了什么**；
        #    否则下一个人（包括本方）只会在事后才知道。同族＝`#398`。
        n = len(result["done"]) + len(result["stalled"])
        print(f"🔴 `--no-notify`：本次**未推企微**，但已把 {n} 条信号标记为「已报」"
              f"⇒ **定时任务此后不会再报它们**。人工核查请改用 `--peek`（＝`--dry-run`，不写状态）。",
              file=sys.stderr)

    _commit(repo_root, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
