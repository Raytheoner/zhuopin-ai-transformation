"""队列 #382⑴bis：桥一落信号后直接起无头 Codex 拆件，彻底去掉轮询。

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

1. **章程正本必须在仓库内，不内联、不复述**：无头 Codex 的 `cwd` 是仓库根，
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
   可见，后者留给无头 Codex 自己在其章程 §四 报告里交代。
4. **非阻塞**：`Popen` 后立即返回，不等子进程收工——`mark_reply_arrived`
   是归档主流程的旁路增强，阻塞等一次可能耗时数分钟的拆件会话，等于把
   "标个状态"的延迟系在"干完一整套人工判断量级的活"上，本末倒置。

## 关于"起活期间又来一条"（队列 #599 P6：调度层无状态化）

此前的做法是让无头 Codex 自己在收工前多探测一次信号、有则回到章程 §一 再
走一轮——这会让同一个会话越跑越长，且"要不要再走一轮"这个判断散落在
被调度的那个会话自己手里，调度方（本模块）反而不知道也管不了。**现改
为调度层负责**：起活成功后另起一个不阻塞的后台等待（`_spawn_watcher`，
生产用守护线程、测试可注入同步替身 `run_in_thread`，遵循文首取舍 4
「非阻塞」），待子进程真正退出后再读一次 `patrol_signal.read_signal`——
仍有未消费的信号即再调用本函数起一轮全新会话，如此链式推进，直到某次
子进程退出时信号已空为止。**每一轮会话只对"这一轮"负责，不再自己判断
是否要再来一轮**——`_build_prompt` 因此不再附带"回到 §一 再走一轮"的
调用侧说明。

## 队列 #416 ⑸bis：链式推进本身可能因持续性故障而"看似在跑、实则空转"

`#599` 那条链式推进只回答了"子进程退出了、还有信号吗"，从不问"这个子
进程刚才那一轮到底是干完了活退出的，还是刚起来就死了"——2026-09-14
两次无头会话均因账号月度用量上限秒退（一行 `You've hit your monthly
spend limit` 即退出），`_spawn_watcher` 读到"信号仍在"但从不检查
`proc.wait()` 的返回码，也不知道那一轮总共只活了几秒，於是**这类持续性
失败会被当成正常的一轮**：链式推进不停地"再起一轮"，每一轮都在几秒内
夭折，没有任何告警，直到有人手工发现。本节补三条治本判据（①②③；④见
`scripts/patrol_stale_signal_fallback.py` 文首）：

1. **夭折判据**：退出码非 0，**或**存活 < `MIN_ALIVE_SECONDS_FOR_SUCCESS`
   （60 秒）且退出时信号仍未被消费——正常跑完一整套拆件巡逻章程耗时远
   超 60 秒，「秒退且没做完事」本身就是异常信号，与退出码是否恰好为 0
   无关（`claude` CLI 遇到用量上限时未必以非零码退出）。
2. **退避与停摆上限**：连续夭折时按 `60 * 2**(n-1)` 秒退避（1/2/4… 分钟，
   `BACKOFF_CAP_SECONDS` 封顶 30 分钟）再重试；连续 `FAILURE_ALERT_
   THRESHOLD`（3）次仍夭折 ⇒ **停止链式**，告警一次，信号原样留着（不
   消费、不假装处理过）——同 `#382⑴bis` 一贯口径：失败绝不允许被吞掉，
   但也不允许无限制地空转重试。
3. **失败计数落盘**（`load_failure_state`/`save_failure_state`，落点
   `reports/patrol_dispatch_failure_state.json`，同 `outbox_relay.py`
   决策点 9 的 `outbox_relay_unreadable_state.json` 先例）：服务本身
   会因断线重连/笔记本休眠反复重启，只存内存的计数每次重启即清零，
   "连续 3 次"这个判据在真实使用形态下永远数不到 3。任一次成功（非
   夭折）即重置计数——"连续"只统计紧邻的失败，不与更早的历史失败
   合并计数。
"""
from __future__ import annotations

