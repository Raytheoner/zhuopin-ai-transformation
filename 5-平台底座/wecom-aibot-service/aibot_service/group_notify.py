"""归档成功后回部门群发一条通报留痕（Paul 2026-07-12 拍板，2026-07-15 定型：
三部门群各自独立小群，走既有企微**群机器人 webhook** 机制——不是智能机器人
的 chatid 通道，二者是两套不同的企微能力，本模块只用前者。

与 `forwarding.py`（全量转发给 Paul）是两条独立通知路径，互不替代：转发给
Paul 是"给 Paul 一份副本"，本模块是"让部门群知道机器人已经收到并归档"。
只在**命中部门映射**（`matched=True`）时发——`待分拣`（未命中发送人）没有
对应的真实部门群可发，也不该猜。部门未在 `department_group_mapping.yaml`
里配置（如销售部，Paul 2026-07-15 拍板暂不启用）或对应 webhook 环境变量在
`.env` 里缺失/为空时同样跳过——fail-closed，不拿空值当 webhook 发送。

本模块与 `intake.py` 的归档流程、`forwarding.py` 的转发流程相互独立、互不
影响——通报失败不影响归档/转发是否成功（`connection.py` 里各自 try/except）。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from zhuopin_platform.audit import AuditEvent, AuditLogger
from zhuopin_platform.shared_tools.notifiers import wecom
from zhuopin_platform.shared_tools.secrets import SecretsProvider


def _skip(
    audit: AuditLogger, evaluator: str, department: str, sender: str, reason: str
) -> None:
    audit.record(
        AuditEvent(
            scenario="wecom-aibot",
            action="group_notify_skipped",
            evaluator=evaluator,
            automation_level="L1",
            decision={"department": department, "reason": reason},
            data_sources={"sender": sender},
        )
    )


async def notify_department_group(
    *,
    department: str,
    matched: bool,
    sender: str,
    msgtype: str,
    filename: str,
    secrets: SecretsProvider,
    group_mapping: dict[str, str],
    audit: AuditLogger,
    evaluator: str = "system",
) -> None:
    if not matched:
        _skip(audit, evaluator, department, sender, "sender_unmatched")
        return

    env_var_name = group_mapping.get(department)
    if not env_var_name:
        _skip(audit, evaluator, department, sender, "group_not_configured")
        return

    try:
        webhook_url = secrets.get(env_var_name)
    except KeyError:
        webhook_url = ""
    if not webhook_url:
        _skip(audit, evaluator, department, sender, "group_webhook_not_configured")
        return

    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    kind = "文件" if msgtype == "file" else "文本反馈"
    content = (
        f"✅ 已归档：{sender} 的{kind}\n"
        f"文件：{filename}\n"
        f"时间：{now}"
    )
    # wecom.send_markdown 是同步阻塞的 urllib 调用，on_message 是 async——
    # 丢线程池执行，避免卡住事件循环。
    await asyncio.to_thread(wecom.send_markdown, webhook_url, content)

    audit.record(
        AuditEvent(
            scenario="wecom-aibot",
            action="group_notified",
            evaluator=evaluator,
            automation_level="L1",
            decision={"department": department},
            data_sources={"sender": sender, "filename": filename},
        )
    )
