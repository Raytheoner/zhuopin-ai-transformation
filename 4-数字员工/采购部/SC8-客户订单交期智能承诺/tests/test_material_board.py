"""物料看板聚合引擎（sc8.material_board，队列 #334）—— 全 mock，不触网。

覆盖 tasks 3.2-3.6 + 4.1/4.2：跨成品聚合去重、无缺口不出现、替代料不重复计、
按出货月归集与滚动、答交明细按物料级累计、状态分歧如实标示、取数缺口列不留空，
以及 Snapshot 新字段的向后兼容与既有 rows/counts 零漂移。
"""
from __future__ import annotations

import json
from datetime import date

from sc8 import material_board as mb
from sc8.baoguan import (STATUS_CONFIRMED_NO_TRANSIT, STATUS_NO_TRANSIT,
                         STATUS_TRANSIT_CONFIRMED, STATUS_TRANSIT_UNCONFIRMED,
                         BaoguanRow, ComponentSupplyStatus)
from sc8.baoguan_service import Snapshot


def _cst(cid, *, gap, qty=None, status=STATUS_TRANSIT_CONFIRMED, name="", tq=0.0, role=""):
    return ComponentSupplyStatus(
        component_id=cid, component_name=name or f"品名-{cid}",
        qty_needed=qty if qty is not None else gap, status=status,
        transit_qty=tq, confirmed_date=None, available_qty=0.0, gap_qty=gap, role=role)


def _row(product, ship, comps):
    return BaoguanRow(
        so_id=f"FO-{product}", product_id=product, product_name=f"成品{product}",
        customer_name="比亚迪", qty=10, ship_date=date.fromisoformat(ship),
        kit_date=None, gap_days=None, risk="🟢", bottleneck_material=None,
        has_bom=True, component_status=list(comps))


TODAY = date(2026, 8, 20)


# ── 3.2 跨成品聚合／无缺口不出现／替代料不重复计 ──────────────────────────────

def test_aggregates_same_material_across_products():
    board = mb.build_material_board(
        [_row("F1", "2026-08-05", [_cst("R01", gap=100)]),
         _row("F2", "2026-08-25", [_cst("R01", gap=200)])],
        today=TODAY, months=3)
    assert [r["id"] for r in board.rows] == ["R01"]
    assert board.rows[0]["m"][0] == 300.0
    assert board.rows[0]["nrow"] == 2


def test_material_without_gap_does_not_appear():
    board = mb.build_material_board(
        [_row("F1", "2026-08-05", [_cst("R01", gap=0), _cst("R02", gap=-5),
                                   _cst("R03", gap=7)])],
        today=TODAY, months=3)
    assert [r["id"] for r in board.rows] == ["R03"]


def test_substitute_display_row_is_not_a_material_row_and_not_double_counted():
    """D11：替代料展示行沿用主料需求量，聚合它会把同一份缺口重复计一次。"""
    board = mb.build_material_board(
        [_row("F1", "2026-08-05", [_cst("R01", gap=100, role="primary"),
                                   _cst("R09", gap=100, role="substitute")])],
        today=TODAY, months=3)
    assert [r["id"] for r in board.rows] == ["R01"]
    assert board.rows[0]["total"] == 100.0        # 不是 200
    assert board.rows[0]["hasSub"] is True


def test_plain_row_is_not_marked_as_having_substitute():
    board = mb.build_material_board(
        [_row("F1", "2026-08-05", [_cst("R01", gap=100)])], today=TODAY, months=3)
    assert board.rows[0]["hasSub"] is False


def test_falls_back_to_qty_needed_when_gap_qty_is_none():
    """净额开关关闭时 gap_qty 恒为 None——退回本项目毛需求，而不是把该物料整个丢掉。"""
    c = ComponentSupplyStatus(component_id="R01", component_name="X", qty_needed=42.0,
                              status=STATUS_NO_TRANSIT, transit_qty=0.0, confirmed_date=None)
    board = mb.build_material_board([_row("F1", "2026-08-05", [c])], today=TODAY, months=3)
    assert board.rows[0]["total"] == 42.0


# ── 3.3 月份归集／合计／窗口外／滚动 ──────────────────────────────────────────

