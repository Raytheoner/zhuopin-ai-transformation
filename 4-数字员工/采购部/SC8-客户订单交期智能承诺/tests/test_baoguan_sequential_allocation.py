"""#118 批2·优先级分配引擎首版：跨订单共享现货池按优先级依次扣减（队列 #118/#147④，
2026-07-29 Paul 拍板）。

真实案例（S02Y.0210）：同一料号被 3 张需求单（600/400/500 套，出货
07-20/08-20/09-20）共同争用现货 1,153 件，此前 `_kittable_qty`/`_covered_by_stock`
各自独立读取现货全量，3 行都判"齐套"，但 600+400+500=1,500 > 1,153，实际第三行
不该判齐——姚祖怡 07-29 指出"必须逐级扣料"。

临时优先级＝出货日期升序（PMC 真实优先级表 #15 尚未上线，Paul 07-29 拍板用此代替，
#15 上线后传入真实 `priority_resolver` 即自动切换）。
"""
from __future__ import annotations

from datetime import date

from zhuopin_platform.shared_tools.models import BomRow

from sc8.baoguan import (RISK_GREEN, RISK_RED, _allocate_sequential_inventory,
                         assess_supply_risk, build_dashboard)
from sc8.models import SalesOrder

TODAY = date(2026, 7, 29)


def _so(so_id, item="S02Y.0210", qty=1000, ship="2026-09-01"):
    return SalesOrder(so_id=so_id, customer_id="", customer_name="上海东风汽车进出口有限公司",
                      item_code=item, qty=qty, required_date=ship,
                      doc_type="预测订单", item_name="EQ43-1-C2_PCBA")


def _bom(product="S02Y.0210", component="R01X.0001", qty_per_unit=1.0):
    return [BomRow(product_id=product, component_id=component, component_name=component,
                   level=1, qty_per_unit=qty_per_unit, loss_rate=0.0, unit="PCS")]


# ── _allocate_sequential_inventory 直接单测 ─────────────────────────────────

def test_no_competition_leaves_inventory_untouched():
    """单一订单独占某物料 → 该物料键原样保留全量库存，不受影响（向后兼容）。"""
    so = _so("SO-1")
    bom = _bom()
    effective = _allocate_sequential_inventory([so], bom, {"R01X.0001": 500.0})
    assert effective[0]["R01X.0001"] == 500.0


def test_two_orders_share_pool_earlier_ship_date_first():
    """2 张单争用同一物料，出货早的先拿满额，出货晚的只拿剩余。"""
    early = _so("SO-EARLY", ship="2026-07-20", qty=600)
    late = _so("SO-LATE", ship="2026-08-20", qty=600)
    bom = _bom()
    effective = _allocate_sequential_inventory([late, early], bom, {"R01X.0001": 800.0})
    # early 在 orders[1]，先处理：拿到全量 800（分配前快照），消耗 600（毛需求=qty*qty_per_unit=600）
    assert effective[1]["R01X.0001"] == 800.0
    # late 在 orders[0]，后处理：只剩 800-600=200
    assert effective[0]["R01X.0001"] == 200.0


def test_allocation_does_not_grant_surplus_beyond_need():
    """占用仅按需求数量、不含富余（Paul 07-28 拍板口径）：早订单需求小于池子时，
    只扣自己的需求量，剩余留给下一顺位，不会因为"反正池子够"就多占。"""
    early = _so("SO-EARLY", ship="2026-07-20", qty=100)   # 只需要 100
    late = _so("SO-LATE", ship="2026-08-20", qty=500)
    bom = _bom()
    effective = _allocate_sequential_inventory([early, late], bom, {"R01X.0001": 1000.0})
    assert effective[0]["R01X.0001"] == 1000.0   # early：分配前快照仍是全量
    assert effective[1]["R01X.0001"] == 900.0     # late：只扣了 early 实际需求 100


def test_priority_resolver_overrides_ship_date_default():
    """传入真实 priority_resolver（#15 上线后）时改由它决定顺序，不再按出货日期。"""
    early = _so("SO-EARLY", ship="2026-07-20", qty=600)
    late = _so("SO-LATE", ship="2026-08-20", qty=600)
    bom = _bom()

    def _resolver(material_id, competing_so_ids):
        return ["SO-LATE", "SO-EARLY"]   # 强制 LATE 优先（模拟真实 PMC 优先级）

    effective = _allocate_sequential_inventory([early, late], bom, {"R01X.0001": 800.0},
                                               priority_resolver=_resolver)
    assert effective[1]["R01X.0001"] == 800.0     # late（orders[1]）现在先拿满额
    assert effective[0]["R01X.0001"] == 200.0     # early（orders[0]）只剩余量


def test_priority_resolver_same_so_id_multiple_lines_falls_back_to_original_order():
    """真实数据踩坑复现：同一 FO 文档下多个行项共享同一个 so_id，priority_resolver
    接口粒度只到 so_id、无法区分——多个下标应按其在 orders 中的原始相对顺序二级排序，
    而不是被 so_id 意外去重/合并成一条（首版用 dict[so_id] 时的真实生产 bug）。"""
    line1 = _so("FO-1", ship="2026-07-20", qty=600)   # 同一 FO 的第 1 行
    line2 = _so("FO-1", ship="2026-08-20", qty=400)   # 同一 FO 的第 2 行，so_id 相同
    line3 = _so("FO-1", ship="2026-09-20", qty=500)   # 同一 FO 的第 3 行，so_id 相同
    bom = _bom()

    def _resolver(material_id, competing_so_ids):
        return ["FO-1"]   # 真实 resolver 接口粒度到 so_id，3 行都映射到同一个 id

    effective = _allocate_sequential_inventory([line1, line2, line3], bom,
                                               {"R01X.0001": 1153.0},
                                               priority_resolver=_resolver)
    # 3 行不能被折叠成 1 条：仍应按原始出现顺序（line1→line2→line3）依次扣减
    assert effective[0]["R01X.0001"] == 1153.0          # line1 先拿满额
    assert effective[1]["R01X.0001"] == 1153.0 - 600     # line2：扣掉 line1 的 600
    assert effective[2]["R01X.0001"] == 1153.0 - 600 - 400   # line3：再扣掉 line2 的 400


