"""BOM 缺口物料清单替代料并列展示（#297，姚祖怡 2026-08-06 新提要求，队列 #296/#297
同车，design.md D4）。

与 C-1/C-2（`_substitute_groups`/`_kittable_qty`/`_covered_by_stock`，替代料等价
合并判缺料）是两件不同的事——那里是**判定**（替代关系是否参与齐套聚合计算），
本文件是**展示**（把已识别到的替代料摊开成独立一行给她看）。本文件全程不改变
四色判定/净额/缺口聚合计算结果，只验证展示层追加逻辑本身。
"""
from __future__ import annotations

from datetime import date

from zhuopin_platform.shared_tools.models import BomRow, SrmDeliveryOrder

from sc8.baoguan import RISK_RED, _component_supply_status, assess_supply_risk, render_html, row_to_dict
from sc8.forecast import MaterialArrivals
from sc8.models import SalesOrder

TODAY = date(2026, 8, 1)


def _so(qty=800, ship="2026-09-01", item="F02N.0242"):
    return SalesOrder(so_id="FO-1", customer_id="", customer_name="某OEM",
                      item_code=item, qty=qty, required_date=ship,
                      doc_type="预测订单", item_name="ECU")


def _row(component, *, name=None, sequence="", is_substitute=False, qty=1.0, product="F02N.0242"):
    return BomRow(product_id=product, component_id=component,
                 component_name=name if name is not None else component,
                 level=1, qty_per_unit=qty, loss_rate=0.0, unit="PCS",
                 sequence=sequence, is_substitute=is_substitute)


def _srm(material, committed):
    return SrmDeliveryOrder(delivery_id=f"SRM-{material}", demand_id="", supplier_id="",
                            material_id=material, qty_committed=0,
                            committed_date=committed, status="confirmed")


# ── _component_supply_status 白盒单测（substitute_groups 参数） ────────────────

def test_no_substitute_groups_role_empty_zero_drift():
    """substitute_groups 缺省/无命中：role 恒为空串，不追加任何行——与本变更包实施前
    完全一致。"""
    mat = MaterialArrivals(arrivals={"A": date(2026, 8, 20)}, no_feedback_materials=[],
                           bottleneck_material="A", has_bom=True)
    out = _component_supply_status(mat, gross={"A": 800.0}, names={},
                                   purchase_orders={"A": 0.0}, inventory={"A": 0.0})
    assert len(out) == 1
    assert out[0].role == ""


def test_substitute_row_appended_immediately_after_primary():
    """替代料展示行紧随主料行之后（列表顺序即渲染顺序），role 标注区分两者。"""
    mat = MaterialArrivals(arrivals={"R01A.1459": date(2026, 8, 20)},
                           no_feedback_materials=[], bottleneck_material="R01A.1459",
                           has_bom=True)
    out = _component_supply_status(
        mat, gross={"R01A.1459": 800.0}, names={"R01A.1459": "MR08X2700FTL",
                                                "R01A.1545": "ABF05K2700FT"},
        purchase_orders={"R01A.1459": 0.0, "R01A.1545": 254.0},
        inventory={"R01A.1459": 0.0, "R01A.1545": 254.0},
        substitute_groups={"R01A.1459": ["R01A.1545"]},
    )
    assert [s.component_id for s in out] == ["R01A.1459", "R01A.1545"]
    assert out[0].role == "primary" and out[1].role == "substitute"


def test_substitute_row_shares_primary_qty_needed_but_independent_avail_gap():
    """真实案例复现（姚祖怡 08-06 举证 F02N.0242/R01A.1459，模板逐字段吻合）：
    主料/替代料两行"本项目需求数量"相同（同一份需求），但可用现货/缺口数量各自
    独立按自身现货计算——不是"合并后剩余"的分摊逻辑。

    她的模板：R01A.1459（主料）现货0/需求800/缺口800；
              R01A.1545（替代料）现货254/需求800/缺口546。
    """
    mat = MaterialArrivals(arrivals={"R01A.1459": date(2026, 8, 20)},
                           no_feedback_materials=["R01A.1459", "R01A.1545"],
                           bottleneck_material="R01A.1459", has_bom=True)
    out = _component_supply_status(
        mat, gross={"R01A.1459": 800.0}, names={},
        purchase_orders={}, inventory={"R01A.1459": 0.0, "R01A.1545": 254.0},
        substitute_groups={"R01A.1459": ["R01A.1545"]},
    )
    primary, substitute = out
    assert primary.qty_needed == 800.0 and substitute.qty_needed == 800.0
    assert primary.available_qty == 0.0 and primary.gap_qty == 800.0
    assert substitute.available_qty == 254.0 and substitute.gap_qty == 546.0


def test_substitute_row_status_computed_independently():
    """替代料行的答交状态/在途量独立按自身料号查询，不沿用主料的状态。"""
    mat = MaterialArrivals(arrivals={"A": date(2026, 8, 20)}, no_feedback_materials=["A"],
                           bottleneck_material="A", has_bom=True)
    out = _component_supply_status(
        mat, gross={"A": 800.0}, names={},
        purchase_orders={"B": 254.0},   # 只有替代料 B 有在途，主料 A 无
        inventory={"A": 0.0, "B": 254.0},
        substitute_groups={"A": ["B"]},
    )
    primary, substitute = out
    from sc8.baoguan import STATUS_NO_TRANSIT, STATUS_TRANSIT_UNCONFIRMED
    assert primary.status == STATUS_NO_TRANSIT          # 无在途、未答交
    assert substitute.status == STATUS_TRANSIT_UNCONFIRMED  # 有在途、未答交


