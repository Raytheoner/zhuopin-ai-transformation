"""归档成功后回部门群发一条通报留痕（Paul 2026-07-12 拍板，2026-07-14 落地）。

与 `forwarding.py`（全量转发给 Paul）是两条独立通知路径，互不替代：转发给
Paul 是"给 Paul 一份副本"，本模块是"让部门群知道机器人已经收到并归档"。
只在**命中部门映射**（`matched=True`）时发——`待分拣`（未命中发送人）没有
对应的真实部门群可发，也不该猜。群 chatid 未配置（仍是 yaml 里的占位符）
时同样跳过，不拿占位符字符串当 chatid 发送——发了也只会是 API 报错，不如
在应用层就 fail-closed 并留痕，等 Paul 把真实 chatid 填进
`department_group_mapping.yaml` 后自然生效，不用再改代码。

本模块与 `intake.py` 的归档流程、`forwarding.py` 的转发流程相互独立、互不
影响——通报失败不影响归档/转发是否成功（`connection.py` 里各自 try/except）。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector

from .department_group_mapping import resolve_group_chatid


async def notify_department_group(
    *,
    department: str,
    matched: bool,
    sender: str,
    msgtype: str,
    filename: str,
    connector: AibotConnector,
    group_mapping: dict[str, str],
    audit: AuditLogger,
    evaluator: str = "system",
) -> None:
    if not matched:
        audit.record(
            AuditEvent(
                scenario="wecom-aibot",
                action="group_notify_skipped",
                evaluator=evaluator,
                automation_level="L1",
                decision={"department": department, "reason": "sender_unmatched"},
                data_sources={"sender": sender},
            )
        )
        return

    chatid = resolve_group_chatid(department, group_mapping)
    if chatid is None:
        audit.record(
            AuditEvent(
                scenario="wecom-aibot",
                action="group_notify_skipped",
                evaluator=evaluator,
                automation_level="L1",
                decision={"department": department, "reason": "group_chatid_not_configured"},
                data_sources={"sender": sender},
            )
        )
        return

    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    kind = "文件" if msgtype == "file" else "文本反馈"
    content = (
        f"✅ 已归档：{sender} 的{kind}\n"
        f"文件：{filename}\n"
        f"时间：{now}"
    )
    await connector.send_markdown(chatid, content)

    audit.record(
        AuditEvent(
            scenario="wecom-aibot",
            action="group_notified",
            evaluator=evaluator,
            automation_level="L1",
            decision={"department": department, "chatid": chatid},
            data_sources={"sender": sender, "filename": filename},
        )
    )
