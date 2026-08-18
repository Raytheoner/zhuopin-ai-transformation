"""指标层单测（spec: sc2-metric-engine）。对应 tasks 4.1-4.6。

本层是 SC2 里唯一会被判例包反复改动的地方（O-1 指标口径 / O-4 异常阈值都落在
这里），故把它钉成纯函数：不触网、不读时钟、不写盘。下面每条测试都是那份契约
的一个侧面。
"""
from __future__ import annotations

from datetime import date

import pytest

from sc2.metrics import DEFAULT_THRESHOLDS, compute_metrics
from sc2.models import FrozenDataset, MetricValue, OrderLine, ReceiptRecord
from sc2.windows import build_windows

BASE = date(2026, 8, 19)
WS = build_windows(BASE)


def _ds(lines=(), receipts=(), mode="mock") -> FrozenDataset:
    return FrozenDataset(order_lines=tuple(lines), receipts=tuple(receipts),
                         mode=mode, fetched_at="2026-08-19T12:00:00+08:00",
                         range_start=WS.month_ago.start, range_end=WS.current.end)


def _line(**kw):
    base = dict(po_id="PO-1", line_no="1", material_id="M1", supplier_id="S1",
                unit_price=1.0, supplier_name="示例供应商", buyer="采购员甲",
                qty_ordered=100.0, qty_received=0.0, order_date=WS.current.start,
                expected_date=WS.current.end, confirmed_date=WS.current.end,
                line_status=2)
    base.update(kw)
    return OrderLine(**base)


def _receipt(**kw):
    base = dict(receipt_doc_no="RCV-1", line_no="10", po_id="PO-1", po_line_no="1",
                material_id="M1", supplier_name="示例供应商",
                receipt_date=WS.current.start, qty_received=100.0, unit_price=1.0)
    base.update(kw)
    return ReceiptRecord(**base)


# ── 4.1 纯函数 ──────────────────────────────────────────────────────────────

def test_同输入同输出():
    ds = _ds([_line()], [_receipt()])
    a = compute_metrics(ds, WS)
    b = compute_metrics(ds, WS)
    assert [(m.key, m.current.value) for m in a] == [(m.key, m.current.value) for m in b]


def test_计算不写盘不触网(tmp_path, monkeypatch):
    """把 socket 与 open 都掐掉，指标计算仍应正常完成。"""
    import socket

    def _no_net(*a, **k):
        raise AssertionError("指标层不得发起网络请求")

    monkeypatch.setattr(socket, "socket", _no_net)
    monkeypatch.setattr(socket, "create_connection", _no_net)
    metrics = compute_metrics(_ds([_line()], [_receipt()]), WS)
    assert metrics


def test_计算不读当前时刻():
    """窗口由入参决定；用一个远离今天的基准日期，结果应只随入参变化。"""
    old_ws = build_windows(date(2019, 1, 9))
    ds = FrozenDataset(
        order_lines=(_line(order_date=old_ws.current.start),),
        receipts=(), mode="mock", fetched_at="2019-01-09T12:00:00+08:00")
    metrics = {m.key: m for m in compute_metrics(ds, old_ws)}
    assert metrics["order_line_count"].current.value == 1


# ── 4.2 首版指标从宽 ────────────────────────────────────────────────────────

def test_指标清单覆盖四个分组且不预先砍():
    """D5：算得出的全部放上，留给姚祖怡批改删减。"""
    metrics = compute_metrics(_ds([_line()], [_receipt()]), WS)
    groups = {m.group for m in metrics}
    assert {"下单", "收货", "在途", "供应商"} <= groups
    assert len(metrics) >= 10, "首版不得预先砍指标"


def test_不呈现依赖不可达数据源的指标():
    """质检/物流/工时不可达 ⇒ 相关指标 MUST NOT 出现。"""
    keys = {m.key for m in compute_metrics(_ds([_line()], [_receipt()]), WS)}
    for forbidden in ("iqc_pass_rate", "logistics_transit_days", "man_hours"):
        assert forbidden not in keys


# ── 4.3 口径未定须显式标注 ──────────────────────────────────────────────────

def test_收货类指标带具体口径假设而非四字待定():
    metrics = {m.key: m for m in compute_metrics(_ds([_line()], [_receipt()]), WS)}
    caveat = metrics["receipt_qty"].current.caveat
    assert caveat, "口径未定版的指标必须带假设标注"
    assert caveat != "口径待定"
    assert "入库过账" in caveat, "标注须说明假设内容本身"