def test_no_inventory_data_for_material_skips_allocation():
    """物料不在 inventory 字典里（无数据）→ 该键不参与分配，各行也不会凭空得到 0。"""
    so1, so2 = _so("SO-1", ship="2026-07-20"), _so("SO-2", ship="2026-08-20")
    bom = _bom()
    effective = _allocate_sequential_inventory([so1, so2], bom, {})
    assert "R01X.0001" not in effective[0]
    assert "R01X.0001" not in effective[1]


# ── build_dashboard 集成测试：真实 S02Y.0210 三行同构场景 ────────────────────

def test_real_case_three_orders_exceed_pool_third_line_not_kittable(monkeypatch):
    """真实案例复现（姚祖怡 07-29 举证，队列 #118）：600+400+500=1500 > 1153 现货，
    按出货日期升序（07-20/08-20/09-20）依次扣减后，第三行不应再判"现货齐备"。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so_a = _so("SO-A", qty=600, ship="2026-07-20")
    so_b = _so("SO-B", qty=400, ship="2026-08-20")
    so_c = _so("SO-C", qty=500, ship="2026-09-20")
    bom = _bom()
    rows = build_dashboard([so_a, so_b, so_c], bom, [], today=TODAY,
                           inventory={"R01X.0001": 1153.0})
    by_id = {r.so_id: r for r in rows}
    # A: 600 <= 1153 → 现货齐备
    assert by_id["SO-A"].risk == RISK_GREEN
    # B: 累计 600+400=1000 <= 1153 → 仍齐备
    assert by_id["SO-B"].risk == RISK_GREEN
    # C: 累计 600+400+500=1500 > 1153 → 剩余 153 < 500 需求，不再齐备（此前误判齐套的根因）
    assert by_id["SO-C"].risk != RISK_GREEN
    assert by_id["SO-C"].kittable_qty == 153   # floor(153/1.0)，只能先齐 153 套


def test_real_case_same_fo_document_shares_one_so_id_across_lines(monkeypatch):
    """真实数据的实际形态（比上一条更贴近生产）：3 行需求属于**同一张预测订单
    文档**、so_id 完全相同（`fo_to_sales_orders` 按 fo.fo_id 赋值，不是逐行唯一）——
    这正是 2026-07-29 真实部署验证时发现"kq 恒为 1153、逐级扣料完全没生效"的
    真实数据形态，必须单独覆盖，不能只测 so_id 各不相同的简化场景。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    line1 = _so("FO2026070001", qty=600, ship="2026-07-20")
    line2 = _so("FO2026070001", qty=400, ship="2026-08-20")
    line3 = _so("FO2026070001", qty=500, ship="2026-09-20")
    bom = _bom()
    rows = build_dashboard([line1, line2, line3], bom, [], today=TODAY,
                           inventory={"R01X.0001": 1153.0})
    assert len(rows) == 3   # 3 行不能被 so_id 相同静默折叠/丢失
    rows_by_ship = sorted(rows, key=lambda r: r.ship_date)
    assert rows_by_ship[0].risk == RISK_GREEN     # 600 <= 1153
    assert rows_by_ship[1].risk == RISK_GREEN     # 累计 1000 <= 1153
    assert rows_by_ship[2].risk != RISK_GREEN     # 累计 1500 > 1153，第三行不再齐备
    assert rows_by_ship[2].kittable_qty == 153


def test_real_case_kittable_qty_reflects_depleted_pool(monkeypatch):
    """assess_supply_risk 单独调用时同样吃到分配后的有效库存（build_dashboard 统一注入）。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so_c = _so("SO-C", qty=500, ship="2026-09-20")
    bom = _bom()
    # 直接给 SO-C 分配后剩余的 153（模拟 build_dashboard 内部已完成分配后传入的视图）
    row = assess_supply_risk(so_c, bom, [], today=TODAY, inventory={"R01X.0001": 153.0})
    assert row.kittable_qty == 153
    assert row.risk != RISK_GREEN


def test_net_inventory_off_ignores_allocation_entirely(monkeypatch):
    """净额开关 OFF（默认）→ 不分配、inventory 被完全忽略，行为与改造前一致（零漂移）。"""
    monkeypatch.delenv("SC8_NET_INVENTORY", raising=False)
    so_a = _so("SO-A", qty=600, ship="2026-07-20")
    so_c = _so("SO-C", qty=500, ship="2026-09-20")
    bom = _bom()
    rows = build_dashboard([so_a, so_c], bom, [], today=TODAY,
                           inventory={"R01X.0001": 1153.0})
    # 开关关闭时 inventory 被忽略，两行均因无 SRM 承诺按无答复保守估算判红（队列#147续）
    assert all(r.risk == RISK_RED for r in rows)
