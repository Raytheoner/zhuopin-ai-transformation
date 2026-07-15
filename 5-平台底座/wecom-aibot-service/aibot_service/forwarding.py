"""进件全量转发给 Paul（Paul 2026-07-13 拍板，进件逻辑升级）。

机器人收到的所有消息与文件（任何发件人、私聊或群 @ 均含），**除既有归档/
通报流程外**，一律同步转发 Paul 私信一份，附头部信息：发件人+来源
（单聊/群名）+时间；文件原样转发。排除项：心跳（协议层处理，从不到达
本模块）与"机器人自身消息"——本实现把后者理解为"发送人就是 Paul 本人"
时跳过（转发给自己毫无意义）。**"测试指令"排除项的具体判定规则 Paul
未给出明确定义，本次不做内容层面的猜测性过滤**（宁可全转发、不漏发，
比猜错过滤规则更安全）；需要该规则时请 Paul 给出具体判定条件。

本模块与 `intake.py` 的归档流程相互独立、互不影响——转发失败不影响
归档是否成功，归档失败也不影响转发是否成功（`connection.py` 里分别
try/except）。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from zhuopin_platform.audit import AuditEvent, AuditLogger
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector

from .constants import PAUL_USERID
from .frame_parsing import InboundMessage


def _source_label(frame: dict[str, Any]) -> str:
    body = frame.get("body", {}) or {}
    if body.get("chattype") == "group":
        return f"群聊（chatid={body.get('chatid', '未知')}）"
    return "私聊"


def should_forward(message: InboundMessage) -> bool:
    """排除"机器人自身消息"——发送人是 Paul 本人时跳过（转发给自己无意义）。
    心跳帧从不到达本函数（WS 协议层已处理，不会分发为 message 事件）。
    """
    if message.sender == PAUL_USERID:
        return False
    return True


async def forward_inbound_to_paul(
    *,
    frame: dict[str, Any],
    message: InboundMessage,
    connector: AibotConnector,
    audit: AuditLogger,
    evaluator: str = "system",
) -> None:
    if not should_forward(message):
        audit.record(
            AuditEvent(
                scenario="wecom-aibot",
                action="inbound_forward_skipped",
                evaluator=evaluator,
                automation_level="L1",
                decision={"sender": message.sender, "reason": "sender_is_paul"},
                data_sources={},
            )
        )
        return

    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    source = _source_label(frame)
    header = f"【转发】发件人：{message.sender}\n来源：{source}\n时间：{now}"

    if message.msgtype == "text":
        await connector.send_markdown(PAUL_USERID, f"{header}\n\n{message.text_content or ''}")
    elif message.msgtype == "file":
        await connector.send_markdown(PAUL_USERID, header)
        if message.file_url:
            raw_bytes, downloaded_name = await connector.download_file(
                message.file_url, message.file_aes_key
            )
            filename = message.file_name_hint or downloaded_name or "attachment"
            upload = await connector.upload_media(raw_bytes, filename)
            await connector.send_file(PAUL_USERID, upload.media_id)
    else:
        await connector.send_markdown(
            PAUL_USERID, f"{header}\n\n（未支持转发的消息类型：{message.msgtype}）"
        )

    audit.record(
        AuditEvent(
            scenario="wecom-aibot",
            action="inbound_forwarded_to_paul",
            evaluator=evaluator,
            automation_level="L1",
            decision={"sender": message.sender, "msgtype": message.msgtype},
            data_sources={"source": source},
        )
    )
