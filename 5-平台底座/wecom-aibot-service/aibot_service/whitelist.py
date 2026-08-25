"""进件白名单：只处理表内指定发送人的消息/文件（Paul 2026-07-16 口头需求，
队列 #35，当时 5 人；现 8 项，见下方 2026-08-25 段）。

机器人此前对任何发件人一律归档+转发 Paul+群通报，导致同事发来的无关项目
消息被误当业务内容处理、污染队列与 Paul 私信。白名单外发送人改为只收到
一条礼貌回复（说明机器人尚未正式开通），不落档/不转发/不占用队列行/不发
群通报。

与 `department_mapping.py`（发送人→部门，用于归档目的地）是两件不同的事——
白名单只回答"这条消息要不要被处理"，不回答"处理后归哪个部门"。陈承
（IT，userid=2023458）2026-07-16 起在白名单里，但当时不在 `department_mapping.yaml`
（现有四部门口径不含 IT），命中白名单后落入"待分拣"；**2026-07-22（队列 #70）
起 `department_mapping.yaml` 已补入陈承→IT 映射**，此后直接归档进
`7-外部文档/IT/`（归档+转发+群通报三条路径本身不变，变的只是归档目的地）。

陈承同时开通场景①（跟进信直达）推送对象（Paul 2026-07-16 确认）：
`delivery.py::push_followup` 按调用方传入的 `chatid` 直接发送，本就不经
本表过滤，故无需为此额外改动代码——调用 `scripts/push_followup_letter.py`
时把 `--chatid` 传成 `2023458` 即可对陈承推送。

Paul 本人（`PAUL_USERID`）此前不在白名单里，导致他自己发的 test 消息也会
被当"未开通"礼貌拒复、不落档不进队列——这在验证服务是否真正连通归档链
时会造成误判（收到礼貌回复≠归档链没问题，只是发件人不在白名单）。2026-07-18
总线审计发现后补入，Paul 现可像五位专员一样触发完整归档+转发+群通报三条
路径（转发/抄送逻辑本就对 Paul 自身发送有特殊处理，见 `forwarding.py`）。

🔴 **2026-08-25（队列 #380 ／ §四 #116，变更包 `aibot-inbound-whitelist-li-jiaolong`）
——本表自 2026-07-16 上线起首次有了「判据」，并首次补上「谁被挡在门外」的可见性。**
Shao Peishen 2026-08-25 三点全批，落地如下：

- **⑴ 准入判据取 (乙)「出站即入站」**：凡在 `dispatch.py::KNOWN_RECIPIENT_USERIDS`
  内者 SHALL 同时入站可达。此前本表是**一张没有判据的名单**——每个 userid
  逐次口头确认加入，顶部注释记的是「每一次加人的缘由」，不是一条可复用的
  规则；出站名单与入站名单各自演进，**没有任何机制保证二者一致**。李姣龙
  这次是做部门映射核对时顺手撞出来的，不是机制发现的。 🔑 **判据的执行体
  不在本文件、而在单测**：`tests/test_whitelist.py::test_出站已知收件人必须同时入站可达`
  做两表求差，差集非空即红。**本表仍是显式枚举、不从 `dispatch.py` 推导**——
  显式名单可被 IATF 审计逐条追溯到授权来源，推导出来的名单不能。
- **⑵ 李姣龙（财务部，`2025672`）与解植雅（采购部，`2025621`）同批补入**，
  两人的 `department_mapping.yaml` 部门映射同批补齐（见下方「两张表串联」段）。
  🔴 **解植雅不是预防性放行，是补一件已经发生的事**：`reports/wecom_aibot_audit.jsonl:204`
  ——他 2026-07-20T02:55:21Z 发来一条 text 被本门禁挡回，只留一条审计，
  **36 天无人知情**，系写 propose 时翻审计翻出。
- **⑶ `whitelist_rejected` 补独立通道告警**（见本文件 `alert_whitelist_rejected`）。

🔴 **`2025672`／`2025621` 都是纯数字工号，不可推断**（同 `陈承: 2023458`）——
任何「按拼音猜 userid」的做法在他们身上一定错，且错的形态是 fail-closed
静默跳过、命令行一切正常。取值唯一可信源：《企微 chatid 名录》／《全员企微
账号》名录 ＋ 唐燕萍 2026-08-22 财务部#14 回件二次确认（李姣龙那一项两者
独立互证一致）。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Callable, Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger

from .constants import PAUL_USERID

# 白名单发送人 userid（五位专员，Paul 2026-07-16 口头确认；Paul 本人，
# 2026-07-18 总线审计补入；李姣龙／解植雅 2026-08-25 补入，见上 §四 #116）：
# - 2023458        陈承（IT）
# - ChenChen       陈忱（质量部）
# - tangyanping    唐燕萍（财务部）
# - YaoZuYi        姚祖怡（采购部）
# - Hongqin.Wang   王泓钦（销售部）
# - PAUL_USERID    Paul 本人（== "ShaoPeiShen"，见 constants.py）
# - 2025672        李姣龙（财务部）—— 出站 2026-08-24 已通（`dispatch.py`），
#                  入站至今不通；她是 §一 #379 年度提醒的收件人，本次补齐
#                  的正是「她收到提醒后回话能不能被听见」
# - 2025621        解植雅（采购部）—— 2026-07-20 已被本门禁静默挡回一次
WHITELISTED_SENDER_USERIDS = frozenset(
    {
        "2023458",
        "ChenChen",
        "tangyanping",
        "YaoZuYi",
        "Hongqin.Wang",
        PAUL_USERID,
        "2025672",
        "2025621",
    }
)

NOT_ONBOARDED_REPLY = (
    "您好，本机器人目前仅面向指定专员开通，暂不支持与您会话，敬请谅解。"
)

# 🔴 `whitelist_rejected` 告警**只报「谁在何时被挡」，绝不含被拒消息正文**
# ——发送人不在白名单内，正意味着我方尚未获准处理其内容。这条约束不是靠
# 「记得别传正文」守的，而是靠 `alert_whitelist_rejected` 的签名根本收不下
# 正文（只有 `sender`/`msgtype`）守的：拿不到的东西泄不出去。
WHITELIST_REJECTED_ALERT_PREFIX = "入站被挡"


def is_whitelisted(sender: str) -> bool:
    """白名单外一律 fail-closed（不猜测、不放行），与 `department_mapping`
    的 fail-closed 风格一致。"""
    return sender in WHITELISTED_SENDER_USERIDS


def format_whitelist_rejected_alert(sender: str, msgtype: str, occurred_at: datetime) -> str:
    """告警文案。**入参里没有正文字段，这是刻意的**（见
    `WHITELIST_REJECTED_ALERT_PREFIX` 上方注释）。

    `occurred_at` 按项目硬规则显式标 UTC——审计 jsonl 与企微告警文案里的
    时刻都是真 UTC，而文件 mtime／计划任务 `LastRunTime` 是本地，两者混读
    过一次就会差 8 小时（根 `CLAUDE.md`「时间戳必判 UTC vs Win 本地」）。
    """
    stamp = occurred_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return (
        f"{WHITELIST_REJECTED_ALERT_PREFIX}：`{sender}`（msgtype={msgtype}）于 {stamp} "
        f"发来一条消息，因不在入站白名单被 fail-closed 挡回，未归档、未转发、未建队列行。"
        f"若此人应当可达，请补 `whitelist.py` 与 `department_mapping.yaml` 两张表"
        f"（须同批加）；若确不应放行，本条无需处理。"
        f"⚠️ 本告警不含其消息正文——他不在白名单内，正意味着我方尚未获准处理其内容。"
    )


async def alert_whitelist_rejected(
    alert_send: Optional[Callable[[str], None]],
    audit: AuditLogger,
    evaluator: str,
    sender: str,
    msgtype: str,
    *,
    now: Optional[datetime] = None,
) -> None:
    """`whitelist_rejected` 发生时另发一条告警（独立 webhook 通道，与本服务
    自身的智能机器人长连接是两套凭据——同 `gap_alert.py`／`group_notify.py`
    的既有范式，不新造第三条通道）。

    **为什么非要独立通道**：被挡的这条消息本身就是经由机器人长连接进来的，
    用同一条连接回告警在连接正常时固然能发出，但这类缺口恰恰常与连接侧
    异常同时出现；且 `#387` 已把这条独立通道建好并验通，复用即可。

    `alert_send` 未提供（未配置 `WECOM_WEBHOOK_URL`）时整体关闭，只留审计，
    行为与本次改动前完全一致。**告警本身失败绝不向上抛，也绝不改变
    `whitelist_rejected` 审计已经写入这一事实**——审计是事实记录，告警是
    可见性旁路，旁路坏了不能把事实一起吞掉（spec `wecom-feedback-intake`
    「告警通道不可用不得吞掉拒绝事实」）。
    """
    if alert_send is None:
        return
    text = format_whitelist_rejected_alert(sender, msgtype, now or datetime.now(tz=timezone.utc))
    try:
        await asyncio.to_thread(alert_send, text)
    except Exception:  # noqa: BLE001 —— 告警失败不得影响任何主链路
        audit.record(
            AuditEvent(
                scenario="wecom-aibot",
                action="whitelist_rejected_alert_failed",
                evaluator=evaluator,
                automation_level="L1",
                decision={"sender": sender, "msgtype": msgtype},
                data_sources={},
            )
        )
    else:
        audit.record(
            AuditEvent(
                scenario="wecom-aibot",
                action="whitelist_rejected_alerted",
                evaluator=evaluator,
                automation_level="L1",
                decision={"sender": sender, "msgtype": msgtype},
                data_sources={},
            )
        )
