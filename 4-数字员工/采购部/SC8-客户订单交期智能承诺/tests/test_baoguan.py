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
                         render_markdown, row_to_dict)
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


def test_all_no_feedback_is_red_conservative():
    """全部子件无答复 → 无确定承诺，但按保守估算（90天）晚出货远超3天门槛 → 🔴（队列#147续，
    2026-07-29 Paul 拍板：看板是保守预测，未答复子件按90天估算折入严重度，不降级成"待催"）。"""
    so = _so(ship="2026-09-01")
    bom = _bom("S02Y.0035", "R02A.0498", "R02D.0041")
    row = assess_supply_risk(so, bom, [], today=TODAY)
    # 无答复 → 齐料估算 = max(09-01,06-22)+90 = 11-30（v1，姚祖怡 07-23 校准 90 天）；gap = 90
    assert row.kit_date == date(2026, 11, 30)
    assert row.gap_days == 90
    assert row.risk == RISK_RED                  # 保守预警，红（不再是待催）
    assert "保守预警" in row.action              # 措辞区分：非真实确认的延期
    assert row.confirmed_gap_days is None        # 无确定承诺 → 无确定缺口
    assert set(row.no_feedback_materials) == {"R02A.0498", "R02D.0041"}
    assert row.component_count == 2
    # 判据说明 V2 答复2（姚祖怡 07-23，Paul 同日拍板）：展示无答复子件明细（料号+数量+估算到货日）
    detail_by_id = {d.component_id: d for d in row.no_feedback_detail}
    assert set(detail_by_id) == {"R02A.0498", "R02D.0041"}
    for d in detail_by_id.values():
        assert d.qty == 1000.0                       # so.qty(默认1000) × qty_per_unit(1.0)
        assert d.estimated_arrival == date(2026, 11, 30)


def test_confirmed_late_is_red():
    """有真实承诺、但确定齐料晚出货 >3 天 → 🔴 真延期（硬信号）。"""
    so = _so(ship="2026-09-01")
    bom = _bom("S02Y.0035", "R02A.0498")
    row = assess_supply_risk(so, bom, [_srm("R02A.0498", "2026-11-30")], today=TODAY)
    assert row.confirmed_gap_days == (date(2026, 11, 30) - date(2026, 9, 1)).days  # +90
    assert row.risk == RISK_RED
    assert row.no_feedback_materials == []


def test_past_ship_date_uses_today_base():
    """出货日已过（06-10 < 今天 06-22）→ 基准必须取今天，估算 gap=102 而非 90。"""
    so = _so(ship="2026-06-10")
    bom = _bom("S02Y.0035", "R02E.0081")
    row = assess_supply_risk(so, bom, [], today=TODAY)
    # max(06-10,06-22)+90 = 09-20；gap = (09-20 − 06-10) = 102（若误用需求日+90 则为 90）
    assert row.kit_date == date(2026, 9, 20)
    assert row.gap_days == 102
    assert row.risk == RISK_RED                  # 无答复但按保守估算晚出货远超3天 → 红（队列#147续）


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
    # A 确定承诺 08-01 早于出货 → 无确定延期；B 无答复按90天估算晚出货 → 🔴保守预警
    # （队列#147续：瓶颈=无答复子件 B，全量口径 gap_days 驱动判定，不再降级为待催）
    assert row.kit_date == date(2026, 11, 30)
    assert row.bottleneck_material == "R02D.0041"
    assert row.no_feedback_materials == ["R02D.0041"]
    assert row.confirmed_gap_days == (date(2026, 8, 1) - date(2026, 9, 1)).days  # 负，A 按期
    assert row.risk == RISK_RED
    assert "保守预警" in row.action
    # 明细只含无答复的 B，不含已确认承诺的 A（避免误导——A 已有真实交期，非估算）
    assert [d.component_id for d in row.no_feedback_detail] == ["R02D.0041"]


def test_confirmed_bottleneck_differs_from_overall_bottleneck_when_no_feedback_material_later():
    """真实缺陷复现（姚祖怡 07-29 二次举证，队列 #147，S02Y.0135 真实案例同构）：

    子件 A 有确定承诺、晚出货 14 天（>3 天 →🔴真延期，driving confirmed_gap_days）；
    子件 B 无答复，估算到货远晚于 A（driving 全量 kit_date/bottleneck_material）。
    两套指标（确定 vs 全量）各自计算正确，但指向**不同**的瓶颈子件与日期——
    这正是卡片头部"确定齐料晚 N 天"徽标与"出货→齐料"日期/瓶颈对不上的根因。
    """
    so = _so(ship="2026-09-01")
    bom = _bom("S02Y.0035", "A", "B")
    row = assess_supply_risk(so, bom, [_srm("A", "2026-09-15")], today=TODAY)
    assert row.risk == RISK_RED
    assert row.confirmed_gap_days == 14
    assert row.confirmed_bottleneck == "A"                  # 徽标依据的瓶颈
    assert row.confirmed_kit_date == date(2026, 9, 15)       # 徽标依据的日期
    assert row.bottleneck_material == "B"                    # 全量口径瓶颈（与上面不同）
    assert row.kit_date == date(2026, 11, 30)                # 全量口径日期（与上面不同）
    # 两者确实不同——这就是本缺陷的核心：不能在同一处展示位混用两套指标
    assert row.confirmed_bottleneck != row.bottleneck_material
    assert row.confirmed_kit_date != row.kit_date


