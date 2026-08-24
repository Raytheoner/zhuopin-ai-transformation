"""齐料日期按答交数量累计取值（队列 #344，`sc8-kit-date-qty-cumulative`）。

姚祖怡 `F02N.0224` 举证的根因：上方齐料日期/瓶颈物料取的是该物料**最早的那笔答交
日期**，完全不看那一笔答交了多少——连 `answerQty=0` 的记录也照用。下方 BOM 缺口清单
走 `_cumulative_confirmed_batches`（按数量累计至覆盖缺口，#18-a 口径正确），两者从此
在同一个函数上对齐。

四条口径全部由姚祖怡显式签认（采购部#16 三判例 ✅×3 ＋ 2026-08-19 文本回件「对」），
见 `openspec/changes/sc8-kit-date-qty-cumulative/proposal.md`。
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from zhuopin_platform.shared_tools.models import BomRow, SrmDeliveryOrder

from sc8 import baoguan, forecast
from sc8.config import ForecastParams
from sc8.forecast import estimate_material_arrivals
from sc8.models import SalesOrder


# ── 夹具 ────────────────────────────────────────────────────────────────────
# 判例 1 的真实答交序列（2026-08-18 当日真实取数，见 proposal.md「取证」）：
# 唯一有数量的一笔在 2027-05-20，而改造前引擎采用的是 2026-08-20 那笔 qty=0。
R01I_0622_REAL = [
    (date(2026, 8, 20), 0.0),
    (date(2026, 9, 20), 0.0),
    (date(2026, 10, 20), 0.0),
    (date(2026, 11, 20), 0.0),
    (date(2026, 12, 20), 0.0),
    (date(2027, 1, 20), 0.0),
    (date(2027, 2, 20), 0.0),
    (date(2027, 5, 20), 10000.0),
    (date(2027, 6, 20), 0.0),
]


def _bom_row(product_id: str, component_id: str, qty_per_unit: float = 1.0) -> BomRow:
    return BomRow(product_id=product_id, component_id=component_id,
                  component_name=component_id, level=1,
                  qty_per_unit=qty_per_unit, loss_rate=0.0, unit="PCS")


def _params() -> ForecastParams:
    return ForecastParams(no_feedback_lead_days=90, outsource_extra_days=10,
                          logistics_days=1, deviation_alert_days=3,
                          param_version="test")


def _arrivals(commitments, required, *, demand_date=date(2026, 9, 1),
              srm_deliveries=None, bom=None):
    """跑一次 `estimate_material_arrivals`（单成品单子件，除非另给 bom）。"""
    return estimate_material_arrivals(
        "F02N.0224", bom if bom is not None else [_bom_row("F02N.0224", "R01I.0622")],
        srm_deliveries if srm_deliveries is not None else [],
        demand_date=demand_date, params=_params(),
        material_commitments=commitments, required_qty=required,
    )


# ── 2.1 单一实现：下沉后两处导入指向同一个函数对象 ─────────────────────────
def test_cumulative_batches_is_one_single_implementation():
    """`_cumulative_confirmed_batches` 下沉到 forecast.py 后，baoguan.py 只是再导出。

    这条断言不是形式主义：上方齐料日与下方缺口清单曾各自为政，正是 #344 的成因。
    只要两处拿到的是同一个函数对象，口径就**不可能**漂移——而不是"记得同步改两处"。
    """
    assert baoguan._cumulative_confirmed_batches is forecast._cumulative_confirmed_batches
    # `material_board.py` 走的是 `from .baoguan import ...`，其导入路径必须保持可用
    from sc8.material_board import _cumulative_confirmed_batches as mb_fn
    assert mb_fn is forecast._cumulative_confirmed_batches


# ── 2.2 零漂移边界：两参齐备才走新分支 ──────────────────────────────────────
def test_legacy_path_when_commitments_absent():
    """`material_commitments=None` ⇒ 逐字节回到改造前的"最早承诺日"口径。"""
    srm = [SrmDeliveryOrder(delivery_id="SRM-R01I.0622", demand_id="",
                            supplier_id="", material_id="R01I.0622",
                            qty_committed=0, committed_date="2026-08-20",
                            status="planned")]
    mat = _arrivals(None, {"R01I.0622": 5000.0}, srm_deliveries=srm)
    assert mat.arrivals["R01I.0622"] == date(2026, 8, 20)
    assert mat.no_feedback_materials == []


def test_legacy_path_when_required_qty_absent():
    """只传 `material_commitments`、不传 `required_qty` ⇒ 仍走旧口径，不静默换一套。

    D4-(b) 被否决的理由：调用方漏传目标数量时若"按毛需求兜底"，就是一次静默回退——
    返回值完全正常、结论却是另一套口径。宁可不走新分支。
    """
    srm = [SrmDeliveryOrder(delivery_id="SRM-R01I.0622", demand_id="",
                            supplier_id="", material_id="R01I.0622",
                            qty_committed=0, committed_date="2026-08-20",
                            status="planned")]
    mat = _arrivals({"R01I.0622": R01I_0622_REAL}, None, srm_deliveries=srm)
    assert mat.arrivals["R01I.0622"] == date(2026, 8, 20)


# ── 2.3 判例 1（真实案例 R01I.0622） ────────────────────────────────────────
def test_case1_real_r01i_0622_skips_zero_qty_batches():
    """判例 1：齐料日 ＝ 2027-05-20（唯一有量的那笔），**不是** 2026-08-20。"""
    mat = _arrivals({"R01I.0622": R01I_0622_REAL}, {"R01I.0622": 5000.0})
    assert mat.arrivals["R01I.0622"] == date(2027, 5, 20)
    assert mat.no_feedback_materials == []
    assert mat.bottleneck_material == "R01I.0622"


# ── 2.4 判例 2（一笔即够，不再往后累） ──────────────────────────────────────
def test_case2_single_batch_covers_stops_there():
    commitments = {"M1": [(date(2026, 9, 20), 10000.0), (date(2026, 11, 20), 8000.0)]}
    mat = _arrivals(commitments, {"M1": 6000.0},
                    bom=[_bom_row("F02N.0224", "M1")])
    assert mat.arrivals["M1"] == date(2026, 9, 20)


# ── 2.5 判例 3（不够则继续累计到够） ────────────────────────────────────────
def test_case3_accumulates_until_covered():
    """8000＋9000 覆盖 15000 ⇒ 取第二笔 2027-01-20，不是第一笔也不是第三笔。"""
    commitments = {"M1": [(date(2026, 10, 20), 8000.0),
                          (date(2027, 1, 20), 9000.0),
                          (date(2027, 3, 20), 5000.0)]}
    mat = _arrivals(commitments, {"M1": 15000.0}, bom=[_bom_row("F02N.0224", "M1")])
    assert mat.arrivals["M1"] == date(2027, 1, 20)
    assert mat.no_feedback_materials == []


def test_case3_exact_boundary_counts_as_covered():
    """累计**恰好等于**需求即算覆盖（`>=`，不是 `>`）——边界一位之差会整体挪一笔。"""
    commitments = {"M1": [(date(2026, 10, 20), 8000.0), (date(2027, 1, 20), 7000.0),
                          (date(2027, 3, 20), 1.0)]}
    mat = _arrivals(commitments, {"M1": 15000.0}, bom=[_bom_row("F02N.0224", "M1")])
    assert mat.arrivals["M1"] == date(2027, 1, 20)


# ── 2.6 口径 ⑷：全 0 等同无答交，走无答交启发式 ─────────────────────────────
def test_rule4_all_zero_batches_equals_no_answer():
    """姚祖怡 2026-08-19 文本回件：「有答交记录但数量为 0」等同没有答交，走规则 2。

    关键断言是**最后一条**：绝不把那个 0 数量的日期当齐料日。
    """
    all_zero = [(d, 0.0) for d, _ in R01I_0622_REAL]
    demand = date(2026, 9, 1)
    mat = _arrivals({"R01I.0622": all_zero}, {"R01I.0622": 5000.0}, demand_date=demand)
    assert "R01I.0622" in mat.no_feedback_materials
    assert mat.arrivals["R01I.0622"] == demand + timedelta(days=90)
    assert mat.arrivals["R01I.0622"] != date(2026, 8, 20)


def test_no_commitment_record_falls_back_to_legacy_date_not_no_answer():
    """🔴 design D1（2026-08-24 被真实数据当场改判）：逐笔明细里**根本没有**这个料时，
    **原样沿用改造前的最早承诺日**，而不是判"无答交"。

    第一版实现把它判成无答交（照搬 #296 v4 给状态列定的口径）。改回来的理由是
    **授权边界**：那等于把 #211 v2 的 `receiveType==2` 筛选推广到四色判定上，而
    #211 v2 原文明写「范围仅限本函数……未经授权不改判定逻辑」。队列 #344 领的活是
    「答交数量匹配那一层」，换取数源是另一条判据，已另行登记待姚祖怡签认。

    ⚠️ **不要拿影响面来论证这件事**：实测换源变体与本口径只差 2 行、四色计数完全
    相同（都是 105 红），106 这个数字唬人但对结论毫无贡献——两个方向都能用影响面
    编出理由。判据只有一条：谁授权的。
    """
    demand = date(2026, 9, 1)
    srm = [SrmDeliveryOrder(delivery_id="a", demand_id="", supplier_id="",
                            material_id="R01I.0622", qty_committed=0,
                            committed_date="2026-10-15", status="confirmed")]
    mat = _arrivals({}, {"R01I.0622": 5000.0}, demand_date=demand, srm_deliveries=srm)
    assert mat.no_feedback_materials == []
    assert mat.arrivals["R01I.0622"] == date(2026, 10, 15)


def test_no_commitment_and_no_srm_date_is_no_answer():
    """两条管线都查无此料 ⇒ 未答交，走启发式（与改造前完全一致）。"""
    demand = date(2026, 9, 1)
    mat = _arrivals({}, {"R01I.0622": 5000.0}, demand_date=demand)
    assert "R01I.0622" in mat.no_feedback_materials
    assert mat.arrivals["R01I.0622"] == demand + timedelta(days=90)


def test_all_zero_batches_beat_a_legacy_srm_date():
    """口径 ⑷ 优先于上一条的回退：**有记录但全 0** ⇒ 判无答交，即便 srm 侧另有日期。

    这正是判例 1 的形状——`R01I.0622` 的 srm 日期 2026-08-20 恰恰来自那笔 qty=0，
    若让 legacy 回退在这里生效，本变更就等于什么都没修。
    """
    demand = date(2026, 9, 1)
    srm = [SrmDeliveryOrder(delivery_id="a", demand_id="", supplier_id="",
                            material_id="R01I.0622", qty_committed=0,
                            committed_date="2026-08-20", status="planned")]
    all_zero = [(d, 0.0) for d, _ in R01I_0622_REAL]
    mat = _arrivals({"R01I.0622": all_zero}, {"R01I.0622": 5000.0},
                    demand_date=demand, srm_deliveries=srm)
    assert "R01I.0622" in mat.no_feedback_materials
    assert mat.arrivals["R01I.0622"] == demand + timedelta(days=90)
    assert mat.arrivals["R01I.0622"] != date(2026, 8, 20)


# ── 2.7 D3：答了但累计不够（签认口径未覆盖，我方保守外推） ──────────────────
def test_d3_partial_coverage_is_no_answer_and_takes_the_later_date():
    """答了 8000、需求 15000 ⇒ 判无答交，且到货日取 max(启发式估算日, 最晚正数答交日)。

    取更晚与姚祖怡自己写的规则 3（「更晚的那一个是齐套日期」）同向；只取估算日会
    再次低估——低估正是本变更要根治的病。
    """
    demand = date(2026, 9, 1)
    commitments = {"M1": [(date(2027, 5, 20), 8000.0)]}
    mat = _arrivals(commitments, {"M1": 15000.0}, demand_date=demand,
                    bom=[_bom_row("F02N.0224", "M1")])
    assert "M1" in mat.no_feedback_materials
    assert mat.arrivals["M1"] == date(2027, 5, 20)      # 晚于 demand+90 (2026-11-30)


def test_d3_partial_coverage_reverse_branch_takes_the_estimate():
    """反向分支：最晚正数答交日**早于**估算日 ⇒ 取估算日（仍是"更晚的那一个"）。"""
    demand = date(2026, 9, 1)
    commitments = {"M1": [(date(2026, 9, 10), 8000.0)]}
    mat = _arrivals(commitments, {"M1": 15000.0}, demand_date=demand,
                    bom=[_bom_row("F02N.0224", "M1")])
    assert "M1" in mat.no_feedback_materials
    assert mat.arrivals["M1"] == demand + timedelta(days=90)


def test_d3_zero_case_is_a_special_case_of_the_same_rule():
    """全 0 是 D3 的特例、不是例外：没有正数答交日 ⇒ max 退化为纯估算日 ⇒ 复现口径 ⑷。"""
    demand = date(2026, 9, 1)
    only_zeros = {"M1": [(date(2027, 5, 20), 0.0)]}
    mat = _arrivals(only_zeros, {"M1": 15000.0}, demand_date=demand,
                    bom=[_bom_row("F02N.0224", "M1")])
    assert mat.arrivals["M1"] == demand + timedelta(days=90)


# ── 2.8 瓶颈物料 / kit_date 随新到货日联动 ───────────────────────────────────
def test_bottleneck_follows_new_arrival_dates():
    """改了 arrivals 就必须改瓶颈——否则等于只修了一半。

    M1 旧口径下最早答交日 2026-09-20（早于 M2 的 2026-12-01）⇒ 旧瓶颈是 M2；
    新口径下 M1 要累计到 2027-05-20 才够 ⇒ 新瓶颈是 M1。
    """
    bom = [_bom_row("F02N.0224", "M1"), _bom_row("F02N.0224", "M2")]
    commitments = {
        "M1": [(date(2026, 9, 20), 0.0), (date(2027, 5, 20), 10000.0)],
        "M2": [(date(2026, 12, 1), 10000.0)],
    }
    required = {"M1": 5000.0, "M2": 5000.0}

    legacy = estimate_material_arrivals(
        "F02N.0224", bom,
        [SrmDeliveryOrder(delivery_id="a", demand_id="", supplier_id="",
                          material_id="M1", qty_committed=0,
                          committed_date="2026-09-20", status="planned"),
         SrmDeliveryOrder(delivery_id="b", demand_id="", supplier_id="",
                          material_id="M2", qty_committed=0,
                          committed_date="2026-12-01", status="planned")],
        demand_date=date(2026, 9, 1), params=_params())
    assert legacy.bottleneck_material == "M2"
    assert max(legacy.arrivals.values()) == date(2026, 12, 1)

    fixed = _arrivals(commitments, required, bom=bom)
    assert fixed.bottleneck_material == "M1"
    assert max(fixed.arrivals.values()) == date(2027, 5, 20)


# ── 3.x 调用层（assess_supply_risk） ────────────────────────────────────────
def _so(qty: float = 5000.0, required_date: str = "2026-10-01") -> SalesOrder:
    return SalesOrder(so_id="SO-344", item_code="F02N.0224", item_name="测试成品",
                      qty=qty, required_date=required_date,
                      customer_id="C1", customer_name="测试客户")


def test_assess_uses_gross_as_target_when_net_inventory_off(monkeypatch):
    monkeypatch.setattr("sc8.config.net_inventory_enabled", lambda: False)
    row = baoguan.assess_supply_risk(
        _so(qty=5000.0), [_bom_row("F02N.0224", "R01I.0622")], [],
        today=date(2026, 9, 1), params=_params(),
        material_commitments={"R01I.0622": R01I_0622_REAL},
        inventory={"R01I.0622": 4000.0},   # 传了也不该生效（开关 OFF）
    )
    # 毛需求 5000 ≤ 10000 ⇒ 2027-05-20 那笔即覆盖
    assert row.kit_date == date(2027, 5, 20)


def test_assess_uses_gap_as_target_when_net_inventory_on(monkeypatch):
    """净额 ON ⇒ 累计目标 ＝ 缺口（gross − 现货），与 `_component_supply_status` 逐字一致。

    毛需求 12000、现货 4000 ⇒ 缺口 8000；答交 5000@10-20 ＋ 6000@2027-01-20 ⇒ 累计
    11000 覆盖 8000，取 2027-01-20。若错按毛需求 12000 当目标，则要累到第三笔。
    """
    monkeypatch.setattr("sc8.config.net_inventory_enabled", lambda: True)
    commitments = {"M1": [(date(2026, 10, 20), 5000.0),
                          (date(2027, 1, 20), 6000.0),
                          (date(2027, 4, 20), 6000.0)]}
    row = baoguan.assess_supply_risk(
        _so(qty=12000.0), [_bom_row("F02N.0224", "M1")], [],
        today=date(2026, 9, 1), params=_params(),
        material_commitments=commitments, inventory={"M1": 4000.0})
    assert row.kit_date == date(2027, 1, 20)


def test_top_kit_date_matches_bottom_gap_list_last_batch(monkeypatch):
    """🔴 本变更的存在理由：上方齐料日采用的那一笔，与下方 BOM 缺口清单累计明细的
    最后一笔，必须是同一天。

    改造前这条断言是红的——那就是姚祖怡说的「下面的清单对、上面的汇总数不对」。
    """
    monkeypatch.setattr("sc8.config.net_inventory_enabled", lambda: True)
    commitments = {"R01I.0622": R01I_0622_REAL}
    row = baoguan.assess_supply_risk(
        _so(qty=5000.0), [_bom_row("F02N.0224", "R01I.0622")], [],
        today=date(2026, 9, 1), params=_params(),
        material_commitments=commitments, inventory={"R01I.0622": 0.0},
        purchase_orders={})
    gap_rows = [c for c in row.component_status if c.component_id == "R01I.0622"]
    assert gap_rows, "缺口清单里应有该子件"
    assert gap_rows[0].confirmed_batches, "应有累计答交明细"
    assert gap_rows[0].confirmed_batches[-1][0] == row.kit_date


def test_assess_zero_drift_when_commitments_none(monkeypatch):
    """数据源整体加载失败降级（`material_commitments=None`）⇒ 与改造前完全一致。"""
    monkeypatch.setattr("sc8.config.net_inventory_enabled", lambda: True)
    srm = [SrmDeliveryOrder(delivery_id="a", demand_id="", supplier_id="",
                            material_id="R01I.0622", qty_committed=0,
                            committed_date="2026-08-20", status="planned")]
    row = baoguan.assess_supply_risk(
        _so(qty=5000.0), [_bom_row("F02N.0224", "R01I.0622")], srm,
        today=date(2026, 9, 1), params=_params(),
        material_commitments=None, inventory={"R01I.0622": 0.0})
    assert row.kit_date == date(2026, 8, 20)


def test_material_fully_covered_by_stock_does_not_break(monkeypatch):
    """现货已完全覆盖（缺口 ≤ 0）的子件不因新口径产生异常到货日或异常四色。"""
    monkeypatch.setattr("sc8.config.net_inventory_enabled", lambda: True)
    row = baoguan.assess_supply_risk(
        _so(qty=5000.0), [_bom_row("F02N.0224", "R01I.0622")], [],
        today=date(2026, 9, 1), params=_params(),
        material_commitments={"R01I.0622": R01I_0622_REAL},
        inventory={"R01I.0622": 99999.0})
    assert row.risk == baoguan.RISK_GREEN
    assert row.kit_date is None


# ── 4.1 展示层：过期文案已撤 ────────────────────────────────────────────────
def test_materials_page_no_longer_claims_pending_confirmation():
    """队列 #334 行内登记的尾巴：齐料日期口径已签认并落地，页面不得再写"待回件"。"""
    from sc8 import webapp
    html = webapp._materials_page()
    assert "待回件" not in html
    assert "正在与采购部确认中" not in html
