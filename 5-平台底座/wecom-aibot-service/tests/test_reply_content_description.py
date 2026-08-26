"""队列 #416 ⑷⑸：转发的内容描述 ＋ 归档文件名带跟进信编号。

素材取自 2026-08-26 的**真实**回件（唐燕萍那份 43,657 B 的 docx）与 08-24
那条被 Shao Peishen 当作"老格式"的真实文本归档件，只读演练、不发任何真实消息。
"""
from __future__ import annotations

import asyncio

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools import followup_gate as fg
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector

from aibot_service import followup_readme_bridge as bridge
from aibot_service.constants import PAUL_USERID
from aibot_service.forwarding import (
    build_forward_description,
    forward_inbound_to_paul,
    render_letter_number,
)
from aibot_service.frame_parsing import InboundMessage
from aibot_service.intake import _build_filename, archive_inbound_message

from fakes import fake_client_factory

# 真实回传文件名（专员自己起的名字），08-24 那条描述里《…》内的正是它。
REAL_HINT = "财务部-唐燕萍-跟进-2026-08-23-起点反转方案已定稿与两处口径请裁-回复.docx"
README_HEADER = (
    "## 现有跟进信清单\n\n"
    "| 编号 | 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态 |\n"
    "|---|---|---|---|---|---|\n"
)
LETTER_FILE = "财务部-唐燕萍-跟进-2026-08-23-起点反转方案已定稿与两处口径请裁.md"


def _write_readme(repo_root, status="✅ 已发出 2026-08-23"):
    path = repo_root / bridge.FOLLOWUP_README_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        README_HEADER
        + f"| 财务部#15 | 2026-08-23 | 财务部 · 唐燕萍 | 起点反转方案 → "
          f"目标文件：`{LETTER_FILE}` | 尽快 | {status} |\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------- ⑸ 文件名带编号

def test_letter_number_segment_lands_before_the_date():
    """🔴 编号**不能**追在末尾——`<topic>` 是贪婪的 `.+`，会把它吞掉。"""
    name = _build_filename(
        "财务部", "tangyanping", "2026-08-26", "某主题-回复", ".docx", "b815d4d1",
        letter_number="财务部#15",
    )
    assert name == "财务部-tangyanping-回复-财务部#15-2026-08-26-某主题-回复-b815d4d1.docx"
    # 编号进去之后，stem 逐字比对**照样**认得原信主题（否则 README 配不上）。
    assert fg.extract_reply_source_stem(name) == "某主题-回复"
    assert fg.extract_letter_number(name) == "财务部#15"


def test_old_filenames_without_number_still_parse():
    """已归档的历史件零影响——编号段是可选的。"""
    old = "采购部-YaoZuYi-回复-2026-08-21-采购部-姚祖怡-跟进-2026-08-20-SC2判例-0d6acc8a.docx"
    assert fg.extract_reply_source_stem(old) == "采购部-姚祖怡-跟进-2026-08-20-SC2判例"
    assert fg.extract_letter_number(old) is None


def test_resolve_letter_number_reads_readme_readonly(tmp_path):
    readme = _write_readme(tmp_path)
    before = readme.read_text(encoding="utf-8")
    prospective = _build_filename(
        "财务部", "tangyanping", "2026-08-26",
        "财务部-唐燕萍-跟进-2026-08-23-起点反转方案已定稿与两处口径请裁-回复",
        ".docx", "b815d4d1",
    )

    number = bridge.resolve_letter_number(
        archived_filename=prospective, repo_root=tmp_path, department="财务部",
    )

    assert number == "财务部#15"
    assert readme.read_text(encoding="utf-8") == before   # 只读，一个字节都不动


def test_resolve_letter_number_returns_none_and_never_raises(tmp_path):
    """README 不存在 ⇒ None，**不抛**——拿不到编号是"文件名少一段"，不是归档失败。"""
    assert bridge.resolve_letter_number(
        archived_filename="随便什么.docx", repo_root=tmp_path, department="财务部",
    ) is None


def test_archive_file_message_writes_number_into_filename(tmp_path):
    _write_readme(tmp_path)
    docs_root = tmp_path / "7-外部文档"
    queue_path = tmp_path / "queue.md"
    queue_path.write_text(
        "## 一、任务看板\n\n| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|---|---|---|---|---|---|---|\n| 1 | x | CC | p | e | 待领 | — | 08-26 |\n",
        encoding="utf-8",
    )
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}
    connector = AibotConnector("bot", "secret", client_factory=fake_client_factory(store))
    store["client"].download_response = (b"PK\x03\x04fake-docx", REAL_HINT)
    message = InboundMessage(
        sender="tangyanping", msgtype="file", file_url="https://x/f",
        file_name_hint=REAL_HINT, msgid="b815d4d1",
    )

    result = asyncio.run(archive_inbound_message(
        message=message, connector=connector, external_docs_root=docs_root,
        queue_path=queue_path, department_mapping={"tangyanping": "财务部"}, audit=audit,
        letter_number_resolver=lambda name, dept: bridge.resolve_letter_number(
            archived_filename=name, repo_root=tmp_path, department=dept,
        ),
    ))

    assert result.letter_number == "财务部#15"
    assert "财务部#15" in result.archived_path.name
    assert result.archived_path.exists()
    archived = [e for e in audit.query_by(scenario="wecom-aibot") if e["action"] == "archived"][0]
    assert archived["decision"]["letter_number"] == "财务部#15"


# ---------------------------------------------------------------- ⑷ 内容描述

