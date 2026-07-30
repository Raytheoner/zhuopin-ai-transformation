import asyncio

import pytest

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector

from aibot_service.frame_parsing import InboundMessage
from aibot_service.intake import (
    archive_inbound_message,
    ArchiveCorruptionError,
    UnsupportedMessageTypeError,
)
from aibot_service.department_mapping import UNMATCHED_DEPARTMENT
from aibot_service.queue_lock_pending import read_deferred_appends

from fakes import fake_client_factory, FakeQueueEditLock

QUEUE_TEXT = """\
## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 1 | 既有任务 | CC | p | e | 待领 | — | 07-09 |
"""

MAPPING = {"姚祖怡": "采购部", "陈忱": "质量部"}


def _setup(tmp_path):
    docs_root = tmp_path / "7-外部文档"
    queue_path = tmp_path / "queue.md"
    queue_path.write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}
    connector = AibotConnector("bot", "secret", client_factory=fake_client_factory(store))
    return docs_root, queue_path, audit, connector, store


def test_archive_text_message_matched_department(tmp_path):
    docs_root, queue_path, audit, connector, store = _setup(tmp_path)
    message = InboundMessage(sender="姚祖怡", msgtype="text", text_content="收到，明天回复")

    result = asyncio.run(
        archive_inbound_message(
            message=message,
            connector=connector,
            external_docs_root=docs_root,
            queue_path=queue_path,
            department_mapping=MAPPING,
            audit=audit,
        )
    )

    assert result.department == "采购部"
    assert result.matched is True
    assert result.archived_path.exists()
    assert result.archived_path.read_text(encoding="utf-8") == "收到，明天回复"
    assert "采购部-姚祖怡-回复-" in result.archived_path.name

    new_queue = queue_path.read_text(encoding="utf-8")
    assert "采购专线" in new_queue
    assert "| 2 |" in new_queue

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "archived" in actions
    assert "queue_appended" in actions
    assert "mapping_unmatched" not in actions


def test_archive_matched_department_outside_four_domains_falls_back_to_paul_owner(tmp_path):
    """2026-07-22（队列 #70）：陈承（IT）命中 `department_mapping` 表（不再是
    未命中/待分拣），但 IT 不是 Cowork 的四域专线之一，`DEPARTMENT_TO_QUEUE_OWNER`
    没有对应项——队列行的领取方应落回默认值 Paul（与"完全未命中发送人"用的
    同一个默认值），而不是报错或误标某个专线。"""
    docs_root, queue_path, audit, connector, store = _setup(tmp_path)
    mapping = {**MAPPING, "陈承": "IT"}
    message = InboundMessage(sender="陈承", msgtype="text", text_content="AP/Query 已修复")

    result = asyncio.run(
        archive_inbound_message(
            message=message,
            connector=connector,
            external_docs_root=docs_root,
            queue_path=queue_path,
            department_mapping=mapping,
            audit=audit,
        )
    )

    assert result.department == "IT"
    assert result.matched is True
    assert "IT-陈承-回复-" in result.archived_path.name
    assert result.archived_path.parent == docs_root / "IT"

    new_queue = queue_path.read_text(encoding="utf-8")
    assert "| Paul |" in new_queue


def test_archive_multiple_same_day_messages_do_not_overwrite(tmp_path):
    """2026-07-13 真实生产链路联调发现的回归：同发送人同天多条消息此前会
    互相覆盖归档文件（原文件名只到日期粒度），现按 msgid 消歧。"""
    docs_root, queue_path, audit, connector, store = _setup(tmp_path)

    first = InboundMessage(
        sender="姚祖怡", msgtype="text", text_content="第一条消息", msgid="msgid-AAA"
    )
    second = InboundMessage(
        sender="姚祖怡", msgtype="text", text_content="第二条消息", msgid="msgid-BBB"
    )

    result1 = asyncio.run(
        archive_inbound_message(
            message=first,
            connector=connector,
            external_docs_root=docs_root,
            queue_path=queue_path,
            department_mapping=MAPPING,
            audit=audit,
        )
    )
    result2 = asyncio.run(
        archive_inbound_message(
            message=second,
            connector=connector,
            external_docs_root=docs_root,
            queue_path=queue_path,
            department_mapping=MAPPING,
            audit=audit,
        )
    )

    assert result1.archived_path != result2.archived_path
    assert result1.archived_path.exists()
    assert result2.archived_path.exists()
    assert result1.archived_path.read_text(encoding="utf-8") == "第一条消息"
    assert result2.archived_path.read_text(encoding="utf-8") == "第二条消息"


