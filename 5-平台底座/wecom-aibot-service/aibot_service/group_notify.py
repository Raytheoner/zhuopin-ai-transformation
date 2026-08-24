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

🔴 **2026-08-24（队列 #387 ⑵⑶）：回执路由口径由「发送人所属部门」改为
「来源群优先」。** 真实事故：陈承（IT）在**财务部群**里 @ 机器人，归档全部
成功，但回执按 `archive_result.department`＝`IT` 去查映射表——表里没有 IT
键，`group_not_configured` **静默跳过**，群里等回执的人什么也没等到；同一
天唐燕萍在财务部群里的两条则正常收到。**关键在于：即便当时 IT 群已配好，
陈承那条回执也会跑到 IT 群去，而他是在财务部群里问的。** 补映射只修了症状
之一，修不了路由本身。故本次两件都做：

- **主修法（⑶）**：入站帧本就带 `chatid`/`chattype`（队列 #279 起已进
  `InboundMessage`，只是从未被本模块消费）——**群消息一律回原群**，私聊
  才回落到「发送人所属部门群」。来源群是现成的事实，不需要经由「发送人属
  哪个部门」这一层推断，那一层恰恰是本次错误的来源。
- **辅修法（⑵）**：`department_group_chatid_mapping.yaml` 补 `IT` 键
  （运维部AI保障群，chatid 2026-08-24 实采）。

🔴 **同批把 `group_not_configured` 由静默跳过改为「跳过并告警」**——这是
这组缺陷能藏住的唯一原因：IT 域自 2026-07-22 起就能归档，从那天起它的回执
就一直在静默跳过，**审计里每次都有记录，却没有任何人被惊动**，直到有人在群
里等回执等不到。fail-closed 依旧（不拿空值发送），但不再 fail-silent。

⚠️ **哪些跳过发告警、哪些不发，是有意区分的**：只有「配置缺口」类
（`group_not_configured`／`group_webhook_not_configured`）发告警——那是
**本该配却没配**、且不告警就永远不会有人发现的一类。`sender_unmatched`
不发——它已有 `mapping_unmatched` 审计 ＋ 归档落 `待分拣` ＋ 队列行 owner
回落三处可见后果，再加一条告警只会把告警变成噪音。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Callable, Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger
from zhuopin_platform.shared_tools.notifiers import wecom
from zhuopin_platform.shared_tools.secrets import SecretsProvider

# 队列 #387：这两个 reason 属「配置缺口」——本该配、没配上，且除了审计里
# 一行谁也不会看的记录之外没有任何外部信号。它们发告警。
ALERTABLE_SKIP_REASONS = frozenset({"group_not_configured", "group_webhook_not_configured"})

# 回执路由取值，随 `group_notified`/`group_notify_skipped` 审计事件一并留痕
# ——同一条审计事件此后可以回答「这条回执是按来源群发的还是按部门发的」，
# 而这正是 #387 追因时最想知道、却查不出来的那一项。
ROUTE_SOURCE_GROUP = "source_group"
ROUTE_SENDER_DEPARTMENT = "sender_department"


def _skip(
    audit: AuditLogger,
    evaluator: str,
    department: str,
    sender: str,
    reason: str,
    *,
    route: str = ROUTE_SENDER_DEPARTMENT,
) -> None:
    audit.record(
        AuditEvent(
            scenario="wecom-aibot",
            action="group_notify_skipped",
            evaluator=evaluator,
            automation_level="L1",
            decision={"department": department, "reason": reason, "route": route},
            data_sources={"sender": sender},
        )
    )


