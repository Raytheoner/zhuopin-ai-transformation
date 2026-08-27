"""`delivery.push_followup` 的长度守卫接线（队列 #416，`OP-0828-B`）。

本文件只钉三件事，且每一件都对应一个真实失效模式：
⑴ **超限即干净失败**——一条都没发、README 一字未改、审计与事实一致、可安全重试；
⑵ **三条通道发的是同一份**——不许出现「私信全文、群里提要」或「私信成功、
   群里什么都没有」；
⑶ **限内行为逐字不变**——守卫上线不得改变今天发得出去的那些信。
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector

from aibot_service.constants import PAUL_USERID
from aibot_service.delivery import push_followup
from aibot_service.message_length import CC_PREFIX, OversizedMessageError, measure

from fakes import fake_client_factory

README_TEXT = """\
## 现有跟进信清单

| 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |
|------|--------|---------|---------|---------|
| 2026-08-28 | 采购部 · 姚祖怡 | 判例批改表 | 方便时回 | 🆕 待发 |
"""

_FILLER = "正文若干，这里刻意写长一点，好让整封信超过测试里设的上限。" * 20

LONG_LETTER = f"""\
# 采购部#19 · 六件一次问齐

## 一、判例表 A

{_FILLER}

## 二、责任人列请你改选

