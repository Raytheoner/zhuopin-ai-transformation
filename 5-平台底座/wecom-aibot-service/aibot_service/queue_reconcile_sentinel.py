"""归档↔队列对账哨兵（design D18，队列 #69/#70，2026-07-22，dry-run 模式）。

企微机器人的归档（`intake.py`）与追加队列行（`queue_appender.py`）是两个
独立动作，中间没有事务性保证。2026-07-21 唐燕萍那条归档真实出现过"归档
成功 + `queue_appended` 审计事件都记录成功，但队列文件里从未出现对应行"
的静默丢失（根因见 `queue_appender.py` 模块 docstring：并发写手覆盖，已
补乐观并发重试）。本模块提供一道独立的事后核对，作为该修复之外的第二层
防线——万一还有别的写手/路径导致同类丢失，能被发现而不是永远沉默。

**本次只做 dry-run**：发现疑似漏行只私信 Paul 一条汇总报告，不自动写回
队列。理由：自动补行依赖对队列表格结构又一次解析/编号计算，本身也可能出
错或再次撞上并发写；而且"归档了但没进队列"里也可能包含合理的例外（如
`queue_appender.py` 抛错被上层吞掉、或该消息本就不该进队列），不宜不问
青红皂白就自动补一行。观察一段时间确认误报率可接受后，自动补行留作二期
（登记跨桌任务队列待领行）。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path, PurePath
from typing import Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger

DEFAULT_WITHIN_DAYS = 7


def find_unreconciled_archives(
    audit_events: list[dict],
    queue_text: str,
    *,
    now: datetime,
    within_days: int = DEFAULT_WITHIN_DAYS,
) -> list[dict]:
    """`audit_events` 应为已按 `scenario="wecom-aibot", action="archived"`
    过滤好的审计记录列表。匹配规则：归档文件名（含消歧哈希后缀，`intake.py`
    命名里唯一的部分）整串出现在 `queue_text` 全文里即视为"已覆盖"——不要求
    出现在某一行、不解析表格结构，只做最朴素的子串匹配，避免哨兵自己的解析
    逻辑成为新的误判来源。`within_days` 之外（含时间戳缺失/无法解析）的记录
    不纳入扫描范围，只关心近期新鲜信号，早期历史件不重复提醒。

    返回值按时间戳升序排列，仅含"未在队列文件中找到文件名"的记录。
    """
    cutoff = now - timedelta(days=within_days)
    unreconciled: list[dict] = []
    for event in audit_events:
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
        filename = PurePath(archived_path).name
        if filename not in queue_text:
            unreconciled.append(event)
    unreconciled.sort(key=lambda e: e.get("timestamp", ""))
    return unreconciled


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
    events = audit.query_by(scenario="wecom-aibot", action="archived")
    queue_text = queue_path.read_text(encoding="utf-8") if queue_path.exists() else ""
    unreconciled = find_unreconciled_archives(events, queue_text, now=now, within_days=within_days)
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
