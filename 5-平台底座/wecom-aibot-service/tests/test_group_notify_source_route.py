"""队列 #387 ⑵⑶：回执路由由「发送人所属部门」改为「来源群优先」＋
配置缺口类跳过改为「跳过并告警」。

单独成文件（不并进 `test_group_notify.py`）的理由：那份文件的全部用例都在
验证「按部门查表发送」这一条既有语义，本文件验证的是**取代它的那条新路由**
与**它的反例**——两者混在一起读，很容易把「按部门」当成仍然优先的判据。

真实事故复现基准（2026-08-24，审计原文 `reports/wecom_aibot_audit.jsonl`
13:06:27／13:21:06）：陈承（IT）在**财务部群**里 @ 机器人，归档两条全部
成功（`archived ｜ department=IT ｜ matched=true`），回执两条全部
`group_notify_skipped ｜ department=IT ｜ reason=group_not_configured`。
"""
import asyncio

from zhuopin_platform.audit import AuditLogger

from aibot_service.group_notify import notify_department_group_via_chatid

# 真实值，与 `department_group_chatid_mapping.yaml` 一致——刻意用真值而非
# 占位串：本组测试要证明的正是「这两个群不能互相顶替」，用 "GroupA"/"GroupB"
# 这类占位会让读测试的人看不出事故当时到底发生了什么。
FINANCE_GROUP = "wrvDL_DAAAva1MWrKjLmuDWOu1BNxHaA"
IT_GROUP = "wrvDL_DAAARjP0BlFLup5e1Cv3vcCvMQ"


class FakeConnector:
    """最小化 `send_markdown(chatid, content)` 协程替身——本函数对 connector
    的隐式依赖就这一个方法（同 `test_group_notify.py` 的既有替身）。"""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    async def send_markdown(self, chatid, content):
        self.calls.append((chatid, content))


def _actions(audit):
    return [r["action"] for r in audit.query_by(scenario="wecom-aibot")]


# ── 主修法 ⑶：群消息回原群 ──────────────────────────────────────────────


def test_group_message_replies_to_source_group_not_sender_department(tmp_path):
    """🔴 本组最重要的一条 —— 「补完映射也修不好路由」的反例锁。

    刻意**把 IT 群配进映射表**（即 ⑵ 已经做完的状态），陈承却是在财务部群
    里 @ 的。若实现退回「按发送人部门查表」，回执会发去 IT 群，本断言当场
    失败。这正是 Shao Peishen 2026-08-24 当场确认主次时说的那句话的机器形态：
    「就算 IT 群配好了，回执还是会跑到 IT 群去。」
    """
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = FakeConnector()

    asyncio.run(
        notify_department_group_via_chatid(
            department="IT",
            matched=True,
            sender="2023458",
            msgtype="text",
            filename="IT-2023458-回复-2026-08-24-文本反馈-m1.md",
            connector=connector,
            chatid_mapping={"财务部": FINANCE_GROUP, "IT": IT_GROUP},
            audit=audit,
            source_chatid=FINANCE_GROUP,
            source_chattype="group",
        )
    )

    assert len(connector.calls) == 1
    chatid, _content = connector.calls[0]
    assert chatid == FINANCE_GROUP, "群消息的回执必须回原群"
    assert chatid != IT_GROUP, "回执不得按发送人所属部门跑到 IT 群去（#387 ⑶ 事故形态）"

    notified = [
        r for r in audit.query_by(scenario="wecom-aibot") if r["action"] == "group_notified"
    ]
    assert len(notified) == 1
    assert notified[0]["decision"]["route"] == "source_group"
    assert notified[0]["decision"]["chatid"] == FINANCE_GROUP


def test_group_message_does_not_consult_mapping_at_all(tmp_path):
    """群消息路径**不查映射表**——部门根本不在表里也照发原群。

    锁死「来源群是事实、部门是推断」这个取舍：事实可用时不退回推断链。
    """
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = FakeConnector()

    asyncio.run(
        notify_department_group_via_chatid(
            department="IT",
            matched=True,
            sender="2023458",
            msgtype="text",
            filename="x.md",
            connector=connector,
            chatid_mapping={},  # 空表
            audit=audit,
            source_chatid="wrSourceGroup",
            source_chattype="group",
        )
    )

    assert len(connector.calls) == 1
    assert connector.calls[0][0] == "wrSourceGroup"
    assert "group_notify_skipped" not in _actions(audit)


