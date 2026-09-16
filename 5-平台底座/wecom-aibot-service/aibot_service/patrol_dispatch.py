"""队列 #382⑴bis：桥一落信号后直接起无头 CC 拆件，彻底去掉轮询。

## 它替代的是什么

`#382⑴` 把「有没有新回件」的判断从「扫 2 MB 队列真身」降到「看一个几百
字节的信号文件在不在」，但拆件巡逻本身仍是**定时**触发（`*/10 * * * *`
分钟级轮询）——从"回件落盘"到"有人真的去拆"之间仍隔着最多 10 分钟的
轮询延迟，且 08-31~09-04 期间该定时任务本身被人工判下线、这段延迟直接
变成无穷大（见队列 `#382` 2026-09-04 登记）。

本模块把「打标即开班」落到实处：`followup_readme_bridge.mark_reply_
arrived` 把回件标完第九态、落完信号的**同一次调用**里，直接 `subprocess.
Popen` 起一个无头 `claude -p` 会话去执行拆件巡逻章程，不等任何定时器。

## 四条设计取舍

1. **章程正本必须在仓库内，不内联、不复述**：无头 CC 的 `cwd` 是仓库根，
   能读仓库内任何文件；仓库外的 `C:\\Users\\Paul Shao\\Claude\\Scheduled\\
   huijian-chaijian-patrol\\SKILL.md` 它读不到。内联一份到本模块字符串里
   是另一条路，但那会再造一份"会漂"的副本——两份正本谁改了谁没改，迟早
   分岔（本项目已在"编号/状态两份副本"上吃过 6 次同类亏，见队列 `#382`
   转述登记 ⑵）。故正本已原文照搬迁入 `resolve_patrol_charter_path()`
   指向的仓库内路径，本模块只读它、不复述其内容；读不到即 fail-open 记
   失败（见取舍 3），不生成兜底版本。
2. **并发守卫用"进程是否还活着"，不用"锁文件是否存在"**：信号密集时
   （回件扎堆到达）会有多个候选起活时刻，若每次都无条件起一个新的无头
   CC，会有多个会话同时抢 README/队列编辑锁——章程既有的编辑锁重试/退避
   （协议〇.7）能扛住偶发冲突，但没必要每次都制造这种冲突。锁文件记
   `pid`；下次候选起活时若该 `pid` 仍存活，直接跳过（不算失败——已有
   一个在跑，等它退出后 `_spawn_watcher` 会复查信号、把这次的新信号
   一并接住，见后文「关于起活期间又来一条」）。`pid` 不存活（上次异常退出留下的陈旧锁）
   则视为空闲，照常起活——**宁可偶尔多起一个重复的（章程编辑锁会兜住），
   也不可把"查活着与否本身失败"当成"活着"而永久卡死**（`_pid_alive`
   查询异常时的口径，见该函数文首）。
3. **fail-open 边界只对"起没起来"负责，不去改信号**：本模块从不读写
   `patrol_signal.json`——起活失败（章程文件缺失/读不了、`claude` 不在
   PATH、`Popen` 本身抛异常）时，信号文件原样留着（调用方 `patrol_signal.
   raise_signal` 早于本模块执行，与本模块是否成功无关），下一条真实回件
   到达时会再触发一次起活候选。**失败绝不允许被吞掉**：`_record` 把每
   一次候选（起了/跳过/失败）都记一条 `audit` 事件外加一行 `log()` 输出
   ——"起活失败"和"起活成功但拆件本身出错"是两件事，本模块只保证前者
   可见，后者留给无头 CC 自己在其章程 §四 报告里交代。
4. **非阻塞**：`Popen` 后立即返回，不等子进程收工——`mark_reply_arrived`
   是归档主流程的旁路增强，阻塞等一次可能耗时数分钟的拆件会话，等于把
   "标个状态"的延迟系在"干完一整套人工判断量级的活"上，本末倒置。

## 关于"起活期间又来一条"（队列 #599 P6：调度层无状态化）

此前的做法是让无头 CC 自己在收工前多探测一次信号、有则回到章程 §一 再
走一轮——这会让同一个会话越跑越长，且"要不要再走一轮"这个判断散落在
被调度的那个会话自己手里，调度方（本模块）反而不知道也管不了。**现改
为调度层负责**：起活成功后另起一个不阻塞的后台等待（`_spawn_watcher`，
生产用守护线程、测试可注入同步替身 `run_in_thread`，遵循文首取舍 4
「非阻塞」），待子进程真正退出后再读一次 `patrol_signal.read_signal`——
仍有未消费的信号即再调用本函数起一轮全新会话，如此链式推进，直到某次
子进程退出时信号已空为止。**每一轮会话只对"这一轮"负责，不再自己判断
是否要再来一轮**——`_build_prompt` 因此不再附带"回到 §一 再走一轮"的
调用侧说明。
"""
from __future__ import annotations

import json
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from zhuopin_platform.audit import AuditEvent

from . import patrol_signal
from .repo_paths import (
    resolve_patrol_charter_path,
    resolve_patrol_dispatch_lock_path,
    resolve_patrol_dispatch_log_dir,
)

