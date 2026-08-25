"""队列 #399（followup-supplement-channel）＋ 并入的 #400 —— 补件通道端到端。

覆盖 §四 #119 六点里落在服务侧的四点：
- ①(a) 补件住在 README 内**独立第二张表**，主表消费者结构性读不到它；
- ③(b) 班次 MUST NOT 发补件，但**每轮必须显式报出补件表行数**（含 0 行、含 dry-run）；
- ④(b) 补件复用闭环四态 ＋ 「需回复」显式列决定回填哪个终态；
- ⑥(b) 审计并回正式 action 名，靠 `decision.kind="supplement"` 区分。
外加 #400：批准转终态时**同一次写入**剥除编号列括注（含变异验证与幂等）。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector

from aibot_service.approval import (
    SupplementReplyRequiredMissingError,
    approve_followup_letter,
)
from aibot_service.delivery import (
    DELIVERED_STATUS_PREFIX,
    push_followup,
    resolve_backfill_status,
)
from aibot_service.dispatch import summarize_supplement_table
from aibot_service.readme_table import (
    MAIN_TABLE_SECTION,
    NO_REPLY_NEEDED_STATUS,
    SUPPLEMENT_TABLE_SECTION,
    ReadmeTableError,
    iter_rows,
    locate_row,
    strip_unnumbered_annotation,
    write_cells,
)

from fakes import fake_client_factory

NOW = datetime(2026, 8, 25, 3, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(minutes=30)

# `采购部#18` 用的是 2026-08-25 队列 #400 行内记录的**真实两格**。
MAIN_BLOCK = """\
## 现有跟进信清单

| 编号 | 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |
|------|------|--------|---------|---------|---------|
| 财务部#15 | 2026-08-23 | 财务部 · 唐燕萍 | FI2 面板复核 | 尽快 | ✅ 已推送 2026-08-23 08:26 UTC |
| 采购部#18（待你审，暂不占号） | 2026-08-24 | 采购部 · 姚祖怡 | 判例批改表 | 8 月内 | ⏳ 待你审 |
"""

SUPPLEMENT_BLOCK = """\
## 补件登记（不占编号、不占串行闸，2026-08-24 立表）

