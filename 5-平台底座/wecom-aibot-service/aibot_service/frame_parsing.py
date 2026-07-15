"""从企微 WsFrame 提取发送人/消息类型/内容。

**2026-07-13 真实测试群 echo 联调已确认字段路径**（原 design.md Risks 登记的
未验证项，现已实测核实，字段路径与本文件原实现假设一致，未改代码）：
- `sender` = `body.from.userid`——是企微 **userid**（如 `"ShaoPeiShen"`，拼音
  风格），**不是中文显示名**。`department_mapping.yaml` 的键必须是 userid，
  不能沿用协同一页纸上的中文姓名占位值——这是本次联调发现的新待办，见该
  文件顶部注记。
- `chatid` 在 `body.chatid`（群聊场景，顶层字段，不嵌在 `from` 里）。
- 群聊消息另含 `chattype`（`"group"`/`"single"`）、`response_url`（本服务
  未使用，走 `aibot_send_msg` 主动发送而非该 URL 回复）。
- `msgid`（`body.msgid`）——企微给每条消息的唯一 ID。**2026-07-13 真实生产链路
  联调发现**：intake.py 归档文件名原按"日期"粒度（不含 msgid/时分秒），同一
  发送人同一天发多条文本消息会互相覆盖文件（真实测试中 3 条消息只留下最后
  一条的内容）——已修复为文件名带 `msgid` 后缀消除碰撞，见 `intake.py`。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class InboundMessage:
    sender: str
    msgtype: str
    text_content: Optional[str] = None
    file_url: Optional[str] = None
    file_aes_key: Optional[str] = None
    file_name_hint: Optional[str] = None
    msgid: Optional[str] = None


def parse_inbound_frame(frame: dict[str, Any]) -> InboundMessage:
    body = frame.get("body", {}) or {}
    msgtype = str(body.get("msgtype", ""))
    msgid = body.get("msgid")

    from_field = body.get("from")
    if isinstance(from_field, dict):
        sender = from_field.get("userid") or from_field.get("name") or ""
    else:
        sender = from_field or body.get("sender") or ""

    text_content = None
    file_url = file_aes_key = file_name_hint = None

    if msgtype == "text":
        text_content = (body.get("text") or {}).get("content", "")
    elif msgtype == "file":
        file_body = body.get("file") or {}
        file_url = file_body.get("url")
        file_aes_key = file_body.get("aeskey")
        file_name_hint = file_body.get("filename") or file_body.get("md5")

    return InboundMessage(
        sender=str(sender),
        msgtype=msgtype,
        text_content=text_content,
        file_url=file_url,
        file_aes_key=file_aes_key,
        file_name_hint=file_name_hint,
        msgid=str(msgid) if msgid else None,
    )