CLAUDE_EXECUTABLE = "claude"
#: Token 优化 Phase 1（队列 #581）：无头巡逻默认走最便宜的模型；ASIL/合规相关建造不走本模块。
PATROL_MODEL = "sonnet"

ACTION_STARTED = "started"
ACTION_SKIPPED_BUSY = "skipped_busy"
ACTION_FAILED = "failed"

_EVENT_DRIVEN_PREAMBLE = """【事件驱动拆件起活 · 队列 #382⑴bis】
本 session 由 `followup_readme_bridge.mark_reply_arrived` 在把一封回件标为
第九态、落完信号的同一次调用里直接无头启动——零轮询、零人工触发。以下附
完整拆件巡逻章程原文（已迁入仓库 `0-学习与工具/skills源码/huijian-
chaijian-patrol/SKILL.md`，原文原样、未改一字）。

按章程 §〇ter 开始：先跑信号探测，此刻理应为 `[SIGNAL]`（正是你被起来的
原因）；随后按 §一~§四 全套执行，**执行完毕、报告已登记 §二 批次之后**
才消费信号——这是章程原有顺序，未变。

🔴 本次起活方式新增于章程原文之外的规则（只在这次无头调用生效，不改
章程正文；队列 #599 P6 起，"要不要再走一轮"已改由调度层负责，本会话
不再自己判断）：**你只对这一轮 §一~§四（含信号消费）负责，收尾前不必
再探测信号、不必回到 §一 重走**——起活期间若又有新回件到达，调度层会
在你这次会话真正收工、进程退出后另起一个全新的无头会话去处理，与本次
会话无关。按章程 §六 正常收尾即可。

若 `mcp__ccd_session_mgmt__set_session_title` 等工具不存在，跳过继续。

────────── 以下为拆件巡逻章程原文 ──────────
"""


def _utc_stamp(now: Optional[datetime] = None) -> str:
    """UTC 且显式带 `Z`——与本服务其余模块同口径。"""
    moment = now or datetime.now(tz=timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _pid_alive(pid: int) -> bool:
    """Windows 判活：`tasklist /FI "PID eq N"` 输出含该 PID 即视为存活。

    查询本身失败（`tasklist` 不存在/超时/异常）时**按"不存活"处理**（会
    去起一个可能重复的无头 CC）而非"存活"（会永久跳过、信号原地卡死）
    ——两个方向的代价不对称：重复起活的后果由既有编辑锁重试/退避兜住，
    是"多做一次无害的事"；误判存活的后果是"该做的事没人做"，正是本模块
    要防的那类失效（见文首取舍 2）。
    """
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True, text=True, timeout=5,
        )
        return str(pid) in result.stdout
    except Exception:  # noqa: BLE001 —— 查询失败按"不存活"处理，见上
        return False


def _build_prompt(charter_text: str) -> str:
    return _EVENT_DRIVEN_PREAMBLE + charter_text


def _run_in_thread(target: Callable[[], None]) -> None:
    threading.Thread(target=target, daemon=True).start()


def _spawn_watcher(
    proc: "subprocess.Popen",
    repo_root: Path,
    *,
    audit,
    evaluator: str,
    log: Callable[[str], None],
    popen: Callable[..., "subprocess.Popen"],
    pid_alive: Callable[[int], bool],
    run_in_thread: Callable[[Callable[[], None]], None],
) -> None:
    """子进程退出后复查信号，仍有未消费信号则再起一轮全新会话（队列 #599 P6）。

    只等这一个子进程，不轮询——`proc.wait()` 阻塞在后台线程里，主线程
    早已随 `dispatch_headless_patrol` 返回（文首取舍 4「非阻塞」）。链式
    推进由"再调一次 `dispatch_headless_patrol`"自然实现：它自己起活成功
    时又会再挂一个 `_spawn_watcher`，直到某次子进程退出时信号已空为止。
    """
    def _watch() -> None:
        try:
            proc.wait()
        except Exception:  # noqa: BLE001 —— 等待本身失败不得让后台线程抛出
            return
        try:
            snapshot = patrol_signal.read_signal(repo_root)
        except Exception:  # noqa: BLE001 —— 复查信号失败按"无新信号"处理，不误起
            return
        if not snapshot.present:
            return
        try:
            log("· [拆件起活] 子进程已退出、信号仍在，链式再起一轮")
        except Exception:  # noqa: BLE001
            pass
        dispatch_headless_patrol(
            repo_root, audit=audit, evaluator=evaluator, log=log,
            popen=popen, pid_alive=pid_alive, run_in_thread=run_in_thread,
        )

    run_in_thread(_watch)


@dataclass
class DispatchResult:
    action: str
    detail: str = ""
    pid: Optional[int] = None
    log_path: str = ""


