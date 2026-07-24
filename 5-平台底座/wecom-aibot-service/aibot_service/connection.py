"""服务级连接管理：凭据加载 + AibotConnector 构造 + 生命周期事件审计 +
inbound 消息分发给 intake.py（design.md D2/D3/D5/D6）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import (
    AibotClientLike,
    AibotConnector,
    default_client_factory,
)
from zhuopin_platform.shared_tools.secrets import SecretsProvider

from .constants import PAUL_USERID
from .department_group_mapping import load_department_group_mapping
from .department_mapping import load_department_mapping
from .forwarding import forward_inbound_to_paul
from .frame_parsing import parse_inbound_frame
from .group_notify import notify_department_group
from .intake import archive_inbound_message
from .queue_git_sync import DEFAULT_BACKOFF_SECONDS, DEFAULT_MAX_RETRIES, sync_after_archive
from .whitelist import is_whitelisted, NOT_ONBOARDED_REPLY

BOTID_KEY = "WECOM_AIBOT_BOTID"
SECRET_KEY = "WECOM_AIBOT_SECRET"

# design.md D2/D3：应用层重连预算保守封顶，快速交给部署层（计划任务）兜底。
DEFAULT_MAX_RECONNECT_ATTEMPTS = 6
DEFAULT_RECONNECT_BASE_DELAY_MS = 2000
DEFAULT_HEARTBEAT_INTERVAL_MS = 30_000

# 2026-07-17 P0 事故根因（服务 07-16 16:09 CST 起僵尸存活约 33 小时）：SDK 重连
# 预算耗尽后只触发 on_error、不会让进程退出，`_run_forever` 的
# `asyncio.Event().wait()` 因此永久挂起——"交给部署层兜底"从未真正发生，因为
# 部署层（start-aibot-service-dev.ps1 三级退避重启）只在进程真正退出时才生效。
# 用 SDK 报出的这个错误文案识别"重连预算已耗尽、SDK 不会再自己好"的终态信号。
UNRECOVERABLE_ERROR_MARKERS = ("Max reconnect attempts exceeded",)


def _is_unrecoverable_error(err: Exception) -> bool:
    text = str(err)
    return any(marker in text for marker in UNRECOVERABLE_ERROR_MARKERS)


def _audit_lifecycle(audit: AuditLogger, evaluator: str, action: str, **decision) -> None:
    audit.record(
        AuditEvent(
            scenario="wecom-aibot",
            action=action,
            evaluator=evaluator,
            automation_level="L1",
            decision=decision,
            data_sources={},
        )
    )


def build_connector(
    *,
    secrets: SecretsProvider,
    audit: AuditLogger,
    external_docs_root: Path,
    queue_path: Path,
    evaluator: str = "system",
    mapping_path: Optional[Path] = None,
    group_mapping_path: Optional[Path] = None,
    max_reconnect_attempts: int = DEFAULT_MAX_RECONNECT_ATTEMPTS,
    reconnect_base_delay_ms: int = DEFAULT_RECONNECT_BASE_DELAY_MS,
    heartbeat_interval_ms: int = DEFAULT_HEARTBEAT_INTERVAL_MS,
    client_factory: Callable[..., AibotClientLike] = default_client_factory,
    on_fatal_disconnect: Optional[Callable[[], None]] = None,
    repo_root: Optional[Path] = None,
    pending_queue_appends_path: Optional[Path] = None,
    queue_git_remote: str = "origin",
    queue_git_branch: str = "master",
    queue_sync_max_retries: int = DEFAULT_MAX_RETRIES,
    queue_sync_backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
    queue_sync_fallback_send: Optional[Callable[[str], None]] = None,
) -> AibotConnector:
    """构造已接好审计 + 归档分发的 `AibotConnector`；不建立实际连接（调用方
    另行 `await connector.connect()`）。凭据缺失时 `SecretsProvider` 抛
    `KeyError`，不静默用空值启动（spec `wecom-aibot-connector` 要求）。

    `on_fatal_disconnect`：SDK 重连预算耗尽（不可恢复）时调用，供调用方主动
    退出进程、交部署层重启脚本兜底（见 `UNRECOVERABLE_ERROR_MARKERS` 注释）。
    未传时该情形仅记审计、不触发额外动作（向后兼容旧调用方）。

    `repo_root`：D1（design.md，Mac 迁移变更包）队列 git 同步所需的仓库根
    目录——未传时（如测试、或未来某些部署场景不需要此能力）整条同步路径
    直接跳过，不影响既有行为，向后兼容旧调用方。
    """
    bot_id = secrets.get(BOTID_KEY)
    secret = secrets.get(SECRET_KEY)
    mapping = load_department_mapping(mapping_path)
    group_mapping = load_department_group_mapping(group_mapping_path)

    connector_holder: dict[str, AibotConnector] = {}

    def on_connected() -> None:
        _audit_lifecycle(audit, evaluator, "connection_established")

    def on_authenticated() -> None:
        _audit_lifecycle(audit, evaluator, "authenticated")

    def on_disconnected(reason: str) -> None:
        _audit_lifecycle(audit, evaluator, "disconnected", reason=reason)

    def on_reconnecting(attempt: int) -> None:
        _audit_lifecycle(audit, evaluator, "reconnecting", attempt=attempt)

    def on_error(err: Exception) -> None:
        audit.record(
            AuditEvent(
                scenario="wecom-aibot",
                action="connection_error",
                evaluator=evaluator,
                automation_level="L1",
                decision={},
                data_sources={},
                error=str(err),
            )
        )
        if _is_unrecoverable_error(err):
            _audit_lifecycle(audit, evaluator, "fatal_disconnect_detected", error=str(err))
            if on_fatal_disconnect is not None:
                on_fatal_disconnect()

    async def on_message(frame: dict) -> None:
        """门禁①结构性保证的唯一 inbound 入口：只转给 archive_inbound_message
        （归档/登记/队列）+ notify_department_group（归档成功后回部门群通报，
        Paul 2026-07-12 拍板/2026-07-14 落地）+ forward_inbound_to_paul（全量
        转发通知，Paul 2026-07-13 拍板新增），不做任何语义解析/业务分支
        （design.md D8）。三条路径各自 try/except，互不影响——任一失败不影响
        其余两条是否成功。

        前置白名单分流（Paul 2026-07-16 口头需求，队列 #35）：发送人不在
        `whitelist.WHITELISTED_SENDER_USERIDS` 里时，只回一条礼貌回复，
        不进入以上三条路径——机器人尚未正式对外开放，避免同事发来的无关
        消息被误当业务内容处理、污染队列与 Paul 私信。
        """
        message = parse_inbound_frame(frame)

        if not is_whitelisted(message.sender):
            try:
                await connector_holder["connector"].send_markdown(
                    message.sender, NOT_ONBOARDED_REPLY
                )
            except Exception as exc:  # noqa: BLE001 —— 回复失败也要留痕，不影响拒绝已发生的事实
                audit.record(
                    AuditEvent(
                        scenario="wecom-aibot",
                        action="whitelist_reply_failed",
                        evaluator=evaluator,
                        automation_level="L1",
                        decision={"sender": message.sender},
                        data_sources={},
                        error=str(exc),
                    )
                )
            audit.record(
                AuditEvent(
                    scenario="wecom-aibot",
                    action="whitelist_rejected",
                    evaluator=evaluator,
                    automation_level="L1",
                    decision={"sender": message.sender, "msgtype": message.msgtype},
                    data_sources={},
                )
            )
            return

        archive_result = None
        try:
            archive_result = await archive_inbound_message(
                message=message,
                connector=connector_holder.get("connector"),
                external_docs_root=external_docs_root,
                queue_path=queue_path,
                department_mapping=mapping,
                audit=audit,
                evaluator=evaluator,
            )
        except Exception as exc:  # noqa: BLE001 —— 归档失败必须留痕，不得吞掉
            audit.record(
                AuditEvent(
                    scenario="wecom-aibot",
                    action="message_dispatch_failed",
                    evaluator=evaluator,
                    automation_level="L1",
                    decision={"msgtype": message.msgtype, "sender": message.sender},
                    data_sources={},
                    error=str(exc),
                )
            )

        if archive_result is not None and repo_root is not None:
            try:
                await sync_after_archive(
                    repo_root=repo_root,
                    queue_path=queue_path,
                    append_kwargs=archive_result.queue_append_kwargs,
                    audit=audit,
                    connector=connector_holder.get("connector"),
                    recipient=PAUL_USERID,
                    fallback_send=queue_sync_fallback_send,
                    pending_path=pending_queue_appends_path,
                    evaluator=evaluator,
                    remote=queue_git_remote,
                    branch=queue_git_branch,
                    max_retries=queue_sync_max_retries,
                    backoff_seconds=queue_sync_backoff_seconds,
                )
            except Exception as exc:  # noqa: BLE001 —— sync_after_archive 本身不抛，这里是防御性兜底
                audit.record(
                    AuditEvent(
                        scenario="wecom-aibot",
                        action="queue_sync_dispatch_failed",
                        evaluator=evaluator,
                        automation_level="L1",
                        decision={},
                        data_sources={"sender": message.sender},
                        error=str(exc),
                    )
                )

        if archive_result is not None:
            try:
                await notify_department_group(
                    department=archive_result.department,
                    matched=archive_result.matched,
                    sender=message.sender,
                    msgtype=message.msgtype,
                    filename=archive_result.archived_path.name,
                    secrets=secrets,
                    group_mapping=group_mapping,
                    audit=audit,
                    evaluator=evaluator,
                )
            except Exception as exc:  # noqa: BLE001 —— 通报失败必须留痕，不得吞掉
                audit.record(
                    AuditEvent(
                        scenario="wecom-aibot",
                        action="group_notify_dispatch_failed",
                        evaluator=evaluator,
                        automation_level="L1",
                        decision={"department": archive_result.department},
                        data_sources={"sender": message.sender},
                        error=str(exc),
                    )
                )

        try:
            await forward_inbound_to_paul(
                frame=frame,
                message=message,
                connector=connector_holder["connector"],
                audit=audit,
                evaluator=evaluator,
            )
        except Exception as exc:  # noqa: BLE001 —— 转发失败必须留痕，不得吞掉
            audit.record(
                AuditEvent(
                    scenario="wecom-aibot",
                    action="forward_dispatch_failed",
                    evaluator=evaluator,
                    automation_level="L1",
                    decision={"msgtype": message.msgtype, "sender": message.sender},
                    data_sources={},
                    error=str(exc),
                )
            )

    connector = AibotConnector(
        bot_id,
        secret,
        client_factory=client_factory,
        max_reconnect_attempts=max_reconnect_attempts,
        heartbeat_interval_ms=heartbeat_interval_ms,
        reconnect_base_delay_ms=reconnect_base_delay_ms,
        on_connected=on_connected,
        on_authenticated=on_authenticated,
        on_disconnected=on_disconnected,
        on_reconnecting=on_reconnecting,
        on_error=on_error,
        on_message=on_message,
    )
    connector_holder["connector"] = connector
    return connector
