from aibot_service.department_group_mapping import (
    DEFAULT_GROUP_MAPPING_PATH,
    load_department_group_mapping,
)


def test_default_mapping_file_loads_three_enabled_departments():
    """销售部 Paul 2026-07-15 拍板暂不启用，故意不在默认映射表里。"""
    mapping = load_department_group_mapping()
    assert DEFAULT_GROUP_MAPPING_PATH.exists()
    assert set(mapping) == {"财务部", "质量部", "采购部"}
    assert "销售部" not in mapping


def test_default_mapping_values_are_env_var_names_not_secrets():
    """本表提交进 git，只能存环境变量名，绝不能出现真实 webhook key。"""
    mapping = load_department_group_mapping()
    for value in mapping.values():
        assert value.startswith("WECOM_WEBHOOK_URL_")
        assert "qyapi.weixin.qq.com" not in value


def test_load_from_custom_path(tmp_path):
    custom = tmp_path / "custom_group_mapping.yaml"
    custom.write_text("财务部: WECOM_WEBHOOK_URL_FINANCE\n", encoding="utf-8")
    mapping = load_department_group_mapping(custom)
    assert mapping == {"财务部": "WECOM_WEBHOOK_URL_FINANCE"}
