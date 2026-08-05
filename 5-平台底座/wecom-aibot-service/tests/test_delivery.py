import asyncio

import pytest

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector

from aibot_service.constants import PAUL_USERID
from aibot_service.delivery import push_followup, BackfillWriteError
from aibot_service.gates import DeliveryNotFinalizedError

from fakes import fake_client_factory

README_TEXT = """\
## 现有跟进信清单

| 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |
|------|--------|---------|---------|---------|
| 2026-07-06 | 质量部 · 陈忱 | 8D 预填校准会议程 | 校准会 7 月内 | 🆕 待发 |
| 2026-07-04 | 质量部 · 陈忱 | 产品类样本 | 尽量 7/15 前 | ✅ 已发 |
"""


def _match_8d(cells):
    return "8D 预填校准会议程" in cells[2]


def _setup(tmp_path, readme_text=README_TEXT):
    readme_path = tmp_path / "README.md"
    readme_path.write_text(readme_text, encoding="utf-8")
    md_path = tmp_path / "letter.md"
    md_path.write_text("正文：请尽快回复。", encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}
    connector = AibotConnector("bot", "secret", client_factory=fake_client_factory(store))
    return readme_path, md_path, audit, connector, store


def test_push_followup_happy_path_no_docx(tmp_path):
    readme_path, md_path, audit, connector, store = _setup(tmp_path)

    result = asyncio.run(
        push_followup(
            readme_path=readme_path,
            md_path=md_path,
            docx_path=None,
            connector=connector,
            chatid="chat-1",
            match=_match_8d,
            audit=audit,
            cc_to_paul=False,  # 本测试只关心主推送，CC 行为见专门的 CC 测试
        )
    )

    assert result.media_id is None
    chatid, body = store["client"].sent_messages[0]
    assert chatid == "chat-1"
    assert body["markdown"]["content"] == "正文：请尽快回复。"

    new_text = readme_path.read_text(encoding="utf-8")
    assert "✅ 已推送" in new_text
    assert "🆕 待发" not in new_text  # 已被回填替换

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "followup_delivered" in actions
    assert "followup_backfilled" in actions


def test_push_followup_with_docx_uploads_and_sends_file(tmp_path):
    readme_path, md_path, audit, connector, store = _setup(tmp_path)
    docx_path = tmp_path / "letter.docx"
    docx_path.write_bytes(b"fake docx bytes")

    store_client_setup_needed = True
    # 需要先拿到 client 才能设 raw_frame_responses；连接尚未建立也没关系，
    # client 对象已在 AibotConnector 构造阶段创建好。
    client = store["client"]
    client.raw_frame_responses["aibot_upload_media_init"] = [{"body": {"upload_id": "U1"}}]
    client.raw_frame_responses["aibot_upload_media_finish"] = [{"body": {"media_id": "M1"}}]

    result = asyncio.run(
        push_followup(
            readme_path=readme_path,
            md_path=md_path,
            docx_path=docx_path,
            connector=connector,
            chatid="chat-1",
            match=_match_8d,
            audit=audit,
            cc_to_paul=False,  # 本测试只关心主推送，CC 行为见专门的 CC 测试
        )
    )

    assert result.media_id == "M1"
    # 第一条是 markdown 正文，第二条是 file 消息
    assert len(client.sent_messages) == 2
    assert client.sent_messages[1][1] == {"msgtype": "file", "file": {"media_id": "M1"}}


def test_push_followup_multiple_attachments(tmp_path):
    """队列 #93：docx_path（首个）+ extra_attachments（追加）一次全部发出。"""
    readme_path, md_path, audit, connector, store = _setup(tmp_path)
    docx_path = tmp_path / "letter.docx"
    docx_path.write_bytes(b"fake docx bytes")
    extra1 = tmp_path / "attachment1.xlsx"
    extra1.write_bytes(b"fake xlsx bytes")
    extra2 = tmp_path / "attachment2.pdf"
    extra2.write_bytes(b"fake pdf bytes")

    client = store["client"]
    client.raw_frame_responses["aibot_upload_media_init"] = [
        {"body": {"upload_id": "U1"}},
        {"body": {"upload_id": "U2"}},
        {"body": {"upload_id": "U3"}},
    ]
    client.raw_frame_responses["aibot_upload_media_finish"] = [
        {"body": {"media_id": "M1"}},
        {"body": {"media_id": "M2"}},
        {"body": {"media_id": "M3"}},
    ]

    result = asyncio.run(
        push_followup(
            readme_path=readme_path,
            md_path=md_path,
            docx_path=docx_path,
            extra_attachments=[extra1, extra2],
            connector=connector,
            chatid="chat-1",
            match=_match_8d,
            audit=audit,
            cc_to_paul=False,
        )
    )

    assert result.media_id == "M1"
    assert result.media_ids == ["M1", "M2", "M3"]
    # 正文 markdown 1 条 + 三份附件各 1 条 file 消息 = 4 条
    assert len(client.sent_messages) == 4
    assert client.sent_messages[1] == ("chat-1", {"msgtype": "file", "file": {"media_id": "M1"}})
    assert client.sent_messages[2] == ("chat-1", {"msgtype": "file", "file": {"media_id": "M2"}})
    assert client.sent_messages[3] == ("chat-1", {"msgtype": "file", "file": {"media_id": "M3"}})

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    delivered = [r for r in audit.query_by(scenario="wecom-aibot") if r["action"] == "followup_delivered"]
    assert delivered[0]["decision"]["media_ids"] == ["M1", "M2", "M3"]


