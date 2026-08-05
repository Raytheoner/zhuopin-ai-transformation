import asyncio
from datetime import date

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector

from aibot_service.dispatch import dispatch_followup_letters, has_unmarked_imminent_deadline
from aibot_service.readme_table import build_target_file_annotation

from fakes import fake_client_factory

TODAY = date(2026, 8, 5)

HEADER = (
    "| 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |\n"
    "|------|--------|---------|---------|---------|\n"
)


def _write_readme(tmp_path, rows: str):
    readme_path = tmp_path / "README.md"
    readme_path.write_text("## 现有跟进信清单\n\n" + HEADER + rows, encoding="utf-8")
    return readme_path


def _write_letter(tmp_path, department, name, date_str, topic="测试事项", docx=False):
    md_path = tmp_path / f"{department}-{name}-跟进-{date_str}-{topic}.md"
    md_path.write_text(f"正文：{topic}", encoding="utf-8")
    if docx:
        (md_path.with_suffix(".docx")).write_bytes(b"fake docx")
    return md_path


def _setup(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}
    connector = AibotConnector("bot", "secret", client_factory=fake_client_factory(store))
    return audit, connector, store


def test_no_finalized_rows_sends_nothing(tmp_path):
    rows = "| 2026-08-05 | 采购部 · 姚祖怡 | 测试事项 | 不急 | ⏳ 待你审 |\n"
    readme_path = _write_readme(tmp_path, rows)
    audit, connector, store = _setup(tmp_path)

    outcome = asyncio.run(
        dispatch_followup_letters(readme_path=readme_path, connector=connector, audit=audit, today=TODAY)
    )

    assert outcome.sent == []
    assert outcome.failed == []
    assert store["client"].sent_messages == []


def test_manual_only_marked_row_is_skipped(tmp_path):
    rows = (
        "| 2026-08-05 | 采购部 · 姚祖怡 | 测试事项 | 🔒人工发送 · 2026-08-06（本周五）前 | 🆕 待发 |\n"
    )
    readme_path = _write_readme(tmp_path, rows)
    _write_letter(tmp_path, "采购部", "姚祖怡", "2026-08-05")
    audit, connector, store = _setup(tmp_path)

    outcome = asyncio.run(
        dispatch_followup_letters(readme_path=readme_path, connector=connector, audit=audit, today=TODAY)
    )

    assert len(outcome.skipped_manual) == 1
    assert outcome.sent == []
    assert store["client"].sent_messages == []
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "dispatch_skipped_manual" in actions


def test_unmarked_imminent_deadline_row_is_skipped_and_recorded(tmp_path):
    # 2026-08-07 距 TODAY(2026-08-05) 仅 2 天，在 3 天窗口内，但未标 🔒人工发送。
    rows = "| 2026-08-05 | 采购部 · 姚祖怡 | 测试事项 | 2026-08-07 前给结论 | 🆕 待发 |\n"
    readme_path = _write_readme(tmp_path, rows)
    _write_letter(tmp_path, "采购部", "姚祖怡", "2026-08-05")
    audit, connector, store = _setup(tmp_path)

    outcome = asyncio.run(
        dispatch_followup_letters(readme_path=readme_path, connector=connector, audit=audit, today=TODAY)
    )

    assert len(outcome.skipped_unmarked_deadline) == 1
    assert outcome.sent == []
    assert store["client"].sent_messages == []
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "dispatch_skipped_unmarked_deadline" in actions


def test_far_future_explicit_date_is_not_treated_as_imminent(tmp_path):
    # 2027-01-01 远超 3 天窗口——正常发送，不应被拦。
    rows = "| 2026-08-05 | 采购部 · 姚祖怡 | 测试事项 | 2027-01-01 前给结论 | 🆕 待发 |\n"
    readme_path = _write_readme(tmp_path, rows)
    _write_letter(tmp_path, "采购部", "姚祖怡", "2026-08-05")
    audit, connector, store = _setup(tmp_path)

    outcome = asyncio.run(
        dispatch_followup_letters(readme_path=readme_path, connector=connector, audit=audit, today=TODAY)
    )

    assert outcome.skipped_unmarked_deadline == []
    assert len(outcome.sent) == 1


