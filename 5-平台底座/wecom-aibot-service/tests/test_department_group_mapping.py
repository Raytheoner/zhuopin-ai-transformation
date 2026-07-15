from aibot_service.department_group_mapping import (
    DEFAULT_GROUP_MAPPING_PATH,
    load_department_group_mapping,
    resolve_group_chatid,
)


def test_default_mapping_file_loads_and_has_four_departments():
    mapping = load_department_group_mapping()
    assert DEFAULT_GROUP_MAPPING_PATH.exists()
    assert set(mapping) == {"财务部", "质量部", "采购部", "销售部"}


def test_resolve_returns_none_for_placeholder_value():
    mapping = {"财务部": "PLACEHOLDER_FINANCE_GROUP_CHATID"}
    assert resolve_group_chatid("财务部", mapping) is None


def test_resolve_returns_none_for_unmapped_department():
    assert resolve_group_chatid("财务部", {}) is None


def test_resolve_returns_real_chatid_when_configured():
    mapping = {"财务部": "wrXXXXXXXXXXXXXXXXXXXXXXXX"}
    assert resolve_group_chatid("财务部", mapping) == "wrXXXXXXXXXXXXXXXXXXXXXXXX"


def test_load_from_custom_path(tmp_path):
    custom = tmp_path / "custom_group_mapping.yaml"
    custom.write_text("财务部: REAL_ID\n", encoding="utf-8")
    mapping = load_department_group_mapping(custom)
    assert mapping == {"财务部": "REAL_ID"}
