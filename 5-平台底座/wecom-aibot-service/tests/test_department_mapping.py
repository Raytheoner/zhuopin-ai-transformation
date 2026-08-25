from pathlib import Path

import pytest

from aibot_service.department_mapping import (
    load_department_mapping,
    resolve_department,
    UNMATCHED_DEPARTMENT,
    DEFAULT_MAPPING_PATH,
)


def test_default_mapping_file_loads_and_matches_four_domains_plus_it():
    """键是企微 userid（2026-07-13 真实联调确认，非中文名）。2026-07-22（队列
    #70）新增陈承（IT，userid=2023458）——IT 不是 Cowork 的四域专线之一，映射
    值就是 "IT"（非 "IT部"），与 `7-外部文档/IT/` 归档目录名一致。

    2026-08-25（队列 #380 ／ §四 #116）新增李姣龙（`2025672`，财务部）与
    解植雅（`2025621`，采购部），**与白名单同批加**（见
    `test_whitelist_inbound_admission.py` 的两表求差不变式）。
    """
    mapping = load_department_mapping()
    assert mapping == {
        "YaoZuYi": "采购部",
        "tangyanping": "财务部",
        "ChenChen": "质量部",
        "Hongqin.Wang": "销售部",
        "2023458": "IT",
        "2025672": "财务部",
        "2025621": "采购部",
    }


def test_numeric_yaml_keys_survive_str_normalisation():
    """🔴 `2025672`／`2025621` 在 YAML 里带引号，但**引号是写法一致性、不是
    正确性**：`department_mapping.py` 的 `{str(k): str(v) ...}` 会把 YAML 解析
    出的 int 键一并归一成 str。

    本测把这条依赖钉住——若哪天有人去掉那层 `str()`、又恰好有人写了不带引号
    的数字键，查表会静默查不中、来件落"待分拣"，**而命令行一切正常**。
    """
    mapping = load_department_mapping()
    assert mapping["2025672"] == "财务部"
    assert mapping["2025621"] == "采购部"
    assert all(isinstance(k, str) for k in mapping)


def test_resolve_department_matched():
    mapping = {"姚祖怡": "采购部"}
    assert resolve_department("姚祖怡", mapping) == "采购部"


def test_resolve_department_unmatched_fails_closed():
    mapping = {"姚祖怡": "采购部"}
    assert resolve_department("陌生人", mapping) == UNMATCHED_DEPARTMENT


def test_resolve_department_does_not_fuzzy_match():
    """fail-closed：不做模糊/子串匹配，只做精确 key 命中。"""
    mapping = {"姚祖怡": "采购部"}
    assert resolve_department("姚祖怡（临时代理）", mapping) == UNMATCHED_DEPARTMENT


def test_load_department_mapping_rejects_non_mapping_yaml(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_department_mapping(bad)


def test_default_mapping_path_points_inside_package():
    assert DEFAULT_MAPPING_PATH.name == "department_mapping.yaml"
    assert DEFAULT_MAPPING_PATH.parent == Path(__file__).resolve().parent.parent / "aibot_service"