def test_confirmed_bottleneck_none_when_no_confirmed_materials():
    """全部子件无答复 → confirmed_bottleneck/confirmed_kit_date 均为 None（无确定口径可展示，前端应回退全量口径）。"""
    so = _so(ship="2026-09-01")
    bom = _bom("S02Y.0035", "A", "B")
    row = assess_supply_risk(so, bom, [], today=TODAY)
    assert row.confirmed_bottleneck is None
    assert row.confirmed_kit_date is None


def test_row_to_dict_serializes_confirmed_kit_and_bottleneck():
    """row_to_dict 的 ckit/cbn 与 confirmed_kit_date/confirmed_bottleneck 一致，供前端卡片头部改用（队列 #147）。"""
    so = _so(ship="2026-09-01")
    bom = _bom("S02Y.0035", "A", "B")
    row = assess_supply_risk(so, bom, [_srm("A", "2026-09-15")], today=TODAY)
    d = row_to_dict(row)
    assert d["ckit"] == "2026-09-15"
    assert d["cbn"] == "A"
    # 全量口径字段保持不变，未被本次修复覆盖或删除
    assert d["kit"] == "2026-11-30"
    assert d["bn"] == "B"


def test_row_to_dict_ckit_cbn_empty_when_no_confirmed_materials():
    so = _so(ship="2026-09-01")
    bom = _bom("S02Y.0035", "A", "B")
    row = assess_supply_risk(so, bom, [], today=TODAY)
    d = row_to_dict(row)
    assert d["ckit"] is None
    assert d["cbn"] == ""


def test_render_html_card_header_and_badge_share_overall_gap_source():
    """卡片头部渲染逻辑（队列 #147 续，2026-07-29 Paul 拍板改口径）：徽标与头部
    "出货→齐料"日期/瓶颈统一改回都用全量口径（r.gap/r.kit/r.bn，天然取确定与
    估算中较严重者），二者同源即不会再对不上；r.ckit/r.cbn（确定口径）仍保留
    在数据载荷里供 action 文案区分措辞，但不再是头部展示的默认来源。
    """
    so = _so(ship="2026-09-01")
    bom = _bom("S02Y.0035", "A", "B")
    rows = [assess_supply_risk(so, bom, [_srm("A", "2026-09-15")], today=TODAY)]
    html = render_html(rows, today=TODAY)
    # ckit/cbn 字段仍在数据载荷里（未删除），但头部渲染不再优先它们
    assert "r.ckit" in html and "r.cbn" in html
    assert "headKitDate" not in html and "headBnId" not in html
    # 徽标/头部改用 r.gap（全量口径），措辞按瓶颈是否已答复区分"确定"/"保守预警"
    assert "bottleneckUnanswered" in html
    assert "保守预警" in html and "确定齐料晚" in html


def test_no_feedback_detail_empty_when_all_confirmed():
    """全部子件均有承诺 → no_feedback_detail 为空（无估算子件可展示）。"""
    so = _so(ship="2026-09-01")
    bom = _bom("S02Y.0035", "R02A.0498", "R02D.0041")
    srm = [_srm("R02A.0498", "2026-08-01"), _srm("R02D.0041", "2026-08-15")]
    row = assess_supply_risk(so, bom, srm, today=TODAY)
    assert row.no_feedback_detail == []


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


def test_gap_days_arithmetic_matches_calendar_day_span():
    """锁住 gap_days = (齐料日 − 出货日).days 的纯算术（姚祖怡 V6 #8"齐料晚+41天"
    质疑，现网复核结论：现网不复现，算术本身正确——见 V6回件-分类裁决与现网复核
    §3.1）。用她报告里的两组真实数字直接锁算法，防未来回归：
      · S02Y.0135：出货 07-10 → 齐套 10-25，真实缺口 = 107 天（她引用的"104天"
        实为不同齐套日 10-22 所致，非本函数计算错误）；
      · 另一料号 S02Y.0035：出货 07-10 → 齐套 08-20，缺口 = 41 天（她看到的
        "+41天"字样来自这一行，与 S02Y.0135 无关，高度疑为看串行）。
    两组均为公历日期相减，与 Python date 减法结果比对，双重锁定不依赖人工心算。
    """
    so_a = _so(item="S02Y.0135", ship="2026-07-10")
    row_a = assess_supply_risk(so_a, _bom("S02Y.0135", "R01B.0115"),
                               [_srm("R01B.0115", "2026-10-25")], today=TODAY)
    assert row_a.gap_days == 107
    assert row_a.gap_days == (date(2026, 10, 25) - date(2026, 7, 10)).days

    so_b = _so(item="S02Y.0035", ship="2026-07-10")
    row_b = assess_supply_risk(so_b, _bom("S02Y.0035", "R02A.0019"),
                               [_srm("R02A.0019", "2026-08-20")], today=TODAY)
    assert row_b.gap_days == 41
    assert row_b.gap_days == (date(2026, 8, 20) - date(2026, 7, 10)).days