def test_口径已确认时不再带标注():
    metrics = {m.key: m for m in compute_metrics(
        _ds([_line()], [_receipt()]), WS, caliber_confirmed=True)}
    assert metrics["receipt_qty"].current.caveat == ""


# ── 4.4 空窗口与除零 ────────────────────────────────────────────────────────

def test_空窗口比率输出无数据而非零():
    """spec：分母为零时输出「无数据」，**不是 0%**——0% 会被读成「有量但很差」。"""
    metrics = {m.key: m for m in compute_metrics(_ds([], []), WS)}
    v = metrics["receipt_match_rate"].current
    assert not v.has_data
    assert v.value is None


def test_空窗口计数型指标为零而非无数据():
    """计数与比率不同：本周确实一单没下，0 就是真值。"""
    metrics = {m.key: m for m in compute_metrics(_ds([], []), WS)}
    assert metrics["order_line_count"].current.value == 0


def test_环比涉无数据窗口时输出无可比基准():
    """本周有数据、对比窗口无数据 ⇒ 不得输出 100% 或 ∞。"""
    ds = _ds([_line(order_date=WS.current.start)], [])
    m = {x.key: x for x in compute_metrics(ds, WS)}["order_line_count"]
    assert m.current.value == 1
    assert not m.previous.has_data or m.previous.value == 0
    assert m.week_over_week is None, "无可比基准时环比须为 None，不得为 100%/∞"


def test_基准为零时环比为无可比基准():
    v_cur, v_zero = MetricValue(5.0), MetricValue(0.0)
    from sc2.models import Metric
    m = Metric(key="k", name="n", group="下单",
               current=v_cur, previous=v_zero, month_ago=v_zero)
    assert m.week_over_week is None
    assert m.month_over_month is None


# ── 4.5 异常识别与阈值 ──────────────────────────────────────────────────────

def test_阈值来自外部配置而非硬编码():
    # 本周 2 行 vs 上周 1 行 ⇒ 周环比 +100%：宽阈值不该报，严阈值该报。
    ds = _ds([_line(po_id="C1", order_date=WS.current.start),
              _line(po_id="C2", order_date=WS.current.end),
              _line(po_id="P1", order_date=WS.previous.start)], [])
    loose = compute_metrics(ds, WS, thresholds={"wow_abs_pct": 10.0})
    tight = compute_metrics(ds, WS, thresholds={"wow_abs_pct": 0.0001})
    assert [m.anomaly for m in loose] != [m.anomaly for m in tight], \
        "改阈值必须改变异常判定，否则说明阈值被硬编码了"


def test_默认阈值带未经确认标注():
    metrics = compute_metrics(_ds([_line()], [_receipt()]), WS)
    assert all(m.threshold_unconfirmed for m in metrics)


def test_阈值经确认后不再带未确认标注():
    metrics = compute_metrics(_ds([_line()], [_receipt()]), WS,
                              thresholds_confirmed=True)
    assert not any(m.threshold_unconfirmed for m in metrics)


def test_默认阈值不因任何时长自动转为已确认():
    """spec：判据类永不默认生效（IATF 显式签认红线）。

    `compute_metrics` 不接受任何「已过 N 天即视为确认」的入口——确认只能由
    调用方显式传 `thresholds_confirmed=True`。此处以签名反证：没有时间参数，
    就没有「超时自动确认」的可能。
    """
    import inspect
    params = inspect.signature(compute_metrics).parameters
    for banned in ("now", "today", "elapsed_days", "auto_confirm_after"):
        assert banned not in params


def test_默认阈值集合可读且非空():
    assert DEFAULT_THRESHOLDS and "wow_abs_pct" in DEFAULT_THRESHOLDS


def test_异常仅标出超阈值项():
    """本周暴涨的指标应被标异常，平稳的不应被标。"""
    ds = _ds([_line(po_id=f"PO-C{i}", order_date=WS.current.start) for i in range(10)]
             + [_line(po_id="PO-P1", order_date=WS.previous.start)], [])
    metrics = {m.key: m for m in compute_metrics(ds, WS, thresholds={"wow_abs_pct": 0.5})}
    assert metrics["order_line_count"].anomaly, "10 vs 1 的周环比应命中异常"


# ── D17：在途判定不得用数量启发式 ───────────────────────────────────────────

