"""保供看板功能批1（姚祖怡 07-23，队列 #87④/开场prompt-保供看板功能批1）：

  ③ 料品名称（component_names，跨全部层级，纯展示）
  #12 子件供给状态全展示（component_status：无在途/有在途未答复/既有在途又有答交/边界）
  #14 需求日可齐套数量（demand_kittable_qty，同 C-2 口径 + PO 在途叠加）

均为纯展示/派生列，不改四色判定/净额/kittable_qty 既有口径（红线）。
"""
from __future__ import annotations

from datetime import date

from zhuopin_platform.shared_tools.models import BomRow, SrmDeliveryOrder

from sc8.baoguan import (RISK_RED, STATUS_CONFIRMED_NO_TRANSIT, STATUS_NO_TRANSIT,
                         STATUS_TRANSIT_CONFIRMED, STATUS_TRANSIT_UNCONFIRMED,
                         assess_supply_risk, render_html, row_to_dict)
from sc8.models import SalesOrder

TODAY = date(2026, 8, 1)


def _so(item="P1", qty=1000, ship="2026-09-01", name="ECU"):
    return SalesOrder(so_id=f"FO-{item}", customer_id="", customer_name="某OEM",
                      item_code=item, qty=qty, required_date=ship,
                      doc_type="预测订单", item_name=name)


def _row(product, component, *, name=None, qty_per_unit=1.0, sequence="", is_substitute=False):
    return BomRow(product_id=product, component_id=component,
                 component_name=name if name is not None else component,
                 level=1, qty_per_unit=qty_per_unit, loss_rate=0.0, unit="PCS",
                 sequence=sequence, is_substitute=is_substitute)


def _srm(material, committed):
    return SrmDeliveryOrder(delivery_id=f"SRM-{material}", demand_id="", supplier_id="",
                            material_id=material, qty_committed=0,
                            committed_date=committed, status="confirmed")


# ── ③ 料品名称（component_names） ───────────────────────────────────────────

def test_component_names_populated_from_bom_when_has_bom():
    so = _so()
    bom = [_row("P1", "A", name="料A"), _row("P1", "B", name="料B")]
    row = assess_supply_risk(so, bom, [], today=TODAY)
    assert row.component_names == {"A": "料A", "B": "料B"}


def test_component_names_empty_when_no_bom():
    so = _so(item="NOBOM")
    row = assess_supply_risk(so, [], [], today=TODAY)
    assert row.component_names == {}


def test_component_names_covers_deep_leaf_from_combined_bom():
    """B1 多层展开场景：品名映射来自整批组合 bom（非按 product_id 过滤），才能覆盖深层叶子件。"""
    so = _so(item="TOP")
    # TOP 的直接子件 SEMI 是半成品（同批 bom 里也作为另一张 SO 的 product_id 出现）；
    # SEMI 自己的子件 LEAF 应该也能在 component_names 里查到品名。
    bom = [_row("TOP", "SEMI", name="半成品"), _row("SEMI", "LEAF", name="叶子件")]
    row = assess_supply_risk(so, bom, [], today=TODAY)
    assert row.component_names["LEAF"] == "叶子件"


# ── #12 子件供给状态全展示（component_status） ──────────────────────────────

def test_component_status_empty_when_purchase_orders_not_passed():
    so = _so()
    bom = [_row("P1", "A")]
    row = assess_supply_risk(so, bom, [], today=TODAY)
    assert row.component_status == []


def test_component_status_no_transit():
    so = _so()
    bom = [_row("P1", "A")]
    row = assess_supply_risk(so, bom, [], today=TODAY, purchase_orders={})
    assert len(row.component_status) == 1
    s = row.component_status[0]
    assert s.component_id == "A" and s.status == STATUS_NO_TRANSIT
    assert s.transit_qty == 0 and s.confirmed_date is None


def test_component_status_transit_unconfirmed():
    so = _so()
    bom = [_row("P1", "A")]
    row = assess_supply_risk(so, bom, [], today=TODAY, purchase_orders={"A": 300.0})
    s = row.component_status[0]
    assert s.status == STATUS_TRANSIT_UNCONFIRMED
    assert s.transit_qty == 300.0 and s.confirmed_date is None


