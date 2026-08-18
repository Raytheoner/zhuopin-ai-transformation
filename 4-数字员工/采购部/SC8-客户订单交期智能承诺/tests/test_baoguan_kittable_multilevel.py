"""可齐套套数／需求日可齐套数量 多层穿透改造（队列 #266，2026-08-18）。

**根因**：C-2（`_kittable_qty`，2026-07-15）与 #14（`_demand_kittable_qty`，07-23）落地时
只扫描 `product_id == so.item_code` 的**第一层直接子件**。真实数据里 F 开头成品的第一层
子件本身就是半成品（如 `F02N.0224` → `S02Y.0197`、`F02N.0233` → `S02Y.0207`），而半成品是
自制件、不进 Stock API（该 API 只覆盖采购/外购叶子件），故 `inventory.get(半成品,0)` 恒为 0
→ 可齐套套数恒为 0、瓶颈恒锁定在半成品节点、缺口恒等于整单订货量——**这两个字段对这批
真实成品实质上从未产出过有意义的数字**。

**判定来源**：姚祖怡 2026-08-12 采购部#13 判例批改回件——判例 1（`F02N.0233`）❌、判例 2
（另 10 个 F 开头成品）❌、**判例 3（对照组 `S02Y.0210`，第一层即 R 开头采购件）✅ 维持现状**；
她在"反推规则"填空里亲手写下：改造为多层穿透、下钻到采购件层后重算。

**本文件覆盖**：① `_unit_usage` 单台用量穿透（含多层嵌套/循环防御/异常用量）
② `_kittable_qty` 穿透后不再恒 0 ③ `_demand_kittable_qty` 穿透后在途 PO 能被正确计入
④ **判例 3 零漂移**（第一层即叶子件时逐值与改造前完全相同，含损耗率非 0 的真实行）
⑤ 替代料跨层等价合并仍生效（与 #263 `_substitute_groups` 协同）。
"""
from __future__ import annotations

from datetime import date

from zhuopin_platform.shared_tools.models import BomRow

from sc8.baoguan import _demand_kittable_qty, _kittable_qty, _unit_usage
from sc8.models import SalesOrder

TODAY = date(2026, 8, 18)
SHIP = date(2026, 9, 20)


def _so(qty=1000, ship="2026-09-20", item="F1"):
    return SalesOrder(so_id="FO-1", customer_id="", customer_name="某OEM",
                      item_code=item, qty=qty, required_date=ship,
                      doc_type="预测订单", item_name="ECU")


def _row(component, *, product="F1", qty=1.0, sequence="", is_substitute=False,
         loss=0.0, level=1):
    return BomRow(product_id=product, component_id=component, component_name=component,
                 level=level, qty_per_unit=qty, loss_rate=loss, unit="PCS",
                 sequence=sequence, is_substitute=is_substitute)


# ── ① _unit_usage 单台用量穿透 ──────────────────────────────────────────────

def test_unit_usage_single_level_equals_qty_per_unit():
    """第一层即叶子件（判例 3 形态）：单台用量就是 qty_per_unit 本身。"""
    bom = [_row("R1", qty=2.0), _row("R2", qty=5.0)]
    assert _unit_usage(bom, "F1") == {"R1": 2.0, "R2": 5.0}


def test_unit_usage_penetrates_semi_finished_and_multiplies():
    """F1 →(3) S1 →(4) R1：单台用量应为 12，而不是把 S1 当成叶子件。"""
    bom = [_row("S1", product="F1", qty=3.0), _row("R1", product="S1", qty=4.0)]
    assert _unit_usage(bom, "F1") == {"R1": 12.0}


def test_unit_usage_two_level_nesting():
    """F1 →(2) S1 →(3) S2 →(5) R1 = 30。"""
    bom = [_row("S1", product="F1", qty=2.0), _row("S2", product="S1", qty=3.0),
           _row("R1", product="S2", qty=5.0)]
    assert _unit_usage(bom, "F1") == {"R1": 30.0}


def test_unit_usage_accumulates_same_leaf_from_multiple_paths():
    """同一叶子件经两条路径到达时用量累加（真实场景：R01I.0622 既在半成品下也可直挂）。"""
    bom = [_row("S1", product="F1", qty=2.0), _row("R1", product="S1", qty=3.0),
           _row("R1", product="F1", qty=1.0)]
    assert _unit_usage(bom, "F1") == {"R1": 7.0}


def test_unit_usage_ignores_substitute_path():
    """替代料不参与单台用量（与 `_gross_need` 的 main_bom 过滤同一口径）。"""
    bom = [_row("R1", qty=2.0, sequence="10"),
           _row("R9", qty=2.0, sequence="10", is_substitute=True)]
    assert _unit_usage(bom, "F1") == {"R1": 2.0}


def test_unit_usage_returns_none_on_non_positive_qty():
    """用量非正 = 数据异常，返回 None（保留改造前"不以 0 冒充"的语义）。"""
    assert _unit_usage([_row("R1", qty=0.0)], "F1") is None
    assert _unit_usage([_row("S1", qty=1.0), _row("R1", product="S1", qty=-1.0)], "F1") is None


def test_unit_usage_survives_bom_cycle():
    """BOM 循环引用不得导致无限递归（与 explode_bom 的 visited 防御同口径）。"""
    bom = [_row("S1", product="F1", qty=1.0), _row("S2", product="S1", qty=1.0),
           _row("S1", product="S2", qty=1.0), _row("R1", product="S2", qty=2.0)]
    assert _unit_usage(bom, "F1") == {"R1": 2.0}


