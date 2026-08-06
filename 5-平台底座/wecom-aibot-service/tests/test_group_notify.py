import asyncio

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.secrets import EnvSecretsProvider

from aibot_service.group_notify import notify_department_group, notify_department_group_via_chatid


def _secrets(**kv):
    return EnvSecretsProvider(override=kv)


def test_notify_posts_to_configured_group_webhook(tmp_path, monkeypatch):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    calls = []
    monkeypatch.setattr(
        "aibot_service.group_notify.wecom.send_markdown",
        lambda url, content: calls.append((url, content)),
    )

    asyncio.run(
        notify_department_group(
            department="财务部",
            matched=True,
            sender="tangyanping",
            msgtype="text",
            filename="财务部-tangyanping-回复-2026-07-14-文本反馈-abc123.md",
            secrets=_secrets(WECOM_WEBHOOK_URL_FINANCE="https://example/webhook?key=REAL"),
            group_mapping={"财务部": "WECOM_WEBHOOK_URL_FINANCE"},
            audit=audit,
        )
    )

    assert len(calls) == 1
    url, content = calls[0]
    assert url == "https://example/webhook?key=REAL"
    assert "已归档" in content
    assert "tangyanping" in content
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "group_notified" in actions


def test_notify_skipped_when_sender_unmatched(tmp_path, monkeypatch):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    calls = []
    monkeypatch.setattr(
        "aibot_service.group_notify.wecom.send_markdown",
        lambda url, content: calls.append((url, content)),
    )

    asyncio.run(
        notify_department_group(
            department="待分拣",
            matched=False,
            sender="unknown-user",
            msgtype="text",
            filename="待分拣-unknown-user-回复-2026-07-14-文本反馈-abc123.md",
            secrets=_secrets(WECOM_WEBHOOK_URL_FINANCE="https://example/webhook?key=REAL"),
            group_mapping={"财务部": "WECOM_WEBHOOK_URL_FINANCE"},
            audit=audit,
        )
    )

    assert calls == []
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "group_notify_skipped" in actions
    assert "group_notified" not in actions