def test_archive_file_message_downloads_and_writes_bytes(tmp_path):
    docs_root, queue_path, audit, connector, store = _setup(tmp_path)
    store["client"].download_response = (b"\x50\x4b\x03\x04fake-xlsx", "权重表.xlsx")
    message = InboundMessage(
        sender="陈忱",
        msgtype="file",
        file_url="https://example/files/1",
        file_aes_key="AESKEY",
        file_name_hint="权重表.xlsx",
    )

    result = asyncio.run(
        archive_inbound_message(
            message=message,
            connector=connector,
            external_docs_root=docs_root,
            queue_path=queue_path,
            department_mapping=MAPPING,
            audit=audit,
        )
    )

    assert result.department == "质量部"
    assert result.archived_path.suffix == ".xlsx"
    assert result.archived_path.read_bytes().startswith(b"\x50\x4b\x03\x04")
    assert store["client"].downloads == [("https://example/files/1", "AESKEY")]


def test_archive_file_message_with_non_utf8_binary_content_is_not_flagged_corrupt(tmp_path):
    """2026-07-13 真实生产链路联调发现的回归：归档一份真实 docx（本质是
    ZIP 二进制，含非 UTF-8 字节）此前会被写后读回校验误判为"写入损坏"
    （校验逻辑对所有归档文件不分青红皂白做 UTF-8 解码）。用真会让
    `bytes.decode("utf-8")` 抛错的内容验证不再误判。"""
    docs_root, queue_path, audit, connector, store = _setup(tmp_path)
    non_utf8_binary = b"PK\x03\x04\x9f\xff\xfe\x00binary-docx-content-not-valid-utf8"
    with pytest.raises(UnicodeDecodeError):
        non_utf8_binary.decode("utf-8")  # 确认这段内容确实不是合法 UTF-8，测试才有意义
    store["client"].download_response = (non_utf8_binary, "跟进信.docx")
    message = InboundMessage(
        sender="陈忱",
        msgtype="file",
        file_url="https://example/files/2",
        file_aes_key="AESKEY",
        file_name_hint="跟进信.docx",
    )

    result = asyncio.run(
        archive_inbound_message(
            message=message,
            connector=connector,
            external_docs_root=docs_root,
            queue_path=queue_path,
            department_mapping=MAPPING,
            audit=audit,
        )
    )

    assert result.archived_path.read_bytes() == non_utf8_binary
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "archive_corruption_detected" not in actions
    assert "archived" in actions


def test_archive_unmatched_sender_goes_to_pending_bucket(tmp_path):
    docs_root, queue_path, audit, connector, store = _setup(tmp_path)
    message = InboundMessage(sender="陌生人", msgtype="text", text_content="谁在说话")

    result = asyncio.run(
        archive_inbound_message(
            message=message,
            connector=connector,
            external_docs_root=docs_root,
            queue_path=queue_path,
            department_mapping=MAPPING,
            audit=audit,
        )
    )

    assert result.matched is False
    assert result.department == UNMATCHED_DEPARTMENT
    assert (docs_root / UNMATCHED_DEPARTMENT).exists()

    new_queue = queue_path.read_text(encoding="utf-8")
    assert "Paul" in new_queue
    assert "发送人身份待确认" in new_queue

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "mapping_unmatched" in actions


