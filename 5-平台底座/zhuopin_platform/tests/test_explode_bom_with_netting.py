"""多层 BOM 递归展开 + 逐层现货抵扣（B1，shortage-multilevel-bom-b1，2026-07-13）。

姚祖怡 2026-07-09 批改发现：SC8 现状只展开直接子件，半成品（如 S02Y.0198）
不继续分解，其下真实原材料（如 R02A.0019）完全不进入计算。本测试覆盖
explode_bom_with_netting 的核心行为：半成品有货不深挖、无货/不够按净缺口
深挖、叶子件不抵扣，纯 mock 不触网。
"""
from __future__ import annotations

from zhuopin_platform.agents.kit_engine import explode_bom_with_netting
from zhuopin_platform.shared_tools.models import BomRow, ProductionPlan


def _bom_row(product, component, qty=1.0, loss=0.0):
    return BomRow(product_id=product, component_id=component, component_name=component,
                 level=1, qty_per_unit=qty, loss_rate=loss, unit="PCS")


def _plan(product, qty):
    return ProductionPlan(plan_id="P1", product_id=product, product_name=product,
                          planned_qty=qty, planned_date="2026-07-20")


def test_semi_finished_with_sufficient_stock_not_expanded():
    """半成品现货充足 → 不展开其子件，子件不出现在返回结果里。"""
    bom = [
        _bom_row("FIN", "SEMI"),          # 成品→半成品
        _bom_row("SEMI", "RAW1"),         # 半成品→原材料（若展开会出现在结果里）
    ]
    inventory = {"SEMI": 1000.0}          # 半成品现货远超需求
    gross = explode_bom_with_netting(bom, [_plan("FIN", 100)], inventory)
    assert gross == {}, "半成品现货够用，不应深挖其子件（RAW1 不应出现）"


def test_semi_finished_insufficient_stock_expands_by_net_shortage():
    """半成品现货不足 → 按净缺口（毛需求-现货）展开子件，非原始毛需求。"""
    bom = [_bom_row("FIN", "SEMI"), _bom_row("SEMI", "RAW1")]
    inventory = {"SEMI": 30.0}            # 需求100，现货30，净缺口70
    gross = explode_bom_with_netting(bom, [_plan("FIN", 100)], inventory)
    assert gross == {"RAW1": 70.0}


def test_semi_finished_no_inventory_record_expands_full_need():
    """半成品在 inventory 中无记录 → 视为现货0，按原始毛需求全额展开（保守兜底）。"""
    bom = [_bom_row("FIN", "SEMI"), _bom_row("SEMI", "RAW1")]
    gross = explode_bom_with_netting(bom, [_plan("FIN", 100)], inventory={})
    assert gross == {"RAW1": 100.0}


def test_leaf_material_not_netted():
    """叶子件（非子装配）不做现货抵扣，直接按毛需求累加，即便 inventory 里有它的现货记录。"""
    bom = [_bom_row("FIN", "RAW1")]
    inventory = {"RAW1": 1000.0}          # 叶子件现货充足也不应影响结果
    gross = explode_bom_with_netting(bom, [_plan("FIN", 100)], inventory)
    assert gross == {"RAW1": 100.0}, "叶子件是否够用交由下游判断，本函数不抵扣叶子件"


def test_yao_scenario_semi_finished_no_stock_raw_material_shortage_visible():
    """姚祖怡 S02Y.0035 场景复现：半成品无货、其原材料也缺货——应在结果中可见，
    不应像现状(level=1-only)一样被完全忽略而导致"假按期"。"""
    bom = [
        _bom_row("S02Y.0035", "SEMI_X", qty=1.0),
        _bom_row("SEMI_X", "R02A.0019", qty=2.0),   # 每个半成品需要2个该原材料
    ]
    inventory = {"SEMI_X": 0.0, "R02A.0019": 0.0}    # 半成品和原材料都无货
    gross = explode_bom_with_netting(bom, [_plan("S02Y.0035", 500)], inventory)
    assert gross == {"R02A.0019": 1000.0}, "半成品无货→净缺口500→需2倍原材料=1000，必须可见"


def test_multi_level_three_layers():
    """三层结构：成品→半成品A→半成品B→叶子件，逐层净额结转正确。"""
    bom = [
        _bom_row("FIN", "SEMI_A", qty=1.0),
        _bom_row("SEMI_A", "SEMI_B", qty=2.0),
        _bom_row("SEMI_B", "RAW1", qty=3.0),
    ]
    inventory = {"SEMI_A": 20.0, "SEMI_B": 5.0}   # A有部分货，B也有部分货
    # FIN需求100 → SEMI_A净缺口=100-20=80 → SEMI_B毛需求=80*2=160，净缺口=160-5=155
    # → RAW1 = 155*3 = 465
    gross = explode_bom_with_netting(bom, [_plan("FIN", 100)], inventory)
    assert gross == {"RAW1": 465.0}


def test_net_at_each_level_false_disables_netting_matches_explode_bom():
    """net_at_each_level=False 时退化为无条件展开（等同现有 explode_bom 行为）。"""
    bom = [_bom_row("FIN", "SEMI"), _bom_row("SEMI", "RAW1")]
    inventory = {"SEMI": 1000.0}   # 即便现货充足
    gross = explode_bom_with_netting(bom, [_plan("FIN", 100)], inventory, net_at_each_level=False)
    assert gross == {"RAW1": 100.0}, "关闭逐层净额时应无条件展开，不因现货而跳过"


def test_not_calling_function_means_explode_bom_unaffected():
    """确认 explode_bom（现状函数）本身逻辑不受影响——单独 import 验证签名未变。"""
    from zhuopin_platform.agents.kit_engine import explode_bom
    bom = [_bom_row("FIN", "SEMI"), _bom_row("SEMI", "RAW1")]
    gross = explode_bom(bom, [_plan("FIN", 100)])
    assert gross == {"RAW1": 100.0}, "explode_bom 现状行为（无条件展开）必须保持不变"
