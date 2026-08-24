"""队列 #387 ⑷⑸：IT 域队列 owner 归属 ＋ 对 Shao Peishen 本人的入站消息
不建队列行。

⑷ 陈承（IT）的来件此前 owner 落 `Paul`，与「发送人根本没命中部门映射」共用
   同一个默认值——读队列的人分不出这一行是「归属明确、只是没配」还是「身份
   都没认出来」。
⑸ Shao Peishen 2026-08-24 拍板：「把对你本人的入站消息直接不建队列行」。
   他是任务的发起方，不是需要被拆件的外部来件；此前每在群里说一句话就产生
   一条待领行，实测已积 15 条、其中 14 条由两班拆件巡逻逐条人工关闭。
"""
import asyncio

from zhuopin_platform.audit import AuditLogger

from aibot_service.constants import PAUL_USERID
from aibot_service.intake import DEPARTMENT_TO_QUEUE_OWNER, archive_inbound_message
from aibot_service.frame_parsing import InboundMessage

QUEUE_TEMPLATE = """# 跨桌任务队列（测试用最小骨架）

> 编号高水位线：#100

## 一、任务看板

| 编号 | 任务 | 领取方 | 输入指针 | 预期产出 | 状态 | 触碰区 | 登记 |
|---|---|---|---|---|---|---|---|
| 100 | 既有行 | Paul | `x` | y | [S:done] |  | 2026-08-01 |

## 二、待 commit 批次

"""


def _queue(tmp_path):
    path = tmp_path / "跨桌任务队列-机制环境.md"
    path.write_text(QUEUE_TEMPLATE, encoding="utf-8")
    return path


def _archive(tmp_path, sender, department_mapping):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    queue_path = _queue(tmp_path)
    result = asyncio.run(
        archive_inbound_message(
            message=InboundMessage(
                sender=sender,
                msgtype="text",
                text_content="测试正文",
                msgid="msg-abc",
                chatid="wrSomeGroup",
                chattype="group",
            ),
            connector=None,
            external_docs_root=tmp_path / "7-外部文档",
            queue_path=queue_path,
            department_mapping=department_mapping,
            audit=audit,
        )
    )
    return result, audit, queue_path


# ── ⑷ IT 域 owner ──────────────────────────────────────────────────────


def test_it_department_has_dedicated_queue_owner():
    """IT 不再回落 `UNMATCHED_QUEUE_OWNER`。"""
    assert DEPARTMENT_TO_QUEUE_OWNER["IT"] == "业务总线"


def test_it_owner_is_not_an_invented_role():
    """🔴 刻意不写 `IT专线` —— 本项目没有这个角色（`whitelist.py` 原文：
    「不臆造一个不存在的『IT专线』角色」）。"""
    assert "IT专线" not in DEPARTMENT_TO_QUEUE_OWNER.values()


def test_it_inbound_row_carries_business_bus_owner(tmp_path):
    result, _audit, queue_path = _archive(tmp_path, "2023458", {"2023458": "IT"})

    assert result.department == "IT"
    assert result.matched is True
    assert result.queue_row is not None
    assert "业务总线" in result.queue_row
    assert "业务总线" in queue_path.read_text(encoding="utf-8")


def test_unmatched_sender_still_falls_back_to_paul(tmp_path):
    """未命中部门映射的回落值不变——⑷ 只补 IT，不动 fail-closed 默认值。"""
    result, _audit, _queue_path = _archive(tmp_path, "nobody", {"2023458": "IT"})

    assert result.matched is False
    assert "Paul" in result.queue_row


# ── ⑸ 本人入站不建队列行 ────────────────────────────────────────────────


def test_own_inbound_message_creates_no_queue_row(tmp_path):
    result, audit, queue_path = _archive(tmp_path, PAUL_USERID, {"2023458": "IT"})

    assert result.queue_row is None
    assert result.queue_append_skipped is True
    # 队列文件一个字都没动
    assert queue_path.read_text(encoding="utf-8") == QUEUE_TEMPLATE

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "queue_append_skipped" in actions
    assert "queue_appended" not in actions

    skipped = [
        r for r in audit.query_by(scenario="wecom-aibot")
        if r["action"] == "queue_append_skipped"
    ]
    assert skipped[0]["decision"]["reason"] == "sender_is_paul"


def test_own_inbound_message_is_still_archived(tmp_path):
    """⚠️ 归档本身保留——留痕一条不丢，不建的只是那条待领行。"""
    result, audit, _queue_path = _archive(tmp_path, PAUL_USERID, {"2023458": "IT"})

    assert result.archived_path.exists()
    assert result.archived_path.read_text(encoding="utf-8") == "测试正文"
    assert "archived" in [r["action"] for r in audit.query_by(scenario="wecom-aibot")]


def test_skipped_is_not_conflated_with_deferred(tmp_path):
    """🔴 `queue_append_skipped` 与 `queue_append_deferred` 是两件不同的事。

    deferred ＝「这一行还欠着，等下次补录」；skipped ＝「这一行本就不该存在」。
    混用会让补录链路去补一条永远不该补的行。
    """
    result, _audit, _queue_path = _archive(tmp_path, PAUL_USERID, {"2023458": "IT"})

    assert result.queue_append_skipped is True
    assert result.queue_append_deferred is False


def test_skip_judgement_matches_forwarding_module(tmp_path):
    """🔴 判据与 `forwarding.py::should_forward` 同源——不新造第二套「谁是
    本人」的判定。两处一旦分叉，就会出现「转发认得他、队列不认得他」这类
    只在特定消息上才暴露的偏差。"""
    from aibot_service.forwarding import should_forward

    msg = InboundMessage(sender=PAUL_USERID, msgtype="text", text_content="x")
    assert should_forward(msg) is False  # 转发侧认定「这是他本人」

    result, _audit, _queue_path = _archive(tmp_path, PAUL_USERID, {})
    assert result.queue_append_skipped is True  # 队列侧同一判定


def test_other_senders_unaffected(tmp_path):
    """回归锁：非本人发送人照常建行。"""
    result, audit, _queue_path = _archive(tmp_path, "tangyanping", {"tangyanping": "财务部"})

    assert result.queue_append_skipped is False
    assert result.queue_row is not None
    assert "财务专线" in result.queue_row
    assert "queue_appended" in [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