{_FILLER}
"""

SHORT_LETTER = "# 采购部#20 · 一句话\n\n祖怡，方便时回一句。\n"


def _match(cells):
    return "判例批改表" in cells[2]


def _setup(tmp_path: Path, letter: str, with_docx: bool = True):
    readme_path = tmp_path / "README.md"
    readme_path.write_text(README_TEXT, encoding="utf-8")
    md_path = tmp_path / "letter.md"
    md_path.write_text(letter, encoding="utf-8")
    docx_path = None
    if with_docx:
        docx_path = tmp_path / "letter.docx"
        docx_path.write_bytes(b"fake docx bytes")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}
    connector = AibotConnector("bot", "secret", client_factory=fake_client_factory(store))
    client = store["client"]
    client.raw_frame_responses["aibot_upload_media_init"] = [{"body": {"upload_id": "U1"}}]
    client.raw_frame_responses["aibot_upload_media_chunk"] = [{"errcode": 0}]
    client.raw_frame_responses["aibot_upload_media_finish"] = [{"body": {"media_id": "M1"}}]
    return readme_path, md_path, docx_path, audit, connector, store


def _markdown_sends(store) -> list[tuple[str, str]]:
    return [
        (chatid, body["markdown"]["content"])
        for chatid, body in store["client"].sent_messages
        if body.get("msgtype") == "markdown"
    ]


def test_within_limit_behaviour_is_byte_identical(tmp_path, monkeypatch):
    """限内不降级——守卫上线不得改变今天正常那些信的任何一个字节。"""
    monkeypatch.setenv("WECOM_AIBOT_MARKDOWN_MAX_BYTES", "14000")
    readme_path, md_path, docx_path, audit, connector, store = _setup(tmp_path, SHORT_LETTER)

    asyncio.run(push_followup(
        readme_path=readme_path, md_path=md_path, docx_path=docx_path,
        connector=connector, chatid="chat-1", match=_match, audit=audit,
        cc_group_chatid="group-1",
    ))

    sends = _markdown_sends(store)
    assert sends[0] == ("chat-1", SHORT_LETTER)
    assert sends[1] == (PAUL_USERID, CC_PREFIX + SHORT_LETTER)
    assert sends[2] == ("group-1", CC_PREFIX + SHORT_LETTER)

    delivered = [r for r in audit.query_by(scenario="wecom-aibot")
                 if r["action"] == "followup_delivered"][0]
    assert delivered["decision"]["length_guard"]["degraded"] is False


def test_over_limit_degrades_and_all_three_channels_get_the_same_body(tmp_path, monkeypatch):
    """🔴 三条通道必须发同一份——错位才是最难发现的那种失败。"""
    monkeypatch.setenv("WECOM_AIBOT_MARKDOWN_MAX_BYTES", "900")
    readme_path, md_path, docx_path, audit, connector, store = _setup(tmp_path, LONG_LETTER)

    asyncio.run(push_followup(
        readme_path=readme_path, md_path=md_path, docx_path=docx_path,
        connector=connector, chatid="chat-1", match=_match, audit=audit,
        cc_group_chatid="group-1",
    ))

    sends = _markdown_sends(store)
    assert len(sends) == 3
    private_body = sends[0][1]
    assert sends[1][1] == CC_PREFIX + private_body
    assert sends[2][1] == CC_PREFIX + private_body
    assert private_body != LONG_LETTER
    assert "只是提要，不是完整正文" in private_body
    assert "letter.docx" in private_body
    # 每一条实际外发串都在限内——含加了前缀的那两条。
    assert all(measure(body) <= 900 for _, body in sends)

    # 附件照发、README 照回填：降级只降正文，不降交付。
    assert any(b.get("msgtype") == "file" for _, b in store["client"].sent_messages)
    assert "✅ 已推送" in readme_path.read_text(encoding="utf-8")

    guard = [r for r in audit.query_by(scenario="wecom-aibot")
             if r["action"] == "followup_delivered"][0]["decision"]["length_guard"]
    assert guard["degraded"] is True
    assert guard["original_bytes"] == measure(LONG_LETTER)
    assert set(guard["channels"]) == {"私信", "抄送ShaoPeiShen", "群抄送"}


def test_cc_prefix_pushes_a_borderline_letter_over_and_guard_catches_it(tmp_path, monkeypatch):
    """🔴 正文刚好在限内、加 `【抄送】` 后超限 —— 只验私信侧会漏掉的正是这种。

    守卫若只按原文算，这一封会「私信成功、抄送两条静默失败」。
    """
    letter = "# T\n\n" + "啊" * 400
    monkeypatch.setenv("WECOM_AIBOT_MARKDOWN_MAX_BYTES", str(measure(letter)))
    readme_path, md_path, docx_path, audit, connector, store = _setup(tmp_path, letter)

    asyncio.run(push_followup(
        readme_path=readme_path, md_path=md_path, docx_path=docx_path,
        connector=connector, chatid="chat-1", match=_match, audit=audit,
        cc_group_chatid="group-1",
    ))

    sends = _markdown_sends(store)
    assert sends[0][1] != letter, "加了抄送前缀后已超限，本封必须降级"
    assert all(measure(body) <= measure(letter) for _, body in sends)


def test_no_cc_means_borderline_letter_is_sent_as_is(tmp_path, monkeypatch):
    """反面：同一封信不抄送时不该被降级——守卫不得对着原文瞎保守。"""
    letter = "# T\n\n" + "啊" * 400
    monkeypatch.setenv("WECOM_AIBOT_MARKDOWN_MAX_BYTES", str(measure(letter)))
    readme_path, md_path, docx_path, audit, connector, store = _setup(tmp_path, letter)

    asyncio.run(push_followup(
        readme_path=readme_path, md_path=md_path, docx_path=docx_path,
        connector=connector, chatid="chat-1", match=_match, audit=audit,
        cc_to_paul=False,
    ))

    assert _markdown_sends(store)[0][1] == letter


def test_oversized_without_attachment_fails_cleanly_nothing_sent(tmp_path, monkeypatch):
    """🔴 本文件最要紧的一条：失败必须是**干净**的。

    `#416` 那次失败之所以「值得保住」，是因为 `sent:False／acks:[]／
    media_ids:[]／backfilled:False` 与 README 状态一致 ⇒ 可安全重试、
    不会触发次日 09:30 重发。修复不得把它改成「半发」。
    """
    monkeypatch.setenv("WECOM_AIBOT_MARKDOWN_MAX_BYTES", "900")
    readme_path, md_path, _, audit, connector, store = _setup(
        tmp_path, LONG_LETTER, with_docx=False)

    with pytest.raises(OversizedMessageError):
        asyncio.run(push_followup(
            readme_path=readme_path, md_path=md_path, docx_path=None,
            connector=connector, chatid="chat-1", match=_match, audit=audit,
            cc_group_chatid="group-1",
        ))

    # ① 一条都没发（正文、附件、抄送，一个字节都没出去）
    assert store["client"].sent_messages == []
    # ② README 一字未改，仍是「🆕 待发」，可安全重试
    assert readme_path.read_text(encoding="utf-8") == README_TEXT
    # ③ 审计与事实一致
    records = audit.query_by(scenario="wecom-aibot")
    actions = [r["action"] for r in records]
    assert "followup_delivery_failed" in actions
    assert "followup_delivered" not in actions
    assert "followup_backfilled" not in actions
    failed = [r for r in records if r["action"] == "followup_delivery_failed"][0]
    assert failed["decision"]["sent"] is False
    assert failed["decision"]["backfilled"] is False
    assert failed["decision"]["acks"] == []
    assert failed["decision"]["media_ids"] == []
