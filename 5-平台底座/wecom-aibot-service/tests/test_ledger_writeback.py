"""发送侧 → 口径点台账回写（`coverage-point-ledger` tasks §2bis 的 2b.3）。

补的洞：2026-09-07 `财务部#17` 发出后，台账那两行 `在途` 是 `OP-0907-L` 手写脚本
补的，不是机制。本文件断言"发出成功 ⇒ 台账自动转 `在途`"这条路真的通了，且
**它坏掉的时候不会把一次成功的发送连累成失败**。

🔴 全程 mock：不连企微、不发任何真实消息（`fakes.fake_client_factory`），
台账造在 `tmp_path`，仓库内那五份真台账一个字节都不碰。
"""
from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path

import pytest

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.coverage_point_ledger import (
    Event,
    LedgerEvent,
    LedgerStore,
    PointType,
    Status,
)
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector

from aibot_service import ledger_writeback
from aibot_service.delivery import push_followup
from aibot_service.ledger_writeback import (
    letter_ref_from_row,
    point_ids_declared_in_letter,
    record_letter_sent,
)

from fakes import fake_client_factory

# 带「编号」列的 README —— 真身主表就是这个形状（2026-07-31 起加编号列）。
README_TEXT = """\
## 现有跟进信清单

| 日期 | 编号 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-09-07） |
|------|------|--------|---------|---------|---------|
| 2026-09-07 | 财务部#17 | 财务部 · 唐燕萍 | FI10 存货跌价计提底稿索取 | 一周内 | 🆕 待发 |
"""

LETTER_MD = """\
---
title: "财务部#17 · FI10 存货跌价智能分析：想先借你近 2–3 年的计提底稿"
编号: 财务部#17
created: 2026-09-07
status: 🆕 待发
收信人: 财务部 · 唐燕萍
决策点: 1 项（材料索取：近 2–3 年跌价准备计提底稿）
配套: 队列 §一 #474（FI10 场景行）／口径点台账 `FI10-G-07`（`6-人才与组织/部门AI专员跟进/口径点台账/财务域.jsonl`）／`openspec/changes/fi10-inventory-writedown-mvp/design.md` D9
---

唐燕萍，想先借你近 2–3 年的跌价计提底稿。
"""


def _match_fi10(cells):
    return any("FI10" in cell for cell in cells)


def _create_row(point_id: str, **kw) -> LedgerEvent:
    base = dict(
        id=point_id,
        event=Event.CREATE,
        status=Status.ASKING,
        type=PointType.MATERIAL_REQUEST,
        scene="FI10",
        proposer="Shao Peishen",
        fact_date="2026-09-06",
        recorded_on="2026-09-06T21:30:00+08:00",
        by="OP-0906-W-test",
        case_text="近 2–3 年跌价准备计提底稿（测试数据，非真实口径点）",
        proposed_ruling="（测试数据）",
        carrier=("openspec:fi10-inventory-writedown-mvp",),
    )
    base.update(kw)
    return LedgerEvent(**base)


def _setup(tmp_path, *, ledger_rows=(), letter_md=LETTER_MD, readme=README_TEXT):
    readme_path = tmp_path / "README.md"
    readme_path.write_text(readme, encoding="utf-8")
    md_path = tmp_path / "财务部-唐燕萍-跟进-2026-09-07-FI10.md"
    md_path.write_text(letter_md, encoding="utf-8")

    store = LedgerStore(ledger_writeback.resolve_ledger_dir(readme_path))
    store.initialize()
    for row in ledger_rows:
        store.append(row)

    audit_path = tmp_path / "audit.jsonl"
    audit = AuditLogger.jsonl(audit_path)
    sent: dict = {}
    connector = AibotConnector("bot", "secret", client_factory=fake_client_factory(sent))
    return readme_path, md_path, store, audit, audit_path, connector


