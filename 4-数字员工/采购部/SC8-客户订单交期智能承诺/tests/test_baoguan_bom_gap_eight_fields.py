"""BOM 缺口物料清单八字段整体呈现（队列 #152，姚祖怡三次重申：07-26 V6 #18-a →
07-28 判例回件 → 07-29 第三次）——本文件锁住这个"整体验收单位"本身。

根因：八字段此前散落在三条任务（#118①可用现货数量 / #151缺口数量 / #139②答交
数量·日期），从未有一条任务的验收标准是"八字段整体齐"。本文件覆盖：
  ④⑥ available_qty/gap_qty 计算 + #151 展示层过滤（不改 gross/kittable 计算输入）
  ⑦⑧ 答交数量/日期不再静默回退到已指认取错源头的旧字段（confirmed_date/PO答交口径）
  八字段整体呈现（真表格渲染）
"""
from __future__ import annotations

from datetime import date

from zhuopin_platform.shared_tools.models import BomRow, SrmDeliveryOrder

from sc8.baoguan import _component_supply_status, assess_supply_risk, render_html, row_to_dict
from sc8.forecast import MaterialArrivals
from sc8.models import SalesOrder

TODAY = date(2026, 8, 1)


def _so(item="P1", qty=100, ship="2026-09-01"):
    return SalesOrder(so_id=f"FO-{item}", customer_id="", customer_name="某OEM",
                      item_code=item, qty=qty, required_date=ship,
                      doc_type="预测订单", item_name="ECU")


def _row(product, component, *, name=None, qty_per_unit=1.0):
    return BomRow(product_id=product, component_id=component,
                 component_name=name if name is not None else component,
                 level=1, qty_per_unit=qty_per_unit, loss_rate=0.0, unit="PCS")


def _srm(material, committed):
    return SrmDeliveryOrder(delivery_id=f"SRM-{material}", demand_id="", supplier_id="",
                            material_id=material, qty_committed=0,
                            committed_date=committed, status="confirmed")


# ── _component_supply_status 白盒单测：available_qty/gap_qty + #151 过滤 ──────

def test_component_supply_status_computes_available_and_gap_qty():
    """④可用现货数量/⑥缺口数量＝调用方传入的净额与 qty_needed 之差（姚祖怡定义逐字对应，
    示例数量与其原话一致：需求900、现货784→缺口116）。"""
    mat = MaterialArrivals(arrivals={"A": date(2026, 8, 20)}, no_feedback_materials=[],
                           bottleneck_material="A", has_bom=True)
    out = _component_supply_status(mat, gross={"A": 900.0}, names={"A": "电容"},
                                   purchase_orders={"A": 0.0}, inventory={"A": 784.0})
    assert len(out) == 1
    s = out[0]
    assert s.available_qty == 784.0
    assert s.gap_qty == 116.0


def test_component_supply_status_filters_out_non_positive_gap():
    """#151：缺口≤0 的子件不进入返回列表（展示层过滤），姚祖怡 07-26 V6 回件原文签认
    "缺口数量如≤0，则该行视为满足齐套需求，不应该体现在缺料子件中"。"""
    mat = MaterialArrivals(arrivals={"A": date(2026, 8, 20), "B": date(2026, 8, 20)},
                           no_feedback_materials=[], bottleneck_material="A", has_bom=True)
    out = _component_supply_status(mat, gross={"A": 100.0, "B": 100.0}, names={},
                                   purchase_orders={"A": 0.0, "B": 0.0},
                                   inventory={"A": 100.0, "B": 150.0})  # A缺口=0，B缺口=-50
    assert out == []   # 两条都被过滤，不出现在展示清单里


def test_component_supply_status_gap_filter_does_not_mutate_gross_input():
    """锁住展示/计算分离：过滤只影响返回列表本身，不改写/不消耗调用方传入的 gross。"""
    gross = {"A": 100.0}
    mat = MaterialArrivals(arrivals={"A": date(2026, 8, 20)}, no_feedback_materials=[],
                           bottleneck_material="A", has_bom=True)
    _component_supply_status(mat, gross=gross, names={}, purchase_orders={"A": 0.0},
                             inventory={"A": 100.0})
    assert gross == {"A": 100.0}   # 调用前后原样不变


def test_component_supply_status_available_and_gap_none_without_inventory():
    """inventory 缺省（净额开关关/无库存数据）→ available_qty/gap_qty 恒为 None，不做
    任何过滤（零漂移，与既有 kittable_qty 等字段"不以 0 冒充"同一约定）。"""
    mat = MaterialArrivals(arrivals={"A": date(2026, 8, 20)}, no_feedback_materials=[],
                           bottleneck_material="A", has_bom=True)
    out = _component_supply_status(mat, gross={"A": 100.0}, names={},
                                   purchase_orders={"A": 0.0})
    assert len(out) == 1
    assert out[0].available_qty is None and out[0].gap_qty is None


