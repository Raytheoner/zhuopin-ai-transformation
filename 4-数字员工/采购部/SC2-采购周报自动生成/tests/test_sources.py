"""取数层单测（spec: sc2-feed-source）。对应 tasks 2.1-2.7。

🔴 **本文件已随 D15-R 改写**：SRM 供应计划看板在 2026-08-18 实测中被证实
**不允许查询当前时间 7 天之前的数据**（错误码 300234），历史窗口取不到，故退出
周报取数路径；收货侧改走 ERP `GR/Query`（整表分页 + 客户端按 `BusinessDate`
过滤）。下面的测试守的是修正后的契约。

四条被测命题：
① 数据源边界——只 ERP，不得以占位值伪造质检/物流维度；
② real fail-loud——任一步挂即整体失败，**不得静默降级**；
③ 服务端过滤一律不可信，窗口归属自己算（F14）；
④ 行级状态取数的料号上限须显式留痕（No silent caps）。
"""
from __future__ import annotations

from datetime import date

import pytest

from sc2.models import LINE_STATUS_UNKNOWN, FrozenDataset
from sc2.sources import (
    FeedError,
    MockFeed,
    RateLimitedError,
    RealFeed,
    probe_endpoint_filter,
)
from sc2.windows import build_windows

BASE = date(2026, 8, 19)


# ── 测试替身 ────────────────────────────────────────────────────────────────

def _po(pid="PO-1", mat="R01B.0754", line="1", make="2026-08-19", **kw):
    from zhuopin_platform.shared_tools.models import PurchaseOrder
    base = dict(po_id=pid, material_id=mat, qty_ordered=100, qty_received=0,
                expected_date=make, supplier_confirmed_date=make,
                supplier_id="ZA.0317", status="in_transit", line_no=line,
                make_date=make, unit_price=5.5, supplier_name="示例电子",
                buyer="采购员甲")
    base.update(kw)
    return PurchaseOrder(**base)


def _rl(po="PO-1", po_line="1", d="2026-08-19", qty=100.0, **kw):
    from zhuopin_platform.shared_tools.models import ReceiptLine
    base = dict(receipt_doc_no="RCV-1", line_no="10", po_id=po, po_line_no=po_line,
                material_id="R01B.0754", material_name="料件", qty_received=qty,
                receipt_date=d, supplier_name="示例电子", unit_price=5.5)
    base.update(kw)
    return ReceiptLine(**base)


class _OkErp:
    def __init__(self, orders=None, receipts=None):
        self._orders = [_po()] if orders is None else orders
        self._receipts = [_rl()] if receipts is None else receipts
        self.asked_materials = None

    def get_purchase_orders(self, days=60):
        return self._orders

    def get_purchase_line_status(self, item_codes):
        self.asked_materials = list(item_codes)
        return {("PO-1", "1"): 2}

    def get_receipt_lines(self, days=60):
        return self._receipts


class _BoomOrders(_OkErp):
    def get_purchase_orders(self, days=60):
        raise RuntimeError("ERP 采购订单挂了")


class _BoomReceipts(_OkErp):
    def get_receipt_lines(self, days=60):
        raise RuntimeError("ERP 收货行挂了")


# ── ① mock 源与数据源边界 ───────────────────────────────────────────────────

def test_mock源返回冻结数据集且覆盖关键形态():
    ds = MockFeed().fetch(build_windows(BASE))
    assert isinstance(ds, FrozenDataset)
    assert ds.mode == "mock"
    assert ds.order_lines and ds.receipts
    assert any(l.is_closed for l in ds.order_lines)      # 短缺关闭行（D17 活样本）
    assert any(not l.is_closed for l in ds.order_lines)


def test_冻结数据集不含质检与物流维度():
    """spec：MUST NOT 以 0/空值/估算值代替不可达数据源参与计算。"""
    ds = MockFeed().fetch(build_windows(BASE))
    for line in ds.order_lines:
        assert not hasattr(line, "iqc_result")
        assert not hasattr(line, "logistics_status")


def test_取数结果带取数时刻与区间标注():
    ws = build_windows(BASE)
    ds = MockFeed().fetch(ws)
    assert ds.fetched_at
    assert ds.range_start == ws.month_ago.start
    assert ds.range_end == ws.current.end
    assert ds.source_notes


def test_real取数说明写明收货口径非SRM答交():
    """D15-R 的代价与来由必须一路带到周报标注上。"""
    ds = RealFeed(erp=_OkErp()).fetch(build_windows(BASE))
    notes = "".join(ds.source_notes.values())
    assert "入库过账" in notes
    assert "SRM" in notes and "300234" in notes


# ── ② real fail-loud ────────────────────────────────────────────────────────

def test_订单侧挂时整体失败():
    with pytest.raises(FeedError):
        RealFeed(erp=_BoomOrders()).fetch(build_windows(BASE))


def test_收货侧挂时整体失败():
    """spec 场景「单源不可达即整体失败」。

    一份基于残缺数据却看起来完整的周报，比一次明确的失败危害更大。
    """
    with pytest.raises(FeedError):
        RealFeed(erp=_BoomReceipts()).fetch(build_windows(BASE))


def test_失败时不得降级为mock或部分数据():
    try:
        RealFeed(erp=_BoomReceipts()).fetch(build_windows(BASE))
    except FeedError as e:
        assert "mock" not in str(e).lower()
    else:
        pytest.fail("应当上抛 FeedError，而不是返回部分数据")