def test_build_dashboard_sorts_by_risk_tier_then_gap_days_desc():
    """排序：先按风险等级、同等级内缺口天数降序（队列#147续，2026-07-29 Paul 拍板改口径后：
    无答复子件按90天保守估算同样归入🔴，与真实确认延期同一色阶，按缺口大小排序区分）。"""
    green = _so(item="GREEN", ship="2026-09-01")
    unanswered = _so(item="UNANSWERED", ship="2026-09-01")        # 无答复→保守估算，gap=90
    confirmed_late = _so(item="CONFIRMEDLATE", ship="2026-06-10")  # 确定承诺延期，gap=52（更小）
    bom = _bom("GREEN", "C1") + _bom("UNANSWERED", "C3") + _bom("CONFIRMEDLATE", "C2")
    srm = [_srm("C1", "2026-08-01"), _srm("C2", "2026-08-01")]
    rows = build_dashboard([green, unanswered, confirmed_late], bom, srm, today=TODAY)
    assert rows[0].product_id == "UNANSWERED" and rows[0].risk == RISK_RED     # gap=90，最大，最前
    assert rows[1].product_id == "CONFIRMEDLATE" and rows[1].risk == RISK_RED  # gap=52
    assert rows[-1].product_id == "GREEN" and rows[-1].risk == RISK_GREEN     # 按期最后


def test_classify_gap_branch_still_reachable_structurally():
    """🟠"待催"分支结构性保留（Paul 2026-07-29 拍板："保留这个概念/UI，后续再优化"）：
    在当前生产参数（NO_FEEDBACK_LEAD_DAYS=90）下该分支不会被触发（见上面两个红色化
    测试），但直接单测 `_classify()` 验证分支代码本身仍正确——用 gap_days<=0 但
    no_feedback_n>0 的组合直接触发（真实生产中需 lead_days 配到很小才可能出现）。
    """
    from sc8.baoguan import RISK_GAP, _classify
    risk, action = _classify(0, None, True, None, 2, "C9", None, True)
    assert risk == RISK_GAP
    assert "待催" in action


def test_render_markdown_has_groups_and_counts():
    so_red = _so(item="RED", ship="2026-06-10")
    bom = _bom("RED", "C2")
    srm = [_srm("C2", "2026-08-01")]     # 有承诺但确定晚于出货 → 真延期红
    md = render_markdown(build_dashboard([so_red], bom, srm, today=TODAY), today=TODAY)
    assert "成品保供预警看板" in md
    assert "🔴 保供高风险" in md
    assert "2026-06-22" in md            # 生成日
    assert "RED" in md


def test_render_markdown_red_group_for_unanswered_conservative():
    """无答复子件按90天保守估算 → 归入🔴真延期分组（队列#147续，2026-07-29 Paul 拍板
    改口径后不再降级为"🟠 承诺缺口"待催分组）。"""
    so = _so(item="WAIT", ship="2026-09-01")
    md = render_markdown(build_dashboard([so], _bom("WAIT", "C9"), [], today=TODAY), today=TODAY)
    assert "🔴 保供高风险" in md
    assert "保守预警" in md


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
    # 姚祖怡 07-26 V6 #14：导出 CSV 与导出 Excel 重复，只保留导出 Excel
    assert "导出 CSV" not in html and 'id="csv"' not in html
    assert "导出 Excel" in html and "按缺口天数" in html
    # gap=102 进了数据载荷（max(06-10,06-22)+90 − 06-10 = 102，今天基准）
    assert '"gap": 102' in html
    # 客户名中的 < > 被转义为 \\u003c（防 </script> 破出 + 防注入），原始尖括号不出现
    assert "深圳立达<测试>" not in html
    assert "\\u003c" in html


