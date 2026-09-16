# -*- coding: utf-8 -*-
"""泳道看护 · 阻塞等待（队列 §一 `#598` 期望产出 ①，Token 优化 P2）。

看护会话此前每轮自己起 `check-heartbeat`／`summary`／`show` 逐条查一遍再判断
要不要继续等，请求数偏高（#598 立行原文）。本工具把"逐轮自查"收进一次
`wait` 调用：内部每 `--poll-interval` 秒轮询一次，**只在真出现事件时才退出**，
调用方不必自己写轮询循环。

🔴 **只读，不改状态机判据**：本工具全程只调 `工具-泳道看护状态机.py` 里的
只读函数（`_read_state`／`_read_last_sentinel`／`resolve_heartbeat_path`／
`heartbeat_rel_path`／`lane_in_batch`）与只读常量，MUST NOT 调用
`pause_lane`／`check_heartbeat`（后者会落 `paused`＋推企微通知，那是一次
主动判定，不是"看一眼现在什么状态"）——`check-heartbeat` 那把真正的判定与
落状态仍由 SKILL 步骤 5.6 在 `wait` 返回之后另行调用，两者分工不重叠。

轮询三类信号：
  ⑴ 心跳文件（mtime＋收工哨兵，同 `check_heartbeat` 的只读判据，未落任何状态）；
  ⑵ 状态记录（`lanes[lane].status`：`done`／`paused`）——这是"summary"一词在
     本工具里的落地：不重新格式化 `build_summary()` 的人读文案，直接读它背后
     那份状态记录，两者是同一个权威源；
  ⑶ 进程（可选 `--log-dir`，指向 `工具-opener批处理执行v2.ps1 -Detach` 的日志
     目录，读 `launcher.json`／`exit.txt`判断子进程是否已退出——覆盖"泳道从未
     写过一行心跳就已经跪了"这种心跳／状态两处都看不到信号的场景）。

🔑 **批次归属的天然局限**：泳道只有在触发过 `pause`／`heartbeat --done`／
看门狗等事件后才会在 `reports/lane-watch-state.json` 里留下可判定归属的记录
（见 `resolve_lane_batch()` 文档）——一条**健康运行中、还没出过任何事件**的
泳道在状态文件里天然没有痕迹。故 NO-HEARTBEAT／TIMEOUT 只覆盖"已在状态文件
留过痕的泳道"；对纯健康运行、零事件的泳道，`wait` 只会诚实地跑满
`--max-wait` 后报 MAX-WAIT——这不是漏检，是如实反映"目前没有任何可判定的
信号"，调用方按 MAX-WAIT 重新调一次 `wait` 即可继续等。

退出码（`_cmd_wait` 与 `EXIT_CODES` 是唯一权威源，不在别处复述数字）：
  0  DONE           批次内至少一条泳道已终态，或某个 `--log-dir` 子进程已退出
  10 PAUSED         批次内至少一条泳道处于 `paused`（命中 🟡/🔴/🐕 决策点）
  11 NO-HEARTBEAT   已留痕的泳道里，至少一条心跳文件完全不存在
  12 TIMEOUT        已留痕的泳道里，至少一条心跳文件存在但超过 `--stale-minutes` 未更新
  13 MAX-WAIT       轮询满 `--max-wait` 秒仍无任何上述信号（健康运行中）
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Callable, Optional

_TOOLS_DIR = Path(__file__).resolve().parent

# 白盒复用手法与 `工具-泳道看护状态机.py::_editlock` 同款（按文件路径
# importlib 加载，不走 `import 工具-...` 的包名解析——文件名含中文/连字符）。
_STATE_MACHINE_SCRIPT = _TOOLS_DIR / "工具-泳道看护状态机.py"
_spec = importlib.util.spec_from_file_location(
    "_lane_watch_wait_statemachine_reuse", _STATE_MACHINE_SCRIPT
)
_state_machine = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _state_machine
_spec.loader.exec_module(_state_machine)

HEARTBEAT_STALE_MINUTES_DEFAULT = _state_machine.HEARTBEAT_STALE_MINUTES_DEFAULT
DEFAULT_MAX_WAIT_SECONDS = 540.0
DEFAULT_POLL_INTERVAL_SECONDS = 15.0

EXIT_CODES = {
    "done": 0,
    "paused": 10,
    "no_heartbeat": 11,
    "timeout": 12,
    "max_wait": 13,
}

_STATUS_LABELS = {
    "done": ("🏁", "DONE"),
    "paused": ("⏸", "PAUSED"),
    "no_heartbeat": ("❓", "NO-HEARTBEAT"),
    "timeout": ("🐕", "TIMEOUT"),
    "max_wait": ("⏱", "MAX-WAIT"),
}


def _batch_lanes(state: dict, batch: str) -> dict:
    """当前状态文件里可判定归属于 `batch` 的泳道——`lane_in_batch()` 同一口径。"""
    return {
        lane: lane_state
        for lane, lane_state in state.get("lanes", {}).items()
        if _state_machine.lane_in_batch(lane_state, batch)
    }


def _pid_alive(pid: int) -> Optional[bool]:
    """只读查一次 `tasklist`——查不到（命令缺失/超时）时返回 `None`（未知，
    不当"已退出"判），避免因查询本身失败而误判进程已死。"""
    import subprocess

    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, ValueError):
        return None
    if out.returncode != 0:
        return None
    return str(pid) in out.stdout


def check_process_exits(log_dirs: list) -> list:
    """给定若干 `-Detach` 日志目录，逐个只读判断其子进程是否已退出。

    优先读 `exit.txt`（子进程结束时权威落盘，见
    `工具-opener批处理执行v2.ps1` 模块注释）；`exit.txt` 还没出现时回落读
    `launcher.json` 里的 `pid` 现查一次 `tasklist`。"""
    results = []
    for d in log_dirs:
        base = Path(d)
        exit_path = base / "exit.txt"
        if exit_path.is_file():
            code = exit_path.read_text(encoding="utf-8").strip()
            results.append({"log_dir": str(d), "exited": True, "exit_code": code})
            continue
        pid = None
        launcher_path = base / "launcher.json"
        if launcher_path.is_file():
            try:
                pid = json.loads(launcher_path.read_text(encoding="utf-8")).get("pid")
            except (OSError, json.JSONDecodeError):
                pid = None
        alive = _pid_alive(pid) if pid else None
        results.append({
            "log_dir": str(d), "exited": (alive is False), "exit_code": None,
        })
    return results


def _heartbeat_signal(lane: str, stale_minutes: float) -> str:
    """单条泳道的只读心跳判据——`missing`／`stale`／`ok`／`exempt`。

    `exempt`＝命中收工哨兵（`DONE ｜`／`STOPPED ｜`），同 `check_heartbeat()`
    的终态豁免（不重复判失联），但本函数**不落任何状态**、不推通知。
    """
    path = _state_machine.resolve_heartbeat_path(_state_machine.heartbeat_rel_path(lane))
    if not path.exists():
        return "missing"
    sentinel = _state_machine._read_last_sentinel(path)
    if sentinel in ("DONE", "STOPPED"):
        return "exempt"
    age_minutes = (time.time() - path.stat().st_mtime) / 60.0
    return "stale" if age_minutes > stale_minutes else "ok"


def wait_for_batch(
    *, batch: str, max_wait: float = DEFAULT_MAX_WAIT_SECONDS,
    poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
    stale_minutes: float = HEARTBEAT_STALE_MINUTES_DEFAULT,
    log_dirs: Optional[list] = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    clock_fn: Callable[[], float] = time.monotonic,
) -> dict:
    """轮询直到出现事件或 `max_wait` 耗尽。返回 `{"status", "lanes", "elapsed",
    ["process"]}`；`status` 取值见模块文档 `EXIT_CODES`。"""
    log_dirs = log_dirs or []
    start = clock_fn()

    while True:
        state = _state_machine._read_state()
        lanes = _batch_lanes(state, batch)

        done_lanes = sorted(
            lane for lane, s in lanes.items() if s.get("status") == _state_machine.STATUS_DONE
        )
        if done_lanes:
            return {"status": "done", "lanes": done_lanes, "elapsed": round(clock_fn() - start, 1)}

        process_results = check_process_exits(log_dirs)
        exited = [p for p in process_results if p["exited"]]
        if exited:
            return {
                "status": "done", "lanes": [], "process": exited,
                "elapsed": round(clock_fn() - start, 1),
            }

        paused_lanes = sorted(lane for lane, s in lanes.items() if s.get("status") == "paused")
        if paused_lanes:
            return {"status": "paused", "lanes": paused_lanes, "elapsed": round(clock_fn() - start, 1)}

        missing, stale = [], []
        for lane in lanes:
            signal = _heartbeat_signal(lane, stale_minutes)
            if signal == "missing":
                missing.append(lane)
            elif signal == "stale":
                stale.append(lane)
        if missing:
            return {"status": "no_heartbeat", "lanes": sorted(missing), "elapsed": round(clock_fn() - start, 1)}
        if stale:
            return {"status": "timeout", "lanes": sorted(stale), "elapsed": round(clock_fn() - start, 1)}

        elapsed = clock_fn() - start
        if elapsed >= max_wait:
            return {"status": "max_wait", "lanes": sorted(lanes.keys()), "elapsed": round(elapsed, 1)}

        sleep_fn(min(poll_interval, max_wait - elapsed))


def _cmd_wait(args: argparse.Namespace) -> int:
    result = wait_for_batch(
        batch=args.batch, max_wait=args.max_wait, poll_interval=args.poll_interval,
        stale_minutes=args.stale_minutes, log_dirs=args.log_dir or [],
    )
    icon, label = _STATUS_LABELS[result["status"]]
    lanes = result.get("lanes") or []
    lane_text = "、".join(f"`{l}`" for l in lanes) if lanes else "（无具名泳道命中）"
    print(f"{icon} {label}｜批次 `{args.batch}`｜耗时 {result['elapsed']}s｜{lane_text}")
    for p in (result.get("process") or [])[:5]:
        print(f"  进程已退出：{p['log_dir']}（exit={p.get('exit_code')}）")
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    return EXIT_CODES[result["status"]]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="泳道看护 · 阻塞等待（#598 ①：一次调用代替逐轮自查）。")
    sub = p.add_subparsers(dest="command", required=True)

    p_wait = sub.add_parser(
        "wait", help="轮询直到批次内出现 DONE/PAUSED/NO-HEARTBEAT/TIMEOUT，或 --max-wait 耗尽（MAX-WAIT）",
    )
    p_wait.add_argument("--batch", required=True)
    p_wait.add_argument("--max-wait", type=float, default=DEFAULT_MAX_WAIT_SECONDS, help=f"秒，默认 {DEFAULT_MAX_WAIT_SECONDS:.0f}")
    p_wait.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL_SECONDS, help=f"秒，默认 {DEFAULT_POLL_INTERVAL_SECONDS:.0f}")
    p_wait.add_argument("--stale-minutes", type=float, default=HEARTBEAT_STALE_MINUTES_DEFAULT)
    p_wait.add_argument(
        "--log-dir", action="append", default=None,
        help="可重复：`工具-opener批处理执行v2.ps1 -Detach` 的日志目录，读 launcher.json/exit.txt 判子进程是否已退出",
    )
    p_wait.add_argument("--json", action="store_true")
    p_wait.set_defaults(func=_cmd_wait)

    return p


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
