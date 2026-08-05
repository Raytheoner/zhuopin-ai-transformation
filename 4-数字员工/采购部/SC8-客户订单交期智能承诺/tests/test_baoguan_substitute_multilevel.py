"""替代料关系多层穿透（队列 #263，2026-08-05，根因由 #213 真实举证坐实）。

C-1（sc8-baoguan-substitute-partial-kit，2026-07-15）落地时 `_substitute_groups`
只扫描成品**直属**行，替代料若定义在半成品子件**自己的** BOM 里则永远看不到——
真实案例 `F02N.0233`：替代关系 `R01A.0707`↔`R01A.0012` 定义在半成品子件
`S02Y.0207` 自己的 BOM 里，此前误判为缺口（该替代料从未被纳入齐套判定）。

本文件覆盖：① `_bom_subtree_product_ids` 半成品闭包收集 ② `_substitute_groups`
跨层级分组 ③ 端到端 `assess_supply_risk` 复现真实场景 ④ 序号跨产品碰撞不误并组
（分组键改用 (product_id, sequence)）⑤ 单层 BOM 零漂移（与改造前完全一致）。
"""
from __future__ import annotations

from datetime import date

from zhuopin_platform.shared_tools.models import BomRow

from sc8.baoguan import (RISK_GREEN, RISK_RED, _bom_subtree_product_ids,
                         _gross_need, _substitute_groups, assess_supply_risk)
from sc8.models import SalesOrder

TODAY = date(2026, 8, 1)


def _so(qty=1000, ship="2026-09-01", item="F1"):
    return SalesOrder(so_id="FO-1", customer_id="", customer_name="某OEM",
                      item_code=item, qty=qty, required_date=ship,
                      doc_type="预测订单", item_name="ECU")


def _row(component, *, sequence="", is_substitute=False, qty=1.0, product="F1"):
    return BomRow(product_id=product, component_id=component, component_name=component,
                 level=1, qty_per_unit=qty, loss_rate=0.0, unit="PCS",
                 sequence=sequence, is_substitute=is_substitute)


# ── ① _bom_subtree_product_ids ──────────────────────────────────────────────

def test_subtree_includes_self_when_no_semi_finished():
    bom = [_row("A", sequence="10")]
    assert _bom_subtree_product_ids(bom, "F1") == {"F1"}


def test_subtree_includes_nested_semi_finished_component():
    """F1 的直接子件 S1 本身也是产品(自己有 BOM 行) → S1 计入闭包。"""
    bom = [
        _row("S1", sequence="10", product="F1"),          # F1 → S1（半成品）
        _row("R1", sequence="120", product="S1"),          # S1 → R1（叶子件）
    ]
    assert _bom_subtree_product_ids(bom, "F1") == {"F1", "S1"}


def test_subtree_does_not_recurse_through_substitute_path():
    """S1（主料路径）与 S2（替代料路径）都各自是半成品（都有自己的子件），但只有
    经主料路径可达的 S1 应计入闭包——与 `_gross_need` 的 `main_bom` 过滤同一口径。"""
    bom = [
        _row("S1", sequence="10", product="F1", is_substitute=False),
        _row("S2", sequence="10", product="F1", is_substitute=True),   # 替代路径
        _row("R1", sequence="20", product="S1"),   # 证明 S1 自己也有子件（是半成品）
        _row("R2", sequence="20", product="S2"),   # 证明 S2 自己也有子件（是半成品）
    ]
    subtree = _bom_subtree_product_ids(bom, "F1")
    assert subtree == {"F1", "S1"}
    assert "S2" not in subtree


def test_subtree_multi_level_depth_two():
    """F1 → S1 → S2 → R1（两层半成品嵌套），闭包应包含全部三层产品节点。"""
    bom = [
        _row("S1", sequence="10", product="F1"),
        _row("S2", sequence="10", product="S1"),
        _row("R1", sequence="10", product="S2"),
    ]
    assert _bom_subtree_product_ids(bom, "F1") == {"F1", "S1", "S2"}


# ── ② _substitute_groups 跨层级分组 ─────────────────────────────────────────

def test_substitute_groups_found_in_direct_row_still_works():
    """单层场景（改造前既有行为）：分组键退化为等价，零漂移。"""
    bom = [_row("A", sequence="10", is_substitute=False),
          _row("B", sequence="10", is_substitute=True)]
    assert _substitute_groups(bom, "F1") == {"A": ["B"]}


