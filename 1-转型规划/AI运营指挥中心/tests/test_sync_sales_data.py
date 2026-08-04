"""队列 #108③：sync_sales_data.py 脱敏逻辑边界单测（脏 JSON/缺 PII 字段/嵌套异常）。"""
import copy
import importlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

sync_sales_data = importlib.import_module("sync_sales_data")


def test_desensitize_normal_lead_masks_all_pii_fields():
    leads = [{"name": "张三", "contact": "张三", "phone": "13800000000", "email": "a@b.com"}]
    result = sync_sales_data.desensitize_leads(copy.deepcopy(leads))
    assert result[0]["contact"] == sync_sales_data.MASK
    assert result[0]["phone"] == sync_sales_data.MASK
    assert result[0]["email"] == sync_sales_data.MASK
    assert result[0]["name"] == "张三"  # 非 PII 字段不受影响


def test_desensitize_missing_pii_fields_no_crash():
    leads = [{"name": "李四"}]  # 缺 contact/phone/email 三个字段
    result = sync_sales_data.desensitize_leads(leads)
    assert result == [{"name": "李四"}]  # 缺的字段不补空，原样保留


def test_desensitize_partial_pii_fields():
    leads = [{"name": "王五", "phone": "13900000000"}]  # 只有 phone，缺 contact/email
    result = sync_sales_data.desensitize_leads(leads)
    assert result[0]["phone"] == sync_sales_data.MASK
    assert "contact" not in result[0]
    assert "email" not in result[0]


def test_desensitize_skips_non_dict_entries():
    """脏 JSON：列表中混入非 dict 条目，不中断其余条目的脱敏处理。"""
    leads = ["脏字符串条目", {"phone": "13800000000"}, None, 12345, ["嵌套列表"]]
    result = sync_sales_data.desensitize_leads(leads)
    assert result[0] == "脏字符串条目"
    assert result[1]["phone"] == sync_sales_data.MASK
    assert result[2] is None
    assert result[3] == 12345
    assert result[4] == ["嵌套列表"]


def test_desensitize_nested_anomaly_field_value_replaced_wholesale():
    """PII 字段值本身是嵌套结构（异常形态）——整体替换为 MASK，不递归探查。"""
    leads = [{"phone": {"mobile": "13800000000", "office": "021-12345"}}]
    result = sync_sales_data.desensitize_leads(leads)
    assert result[0]["phone"] == sync_sales_data.MASK  # 不是残留嵌套 dict


def test_desensitize_empty_list():
    assert sync_sales_data.desensitize_leads([]) == []


def test_main_handles_high_risk_leads_wrong_type(tmp_path, monkeypatch):
    """脏 JSON：顶层 high_risk_leads 字段类型不对（如被写成字符串），不崩溃、按空列表处理。"""
    source = tmp_path / "dashboard_data.json"
    source.write_text(
        json.dumps({"sync_time": "2026-08-04 10:00", "high_risk_leads": "不是列表"}, ensure_ascii=False),
        encoding="utf-8",
    )
    target_dir = tmp_path / "out"
    monkeypatch.setattr(sync_sales_data, "SOURCE", source)
    monkeypatch.setattr(sync_sales_data, "TARGET_DIR", target_dir)
    monkeypatch.setattr(sync_sales_data, "TARGET", target_dir / "sales_dashboard_data.json")

    exit_code = sync_sales_data.main()

    assert exit_code == 0
    written = json.loads((target_dir / "sales_dashboard_data.json").read_text(encoding="utf-8"))
    assert written["high_risk_leads"] == []


def test_main_source_env_var_override(tmp_path, monkeypatch):
    """队列 #108①：SALES_CRM_DATA_PATH 环境变量可覆盖硬编码默认源路径。"""
    custom_source = tmp_path / "custom_dashboard_data.json"
    custom_source.write_text(
        json.dumps({"sync_time": "2026-08-04 10:00", "high_risk_leads": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setenv("SALES_CRM_DATA_PATH", str(custom_source))

    module = importlib.reload(sync_sales_data)
    try:
        assert module.SOURCE == custom_source
    finally:
        monkeypatch.delenv("SALES_CRM_DATA_PATH", raising=False)
        importlib.reload(sync_sales_data)  # 恢复模块级默认状态，不污染后续测试


def test_main_source_env_var_unset_falls_back_to_default(monkeypatch):
    """未设置环境变量时，回落原硬编码默认路径，现状零改变。"""
    monkeypatch.delenv("SALES_CRM_DATA_PATH", raising=False)
    module = importlib.reload(sync_sales_data)
    try:
        assert module.SOURCE == module.DEFAULT_SOURCE
    finally:
        importlib.reload(sync_sales_data)