def test_unit_usage_no_children_returns_empty():
    assert _unit_usage([_row("R1", product="OTHER")], "F1") == {}


# ── ② _kittable_qty 穿透后不再恒 0（判例 1/2 形态） ─────────────────────────

def test_kittable_penetrates_semi_finished_instead_of_zero():
    """**本次要修的真实缺陷**：第一层子件是半成品 S1，半成品无库存记录（自制件不进
    Stock API）。改造前 → floor(0/1)=0、瓶颈=S1、缺口=整单量；改造后应下钻到 R1 用真实
    现货算出有意义的数字。"""
    bom = [_row("S1", product="F1", qty=1.0), _row("R1", product="S1", qty=2.0)]
    inventory = {"R1": 900}          # S1 不在 inventory 里（半成品无现货记录）
    qty, bottleneck, shortfall = _kittable_qty(_so(qty=1000), bom, inventory)
    assert qty == 450                # floor(900 / 2)
    assert bottleneck == "R1"        # 瓶颈是真正的采购件，不是半成品
    assert shortfall == 1100         # 1000*2 - 900


def test_kittable_takes_min_across_penetrated_leaves():
    bom = [_row("S1", product="F1", qty=1.0), _row("R1", product="S1", qty=1.0),
           _row("R2", product="S1", qty=1.0), _row("R3", product="F1", qty=1.0)]
    inventory = {"R1": 800, "R2": 300, "R3": 5000}
    qty, bottleneck, shortfall = _kittable_qty(_so(qty=1000), bom, inventory)
    assert (qty, bottleneck, shortfall) == (300, "R2", 700)


def test_kittable_substitute_merge_still_applies_across_levels():
    """#263 跨层替代料分组 + 本次穿透协同：R1 的替代料 R1B 现货应等价合并计入。"""
    bom = [_row("S1", product="F1", qty=1.0),
           _row("R1", product="S1", qty=1.0, sequence="10"),
           _row("R1B", product="S1", qty=1.0, sequence="10", is_substitute=True)]
    qty, bottleneck, _ = _kittable_qty(_so(qty=1000), bom, {"R1": 400, "R1B": 350})
    assert qty == 750
    assert bottleneck == "R1"


def test_kittable_returns_none_when_no_components():
    assert _kittable_qty(_so(), [_row("R1", product="OTHER")], {"R1": 5}) == (None, None, None)


def test_kittable_returns_none_on_anomalous_usage():
    assert _kittable_qty(_so(), [_row("R1", qty=0.0)], {"R1": 5}) == (None, None, None)


# ── ③ _demand_kittable_qty 穿透后在途 PO 能被计入 ───────────────────────────

def test_demand_kittable_penetrates_and_counts_transit_po():
    """改造前：第一层是半成品 S1，`full_arrivals` 只含叶子件 → S1 查不到到货日 → 在途量
    永不计入 → 恒为 0。改造后应下钻到 R1，其到货日 ≤ 出货日 → 在途 PO 计入。"""
    bom = [_row("S1", product="F1", qty=1.0), _row("R1", product="S1", qty=2.0)]
    qty, bottleneck = _demand_kittable_qty(
        _so(qty=1000), bom, {"R1": 900}, {"R1": 1100},
        {"R1": date(2026, 9, 1)}, SHIP)
    assert qty == 1000               # floor((900+1100)/2)
    assert bottleneck == "R1"


def test_demand_kittable_excludes_po_arriving_after_ship():
    bom = [_row("S1", product="F1", qty=1.0), _row("R1", product="S1", qty=2.0)]
    qty, _ = _demand_kittable_qty(
        _so(qty=1000), bom, {"R1": 900}, {"R1": 1100},
        {"R1": date(2026, 10, 1)}, SHIP)      # 晚于出货日 → 不计入
    assert qty == 450


# ── ④ 判例 3 零漂移：第一层即叶子件时与改造前逐值相同 ───────────────────────

def test_case3_single_level_zero_drift_including_nonzero_loss_rate():
    """判例 3（`S02Y.0210`）＝第一层已是 R 开头采购件，姚祖怡批改为 ✅「维持现状不用动」。

    真实 BOM 里存在 `loss_rate=0.003` 的一层行（`S02Y.0035`→`R01D.0017`，本仓库实测
    4523 行中 2 行非 0）。改造前 `_kittable_qty` 用的是 **裸 `qty_per_unit`、不乘
    (1+损耗率)**；本次穿透沿用同一口径，故该行结果不得因改造而漂移。
    """
    bom = [_row("R1", qty=26.0, loss=0.003), _row("R2", qty=1.0)]
    qty, bottleneck, shortfall = _kittable_qty(_so(qty=100), bom, {"R1": 2600, "R2": 5000})
    assert qty == 100                # floor(2600/26)，若误乘 1.003 则为 99
    assert bottleneck == "R1"
    assert shortfall == 0            # 100*26 - 2600，若误乘损耗则为正数


def test_case3_tie_break_keeps_first_bom_row():
    """并列最小值时仍取 BOM 里靠前那一行（改造前 `<` 严格比较的既有行为）。"""
    bom = [_row("R1", qty=1.0), _row("R2", qty=1.0)]
    _, bottleneck, _ = _kittable_qty(_so(qty=10), bom, {"R1": 5, "R2": 5})
    assert bottleneck == "R1"