def test_buckets_by_ship_month_and_total_is_sum():
    board = mb.build_material_board(
        [_row("F1", "2026-08-05", [_cst("R01", gap=100)]),
         _row("F2", "2026-09-15", [_cst("R01", gap=300)]),
         _row("F3", "2026-10-31", [_cst("R01", gap=500)])],
        today=TODAY, months=3)
    r = board.rows[0]
    assert r["m"] == [100.0, 300.0, 500.0]
    assert r["total"] == 900.0
    assert [m.label for m in board.months] == ["8月", "9月", "10月"]


def test_out_of_window_gap_excluded_from_columns_and_total_but_visible():
    board = mb.build_material_board(
        [_row("F1", "2026-08-05", [_cst("R01", gap=100)]),
         _row("F2", "2026-12-01", [_cst("R01", gap=999)])],
        today=TODAY, months=3)
    r = board.rows[0]
    assert r["m"] == [100.0, 0.0, 0.0] and r["total"] == 100.0
    assert r["out"] == 999.0                      # 不计入，但可见（页面显示徽标）
    assert board.out_of_window_qty == 999.0


def test_material_entirely_out_of_window_is_not_listed_but_is_counted():
    """一行全 0 会被读成「这个料不缺」——不列，但在 meta 里报出被排除了多少。"""
    board = mb.build_material_board(
        [_row("F1", "2027-03-01", [_cst("R01", gap=888)])], today=TODAY, months=3)
    assert board.rows == []
    assert board.out_of_window_materials == 1
    assert board.meta()["out_of_window_materials"] == 1


def test_window_rolls_with_snapshot_date():
    board = mb.build_material_board([], today=date(2026, 9, 1), months=3)
    assert [m.ym for m in board.months] == ["2026-09", "2026-10", "2026-11"]


def test_window_crossing_year_boundary_labels_carry_the_year():
    """跨年时「1月」在 12/1/2 三列里指代不清，必须带年份。"""
    board = mb.build_material_board([], today=date(2026, 12, 1), months=3)
    assert [m.label for m in board.months] == ["12月", "2027年1月", "2027年2月"]
    assert board.meta()["window"] == "2026-12 ~ 2027-02"


def test_month_span_is_configurable(monkeypatch):
    monkeypatch.setenv("SC8_MATERIAL_BOARD_MONTHS", "6")
    board = mb.build_material_board([], today=TODAY)          # months=None → 走 config
    assert len(board.months) == 6


# ── 3.4 答交明细：物料级全量、按三月合计缺口累计 ──────────────────────────────

def test_commitments_accumulate_against_three_month_total_not_per_row():
    """D3：累计目标是物料的三月合计缺口，不是任何单张成品行的缺口。"""
    board = mb.build_material_board(
        [_row("F1", "2026-08-05", [_cst("R01", gap=100)]),
         _row("F2", "2026-09-05", [_cst("R01", gap=250)])],
        today=TODAY, months=3,
        commitments={"R01": [(date(2026, 9, 20), 100.0), (date(2026, 10, 20), 300.0),
                             (date(2026, 11, 20), 500.0)]})
    r = board.rows[0]
    assert r["total"] == 350.0
    # 100 不够 350 → 继续取 300；累计 400 ≥ 350 → 停，不再取 500
    assert r["cb"] == [{"d": "2026-09-20", "q": 100.0}, {"d": "2026-10-20", "q": 300.0}]


def test_zero_quantity_commitment_shown_as_zero_not_dropped():
    """`q==0` 是「差异已确认、答复为 0」的合法记录，与「无答交记录」不是一回事。"""
    board = mb.build_material_board(
        [_row("F1", "2026-08-05", [_cst("R01", gap=100)])], today=TODAY, months=3,
        commitments={"R01": [(date(2026, 9, 20), 0.0)]})
    assert board.rows[0]["cb"] == [{"d": "2026-09-20", "q": 0.0}]


def test_no_commitments_yields_empty_batches():
    board = mb.build_material_board(
        [_row("F1", "2026-08-05", [_cst("R01", gap=100)])], today=TODAY, months=3)
    assert board.rows[0]["cb"] == []


# ── 3.5 状态四态与分歧 ────────────────────────────────────────────────────────