def test_real正常路径产出real模式数据集():
    ds = RealFeed(erp=_OkErp()).fetch(build_windows(BASE))
    assert ds.mode == "real"
    assert len(ds.order_lines) == 1
    assert ds.order_lines[0].line_status == 2         # D17：行级状态已取回
    assert len(ds.receipts) == 1


def test_下单日取真实制单日而非交期():
    """`expected_date` 会降级自 makeDate，故它不等于制单日；周报须按真实制单日落窗口。"""
    ds = RealFeed(erp=_OkErp(orders=[
        _po(make="2026-08-19", expected_date="2026-09-30")])).fetch(build_windows(BASE))
    assert ds.order_lines[0].order_date == date(2026, 8, 19)
    assert ds.order_lines[0].expected_date == date(2026, 9, 30)


def test_金额字段随订单行带出():
    ds = RealFeed(erp=_OkErp()).fetch(build_windows(BASE))
    line = ds.order_lines[0]
    assert line.unit_price == 5.5
    assert line.amount == pytest.approx(100 * 5.5)
    assert line.buyer == "采购员甲"


def test_行级状态取不到时记为未知而非误当作关闭():
    class _NoStatus(_OkErp):
        def get_purchase_line_status(self, item_codes):
            return {}

    ds = RealFeed(erp=_NoStatus()).fetch(build_windows(BASE))
    line = ds.order_lines[0]
    assert line.line_status == LINE_STATUS_UNKNOWN
    assert not line.is_closed          # 未知按未关闭处理，不静默吞掉在途量


def test_限流表达为取数失败而非无数据():
    class _Limited(_OkErp):
        def get_receipt_lines(self, days=60):
            raise RuntimeError("接口限流（900301），请等待 30 秒后重试")

    with pytest.raises(RateLimitedError):
        RealFeed(erp=_Limited()).fetch(build_windows(BASE))


def test_限流错误是取数失败的一种():
    assert issubclass(RateLimitedError, FeedError)


# ── ③ 服务端过滤不可信，窗口归属自己算 ──────────────────────────────────────

def test_窗口外的收货行被客户端二次过滤剔除():
    """`GR/Query` 对 startDate/endDate/businessDate/beginDate 及故意拼错的参数名
    返回的 Total 全部等于无过滤基线（2026-08-18 实测）⇒ 服务端过滤不可信。"""
    ws = build_windows(BASE)
    ds = RealFeed(erp=_OkErp(receipts=[
        _rl(d="2026-08-19"),                    # 窗口内
        _rl(d="2020-01-01", qty=999.0),         # 窗口外——服务端没滤掉，我们要滤
    ])).fetch(ws)
    assert len(ds.receipts) == 1
    assert all(ws.month_ago.start <= r.receipt_date <= ws.current.end
               for r in ds.receipts)


def test_订单集合刻意不按窗口裁剪():
    """「在途/未清」必须能看到更早下单、至今未清的行；取数层先裁剪会静默抹掉它们。"""
    ds = RealFeed(erp=_OkErp(orders=[
        _po(pid="PO-NEW", make="2026-08-19"),
        _po(pid="PO-OLD", make="2026-06-01"),
    ])).fetch(build_windows(BASE))
    assert {l.po_id for l in ds.order_lines} == {"PO-NEW", "PO-OLD"}


def test_端点静默返回全表则判过滤不可信():
    """F14：参数名拼错时静默返回全表的端点，其过滤条件不可信。"""
    full = [{"a": 1}] * 50
    assert probe_endpoint_filter(query_ok=lambda: full,
                                 query_bad_param=lambda: full) == "filter_untrusted"


def test_端点报错或返回空集则判过滤可信():
    def _raises():
        raise RuntimeError("unknown parameter")

    assert probe_endpoint_filter(query_ok=lambda: [{"a": 1}],
                                 query_bad_param=_raises) == "filter_trusted"
    assert probe_endpoint_filter(query_ok=lambda: [{"a": 1}],
                                 query_bad_param=lambda: []) == "filter_trusted"


# ── ④ 行级状态料号上限（D17 缓解，No silent caps）────────────────────────────

def test_行级状态只对窗口内料号取数():
    """不对 90 天全量料号取状态，否则上千次请求。"""
    erp = _OkErp(orders=[_po(pid="PO-IN", mat="M-IN", make="2026-08-19"),
                         _po(pid="PO-OUT", mat="M-OUT", make="2026-01-05")])
    RealFeed(erp=erp).fetch(build_windows(BASE))
    assert erp.asked_materials == ["M-IN"]


def test_料号数超上限时截断且在取数提示里说出来():
    """静默截断会让「未清行数」偏低而报表看上去完全正常——故必须留痕。"""
    erp = _OkErp(orders=[_po(pid=f"PO-{i}", mat=f"M{i:04d}", make="2026-08-19")
                         for i in range(50)])
    ds = RealFeed(erp=erp, max_status_materials=5).fetch(build_windows(BASE))
    assert len(erp.asked_materials) == 5
    assert any("超过行级状态取数上限" in v for v in ds.source_notes.values()), \
        "截断了却没在 source_notes 里说出来"


def test_未超上限时不产生截断提示():
    ds = RealFeed(erp=_OkErp()).fetch(build_windows(BASE))
    assert not any("超过行级状态取数上限" in v for v in ds.source_notes.values())