def test_render_letter_number_matches_the_08_24_wording():
    assert render_letter_number("财务部#15") == "财务部跟进信第 15 封"
    assert render_letter_number(None) is None
    assert render_letter_number("形态不对") == "形态不对"    # 不猜，原样返回


def test_file_description_restores_the_08_24_full_sentence():
    message = InboundMessage(sender="tangyanping", msgtype="file", file_name_hint=REAL_HINT)

    text = build_forward_description(
        message, letter_number="财务部#15",
        archived_filename="财务部-tangyanping-回复-财务部#15-2026-08-26-x-b815d4d1.docx",
    )

    # 分得出是文档还是文字（旧实现三行头部里没有这一项）
    assert "📎 文档附件（.docx）" in text
    # 08-24 那句话的三个要件：附件标题《…》、回的是哪一封、详见附件
    assert "《财务部-唐燕萍-跟进-2026-08-23-起点反转方案已定稿与两处口径请裁-回复》" in text
    assert "是对你上次发我的「财务部跟进信第 15 封」的回信" in text
    assert "详见附件" in text


def test_text_description_says_it_is_text_and_carries_a_summary():
    message = InboundMessage(
        sender="tangyanping", msgtype="text",
        text_content="两处口径我都认了，按你写的第二版执行，另外第 3 条需要再确认一下时点。",
    )

    text = build_forward_description(message, letter_number="财务部#15")

    assert "💬 文字回复" in text
    assert "财务部跟进信第 15 封" in text
    assert "摘要：两处口径我都认了" in text


def test_supplement_reply_reports_position_without_asserting_it_is_the_reply():
    """🔴 2026-08-26 那份真实补件：README 明写「勿配财务部#15、归补件行」
    （已知误配缺陷 #366 M6）⇒ 描述只报位置，**不把已知可能错的归属写成
    肯定句**。"""
    message = InboundMessage(
        sender="tangyanping", msgtype="file",
        file_name_hint="财务部-唐燕萍-补件-2026-08-25-面板已修复可采信与R5分母请签认一句-回复.docx",
    )

    text = build_forward_description(message, letter_number="财务部#15", is_supplement=True)

    assert "落在「财务部跟进信第 15 封」之后" in text
    assert "闭环后的补充说明" in text
    assert "人工确认" in text
    assert "的回信" not in text          # 断言句必须消失


def test_supplement_number_still_resolved_for_the_filename(tmp_path):
    """⑸ 在补件档上**必须照样出编号**——那正是队列行点名的那条审计事实
    （`followup_readme_bridge_supplement_after_closed` 已经拿到了它）。
    只认 `outcome.matched` 会让本条修复恰好在它要修的案例上失效。"""
    _write_readme(tmp_path, status="✅ 已闭环 2026-08-24 回件已回灌")
    prospective = _build_filename(
        "财务部", "tangyanping", "2026-08-26", "某补件-回复", ".docx", "b815d4d1",
    )

    assert bridge.resolve_letter_number(
        archived_filename=prospective, repo_root=tmp_path, department="财务部",
    ) == "财务部#15"


def test_description_is_fail_loud_when_letter_cannot_be_paired():
    """🔴 配不上就明说配不上，**不编一个编号**。"""
    message = InboundMessage(sender="ChenChen", msgtype="file", file_name_hint="随手一份.docx")

    text = build_forward_description(message, letter_number=None)

    assert "未能确定它回的是哪一封跟进信" in text
    assert "#" not in text


def test_forward_sends_description_and_records_letter_number(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}
    connector = AibotConnector("bot", "secret", client_factory=fake_client_factory(store))
    store["client"].download_response = (b"bin", REAL_HINT)
    store["client"].raw_frame_responses["aibot_upload_media_init"] = [{"body": {"upload_id": "U1"}}]
    store["client"].raw_frame_responses["aibot_upload_media_finish"] = [{"body": {"media_id": "M1"}}]
    message = InboundMessage(
        sender="tangyanping", msgtype="file", file_url="https://x/f", file_name_hint=REAL_HINT,
    )

    asyncio.run(forward_inbound_to_paul(
        frame={"body": {"chattype": "group", "chatid": "wrvDL_x"}},
        message=message, connector=connector, audit=audit,
        letter_number="财务部#15",
        archived_filename="财务部-tangyanping-回复-财务部#15-2026-08-26-x-b815d4d1.docx",
    ))

    chatid, body = store["client"].sent_messages[0]
    content = body["markdown"]["content"]
    assert chatid == PAUL_USERID
    assert "发件人：tangyanping" in content          # 三行头部照旧
    assert "📎 文档附件" in content                   # ⑷ 新增：类型
    assert "财务部跟进信第 15 封" in content          # ⑷ 新增：回的是哪一封
    forwarded = [e for e in audit.query_by(scenario="wecom-aibot")
                 if e["action"] == "inbound_forwarded_to_paul"][0]
    assert forwarded["decision"]["letter_number"] == "财务部#15"


def test_forward_text_keeps_original_content_verbatim(tmp_path):
    """摘要只是入口——原文一字不改地跟在后面。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}
    connector = AibotConnector("bot", "secret", client_factory=fake_client_factory(store))
    original = "两处口径我都认了" * 20
    message = InboundMessage(sender="tangyanping", msgtype="text", text_content=original)

    asyncio.run(forward_inbound_to_paul(
        frame={"body": {"chattype": "single"}}, message=message,
        connector=connector, audit=audit, letter_number="财务部#15",
    ))

    content = store["client"].sent_messages[0][1]["markdown"]["content"]
    assert original in content
    assert "———— 原文 ————" in content