def test_relative_wording_without_explicit_date_is_not_flagged(tmp_path):
    # "不急，方便时看一眼即可"——本项目最常见的交期要点措辞，不含明确日期，
    # 不应被误判为"疑似漏标硬截止"。
    rows = "| 2026-08-05 | 采购部 · 姚祖怡 | 测试事项 | 不急，方便时看一眼即可 | 🆕 待发 |\n"
    readme_path = _write_readme(tmp_path, rows)
    _write_letter(tmp_path, "采购部", "姚祖怡", "2026-08-05")
    audit, connector, store = _setup(tmp_path)

    outcome = asyncio.run(
        dispatch_followup_letters(readme_path=readme_path, connector=connector, audit=audit, today=TODAY)
    )

    assert outcome.skipped_unmarked_deadline == []
    assert len(outcome.sent) == 1


def test_unresolvable_recipient_is_recorded_as_failed_not_blocking(tmp_path):
    rows = (
        "| 2026-08-05 | 销售部 · 未知新人 | 无法解析的行 | 不急 | 🆕 待发 |\n"
        "| 2026-08-05 | 采购部 · 姚祖怡 | 测试事项 | 不急 | 🆕 待发 |\n"
    )
    readme_path = _write_readme(tmp_path, rows)
    _write_letter(tmp_path, "采购部", "姚祖怡", "2026-08-05")
    audit, connector, store = _setup(tmp_path)

    outcome = asyncio.run(
        dispatch_followup_letters(readme_path=readme_path, connector=connector, audit=audit, today=TODAY)
    )

    assert len(outcome.failed) == 1
    assert "无法解析收件人" in outcome.failed[0][1]
    assert len(outcome.sent) == 1  # 第二行不受第一行失败影响，正常发送


def test_unresolvable_file_ambiguity_is_recorded_as_failed(tmp_path):
    rows = "| 2026-08-05 | 采购部 · 姚祖怡 | 测试事项 | 不急 | 🆕 待发 |\n"
    readme_path = _write_readme(tmp_path, rows)
    # 故意制造两个匹配文件（歧义），dispatch 不应猜测哪个是对的。
    _write_letter(tmp_path, "采购部", "姚祖怡", "2026-08-05", topic="事项甲")
    _write_letter(tmp_path, "采购部", "姚祖怡", "2026-08-05", topic="事项乙")
    audit, connector, store = _setup(tmp_path)

    outcome = asyncio.run(
        dispatch_followup_letters(readme_path=readme_path, connector=connector, audit=audit, today=TODAY)
    )

    assert len(outcome.failed) == 1
    assert "无法唯一定位" in outcome.failed[0][1]
    assert store["client"].sent_messages == []


# 队列 #241：dispatch 的行→文件匹配判据只用「收信人＋日期」，同日多封
# 必然歧义（2026-08-04 首次真实触发命中）。修法⑴——README 行携带目标
# 文件名标注，dispatch 优先读标注，不再仅凭「收信人＋日期」猜测。


def test_annotated_row_resolves_uniquely_despite_same_day_ambiguity(tmp_path):
    # 复现 #241 真实触发场景：同一收信人、同一天 3 个候选文件，仅凭
    # 「收信人＋日期」必然歧义；标注目标文件名后应能唯一定位其中一个。
    target = _write_letter(tmp_path, "采购部", "姚祖怡", "2026-07-29", topic="批2上月未齐套跨月占用判例批改")
    _write_letter(tmp_path, "采购部", "姚祖怡", "2026-07-29", topic="批2修复交付与18-19两条如实说明")
    _write_letter(tmp_path, "采购部", "姚祖怡", "2026-07-29", topic="齐料晚N天徽标真实缺陷已修复")
    topic_cell = "批 2 引擎最后一项口径判例包" + build_target_file_annotation(target.name)
    rows = f"| 2026-07-29 | 采购部 · 姚祖怡 | {topic_cell} | 不急 | 🆕 待发 |\n"
    readme_path = _write_readme(tmp_path, rows)
    audit, connector, store = _setup(tmp_path)

    outcome = asyncio.run(
        dispatch_followup_letters(readme_path=readme_path, connector=connector, audit=audit, today=TODAY)
    )

    assert outcome.failed == []
    assert len(outcome.sent) == 1