def test_substitute_groups_found_in_nested_semi_finished_bom():
    """#263 核心场景：替代关系定义在半成品子件 S1 自己的 BOM 里（非 F1 直属行）。"""
    bom = [
        _row("S1", sequence="10", product="F1", is_substitute=False),   # F1 → S1
        _row("R01A.0707", sequence="120", product="S1", is_substitute=False),  # S1 内主料
        _row("R01A.0012", sequence="120", product="S1", is_substitute=True),   # S1 内替代料
    ]
    assert _substitute_groups(bom, "F1") == {"R01A.0707": ["R01A.0012"]}


def test_sequence_collision_across_products_not_merged():
    """F1 直属行与半成品 S1 内部行恰好用了同一个 sequence 编号——分组键必须区分
    product_id，否则会把两个完全无关的料位误并成一组（回归此前用纯 sequence
    分组时的隐患）。"""
    bom = [
        _row("X", sequence="10", product="F1", is_substitute=False),   # F1 seq10 主料
        _row("Y", sequence="10", product="F1", is_substitute=True),    # F1 seq10 替代
        _row("S1", sequence="20", product="F1", is_substitute=False),  # F1 → S1
        _row("R01A.0707", sequence="10", product="S1", is_substitute=False),  # S1 seq10（同号不同产品）
        _row("R01A.0012", sequence="10", product="S1", is_substitute=True),
    ]
    groups = _substitute_groups(bom, "F1")
    assert groups == {"X": ["Y"], "R01A.0707": ["R01A.0012"]}
    assert "R01A.0707" not in groups.get("X", [])   # 确认未被误并


def test_no_semi_finished_no_change():
    """无半成品的普通 BOM：分组结果与改造前完全一致。"""
    bom = [_row("A", sequence="10"), _row("C", sequence="20")]
    assert _substitute_groups(bom, "F1") == {}


# ── ③ 端到端复现真实案例 F02N.0233（R01A.0707 ↔ R01A.0012 定义在 S02Y.0207 里）──

def test_end_to_end_real_case_f02n0233_substitute_stock_now_recognized(monkeypatch):
    """净额开关 ON：主料 R01A.0707 现货不足，改造前该缺口不可见替代料 R01A.0012，
    判"待催"；改造后正确识别组内替代料现货，合计判齐。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(qty=1000, item="F02N.0233")
    bom = [
        _row("S02Y.0207", sequence="10", product="F02N.0233", qty=1.0),
        _row("R01A.0707", sequence="120", product="S02Y.0207",
            is_substitute=False, qty=1.0),
        _row("R01A.0012", sequence="120", product="S02Y.0207",
            is_substitute=True, qty=1.0),
    ]
    # 毛需求（多层递归，F02N.0233×1000 → S02Y.0207×1000 → R01A.0707×1000）
    need = _gross_need(so, bom)
    assert need == {"R01A.0707": 1000.0}

    # R01A.0707 现货 200 不足，R01A.0012（替代）现货 900 → 合计 1100 ≥ 1000，判齐
    r = assess_supply_risk(so, bom, srm_deliveries=[], today=TODAY,
                          inventory={"R01A.0707": 200, "R01A.0012": 900})
    assert r.substitute_groups == {"R01A.0707": ["R01A.0012"]}
    assert "R01A.0707" not in r.no_feedback_materials
    assert "R01A.0012" not in r.no_feedback_materials


def test_end_to_end_real_case_without_substitute_stock_still_short(monkeypatch):
    """对照组：若替代料现货不够，即便本次修复生效，缺口判定依然正确保留
    （不因为"能看到替代料"就总是判齐）。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(qty=1000, item="F02N.0233")
    bom = [
        _row("S02Y.0207", sequence="10", product="F02N.0233", qty=1.0),
        _row("R01A.0707", sequence="120", product="S02Y.0207",
            is_substitute=False, qty=1.0),
        _row("R01A.0012", sequence="120", product="S02Y.0207",
            is_substitute=True, qty=1.0),
    ]
    r = assess_supply_risk(so, bom, srm_deliveries=[], today=TODAY,
                          inventory={"R01A.0707": 200, "R01A.0012": 100})
    assert "R01A.0707" in r.no_feedback_materials
    assert r.risk == RISK_RED