def test_substitute_row_not_emitted_when_primary_filtered_by_zero_gap():
    """主料行本身因缺口≤0（#151 展示层过滤）未进入清单时，替代料展示行同样不追加——
    只对"真正出现在缺口清单里"的主料行追加替代料。"""
    mat = MaterialArrivals(arrivals={"A": date(2026, 8, 20)}, no_feedback_materials=[],
                           bottleneck_material="A", has_bom=True)
    out = _component_supply_status(
        mat, gross={"A": 100.0}, names={},
        purchase_orders={}, inventory={"A": 100.0, "B": 999.0},   # A 现货已覆盖，缺口=0
        substitute_groups={"A": ["B"]},
    )
    assert out == []


def test_multiple_substitutes_all_appended():
    """一个主料位有多个替代料时，逐一追加，顺序稳定。"""
    mat = MaterialArrivals(arrivals={"A": date(2026, 8, 20)}, no_feedback_materials=[],
                           bottleneck_material="A", has_bom=True)
    out = _component_supply_status(
        mat, gross={"A": 500.0}, names={},
        purchase_orders={}, inventory={"A": 0.0, "B": 100.0, "C": 200.0},
        substitute_groups={"A": ["B", "C"]},
    )
    assert [s.component_id for s in out] == ["A", "B", "C"]
    assert [s.role for s in out] == ["primary", "substitute", "substitute"]


def test_substitute_row_confirmed_batches_independent():
    """替代料行的答交数量累计明细独立按自身料号从 material_commitments 取数。"""
    mat = MaterialArrivals(arrivals={"A": date(2026, 8, 20)}, no_feedback_materials=["A"],
                           bottleneck_material="A", has_bom=True)
    commitments = {"B": [(date(2026, 7, 20), 100.0)]}   # 只有替代料 B 有答交记录
    out = _component_supply_status(
        mat, gross={"A": 500.0}, names={},
        purchase_orders={}, inventory={"A": 0.0, "B": 0.0},
        substitute_groups={"A": ["B"]}, material_commitments=commitments,
    )
    primary, substitute = out
    assert primary.confirmed_batches == ()
    assert substitute.confirmed_batches == ((date(2026, 7, 20), 100.0),)


# ── assess_supply_risk 集成 + row_to_dict 序列化 ────────────────────────────

def test_assess_supply_risk_end_to_end_substitute_display(monkeypatch):
    """端到端真实案例复现（F02N.0242/R01A.1459/R01A.1545，她的举证案例）。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(qty=800)
    bom = [_row("R01A.1459", name="MR08X2700FTL", sequence="10", is_substitute=False),
          _row("R01A.1545", name="ABF05K2700FT", sequence="10", is_substitute=True)]
    row = assess_supply_risk(
        so, bom, [], today=TODAY,
        inventory={"R01A.1459": 0.0, "R01A.1545": 254.0}, purchase_orders={})
    d = row_to_dict(row)
    cst = d["cst"]
    assert len(cst) == 2
    assert cst[0]["id"] == "R01A.1459" and cst[0]["role"] == "primary"
    assert cst[0]["qty"] == 800.0 and cst[0]["aq"] == 0.0 and cst[0]["gq"] == 800.0
    assert cst[1]["id"] == "R01A.1545" and cst[1]["role"] == "substitute"
    assert cst[1]["qty"] == 800.0 and cst[1]["aq"] == 254.0 and cst[1]["gq"] == 546.0


def test_substitute_display_does_not_change_four_color_risk_or_kittable(monkeypatch):
    """红线核对：替代料并列展示不改变四色判定/净额/kittable_qty 既有聚合结果——
    与"无替代料"场景的判定结果逐字段对照（本函数本身不改动，只验证接线未破坏）。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(qty=800)
    bom = [_row("R01A.1459", sequence="10", is_substitute=False),
          _row("R01A.1545", sequence="10", is_substitute=True)]
    row = assess_supply_risk(
        so, bom, [], today=TODAY,
        inventory={"R01A.1459": 0.0, "R01A.1545": 254.0}, purchase_orders={})
    # 齐套判定（C-1/C-2 既有逻辑）：主料+替代料现货合计 254 < 毛需求 800 → 仍缺料 → 🔴
    assert row.risk == RISK_RED
    assert row.kittable_qty == 254   # 既有 _kittable_qty 口径不受本次展示层改动影响


def test_substitute_display_zero_drift_without_substitute_relationship():
    """无替代关系的普通 BOM：cst 序列化与本变更包实施前完全一致（role 恒空串）。"""
    so = _so(qty=100, item="P1")
    bom = [_row("A", product="P1")]
    row = assess_supply_risk(so, bom, [], today=TODAY, purchase_orders={"A": 20})
    d = row_to_dict(row)
    assert len(d["cst"]) == 1
    assert d["cst"][0]["role"] == ""


# ── 前端渲染（HTML/JS）冒烟 ──────────────────────────────────────────────────

def test_render_html_shows_primary_and_substitute_role_tags(monkeypatch):
    """真实案例前端渲染：主料料号后标"（主料）"，替代料料号后标"（替代料）"。"""
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(qty=800)
    bom = [_row("R01A.1459", name="MR08X2700FTL", sequence="10", is_substitute=False),
          _row("R01A.1545", name="ABF05K2700FT", sequence="10", is_substitute=True)]
    rows = [assess_supply_risk(
        so, bom, [], today=TODAY,
        inventory={"R01A.1459": 0.0, "R01A.1545": 254.0}, purchase_orders={})]
    html = render_html(rows, today=TODAY)
    assert "ROLE_TAG" in html and "primary:" in html and "substitute:" in html
    assert "（主料）" in html and "（替代料）" in html