async def _alert_skip(
    alert_send: Optional[Callable[[str], None]],
    audit: AuditLogger,
    evaluator: str,
    department: str,
    sender: str,
    reason: str,
) -> None:
    """配置缺口类跳过时发一条告警（独立 webhook 通道，与本服务自身的长连接
    是两套凭据——同 `gap_alert.py`/`queue_edit_lock` 告警的既有范式）。

    `alert_send` 未提供（未配置 `WECOM_WEBHOOK_URL`）时整体关闭，只留审计，
    行为与本次改动前完全一致。**告警本身失败绝不向上抛**——通报是旁路，
    它的告警更是旁路的旁路，不该影响归档/转发/队列追加任何一条主链路。
    """
    if reason not in ALERTABLE_SKIP_REASONS or alert_send is None:
        return
    text = (
        f"归档回执未能发出：部门「{department}」在 department_group_chatid_mapping.yaml "
        f"里没有可用的群 chatid（reason={reason}）。发送人：{sender}。"
        f"归档本身已成功，丢的只有这条回执——请补映射或确认该部门是否有意不配群。"
    )
    try:
        await asyncio.to_thread(alert_send, text)
    except Exception:  # noqa: BLE001 —— 告警失败不得影响任何主链路
        audit.record(
            AuditEvent(
                scenario="wecom-aibot",
                action="group_notify_skip_alert_failed",
                evaluator=evaluator,
                automation_level="L1",
                decision={"department": department, "reason": reason},
                data_sources={"sender": sender},
            )
        )
    else:
        audit.record(
            AuditEvent(
                scenario="wecom-aibot",
                action="group_notify_skip_alerted",
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
    source_chatid: Optional[str] = None,
    source_chattype: Optional[str] = None,
    alert_send: Optional[Callable[[str], None]] = None,
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

    ━━━ 🔴 **队列 #387 ⑶：路由口径改为「来源群优先」** ━━━

    `source_chattype`/`source_chatid` 来自入站帧（`InboundMessage.chattype`/
    `.chatid`，队列 #279 已提取）。两条路由：

    ⑴ **群消息 ⇒ 回原群**（`source_chattype == "group"` 且 `source_chatid`
       非空）。**不查映射表、不看 `matched`** —— 来源群是入站帧给出的**事实**，
       而 `matched`/映射表回答的是「这个人属哪个部门、那个部门的群在哪」，
       是一条**推断链**。事实可用时不该退回去走推断链，#387 正是那条推断链
       给出了一个语法上完全合法、语义上完全错误的目的地。

    ⑵ **私聊（或帧里没有 chatid）⇒ 回落发送人所属部门群**，判据与映射表
       用法一字未改（`matched` ⇒ 在表里 ⇒ 值非空），这是本函数改动前的
       全部行为，作为回落原样保留。

    ⚠️ **⑴ 刻意不受 `matched` 门槛约束，这是一处行为扩面，如实写明**：改动
    前，未命中部门映射的发送人（走 `待分拣`）在群里发言不会有任何回执。改动
    后他会在**他自己发言的那个群**里收到一条「已归档」。这不是漏想——旧判据
    里 `sender_unmatched` 跳过的理由原文是「没有对应的真实部门群可发，也不该
    猜」，而**回原群这条路径压根不需要猜**，那条理由在这条路径上不成立。实际
    影响面极小：白名单只有 6 人，其中 5 人均已命中部门映射，唯一未命中的是
    `ShaoPeiShen` 本人（他在群里发的测试消息此后会收到一条回执——**这恰好是
    队列 #387 ⑵ 要求的那次「chatid 反查」所需的凭据**）。
    """
    if source_chattype == "group" and source_chatid:
        target_chatid = source_chatid
        route = ROUTE_SOURCE_GROUP
    else:
        route = ROUTE_SENDER_DEPARTMENT
        if not matched:
            _skip(audit, evaluator, department, sender, "sender_unmatched", route=route)
            return

        if department not in chatid_mapping:
            _skip(audit, evaluator, department, sender, "group_not_configured", route=route)
            await _alert_skip(
                alert_send, audit, evaluator, department, sender, "group_not_configured"
            )
            return

        target_chatid = chatid_mapping.get(department) or ""
        if not target_chatid:
            _skip(
                audit, evaluator, department, sender,
                "group_webhook_not_configured", route=route,
            )
            await _alert_skip(
                alert_send, audit, evaluator, department, sender,
                "group_webhook_not_configured",
            )
            return

    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    kind = "文件" if msgtype == "file" else "文本反馈"
    content = (
        f"✅ 已归档：{sender} 的{kind}\n"
        f"文件：{filename}\n"
        f"时间：{now}"
    )
    await connector.send_markdown(target_chatid, content)

    audit.record(
        AuditEvent(
            scenario="wecom-aibot",
            action="group_notified",
            evaluator=evaluator,
            automation_level="L1",
            decision={
                "department": department,
                "channel": "aibot_chatid",
                # 队列 #387：留痕「按什么路由发的」与「实际发到了哪个 chatid」
                # ——#387 追因时最想知道的就是这两项，而当时的审计事件一项
                # 也答不出来。
                "route": route,
                "chatid": target_chatid,
            },
            data_sources={"sender": sender, "filename": filename},
        )
    )