def test_component_status_transit_confirmed():
    so = _so(ship="2026-09-01")
    bom = [_row("P1", "A")]
    row = assess_supply_risk(so, bom, [_srm("A", "2026-08-15")], today=TODAY,
                             purchase_orders={"A": 500.0})
    s = row.component_status[0]
    assert s.status == STATUS_TRANSIT_CONFIRMED
    assert s.transit_qty == 500.0 and s.confirmed_date == date(2026, 8, 15)


def test_component_status_confirmed_no_transit_edge_case():
    """边界：有 SRM 承诺但查无在途 PO（数据口径不一致）——如实展示，不臆造原因。"""
    so = _so(ship="2026-09-01")
    bom = [_row("P1", "A")]
    row = assess_supply_risk(so, bom, [_srm("A", "2026-08-15")], today=TODAY,
                             purchase_orders={})
    s = row.component_status[0]
    assert s.status == STATUS_CONFIRMED_NO_TRANSIT
    assert s.transit_qty == 0 and s.confirmed_date == date(2026, 8, 15)


def test_component_status_names_and_qty_needed():
    so = _so(qty=500)
    bom = [_row("P1", "A", name="电容", qty_per_unit=2.0)]
    row = assess_supply_risk(so, bom, [], today=TODAY, purchase_orders={})
    s = row.component_status[0]
    assert s.component_name == "电容"
    assert s.qty_needed == 1000.0   # 500 * 2.0


def test_component_status_excludes_stock_covered_materials(monkeypatch):
    """净额开关 ON 且现货已覆盖的子件不再出现在 component_status（与 mat.arrivals 一致）。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(qty=100)
    bom = [_row("P1", "A", qty_per_unit=1.0), _row("P1", "B", qty_per_unit=1.0)]
    row = assess_supply_risk(so, bom, [], today=TODAY,
                             inventory={"A": 500}, purchase_orders={"A": 10, "B": 10})
    ids = {s.component_id for s in row.component_status}
    assert ids == {"B"}   # A 被现货覆盖，B 仍待到货


def test_component_status_does_not_change_four_color_risk():
    so = _so(qty=100)
    bom = [_row("P1", "A")]
    row = assess_supply_risk(so, bom, [], today=TODAY, purchase_orders={"A": 999})
    # 队列#147续：无 SRM 承诺按90天保守估算🔴，不因有在途 PO 改判；有无在途本身不影响四色
    assert row.risk == RISK_RED


# ── #14 需求日可齐套数量（demand_kittable_qty） ─────────────────────────────

def test_demand_kittable_none_without_purchase_orders(monkeypatch):
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(qty=1000)
    bom = [_row("P1", "A")]
    row = assess_supply_risk(so, bom, [], today=TODAY, inventory={"A": 500})
    assert row.demand_kittable_qty is None
    assert row.demand_kittable_bottleneck is None


def test_demand_kittable_none_when_netting_off():
    so = _so(qty=1000)
    bom = [_row("P1", "A")]
    row = assess_supply_risk(so, bom, [], today=TODAY,
                             inventory={"A": 500}, purchase_orders={"A": 500})
    assert row.demand_kittable_qty is None


def test_demand_kittable_includes_po_arriving_before_ship_date(monkeypatch):
    """子件 A 无 SRM 承诺 → 估算到货日 = max(ship,today)+90，远晚于出货日 → 在途量不计入。
    子件 B 有 SRM 承诺、到货日早于出货日 → 在途量计入需求日可齐套。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(qty=1000, ship="2026-09-01")
    bom = [_row("P1", "A", qty_per_unit=1.0), _row("P1", "B", qty_per_unit=1.0)]
    srm = [_srm("B", "2026-08-01")]   # B 到货日早于出货日 09-01
    row = assess_supply_risk(so, bom, srm, today=TODAY,
                             inventory={"A": 200, "B": 200},
                             purchase_orders={"A": 300, "B": 300})
    # A: 无答复，估算到货远晚于出货 → 只算现货 200 → floor(200/1)=200
    # B: 到货 08-01 <= 09-01 → 现货200+在途300=500 → floor(500/1)=500
    # min(200,500)=200，瓶颈=A
    assert row.demand_kittable_qty == 200
    assert row.demand_kittable_bottleneck == "A"


