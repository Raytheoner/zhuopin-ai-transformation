"""#118 优先级判据补全 ②③ 级（队列 #118，2026-08-18，姚祖怡 2026-08-12 采购部#13 新问题 4）。

**背景**：2026-07-29 首版建造时 Paul 当面拍板"先用出货日期早晚当临时优先级"，故当时只
实现了第 ① 级。姚祖怡 2026-08-12 回件把预测订单优先级判据**一次写全**：

  ① 计划出货日期在前的优先（举例：2026-08-10 高于 2026-08-20）——首版已实现；
  ② **出货日期相同则 ERP 预测订单数量大的优先**（她的举例：同为 2026-08-10 的
     `F02N.0224` 数量 1100 与 `F02N.0226` 数量 600，F02N.0224 优先）——本次新增；
  ③ **数量与出货日期都相同则按取值的自然顺序，先取值的先占用**——本次新增（＝
     `orders` 列表原始下标顺序，首版恰好靠 `i` 二级排序满足，本次显式化并加测试锁定）。

**边界（如实登记）**：她这三级是否即 #15「真实 PMC 优先级表」的最终形态、还是仍需 PMC 侧
表格覆盖，她本次未提 —— 故本次**不动 `priority_resolver` 的优先地位**：传入真实 resolver 时
仍以 resolver 给的 so_id 次序为准，②③ 只作为**同一 so_id 内多行项**（resolver 接口粒度到
so_id、对行项无法区分）与**无 resolver 兜底**时的排序判据。
"""
from __future__ import annotations

from datetime import date

from zhuopin_platform.shared_tools.models import BomRow

from sc8.baoguan import _allocate_sequential_inventory, _resolve_priority_order
from sc8.models import SalesOrder

TODAY = date(2026, 8, 18)


def _so(so_id, item="F02N.0224", qty=1000, ship="2026-08-10"):
    return SalesOrder(so_id=so_id, customer_id="", customer_name="深圳立达",
                      item_code=item, qty=qty, required_date=ship,
                      doc_type="预测订单", item_name="ECU")


def _bom(product, component="R01X.0001", qty_per_unit=1.0):
    return [BomRow(product_id=product, component_id=component, component_name=component,
                   level=1, qty_per_unit=qty_per_unit, loss_rate=0.0, unit="PCS")]


# ── ① 出货日期在前优先（首版既有，回归锁定） ────────────────────────────────

def test_level1_earlier_ship_date_wins():
    a = _so("FO-A", ship="2026-08-20", qty=100)
    b = _so("FO-B", ship="2026-08-10", qty=100)
    assert _resolve_priority_order("R01X.0001", [0, 1], [a, b], None) == [1, 0]


# ── ② 出货日期相同 → 数量大的优先（本次新增，用她的真实举证） ────────────────

def test_level2_same_ship_date_larger_qty_wins_real_case():
    """姚祖怡真实举证：同为 2026-08-10，F02N.0224 数量 1100 应优先于 F02N.0226 数量 600。"""
    f0226 = _so("FO2026080002", item="F02N.0226", qty=600, ship="2026-08-10")
    f0224 = _so("FO2026080002", item="F02N.0224", qty=1100, ship="2026-08-10")
    # 即便数量小的那行在列表里排在前面，也应让数量大的先占用
    assert _resolve_priority_order("R01X.0001", [0, 1], [f0226, f0224], None) == [1, 0]


def test_level2_does_not_override_level1():
    """数量大但出货日期晚 → 仍排在后面（② 只在 ① 相同时才生效）。"""
    late_big = _so("FO-A", qty=5000, ship="2026-09-20")
    early_small = _so("FO-B", qty=10, ship="2026-08-10")
    assert _resolve_priority_order("R01X.0001", [0, 1], [late_big, early_small], None) == [1, 0]


# ── ③ 日期与数量都相同 → 取值自然顺序 ───────────────────────────────────────

def test_level3_same_date_and_qty_keeps_natural_order():
    a = _so("FO-A", qty=500, ship="2026-08-10")
    b = _so("FO-B", qty=500, ship="2026-08-10")
    c = _so("FO-C", qty=500, ship="2026-08-10")
    assert _resolve_priority_order("R01X.0001", [0, 1, 2], [a, b, c], None) == [0, 1, 2]


def test_three_levels_combined():
    """混合场景：先按日期，再按数量降序，最后按自然顺序。"""
    o0 = _so("O0", qty=100, ship="2026-08-20")
    o1 = _so("O1", qty=300, ship="2026-08-10")
    o2 = _so("O2", qty=900, ship="2026-08-10")
    o3 = _so("O3", qty=300, ship="2026-08-10")
    got = _resolve_priority_order("R01X.0001", [0, 1, 2, 3], [o0, o1, o2, o3], None)
    assert got == [2, 1, 3, 0]      # 900 → 300(先出现) → 300(后出现) → 08-20 那张


# ── ②③ 在真实扣减链路里生效 ────────────────────────────────────────────────

def test_allocation_gives_pool_to_larger_qty_first_on_same_ship_date():
    """现货 1000：同日 F02N.0224(1100) 应先拿，F02N.0226(600) 只能拿剩下的 0。"""
    f0226 = _so("FO2026080002", item="F02N.0226", qty=600, ship="2026-08-10")
    f0224 = _so("FO2026080002", item="F02N.0224", qty=1100, ship="2026-08-10")
    bom = _bom("F02N.0226") + _bom("F02N.0224")
    effective = _allocate_sequential_inventory([f0226, f0224], bom, {"R01X.0001": 1000.0})
    assert effective[1]["R01X.0001"] == 1000.0        # F02N.0224 先占，看到全量
    assert effective[0]["R01X.0001"] == 0.0           # F02N.0226 后占，已被吃光


# ── resolver 优先地位不变（真实 PMC 表 #15 上线后仍以其为准） ────────────────

def test_resolver_still_outranks_qty_criteria():
    """resolver 明确给出 so_id 次序时，②③ 不得反超它。"""
    big_early = _so("FO-A", qty=9999, ship="2026-08-10")
    small_late = _so("FO-B", qty=1, ship="2026-08-10")

    def _resolver(material_id, competing_so_ids):
        return ["FO-B", "FO-A"]      # PMC 表明确要求 B 先

    assert _resolve_priority_order("R01X.0001", [0, 1], [big_early, small_late],
                                   _resolver) == [1, 0]


def test_resolver_same_so_id_lines_use_new_criteria_as_tiebreak():
    """resolver 粒度只到 so_id，同一 FO 下多行项无从区分 → 用 ①②③ 作二级判据
    （而不是仅按原始下标），与无 resolver 时口径一致。"""
    line1 = _so("FO-1", qty=600, ship="2026-08-10")
    line2 = _so("FO-1", qty=900, ship="2026-08-10")     # 同日、数量更大 → 应先占
    line3 = _so("FO-1", qty=400, ship="2026-07-20")     # 出货更早 → 最先

    def _resolver(material_id, competing_so_ids):
        return ["FO-1"]

    assert _resolve_priority_order("R01X.0001", [0, 1, 2], [line1, line2, line3],
                                   _resolver) == [2, 1, 0]