def test_group_message_from_unmatched_sender_still_replies(tmp_path):
    """⚠️ 行为扩面的显式锁：未命中部门映射的发送人在群里发言，回执照回原群。

    旧判据 `sender_unmatched` 跳过的理由原文是「没有对应的真实部门群可发，
    也不该猜」——回原群这条路径不需要猜，那条理由在此不成立。实际影响面
    ＝白名单 6 人里唯一未命中部门映射的 `ShaoPeiShen` 本人。
    """
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = FakeConnector()

    asyncio.run(
        notify_department_group_via_chatid(
            department="待分拣",
            matched=False,
            sender="ShaoPeiShen",
            msgtype="text",
            filename="x.md",
            connector=connector,
            chatid_mapping={"财务部": FINANCE_GROUP},
            audit=audit,
            source_chatid="wrOpsGroup",
            source_chattype="group",
        )
    )

    assert len(connector.calls) == 1
    assert connector.calls[0][0] == "wrOpsGroup"


# ── 回落路径：私聊仍按发送人所属部门 ────────────────────────────────────


def test_private_message_falls_back_to_department_group(tmp_path):
    """私聊（`chattype=single`）⇒ 回落「发送人所属部门群」，判据一字未改。

    同时验证 ⑵：IT 键已配，陈承私聊的回执落运维部AI保障群。
    """
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = FakeConnector()

    asyncio.run(
        notify_department_group_via_chatid(
            department="IT",
            matched=True,
            sender="2023458",
            msgtype="text",
            filename="x.md",
            connector=connector,
            chatid_mapping={"财务部": FINANCE_GROUP, "IT": IT_GROUP},
            audit=audit,
            source_chatid=None,
            source_chattype="single",
        )
    )

    assert len(connector.calls) == 1
    assert connector.calls[0][0] == IT_GROUP
    notified = [
        r for r in audit.query_by(scenario="wecom-aibot") if r["action"] == "group_notified"
    ]
    assert notified[0]["decision"]["route"] == "sender_department"


def test_group_chattype_without_chatid_falls_back(tmp_path):
    """`chattype=group` 但帧里没有 chatid（异常帧）⇒ 回落部门群，不拿空值发送。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = FakeConnector()

    asyncio.run(
        notify_department_group_via_chatid(
            department="财务部",
            matched=True,
            sender="tangyanping",
            msgtype="text",
            filename="x.md",
            connector=connector,
            chatid_mapping={"财务部": FINANCE_GROUP},
            audit=audit,
            source_chatid="",
            source_chattype="group",
        )
    )

    assert len(connector.calls) == 1
    assert connector.calls[0][0] == FINANCE_GROUP


def test_omitting_new_params_keeps_pre_change_behavior(tmp_path):
    """三个新参数一个都不传时，行为与改动前完全一致（既有调用方零影响）。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = FakeConnector()

    asyncio.run(
        notify_department_group_via_chatid(
            department="财务部",
            matched=True,
            sender="tangyanping",
            msgtype="text",
            filename="x.md",
            connector=connector,
            chatid_mapping={"财务部": FINANCE_GROUP},
            audit=audit,
        )
    )

    assert len(connector.calls) == 1
    assert connector.calls[0][0] == FINANCE_GROUP


# ── `group_not_configured` 由静默跳过改为「跳过并告警」 ──────────────────