def test_push_followup_extra_attachments_only_no_docx(tmp_path):
    """docx_path 为空、只有 extra_attachments 时仍能正常工作（无隐含依赖首位必须是 docx）。"""
    readme_path, md_path, audit, connector, store = _setup(tmp_path)
    extra1 = tmp_path / "attachment1.xlsx"
    extra1.write_bytes(b"fake xlsx bytes")

    client = store["client"]
    client.raw_frame_responses["aibot_upload_media_init"] = [{"body": {"upload_id": "U1"}}]
    client.raw_frame_responses["aibot_upload_media_finish"] = [{"body": {"media_id": "M1"}}]

    result = asyncio.run(
        push_followup(
            readme_path=readme_path,
            md_path=md_path,
            docx_path=None,
            extra_attachments=[extra1],
            connector=connector,
            chatid="chat-1",
            match=_match_8d,
            audit=audit,
            cc_to_paul=False,
        )
    )

    assert result.media_id == "M1"
    assert result.media_ids == ["M1"]


def test_push_followup_rejects_when_not_finalized(tmp_path):
    text = README_TEXT.replace("| 🆕 待发 |", "| ✅ 已发 |", 1)
    readme_path, md_path, audit, connector, store = _setup(tmp_path, text)

    with pytest.raises(DeliveryNotFinalizedError):
        asyncio.run(
            push_followup(
                readme_path=readme_path,
                md_path=md_path,
                docx_path=None,
                connector=connector,
                chatid="chat-1",
                match=_match_8d,
                audit=audit,
            )
        )

    assert store["client"].sent_messages == []
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "delivery_rejected" in actions


def test_push_followup_backfill_failure_still_raises_after_send(tmp_path, monkeypatch):
    readme_path, md_path, audit, connector, store = _setup(tmp_path)

    import aibot_service.delivery as delivery_mod

    def _boom(text, loc, new_status):
        raise OSError("模拟文件被占用")

    monkeypatch.setattr(delivery_mod, "write_status", _boom)

    with pytest.raises(BackfillWriteError):
        asyncio.run(
            push_followup(
                readme_path=readme_path,
                md_path=md_path,
                docx_path=None,
                connector=connector,
                chatid="chat-1",
                match=_match_8d,
                audit=audit,
                cc_to_paul=False,  # 本测试只关心主推送+回填失败行为
            )
        )

    # 发送本身已成功（不因回填失败而"假装没发过"）
    assert len(store["client"].sent_messages) == 1
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "followup_delivered" in actions
    assert "followup_backfill_failed" in actions


def test_push_followup_cc_to_paul_default_on(tmp_path):
    """Paul 拍板：出站跟进信固定抄送逻辑，默认开启。"""
    readme_path, md_path, audit, connector, store = _setup(tmp_path)

    asyncio.run(
        push_followup(
            readme_path=readme_path,
            md_path=md_path,
            docx_path=None,
            connector=connector,
            chatid="chat-1",
            match=_match_8d,
            audit=audit,
        )
    )

    assert len(store["client"].sent_messages) == 2
    primary_chatid, primary_body = store["client"].sent_messages[0]
    cc_chatid, cc_body = store["client"].sent_messages[1]
    assert primary_chatid == "chat-1"
    assert cc_chatid == PAUL_USERID
    assert "【抄送】" in cc_body["markdown"]["content"]
    assert "正文：请尽快回复。" in cc_body["markdown"]["content"]

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "followup_cc_delivered" in actions