def test_demand_kittable_excludes_po_arriving_after_ship_date(monkeypatch):
    """子件到货日晚于出货日 → 在途量不计入需求日可齐套（只算现货）。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(qty=1000, ship="2026-09-01")
    bom = [_row("P1", "A", qty_per_unit=1.0)]
    srm = [_srm("A", "2026-09-10")]   # 晚于出货日
    row = assess_supply_risk(so, bom, srm, today=TODAY,
                             inventory={"A": 150}, purchase_orders={"A": 900})
    assert row.demand_kittable_qty == 150   # 在途 900 不计入（09-10 > 09-01）


def test_demand_kittable_substitute_group_combined(monkeypatch):
    """含替代料的料位：可用量 = 主料+替代料 现货合计 +（主料需求日前到货的在途量）。

    替代料本身不参与 estimate_material_arrivals（避免幻影组件误查 SRM，见 assess_supply_risk
    注释），故替代料的在途量在需求日可齐套里不会被计入（只计其现货）——已知的保守边界，
    不会高估可齐套数量。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(qty=1000, ship="2026-09-01")
    bom = [_row("P1", "A", qty_per_unit=1.0, sequence="10", is_substitute=False),
          _row("P1", "B", qty_per_unit=1.0, sequence="10", is_substitute=True)]
    srm = [_srm("A", "2026-08-01"), _srm("B", "2026-08-01")]
    row = assess_supply_risk(so, bom, srm, today=TODAY,
                             inventory={"A": 100, "B": 100},
                             purchase_orders={"A": 50, "B": 50})
    # A: 现货100+在途50(到货08-01<=出货09-01)=150；B(替代料，无到货日估算): 只算现货100
    assert row.demand_kittable_qty == 250


def test_demand_kittable_no_direct_components_is_none(monkeypatch):
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(item="EMPTY")
    row = assess_supply_risk(so, [], [], today=TODAY, inventory={}, purchase_orders={})
    assert row.demand_kittable_qty is None


# ── row_to_dict 序列化 ──────────────────────────────────────────────────────

def test_row_to_dict_serializes_new_fields(monkeypatch):
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(qty=100, ship="2026-09-01")
    bom = [_row("P1", "A", name="电容", qty_per_unit=1.0)]
    row = assess_supply_risk(so, bom, [], today=TODAY,
                             inventory={"A": 50}, purchase_orders={"A": 20})
    d = row_to_dict(row)
    assert d["cn"] == {"A": "电容"}
    assert d["cst"] == [{"id": "A", "name": "电容", "qty": 100.0, "st": "transit_unconfirmed",
                         "tq": 20.0, "aq": 50.0, "gq": 50.0, "cd": None, "cb": []}]
    assert d["dkq"] == 50 and d["dkbn"] == "A"   # 到货远超出货日，只算现货50


def test_row_to_dict_defaults_when_no_po_data():
    so = _so(item="P2")
    bom = [_row("P2", "R01")]
    row = assess_supply_risk(so, bom, [], today=TODAY)
    d = row_to_dict(row)
    assert d["cn"] == {"R01": "R01"}
    assert d["cst"] == []
    assert d["dkq"] is None and d["dkbn"] is None


# ── ①②④ 界面元素（分页/导出Excel/图例）静态渲染冒烟 ─────────────────────────

def test_render_html_has_pagination_excel_and_legend():
    so = _so(item="S1")
    bom = [_row("S1", "C1")]
    rows = [assess_supply_risk(so, bom, [], today=TODAY)]
    html = render_html(rows, today=TODAY)
    # ②分页
    assert 'id="pageSize"' in html and 'value="10"' in html and 'value="200"' in html
    assert 'id="pagerTop"' in html and 'id="pagerBottom"' in html
    assert "function renderPager" in html
    # ①导出 Excel（导出 CSV 已按姚祖怡 07-26 V6 #14 去除，只留 Excel 一个入口）
    assert 'id="xlsx"' in html and "导出 Excel" in html and "function exportExcel" in html
    assert 'id="csv"' not in html and "导出 CSV" not in html
    # ④图例
    assert 'id="legendBtn"' in html and 'id="legendPanel"' in html
    assert "四色判据" in html