| 承接编号 | 日期 | 收信人 | 主要事项 | 需回复 | 发送状态 |
|---------|------|--------|---------|--------|---------|
| 财务部#15 | 2026-08-25 | 财务部 · 唐燕萍 | 面板已修复可采信 | 否 | ⏳ 待你审 |
| 财务部#15 | 2026-08-25 | 财务部 · 唐燕萍 | R5 分母请签认一句 | 是 | ⏳ 待你审 |
| 财务部#15 | 2026-08-25 | 财务部 · 唐燕萍 | 需回复列忘了填 |  | ⏳ 待你审 |
"""

README_TEXT = MAIN_BLOCK + "\n" + SUPPLEMENT_BLOCK


def _setup(tmp_path, readme_text=README_TEXT):
    readme_path = tmp_path / "README.md"
    readme_path.write_text(readme_text, encoding="utf-8")
    return (
        readme_path,
        AuditLogger.jsonl(tmp_path / "audit.jsonl"),
        tmp_path / "cooldown_state.json",
    )


def _approve(readme_path, audit, cooldown, match, section, now=LATER):
    """批准须走两次调用（冷却窗口：首调只记观测时刻并拒绝）——补件与正式信
    **同规**，这正是 spec「MUST NOT 为补件放宽其中任何一条」那句。"""
    from aibot_service.approval import ApprovalCooldownError

    with pytest.raises(ApprovalCooldownError):
        approve_followup_letter(
            readme_path=readme_path, match=match, quote="Shao Peishen: 发",
            audit=audit, cooldown_state_path=cooldown, now=NOW, section=section,
        )
    return approve_followup_letter(
        readme_path=readme_path, match=match, quote="Shao Peishen: 发",
        audit=audit, cooldown_state_path=cooldown, now=now, section=section,
    )


# ------------------------------------------------- ①(a) 载体隔离是结构性的

def test_主表消费者读不到补件行():
    main_rows = iter_rows(README_TEXT)
    assert len(main_rows) == 2
    assert all("补件" not in c for r in main_rows for c in r.cells)


def test_补件表存在与否不改变主表读数():
    assert [r.cells for r in iter_rows(MAIN_BLOCK)] == [
        r.cells for r in iter_rows(README_TEXT)
    ]


def test_补件表首列不叫编号():
    """免疫来自「读不到那张表」，而列名不同又多挡一层：任何按「编号」找列的
    代码在补件表上都会取不到，而不是取到一个看起来像编号的值。"""
    rows = iter_rows(README_TEXT, SUPPLEMENT_TABLE_SECTION)
    assert rows[0].header_cells[0] == "承接编号"


# ---------------------------------------- ③(b) 班次不发补件，但必须出声

def test_班次摘要在有待发补件时报出行数(tmp_path):
    text = README_TEXT.replace("| 面板已修复可采信 | 否 | ⏳ 待你审 |",
                               "| 面板已修复可采信 | 否 | 🆕 待发 |")
    note = summarize_supplement_table(text)
    assert "共 3 行" in note
    assert "1 行" in note
    assert "不自动发送" in note


def test_班次摘要在零行待发时同样报出():
    """🔴 **沉默不算通过**——0 行也必须打印。#399 之所以能藏住整整一天，正是
    因为班次对补件的沉默与「今天没活」在输出上逐字相同。"""
    note = summarize_supplement_table(README_TEXT)
    assert "共 3 行" in note
    assert "」0 行" in note


def test_补件表读不到时摘要也出声而不是装作没有():
    note = summarize_supplement_table(MAIN_BLOCK)
    assert "读不到" in note


def test_摘要不因主表无待发而缺席():
    """`dispatch_followup_letters` 在主表零行时提前 return——摘要必须在那个
    return **之前**算好。这条锁的就是「主表没活所以整轮沉默」这个形态。"""
    from aibot_service.dispatch import DispatchOutcome

    assert DispatchOutcome().supplement_note == ""  # 默认值即空串、非 None
    empty_main = (
        "## 现有跟进信清单\n\n"
        "| 编号 | 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态 |\n"
        "|------|------|--------|---------|---------|---------|\n"
        "\n" + SUPPLEMENT_BLOCK
    )
    assert iter_rows(empty_main) == []
    assert "共 3 行" in summarize_supplement_table(empty_main)


# ------------------------------------------------ ④(b) 需回复列与终态语义

def test_通知型补件发出即置无需回复():
    loc = locate_row(README_TEXT, lambda c: "面板已修复可采信" in c[3],
                     SUPPLEMENT_TABLE_SECTION)
    assert resolve_backfill_status(loc, SUPPLEMENT_TABLE_SECTION, "2026-08-25") == (
        NO_REPLY_NEEDED_STATUS
    )


def test_签认型补件发出后仍在途():
    loc = locate_row(README_TEXT, lambda c: "R5 分母请签认" in c[3],
                     SUPPLEMENT_TABLE_SECTION)
    status = resolve_backfill_status(loc, SUPPLEMENT_TABLE_SECTION, "2026-08-25")
    assert status.startswith(DELIVERED_STATUS_PREFIX)


def test_需回复列读不到时按签认型处理():
    """两个方向代价不对称：误判成通知型会把一封还在等签认的补件直接标成
    「已了结」，那个签认从此在任何机器载体上都无迹可寻。"""
    loc = locate_row(README_TEXT, lambda c: "需回复列忘了填" in c[3],
                     SUPPLEMENT_TABLE_SECTION)
    assert resolve_backfill_status(loc, SUPPLEMENT_TABLE_SECTION, "x").startswith(
        DELIVERED_STATUS_PREFIX)


def test_主表回填语义未变():
    loc = locate_row(README_TEXT, lambda c: "FI2 面板复核" in c[3])
    assert resolve_backfill_status(loc, MAIN_TABLE_SECTION, "T") == (
        f"{DELIVERED_STATUS_PREFIX} T")


def test_需回复列为空则拒绝批准且不改文件(tmp_path):
    readme_path, audit, cooldown = _setup(tmp_path)
    before = readme_path.read_text(encoding="utf-8")
    with pytest.raises(SupplementReplyRequiredMissingError):
        approve_followup_letter(
            readme_path=readme_path, match=lambda c: "需回复列忘了填" in c[3],
            quote="Shao Peishen: 发", audit=audit,
            cooldown_state_path=cooldown, now=NOW,
            section=SUPPLEMENT_TABLE_SECTION,
        )
    assert readme_path.read_text(encoding="utf-8") == before
    events = list(audit.query_by(scenario="wecom-aibot"))
    assert events[-1]["action"] == "followup_approval_rejected"
    assert events[-1]["decision"]["reason"] == "supplement_reply_required_missing"


def test_需回复列为空时不启动冷却计时器(tmp_path):
    """内容本身就不合法的补件不该先把冷却窗口跑起来，否则修好内容还得再等
    一轮——判据放在冷却之前正是为此。"""
    readme_path, audit, cooldown = _setup(tmp_path)
    with pytest.raises(SupplementReplyRequiredMissingError):
        approve_followup_letter(
            readme_path=readme_path, match=lambda c: "需回复列忘了填" in c[3],
            quote="q", audit=audit, cooldown_state_path=cooldown, now=NOW,
            section=SUPPLEMENT_TABLE_SECTION,
        )
    assert not cooldown.exists()


# ------------------------------------------ 批准路径覆盖补件表（review-state）

def test_补件行可被批准且复用同一条判据链(tmp_path):
    readme_path, audit, cooldown = _setup(tmp_path)
    result = _approve(readme_path, audit, cooldown,
                      lambda c: "面板已修复可采信" in c[3], SUPPLEMENT_TABLE_SECTION)
    assert result.new_status == "🆕 待发"
    rows = iter_rows(readme_path.read_text(encoding="utf-8"), SUPPLEMENT_TABLE_SECTION)
    assert rows[0].cells[-1] == "🆕 待发"
    approved = [r for r in audit.query_by(scenario="wecom-aibot")
                if r["action"] == "followup_approved"]
    assert approved[-1]["decision"]["kind"] == "supplement"


def test_批准补件不动主表(tmp_path):
    readme_path, audit, cooldown = _setup(tmp_path)
    _approve(readme_path, audit, cooldown,
             lambda c: "面板已修复可采信" in c[3], SUPPLEMENT_TABLE_SECTION)
    assert [r.cells for r in iter_rows(readme_path.read_text(encoding="utf-8"))] == [
        r.cells for r in iter_rows(README_TEXT)
    ]


def test_补件行的承接编号列不被剥括注(tmp_path):
    readme_path, audit, cooldown = _setup(tmp_path)
    _approve(readme_path, audit, cooldown,
             lambda c: "面板已修复可采信" in c[3], SUPPLEMENT_TABLE_SECTION)
    rows = iter_rows(readme_path.read_text(encoding="utf-8"), SUPPLEMENT_TABLE_SECTION)
    assert rows[0].cells[0] == "财务部#15"


def test_指定不存在的表时报错而不是落到另一张表(tmp_path):
    readme_path, audit, cooldown = _setup(tmp_path, MAIN_BLOCK)
    with pytest.raises(ReadmeTableError):
        approve_followup_letter(
            readme_path=readme_path, match=lambda c: True, quote="q", audit=audit,
            cooldown_state_path=cooldown, now=NOW, section=SUPPLEMENT_TABLE_SECTION,
        )


# ------------------------------------------------------ #400 编号列剥括注

def test_剥括注只剥括注不改编号数值():
    assert strip_unnumbered_annotation("采购部#18（待你审，暂不占号）") == "采购部#18"


def test_剥括注幂等():
    once = strip_unnumbered_annotation("采购部#18（待你审，暂不占号）")
    assert strip_unnumbered_annotation(once) == once == "采购部#18"


def test_无编号数值的单元格不动():
    """`销售部（未发，不编号）` 的括注是该格**仅有的信息**，剥掉只会留下一个
    失去含义的 `销售部`。本要求修的是「编号已存在、括注却还说没发」。"""
    assert strip_unnumbered_annotation("销售部（未发，不编号）") == "销售部（未发，不编号）"


def test_与未发无关的括注不被误剥():
    assert strip_unnumbered_annotation("采购部#18（含附件两份）") == "采购部#18（含附件两份）"


def test_采购部18真实两格喂新判据必须产生一次修改(tmp_path):
    """🔴 design §四 的变异验证要求（tasks 3.6）：把 `采购部#18` **当前的真实
    两格**喂给新判据，**必须**产生一次修改；剥完再喂一次，**必须**幂等无修改。"""
    readme_path, audit, cooldown = _setup(tmp_path)
    before = locate_row(README_TEXT, lambda c: "判例批改表" in c[3])
    assert before.cells[0] == "采购部#18（待你审，暂不占号）"

    _approve(readme_path, audit, cooldown, lambda c: "判例批改表" in c[3],
             MAIN_TABLE_SECTION)
    after = locate_row(readme_path.read_text(encoding="utf-8"),
                       lambda c: "判例批改表" in c[3])
    assert after.cells[0] == "采购部#18", "第一次必须产生修改"
    assert after.cells[-1] == "🆕 待发"

    # 幂等：再剥一次不产生任何修改。
    assert strip_unnumbered_annotation(after.cells[0]) == after.cells[0]


def test_剥括注与转终态必须是同一次写入():
    """🔴 分两次写就多出一个「状态改了、括注没改」的中间态——**而那正是 #400
    这个缺陷本身**。故本仓库不提供「只改状态」的中间产物：两格由 `write_cells`
    一次写出，中间态在实现上无处产生。"""
    loc = locate_row(README_TEXT, lambda c: "判例批改表" in c[3])
    out = write_cells(README_TEXT, loc, {
        loc.status_col_index: "🆕 待发",
        0: strip_unnumbered_annotation(loc.cells[0]),
    })
    row = [ln for ln in out.splitlines() if "判例批改表" in ln]
    assert len(row) == 1
    assert "采购部#18 |" in row[0] and "🆕 待发" in row[0]
    assert "暂不占号" not in out


def test_编号数值不因批准而重新分配(tmp_path):
    readme_path, audit, cooldown = _setup(tmp_path)
    _approve(readme_path, audit, cooldown, lambda c: "判例批改表" in c[3],
             MAIN_TABLE_SECTION)
    assert "采购部#18" in readme_path.read_text(encoding="utf-8")
    assert "采购部#19" not in readme_path.read_text(encoding="utf-8")


def test_无括注时编号列一字不变(tmp_path):
    text = README_TEXT.replace("采购部#18（待你审，暂不占号）", "采购部#18")
    readme_path, audit, cooldown = _setup(tmp_path, text)
    _approve(readme_path, audit, cooldown, lambda c: "判例批改表" in c[3],
             MAIN_TABLE_SECTION)
    after = locate_row(readme_path.read_text(encoding="utf-8"),
                       lambda c: "判例批改表" in c[3])
    assert after.cells[0] == "采购部#18"
    approved = [r for r in audit.query_by(scenario="wecom-aibot")
                if r["action"] == "followup_approved"]
    assert approved[-1]["decision"]["number_annotation_stripped"] is False


def test_审计记下编号列前后值(tmp_path):
    """只写「已批准」而不写编号列前后值，事后无从复核那一格有没有跟着变。"""
    readme_path, audit, cooldown = _setup(tmp_path)
    _approve(readme_path, audit, cooldown, lambda c: "判例批改表" in c[3],
             MAIN_TABLE_SECTION)
    approved = [r for r in audit.query_by(scenario="wecom-aibot")
                if r["action"] == "followup_approved"][-1]
    assert approved["decision"]["number_before"] == "采购部#18（待你审，暂不占号）"
    assert approved["decision"]["number_after"] == "采购部#18"
    assert approved["decision"]["number_annotation_stripped"] is True
    assert approved["decision"]["kind"] == "letter"


# --------------------------------- ⑥(b) 审计并回正式 action 名 ＋ 终态回填

def _push_setup(tmp_path, readme_text=README_TEXT):
    readme_path = tmp_path / "README.md"
    readme_path.write_text(readme_text, encoding="utf-8")
    md_path = tmp_path / "letter.md"
    md_path.write_text("正文：面板已修复，可恢复采信。", encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}
    connector = AibotConnector("bot", "secret", client_factory=fake_client_factory(store))
    return readme_path, md_path, audit, connector


def _push(readme_path, md_path, audit, connector, match, section):
    text = readme_path.read_text(encoding="utf-8")
    loc = locate_row(text, match, section)
    readme_path.write_text(write_cells(text, loc, {loc.status_col_index: "🆕 待发"}),
                           encoding="utf-8")
    return asyncio.run(push_followup(
        readme_path=readme_path, md_path=md_path, docx_path=None,
        connector=connector, chatid="chat-tang", match=match, audit=audit,
        cc_to_paul=False, section=section,
    ))


def test_补件发送记正式action名并以kind区分(tmp_path):
    """决策点 6(b)：**审计是给事后复核「这个人收到过什么」用的**，按「用什么
    脚本发的」分家会逼复核者先懂实现细节。故并回 `followup_delivered`。"""
    readme_path, md_path, audit, connector = _push_setup(tmp_path)
    _push(readme_path, md_path, audit, connector,
          lambda c: "面板已修复可采信" in c[3], SUPPLEMENT_TABLE_SECTION)
    events = list(audit.query_by(scenario="wecom-aibot"))
    delivered = [e for e in events if e["action"] == "followup_delivered"]
    assert len(delivered) == 1, "补件必须记正式 action 名，不另起 supplement_* 前缀"
    assert delivered[0]["decision"]["kind"] == "supplement"
    assert not any(e["action"].startswith("supplement_") for e in events)


def test_按正式action名查收信人去件时补件也在结果里(tmp_path):
    readme_path, md_path, audit, connector = _push_setup(tmp_path)
    _push(readme_path, md_path, audit, connector,
          lambda c: "FI2 面板复核" in c[3], MAIN_TABLE_SECTION)
    _push(readme_path, md_path, audit, connector,
          lambda c: "面板已修复可采信" in c[3], SUPPLEMENT_TABLE_SECTION)
    delivered = [e for e in audit.query_by(scenario="wecom-aibot")
                 if e["action"] == "followup_delivered"]
    assert len(delivered) == 2, "一条时间线，不漏查"
    assert {e["decision"]["kind"] for e in delivered} == {"letter", "supplement"}


def test_通知型补件推送后回填无需回复(tmp_path):
    readme_path, md_path, audit, connector = _push_setup(tmp_path)
    result = _push(readme_path, md_path, audit, connector,
                   lambda c: "面板已修复可采信" in c[3], SUPPLEMENT_TABLE_SECTION)
    assert result.new_status == NO_REPLY_NEEDED_STATUS
    rows = iter_rows(readme_path.read_text(encoding="utf-8"), SUPPLEMENT_TABLE_SECTION)
    assert rows[0].cells[-1] == NO_REPLY_NEEDED_STATUS


def test_签认型补件推送后仍标已推送(tmp_path):
    readme_path, md_path, audit, connector = _push_setup(tmp_path)
    result = _push(readme_path, md_path, audit, connector,
                   lambda c: "R5 分母请签认" in c[3], SUPPLEMENT_TABLE_SECTION)
    assert result.new_status.startswith(DELIVERED_STATUS_PREFIX)


def test_正式信推送语义与行为完全未变(tmp_path):
    readme_path, md_path, audit, connector = _push_setup(tmp_path)
    result = _push(readme_path, md_path, audit, connector,
                   lambda c: "FI2 面板复核" in c[3], MAIN_TABLE_SECTION)
    assert result.new_status.startswith(DELIVERED_STATUS_PREFIX)
    delivered = [e for e in audit.query_by(scenario="wecom-aibot")
                 if e["action"] == "followup_delivered"]
    assert delivered[0]["decision"]["kind"] == "letter"