def test_push_followup_cc_includes_docx_attachment(tmp_path):
    readme_path, md_path, audit, connector, store = _setup(tmp_path)
    docx_path = tmp_path / "letter.docx"
    docx_path.write_bytes(b"fake docx bytes")
    client = store["client"]
    client.raw_frame_responses["aibot_upload_media_init"] = [{"body": {"upload_id": "U1"}}]
    client.raw_frame_responses["aibot_upload_media_finish"] = [{"body": {"media_id": "M1"}}]

    asyncio.run(
        push_followup(
            readme_path=readme_path,
            md_path=md_path,
            docx_path=docx_path,
            connector=connector,
            chatid="chat-1",
            match=_match_8d,
            audit=audit,
        )
    )

    # 主markdown / 主file / CCmarkdown / CCfile
    assert len(client.sent_messages) == 4
    assert client.sent_messages[2][0] == PAUL_USERID
    assert client.sent_messages[3] == (PAUL_USERID, {"msgtype": "file", "file": {"media_id": "M1"}})


def test_push_followup_cc_skipped_when_primary_target_is_paul(tmp_path):
    readme_path, md_path, audit, connector, store = _setup(tmp_path)

    asyncio.run(
        push_followup(
            readme_path=readme_path,
            md_path=md_path,
            docx_path=None,
            connector=connector,
            chatid=PAUL_USERID,
            match=_match_8d,
            audit=audit,
        )
    )

    # 主送目标就是 Paul，不重复抄送给自己
    assert len(store["client"].sent_messages) == 1
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "followup_cc_delivered" not in actions


def test_push_followup_cc_disabled_sends_only_primary(tmp_path):
    readme_path, md_path, audit, connector, store = _setup(tmp_path)

    asyncio.run(
        push_followup(
            readme_path=readme_path,
            md_path=md_path,
            docx_path=None,
            connector=connector,
            chatid="chat-1",
            match=_match_8d,
            audit=audit,
            cc_to_paul=False,
        )
    )

    assert len(store["client"].sent_messages) == 1


def test_push_followup_cc_failure_does_not_break_primary_success(tmp_path, monkeypatch):
    """抄送失败不该掩盖主推送已成功的事实——不抛异常，只记审计。"""
    readme_path, md_path, audit, connector, store = _setup(tmp_path)

    original_send_markdown = connector.send_markdown
    call_count = {"n": 0}

    async def flaky_send_markdown(chatid, content):
        call_count["n"] += 1
        if chatid == PAUL_USERID:
            raise RuntimeError("模拟企微抄送失败")
        return await original_send_markdown(chatid, content)

    monkeypatch.setattr(connector, "send_markdown", flaky_send_markdown)

    result = asyncio.run(
        push_followup(
            readme_path=readme_path,
            md_path=md_path,
            docx_path=None,
            connector=connector,
            chatid="chat-1",
            match=_match_8d,
            audit=audit,
        )
    )

    # 主推送依旧成功、README 依旧正确回填
    assert result.new_status.startswith("✅ 已推送")
    new_text = readme_path.read_text(encoding="utf-8")
    assert "✅ 已推送" in new_text

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "followup_cc_failed" in actions
    assert "followup_cc_delivered" not in actions


# 队列 #270：群 cc 改走机器人 chatid 通道（取代群机器人 webhook 单向通报）。


def test_push_followup_group_cc_sent_when_chatid_provided(tmp_path):
    """cc_group_chatid 提供时，主送后额外用同一机器人通道发一份到该群。"""
    readme_path, md_path, audit, connector, store = _setup(tmp_path)

    asyncio.run(
        push_followup(
            readme_path=readme_path,
            md_path=md_path,
            docx_path=None,
            connector=connector,
            chatid="chat-1",
            match=_match_8d,
            audit=audit,
            cc_to_paul=False,  # 本测试只关心群 cc，避免与 Paul cc 消息数混淆
            cc_group_chatid="group-procurement",
        )
    )

    assert len(store["client"].sent_messages) == 2
    primary_chatid, primary_body = store["client"].sent_messages[0]
    group_chatid, group_body = store["client"].sent_messages[1]
    assert primary_chatid == "chat-1"
    assert group_chatid == "group-procurement"
    assert "【抄送】" in group_body["markdown"]["content"]
    assert "正文：请尽快回复。" in group_body["markdown"]["content"]

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "followup_group_cc_delivered" in actions
    assert "followup_group_cc_failed" not in actions


