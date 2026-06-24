"""成品保供预警看板（baoguan）逻辑测试 —— 全 mock，不触网（§7.1 先跑通逻辑）。

覆盖：
  · 全部子件无答复 → 齐料=max(出货日,今天)+30 → 🔴；
  · 出货日已过 → 基准取"今天"（验证 max(需求日,今天) 而非需求日+30）；
  · 全部子件有承诺且早于出货 → 🟢；
  · 部分承诺 + 无答复 → 瓶颈=无答复子件、🔴；
  · 无 BOM → 🔴 + gap=None；
  · 看板渲染三色分组 + 计数。
"""
from __future__ import annotations

from datetime import date

import pytest
from zhuopin_platform.shared_tools.models import BomRow, SrmDeliveryOrder

from sc8.baoguan import (RISK_GAP, RISK_GREEN, RISK_RED, RISK_YELLOW,
                         assess_supply_risk, build_dashboard, render_html,
                         render_markdown)
from sc8.models import SalesOrder

TODAY = date(2026, 6, 22)


def _so(item="S02Y.0035", ship="2026-09-01", name="ECU", cust="比亚迪", qty=1000):
    return SalesOrder(so_id=f"FO-{item}", customer_id="", customer_name=cust,
                      item_code=item, qty=qty, required_date=ship,
                      doc_type="预测订单", item_name=name)


def _bom(product, *components):
    return [BomRow(product_id=product, component_id=c, component_name=c,
                   level=1, qty_per_unit=1.0, loss_rate=0.0, unit="PCS")
            for c in components]


def _srm(material, committed):
    return SrmDeliveryOrder(delivery_id=f"SRM-{material}", demand_id="", supplier_id="",
                            material_id=material, qty_committed=0,
                            committed_date=committed, status="confirmed")


def test_all_no_feedback_is_gap():
    """全部子件无答复 → 无确定承诺可判定 → 🟠 待催（非真延期红）。"""
    so = _so(ship="2026-09-01")
    bom = _bom("S02Y.0035", "R02A.0498", "R02D.0041")
    row = assess_supply_risk(so, bom, [], today=TODAY)
    # 无答复 → 齐料估算 = max(09-01,06-22)+30 = 10-01；gap = 30（仅参考）
    assert row.kit_date == date(2026, 10, 1)
    assert row.gap_days == 30
    assert row.risk == RISK_GAP                  # 待催，不是真延期
    assert row.confirmed_gap_days is None        # 无确定承诺 → 无确定缺口
    assert set(row.no_feedback_materials) == {"R02A.0498", "R02D.0041"}
    assert row.component_count == 2


def test_confirmed_late_is_red():
    """有真实承诺、但确定齐料晚出货 >3 天 → 🔴 真延期（硬信号）。"""
    so = _so(ship="2026-09-01")
    bom = _bom("S02Y.0035", "R02A.0498")
    row = assess_supply_risk(so, bom, [_srm("R02A.0498", "2026-11-30")], today=TODAY)
    assert row.confirmed_gap_days == (date(2026, 11, 30) - date(2026, 9, 1)).days  # +90
    assert row.risk == RISK_RED
    assert row.no_feedback_materials == []


def test_past_ship_date_uses_today_base():
    """出货日已过（06-10 < 今天 06-22）→ 基准必须取今天，估算 gap=42 而非 30。"""
    so = _so(ship="2026-06-10")
    bom = _bom("S02Y.0035", "R02E.0081")
    row = assess_supply_risk(so, bom, [], today=TODAY)
    # max(06-10,06-22)+30 = 07-22；gap = (07-22 − 06-10) = 42（若误用需求日+30 则为 30）
    assert row.kit_date == date(2026, 7, 22)
    assert row.gap_days == 42
    assert row.risk == RISK_GAP                  # 无答复 → 待催（估算 gap 仅参考）


def test_all_confirmed_before_ship_is_green():
    so = _so(ship="2026-09-01")
    bom = _bom("S02Y.0035", "R02A.0498", "R02D.0041")
    srm = [_srm("R02A.0498", "2026-08-01"), _srm("R02D.0041", "2026-08-15")]
    row = assess_supply_risk(so, bom, srm, today=TODAY)
    assert row.kit_date == date(2026, 8, 15)        # 最晚承诺
    assert row.gap_days == (date(2026, 8, 15) - date(2026, 9, 1)).days  # 负数
    assert row.risk == RISK_GREEN
    assert row.no_feedback_materials == []