# ── assess_supply_risk 集成：inventory 只在净额开关生效时才传入 _component_supply_status ──

def test_assess_supply_risk_wires_available_gap_qty_when_net_inventory_on(monkeypatch):
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(item="S1", qty=900)
    bom = [_row("S1", "R01B.0115", name="连接器", qty_per_unit=1.0)]
    row = assess_supply_risk(so, bom, [], today=TODAY,
                             inventory={"R01B.0115": 784.0}, purchase_orders={"R01B.0115": 3000.0})
    s = row.component_status[0]
    assert s.available_qty == 784.0
    assert s.gap_qty == 116.0


def test_assess_supply_risk_available_gap_qty_none_when_net_inventory_off():
    so = _so(item="S1", qty=900)
    bom = [_row("S1", "A", qty_per_unit=1.0)]
    row = assess_supply_risk(so, bom, [], today=TODAY, purchase_orders={"A": 3000.0})
    s = row.component_status[0]
    assert s.available_qty is None and s.gap_qty is None


# ── row_to_dict 序列化 ────────────────────────────────────────────────────

def test_row_to_dict_serializes_available_and_gap_qty(monkeypatch):
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(item="S1", qty=900)
    bom = [_row("S1", "A", qty_per_unit=1.0)]
    row = assess_supply_risk(so, bom, [], today=TODAY,
                             inventory={"A": 784.0}, purchase_orders={"A": 3000.0})
    d = row_to_dict(row)
    assert d["cst"][0]["aq"] == 784.0
    assert d["cst"][0]["gq"] == 116.0


# ── 八字段整体呈现：HTML 真表格渲染 + 答交源头修复 ──────────────────────────

def test_render_html_bom_gap_list_is_a_real_table_with_eight_columns():
    """队列 #152：BOM 缺口物料清单改真表格渲染（表格对齐+子件上下行对齐+自动换行由
    .cst-table CSS 承载），八个表头字段一次性齐全，不再分散在三条任务里各展示一部分。"""
    so = _so(item="S1", qty=900)
    bom = [_row("S1", "A", name="电容")]
    rows = [assess_supply_risk(so, bom, [], today=TODAY, purchase_orders={"A": 20})]
    html = render_html(rows, today=TODAY)
    assert 'class="cst-table"' in html
    for header in ("料号", "品名", "状态", "可用现货数量", "本项目需求数量",
                   "缺口数量", "答交数量", "答交日期"):
        assert header in html


def test_answer_qty_and_date_show_none_instead_of_falling_back_to_stale_po_answer():
    """根治姚祖怡三次重申的取数源头 bug：cb（SRM 供应计划口径，真实数据源）为空时，
    前端如实显示"无"，不再静默回退到 cd（/purchase/answer 整单口径，姚祖怡 07-29 指认
    这正是 S02Y.0135/R01B.0115 显示错误答交日期 2026-08-20 的源头）——旧写法一旦
    cb 因 SRM"7天前数据不可查"限制取不到，就会让这个已知不准的旧值悄悄顶替上场，
    是"看起来像修好了却还在犯同一个错"的三次重申根因。"""
    so = _so(item="S1", qty=100)
    bom = [_row("S1", "A", name="电容")]
    # 有 SRM 承诺（confirmed_date 命中，走 /purchase/answer 分层取数）但未传
    # material_commitments → confirmed_batches 恒为空，复现真实生产场景（SRM 供应
    # 计划板 7 天查询限制导致 cb 取不到）。
    rows = [assess_supply_risk(so, bom, [_srm("A", "2026-08-20")],
                               today=TODAY, purchase_orders={"A": 100.0})]
    d = row_to_dict(rows[0])
    assert d["cst"][0]["cd"] == "2026-08-20"   # 旧字段仍序列化（内部排障参考）……
    assert d["cst"][0]["cb"] == []             # ……但真实展示源（cb）确实为空
    html = render_html(rows, today=TODAY)
    assert "answerQtyText(s)" in html and "answerDateText(s)" in html
    # 旧回退写法的可执行代码模式（三元判断+esc(s.cd)）已彻底消失——s.cd 仅在解释性
    # 中文注释里被提及（说明为什么不再用它），不再出现在任何可执行 JS 代码路径里。
    assert "esc(s.cd)" not in html and "s.cd?" not in html