def test_notify_skipped_when_department_absent_from_mapping(tmp_path, monkeypatch):
    """销售部 Paul 2026-07-15 拍板暂不启用——不在映射表里，应 fail-closed 跳过。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    calls = []
    monkeypatch.setattr(
        "aibot_service.group_notify.wecom.send_markdown",
        lambda url, content: calls.append((url, content)),
    )

    asyncio.run(
        notify_department_group(
            department="销售部",
            matched=True,
            sender="Hongqin.Wang",
            msgtype="text",
            filename="x.md",
            secrets=_secrets(),
            group_mapping={"财务部": "WECOM_WEBHOOK_URL_FINANCE"},
            audit=audit,
        )
    )

    assert calls == []
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "group_notify_skipped" in actions


def test_notify_skipped_when_webhook_env_var_missing(tmp_path, monkeypatch):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    calls = []
    monkeypatch.setattr(
        "aibot_service.group_notify.wecom.send_markdown",
        lambda url, content: calls.append((url, content)),
    )

    asyncio.run(
        notify_department_group(
            department="财务部",
            matched=True,
            sender="tangyanping",
            msgtype="text",
            filename="x.md",
            secrets=_secrets(),  # WECOM_WEBHOOK_URL_FINANCE 未配置
            group_mapping={"财务部": "WECOM_WEBHOOK_URL_FINANCE"},
            audit=audit,
        )
    )

    assert calls == []
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "group_notify_skipped" in actions


def test_notify_skipped_when_webhook_env_var_empty_string(tmp_path, monkeypatch):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    calls = []
    monkeypatch.setattr(
        "aibot_service.group_notify.wecom.send_markdown",
        lambda url, content: calls.append((url, content)),
    )

    asyncio.run(
        notify_department_group(
            department="财务部",
            matched=True,
            sender="tangyanping",
            msgtype="text",
            filename="x.md",
            secrets=_secrets(WECOM_WEBHOOK_URL_FINANCE=""),
            group_mapping={"财务部": "WECOM_WEBHOOK_URL_FINANCE"},
            audit=audit,
        )
    )

    assert calls == []
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "group_notify_skipped" in actions


def test_notify_file_message_uses_file_wording(tmp_path, monkeypatch):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    calls = []
    monkeypatch.setattr(
        "aibot_service.group_notify.wecom.send_markdown",
        lambda url, content: calls.append((url, content)),
    )

    asyncio.run(
        notify_department_group(
            department="质量部",
            matched=True,
            sender="ChenChen",
            msgtype="file",
            filename="质量部-ChenChen-回复-2026-07-14-8D报告-abc123.docx",
            secrets=_secrets(WECOM_WEBHOOK_URL_QUALITY="https://example/webhook?key=Q"),
            group_mapping={"质量部": "WECOM_WEBHOOK_URL_QUALITY"},
            audit=audit,
        )
    )

    _, content = calls[0]
    assert "文件" in content
    assert "8D报告" in content


# ── 队列 #279/#280：notify_department_group_via_chatid（aibot 通道，取代
# 上面这套 webhook 测试要验证的同一功能，判据与审计 action 名完全对齐，
# 只换发送介质）─────────────────────────────────────────────────────────

class _FakeConnector:
    """最小化 `send_markdown(chatid, content)` 协程替身，不需要完整
    `AibotConnector`/`AibotClientLike` 契约——`notify_department_group_
    via_chatid` 对 connector 的隐式依赖就这一个方法。"""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    async def send_markdown(self, chatid, content):
        self.calls.append((chatid, content))


def test_notify_via_chatid_sends_to_configured_group(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = _FakeConnector()

    asyncio.run(
        notify_department_group_via_chatid(
            department="财务部",
            matched=True,
            sender="tangyanping",
            msgtype="text",
            filename="财务部-tangyanping-回复-2026-07-14-文本反馈-abc123.md",
            connector=connector,
            chatid_mapping={"财务部": "GroupChatIdFinance"},
            audit=audit,
        )
    )

    assert len(connector.calls) == 1
    chatid, content = connector.calls[0]
    assert chatid == "GroupChatIdFinance"
    assert "已归档" in content
    assert "tangyanping" in content
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "group_notified" in actions


def test_notify_via_chatid_skipped_when_sender_unmatched(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = _FakeConnector()

    asyncio.run(
        notify_department_group_via_chatid(
            department="待分拣",
            matched=False,
            sender="unknown-user",
            msgtype="text",
            filename="待分拣-unknown-user-回复-2026-07-14-文本反馈-abc123.md",
            connector=connector,
            chatid_mapping={"财务部": "GroupChatIdFinance"},
            audit=audit,
        )
    )

    assert connector.calls == []
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "group_notify_skipped" in actions
    assert "group_notified" not in actions


def test_notify_via_chatid_skipped_when_department_absent_from_mapping(tmp_path):
    """销售部 Paul 2026-07-15 拍板暂不启用——不在映射表里，应 fail-closed 跳过。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = _FakeConnector()

    asyncio.run(
        notify_department_group_via_chatid(
            department="销售部",
            matched=True,
            sender="Hongqin.Wang",
            msgtype="text",
            filename="x.md",
            connector=connector,
            chatid_mapping={"财务部": "GroupChatIdFinance"},
            audit=audit,
        )
    )

    assert connector.calls == []
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "group_notify_skipped" in actions


def test_notify_via_chatid_skipped_when_value_missing(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = _FakeConnector()

    asyncio.run(
        notify_department_group_via_chatid(
            department="财务部",
            matched=True,
            sender="tangyanping",
            msgtype="text",
            filename="x.md",
            connector=connector,
            chatid_mapping={},  # 财务部不在表里
            audit=audit,
        )
    )

    assert connector.calls == []
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "group_notify_skipped" in actions


def test_notify_via_chatid_skipped_when_value_empty_string(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = _FakeConnector()

    asyncio.run(
        notify_department_group_via_chatid(
            department="财务部",
            matched=True,
            sender="tangyanping",
            msgtype="text",
            filename="x.md",
            connector=connector,
            chatid_mapping={"财务部": ""},  # 占位未采集
            audit=audit,
        )
    )

    assert connector.calls == []
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "group_notify_skipped" in actions


def test_notify_via_chatid_file_message_uses_file_wording(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = _FakeConnector()

    asyncio.run(
        notify_department_group_via_chatid(
            department="质量部",
            matched=True,
            sender="ChenChen",
            msgtype="file",
            filename="质量部-ChenChen-回复-2026-07-14-8D报告-abc123.docx",
            connector=connector,
            chatid_mapping={"质量部": "GroupChatIdQuality"},
            audit=audit,
        )
    )

    _, content = connector.calls[0]
    assert "文件" in content
    assert "8D报告" in content
