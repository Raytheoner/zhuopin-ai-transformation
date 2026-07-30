"""企微智能机器人服务入口——读 .env → 建连接 → 阻塞运行（部署层用计划任务
包起来常驻，见 ../deploy-server.ps1）。

环境变量：
  WECOM_AIBOT_BOTID / WECOM_AIBOT_SECRET   必填，凭据（见 SecretsProvider）
  WECOM_AIBOT_EXTERNAL_DOCS_ROOT           可选，默认 <repo_root>/7-外部文档
  WECOM_AIBOT_QUEUE_PATH                   可选，默认 <repo_root>/1-转型规划/0-全景路线图/跨桌任务队列.md
  WECOM_AIBOT_AUDIT_PATH                   可选，默认 <repo_root>/5-平台底座/wecom-aibot-service/reports/wecom_aibot_audit.jsonl
  WECOM_AIBOT_REPO_ROOT                    可选，显式指定 git 同步/审计路径锚定的仓库根，
                                            绕开下方"以队列文件动态解析"的默认逻辑（队列 #126）

队列 #126：本服务常驻的 checkout（如 `ops/wecom-service-home` worktree）与
`WECOM_AIBOT_QUEUE_PATH` 实际指向的 checkout（通常是主工作区）可能不是同一
个——`REPO_ROOT` 不再直接拿本脚本自身位置反推的值使用，而是以已解析出的
`queue_path` 为锚点动态问 git 它真正所属的仓库根在哪（见
`aibot_service.repo_paths.resolve_repo_root`），据此定位的仓库根同时也是
审计文件（`WECOM_AIBOT_AUDIT_PATH` 默认值）的统一落盘位置——与一次性脚本
`push_followup_letter.py` 共用同一份物理文件，消除收发留痕分裂。
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from dotenv import load_dotenv

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.notifiers import wecom
from zhuopin_platform.shared_tools.secrets import EnvSecretsProvider

SERVICE_DIR = Path(__file__).resolve().parent.parent
NAIVE_REPO_ROOT = SERVICE_DIR.parents[1]  # 5-平台底座/wecom-aibot-service -> 本 checkout 自身的根

sys.path.insert(0, str(SERVICE_DIR))
from aibot_service.connection import build_connector  # noqa: E402
from aibot_service.constants import PAUL_USERID  # noqa: E402
from aibot_service.gap_alert import build_reconnect_notice, last_event_timestamp, send_gap_alert  # noqa: E402
from aibot_service.queue_reconcile_sentinel import run_reconciliation_sentinel  # noqa: E402
from aibot_service.repo_paths import resolve_audit_path, resolve_repo_root  # noqa: E402


class ConnectionAbandonedError(RuntimeError):
    """SDK 重连预算耗尽、判定不可恢复——需要让本进程退出，交部署层
    （start-aibot-service-dev.ps1 三级退避重启）重新拉起一个干净的连接。
    2026-07-17 P0 事故：此前没有这个退出路径，进程会在
    `asyncio.Event().wait()` 里僵尸存活，部署层的重启逻辑永远等不到进程
    退出、也就永远不会触发。"""


async def _run_forever(
    connector,
    audit_path: Path,
    audit: AuditLogger,
    fatal_event: asyncio.Event,
    fallback_send: Optional[Callable[[str], None]] = None,
    queue_path: Optional[Path] = None,
) -> None:
    # 必须在 connect() 之前读——建连会写新的审计事件，建连后再读会读到刚写
    # 入的"连接成功"事件本身，间隔恒为 0，判断不出真实中断时长。
    last_ts = last_event_timestamp(audit_path)

    await connector.connect()
    await asyncio.sleep(1)  # 等 aibot_subscribe 认证完成（connect() 只等 WS 握手，不等鉴权）

    # Paul 2026-07-19 要求：不管这次中断长短，每次(重)连接都要发一条通报
    # （此前只在超阈值时才通知，短间隔重连收不到任何确认消息）。
    notice_text = build_reconnect_notice(last_ts, datetime.now(timezone.utc))
    await send_gap_alert(
        connector, audit, notice_text, PAUL_USERID,
        fallback_send=fallback_send,
        last_event_at=last_ts.isoformat() if last_ts else "",
    )

    # 归档↔队列对账哨兵（design D18，队列 #69/#70，2026-07-22，dry-run）——
    # 同样每次连接成功后跑一次；发现疑似漏行只私信 Paul 一条汇总报告，不
    # 自动写队列（见模块 docstring）。queue_path 未提供时（如测试场景）跳过。
    if queue_path is not None:
        await run_reconciliation_sentinel(
            connector, audit, queue_path, PAUL_USERID, now=datetime.now(timezone.utc)
        )

    await fatal_event.wait()
    raise ConnectionAbandonedError("企微连接不可恢复（SDK重连预算耗尽），退出进程交部署层重启")


def main() -> None:
    load_dotenv(SERVICE_DIR.parent / ".env")  # 5-平台底座/.env（照 SC8 .env 放置层级）

    queue_path = Path(
        os.environ.get(
            "WECOM_AIBOT_QUEUE_PATH",
            NAIVE_REPO_ROOT / "1-转型规划" / "0-全景路线图" / "跨桌任务队列.md",
        )
    )
    # 队列 #126：本 checkout（`NAIVE_REPO_ROOT`）与 `queue_path` 实际所在的
    # checkout 可能不是同一个（服务常驻某 worktree、队列文件固定指向主工
    # 作区）——以 `queue_path` 动态反查其真正所属的仓库根，`NAIVE_REPO_ROOT`
    # 只作解析失败时的回落值。
    resolved_repo_root = resolve_repo_root(queue_path, fallback=NAIVE_REPO_ROOT)

    external_docs_root = Path(
        os.environ.get("WECOM_AIBOT_EXTERNAL_DOCS_ROOT", resolved_repo_root / "7-外部文档")
    )
    audit_path = Path(
        os.environ.get("WECOM_AIBOT_AUDIT_PATH", resolve_audit_path(resolved_repo_root))
    )
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    pending_queue_appends_path = SERVICE_DIR / "reports" / "pending_queue_appends.jsonl"
    # 队列 #168：机器人本地追加队列行前占用协议〇.7 共享编辑锁，占用中推迟
    # 补录而不是直接写盘覆盖人类正在编辑的内容——见 connection.py::
    # build_connector 的 `enable_queue_edit_lock` 文档。
    pending_lock_path = SERVICE_DIR / "reports" / "pending_queue_lock_appends.jsonl"

    secrets = EnvSecretsProvider()
    audit = AuditLogger.jsonl(audit_path)
    fatal_event = asyncio.Event()

    # gap_alert 兜底通道——与本服务自身的智能机器人长连接是两套独立凭据/
    # 通道（见 CLAUDE.md §3「告警兜底」），主通道恰好在自身连接故障期间
    # 发送提醒失败时（2026-07-19 真实事故），改走这条不依赖同一条连接的
    # webhook 通道。未配置则维持原样（只记录失败，不崩溃）。队列 git 同步
    # 降级告警（D1）复用同一条通道。
    webhook_url = os.environ.get("WECOM_WEBHOOK_URL")
    fallback_send = (
        (lambda text: wecom.send_text(webhook_url, f"⚠️ 企微智能机器人服务：{text}"))
        if webhook_url else None
    )

    connector = build_connector(
        secrets=secrets,
        audit=audit,
        external_docs_root=external_docs_root,
        queue_path=queue_path,
        on_fatal_disconnect=fatal_event.set,
        repo_root=resolved_repo_root,
        pending_queue_appends_path=pending_queue_appends_path,
        queue_sync_fallback_send=fallback_send,
        enable_queue_edit_lock=True,
        pending_lock_path=pending_lock_path,
    )

    asyncio.run(_run_forever(connector, audit_path, audit, fatal_event, fallback_send, queue_path))


if __name__ == "__main__":
    main()
