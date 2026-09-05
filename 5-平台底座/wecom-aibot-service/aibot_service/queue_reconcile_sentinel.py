"""归档↔队列对账哨兵（design D18，队列 #69/#70，2026-07-22；判据 2026-07-25
起改审计日志内部配对，队列 #107）。

企微机器人的归档（`intake.py`）与追加队列行（`queue_appender.py`）是两个
独立动作，中间没有事务性保证。2026-07-21 唐燕萍那条归档真实出现过"归档
成功 + `queue_appended` 审计事件都记录成功，但队列文件里从未出现对应行"
的静默丢失（根因见 `queue_appender.py` 模块 docstring：并发写手覆盖，已
补乐观并发重试）。本模块提供一道独立的事后核对，作为该修复之外的第二层
防线——万一还有别的写手/路径导致同类丢失，能被发现而不是永远沉默。

**判据变迁（队列 #107）**：初版判据是"归档文件名 vs 队列全文子串匹配"——
2026-07-25 dry-run 首跑报 10 条疑似漏行，总线只读复核确认**10 条全为
误报**：均已处理完、行已被 07-24 首次清扫迁入《跨桌任务队列-归档-
YYYYMM.md》，而哨兵当时只扫**现役队列**正文，匹配不到即误报，且逐周
恶化（归档越多误报越多，此前 #99 意图的"扫归档件"当时未生效）。**改为
审计日志内部配对**：`intake.py::archive_inbound_message` 对每条消息总是
先记一条 `archived`、随后立刻记一条 `queue_appended`（顺序固定，全库唯一
emitter，见 `intake.py`/`queue_appender.py`）；`connection.py::on_message`
逐条 `await` 顺序处理消息，同一条连接上至多同时有一条消息"在途"——据此
按**单件在途**（非普通 FIFO 队列，见 `find_unreconciled_archives` 函数
docstring 为何两者不等价）配对：某条 `archived` 若直到下一条 `archived`
出现前都没等到配对的 `queue_appended`（如 `append_pending_task` 重试耗尽
抛错，异常发生在 `queue_appended` 记录之前）才是真实漏行。此判据只看审计
日志本身，与队列文件里那一行现在躺在哪个文件、编号是多少、措辞是否被
改写全部无关，天然 robust 于清扫/改号/改措辞。`queue_text`（现役队列正文
+ 归档件，见 `_collect_reconciliation_text`）降级为**可选二级交叉校验**
——配对判定为"未配对"时，若文件名仍能在 `queue_text` 里找到，则不视为真
漏行（配对判据备注"兜底可保留扫现役+归档件作二次校验"）：这层交叉校验只
用于兜底覆盖配对本身理论上可能漏配的边界情形，不会掩盖真实漏行（真漏行
的文件名不会出现在队列文本任何地方）。

**本次只做 dry-run**：发现疑似漏行只私信 Paul 一条汇总报告，不自动写回
队列。理由：自动补行依赖对队列表格结构又一次解析/编号计算，本身也可能出
错或再次撞上并发写；而且"归档了但没进队列"里也可能包含合理的例外（如
`queue_appender.py` 抛错被上层吞掉、或该消息本就不该进队列），不宜不问
青红皂白就自动补一行。观察一段时间确认误报率可接受后，自动补行留作二期
（登记跨桌任务队列待领行）。
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path, PurePath
from typing import Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger
from zhuopin_platform.shared_tools.queue_table import iter_queue_paths

from .forwarding import is_self_sender

DEFAULT_WITHIN_DAYS = 7
_ARCHIVE_FILENAME_RE = re.compile(r"^跨桌任务队列-归档-\d{6}\.md$")

# 「这条 `archived` 已经有结论了」的三种事件——见 `find_unreconciled_archives`
# 的队列 #416 ⑺ 段落。三者语义各不相同（追成了／补录成了／本就不该建），
# 但对本模块**只有一个含义**：它不欠一行。
PENDING_CLEARING_ACTIONS = (
    "queue_appended",
    "queue_append_pending_flushed",
    # 队列 #416 ⑺（2026-08-26）：`intake.py` 对「Shao Peishen 本人入站」记的
    # 事件。2026-08-24 已拍板「本人入站不建行（归档保留）」并为此**专门新增**
    # 了这个字段，而哨兵这一侧**从未读过它** ⇒ 他每自己发一条消息，哨兵就
    # 报一条永远修不掉的疑似漏行（2026-08-26 20:18 群内实例）。
    "queue_append_skipped",
)


def find_unreconciled_archives(
    audit_events: list[dict],
    *,
    now: datetime,
    within_days: int = DEFAULT_WITHIN_DAYS,
    queue_text: Optional[str] = None,
) -> list[dict]:
    """`audit_events` 应为按 `scenario="wecom-aibot"` 过滤、按审计日志写入
    顺序（`AuditLogger.query_by` 保留 JSONL 文件的追加顺序，等价于时间顺序）
    排列的记录列表，不要求预先过滤 action（本函数内部只挑出 `archived`/
    `queue_appended`/`queue_append_pending_flushed` 三类，忽略其余）。

    队列 #192-B：`queue_append_pending_flushed`（`queue_lock_pending.py`
    补录锁忙推迟消息成功时记的事件）与 `queue_appended` 一样视为"清空
    pending"——此前只认 `queue_appended`，导致被 #168 推迟过、走补录路径
    成功落队列的消息，在本判据下被误判"未配对"（当日 9 个 archived vs 8
    个 queue_appended，差的正是被补录的那条），只是恰好被下方的 `queue_text`
    二级交叉校验兜住、未造成误报——但那正是 #107 判据变迁想摆脱的"依赖
    文本匹配"退路，理应在配对本身这一层就解决。

    判据（队列 #107，见模块 docstring 判据变迁）：按出现顺序做**单件在途**
    配对——`connection.py::on_message` 逐条 `await` 处理消息，同一条连接上
    至多同时有一条消息"在途"（其 `archived` 已记但 `queue_appended` 尚未
    确定），故不能用普通 FIFO 队列配对（那等价于假设可以有多条同时挂起、
    按到达顺序依次消费，而真实约束是"新 `archived` 出现即说明上一条消息
    已经处理完毕"）。逐条扫描：遇到 `archived` 时，若上一条还留着一个未
    配对的 `pending`，说明它直到下一条消息开始都没等到 `queue_appended`
    ——判定该 `pending` 未配对，并把当前这条记作新的 `pending`；遇到
    `queue_appended` 时清空 `pending`（配对成功）。循环结束后若仍有
    `pending` 留存，也计入未配对候选。

    `within_days` 之外（含时间戳缺失/无法解析）的候选不纳入扫描范围，只
    关心近期新鲜信号，早期历史件不重复提醒。`queue_text` 提供时对候选做
    一次二级交叉校验（子串匹配现役队列+归档件），命中即不视为真漏行；不
    提供时（默认）跳过这层校验，纯以配对结果为准。

    返回值按时间戳升序排列。
    """
    cutoff = now - timedelta(days=within_days)
    unpaired_candidates: list[dict] = []
    pending: Optional[dict] = None
    for event in audit_events:
        action = event.get("action")
        if action == "archived":
            if pending is not None:
                unpaired_candidates.append(pending)
            pending = event
        elif action in PENDING_CLEARING_ACTIONS:
            pending = None
    if pending is not None:
        unpaired_candidates.append(pending)

    unreconciled: list[dict] = []
    for event in unpaired_candidates:
        # 🔴 队列 #416 ⑺ 第二道（判据同源）：发送人是 Shao Peishen 本人时
        # **一律不计入漏行**，判据取自 `forwarding.is_self_sender`——2026-08-24
        # 拍板原文要求「判据与 `forwarding.should_forward` 同源」。
        #
        # 上面那条 `queue_append_skipped` 是**结构性**的（读 `intake` 记下的
        # 结论），这一条是**语义性**的（自己认得他是谁）。两条都留着不是
        # 冗余：只靠事件，`intake` 万一在记那条事件之前就抛了，本人入站又会
        # 变成一条恒真告警；只靠发送人，则读不出 `intake` 后来可能新增的
        # 其它"本就不该建行"情形。**一个永远红着的告警等于把整条哨兵训练
        # 成噪音**——它比漏报更贵，因为它同时废掉了所有真报。
        if is_self_sender((event.get("data_sources") or {}).get("sender")):
            continue
        ts_raw = event.get("timestamp")
        if not ts_raw:
            continue
        try:
            ts = datetime.fromisoformat(ts_raw)
        except ValueError:
            continue
        if ts < cutoff:
            continue
        archived_path = (event.get("decision") or {}).get("archived_path")
        if not archived_path:
            continue
        if queue_text is not None and PurePath(archived_path).name in queue_text:
            continue
        unreconciled.append(event)
    unreconciled.sort(key=lambda e: e.get("timestamp", ""))
    return unreconciled


def _collect_reconciliation_text(queue_path: Path) -> str:
    """拼接队列正文 + 同目录按月归档件《跨桌任务队列-归档-YYYYMM.md》全文，
    供 `find_unreconciled_archives` 做子串匹配。

    协议〇.8（2026-07-24 首次清扫起）：值周巡检每周把 §一/§二/§三/§四 已
    完成行整行迁出正文、搬进同目录按月归档件——迁走后哨兵若只扫正文，会
    把这些"其实已经妥善归档、只是行搬了家"的历史行误判为"疑似漏行"（队列
    #99：07-24 16:40 CST 重连时确已产生过一次这类假阳性私信）。归档件内容
    是已完成行的历史存档、写定后不会再变，一并纳入子串匹配不会引入新的
    误判风险；不做时间窗口过滤（`within_days` 只管审计事件本身的新鲜度，
    归档件是否被扫描与其无关）、不递归子目录、只认严格匹配命名律的文件。

    🔴 队列 #341（2026-09-05）：**两份物理队列文件都要读，不只 `queue_path`
    那一份。** #341 把机器人的写入目标从机制环境文件改回业务场景文件，而
    切换之前若干天里写下的行仍留在机制环境文件里——哨兵若只扫写入目标那
    一份，那些行会被逐条误判为"归档成功但队列里没有对应行"，产生一批假
    阳性私信（形态与 #99 那次"行搬了家就报漏行"完全一致）。这也是 #312
    缺口一"一份拆成两份、下游只跟一份"家族的又一个入口，修法同源：
    按 `iter_queue_paths()` 逐份读、合并，**不拼接后只解析一次**。"""
    directory = queue_path.parent
    seen: set[Path] = set()
    parts: list[str] = []
    for candidate in [queue_path, *(directory / PurePath(rel).name for rel in iter_queue_paths())]:
        if candidate in seen:
            continue
        seen.add(candidate)
        parts.append(candidate.read_text(encoding="utf-8") if candidate.exists() else "")
    if directory.exists():
        for path in sorted(directory.glob("跨桌任务队列-归档-*.md")):
            if _ARCHIVE_FILENAME_RE.match(path.name):
                try:
                    parts.append(path.read_text(encoding="utf-8"))
                except OSError:
                    continue
    return "\n".join(parts)


def build_reconciliation_report(unreconciled: list[dict]) -> Optional[str]:
    """无疑似漏行时返回 `None`（调用方据此判断不发送，不刷屏）。"""
    if not unreconciled:
        return None
    lines = [
        f"⚠️ 归档↔队列对账哨兵（dry-run）：发现 {len(unreconciled)} 条疑似漏行——"
        "归档已成功但队列文件里未找到对应行，仅供人工核实，本次不会自动写队列：",
    ]
    for event in unreconciled:
        archived_path = (event.get("decision") or {}).get("archived_path", "?")
        ts = event.get("timestamp", "?")
        sender = (event.get("data_sources") or {}).get("sender", "?")
        lines.append(f"- {ts} | {sender} | {PurePath(archived_path).name}")
    return "\n".join(lines)


async def run_reconciliation_sentinel(
    connector,
    audit: AuditLogger,
    queue_path: Path,
    recipient: str,
    *,
    now: datetime,
    within_days: int = DEFAULT_WITHIN_DAYS,
) -> None:
    """每次连接成功后调用一次（比照 `gap_alert.send_gap_alert` 的调用时机）。
    整条链路失败（含发送失败）都只审计留痕，不向上抛出——哨兵本身不应影响
    服务主流程。"""
    # 不预先按 action 过滤——find_unreconciled_archives 需要 archived 与
    # queue_appended 两类事件按原始顺序配对（队列 #107），过滤掉其一会破坏
    # 配对所需的完整序列。
    events = audit.query_by(scenario="wecom-aibot")
    queue_text = _collect_reconciliation_text(queue_path)
    unreconciled = find_unreconciled_archives(
        events, now=now, within_days=within_days, queue_text=queue_text,
    )
    report = build_reconciliation_report(unreconciled)
    if report is None:
        return
    try:
        await connector.send_markdown(recipient, report)
    except Exception:  # noqa: BLE001 — 哨兵失败不应阻塞服务本身运行
        audit.record(AuditEvent(
            scenario="wecom-aibot", action="reconcile_sentinel_send_failed", evaluator="system",
            automation_level="L1", decision={"sent": False, "count": len(unreconciled)},
            data_sources={},
        ))
        return
    audit.record(AuditEvent(
        scenario="wecom-aibot", action="reconcile_sentinel_report_sent", evaluator="system",
        automation_level="L1", decision={"sent": True, "count": len(unreconciled)},
        data_sources={},
    ))