def _audit_actions(audit_path: Path) -> list[str]:
    return [
        json.loads(line)["action"]
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _push(readme_path, md_path, audit, connector):
    return asyncio.run(
        push_followup(
            readme_path=readme_path,
            md_path=md_path,
            docx_path=None,
            connector=connector,
            chatid="chat-tang",
            match=_match_fi10,
            audit=audit,
            evaluator="OP-0907-AK-test",
            cc_to_paul=False,
        )
    )


# ---------------------------------------------------------------- 判据零件

def test_2b3_编号列取信编号_只认表头带编号的那一列():
    header = ["日期", "编号", "收信人", "主要事项", "发送状态"]
    cells = ["2026-09-07", "财务部#17", "财务部 · 唐燕萍", "你上一封 财务部#16 已消化", "🆕 待发"]
    assert letter_ref_from_row(header, cells) == "财务部#17"


def test_2b3_没有编号列时返回None_不去别的列里猜():
    """🔴 反向对照：`主要事项` 列里提到 `财务部#16`，**不得**被当成本行的编号。

    写错一封信的编号之后，台账看上去完全正常——没有任何东西会报错。
    宁可这次不写（审计里查得到），不可写错一封。
    """
    header = ["日期", "收信人", "主要事项", "发送状态"]
    cells = ["2026-09-07", "财务部 · 唐燕萍", "你上一封 财务部#16 已消化", "🆕 待发"]
    assert letter_ref_from_row(header, cells) is None


def test_2b3_起草期括注也认得():
    assert letter_ref_from_row(["编号"], ["财务部#17（待你审，暂不占号）"]) == "财务部#17"
    assert letter_ref_from_row(["编号"], ["销售部（未发，不编号）"]) is None


def test_2b3_补件表承接编号列同样认得():
    assert letter_ref_from_row(["日期", "承接编号"], ["2026-09-07", "财务部#16"]) == "财务部#16"


def test_2b3_信侧自陈的点id从配套字段取(tmp_path):
    md = tmp_path / "letter.md"
    md.write_text(LETTER_MD, encoding="utf-8")
    assert point_ids_declared_in_letter(md) == ("FI10-G-07",)


def test_2b3_配套字段里的路径与队列号不会被当成点id(tmp_path):
    """`配套:` 是自由文本 —— 反引号里可能是路径、变更包名。

    形状筛只是第一道；真正的把关是与台账 `Snapshot.points` 求交（见
    `test_2b3_信侧自陈了一个台账里不存在的点则不写`）。
    """
    md = tmp_path / "letter.md"
    md.write_text(
        "---\n配套: `6-人才与组织/部门AI专员跟进/口径点台账/财务域.jsonl`／`FI10-G-07`\n---\n正文\n",
        encoding="utf-8",
    )
    assert point_ids_declared_in_letter(md) == ("FI10-G-07",)


def test_2b3_没有frontmatter的信返回空(tmp_path):
    md = tmp_path / "letter.md"
    md.write_text("正文：请尽快回复。", encoding="utf-8")
    assert point_ids_declared_in_letter(md) == ()


# ---------------------------------------------------------------- 主断言

def test_2b3_发出成功后待问点自动转在途(tmp_path):
    """**2b.3 主断言**：一次成功推送 ⇒ 台账多一行 `转态 在途`，带 `letters`。

    四件一起断：状态推进了、`letters` 记下了是哪封信、`fact_date` ＝ 发出日、
    `recorded_on` 带 `+08:00`。
    """
    readme_path, md_path, store, audit, audit_path, connector = _setup(
        tmp_path, ledger_rows=[_create_row("FI10-G-07")]
    )
    assert store.current_status("FI10-G-07") is Status.ASKING

    _push(readme_path, md_path, audit, connector)

    current = store.current("FI10-G-07")
    assert current.status is Status.IN_FLIGHT
    assert current.event is Event.TRANSITION
    assert current.letters == ("财务部#17",)
    assert current.fact_date == date.today().isoformat()
    assert current.recorded_on.endswith("+08:00")
    assert "followup_ledger_writeback" in _audit_actions(audit_path)


def test_2b3_台账侧已连线的点也认得_不依赖信侧自陈(tmp_path):
    """来源⑴：点的 `letters` 里已有该编号（起草期连的线），信里没写点 id 也认得。"""
    rows = [
        _create_row("FI10-G-05"),
        LedgerEvent(
            id="FI10-G-05", event=Event.BACKFILL, status=Status.ASKING,
            fact_date="2026-09-07", recorded_on="2026-09-07T07:00:00+08:00",
            by="OP-0907-L-test", letters=("财务部#17（待你审，暂不占号）",),
            note="起草期连线：本点由 财务部#17 投影，状态不动",
        ),
    ]
    readme_path, md_path, store, audit, audit_path, connector = _setup(
        tmp_path,
        ledger_rows=rows,
        letter_md="---\n编号: 财务部#17\n配套: 队列 §一 #474\n---\n正文\n",
    )

    _push(readme_path, md_path, audit, connector)

    assert store.current_status("FI10-G-05") is Status.IN_FLIGHT


def test_2b3_非投影信零回写_五份域文件字节数不变(tmp_path):
    """`采购部#21` 形态 —— 信不投影任何点 ⇒ 台账一个字节没长，但**审计有留痕**。

    🔑 「不投影」必须与「这一步压根没跑」在审计里长得不一样，否则下次再出
    「30 分钟拆完、台账零回写」时，一样看不出是哪种。
    """
    readme_path, md_path, store, audit, audit_path, connector = _setup(
        tmp_path,
        ledger_rows=[_create_row("FI10-G-07")],
        readme=README_TEXT.replace("财务部#17", "采购部#21"),
        letter_md="---\n编号: 采购部#21\n配套: 队列 §一 #499\n---\nFI10 正文\n",
    )
    before = {p.name: p.stat().st_size for p in store.ledger_dir.glob("*.jsonl")}

    _push(readme_path, md_path, audit, connector)

    assert {p.name: p.stat().st_size for p in store.ledger_dir.glob("*.jsonl")} == before
    assert store.current_status("FI10-G-07") is Status.ASKING

    records = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    writeback = [r for r in records if r["action"] == "followup_ledger_writeback"]
    assert len(writeback) == 1
    assert writeback[0]["decision"]["non_projection"] is True
    assert writeback[0]["decision"]["transitioned"] == []


def test_2b3_信侧自陈了一个台账里不存在的点则不写(tmp_path):
    """**反向对照**：`配套:` 里写了个台账里没有的 id ⇒ 求交挡住，不凭空建点。"""
    readme_path, md_path, store, audit, audit_path, connector = _setup(
        tmp_path,
        ledger_rows=[_create_row("FI10-G-07")],
        letter_md=LETTER_MD.replace("FI10-G-07", "FI10-G-99"),
    )
    before = {p.name: p.stat().st_size for p in store.ledger_dir.glob("*.jsonl")}

    _push(readme_path, md_path, audit, connector)

    assert {p.name: p.stat().st_size for p in store.ledger_dir.glob("*.jsonl")} == before
    assert store.current("FI10-G-99") is None, "🔴 不得凭一句自由文本就建出一个点"


def test_2b3_已签认的点不被一次重推拖回在途(tmp_path):
    """已签认 ⇒ 跳过。把它拖回 `在途` 是无因倒退，凑一个 `note` 出来的理由是假的。"""
    rows = [
        _create_row("FI10-G-07"),
        LedgerEvent(
            id="FI10-G-07", event=Event.TRANSITION, status=Status.IN_FLIGHT,
            fact_date="2026-09-07", recorded_on="2026-09-07T07:40:00+08:00",
            by="OP-0907-L-test", letters=("财务部#17",),
        ),
        LedgerEvent(
            id="FI10-G-07", event=Event.TRANSITION, status=Status.SIGNED,
            fact_date="2026-09-12", recorded_on="2026-09-12T14:02:00+08:00",
            by="OP-0912-B-test",
            evidence="7-外部文档/财务部/财务部-回复-财务部#17-2026-09-12.md",
        ),
    ]
    readme_path, md_path, store, audit, audit_path, connector = _setup(
        tmp_path, ledger_rows=rows
    )
    before = {p.name: p.stat().st_size for p in store.ledger_dir.glob("*.jsonl")}

    _push(readme_path, md_path, audit, connector)

    assert {p.name: p.stat().st_size for p in store.ledger_dir.glob("*.jsonl")} == before
    assert store.current_status("FI10-G-07") is Status.SIGNED


def test_2b3_重推同一封信不产生第二行在途(tmp_path):
    """已是 `在途` ⇒ 跳过。同一封信"发出去"这件事只发生过一次。"""
    readme_path, md_path, store, audit, audit_path, connector = _setup(
        tmp_path, ledger_rows=[_create_row("FI10-G-07")]
    )
    _push(readme_path, md_path, audit, connector)
    size_after_first = (store.ledger_dir / "财务域.jsonl").stat().st_size

    # README 状态已被回填成 `✅ 已推送`，门禁②会拒——直接再调回写逻辑本身。
    result = record_letter_sent(
        readme_path=readme_path,
        md_path=md_path,
        header_cells=["日期", "编号", "收信人", "主要事项", "交期要点", "发送状态（2026-09-07）"],
        cells=["2026-09-07", "财务部#17", "财务部 · 唐燕萍", "FI10", "一周内", "✅ 已推送"],
        by="OP-0907-AK-test",
    )

    assert result.transitioned == []
    assert result.skipped == {"FI10-G-07": "当前 在途"}
    assert (store.ledger_dir / "财务域.jsonl").stat().st_size == size_after_first


# ---------------------------------------------------------------- 隔离

def test_2b3_台账回写失败不影响发送已成功这个事实(tmp_path, monkeypatch):
    """**隔离断言**：回写炸了 ⇒ 推送照样返回成功、README 照样回填，只多一条审计。

    🔑 台账没写上可以事后补（`cli transition` 就是那条路）；把一次成功的发送
    报成失败、让下一班当作"待发"重发，才是不可挽回的。
    """
    readme_path, md_path, store, audit, audit_path, connector = _setup(
        tmp_path, ledger_rows=[_create_row("FI10-G-07")]
    )

    def _boom(**kwargs):
        raise RuntimeError("台账目录被谁锁住了")

    monkeypatch.setattr("aibot_service.delivery.record_letter_sent", _boom)

    result = _push(readme_path, md_path, audit, connector)

    assert result.new_status.startswith("✅ 已推送")
    actions = _audit_actions(audit_path)
    assert "followup_delivered" in actions
    assert "followup_ledger_writeback_failed" in actions
    assert "followup_ledger_writeback" not in actions


def test_2b3_没有台账目录时不建第二本账_只记审计(tmp_path):
    """README 旁边没有 `口径点台账/` 时（如 `.51` 扁平部署）⇒ 不建、不炸、有留痕。"""
    readme_path = tmp_path / "README.md"
    readme_path.write_text(README_TEXT, encoding="utf-8")
    md_path = tmp_path / "letter.md"
    md_path.write_text(LETTER_MD, encoding="utf-8")
    audit_path = tmp_path / "audit.jsonl"
    audit = AuditLogger.jsonl(audit_path)
    connector = AibotConnector("bot", "secret", client_factory=fake_client_factory({}))

    result = _push(readme_path, md_path, audit, connector)

    assert result.new_status.startswith("✅ 已推送")
    assert not (tmp_path / "口径点台账").exists(), "🔴 不得顺手建出一本空的第二本账"
    assert "followup_ledger_writeback" in _audit_actions(audit_path)


@pytest.mark.parametrize("field_name", ["口径点", "配套"])
def test_2b3_口径点字段优先于配套(tmp_path, field_name):
    """`口径点:` 是将来更明确的写法；两者都支持，前者优先。"""
    md = tmp_path / "letter.md"
    md.write_text(f"---\n编号: 财务部#17\n{field_name}: `FI10-G-07`\n---\n正文\n", encoding="utf-8")
    assert point_ids_declared_in_letter(md) == ("FI10-G-07",)