def test_row_to_dict_passthrough_c1_c2_fields(monkeypatch):
    """C-1/C-2（sc8-baoguan-substitute-partial-kit）：row_to_dict 新增字段透传。"""
    from zhuopin_platform.shared_tools.models import BomRow as _BomRow
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(item="P1")
    bom = [
        _BomRow(product_id="P1", component_id="A", component_name="A", level=1,
               qty_per_unit=1.0, loss_rate=0.0, unit="PCS", sequence="10", is_substitute=False),
        _BomRow(product_id="P1", component_id="B", component_name="B", level=1,
               qty_per_unit=1.0, loss_rate=0.0, unit="PCS", sequence="10", is_substitute=True),
    ]
    row = assess_supply_risk(so, bom, [], today=TODAY, inventory={"A": 400, "B": 400})
    d = row_to_dict(row)
    assert d["subs"] == {"A": ["B"]}
    # ksf = 凑够客户下单总量 so.qty(1000) 还差多少 = 1000 - 800 = 200（姚祖怡 07-16 确认口径）
    assert d["kq"] == 800 and d["kbn"] == "A" and d["ksf"] == 200


def test_row_to_dict_c1_c2_defaults_when_absent():
    """无替代料/无现货数据：subs 为空对象，kq/kbn/ksf 为 None（不以 0 冒充）。"""
    so = _so(item="P2")
    bom = _bom("P2", "R01")
    row = assess_supply_risk(so, bom, [], today=TODAY)
    d = row_to_dict(row)
    assert d["subs"] == {}
    assert d["kq"] is None and d["kbn"] is None and d["ksf"] is None


def test_row_to_dict_no_feedback_detail_passthrough():
    """判据说明 V2 答复2：row_to_dict 透传无答复子件明细（料号+数量+估算到货日），供前端展示。"""
    so = _so(item="P3", ship="2026-09-01", qty=500)
    bom = _bom("P3", "R09")
    row = assess_supply_risk(so, bom, [], today=TODAY)
    d = row_to_dict(row)
    # ③ 功能批1：nfd 明细新增 name（品名，取自 BOM component_name，测试 helper 里与料号同值）
    assert d["nfd"] == [{"id": "R09", "qty": 500.0, "eta": "2026-11-30", "name": "R09"}]


def test_render_html_shows_partial_kit_and_substitute_badges(monkeypatch):
    """看板 HTML 内嵌数据含 subs/kq 字段，供前端渲染"可齐套"徽标与"含替代料"标注。"""
    from zhuopin_platform.shared_tools.models import BomRow as _BomRow
    monkeypatch.setenv("SC8_NET_INVENTORY", "on")
    so = _so(item="S02Y.0188", ship="2026-06-10")
    bom = [
        _BomRow(product_id="S02Y.0188", component_id="R01B.0365", component_name="R01B.0365",
               level=1, qty_per_unit=1.0, loss_rate=0.0, unit="PCS",
               sequence="10", is_substitute=False),
        _BomRow(product_id="S02Y.0188", component_id="R01B.0999", component_name="R01B.0999",
               level=1, qty_per_unit=1.0, loss_rate=0.0, unit="PCS",
               sequence="10", is_substitute=True),
    ]
    rows = build_dashboard([so], bom, [], today=TODAY, inventory={"R01B.0365": 300, "R01B.0999": 300})
    html = render_html(rows, today=TODAY)
    assert '"subs": {"R01B.0365": ["R01B.0999"]}' in html
    assert '"kq": 600' in html
    assert "function subsText" in html and "可齐套" in html


def test_render_html_shows_no_feedback_detail():
    """判据说明 V2 答复2：HTML 内嵌数据含 nfd 明细，前端渲染函数/样式就绪。"""
    so = _so(item="S02Y.0188", ship="2026-06-10", qty=200)
    bom = _bom("S02Y.0188", "R01B.0365")
    rows = build_dashboard([so], bom, [], today=TODAY)
    html = render_html(rows, today=TODAY)
    assert '"nfd": [{"id": "R01B.0365", "qty": 200.0, "eta": "2026-09-20", "name": "R01B.0365"}]' in html
    assert "function nfdText" in html and ".nfd{" in html


def test_render_html_has_feedback_buttons(monkeypatch):
    """队列 #110 Feature A：看板每行内嵌 ✅正确/❌误判 反馈按钮，POST 到 /api/baoguan/feedback，
    行标识用 (id, so, ship) 三元组（与案例去重稳定键同一口径）。红线：只采集标注，不改判据
    ——本测试只断言渲染/接口存在，不涉及任何判据字段。"""
    so = _so(item="S02Y.0188", ship="2026-06-10")
    bom = _bom("S02Y.0188", "R01B.0365")
    rows = build_dashboard([so], bom, [], today=TODAY)
    html = render_html(rows, today=TODAY)
    assert "function feedbackHtml" in html and "function submitFeedback" in html
    assert "/api/baoguan/feedback" in html
    assert "data-id=" in html and "data-so=" in html and "data-ship=" in html
    assert "✅ 正确" in html and "❌ 误判" in html