def test_partial_confirmed_bottleneck_is_no_feedback_component():
    so = _so(ship="2026-09-01")
    bom = _bom("S02Y.0035", "R02A.0498", "R02D.0041")
    srm = [_srm("R02A.0498", "2026-08-01")]          # 仅 A 有承诺(按期)，B 无答复
    row = assess_supply_risk(so, bom, srm, today=TODAY)
    # A 确定承诺 08-01 早于出货 → 无确定延期；B 无答复 → 🟠 待催（瓶颈=无答复子件）
    assert row.kit_date == date(2026, 10, 1)
    assert row.bottleneck_material == "R02D.0041"
    assert row.no_feedback_materials == ["R02D.0041"]
    assert row.confirmed_gap_days == (date(2026, 8, 1) - date(2026, 9, 1)).days  # 负，A 按期
    assert row.risk == RISK_GAP


def test_no_bom_is_red_with_none_gap():
    so = _so(item="F02N.0999", ship="2026-09-01")
    row = assess_supply_risk(so, [], [], today=TODAY)   # 无 BOM
    assert row.has_bom is False
    assert row.gap_days is None
    assert row.kit_date is None
    assert row.risk == RISK_RED
    assert "无 BOM" in row.action


def test_yellow_band_1_to_3_days():
    # 构造 gap 恰好 2 天：子件承诺 = 出货日+2
    so = _so(ship="2026-09-01")
    bom = _bom("S02Y.0035", "R02A.0498")
    row = assess_supply_risk(so, bom, [_srm("R02A.0498", "2026-09-03")], today=TODAY)
    assert row.gap_days == 2
    assert row.risk == RISK_YELLOW


def test_build_dashboard_sorts_red_first():
    green = _so(item="GREEN", ship="2026-09-01")
    gap = _so(item="GAP", ship="2026-09-01")
    red = _so(item="RED", ship="2026-06-10")
    bom = _bom("GREEN", "C1") + _bom("GAP", "C3") + _bom("RED", "C2")
    # GREEN 齐套(按期)；RED 有承诺但确定晚(真延期)；GAP 无答复(待催)
    srm = [_srm("C1", "2026-08-01"), _srm("C2", "2026-08-01")]
    rows = build_dashboard([green, gap, red], bom, srm, today=TODAY)
    assert rows[0].product_id == "RED" and rows[0].risk == RISK_RED       # 真延期最前
    assert rows[1].product_id == "GAP" and rows[1].risk == RISK_GAP       # 待催次之
    assert rows[-1].product_id == "GREEN" and rows[-1].risk == RISK_GREEN  # 按期最后


def test_render_markdown_has_groups_and_counts():
    so_red = _so(item="RED", ship="2026-06-10")
    bom = _bom("RED", "C2")
    srm = [_srm("C2", "2026-08-01")]     # 有承诺但确定晚于出货 → 真延期红
    md = render_markdown(build_dashboard([so_red], bom, srm, today=TODAY), today=TODAY)
    assert "成品保供预警看板" in md
    assert "🔴 保供高风险" in md
    assert "2026-06-22" in md            # 生成日
    assert "RED" in md


def test_render_markdown_gap_group_for_no_feedback():
    so = _so(item="WAIT", ship="2026-09-01")
    md = render_markdown(build_dashboard([so], _bom("WAIT", "C9"), [], today=TODAY), today=TODAY)
    assert "🟠 承诺缺口" in md           # 无答复 → 待催分组


def test_render_html_is_interactive_standalone_page():
    so_red = _so(item="S02Y.0188", ship="2026-06-10", cust="深圳立达<测试>")
    bom = _bom("S02Y.0188", "R01B.0365", "R01B.0001")
    html = render_html(build_dashboard([so_red], bom, [], today=TODAY), today=TODAY)
    assert html.startswith("<!DOCTYPE html>")
    assert "<title>成品保供预警看板</title>" in html
    assert "S02Y.0188" in html                       # 数据载荷
    assert "子件承诺覆盖" in html                     # 卡片模板（JS）
    # 互动控件 + 移植自 supplychain 的能力都在
    assert 'id="cards"' in html and 'id="q"' in html and 'id="fbtns"' in html
    assert "导出 CSV" in html and "按缺口天数" in html
    # gap=42 进了数据载荷（max(06-10,06-22)+30 − 06-10 = 42，今天基准）
    assert '"gap": 42' in html
    # 客户名中的 < > 被转义为 \\u003c（防 </script> 破出 + 防注入），原始尖括号不出现
    assert "深圳立达<测试>" not in html
    assert "\\u003c" in html