import json
import os
import uuid
import subprocess
import threading
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from zhuopin_platform.audit import AuditEvent

from . import patrol_signal
from .repo_paths import (
    resolve_patrol_charter_path,
    resolve_patrol_dispatch_failure_state_path,
    resolve_patrol_dispatch_lock_path,
    resolve_patrol_dispatch_log_dir,
)

ACTION_PAUSED = "paused"


def _codex_policy(repo_root: Path) -> dict:
    path = repo_root / '.codex' / 'consumers.local.json'
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    policy = data.get('patrol', {})
    if not isinstance(policy, dict):
        raise ValueError('patrol policy must be an object')
    return policy


def _codex_command(repo_root: Path, evidence: Path, policy: dict) -> list[str]:
    runtime_path = Path(os.environ.get('ZHUOPIN_CODEX_RUNTIME', str(repo_root / '.codex/runtime.local.json')))
    runtime = json.loads(runtime_path.read_text(encoding='utf-8-sig'))
    python = Path(runtime['python'])
    provider = repo_root / '0-学习与工具/codex-handoff/model_provider.py'
    if not python.is_file() or not provider.is_file():
        raise FileNotFoundError('Codex provider/runtime is not installed; no legacy fallback')
    timeout = int(policy.get('timeout_seconds', 1200))
    if timeout <= 0:
        raise ValueError('patrol timeout must be positive')
    argv = [str(python), '-B', str(provider), '--workspace', str(repo_root),
            '--evidence', str(evidence), '--source-id', 'patrol-' + evidence.name,
            '--sandbox', 'workspace-write', '--timeout', str(timeout), '--enabled']
    model = policy.get('model')
    if model:
        if str(model).lower() in ('sonnet', 'opus', 'haiku'):
            raise ValueError('legacy model aliases are prohibited')
        argv += ['--model', str(model)]
    return argv


ACTION_STARTED = "started"
ACTION_SKIPPED_BUSY = "skipped_busy"
ACTION_FAILED = "failed"
#: 队列 #416 ⑸bis①：子进程真的起来过、但退出即被判定为「这一轮没干成活」。
ACTION_CHILD_FAILED = "child_failed"
#: 队列 #416 ⑸bis②：连续夭折达到阈值，主动停止链式推进（不再重试）。
ACTION_CHAIN_HALTED = "chain_halted"

#: ⑸bis①：正常跑完一整套拆件巡逻章程耗时远超此值，见模块 docstring。
MIN_ALIVE_SECONDS_FOR_SUCCESS = 60.0
#: ⑸bis②：连续夭折达到这个次数即停止链式（不是"重试这么多次"，是"数到
#: 这个数就不再重试"——阈值本身不参与退避秒数计算）。
FAILURE_ALERT_THRESHOLD = 3
#: ⑸bis②：第 n 次连续夭折后的退避秒数 = BACKOFF_BASE_SECONDS * 2**(n-1)，
#: 封顶 BACKOFF_CAP_SECONDS。
BACKOFF_BASE_SECONDS = 60.0
BACKOFF_CAP_SECONDS = 1800.0

#: ⑸bis①：留痕日志尾部截取长度——章程失败时的最后一行诊断信息通常在
#: 输出末尾（如"You've hit your monthly spend limit"），不需要整份日志。
_LOG_TAIL_CHARS = 200

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
    去起一个可能重复的无头 Codex）而非"存活"（会永久跳过、信号原地卡死）
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