def _record(audit, evaluator: str, result: DispatchResult, *,
            log: Callable[[str], None]) -> DispatchResult:
    prefix = {"started": "✓", "skipped_busy": "·", "failed": "⚠"}.get(result.action, "·")
    try:
        log(f"{prefix} [拆件起活] {result.detail}")
    except Exception:  # noqa: BLE001
        pass
    if audit is not None:
        try:
            audit.record(AuditEvent(
                scenario="wecom-aibot",
                action=f"patrol_headless_dispatch_{result.action}",
                evaluator=evaluator,
                automation_level="L1",
                decision={"pid": result.pid or 0},
                data_sources={"detail": result.detail, "log": result.log_path},
            ))
        except Exception:  # noqa: BLE001 —— 留痕失败不得反过来破坏"不抛"的契约
            pass
    return result


def dispatch_headless_patrol(
    repo_root: Path,
    *,
    now: Optional[datetime] = None,
    audit=None,
    evaluator: str = "system",
    log: Callable[[str], None] = print,
    popen: Callable[..., "subprocess.Popen"] = subprocess.Popen,
    pid_alive: Callable[[int], bool] = _pid_alive,
    run_in_thread: Callable[[Callable[[], None]], None] = _run_in_thread,
) -> DispatchResult:
    """起一个无头 CC 去执行拆件巡逻章程。绝不向上抛——任何失败都只记
    审计＋日志，不得让 `mark_reply_arrived` 的"绝不向上抛"契约被打破
    （调用方 `_raise_patrol_signal` 已包一层 `except`，本函数自身也不
    应假设那层保护一定存在）。
    """
    try:
        lock_path = resolve_patrol_dispatch_lock_path(repo_root)
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        if lock_path.exists():
            existing_pid = 0
            try:
                lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
                existing_pid = int(lock_data.get("pid", 0))
            except (json.JSONDecodeError, OSError, ValueError, TypeError):
                existing_pid = 0
            if existing_pid and pid_alive(existing_pid):
                return _record(audit, evaluator, DispatchResult(
                    ACTION_SKIPPED_BUSY, pid=existing_pid,
                    detail=(f"已有无头 CC 在跑（pid={existing_pid}），本次不重复起——"
                            f"它退出后调度层会复查一次信号，不会漏（队列 #599 P6）。"),
                ), log=log)
            # pid 不存活（陈旧锁）——继续起活，下方会覆盖这份锁文件。

        charter_path = resolve_patrol_charter_path(repo_root)
        try:
            charter_text = charter_path.read_text(encoding="utf-8")
        except OSError as exc:
            return _record(audit, evaluator, DispatchResult(
                ACTION_FAILED,
                detail=f"拆件章程正本读取失败，未起活，信号原样留着：{charter_path}（{exc}）",
            ), log=log)

        stamp = (now or datetime.now(tz=timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
        log_dir = resolve_patrol_dispatch_log_dir(repo_root)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{stamp}.log"

        prompt = _build_prompt(charter_text)

        try:
            log_file = open(log_path, "w", encoding="utf-8")
        except OSError as exc:
            return _record(audit, evaluator, DispatchResult(
                ACTION_FAILED,
                detail=f"起活日志文件建不了，未起活，信号原样留着：{log_path}（{exc}）",
            ), log=log)

        try:
            proc = popen(
                [CLAUDE_EXECUTABLE, "-p", "--output-format", "text",
                 "--model", PATROL_MODEL,
                 "--dangerously-skip-permissions"],
                stdin=subprocess.PIPE, stdout=log_file, stderr=subprocess.STDOUT,
                cwd=str(repo_root), text=True,
            )
        except OSError as exc:
            return _record(audit, evaluator, DispatchResult(
                ACTION_FAILED,
                detail=f"起 claude 无头会话失败（claude 是否在 PATH？），"
                       f"未起活，信号原样留着：{exc}",
            ), log=log)
        finally:
            try:
                log_file.close()
            except Exception:  # noqa: BLE001
                pass

        try:
            if proc.stdin is not None:
                proc.stdin.write(prompt)
                proc.stdin.close()
        except Exception:  # noqa: BLE001 —— 写 stdin 失败不代表进程没起，继续按已起活记
            pass

        try:
            lock_path.write_text(
                json.dumps({"pid": proc.pid, "started_at": _utc_stamp(now),
                            "log": str(log_path)}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass  # 并发守卫锁写失败不影响"已真实起活"这个事实，见文首取舍 2

        try:
            _spawn_watcher(
                proc, repo_root, audit=audit, evaluator=evaluator, log=log,
                popen=popen, pid_alive=pid_alive, run_in_thread=run_in_thread,
            )
        except Exception:  # noqa: BLE001 —— 挂后台复查失败不代表进程没起，继续按已起活记
            pass

        return _record(audit, evaluator, DispatchResult(
            ACTION_STARTED, pid=proc.pid, log_path=str(log_path),
            detail=f"无头 CC 已起（pid={proc.pid}），输出见 {log_path}",
        ), log=log)
    except Exception as exc:  # noqa: BLE001 —— 本函数绝不向上抛，见文首
        return _record(audit, evaluator, DispatchResult(
            ACTION_FAILED, detail=f"起活流程自身异常，信号原样留着：{exc}",
        ), log=log)
