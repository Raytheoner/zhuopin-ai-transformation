"""场景②：收专员反馈自动归档（design.md 对应 spec wecom-feedback-intake）。

门禁①（结构性，design.md D8）：本文件不 import 任何 erp_connector/
srm_connector，代码路径只允许三类动作——写文件归档 / 追加队列行 / 调用
connector 发确认收讫回执。无论消息内容是什么，只落档、不解析执行业务指令。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable, Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector

from .error_text import describe_exception
from .forwarding import is_self_sender
from .department_mapping import UNMATCHED_DEPARTMENT, resolve_department
from .frame_parsing import InboundMessage
from .queue_appender import append_pending_task, QueueEditLock
from .queue_edit_lock import QueueLockBusy
from .queue_lock_pending import record_deferred_append

CORRUPTION_MARKER = "�"  # U+FFFD replacement character

DEPARTMENT_TO_QUEUE_OWNER = {
    "采购部": "采购专线",
    "财务部": "财务专线",
    "质量部": "质量专线",
    "销售部": "销售专线",
    # IT（2026-08-24 补，队列 #387 ⑷）——陈承的来件此前落 `UNMATCHED_QUEUE_
    # OWNER`（"Paul"），与"发送人根本没命中部门映射"共用同一个默认值，读队列
    # 的人分不出这一行到底是"归属明确、只是没配"还是"身份都没认出来"。
    #
    # 🔴 **owner 取 "业务总线"，刻意不写 "IT专线"**：本项目没有 IT 专线这个
    # 角色（`whitelist.py` 顶部原文：「不臆造一个不存在的『IT专线』角色」）。
    # 陈承两次来件（`#385`/`#386`）实际都是由业务总线拆件派发的，"业务总线"
    # 是队列里既有、且与事实相符的 owner 取值。
    "IT": "业务总线",
}
UNMATCHED_QUEUE_OWNER = "Paul"


class ArchiveCorruptionError(RuntimeError):
    """写后读回校验发现文件名/内容含 U+FFFD——中文写入损坏，不得视为归档成功。"""


class UnsupportedMessageTypeError(ValueError):
    pass


@dataclass
class IntakeResult:
    archived_path: Path
    department: str
    matched: bool
    queue_row: Optional[str]
    queue_append_kwargs: dict
    # 队列 #168：队列文件当前被人类会话持锁编辑时，本次追加会被推迟（消息
    # 本体已归档，只差队列这一行）——`queue_row` 此时为 None，调用方
    # （`connection.py::on_message`）据此跳过 `sync_after_archive`（没有行
    # 可同步），等下一条消息到达时由 `flush_pending_queue_appends` 补录。
    queue_append_deferred: bool = False
    # 队列 #387 ⑸：本次**刻意不建**队列行（发送人是 Shao Peishen 本人）。
    # 与 `queue_append_deferred` 是两件不同的事，不能复用同一个字段——
    # deferred 的含义是「这一行还欠着，等下次补录」，skipped 的含义是
    # 「这一行本就不该存在」。混用会让补录链路去补一条永远不该补的行。
    queue_append_skipped: bool = False
    # 队列 #416 ⑸：本次回件配到的跟进信编号（如 `财务部#15`），由调用方
    # 注入的 `letter_number_resolver` 只读预配对得出；配不上/未注入为 None。
    # 它同时被写进归档文件名，并被 `forwarding` 用于 ⑷ 的内容描述——**一次
    # 解析、两处消费**，不让两边各查一遍再各自漂移。
    letter_number: Optional[str] = None


def _safe_filename_component(text: str, max_len: int = 60) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\r\n]', "_", text).strip()
    return cleaned[:max_len] or "未命名"


def _build_filename(
    department: str, sender: str, date_str: str, topic: str, ext: str, disambiguator: str,
    letter_number: Optional[str] = None,
) -> str:
    # 与既有跟进信 R4 命名律（主题-对象-日期-事项）对齐：部门-发送人-回复-日期-事项。
    # disambiguator（msgid 短后缀，缺失时用微秒级时间戳）防止同发送人同天多条
    # 消息互相覆盖文件——2026-07-13 真实联调发现原实现按日期粒度会静默覆盖。
    #
    # 队列 #416 ⑸：`letter_number`（如 `财务部#15`）给出时插在**日期之前**，
    # 不追在末尾——末尾会被 `followup_gate._ARCHIVE_NAME_RE` 里贪婪的
    # `<topic>` 吞掉，stem 逐字比对随即失效（那条正则已同步放开这一段）。
    # 编号取**规范形态原样**（含部门前缀，与 README 编号列、审计
    # `letter_number` 字段逐字相同），不另造一套短写法：两套写法迟早分叉。
    number_segment = f"{_safe_filename_component(letter_number, 40)}-" if letter_number else ""
    return (
        f"{_safe_filename_component(department)}-{_safe_filename_component(sender)}-"
        f"回复-{number_segment}{date_str}-{_safe_filename_component(topic)}-"
        f"{disambiguator}{ext}"
    )


def _verify_no_corruption(
    path: Path, expected_name: str, *, expected_size: Optional[int] = None
) -> None:
    """写后读回校验：文件名不含 U+FFFD（乱码哨兵，防中文写入损坏）。

    `expected_size` 给出时（file 类消息，写的是二进制字节）只做字节数比对
    ——**不得**对二进制内容做 UTF-8 解码校验（2026-07-13 真实联调发现的
    bug：原实现无差别对所有归档文件做 `read_text(encoding="utf-8")`，一份
    正常下载的真实 docx 被误判为"写入损坏"，因为 docx 本质是 ZIP 二进制，
    UTF-8 解码必然失败——这是校验逻辑的假阳性，不是真损坏）。
    `expected_size` 为 None 时（text 类消息）沿用原有文本内容 U+FFFD 校验。
    """
    if CORRUPTION_MARKER in path.name:
        raise ArchiveCorruptionError(f"归档文件名含 U+FFFD 替换字符：{path.name!r}")
    if path.name != expected_name:
        raise ArchiveCorruptionError(
            f"读回文件名与写入不一致：期望 {expected_name!r}，实得 {path.name!r}"
        )

    if expected_size is not None:
        actual_size = path.stat().st_size
        if actual_size != expected_size:
            raise ArchiveCorruptionError(
                f"归档文件字节数与下载内容不一致（疑似写入损坏）："
                f"期望 {expected_size}，实得 {actual_size}"
            )
        return

    try:
        sample = path.read_text(encoding="utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ArchiveCorruptionError(f"归档文件内容解码失败（疑似写入损坏）：{exc}") from exc
    if CORRUPTION_MARKER in sample:
        raise ArchiveCorruptionError(f"归档文件内容含 U+FFFD 替换字符：{path}")


async def archive_inbound_message(
    *,
    message: InboundMessage,
    connector: Optional[AibotConnector],
    external_docs_root: Path,
    queue_path: Path,
    department_mapping: dict[str, str],
    audit: AuditLogger,
    evaluator: str = "system",
    queue_lock: Optional[QueueEditLock] = None,
    pending_lock_path: Optional[Path] = None,
    letter_number_resolver: Optional[Callable[[str, Optional[str]], Optional[str]]] = None,
    media_download: Optional[Callable[[str, Optional[str], str], Awaitable[tuple]]] = None,
) -> IntakeResult:
    """`letter_number_resolver`（队列 #416 ⑸，默认 None ＝ 老行为）：
    `(拟用文件名, 部门或None) -> 编号或None` 的**只读**查询，用来在落盘前
    拿到「这份回件回灌到哪一封信」。**以回调注入、不在本模块 import 桥模块**
    ——门禁①（见文件头）保证的是本文件的代码路径只做那三类动作，一个只读
    查询由调用方提供、在这里消费，那条结构性保证仍然成立；真要把跟进信
    README 的解析搬进来，门禁① 就名存实亡了（同 `connection.py` 把
    `mark_reply_arrived` 放在 `on_message` 而不是这里的理由）。

    `media_download`（队列 #416 ⑴，默认 None ＝ 直接调 `connector.download_file`）：
    `(url, aes_key, stage) -> (bytes, filename)` 的带重试/可配超时版下载。
    """
    department = resolve_department(message.sender, department_mapping)
    matched = department != UNMATCHED_DEPARTMENT
    target_dir = external_docs_root / department
    target_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(tz=timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    sender_label = message.sender or "未知发送人"
    # msgid 是企微给每条消息的唯一 ID，优先用作防覆盖后缀；缺失（如合成测试）
    # 时退化为微秒级时间戳，仍能区分同一天内的多条消息。
    disambiguator = message.msgid or now.strftime("%H%M%S%f")

    expected_size: Optional[int] = None
    letter_number: Optional[str] = None
    if message.msgtype == "text":
        content = message.text_content or ""
        filename = _build_filename(
            department, sender_label, date_str, "文本反馈", ".md", disambiguator
        )
        target_path = target_dir / filename
        target_path.write_text(content, encoding="utf-8")
    elif message.msgtype == "file":
        if connector is None:
            raise RuntimeError("收到文件消息但未提供 connector，无法解密下载")
        if not message.file_url:
            raise ValueError("文件消息缺 file_url，无法下载")
        # 队列 #416 ⑴：下载走带重试/可配超时的通道（未注入时退回裸调用，
        # 保持向后兼容）。耗尽重试抛 `MediaTransferError`，由 `connection.py`
        # 兜底并**请发件人重发**——🔴 不静默跳过。
        if media_download is not None:
            raw_bytes, downloaded_name = await media_download(
                message.file_url, message.file_aes_key, "download_inbound"
            )
        else:
            raw_bytes, downloaded_name = await connector.download_file(
                message.file_url, message.file_aes_key
            )
        source_name = message.file_name_hint or downloaded_name or "attachment"
        stem = Path(source_name).stem or "attachment"
        ext = Path(source_name).suffix or ""
        # 队列 #416 ⑸：先用**不含编号**的拟用文件名做只读预配对，拿到编号
        # 后再拼最终文件名。两步都用同一个 stem/日期，配对结论因此与随后
        # `mark_reply_arrived` 对**最终**文件名的配对一致（编号段被那条正则
        # 单独识别，不进 `<topic>`）。任何一步拿不到编号，就落回老命名。
        prospective = _build_filename(
            department, sender_label, date_str, stem, ext, disambiguator
        )
        if letter_number_resolver is not None:
            letter_number = letter_number_resolver(
                prospective, department if matched else None
            )
        filename = _build_filename(
            department, sender_label, date_str, stem, ext, disambiguator,
            letter_number=letter_number,
        )
        target_path = target_dir / filename
        target_path.write_bytes(raw_bytes)
        expected_size = len(raw_bytes)
    else:
        raise UnsupportedMessageTypeError(f"未支持的消息类型：{message.msgtype}")

    try:
        _verify_no_corruption(target_path, filename, expected_size=expected_size)
    except ArchiveCorruptionError as exc:
        audit.record(
            AuditEvent(
                scenario="wecom-aibot",
                action="archive_corruption_detected",
                evaluator=evaluator,
                automation_level="L1",
                decision={"path": str(target_path)},
                data_sources={"sender": sender_label, "department": department},
                error=describe_exception(exc),
            )
        )
        raise

    audit.record(
        AuditEvent(
            scenario="wecom-aibot",
            action="archived",
            evaluator=evaluator,
            automation_level="L1",
            decision={
                "department": department,
                "matched": matched,
                "archived_path": str(target_path),
                # 队列 #416 ⑸：编号同时写进文件名与审计，两处一致。
                "letter_number": letter_number or "",
            },
            # 队列 #279：chatid/chattype 随归档事件一并留痕——此前从未记录，
            # 群聊消息即便真实到达也查不出是哪个群发来的（队列 #270 卡在
            # 拿不到群 chatid 正是这个空洞）。None 时序列化为空字符串，
            # 与既有 sender/msgtype 字段保持同一"缺失即空串"约定。
            data_sources={
                "sender": sender_label,
                "msgtype": message.msgtype,
                "chatid": message.chatid or "",
                "chattype": message.chattype or "",
            },
        )
    )
    if not matched:
        audit.record(
            AuditEvent(
                scenario="wecom-aibot",
                action="mapping_unmatched",
                evaluator=evaluator,
                automation_level="L1",
                decision={"sender": sender_label},
                data_sources={"department_mapping_keys": ",".join(sorted(department_mapping))},
            )
        )

    owner = DEPARTMENT_TO_QUEUE_OWNER.get(department, UNMATCHED_QUEUE_OWNER)
    task_desc = (
        f"企微反馈自动归档：{sender_label} 发来{('文件 ' + filename) if message.msgtype == 'file' else '文本反馈'}"
        + ("" if matched else "（发送人身份待确认，未命中部门映射表）")
    )
    # 队列里只留仓库相对路径（不暴露本机绝对路径/用户名/worktree 哈希，也让
    # 指针在不同机器/沙箱环境下仍然有意义）——2026-07-13 真实联调发现原实现
    # 把 target_path 的完整绝对路径写进了正式队列文件，已修复。
    relative_pointer = Path(external_docs_root.name) / department / filename
    # queue_append_kwargs 原样保留本次调用参数——D1（design.md，Mac 迁移变更包）
    # 的 git 层同步在推送冲突时需要用这份原始参数重新调用 append_pending_task
    # 对最新内容重算插入点/编号，而不是重放这次已经算好、可能已过期的行。
    queue_append_kwargs = dict(
        description=task_desc,
        owner=owner,
        input_pointer=f"`{relative_pointer.as_posix()}`",
        expected_output="核实内容并按需处理；如需回灌口径按各域三步法走",
        date_str=date_str,
    )

    # 🔴 队列 #387 ⑸（Shao Peishen 2026-08-24 拍板原话：「就按这个办：把对你
    # 本人的入站消息直接不建队列行」）：**发送人是他本人时不建队列行。**
    #
    # 他是任务的发起方，不是「需要被拆件的外部来件」。此前他每在群里说一句
    # 话就产生一条待领行——实测已积 15 条，其中 14 条由 2026-08-06／08-12
    # 两班拆件巡逻逐条人工关闭（理由一律是「非业务反馈、系采集 chatid 的标注
    # 测试短信、无需回灌」）。**代价不是留下一堆孤儿行，而是每一条都真实
    # 消耗了一次拆件巡逻的人力去关掉一条注定无意义的行。**
    #
    # ⚠️ **归档本身保留**：文件照常落 `7-外部文档/`，留痕一条不丢；不建的
    # 只是那条待领行。
    #
    # 🔴 **判据刻意与 `forwarding.py::should_forward` 同源**（那里已有一条
    # 同语义判定，审计 reason 写作 `sender_is_paul`）——**不新造第二套「谁是
    # 本人」的判定**，两处判据一旦分叉，就会出现「转发认得他、队列不认得他」
    # 这类只在特定消息上才暴露的偏差。
    # 队列 #416 ⑺：判据收敛到 `forwarding.is_self_sender` 这一处唯一实现
    # ——原来这里是自己写的第二份 `== PAUL_USERID`，与转发侧「同源」只是
    # 靠注释约定；第三处（对账哨兵）就是这么漏掉的。
    if is_self_sender(message.sender):
        audit.record(
            AuditEvent(
                scenario="wecom-aibot",
                action="queue_append_skipped",
                evaluator=evaluator,
                automation_level="L1",
                decision={"reason": "sender_is_paul", "owner": owner},
                data_sources={"sender": sender_label, "queue_path": str(queue_path)},
            )
        )
        return IntakeResult(
            archived_path=target_path,
            department=department,
            matched=matched,
            queue_row=None,
            queue_append_kwargs=queue_append_kwargs,
            queue_append_skipped=True,
            letter_number=letter_number,
        )

    try:
        queue_row = append_pending_task(
            queue_path, audit=audit, lock=queue_lock, **queue_append_kwargs
        )
    except QueueLockBusy:
        # 队列 #168：队列文件当前被人类会话持锁编辑——消息本体已在上面归档
        # 成功，只是这一行推迟。存进暂存 JSONL，下次消息到达时由
        # `flush_pending_queue_appends` 补录，不在此处阻塞/重试等待（人类
        # 持锁窗口可长达数分钟，同步等待会拖住整个消息处理）。
        if pending_lock_path is not None:
            record_deferred_append(
                pending_lock_path,
                {
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "sender": sender_label,
                    "append_kwargs": queue_append_kwargs,
                },
            )
        audit.record(
            AuditEvent(
                scenario="wecom-aibot",
                action="queue_append_deferred_lock_busy",
                evaluator=evaluator,
                automation_level="L1",
                decision={"owner": owner},
                data_sources={"sender": sender_label, "queue_path": str(queue_path)},
            )
        )
        return IntakeResult(
            archived_path=target_path,
            department=department,
            matched=matched,
            queue_row=None,
            queue_append_kwargs=queue_append_kwargs,
            queue_append_deferred=True,
            letter_number=letter_number,
        )

    audit.record(
        AuditEvent(
            scenario="wecom-aibot",
            action="queue_appended",
            evaluator=evaluator,
            automation_level="L1",
            decision={"owner": owner},
            data_sources={"queue_path": str(queue_path)},
        )
    )

    return IntakeResult(
        archived_path=target_path,
        department=department,
        matched=matched,
        queue_row=queue_row,
        queue_append_kwargs=queue_append_kwargs,
        letter_number=letter_number,
    )
