"""队列 #270：部门→群 chatid 映射加载 + fail-closed 解析。"""
from zhuopin_platform.audit import AuditLogger

from aibot_service.department_group_chatid_mapping import (
    DEFAULT_GROUP_CHATID_MAPPING_PATH,
    load_department_group_chatid_mapping,
    resolve_group_cc_chatid,
)


def test_default_mapping_file_declares_five_departments_all_captured():
    """队列 #279/#280：2026-08-06 真实测试消息采集确认财务部/质量部/采购部/
    跨部门四个真实 chatid（intake.py 归档审计事件里读出，非猜测/占位）——
    四个部门全部采集完毕。跨部门是与财务/质量/采购平级的独立第4个部门
    （Shao Peishen 2026-08-06 明确："跟其他部门的信件无关"，不是广播/cc
    全部门的特殊对象）。销售部与 department_group_mapping.yaml 同一拍板，
    故意不建映射。

    🔴 **2026-08-24（队列 #387 ⑵）新增第 5 个：`IT` ⇒ 运维部AI保障群。**
    本用例原名 `..._four_departments_...`、原断言写死 4 个部门集合——它是
    这次改动**唯一失败的既有用例**，且失败得完全正确：`IT` 缺席正是 #387
    要修的缺陷之一，而这条断言恰恰把那个缺席钉成了"期望行为"。改断言，
    不是放宽判据：集合仍然是**精确相等**，只是多了一个真实存在的键。

    ⚠️ `销售部` 仍故意不建映射（Paul 2026-07-15 拍板），断言保留。
    """
    mapping = load_department_group_chatid_mapping()
    assert DEFAULT_GROUP_CHATID_MAPPING_PATH.exists()
    assert set(mapping) == {"财务部", "质量部", "采购部", "跨部门", "IT"}
    assert "销售部" not in mapping
    assert "IT部" not in mapping  # 键名写错会静默跳过，与 #387 要修的缺陷同形
    assert all(mapping.values())  # 五个部门均已采集，无空占位


def test_load_from_custom_path_with_real_value(tmp_path):
    custom = tmp_path / "custom_group_chatid_mapping.yaml"
    custom.write_text("采购部: GroupChatIdProcurement\n", encoding="utf-8")
    mapping = load_department_group_chatid_mapping(custom)
    assert mapping == {"采购部": "GroupChatIdProcurement"}


def test_load_treats_bare_yaml_key_as_empty_string(tmp_path):
    """yaml 里裸键（无值，解析出 None）与显式空字符串同等对待——都是"未配置"。"""
    custom = tmp_path / "custom.yaml"
    custom.write_text("财务部:\n采购部: \"\"\n", encoding="utf-8")
    mapping = load_department_group_chatid_mapping(custom)
    assert mapping == {"财务部": "", "采购部": ""}


def test_resolve_returns_chatid_when_configured(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    chatid = resolve_group_cc_chatid(
        department="采购部",
        mapping={"采购部": "GroupChatIdProcurement"},
        audit=audit,
    )
    assert chatid == "GroupChatIdProcurement"
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "followup_group_cc_skipped" not in actions


def test_resolve_skips_when_department_none(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    chatid = resolve_group_cc_chatid(department=None, mapping={"采购部": "X"}, audit=audit)
    assert chatid is None
    rows = audit.query_by(scenario="wecom-aibot")
    assert rows[-1]["action"] == "followup_group_cc_skipped"
    assert rows[-1]["decision"]["reason"] == "department_unknown"


def test_resolve_skips_when_department_not_in_mapping(tmp_path):
    """销售部一类未启用的部门——fail-closed 跳过，同 group_notify.py 的精神。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    chatid = resolve_group_cc_chatid(department="销售部", mapping={"采购部": "X"}, audit=audit)
    assert chatid is None
    rows = audit.query_by(scenario="wecom-aibot")
    assert rows[-1]["action"] == "followup_group_cc_skipped"
    assert rows[-1]["decision"]["reason"] == "department_not_in_mapping"
    assert rows[-1]["decision"]["department"] == "销售部"


def test_resolve_skips_when_chatid_value_empty_placeholder(tmp_path):
    """真实值尚未采集的占位状态——department 在表里但值为空，仍须 fail-closed。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    chatid = resolve_group_cc_chatid(department="采购部", mapping={"采购部": ""}, audit=audit)
    assert chatid is None
    rows = audit.query_by(scenario="wecom-aibot")
    assert rows[-1]["action"] == "followup_group_cc_skipped"
    assert rows[-1]["decision"]["reason"] == "group_chatid_not_configured"


def test_resolve_every_skip_records_an_audit_event_scenario_wecom_aibot(tmp_path):
    """每次跳过都留痕（不静默），scenario 固定为 wecom-aibot 同全项目审计约定。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    for department, mapping in (
        (None, {}),
        ("销售部", {"采购部": "X"}),
        ("采购部", {"采购部": ""}),
    ):
        resolve_group_cc_chatid(department=department, mapping=mapping, audit=audit)
    rows = audit.query_by(scenario="wecom-aibot")
    assert len(rows) == 3
    assert all(r["action"] == "followup_group_cc_skipped" for r in rows)
