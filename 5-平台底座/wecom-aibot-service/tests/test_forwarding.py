import asyncio

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector

from aibot_service.constants import PAUL_USERID
from aibot_service.forwarding import forward_inbound_to_paul, should_forward
from aibot_service.frame_parsing import InboundMessage

from fakes import fake_client_factory


def _setup(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}
    connector = AibotConnector("bot", "secret", client_factory=fake_client_factory(store))
    return audit, connector, store


def test_should_forward_true_for_normal_sender():
    msg = InboundMessage(sender="tangyanping", msgtype="text", text_content="hi")
    assert should_forward(msg) is True


def test_should_forward_false_when_sender_is_paul():
    msg = InboundMessage(sender=PAUL_USERID, msgtype="text", text_content="hi")
    assert should_forward(msg) is False


def test_forward_text_message_sends_header_and_content(tmp_path):
    audit, connector, store = _setup(tmp_path)
    frame = {"body": {"chattype": "single"}}
    message = InboundMessage(sender="tangyanping", msgtype="text", text_content="收到，明天回复")

    asyncio.run(
        forward_inbound_to_paul(frame=frame, message=message, connector=connector, audit=audit)
    )

    chatid, body = store["client"].sent_messages[0]
    assert chatid == PAUL_USERID
    assert "发件人：tangyanping" in body["markdown"]["content"]
    assert "私聊" in body["markdown"]["content"]
    assert "收到，明天回复" in body["markdown"]["content"]
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "inbound_forwarded_to_paul" in actions


def test_forward_group_message_labels_source_with_chatid(tmp_path):
    audit, connector, store = _setup(tmp_path)
    frame = {"body": {"chattype": "group", "chatid": "wrvDL_DAAAva1MWrKjLmuDWOu1BNxHaA"}}
    message = InboundMessage(sender="tangyanping", msgtype="text", text_content="@邵总数字人")

    asyncio.run(
        forward_inbound_to_paul(frame=frame, message=message, connector=connector, audit=audit)
    )

    _, body = store["client"].sent_messages[0]
    assert "群聊" in body["markdown"]["content"]
    assert "wrvDL_DAAAva1MWrKjLmuDWOu1BNxHaA" in body["markdown"]["content"]


def test_forward_file_message_downloads_and_reuploads_as_is(tmp_path):
    audit, connector, store = _setup(tmp_path)
    store["client"].download_response = (b"binary-content", "attachment.docx")
    store["client"].raw_frame_responses["aibot_upload_media_init"] = [
        {"body": {"upload_id": "U1"}}
    ]
    store["client"].raw_frame_responses["aibot_upload_media_finish"] = [
        {"body": {"media_id": "M1"}}
    ]
    frame = {"body": {"chattype": "single"}}
    message = InboundMessage(
        sender="tangyanping",
        msgtype="file",
        file_url="https://example/f",
        file_aes_key="AESKEY",
        file_name_hint="attachment.docx",
    )

    asyncio.run(
        forward_inbound_to_paul(frame=frame, message=message, connector=connector, audit=audit)
    )

    # 第一条是头部说明，第二条是文件本身
    assert len(store["client"].sent_messages) == 2
    header_chatid, header_body = store["client"].sent_messages[0]
    file_chatid, file_body = store["client"].sent_messages[1]
    assert header_chatid == PAUL_USERID
    assert "发件人：tangyanping" in header_body["markdown"]["content"]
    assert file_chatid == PAUL_USERID
    assert file_body == {"msgtype": "file", "file": {"media_id": "M1"}}
    assert store["client"].downloads == [("https://example/f", "AESKEY")]


def test_forward_skipped_when_sender_is_paul(tmp_path):
    audit, connector, store = _setup(tmp_path)
    frame = {"body": {"chattype": "single"}}
    message = InboundMessage(sender=PAUL_USERID, msgtype="text", text_content="自己发的")

    asyncio.run(
        forward_inbound_to_paul(frame=frame, message=message, connector=connector, audit=audit)
    )

    assert store["client"].sent_messages == []
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "inbound_forward_skipped" in actions
    assert "inbound_forwarded_to_paul" not in actions


def test_forward_unsupported_msgtype_sends_placeholder_note(tmp_path):
    audit, connector, store = _setup(tmp_path)
    frame = {"body": {"chattype": "single"}}
    message = InboundMessage(sender="tangyanping", msgtype="voice")

    asyncio.run(
        forward_inbound_to_paul(frame=frame, message=message, connector=connector, audit=audit)
    )

    _, body = store["client"].sent_messages[0]
    assert "未支持转发的消息类型" in body["markdown"]["content"]