def test_push_followup_group_cc_includes_attachments(tmp_path):
    readme_path, md_path, audit, connector, store = _setup(tmp_path)
    docx_path = tmp_path / "letter.docx"
    docx_path.write_bytes(b"fake docx bytes")
    client = store["client"]
    client.raw_frame_responses["aibot_upload_media_init"] = [{"body": {"upload_id": "U1"}}]
    client.raw_frame_responses["aibot_upload_media_finish"] = [{"body": {"media_id": "M1"}}]

    asyncio.run(
        push_followup(
            readme_path=readme_path,
            md_path=md_path,
            docx_path=docx_path,
            connector=connector,
            chatid="chat-1",
            match=_match_8d,
            audit=audit,
            cc_to_paul=False,
            cc_group_chatid="group-procurement",
        )
    )

    # 主markdown / 主file / 群cc markdown / 群cc file
    assert len(client.sent_messages) == 4
    assert client.sent_messages[2][0] == "group-procurement"
    assert client.sent_messages[3] == ("group-procurement", {"msgtype": "file", "file": {"media_id": "M1"}})


def test_push_followup_group_cc_not_attempted_when_chatid_missing(tmp_path):
    """cc_group_chatid 未提供（默认 None）——完全不尝试群 cc，不产生相关审计。"""
    readme_path, md_path, audit, connector, store = _setup(tmp_path)

    asyncio.run(
        push_followup(
            readme_path=readme_path,
            md_path=md_path,
            docx_path=None,
            connector=connector,
            chatid="chat-1",
            match=_match_8d,
            audit=audit,
            cc_to_paul=False,
        )
    )

    assert len(store["client"].sent_messages) == 1
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "followup_group_cc_delivered" not in actions
    assert "followup_group_cc_failed" not in actions
    assert "followup_group_cc_skipped" not in actions


def test_push_followup_group_cc_skipped_when_same_as_primary_target(tmp_path):
    """群 chatid 恰好就是主送目标时不重复发送。"""
    readme_path, md_path, audit, connector, store = _setup(tmp_path)

    asyncio.run(
        push_followup(
            readme_path=readme_path,
            md_path=md_path,
            docx_path=None,
            connector=connector,
            chatid="chat-1",
            match=_match_8d,
            audit=audit,
            cc_to_paul=False,
            cc_group_chatid="chat-1",
        )
    )

    assert len(store["client"].sent_messages) == 1
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "followup_group_cc_delivered" not in actions


def test_push_followup_group_cc_failure_does_not_break_primary_success(tmp_path, monkeypatch):
    """群 cc 失败不该掩盖主推送已成功的事实——不抛异常，只记审计。"""
    readme_path, md_path, audit, connector, store = _setup(tmp_path)

    original_send_markdown = connector.send_markdown

    async def flaky_send_markdown(chatid, content):
        if chatid == "group-procurement":
            raise RuntimeError("模拟企微群 cc 失败")
        return await original_send_markdown(chatid, content)

    monkeypatch.setattr(connector, "send_markdown", flaky_send_markdown)

    result = asyncio.run(
        push_followup(
            readme_path=readme_path,
            md_path=md_path,
            docx_path=None,
            connector=connector,
            chatid="chat-1",
            match=_match_8d,
            audit=audit,
            cc_to_paul=False,
            cc_group_chatid="group-procurement",
        )
    )

    # 主推送依旧成功、README 依旧正确回填
    assert result.new_status.startswith("✅ 已推送")
    new_text = readme_path.read_text(encoding="utf-8")
    assert "✅ 已推送" in new_text

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "followup_group_cc_failed" in actions
    assert "followup_group_cc_delivered" not in actions


def test_push_followup_group_cc_and_paul_cc_both_fire_independently(tmp_path):
    """cc_to_paul 与 cc_group_chatid 互不影响，均可同时生效（各自独立隔离）。"""
    readme_path, md_path, audit, connector, store = _setup(tmp_path)

    asyncio.run(
        push_followup(
            readme_path=readme_path,
            md_path=md_path,
            docx_path=None,
            connector=connector,
            chatid="chat-1",
            match=_match_8d,
            audit=audit,
            cc_group_chatid="group-procurement",
        )
    )

    # 主送 + Paul cc + 群 cc = 3 条 markdown 消息
    assert len(store["client"].sent_messages) == 3
    chatids = [c for c, _ in store["client"].sent_messages]
    assert chatids == ["chat-1", PAUL_USERID, "group-procurement"]

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "followup_cc_delivered" in actions
    assert "followup_group_cc_delivered" in actions
