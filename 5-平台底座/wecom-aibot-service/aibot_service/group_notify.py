"""归档成功后回部门群发一条通报留痕（Paul 2026-07-12 拍板，2026-07-15 定型：
三部门群各自独立小群，最初走既有企微**群机器人 webhook** 机制——不是智能
机器人的 chatid 通道，二者是两套不同的企微能力。

**2026-08-06（队列 #279/#280）**：webhook 单向、群成员回复进不到任何地方
这一缺陷促成迁移——四个部门（含新增"跨部门"）真实 chatid 采集验证完毕后，
`connection.py` 的调用点已切到 `notify_department_group_via_chatid`（本文件
新增函数，同一份判据与审计口径，只是发送介质换成 aibot chatid）。
`notify_department_group`（webhook 版）**保留在本文件但不再被调用**——
未整段删除，是给一段观察期做回滚余地；确认 chatid 路径稳定后再考虑清理。

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


async def notify_department_group_via_chatid(
    *,
    department: str,
    matched: bool,
    sender: str,
    msgtype: str,
    filename: str,
    connector,
    chatid_mapping: dict[str, str],
    audit: AuditLogger,
    evaluator: str = "system",
) -> None:
    """队列 #279/#280：`notify_department_group` 的机器人 chatid 版本——
    取代群机器人 webhook（单向，群成员回复进不到任何地方），改用同一条
    `AibotConnector` chatid 通道（与跟进信群 cc、`delivery.push_followup`
    的 `cc_group_chatid` 同一套映射表 `department_group_chatid_mapping.py`，
    四个部门真实 chatid 已于 2026-08-06 采集验证完毕，见队列 #279/#280）。

    判据与 `notify_department_group` 完全对齐（同一函数改写，非另起一套
    口径）：未命中发送人 / 部门不在映射表 / chatid 值为空（占位/未采集）
    均 fail-closed 跳过并记 `group_notify_skipped` 审计——沿用旧函数同一
    审计 action 名与 reason 取值，下游（若有仪表盘/统计）无需区分两条
    路径。成功发送记 `group_notified`，同样复用旧 action 名。

    `connector` 类型故意不标注（避免在测试里强依赖 `AibotConnector` 的
    真实构造），只要求其具备 `send_markdown(chatid, content)` 协程接口，
    与 `delivery.py::push_followup` 对 `connector` 参数的隐式契约一致。
    """
    if not matched:
        _skip(audit, evaluator, department, sender, "sender_unmatched")
        return

    if department not in chatid_mapping:
        _skip(audit, evaluator, department, sender, "group_not_configured")
        return

    chatid = chatid_mapping.get(department)
    if not chatid:
        _skip(audit, evaluator, department, sender, "group_webhook_not_configured")
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
            decision={"department": department, "channel": "aibot_chatid"},
            data_sources={"sender": sender, "filename": filename},
        )
    )
