import asyncio

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector

from aibot_service.group_notify import notify_department_group

from fakes import fake_client_factory


def _setup(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}
    connector = AibotConnector("bot", "secret", client_factory=fake_client_factory(store))
    return audit, connector, store


def test_notify_sends_to_configured_group_chatid(tmp_path):
    audit, connector, store = _setup(tmp_path)

    asyncio.run(
        notify_department_group(
            department="财务部",
            matched=True,
            sender="tangyanping",
            msgtype="text",
            filename="财务部-tangyanping-回复-2026-07-14-文本反馈-abc123.md",
            connector=connector,
            group_mapping={"财务部": "REAL_FINANCE_CHATID"},
            audit=audit,
        )
    )

    chatid, body = store["client"].sent_messages[0]
    assert chatid == "REAL_FINANCE_CHATID"
    assert "已归档" in body["markdown"]["content"]
    assert "tangyanping" in body["markdown"]["content"]
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "group_notified" in actions


def test_notify_skipped_when_sender_unmatched(tmp_path):
    audit, connector, store = _setup(tmp_path)

    asyncio.run(
        notify_department_group(
            department="待分拣",
            matched=False,
            sender="unknown-user",
            msgtype="text",
            filename="待分拣-unknown-user-回复-2026-07-14-文本反馈-abc123.md",
            connector=connector,
            group_mapping={"财务部": "REAL_FINANCE_CHATID"},
            audit=audit,
        )
    )

    assert store["client"].sent_messages == []
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "group_notify_skipped" in actions
    assert "group_notified" not in actions


def test_notify_skipped_when_group_chatid_not_configured(tmp_path):
    audit, connector, store = _setup(tmp_path)

    asyncio.run(
        notify_department_group(
            department="财务部",
            matched=True,
            sender="tangyanping",
            msgtype="text",
            filename="x.md",
            connector=connector,
            group_mapping={"财务部": "PLACEHOLDER_FINANCE_GROUP_CHATID"},
            audit=audit,
        )
    )

    assert store["client"].sent_messages == []
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "group_notify_skipped" in actions


def test_notify_skipped_when_department_absent_from_mapping(tmp_path):
    audit, connector, store = _setup(tmp_path)

    asyncio.run(
        notify_department_group(
            department="财务部",
            matched=True,
            sender="tangyanping",
            msgtype="text",
            filename="x.md",
            connector=connector,
            group_mapping={},
            audit=audit,
        )
    )

    assert store["client"].sent_messages == []
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "group_notify_skipped" in actions


def test_notify_file_message_uses_file_wording(tmp_path):
    audit, connector, store = _setup(tmp_path)

    asyncio.run(
        notify_department_group(
            department="质量部",
            matched=True,
            sender="ChenChen",
            msgtype="file",
            filename="质量部-ChenChen-回复-2026-07-14-8D报告-abc123.docx",
            connector=connector,
            group_mapping={"质量部": "REAL_QUALITY_CHATID"},
            audit=audit,
        )
    )

    _, body = store["client"].sent_messages[0]
    assert "文件" in body["markdown"]["content"]
    assert "8D报告" in body["markdown"]["content"]