def load_failure_state(path: Path) -> dict:
    """读不到/内容非法一律回落空状态（同 `outbox_relay.load_unreadable_
    state` 既有惯例）——状态文件本身读不到不该反过来挡住起活流程。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_failure_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _backoff_seconds(consecutive_failures: int) -> float:
    """第 n 次连续夭折后的退避秒数，见模块 docstring ⑸bis②。"""
    exponent = max(consecutive_failures - 1, 0)
    return min(BACKOFF_BASE_SECONDS * (2 ** exponent), BACKOFF_CAP_SECONDS)


def _read_log_tail(log_path: str, chars: int = _LOG_TAIL_CHARS) -> str:
    """留痕日志尾部——读不到/无日志路径时返回空串，不抛（诊断辅助，非
    关键路径）。"""
    if not log_path:
        return ""
    try:
        text = Path(log_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[-chars:]


def _signal_not_consumed(initial, current) -> bool:
    if initial is None or not initial.present or not current.present:
        return False
    if initial.corrupted or current.corrupted:
        return True
    before = Counter(json.dumps(x, sort_keys=True, ensure_ascii=False) for x in initial.pending)
    after = Counter(json.dumps(x, sort_keys=True, ensure_ascii=False) for x in current.pending)
    return bool(before) and all(after[key] >= count for key, count in before.items())


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
    log_path: str = "",
    alert_send: Optional[Callable[[str], None]] = None,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    failure_state_path: Optional[Path] = None,
    initial_signal=None,
) -> None:
    """子进程退出后复查信号，仍有未消费信号则再起一轮全新会话（队列 #599 P6）；
    队列 #416 ⑸bis：先判这一轮是不是「夭折」的（退出码非 0，或存活 < 60s
    且信号未被消费），夭折按连续失败计数退避/停摆（③落盘，②退避与阈值），
    只有"确认跑完了"才照旧无退避地链式再起。

    只等这一个子进程，不轮询——`proc.wait()` 阻塞在后台线程里，主线程
    早已随 `dispatch_headless_patrol` 返回（文首取舍 4「非阻塞」）。链式
    推进由"再调一次 `dispatch_headless_patrol`"自然实现：它自己起活成功
    时又会再挂一个 `_spawn_watcher`，直到某次子进程退出时信号已空、或连续
    夭折触顶而主动停止为止。
    """
    state_path = failure_state_path or resolve_patrol_dispatch_failure_state_path(repo_root)

    def _watch() -> None:
        started = monotonic()
        try:
            returncode = proc.wait()
        except Exception:  # noqa: BLE001 —— 等待本身失败不得让后台线程抛出
            return
        alive_seconds = monotonic() - started

        try:
            snapshot = patrol_signal.read_signal(repo_root)
            signal_present = bool(snapshot.present)
        except Exception:  # noqa: BLE001 —— 复查信号失败按"无新信号"处理，不误起
            signal_present = False

        no_progress = signal_present and _signal_not_consumed(initial_signal, snapshot)
        premature = bool(returncode) or no_progress or (
            alive_seconds < MIN_ALIVE_SECONDS_FOR_SUCCESS and signal_present
        )
        state = load_failure_state(state_path)

        if not premature:
            if state.get("consecutive_failures"):
                state["consecutive_failures"] = 0
                save_failure_state(state_path, state)
            if not signal_present:
                return
            try:
                log("· [拆件起活] 子进程已退出、信号仍在，链式再起一轮")
            except Exception:  # noqa: BLE001
                pass
            dispatch_headless_patrol(
                repo_root, audit=audit, evaluator=evaluator, log=log,
                popen=popen, pid_alive=pid_alive, run_in_thread=run_in_thread,
                alert_send=alert_send, monotonic=monotonic, sleep=sleep,
                failure_state_path=state_path,
            )
            return

        consecutive = int(state.get("consecutive_failures", 0)) + 1
        state["consecutive_failures"] = consecutive
        save_failure_state(state_path, state)
        detail = (
            f"无头 Codex（pid={getattr(proc, 'pid', 0)}）夭折——存活 {alive_seconds:.1f}s，"
            f"退出码 {returncode}，无消费进展={no_progress}，连续第 {consecutive} 次；日志尾部：{_read_log_tail(log_path)}"
        )
        _record(audit, evaluator, DispatchResult(
            ACTION_CHILD_FAILED, detail=detail, pid=getattr(proc, "pid", None), log_path=log_path,
        ), log=log)

        if consecutive >= FAILURE_ALERT_THRESHOLD:
            halt_detail = (
                f"连续 {consecutive} 次夭折，停止链式重试——信号原样留着、不消费。"
                f"请检查 {log_path or '（无日志路径）'}。"
            )
            _record(audit, evaluator, DispatchResult(ACTION_CHAIN_HALTED, detail=halt_detail), log=log)
            if alert_send is not None:
                try:
                    alert_send(f"⚠ 拆件巡逻无头会话{halt_detail}")
                except Exception:  # noqa: BLE001
                    pass
            return

        if not signal_present:
            return  # 没有待处理信号——等下一条真实回件到达再触发，不必重试。

        try:
            sleep(_backoff_seconds(consecutive))
        except Exception:  # noqa: BLE001
            pass
        dispatch_headless_patrol(
            repo_root, audit=audit, evaluator=evaluator, log=log,
            popen=popen, pid_alive=pid_alive, run_in_thread=run_in_thread,
            alert_send=alert_send, monotonic=monotonic, sleep=sleep,
            failure_state_path=state_path,
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
    prefix = {
        "started": "✓", "skipped_busy": "·", "failed": "⚠",
        "child_failed": "⚠", "chain_halted": "⚠",
    }.get(result.action, "·")
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
    alert_send: Optional[Callable[[str], None]] = None,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    failure_state_path: Optional[Path] = None,
) -> DispatchResult:
    """起一个无头 Codex 去执行拆件巡逻章程。绝不向上抛——任何失败都只记
    审计＋日志，不得让 `mark_reply_arrived` 的"绝不向上抛"契约被打破
    （调用方 `_raise_patrol_signal` 已包一层 `except`，本函数自身也不
    应假设那层保护一定存在）。
    """
    try:
        policy = _codex_policy(repo_root)
        if policy.get('enabled') is not True:
            return _record(audit, evaluator, DispatchResult(
                ACTION_PAUSED, detail='Codex 拆件消费者暂停；保留信号，不启动任何模型。',
            ), log=log)
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
                    detail=(f"已有无头 Codex 在跑（pid={existing_pid}），本次不重复起——"
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
        stamp += "-" + uuid.uuid4().hex[:8]
        log_path = log_dir / f"{stamp}.log"

        prompt = _build_prompt(charter_text)
        try:
            initial_signal = patrol_signal.read_signal(repo_root)
        except Exception:
            initial_signal = None

        try:
            log_file = open(log_path, "w", encoding="utf-8")
        except OSError as exc:
            return _record(audit, evaluator, DispatchResult(
                ACTION_FAILED,
                detail=f"起活日志文件建不了，未起活，信号原样留着：{log_path}（{exc}）",
            ), log=log)

        try:
            proc = popen(
                _codex_command(repo_root, log_dir / (stamp + '.evidence'), policy),
                stdin=subprocess.PIPE, stdout=log_file, stderr=subprocess.STDOUT,
                cwd=str(repo_root), text=True,
            )
        except OSError as exc:
            return _record(audit, evaluator, DispatchResult(
                ACTION_FAILED,
                detail=f"起 Codex provider 失败（检查运行配置与证据），"
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
                log_path=str(log_path), alert_send=alert_send,
                monotonic=monotonic, sleep=sleep, failure_state_path=failure_state_path,
                initial_signal=initial_signal,
            )
        except Exception:  # noqa: BLE001 —— 挂后台复查失败不代表进程没起，继续按已起活记
            pass

        return _record(audit, evaluator, DispatchResult(
            ACTION_STARTED, pid=proc.pid, log_path=str(log_path),
            detail=f"无头 Codex 已起（pid={proc.pid}），输出见 {log_path}",
        ), log=log)
    except Exception as exc:  # noqa: BLE001 —— 本函数绝不向上抛，见文首
        return _record(audit, evaluator, DispatchResult(
            ACTION_FAILED, detail=f"起活流程自身异常，信号原样留着：{exc}",
        ), log=log)