def test_alerts_when_department_not_in_mapping(tmp_path):
    """🔴 这组缺陷能藏一个月的唯一原因就是它不响。现在它必须响。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = FakeConnector()
    alerts: list[str] = []

    asyncio.run(
        notify_department_group_via_chatid(
            department="IT",
            matched=True,
            sender="2023458",
            msgtype="text",
            filename="x.md",
            connector=connector,
            chatid_mapping={"财务部": FINANCE_GROUP},  # 没有 IT
            audit=audit,
            source_chattype="single",
            alert_send=alerts.append,
        )
    )

    assert connector.calls == []
    assert len(alerts) == 1
    assert "IT" in alerts[0]
    actions = _actions(audit)
    assert "group_notify_skipped" in actions
    assert "group_notify_skip_alerted" in actions


def test_alerts_when_chatid_value_empty(tmp_path):
    """映射表里有键、值是空占位（真实值尚未采集）——同属配置缺口，同样告警。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = FakeConnector()
    alerts: list[str] = []

    asyncio.run(
        notify_department_group_via_chatid(
            department="财务部",
            matched=True,
            sender="tangyanping",
            msgtype="text",
            filename="x.md",
            connector=connector,
            chatid_mapping={"财务部": ""},
            audit=audit,
            source_chattype="single",
            alert_send=alerts.append,
        )
    )

    assert connector.calls == []
    assert len(alerts) == 1


def test_does_not_alert_on_sender_unmatched(tmp_path):
    """⚠️ 刻意不告警的那一类：`sender_unmatched` 已有三处可见后果
    （`mapping_unmatched` 审计 ＋ 归档落待分拣 ＋ 队列行 owner 回落），
    再加一条告警只会把告警变成噪音。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = FakeConnector()
    alerts: list[str] = []

    asyncio.run(
        notify_department_group_via_chatid(
            department="待分拣",
            matched=False,
            sender="unknown-user",
            msgtype="text",
            filename="x.md",
            connector=connector,
            chatid_mapping={"财务部": FINANCE_GROUP},
            audit=audit,
            source_chattype="single",
            alert_send=alerts.append,
        )
    )

    assert alerts == []
    actions = _actions(audit)
    assert "group_notify_skipped" in actions
    assert "group_notify_skip_alerted" not in actions


def test_alert_failure_never_propagates(tmp_path):
    """告警本身失败不得向上抛——通报是旁路，它的告警更是旁路的旁路。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = FakeConnector()

    def _boom(_text):
        raise RuntimeError("webhook 挂了")

    asyncio.run(
        notify_department_group_via_chatid(
            department="IT",
            matched=True,
            sender="2023458",
            msgtype="text",
            filename="x.md",
            connector=connector,
            chatid_mapping={},
            audit=audit,
            source_chattype="single",
            alert_send=_boom,
        )
    )

    assert "group_notify_skip_alert_failed" in _actions(audit)


def test_no_alert_channel_keeps_silent_skip(tmp_path):
    """未配置 `WECOM_WEBHOOK_URL`（alert_send=None）时只记审计，行为同改动前。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = FakeConnector()

    asyncio.run(
        notify_department_group_via_chatid(
            department="IT",
            matched=True,
            sender="2023458",
            msgtype="text",
            filename="x.md",
            connector=connector,
            chatid_mapping={},
            audit=audit,
            source_chattype="single",
        )
    )

    actions = _actions(audit)
    assert "group_notify_skipped" in actions
    assert "group_notify_skip_alerted" not in actions
    assert "group_notify_skip_alert_failed" not in actions


# ── ⑵ 配置本身：IT 键必须在真实映射文件里，且键名是 `IT` 不是 `IT部` ────


def test_real_mapping_file_has_it_key_spelled_exactly_as_department_value():
    """🔴 键名必须与 `department_mapping.yaml` 的**值**逐字一致。

    `department_mapping.yaml` 写的是 `"2023458": IT`，消费方拿到的就是 `IT`
    这个字符串。写成 `IT部` 会命中「不在映射表」分支静默跳过——与本次要修
    的缺陷完全同形，且不会有任何测试失败去提示它。
    """
    from aibot_service.department_group_chatid_mapping import (
        load_department_group_chatid_mapping,
    )
    from aibot_service.department_mapping import load_department_mapping

    chatid_mapping = load_department_group_chatid_mapping()
    department_mapping = load_department_mapping()

    assert department_mapping["2023458"] == "IT"
    assert "IT" in chatid_mapping, "IT 未配进群 chatid 映射表（#387 ⑵）"
    assert chatid_mapping["IT"] == IT_GROUP
    assert "IT部" not in chatid_mapping, "键名写错会静默跳过，与本次要修的缺陷同形"