# ── 姚祖怡 07-26 V6 回件批1修复批：措辞 + Excel 子件明细展开行 ──────────────────

def test_render_html_uses_outstanding_po_wording_not_transit(monkeypatch):
    """V6 #1：""在途""改""存在未交订单""四态描述 + #10 措辞""BOM 缺口物料清单""。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(item="S1", qty=100)
    bom = [_row("S1", "A", name="电容", qty_per_unit=1.0)]
    rows = [assess_supply_risk(so, bom, [], today=TODAY,
                               inventory={"A": 0}, purchase_orders={"A": 20})]
    html = render_html(rows, today=TODAY)
    assert "无未交订单无答交" in html and "有未交订单无答交" in html
    assert "有未交订单已答交" in html and "无未交订单有答交" in html
    assert "BOM 缺口物料清单" in html
    assert "全部无法即时满足需求的子件" not in html


def test_render_html_shows_project_demand_quantity():
    """V6 #2：子件明细展示""本项目需求数量""（=预测订单数量×BOM子件用量，取自既有 cst.qty）。"""
    so = _so(item="S1", qty=100)
    bom = [_row("S1", "A", name="电容", qty_per_unit=3.0)]
    rows = [assess_supply_risk(so, bom, [], today=TODAY, purchase_orders={"A": 20})]
    d = row_to_dict(rows[0])
    assert d["cst"][0]["qty"] == 300.0        # 100 × 3.0，与 _gross_need 同一份取值
    html = render_html(rows, today=TODAY)
    assert "本项目需求数量" in html


def test_export_excel_expands_component_detail_rows():
    """V6 导出-1（#13）：导出 Excel 在每个成品行下追加子件明细展开行（非仅成品行本身）。"""
    so = _so(item="S1", qty=100)
    bom = [_row("S1", "A", name="电容", qty_per_unit=1.0)]
    rows = [assess_supply_risk(so, bom, [], today=TODAY, purchase_orders={"A": 20})]
    html = render_html(rows, today=TODAY)
    assert "function exportExcel" in html
    assert "子件料号" in html and "子件品名" in html and "子件状态" in html
    assert "本项目需求数量" in html and "未交订单量" in html and "答交日期" in html
    assert "r.cst" in html   # 逐行遍历 cst 追加展开行的核心逻辑存在


# ── 姚祖怡 07-28 判例回件（队列 #139）：#17/#128 导出去箭头 + #18-a/b 答交数量/日期 ──

def test_export_excel_no_longer_prefixes_arrow(monkeypatch):
    """#17/#128：子件明细行前的""↳""箭头符号已去除，改用列留空分组区分层级。"""
    so = _so(item="S1", qty=100)
    bom = [_row("S1", "A", name="电容", qty_per_unit=1.0)]
    rows = [assess_supply_risk(so, bom, [], today=TODAY, purchase_orders={"A": 20})]
    html = render_html(rows, today=TODAY)
    assert "↳" not in html                       # 箭头符号已彻底移除
    assert "s.id" in html                        # 子件行料号列直接用 s.id（不再拼接前缀）
    assert "答交数量" in html                     # #18-a 新增列


def test_component_status_confirmed_batches_empty_without_commitments():
    """未传 material_commitments（缺省）→ confirmed_batches 恒为空元组，零漂移。"""
    so = _so(ship="2026-09-01")
    bom = [_row("P1", "A")]
    row = assess_supply_risk(so, bom, [_srm("A", "2026-08-15")], today=TODAY,
                             purchase_orders={"A": 500.0})
    s = row.component_status[0]
    assert s.confirmed_batches == ()


