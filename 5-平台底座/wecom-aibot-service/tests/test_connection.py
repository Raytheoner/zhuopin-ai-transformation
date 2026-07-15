import asyncio

import pytest

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.secrets import EnvSecretsProvider

from aibot_service.connection import build_connector, BOTID_KEY, SECRET_KEY
from aibot_service.constants import PAUL_USERID

from fakes import fake_client_factory

QUEUE_TEXT = """\
## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 1 | 既有任务 | CC | p | e | 待领 | — | 07-09 |
"""


def _secrets(bot_id="BOT1", secret="SECRET1", **extra):
    return EnvSecretsProvider(override={BOTID_KEY: bot_id, SECRET_KEY: secret, **extra})


def test_missing_credentials_raise_keyerror(tmp_path):
    secrets = EnvSecretsProvider(override={})
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")

    with pytest.raises(KeyError):
        build_connector(
            secrets=secrets,
            audit=audit,
            external_docs_root=tmp_path / "7-外部文档",
            queue_path=tmp_path / "queue.md",
            client_factory=fake_client_factory({}),
        )


def test_build_connector_wires_credentials_into_client(tmp_path):
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    connector = build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
    )

    assert connector is not None
    assert store["client"].bot_id == "BOT1"
    assert store["client"].secret == "SECRET1"
    # design.md D2/D3 应用层保守重连预算
    assert store["client"].options["max_reconnect_attempts"] == 6
    assert store["client"].options["reconnect_interval"] == 2000


def test_connection_lifecycle_events_are_audited(tmp_path):
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
    )
    client = store["client"]

    client.handlers["connected"][0]()
    client.handlers["authenticated"][0]()
    client.handlers["disconnected"][0]("network glitch")
    client.handlers["reconnecting"][0](1)
    client.handlers["error"][0](RuntimeError("boom"))

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert actions == [
        "connection_established",
        "authenticated",
        "disconnected",
        "reconnecting",
        "connection_error",
    ]


def test_on_message_dispatches_to_archive_and_appends_queue(tmp_path):
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
    )
    client = store["client"]

    frame = {
        "body": {
            "msgtype": "text",
            "from": {"userid": "YaoZuYi"},  # 姚祖怡，真实 userid（2026-07-13 联调确认）
            "text": {"content": "已收到，稍后回复"},
        }
    }
    asyncio.run(client.handlers["message"][0](frame))

    archived = list((tmp_path / "7-外部文档" / "采购部").glob("*.md"))
    assert len(archived) == 1
    assert archived[0].read_text(encoding="utf-8") == "已收到，稍后回复"

    new_queue = (tmp_path / "queue.md").read_text(encoding="utf-8")
    assert "采购专线" in new_queue


def test_on_message_also_forwards_to_paul(tmp_path):
    """Paul 2026-07-13 拍板：进件除归档外一律同步转发给 Paul。"""
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
    )
    client = store["client"]

    frame = {
        "body": {
            "msgtype": "text",
            "chattype": "single",
            "from": {"userid": "YaoZuYi"},
            "text": {"content": "已收到，稍后回复"},
        }
    }
    asyncio.run(client.handlers["message"][0](frame))

    forwarded = [m for m in client.sent_messages if m[0] == PAUL_USERID]
    assert len(forwarded) == 1
    assert "发件人：YaoZuYi" in forwarded[0][1]["markdown"]["content"]
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "inbound_forwarded_to_paul" in actions


def test_on_message_forward_failure_is_audited_not_raised(tmp_path, monkeypatch):
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
    )
    client = store["client"]

    import aibot_service.connection as connection_mod

    async def _boom(**kwargs):
        raise RuntimeError("转发模拟失败")

    monkeypatch.setattr(connection_mod, "forward_inbound_to_paul", _boom)

    frame = {"body": {"msgtype": "text", "from": {"userid": "YaoZuYi"}, "text": {"content": "x"}}}
    # 不应向上抛出，也不影响归档已成功
    asyncio.run(client.handlers["message"][0](frame))

    archived = list((tmp_path / "7-外部文档" / "采购部").glob("*.md"))
    assert len(archived) == 1
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "forward_dispatch_failed" in actions
    assert "archived" in actions