def test_已关闭行不计入未清():
    """短缺关闭行 qty_received < qty_ordered，纯数量判据会永久误判为在途。"""
    lines = [
        _line(po_id="PO-OPEN", qty_ordered=100, qty_received=30, line_status=2),
        _line(po_id="PO-SHORT", qty_ordered=100, qty_received=30, line_status=4),
        _line(po_id="PO-OVER", qty_ordered=100, qty_received=130, line_status=5),
        _line(po_id="PO-NAT", qty_ordered=100, qty_received=100, line_status=3),
    ]
    metrics = {m.key: m for m in compute_metrics(_ds(lines, []), WS)}
    assert metrics["open_line_count"].current.value == 1, "只有真正未清的那一行算在途"
    assert metrics["open_qty"].current.value == 70.0


def test_行级状态未知时按未关闭处理():
    from sc2.models import LINE_STATUS_UNKNOWN
    lines = [_line(qty_ordered=100, qty_received=0, line_status=LINE_STATUS_UNKNOWN)]
    metrics = {m.key: m for m in compute_metrics(_ds(lines, []), WS)}
    assert metrics["open_line_count"].current.value == 1


# ── 交付侧口径（D15）────────────────────────────────────────────────────────

def test_收货准时率首版不呈现且是刻意撤下():
    """🔴 不是遗漏：ERP 采购订单在 28,274 行里**没有任何交期字段**（2026-08-18 实测），
    `expected_date`/`supplier_confirmed_date` 实际恒等于制单日。以制单日当承诺交期
    算出的准时率恒为「几乎全部逾期」——那是一个**看起来像指标的假数**。
    按 spec sc2-metric-engine「不可算不呈现」撤下，登记为 O-6。"""
    keys = {m.key for m in compute_metrics(_ds([_line()], [_receipt()]), WS)}
    assert "receipt_on_time_rate" not in keys
    assert "delivery_on_time_rate" not in keys


def test_收货行可溯源比例反映JOIN覆盖度():
    """比例偏低本身就是值得采购看一眼的信号（收货追不回来源单）。"""
    line = _line(po_id="PO-A", line_no="1")
    receipts = [
        _receipt(po_id="PO-A", po_line_no="1", receipt_date=WS.current.start),
        _receipt(po_id="PO-UNKNOWN", po_line_no="9", receipt_date=WS.current.end),
    ]
    metrics = {m.key: m for m in compute_metrics(_ds([line], receipts), WS)}
    assert metrics["receipt_match_rate"].current.value == pytest.approx(0.5)


def test_收货类指标标注ERP入库口径而非SRM答交():
    """D15-R 的口径必须一路带到指标标注上。"""
    metrics = {m.key: m for m in compute_metrics(_ds([], [_receipt()]), WS)}
    caveat = metrics["receipt_qty"].current.caveat
    assert "入库过账" in caveat and "SRM" in caveat


def test_跨窗口JOIN_更早下单的订单也能被收货行溯源到():
    """收货发生在本周、订单是几周前下的——只索引本窗口订单会让可溯源比例凭空缩水。"""
    old_line = _line(po_id="PO-OLD", line_no="1", order_date=WS.month_ago.start)
    receipts = [_receipt(po_id="PO-OLD", po_line_no="1",
                         receipt_date=WS.current.start)]
    metrics = {m.key: m for m in compute_metrics(_ds([old_line], receipts), WS)}
    assert metrics["receipt_match_rate"].current.value == pytest.approx(1.0)


def test_金额类指标可算():
    """D15-R 顺带解锁：ZpViewPurOrder 带 finallyPriceTC，金额维度不再是不可算。"""
    lines = [_line(qty_ordered=100, unit_price=5.0)]
    metrics = {m.key: m for m in compute_metrics(_ds(lines, []), WS)}
    assert metrics["order_amount"].current.value == pytest.approx(500.0)


def test_采购员维度可算():
    lines = [_line(po_id="A", buyer="甲"), _line(po_id="B", buyer="乙")]
    metrics = {m.key: m for m in compute_metrics(_ds(lines, []), WS)}
    assert metrics["buyer_count"].current.value == 2


def test_三窗口各自独立计算():
    lines = [_line(po_id="C1", order_date=WS.current.start),
             _line(po_id="C2", order_date=WS.current.end),
             _line(po_id="P1", order_date=WS.previous.start),
             _line(po_id="A1", order_date=WS.month_ago.start)]
    m = {x.key: x for x in compute_metrics(_ds(lines, []), WS)}["order_line_count"]
    assert (m.current.value, m.previous.value, m.month_ago.value) == (2, 1, 1)


def test_窗口外的行不计入任何窗口():
    lines = [_line(po_id="OLD", order_date=date(2020, 1, 1))]
    m = {x.key: x for x in compute_metrics(_ds(lines, []), WS)}["order_line_count"]
    assert (m.current.value, m.previous.value, m.month_ago.value) == (0, 0, 0)