def test_status_taken_as_is_when_consistent():
    board = mb.build_material_board(
        [_row("F1", "2026-08-05", [_cst("R01", gap=10, status=STATUS_TRANSIT_CONFIRMED)]),
         _row("F2", "2026-09-05", [_cst("R01", gap=10, status=STATUS_TRANSIT_CONFIRMED)])],
        today=TODAY, months=3)
    assert board.rows[0]["st"] == STATUS_TRANSIT_CONFIRMED
    assert board.rows[0]["sts"] == [STATUS_TRANSIT_CONFIRMED]


def test_divergent_status_is_flagged_not_silently_picked():
    board = mb.build_material_board(
        [_row("F1", "2026-08-05", [_cst("R01", gap=10, status=STATUS_TRANSIT_CONFIRMED)]),
         _row("F2", "2026-09-05", [_cst("R01", gap=10, status=STATUS_TRANSIT_UNCONFIRMED)])],
        today=TODAY, months=3)
    r = board.rows[0]
    assert r["st"] == mb.STATUS_DIVERGENT
    assert r["sts"] == sorted([STATUS_TRANSIT_CONFIRMED, STATUS_TRANSIT_UNCONFIRMED])


def test_status_labels_match_dashboard_js():
    """四态中文标签在成品看板 JS 与本模块各有一份——必须逐字相同，否则同一状态
    在两个页面上会显示成两种说法。改一处而没改另一处，本测试即失败。"""
    from sc8.baoguan import _HTML_JS
    for code in (STATUS_NO_TRANSIT, STATUS_TRANSIT_UNCONFIRMED,
                 STATUS_TRANSIT_CONFIRMED, STATUS_CONFIRMED_NO_TRANSIT):
        assert f"{code}:'{mb.STATUS_LABELS[code]}'" in _HTML_JS


# ── 3.6 取数缺口列 ────────────────────────────────────────────────────────────

def test_gap_columns_are_explicitly_marked_never_blank():
    board = mb.build_material_board(
        [_row("F1", "2026-08-05", [_cst("R01", gap=10)])], today=TODAY, months=3)
    r = board.rows[0]
    assert r["brand"] == mb.FIELD_GAP and r["owner"] == mb.FIELD_GAP
    assert r["brand"].strip() != ""


def test_buyer_is_carried_but_never_fills_the_owner_column():
    """制单人已被真实数据证伪不等于「负责采购」——只随载荷保留供排障，不得顶替责任人。"""
    board = mb.build_material_board(
        [_row("F1", "2026-08-05", [_cst("R01", gap=10)])], today=TODAY, months=3,
        supply_by_material={"R01": {"suppliers": ["厦门信和达电子有限公司"],
                                    "buyers": ["尤胤栋", "沈潇敏"]}})
    r = board.rows[0]
    assert r["sup"] == ["厦门信和达电子有限公司"]
    assert r["buyers"] == ["尤胤栋", "沈潇敏"]
    assert r["owner"] == mb.FIELD_GAP


def test_missing_supply_data_does_not_raise():
    board = mb.build_material_board(
        [_row("F1", "2026-08-05", [_cst("R01", gap=10)])], today=TODAY, months=3,
        supply_by_material=None)
    assert board.rows[0]["sup"] == [] and board.rows[0]["buyers"] == []


# ── 4.1 Snapshot 新字段向后兼容 ───────────────────────────────────────────────

def test_old_snapshot_json_without_materials_key_deserializes_to_defaults():
    old = {"generated_at": "2026-08-01T10:00:00", "today": "2026-08-01",
           "rows": [], "counts": {"red": 0, "gap": 0, "yel": 0, "grn": 0},
           "status": "2", "param_version": "sc8-params-v1", "components": 0,
           "srm_hit": 0, "ok": True, "note": ""}
    snap = Snapshot(**json.loads(json.dumps(old)))
    assert snap.materials == [] and snap.materials_meta == {}


def test_snapshot_roundtrips_materials():
    snap = Snapshot(generated_at="x", today="2026-08-20",
                    materials=[{"id": "R01"}], materials_meta={"window": "2026-08 ~ 2026-10"})
    assert Snapshot(**json.loads(json.dumps(snap.to_dict()))).materials == [{"id": "R01"}]