def test_on_message_notifies_department_group_when_configured(tmp_path, monkeypatch):
    """Paul 2026-07-12 拍板/2026-07-15 落地：归档成功后回部门群 webhook 发一条通报。"""
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    group_mapping_path = tmp_path / "group_mapping.yaml"
    group_mapping_path.write_text("采购部: WECOM_WEBHOOK_URL_PROCUREMENT\n", encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}
    calls = []
    monkeypatch.setattr(
        "aibot_service.group_notify.wecom.send_markdown",
        lambda url, content: calls.append((url, content)),
    )

    build_connector(
        secrets=_secrets(WECOM_WEBHOOK_URL_PROCUREMENT="https://example/webhook?key=P"),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        group_mapping_path=group_mapping_path,
        client_factory=fake_client_factory(store),
    )
    client = store["client"]

    frame = {
        "body": {
            "msgtype": "text",
            "from": {"userid": "YaoZuYi"},
            "text": {"content": "已收到，稍后回复"},
        }
    }
    asyncio.run(client.handlers["message"][0](frame))

    assert len(calls) == 1
    assert calls[0][0] == "https://example/webhook?key=P"
    assert "已归档" in calls[0][1]
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "group_notified" in actions


def test_on_message_skips_group_notify_when_unconfigured_by_default(tmp_path, monkeypatch):
    """默认 yaml 不含销售部——不应误发。"""
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}
    calls = []
    monkeypatch.setattr(
        "aibot_service.group_notify.wecom.send_markdown",
        lambda url, content: calls.append((url, content)),
    )

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
    )
    client = store["client"]

    frame = {
        "body": {
            "msgtype": "text",
            "from": {"userid": "Hongqin.Wang"},
            "text": {"content": "已收到，稍后回复"},
        }
    }
    asyncio.run(client.handlers["message"][0](frame))

    assert calls == []
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "group_notify_skipped" in actions
    assert "group_notified" not in actions


def test_on_message_group_notify_failure_is_audited_not_raised(tmp_path, monkeypatch):
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    group_mapping_path = tmp_path / "group_mapping.yaml"
    group_mapping_path.write_text("采购部: WECOM_WEBHOOK_URL_PROCUREMENT\n", encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    build_connector(
        secrets=_secrets(WECOM_WEBHOOK_URL_PROCUREMENT="https://example/webhook?key=P"),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        group_mapping_path=group_mapping_path,
        client_factory=fake_client_factory(store),
    )
    client = store["client"]

    import aibot_service.connection as connection_mod

    async def _boom(**kwargs):
        raise RuntimeError("通报模拟失败")

    monkeypatch.setattr(connection_mod, "notify_department_group", _boom)

    frame = {"body": {"msgtype": "text", "from": {"userid": "YaoZuYi"}, "text": {"content": "x"}}}
    # 不应向上抛出，也不影响归档已成功
    asyncio.run(client.handlers["message"][0](frame))

    archived = list((tmp_path / "7-外部文档" / "采购部").glob("*.md"))
    assert len(archived) == 1
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "group_notify_dispatch_failed" in actions
    assert "archived" in actions


def test_on_message_dispatch_failure_is_audited_not_raised(tmp_path, monkeypatch):
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
    )
    client = store["client"]

    import aibot_service.connection as connection_mod

    async def _boom(**kwargs):
        raise RuntimeError("归档模拟失败")

    monkeypatch.setattr(connection_mod, "archive_inbound_message", _boom)

    frame = {"body": {"msgtype": "text", "from": {"userid": "YaoZuYi"}, "text": {"content": "x"}}}
    # 不应向上抛出——门禁①要求归档失败也要留痕而不是让服务崩溃
    asyncio.run(client.handlers["message"][0](frame))

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "message_dispatch_failed" in actions
