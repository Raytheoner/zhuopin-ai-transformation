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

import re
from datetime import datetime, timezone
from pathlib import PurePath
from typing import Any, Awaitable, Callable, Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector

from .constants import PAUL_USERID
from .frame_parsing import InboundMessage

# 正文摘要长度上限（转发本身就带原文/附件，摘要只是"一眼能认出这是什么"）。
SUMMARY_MAX_CHARS = 80

_LETTER_NUMBER_RE = re.compile(r"^(?P<dept>.+)#(?P<seq>\d+)$")


def _source_label(frame: dict[str, Any]) -> str:
    body = frame.get("body", {}) or {}
    if body.get("chattype") == "group":
        return f"群聊（chatid={body.get('chatid', '未知')}）"
    return "私聊"


def is_self_sender(sender: Optional[str]) -> bool:
    """发送人是否为 Shao Peishen 本人。

    🔴 **全库唯一一处「谁是本人」的判定**。此前这条判据被三处各写一遍
    （本模块 `should_forward`、`intake` 的不建行分支、以及**漏写**的
    `queue_reconcile_sentinel`）——第三处漏写的后果就是队列 #416 ⑺：
    他每自己发一条消息，对账哨兵就报一条永远修不掉的疑似漏行。判据分叉
    的失效形态一律如此：**认得他的那几处照常工作，不认得他的那一处永远
    红着**，而红着的那一处会把整条告警训练成噪音。
    """
    return sender == PAUL_USERID


def should_forward(message: InboundMessage) -> bool:
    """排除"机器人自身消息"——发送人是 Paul 本人时跳过（转发给自己无意义）。
    心跳帧从不到达本函数（WS 协议层已处理，不会分发为 message 事件）。
    """
    return not is_self_sender(message.sender)


def render_letter_number(letter_number: Optional[str]) -> Optional[str]:
    """`财务部#15` → `财务部跟进信第 15 封`（08-24 老文案里的说法）。

    形态对不上就原样返回，**不猜**；空值返回 None。
    """
    if not letter_number:
        return None
    m = _LETTER_NUMBER_RE.match(letter_number.strip())
    if not m:
        return letter_number.strip()
    return f"{m.group('dept')}跟进信第 {m.group('seq')} 封"


def _attachment_title(message: InboundMessage, archived_filename: Optional[str]) -> str:
    """附件标题＝**专员自己给的文件名**（去扩展名）。

    刻意不用归档文件名：归档名是机器加的部门/发送人/日期/编号/防重后缀，
    读起来是流水号；08-24 那条完整描述里的《…》正是专员回传时的原文件名。
    """
    hint = message.file_name_hint or ""
    stem = PurePath(hint).stem if hint else ""
    if stem:
        return stem
    if archived_filename:
        return PurePath(archived_filename).stem
    return "未命名附件"


def _summarize(text: Optional[str]) -> str:
    flat = " ".join((text or "").split())
    if not flat:
        return "（空内容）"
    if len(flat) <= SUMMARY_MAX_CHARS:
        return flat
    return flat[:SUMMARY_MAX_CHARS] + "…"