def test_component_status_confirmed_batches_single_match():
    """真实案例复现（姚祖怡 07-28 判例回件 R01D.0006）：单条确认记录恰好满足缺口。"""
    so = _so(item="P1", qty=3000, ship="2026-08-01")   # 毛需求 3000（qty_per_unit=1.0）
    bom = [_row("P1", "A")]
    commitments = {"A": [(date(2026, 7, 20), 3000.0)]}
    row = assess_supply_risk(so, bom, [_srm("A", "2026-08-20")], today=TODAY,
                             purchase_orders={"A": 3000.0},
                             material_commitments=commitments)
    s = row.component_status[0]
    assert s.status == STATUS_TRANSIT_CONFIRMED
    assert s.confirmed_batches == ((date(2026, 7, 20), 3000.0),)
    # 旧口径 confirmed_date（来自 /purchase/answer，本例故意设为错误的 08-20）仍保留在
    # 字段里供内部参考，但前端渲染改为优先展示 confirmed_batches（见 componentStatusHtml）。
    assert s.confirmed_date == date(2026, 8, 20)


def test_component_status_confirmed_batches_cumulative_multiple():
    """答交数量小于缺口 → 继续累加下一条，直至覆盖缺口为止（#18-a 原话）。"""
    so = _so(item="P1", qty=1000, ship="2026-09-01")   # 毛需求 1000
    bom = [_row("P1", "A")]
    commitments = {"A": [(date(2026, 8, 5), 300.0),      # 累计 300 < 1000，继续
                         (date(2026, 7, 20), 400.0),      # 按日期排序后先于08-05：累计 700 < 1000，继续
                         (date(2026, 9, 1), 500.0),       # 累计 1200 >= 1000，止步，本条仍完整展示
                         (date(2026, 10, 1), 200.0)]}     # 已够，不再纳入
    row = assess_supply_risk(so, bom, [_srm("A", "2026-07-20")], today=TODAY,
                             purchase_orders={"A": 1000.0},
                             material_commitments=commitments)
    s = row.component_status[0]
    assert s.confirmed_batches == (
        (date(2026, 7, 20), 400.0), (date(2026, 8, 5), 300.0), (date(2026, 9, 1), 500.0),
    )


def test_component_status_confirmed_batches_only_for_confirmed_states():
    """无答复子件（STATUS_TRANSIT_UNCONFIRMED/STATUS_NO_TRANSIT）不计算 confirmed_batches。"""
    so = _so(item="P1", qty=100, ship="2026-09-01")
    bom = [_row("P1", "A")]
    commitments = {"A": [(date(2026, 8, 1), 999.0)]}   # 即便有承诺记录，无答复子件也不展示
    row = assess_supply_risk(so, bom, [], today=TODAY,
                             purchase_orders={"A": 50.0},
                             material_commitments=commitments)
    s = row.component_status[0]
    assert s.status == STATUS_TRANSIT_UNCONFIRMED
    assert s.confirmed_batches == ()


def test_row_to_dict_serializes_confirmed_batches():
    """row_to_dict 的 cst[].cb 正确序列化 confirmed_batches（#18-a/b）。"""
    so = _so(item="P1", qty=100, ship="2026-09-01")
    bom = [_row("P1", "A")]
    commitments = {"A": [(date(2026, 8, 1), 100.0)]}
    row = assess_supply_risk(so, bom, [_srm("A", "2026-08-01")], today=TODAY,
                             purchase_orders={"A": 100.0},
                             material_commitments=commitments)
    d = row_to_dict(row)
    assert d["cst"][0]["cb"] == [{"d": "2026-08-01", "q": 100.0}]


def test_render_html_shows_answer_quantity_and_multiple_dates():
    """#18-b：卡片视图按""数量×日期""展示答交明细，多条时以顿号分隔逐条列出。"""
    so = _so(item="S1", qty=700, ship="2026-09-01")
    bom = [_row("S1", "A", name="电容")]
    commitments = {"A": [(date(2026, 7, 20), 300.0), (date(2026, 8, 5), 400.0)]}
    rows = [assess_supply_risk(so, bom, [_srm("A", "2026-07-20")], today=TODAY,
                               purchase_orders={"A": 700.0},
                               material_commitments=commitments)]
    html = render_html(rows, today=TODAY)
    assert "answerQtyText" in html and "answerDateText" in html
    assert "s.cb" in html