def test_archive_unsupported_msgtype_raises(tmp_path):
    docs_root, queue_path, audit, connector, store = _setup(tmp_path)
    message = InboundMessage(sender="姚祖怡", msgtype="voice")

    with pytest.raises(UnsupportedMessageTypeError):
        asyncio.run(
            archive_inbound_message(
                message=message,
                connector=connector,
                external_docs_root=docs_root,
                queue_path=queue_path,
                department_mapping=MAPPING,
                audit=audit,
            )
        )


def test_archive_detects_corrupted_filename(tmp_path, monkeypatch):
    docs_root, queue_path, audit, connector, store = _setup(tmp_path)
    message = InboundMessage(sender="姚祖怡", msgtype="text", text_content="正常内容")

    import aibot_service.intake as intake_mod

    def _bad_filename(*args, **kwargs):
        return "��-��-回复-2026-07-11-文本反馈.md"

    monkeypatch.setattr(intake_mod, "_build_filename", _bad_filename)

    with pytest.raises(ArchiveCorruptionError):
        asyncio.run(
            archive_inbound_message(
                message=message,
                connector=connector,
                external_docs_root=docs_root,
                queue_path=queue_path,
                department_mapping=MAPPING,
                audit=audit,
            )
        )

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "archive_corruption_detected" in actions
    # 损坏文件不得被后续当成功处理（不追加队列行）
    assert "queue_appended" not in actions


# ── 编辑锁占用时的推迟补录（队列 #168）───────────────────────────────────


def test_archive_defers_queue_append_when_lock_busy(tmp_path):
    """队列文件当前被人类会话持锁编辑时——消息本体仍须正常归档成功，只是
    队列这一行推迟，暂存进 pending_lock_path，不得静默丢失。"""
    docs_root, queue_path, audit, connector, store = _setup(tmp_path)
    pending_lock_path = tmp_path / "pending_lock.jsonl"
    message = InboundMessage(sender="姚祖怡", msgtype="text", text_content="锁占用期间发来的消息")

    result = asyncio.run(
        archive_inbound_message(
            message=message,
            connector=connector,
            external_docs_root=docs_root,
            queue_path=queue_path,
            department_mapping=MAPPING,
            audit=audit,
            queue_lock=FakeQueueEditLock(busy=True),
            pending_lock_path=pending_lock_path,
        )
    )

    # 消息本体已正常归档——不因队列行推迟而受影响。
    assert result.archived_path.exists()
    assert result.archived_path.read_text(encoding="utf-8") == "锁占用期间发来的消息"
    assert result.queue_row is None
    assert result.queue_append_deferred is True

    # 队列文件本身未被改动（没有绕锁写入）。
    assert queue_path.read_text(encoding="utf-8") == QUEUE_TEXT

    # 推迟的追加参数已原样暂存，供下次补录。
    pending = read_deferred_appends(pending_lock_path)
    assert len(pending) == 1
    assert pending[0]["append_kwargs"]["owner"] == "采购专线"
    assert pending[0]["sender"] == "姚祖怡"

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "archived" in actions
    assert "queue_append_deferred_lock_busy" in actions
    assert "queue_appended" not in actions


def test_archive_with_free_lock_appends_normally_and_releases(tmp_path):
    """锁空闲时——归档+队列追加正常完成，且锁被正确 acquire/release。"""
    docs_root, queue_path, audit, connector, store = _setup(tmp_path)
    lock = FakeQueueEditLock(busy=False)
    message = InboundMessage(sender="姚祖怡", msgtype="text", text_content="锁空闲时发来的消息")

    result = asyncio.run(
        archive_inbound_message(
            message=message,
            connector=connector,
            external_docs_root=docs_root,
            queue_path=queue_path,
            department_mapping=MAPPING,
            audit=audit,
            queue_lock=lock,
        )
    )

    assert result.queue_append_deferred is False
    assert result.queue_row is not None
    assert lock.acquire_calls == 1
    assert lock.release_calls == 1
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "queue_appended" in actions