def test_annotated_row_with_missing_file_fails_without_falling_back_to_guessing(tmp_path):
    # 标注的目标文件不存在（如被改名/移动）时，即便「收信人＋日期」glob
    # 恰好唯一命中另一个文件，也不得静默回退去猜——标注失效本身就该被
    # 看见，而不是悄悄发出一封可能文不对题的信。
    _write_letter(tmp_path, "采购部", "姚祖怡", "2026-07-29", topic="真实存在的文件")
    topic_cell = "主题" + build_target_file_annotation("采购部-姚祖怡-跟进-2026-07-29-不存在的文件.md")
    rows = f"| 2026-07-29 | 采购部 · 姚祖怡 | {topic_cell} | 不急 | 🆕 待发 |\n"
    readme_path = _write_readme(tmp_path, rows)
    audit, connector, store = _setup(tmp_path)

    outcome = asyncio.run(
        dispatch_followup_letters(readme_path=readme_path, connector=connector, audit=audit, today=TODAY)
    )

    assert len(outcome.failed) == 1
    assert "标注的目标文件不存在" in outcome.failed[0][1]
    assert store["client"].sent_messages == []


def test_unannotated_row_still_falls_back_to_department_name_date_glob(tmp_path):
    # 未标注的历史行必须仍走旧判据（向后兼容），不因新增标注判据而失效。
    rows = "| 2026-08-05 | 采购部 · 姚祖怡 | 未标注的旧行 | 不急 | 🆕 待发 |\n"
    readme_path = _write_readme(tmp_path, rows)
    _write_letter(tmp_path, "采购部", "姚祖怡", "2026-08-05")
    audit, connector, store = _setup(tmp_path)

    outcome = asyncio.run(
        dispatch_followup_letters(readme_path=readme_path, connector=connector, audit=audit, today=TODAY)
    )

    assert outcome.failed == []
    assert len(outcome.sent) == 1


def test_multi_row_mixed_success_and_failure_all_processed(tmp_path):
    rows = (
        "| 2026-08-05 | 采购部 · 姚祖怡 | 测试事项甲 | 不急 | 🆕 待发 |\n"
        "| 2026-08-05 | 未知部门 · 陌生人 | 无法解析 | 不急 | 🆕 待发 |\n"
        "| 2026-08-04 | 质量部 · 陈忱 | 测试事项乙 | 不急 | 🆕 待发 |\n"
        "| 2026-08-03 | 财务部 · 唐燕萍 | 草稿未批 | 不急 | ⏳ 待你审 |\n"
    )
    readme_path = _write_readme(tmp_path, rows)
    _write_letter(tmp_path, "采购部", "姚祖怡", "2026-08-05", topic="测试事项甲")
    _write_letter(tmp_path, "质量部", "陈忱", "2026-08-04", topic="测试事项乙", docx=True)
    audit, connector, store = _setup(tmp_path)
    # 陈忱行带 docx：push_followup 内部只上传一次、CC 复用同一 media_id
    # 发 file（不重复上传），故只需一组素材上传响应。
    store["client"].raw_frame_responses["aibot_upload_media_init"] = [{"body": {"upload_id": "U1"}}]
    store["client"].raw_frame_responses["aibot_upload_media_finish"] = [{"body": {"media_id": "M1"}}]

    outcome = asyncio.run(
        dispatch_followup_letters(readme_path=readme_path, connector=connector, audit=audit, today=TODAY)
    )

    assert len(outcome.sent) == 2, outcome.failed
    assert len(outcome.failed) == 1
    new_text = readme_path.read_text(encoding="utf-8")
    assert "⏳ 待你审" in new_text  # 草稿行不受影响
    assert new_text.count("✅ 已推送") == 2
    # push_followup 默认 cc_to_paul=True（Paul 拍板的固定抄送逻辑，本模块
    # 不覆盖）：姚祖怡行无 docx=主送md+抄送md=2条；陈忱行带docx=主送md+
    # 主送file+抄送md+抄送file=4条，合计6条。
    assert len(store["client"].sent_messages) == 6


def test_has_unmarked_imminent_deadline_true_for_near_date_without_marker():
    assert has_unmarked_imminent_deadline("2026-08-07 前给结论", TODAY) is True


def test_has_unmarked_imminent_deadline_false_when_marked():
    assert has_unmarked_imminent_deadline("🔒人工发送 · 2026-08-07 前", TODAY) is False


def test_has_unmarked_imminent_deadline_false_for_far_date():
    assert has_unmarked_imminent_deadline("2027-01-01 前给结论", TODAY) is False


def test_has_unmarked_imminent_deadline_false_for_no_explicit_date():
    assert has_unmarked_imminent_deadline("本周五前", TODAY) is False