def build_forward_description(
    message: InboundMessage,
    *,
    letter_number: Optional[str] = None,
    archived_filename: Optional[str] = None,
    is_supplement: bool = False,
) -> str:
    """转发正文里的**内容描述**（队列 #416 ⑷）。

    Shao Peishen 2026-08-26 实地对比后提出：转发只剩「发件人／来源／时间」
    三行，**分不出是文档还是文字、也没有任何摘要**，要求复原 08-24 那种
    完整描述：「你好，附件《…》是对你上次发我的『财务部跟进信第 15 封』的
    回信，详见附件」。

    🔴 **一处必须说清的事实**：08-24 那句话**不是机器人生成的**——它是唐燕萍
    本人随附件发来的文字消息，归档在
    `7-外部文档/财务部/财务部-tangyanping-回复-2026-08-24-文本反馈-2f95482c….md`，
    机器人只是把她的原文照转。08-26 她只发了文件、没带这句话，三行头部就
    露了出来。⇒ 这一条**不是回归、是新增能力**：把那句话改由机器人自己按
    已知事实生成，从此不依赖专员是否顺手写了说明。

    配不上跟进信时**明说配不上**，不编一个编号——`fail-loud`，与
    `followup_gate` 全篇同一条纪律。
    """
    letter_label = render_letter_number(letter_number)
    if not letter_label:
        reply_to = "**未能确定它回的是哪一封跟进信**（请拆件时人工确认）"
    elif is_supplement:
        # 🔴 `supplement_after_closed` ＝「该收信人最新一封信**已经闭环**」，
        # 机器人只能确定它落在哪封信之后，**不能确定它是那封信的回信**。
        # 2026-08-26 那份真实补件回件正是这一档：README §「财务部补件
        # 2026-08-25」行明写「她下一封回件若含『甲／乙／分母／签认』任一
        # 字样，归本补件行、**勿配财务部#15**」——入信桥有已知误配缺陷
        # （机制修复挂 §一 #366 M6）。**在那条缺陷修好之前，这里只报位置、
        # 不下断言**：把一个已知可能错的归属写成肯定句，等于用机器的语气
        # 替人做了一个人已经说过"要人工判"的判断。
        reply_to = (
            f"落在「{letter_label}」之后（该信已闭环，**属闭环后的补充说明**；"
            "归属请拆件时人工确认，见 #366 M6）"
        )
    else:
        reply_to = f"是对你上次发我的「{letter_label}」的回信"
    if message.msgtype == "file":
        title = _attachment_title(message, archived_filename)
        ext = (PurePath(message.file_name_hint or archived_filename or "").suffix or "").lstrip(".")
        kind = f"📎 文档附件（.{ext}）" if ext else "📎 文档附件"
        body = f"你好，附件《{title}》{reply_to}，详见附件。"
    elif message.msgtype == "text":
        kind = "💬 文字回复"
        body = f"你好，以下是{('' if letter_label else '一条')}文字回复，{reply_to}。\n摘要：{_summarize(message.text_content)}"
    else:
        kind = f"❓ 未支持转发的消息类型（{message.msgtype}）"
        body = f"你好，收到一条 `{message.msgtype}` 消息，{reply_to}。"

    lines = [f"类型：{kind}", "", body]
    if archived_filename:
        lines.append(f"归档：`{archived_filename}`")
    return "\n".join(lines)


async def forward_inbound_to_paul(
    *,
    frame: dict[str, Any],
    message: InboundMessage,
    connector: AibotConnector,
    audit: AuditLogger,
    evaluator: str = "system",
    letter_number: Optional[str] = None,
    archived_filename: Optional[str] = None,
    is_supplement: bool = False,
    media_download: Optional[Callable[[str, Optional[str], str], Awaitable[tuple]]] = None,
    media_upload: Optional[Callable[[bytes, str, str], Awaitable[Any]]] = None,
) -> None:
    """`letter_number` / `archived_filename`（队列 #416 ⑷⑸）：由 `connection.py`
    从归档与跟进信 README 桥的结论传入，缺省 None 时描述照样生成、只是明说
    「未能确定回的是哪一封」。

    `media_download` / `media_upload`（队列 #416 ⑴）：带重试与可配超时的
    media 通道；未注入时退回裸调用（向后兼容既有测试与调用方）。
    """
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
    description = build_forward_description(
        message, letter_number=letter_number, archived_filename=archived_filename,
        is_supplement=is_supplement,
    )

    if message.msgtype == "text":
        # 描述在前、原文在后——原文一字不改地跟在后面，摘要只是入口。
        await connector.send_markdown(
            PAUL_USERID,
            f"{header}\n{description}\n\n———— 原文 ————\n{message.text_content or ''}",
        )
    elif message.msgtype == "file":
        await connector.send_markdown(PAUL_USERID, f"{header}\n{description}")
        if message.file_url:
            if media_download is not None:
                raw_bytes, downloaded_name = await media_download(
                    message.file_url, message.file_aes_key, "download_forward"
                )
            else:
                raw_bytes, downloaded_name = await connector.download_file(
                    message.file_url, message.file_aes_key
                )
            filename = message.file_name_hint or downloaded_name or "attachment"
            if media_upload is not None:
                upload = await media_upload(raw_bytes, filename, "upload_forward")
            else:
                upload = await connector.upload_media(raw_bytes, filename)
            await connector.send_file(PAUL_USERID, upload.media_id)
    else:
        await connector.send_markdown(PAUL_USERID, f"{header}\n{description}")

    audit.record(
        AuditEvent(
            scenario="wecom-aibot",
            action="inbound_forwarded_to_paul",
            evaluator=evaluator,
            automation_level="L1",
            decision={
                "sender": message.sender,
                "msgtype": message.msgtype,
                # 队列 #416 ⑷：转发里到底带没带上「回的是哪一封」，事后可查。
                "letter_number": letter_number or "",
                "letter_is_supplement": is_supplement,
            },
            data_sources={"source": source, "archived_filename": archived_filename or ""},
        )
    )
