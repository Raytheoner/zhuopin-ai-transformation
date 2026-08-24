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
from .department_group_chatid_mapping import load_department_group_chatid_mapping
from .disconnect_inprogress_alert import DisconnectInProgressMonitor
from .department_mapping import load_department_mapping
from .followup_readme_bridge import LOCK_TARGET as FOLLOWUP_README_LOCK_TARGET
from .followup_readme_bridge import mark_reply_arrived
from .forwarding import forward_inbound_to_paul
from .frame_parsing import parse_inbound_frame
from .group_notify import notify_department_group_via_chatid
from .intake import archive_inbound_message
from .queue_edit_lock import AIBOT_LOCK_WHO, SubprocessQueueEditLock
from .queue_git_sync import (
    DEFAULT_BACKOFF_SECONDS,
    DEFAULT_MAX_RETRIES,
    flush_pending_git_sync_appends,
    sync_after_archive,
)
from .queue_lock_pending import flush_pending_queue_appends
from .repo_paths import resolve_repo_root
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
    group_chatid_mapping_path: Optional[Path] = None,
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
    enable_queue_edit_lock: bool = False,
    pending_lock_path: Optional[Path] = None,
    disconnect_alert_fallback_send: Optional[Callable[[str], None]] = None,
    queue_edit_lock_alert_fallback_send: Optional[Callable[[str], None]] = None,
    group_notify_alert_fallback_send: Optional[Callable[[str], None]] = None,
) -> AibotConnector:
    """构造已接好审计 + 归档分发的 `AibotConnector`；不建立实际连接（调用方
    另行 `await connector.connect()`）。凭据缺失时 `SecretsProvider` 抛
    `KeyError`，不静默用空值启动（spec `wecom-aibot-connector` 要求）。

    `on_fatal_disconnect`：SDK 重连预算耗尽（不可恢复）时调用，供调用方主动
    退出进程、交部署层重启脚本兜底（见 `UNRECOVERABLE_ERROR_MARKERS` 注释）。
    未传时该情形仅记审计、不触发额外动作（向后兼容旧调用方）。

    `repo_root`：D1（design.md，Mac 迁移变更包）队列 git 同步所需的仓库根
    目录——未传时（如测试、或未来某些部署场景不需要此能力）整条同步路径
    直接跳过，不影响既有行为，向后兼容旧调用方。**队列 #126 起本参数不再
    被无条件信任**：`queue_git_sync` 每次调用都会用 `queue_path` 动态解析
    其真正所属的 repo 根（服务常驻的 worktree 与队列文件所在 checkout 可
    能不是同一个），此处传入的值只作解析失败时的回落值。

    `enable_queue_edit_lock`（队列 #168，默认 False——不影响任何既有测试/
    调用方）：True 时，机器人本地追加队列行前会先占用协议〇.7 共享编辑锁
    （见 `queue_edit_lock.SubprocessQueueEditLock`），占用中不写盘、改为
    推迟补录（见 `queue_lock_pending.py`），并在每条新消息到达时先尝试
    补录此前推迟的记录。`pending_lock_path` 给出推迟记录的暂存文件路径，
    留空时按 `<解析出的仓库根>/5-平台底座/wecom-aibot-service/reports/
    pending_queue_lock_appends.jsonl` 取默认值。

    `disconnect_alert_fallback_send`（队列 #193，默认 None——不影响任何既有
    测试/调用方）：断连持续超过阈值（见 `disconnect_inprogress_alert.py`）
    时用它发一条"进行中"提示。**必须是独立 webhook 通道，不能依赖同一条
    故障连接**——断连期间用 `connector.send_markdown` 发送必然失败（与
    `gap_alert.py` 2026-07-19 事故同一教训）。未传时功能整体关闭。

    `group_notify_alert_fallback_send`（队列 #387，默认 None——不影响任何
    既有测试/调用方）：归档回执因**部门群映射缺配**而跳过时用它发一条告警。
    这一类跳过此前只写审计、不惊动任何人——IT 域的回执因此静默丢了整整
    一个月（2026-07-22 补入部门映射起，到 08-24 有人在群里等回执才被发现）。
    未传时只记审计、不发告警，行为与本次改动前一致。⚠️ **只对配置缺口类
    跳过告警**（见 `group_notify.ALERTABLE_SKIP_REASONS`），`sender_unmatched`
    不告警——那一类已有三处可见后果，再加告警只是噪音。

    `queue_edit_lock_alert_fallback_send`（队列 #333③，默认 None——不影响
    任何既有测试/调用方）：机器人 `release` 队列编辑锁被结构校验拒绝（锁
    保持占用）时用它发一条告警，与 `audit`（本函数必填参数，同时用于记
    `queue_edit_lock_release_rejected` 审计事件）一起补上此前"锁为什么迟
    迟不放"的可观测性空白（#333 真实事故：拒绝原因全程无人知道，锁卡满
    30 分钟才被陈旧接管）。未传时只记审计、不发告警，行为与本次改动前
    一致；`enable_queue_edit_lock=False` 时本参数不产生任何效果。
    """
    bot_id = secrets.get(BOTID_KEY)
    secret = secrets.get(SECRET_KEY)
    mapping = load_department_mapping(mapping_path)
    # 队列 #279/#280：归档通报改走 aibot chatid（见下方 notify_department_
    # group_via_chatid 调用点），webhook 版 `group_mapping` 不再被消费——
    # `group_mapping_path` 形参仍保留在签名里（向后兼容任何仍在传它的
    # 调用方/测试，静默忽略而非报错），不再据此加载。
    group_chatid_mapping = load_department_group_chatid_mapping(group_chatid_mapping_path)

    # 队列 #168：锁工具（0-学习与工具/工具-共享文档编辑锁.py）所在仓库根，
    # 只在启用锁时才解析——未启用时不产生任何额外 git 子进程调用，向后
    # 兼容零改动。用 `queue_path` 动态解析（与 #126 同思路），不信任
    # `repo_root`（那是调用方为 git 同步传入的值，两者用途独立，测试里
    # 常常只为其中一个搭建了真实环境）。
    lock_repo_root: Optional[Path] = None
    resolved_pending_lock_path: Optional[Path] = None
    if enable_queue_edit_lock:
        lock_repo_root = resolve_repo_root(queue_path, fallback=repo_root or queue_path.parent)
        resolved_pending_lock_path = pending_lock_path or (
            lock_repo_root / "5-平台底座" / "wecom-aibot-service" / "reports"
            / "pending_queue_lock_appends.jsonl"
        )

    def _make_queue_lock(note: str) -> Optional[SubprocessQueueEditLock]:
        if lock_repo_root is None:
            return None
        return SubprocessQueueEditLock(
            lock_repo_root, queue_path, who=AIBOT_LOCK_WHO, note=note,
            audit=audit, alert_send=queue_edit_lock_alert_fallback_send,
        )

    def _make_followup_readme_lock() -> SubprocessQueueEditLock:
        """S4 桥一（队列 #366 M1）用的锁——目标是跟进信 README，不是队列。

        与 `_make_queue_lock` 共用同一个锁实现（协议〇.7 只有一份，不分叉），
        只换 `target`。`FOLLOWUP_README_LOCK_TARGET` 是仓库相对、正斜杠的
        `PurePosixPath`，理由见 `followup_readme_bridge` 里那段注释。
        """
        return SubprocessQueueEditLock(
            lock_repo_root, FOLLOWUP_README_LOCK_TARGET, who=AIBOT_LOCK_WHO,
            note="回件到达自动标第九态（S4 桥一）",
            audit=audit, alert_send=queue_edit_lock_alert_fallback_send,
        )

    connector_holder: dict[str, AibotConnector] = {}

    # 队列 #193：断连期间"进行中"提示——仅在传入 fallback 通道时才构造/接线
    # monitor（同 `enable_queue_edit_lock` 的特性开关模式）。**不能无条件
    # 构造**：`on_disconnected()` 内部 `asyncio.create_task` 要求当前有运行
    # 中的事件循环，而生产环境的 SDK 回调确实跑在事件循环里，但既有测试
    # 大量直接同步调用 `client.handlers[...][0](...)`（无运行中的循环）——
    # 未启用本特性时必须零副作用，不能让这些既有测试因为多了一个不需要
    # 的功能而报 `RuntimeError: no running event loop`。
    disconnect_monitor: Optional[DisconnectInProgressMonitor] = None
    if disconnect_alert_fallback_send is not None:
        disconnect_monitor = DisconnectInProgressMonitor(
            fallback_send=disconnect_alert_fallback_send,
            reconnect_base_delay_ms=reconnect_base_delay_ms,
        )

    def on_connected() -> None:
        _audit_lifecycle(audit, evaluator, "connection_established")

    def on_authenticated() -> None:
        _audit_lifecycle(audit, evaluator, "authenticated")
        if disconnect_monitor is not None:
            disconnect_monitor.on_recovered()

    def on_disconnected(reason: str) -> None:
        _audit_lifecycle(audit, evaluator, "disconnected", reason=reason)
        if disconnect_monitor is not None:
            disconnect_monitor.on_disconnected()

    def on_reconnecting(attempt: int) -> None:
        _audit_lifecycle(audit, evaluator, "reconnecting", attempt=attempt)
        if disconnect_monitor is not None:
            disconnect_monitor.on_reconnecting(attempt)

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

        队列 #168：每条新消息到达时，先尝试补录此前因编辑锁占用被推迟的
        队列行（与当前这条消息、当前发送人是否在白名单无关——纯粹是"逮到
        机会就把欠的账补上"），与后续处理当前消息互不影响（各自独立
        try/except）。
        """
        message = parse_inbound_frame(frame)

        if enable_queue_edit_lock and resolved_pending_lock_path is not None:
            try:
                await flush_pending_queue_appends(
                    pending_path=resolved_pending_lock_path,
                    queue_path=queue_path,
                    repo_root=lock_repo_root,
                    audit=audit,
                    lock_factory=lambda: _make_queue_lock("补录待锁定追加"),
                    connector=connector_holder.get("connector"),
                    recipient=PAUL_USERID,
                    fallback_send=queue_sync_fallback_send,
                    evaluator=evaluator,
                    remote=queue_git_remote,
                    branch=queue_git_branch,
                    git_sync_pending_path=pending_queue_appends_path,
                )
            except Exception as exc:  # noqa: BLE001 —— 补录失败不应阻塞当前消息处理
                audit.record(
                    AuditEvent(
                        scenario="wecom-aibot",
                        action="pending_lock_flush_dispatch_failed",
                        evaluator=evaluator,
                        automation_level="L1",
                        decision={},
                        data_sources={},
                        error=str(exc),
                    )
                )

        # 队列 #286：同样在每条新消息到达时，先尝试补录此前因"非快进重试
        # 耗尽/网络等真实 git 失败"被暂存进 `pending_queue_appends.jsonl`
        # 的记录——此前该文件没有任何自动 flush 通道，是 #286 三条真实
        # 丢失行的直接成因。不依赖 `enable_queue_edit_lock`（那是编辑锁
        # 特性开关，与"git 推送本身失败"是两回事），只要求已接线 git 同步
        # 能力（`repo_root`/`pending_queue_appends_path` 均非空）。
        if repo_root is not None and pending_queue_appends_path is not None:
            try:
                await flush_pending_git_sync_appends(
                    pending_path=pending_queue_appends_path,
                    repo_root=repo_root,
                    queue_path=queue_path,
                    audit=audit,
                    connector=connector_holder.get("connector"),
                    recipient=PAUL_USERID,
                    fallback_send=queue_sync_fallback_send,
                    evaluator=evaluator,
                    remote=queue_git_remote,
                    branch=queue_git_branch,
                    max_retries=queue_sync_max_retries,
                    backoff_seconds=queue_sync_backoff_seconds,
                    lock_factory=(
                        (lambda: _make_queue_lock("补录git同步失败追加"))
                        if lock_repo_root is not None else None
                    ),
                    lock_pending_path=resolved_pending_lock_path,
                )
            except Exception as exc:  # noqa: BLE001 —— 补录失败不应阻塞当前消息处理
                audit.record(
                    AuditEvent(
                        scenario="wecom-aibot",
                        action="pending_git_sync_flush_dispatch_failed",
                        evaluator=evaluator,
                        automation_level="L1",
                        decision={},
                        data_sources={},
                        error=str(exc),
                    )
                )

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
                queue_lock=_make_queue_lock("归档追加"),
                pending_lock_path=resolved_pending_lock_path,
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

        # 队列 #366 / S4 桥一：回件到达即在跟进信 README 打第九态
        # 「📨 回件已到，待拆件」。
        #
        # 放在 `on_message` 而不是 `intake.archive_inbound_message` 里面，
        # 有两条理由：⑴ `intake.py` 文件头的门禁①明写「代码路径只允许三类
        # 动作——写文件归档／追加队列行／发确认收讫回执」，往里加第四类写盘
        # 动作会让那句结构性保证不再成立；⑵ `sync_after_archive` 这个同族的
        # 旁路增强本来就挂在这一层，保持一致。**「同一次动作」指的是同一条
        # 消息的同一次处理，不是同一个函数体。**
        #
        # 仅在启用编辑锁时执行——桥一的硬约束之一就是「必须走编辑锁，不得
        # 直接写文件绕开协议〇.7」，锁不可用时**宁可不标**，不裸写。
        if (
            archive_result is not None
            and lock_repo_root is not None
            and enable_queue_edit_lock
        ):
            try:
                mark_reply_arrived(
                    archived_filename=archive_result.archived_path.name,
                    repo_root=lock_repo_root,
                    audit=audit,
                    lock_factory=_make_followup_readme_lock,
                    # 队列 #366 / `OP-0823-D`：通道②按收信人定位「最新一封
                    # 已发出的信」，收信人由归档时已解析好的部门给出。
                    # `matched=False`（fail-closed 落 `待分拣`）时这里传的是
                    # `UNMATCHED_DEPARTMENT`，配对侧会据此走 fail-loud 分支，
                    # **不猜**。
                    department=(archive_result.department
                                if archive_result.matched else None),
                    evaluator=evaluator,
                    alert_send=queue_edit_lock_alert_fallback_send,
                )
            except Exception as exc:  # noqa: BLE001 —— 该函数契约是"绝不向上抛"，这里是防御性兜底
                audit.record(
                    AuditEvent(
                        scenario="wecom-aibot",
                        action="followup_readme_bridge_dispatch_failed",
                        evaluator=evaluator,
                        automation_level="L1",
                        decision={},
                        data_sources={"sender": message.sender},
                        error=str(exc),
                    )
                )

        # 队列 #168：队列文件被人类持锁编辑时，archive_inbound_message 会
        # 把本次追加推迟（queue_append_deferred=True，queue_row=None）——
        # 此时本地还没有行可同步，跳过 git 同步（等下一条消息到达时由
        # 上方 flush_pending_queue_appends 补录+同步）。
        # 队列 #387 ⑸：`queue_append_skipped`（发送人是 Shao Peishen 本人，
        # 刻意不建行）同样没有行可同步——但与 deferred 的处置不同：deferred
        # 等下次补录，skipped 是**永不补录**。两者在这里都跳过 git 同步，但
        # 各自的语义写在 `IntakeResult` 的两个独立字段上，不合并。
        if (
            archive_result is not None
            and repo_root is not None
            and not archive_result.queue_append_deferred
            and not archive_result.queue_append_skipped
        ):
            try:
                await sync_after_archive(
                    repo_root=repo_root,
                    queue_path=queue_path,
                    append_kwargs=archive_result.queue_append_kwargs,
                    already_appended_row=archive_result.queue_row,
                    audit=audit,
                    connector=connector_holder.get("connector"),
                    recipient=PAUL_USERID,
                    fallback_send=queue_sync_fallback_send,
                    pending_path=pending_queue_appends_path,
                    lock_pending_path=resolved_pending_lock_path,
                    evaluator=evaluator,
                    remote=queue_git_remote,
                    branch=queue_git_branch,
                    max_retries=queue_sync_max_retries,
                    backoff_seconds=queue_sync_backoff_seconds,
                    lock_factory=lambda: _make_queue_lock("git冲突重算追加"),
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
            # 队列 #279/#280：部门群通报改走机器人 chatid 通道（原"部门群
            # webhook 通报"，`group_notify.py::notify_department_group`，
            # webhook 单向、群成员回复进不到任何地方）——四个部门真实
            # chatid 已于 2026-08-06 采集验证完毕（含新增"跨部门"），与
            # 跟进信群 cc（`delivery.push_followup(cc_group_chatid=...)`）
            # 共用同一份 `department_group_chatid_mapping.py` 映射表。
            # webhook 版函数仍保留在 `group_notify.py`（未删除，留观察期
            # 回滚余地），只是不再从这里调用。
            try:
                await notify_department_group_via_chatid(
                    department=archive_result.department,
                    matched=archive_result.matched,
                    sender=message.sender,
                    msgtype=message.msgtype,
                    filename=archive_result.archived_path.name,
                    connector=connector_holder.get("connector"),
                    chatid_mapping=group_chatid_mapping,
                    audit=audit,
                    evaluator=evaluator,
                    # 队列 #387 ⑶：回执按**来源群**回，不按发送人所属部门
                    # 回——这两个字段是入站帧本来就带着的（#279 已提取进
                    # `InboundMessage`），此前一路传到这里却从未被消费。
                    source_chatid=message.chatid,
                    source_chattype=message.chattype,
                    # 队列 #387：映射缺配不再静默跳过，复用同一条独立
                    # webhook 告警通道（未配置时为 None，功能自动关闭）。
                    alert_send=group_notify_alert_fallback_send,
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
