"""变更包 `followup-closure-form-survives-backfill` 回填侧单测（tasks 3.2／4.1–4.5）。

Shao Peishen 2026-09-12 签认：决策点 1(a)／2(a)＋三护栏／3(a)／4(a)／5(c)／6(a)。
本文件证的是**回填落字**这一半；判据本身（解析／越界／快照读回／不一致告警）
在 `zhuopin_platform/tests/test_followup_gate_closure_form.py`。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools import followup_gate as fg
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector

from aibot_service.delivery import (
    DELIVERED_STATUS_PREFIX,
    PRESERVED_STATUS_LABEL,
    push_followup,
    resolve_backfill,
    resolve_backfill_status,
)
from aibot_service.followup_readme_bridge import build_reply_arrived_status
from aibot_service.gates import FINALIZED_STATUS_MARKER
from aibot_service.readme_table import (
    MAIN_TABLE_SECTION,
    NO_REPLY_NEEDED_STATUS,
    SUPPLEMENT_TABLE_SECTION,
    build_closure_form_annotation,
    extract_closure_form,
    extract_target_filename,
    iter_rows,
    locate_row,
)

from fakes import fake_client_factory

HEADER = (
    "## 现有跟进信清单\n\n"
    "| 编号 | 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |\n"
    "|------|------|--------|---------|---------|---------|\n"
)
SUPPLEMENT = (
    "\n## 补件登记（不占编号、不占串行闸）\n\n"
    "| 承接编号 | 日期 | 收信人 | 主要事项 | 需回复 | 发送状态 |\n"
    "|---------|------|--------|---------|--------|---------|\n"
    "| 财务部#15 | 2026-08-25 | 财务部 · 唐燕萍 | 通知型补件 | 否 | 🆕 待发 |\n"
)

合法标注 = build_closure_form_annotation("✅ 无需回复", "三要素明写不用回")


def _readme(topic: str, status: str = FINALIZED_STATUS_MARKER) -> str:
    return (
        HEADER
        + f"| 质量部#20 | 2026-09-12 | 质量部 · 陈忱 | {topic} | 不用回 | {status} |\n"
        + SUPPLEMENT
    )


def _loc(topic: str, status: str = FINALIZED_STATUS_MARKER):
    return locate_row(_readme(topic, status), lambda c: "质量部#20" in c[0])


# ------------------------------------------------------------- 3.1 / 3.2 写入与提取

def test_标注写入与提取往返():
    form = extract_closure_form("主题" + 合法标注)
    assert form is not None and form.is_valid
    assert form.value == "✅ 无需回复" and form.basis == "三要素明写不用回"


def test_写侧拒绝写出不合法标注():
    with pytest.raises(ValueError):
        build_closure_form_annotation("✅ 大概不用回", "x")
    with pytest.raises(ValueError):
        build_closure_form_annotation("✅ 无需回复", "")


def test_标注约七十字节_压在主要事项列六百字节判据之内():
    """决策点 1(a) 代价②：`质量部#7` 该格现 492 B，标注须压在约 100 B 内。"""
    assert len(合法标注.encode("utf-8")) <= 100


def test_追加标注后列数不变_与目标文件标注同列共存():
    """tasks 3.2：只在既有单元格内追加文本，不新增列；与 `#241` 的
    `目标文件：` 标注同列共存、互不干扰。"""
    plain = _readme("主题 → 目标文件：`质量部-陈忱-跟进-2026-09-12-x.md`")
    annotated = _readme("主题 → 目标文件：`质量部-陈忱-跟进-2026-09-12-x.md`" + 合法标注)
    rows_plain = iter_rows(plain)
    rows_annotated = iter_rows(annotated)
    assert len(rows_plain) == len(rows_annotated) == 1
    assert len(rows_plain[0].cells) == len(rows_annotated[0].cells)
    topic = rows_annotated[0].cells[3]
    assert extract_target_filename(topic) == "质量部-陈忱-跟进-2026-09-12-x.md"
    assert extract_closure_form(topic).value == "✅ 无需回复"


# ------------------------------------------------------------- 4.3 无标注逐字相同

def test_无标注回填结果与本变更前逐字相同():
    """spec「空状态格回填后与今天逐字相同」：不多出空分隔符、不多出快照段。"""
    decision = resolve_backfill(_loc("普通主题"), MAIN_TABLE_SECTION, "T")
    assert decision.status == f"{DELIVERED_STATUS_PREFIX} T"
    assert decision.closure_form is None
    assert not decision.snapshot_written
    assert not decision.gate_opened_at_backfill
    assert resolve_backfill_status(_loc("普通主题"), MAIN_TABLE_SECTION, "T") == "✅ 已推送 T"


# ------------------------------------------------------------- 4.1 / 4.2 / 4.5 快照与闭环态

def test_合法无需回复标注_回填首段即闭环态_快照与已推送后段俱在():
    """决策点 2(a)＋护栏③＋决策点 3(a)：`✅ 无需回复 <UTC>　━━━　闭环形态（发出时快照）
    ━━━　…　━━━　✅ 已推送 <UTC>`。"""
    decision = resolve_backfill(_loc("主题" + 合法标注), MAIN_TABLE_SECTION, "2026-09-12 08:00 UTC")
    status = decision.status
    assert status.startswith(f"{NO_REPLY_NEEDED_STATUS} 2026-09-12 08:00 UTC")
    assert fg.CLOSURE_SNAPSHOT_LABEL in status
    assert fg.extract_closure_snapshot(status) == "✅ 无需回复"
    assert "依据：三要素明写不用回" in status
    # 护栏③：「何时推送」这个事实不丢
    assert status.endswith(f"{DELIVERED_STATUS_PREFIX} 2026-09-12 08:00 UTC")
    assert decision.snapshot_written and decision.gate_opened_at_backfill
    # 串行闸判据（前缀）当场认它为闭环
    assert fg.classify_status(status) == "closed"
    assert fg.is_closed_status(status)


def test_护栏二_越界取值_仍写已推送_闸仍锁_且问题被带回():
    """🔴 决策点 2(a) 护栏②／4(a) 的反例：越界 ⇒ 按无标注处理，回填结果与
    无标注**逐字相同**（连快照段都没有），但 `problem` 必须被带回给调用方报出来。"""
    decision = resolve_backfill(
        _loc("主题 → 闭环形态：`✅ 大概不用回`（依据：随便）"), MAIN_TABLE_SECTION, "T")
    assert decision.status == f"{DELIVERED_STATUS_PREFIX} T"
    assert not decision.snapshot_written and not decision.gate_opened_at_backfill
    assert decision.closure_form_problem and "不在闭环四态枚举内" in decision.closure_form_problem
    assert fg.classify_status(decision.status) == "in_flight"  # 闸仍锁


def test_护栏二_缺依据_同样仍写已推送():
    decision = resolve_backfill(
        _loc("主题 → 闭环形态：`✅ 无需回复`"), MAIN_TABLE_SECTION, "T")
    assert decision.status == f"{DELIVERED_STATUS_PREFIX} T"
    assert "缺依据" in decision.closure_form_problem


def test_枚举另三态只快照不开闸():
    """决策点 4(a) 已知边界：起草时能判定的只有 `✅ 无需回复`；另三态属枚举
    合法值（不退化为布尔），但发出那一刻它们不可能为真 ⇒ 快照、不开闸。"""
    topic = "主题" + build_closure_form_annotation("📥 已回件并回灌", "起草人误填")
    decision = resolve_backfill(_loc(topic), MAIN_TABLE_SECTION, "T")
    assert decision.status.startswith(f"{DELIVERED_STATUS_PREFIX} T")
    assert decision.snapshot_written and not decision.gate_opened_at_backfill
    assert fg.classify_status(decision.status) == "in_flight"


def test_保留式_未发出家族的附加内容接在后面():
    """spec「回填保留人写的暂缓理由」（函数级）：状态格为 `⏸ 暂缓（依据：…）`
    时理由原样接在 `　━━━　原状态 ━━━　` 之后。⚠️ 门禁②等值断言下经
    `push_followup` 实际不可达（见 `test_门禁二仍拒绝带附加内容的状态格`）。"""
    prev = "⏸ 暂缓（依据：等陈忱回国再发）"
    decision = resolve_backfill(_loc("普通主题", prev), MAIN_TABLE_SECTION, "T")
    assert decision.status.startswith(f"{DELIVERED_STATUS_PREFIX} T")
    assert decision.status.endswith(f"{fg.STATUS_SEGMENT_SEPARATOR}{PRESERVED_STATUS_LABEL}{prev}")
    assert fg.classify_status(decision.status) == "in_flight"


def test_补件表分支一字未动():
    """决策点 3(a) 代价：补件表 `✅ 无需回复` 不带时刻、不带快照，是 `#399` 已拍板的形态。"""
    text = _readme("主题" + 合法标注)
    loc = locate_row(text, lambda c: "通知型补件" in c[3], SUPPLEMENT_TABLE_SECTION)
    decision = resolve_backfill(loc, SUPPLEMENT_TABLE_SECTION, "T")
    assert decision.status == NO_REPLY_NEEDED_STATUS
    assert decision.closure_form is None and not decision.snapshot_written


# ------------------------------------------------------------- 端到端：push_followup

def _setup(tmp_path, topic: str, status: str = FINALIZED_STATUS_MARKER):
    readme_path = tmp_path / "README.md"
    readme_path.write_text(_readme(topic, status), encoding="utf-8")
    md_path = tmp_path / "letter.md"
    md_path.write_text("正文：不用回。", encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}
    connector = AibotConnector("bot", "secret", client_factory=fake_client_factory(store))
    return readme_path, md_path, audit, connector


def _push(readme_path, md_path, audit, connector):
    return asyncio.run(push_followup(
        readme_path=readme_path, md_path=md_path, docx_path=None,
        connector=connector, chatid="chat-1", match=lambda c: "质量部#20" in c[0],
        audit=audit, cc_to_paul=False,
    ))


def test_端到端_起草时有标注_回填后标注仍读得出且闸开(tmp_path):
    readme_path, md_path, audit, connector = _setup(tmp_path, "主题" + 合法标注)
    result = _push(readme_path, md_path, audit, connector)
    row = locate_row(readme_path.read_text(encoding="utf-8"), lambda c: "质量部#20" in c[0])
    status = row.cells[row.status_col_index]
    assert status == result.new_status
    assert status.startswith(NO_REPLY_NEEDED_STATUS)
    assert fg.extract_closure_snapshot(status) == "✅ 无需回复"
    assert fg.is_closed_status(status)
    # 主要事项列一字未动
    assert extract_closure_form(row.cells[3]).value == "✅ 无需回复"
    backfilled = [r for r in audit.query_by(scenario="wecom-aibot") if r["action"] == "followup_backfilled"]
    assert backfilled and backfilled[-1]["decision"]["gate_opened_at_backfill"] is True
    assert backfilled[-1]["decision"]["closure_snapshot_written"] is True
    assert not any(r["action"] == "followup_closure_form_rejected"
                   for r in audit.query_by(scenario="wecom-aibot"))


def test_端到端_越界标注_审计fail_loud_回填仍已推送(tmp_path):
    """护栏②在真实链路上的反例：`followup_closure_form_rejected` 必须出现，
    状态格仍是 `✅ 已推送 …`、闸仍锁。"""
    readme_path, md_path, audit, connector = _setup(
        tmp_path, "主题 → 闭环形态：`✅ 大概不用回`（依据：随便）")
    result = _push(readme_path, md_path, audit, connector)
    assert result.new_status.startswith(DELIVERED_STATUS_PREFIX)
    assert fg.CLOSURE_SNAPSHOT_LABEL not in result.new_status
    rejected = [r for r in audit.query_by(scenario="wecom-aibot")
                if r["action"] == "followup_closure_form_rejected"]
    assert len(rejected) == 1
    assert rejected[0]["decision"]["treated_as"] == "no_annotation"
    assert "不在闭环四态枚举内" in rejected[0]["decision"]["problem"]
    assert fg.classify_status(result.new_status) == "in_flight"


def test_端到端_无标注_行为与今天逐字相同(tmp_path):
    readme_path, md_path, audit, connector = _setup(tmp_path, "普通主题")
    result = _push(readme_path, md_path, audit, connector)
    assert result.new_status.startswith(f"{DELIVERED_STATUS_PREFIX} ")
    assert fg.STATUS_SEGMENT_SEPARATOR not in result.new_status
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "followup_closure_form_rejected" not in actions


def test_门禁二仍拒绝带附加内容的状态格(tmp_path):
    """如实登记：保留式对「暂缓理由」的保护在真实链路上被门禁②（等值断言、
    D8 红线、本包不改）挡在前面——状态格必须恰为 `🆕 待发` 才发得出。"""
    from aibot_service.gates import DeliveryNotFinalizedError
    readme_path, md_path, audit, connector = _setup(
        tmp_path, "普通主题", "🆕 待发　━━━　原状态 ━━━　⏸ 暂缓（依据：x）")
    with pytest.raises(DeliveryNotFinalizedError):
        _push(readme_path, md_path, audit, connector)


# ------------------------------------------------------------- 4.4 兼容性反例

快照态 = resolve_backfill(_loc("主题" + 合法标注), MAIN_TABLE_SECTION, "T").status
纯已推送 = f"{DELIVERED_STATUS_PREFIX} T"
纯无需回复 = f"{NO_REPLY_NEEDED_STATUS} T"


@pytest.mark.parametrize("fn", [
    fg.classify_status, fg.normalize_status, fg.is_closed_status,
    fg.is_reply_arrived_status, fg.is_not_yet_sent, fg.is_dispatched,
])
def test_兼容_快照态与未写快照的同一状态结论一致(fn):
    """spec「快照 MUST 兼容既有全部状态判据」：喂「写了快照的状态格」与
    「未写快照的同一状态」，除 `normalize_status`（它返回整串、只比首段）外结论逐一相同。"""
    if fn is fg.normalize_status:
        assert fn(快照态).startswith(fn(纯无需回复))
        return
    assert fn(快照态) == fn(纯无需回复)


def test_兼容_快照不影响第九态转态且快照仍可读():
    now = datetime(2026, 9, 12, 8, 0, tzinfo=timezone.utc)
    ninth = build_reply_arrived_status(快照态, "质量部-陈忱-回复-2026-09-12-x-abc123.docx", now)
    assert fg.is_reply_arrived_status(ninth)
    assert fg.classify_status(ninth) == "reply_arrived"
    assert fg.extract_closure_snapshot(ninth) == "✅ 无需回复"
    assert 快照态 in ninth  # 整个原状态原样接在后面


def test_兼容_已推送加快照仍是在途():
    topic = "主题" + build_closure_form_annotation("📥 已回件并回灌", "x")
    status = resolve_backfill(_loc(topic), MAIN_TABLE_SECTION, "T").status
    assert fg.classify_status(status) == fg.classify_status(纯已推送) == "in_flight"
