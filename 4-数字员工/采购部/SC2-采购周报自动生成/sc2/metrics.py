"""指标层 —— 冻结数据集 + 三窗口 → 指标集（**纯函数**）。

🔴 本模块是 SC2 里唯一会被判例包反复改动的地方：O-1（指标清单与口径）与 O-4
（异常阈值）都落在这里。故刻意做成纯函数——**不触网、不读时钟、不写盘**——
使「口径改一次」的成本等于「改一个函数 + 改一组单测」，不牵动取数与交付。

三条口径纪律（spec sc2-metric-engine）：
- **首版指标从宽**：算得出的全部放上，**不预先砍**。预先砍掉的指标姚祖怡看不见，
  也就无从否决——这与 D5「拿实物去问」是同一条逻辑。
- **比率型指标分母为零 → 「无数据」，不是 0%**。0% 会被读成「有业务量但表现
  极差」，而真相是这个窗口根本没有分母。
- **阈值外部配置，默认值须标「未经确认」，且永不因超时自动生效**（判据类，
  IATF 显式签认红线）。本模块签名里刻意没有任何时间参数，从结构上杜绝「超时
  自动确认」。
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Callable, Iterable

from .models import (
    FrozenDataset,
    Metric,
    MetricValue,
    OrderLine,
    ReceiptRecord,
)
from .windows import Window, WindowSet

#: 波动参考阈值（O-4）。`wow_abs_pct` ＝ 周环比绝对变化率超过该值即标出（4.0 ＝ 400%）。
#:
#: 🔴 **±400% 已由姚祖怡 2026-08-21 判例批改回件显式签认**（原为我方随手定的 ±50%，
#: 真实回测下 11 个完整周里 7 周越线 ⇒ 几乎每周都报，等于没报）。签认来源见
#: `THRESHOLDS_CONFIRMED_BY`，并随每期快照留存。
#:
#: ⚠️ **他同时限定了用途**：「仅作为工作量参考使用」⇒ 本阈值标出的是**工作量波动**、
#: 不是异常告警，**不得接入任何推送或告警通道**。周报对外发送仍只有「人工确认发布」
#: 这一条路径（`notify.push` 本包一行未动）。
DEFAULT_THRESHOLDS: dict[str, float] = {
    "wow_abs_pct": 4.0,
    "mom_abs_pct": 4.0,
}

#: 阈值签认来源。IATF：签认必须可追溯到人与时点，不能只把状态位翻成"已确认"。
THRESHOLDS_CONFIRMED_BY = "姚祖怡（采购部 AI 专员）· 采购部#17 判例批改回件 · 2026-08-21"

#: 波动标记的对外措辞。**刻意不叫「异常」**——见 DEFAULT_THRESHOLDS 的用途限定。
ANOMALY_LABEL = "工作量波动参考"

# ── 口径假设标注（O-1 未定版期间，spec 要求写清假设内容本身）────────────────
_CAVEAT_RECEIPT = ("收货口径＝ERP 已入库过账日（BusinessDate），"
                   "非供应商 SRM 答交回报（口径待确认）")
_CAVEAT_AMOUNT = "金额为含税单价 × 数量（未扣退货与折让，口径待确认）"
_CAVEAT_CONFIRM_QTY = ("订单量＝ERP「确认数量」（ConfirmQty）；"
                       "未取到确认数量的行不参与本项求和，条数见取数说明")


@dataclass(frozen=True)
class _Ctx:
    """单个窗口的计算上下文。

    `order_index` 是**全量**订单行索引（不限窗口）——本窗口的收货行要 JOIN 回它的
    采购订单行，而那张订单可能是几周前下的；只索引本窗口订单会让大部分收货行
    找不到来源、可溯源比例凭空缩水。
    """

    lines: tuple[OrderLine, ...]           # 本窗口内**下单**的行
    receipts: tuple[ReceiptRecord, ...]    # 本窗口内**收货**的行
    order_index: dict[tuple[str, str], OrderLine]


def _in(window: Window, day) -> bool:
    return day is not None and window.contains(day)


def _rate(numerator: float, denominator: float) -> float | None:
    """比率。**分母为零返回 None（无数据），不返回 0**。"""
    if denominator == 0:
        return None
    return numerator / denominator


def _open_lines(lines: Iterable[OrderLine]) -> list[OrderLine]:
    """未清行。**按 LineStatus 剔除已关闭（D17），不用数量启发式。**"""
    return [l for l in lines if not l.is_closed and l.qty_open > 0]


def _qty_known(lines: Iterable[OrderLine]) -> list[OrderLine]:
    """确认数量已取到的行 —— **数量类与金额类指标只对它们求和**（D24）。

    取不到确认数量的行**不被折成 0 参与求和**：0 会被读成「这行订了 0 个」，
    而真相是这个数没取到。行数类指标仍照计（那些行确实存在），未知条数写进取数说明。
    """
    return [l for l in lines if l.qty_confirmed_known]


def _top_share(lines) -> float | None:
    """首位供应商的下单量占比。无下单量时无数据。"""
    known = _qty_known(lines)
    total = sum(l.qty_ordered for l in known)
    if total == 0:
        return None
    per = Counter()
    for l in known:
        per[l.supplier_id] += l.qty_ordered
    return _rate(max(per.values()), total)


# 🔴 **收货准时率首版不做——不是遗漏，是取不到基准**（2026-08-18 实测，见 O-6）：
# `ZpViewPurOrder` 在 28,274 行里**没有任何交期字段**（deliveryDate/expectDate/
# planDate/demandDate/arrivalDate 六个候选名全部 0 命中），故底座的 `expected_date`
# 与 `supplier_confirmed_date` 实际恒等于制单日 `makeDate`。以制单日当承诺交期算
# 准时率，结果恒为「几乎全部逾期」——**那是一个看起来像指标的假数**。
# 按 spec sc2-metric-engine「不可算不呈现」撤下；承诺交期的可能来源（SRM
# `get_confirmed_dates` 按单查）留作 O-6 的后续技术验证，不在首版范围。


def _receipt_match_rate(ctx: _Ctx) -> float | None:
    """收货行能 JOIN 回采购订单行的比例——**数据可溯源性指示器**。

    它不是业务指标，而是告诉读者「本期收货里有多大比例能追回到它的采购订单」。
    比例偏低本身就是一个值得采购看一眼的信号（来源单缺失、跨期开单等）。
    """
    if not ctx.receipts:
        return None
    matched = sum(1 for r in ctx.receipts
                  if (r.po_id, r.po_line_no) in ctx.order_index)
    return _rate(matched, len(ctx.receipts))


# ── 指标清单 ────────────────────────────────────────────────────────────────
# 每项 = (key, 名称, 分组, 计算函数, 单位, 口径假设)；计算函数统一收 `_Ctx`，
# 使新增指标只加一行、不改调用侧。
_SPECS: list[tuple[str, str, str, Callable[[_Ctx], float | None], str, str]] = [
    # ── 下单 ──
    ("order_line_count", "下单行数", "下单",
     lambda c: float(len(c.lines)), "行", ""),
    ("order_qty", "下单数量", "下单",
     lambda c: float(sum(l.qty_ordered for l in _qty_known(c.lines))), "", _CAVEAT_CONFIRM_QTY),
    ("order_amount", "下单金额", "下单",
     lambda c: float(sum(l.amount for l in _qty_known(c.lines))), "元",
     _CAVEAT_AMOUNT + "；" + _CAVEAT_CONFIRM_QTY),
    ("order_po_count", "下单单据数", "下单",
     lambda c: float(len({l.po_id for l in c.lines})), "单", ""),
    ("order_material_count", "下单涉及料号数", "下单",
     lambda c: float(len({l.material_id for l in c.lines if l.material_id})), "个", ""),
    ("avg_qty_per_line", "行均下单量", "下单",
     lambda c: _rate(sum(l.qty_ordered for l in _qty_known(c.lines)),
                     len(_qty_known(c.lines))), "", _CAVEAT_CONFIRM_QTY),
    ("buyer_count", "参与采购员数", "下单",
     lambda c: float(len({l.buyer for l in c.lines if l.buyer})), "人", ""),
    # ── 收货 ──
    ("receipt_line_count", "收货行数", "收货",
     lambda c: float(len(c.receipts)), "行", _CAVEAT_RECEIPT),
    ("receipt_qty", "收货数量", "收货",
     lambda c: float(sum(r.qty_received for r in c.receipts)), "", _CAVEAT_RECEIPT),
    ("receipt_amount", "收货金额", "收货",
     lambda c: float(sum(r.amount for r in c.receipts)), "元", _CAVEAT_AMOUNT),
    ("receipt_doc_count", "收货单据数", "收货",
     lambda c: float(len({r.receipt_doc_no for r in c.receipts})), "单", _CAVEAT_RECEIPT),
    ("receipt_material_count", "收货涉及料号数", "收货",
     lambda c: float(len({r.material_id for r in c.receipts if r.material_id})),
     "个", _CAVEAT_RECEIPT),
    ("receipt_match_rate", "收货行可溯源比例", "收货",
     _receipt_match_rate, "%",
     "＝能 JOIN 回采购订单行的收货行占比；偏低说明有收货追不回来源单"),
    # ── 在途 ──
    ("open_line_count", "未清行数", "在途",
     lambda c: float(len(_open_lines(c.lines))), "行", ""),
    ("open_qty", "未清数量", "在途",
     lambda c: float(sum(l.qty_open for l in _open_lines(_qty_known(c.lines)))),
     "", _CAVEAT_CONFIRM_QTY),
    ("open_amount", "未清金额", "在途",
     lambda c: float(sum(l.qty_open * l.unit_price
                         for l in _open_lines(_qty_known(c.lines)))),
     "元", _CAVEAT_AMOUNT + "；" + _CAVEAT_CONFIRM_QTY),
    ("closed_line_count", "已关闭行数", "在途",
     lambda c: float(sum(1 for l in c.lines if l.is_closed)), "行", ""),
    ("open_ratio", "未清行占比", "在途",
     lambda c: _rate(len(_open_lines(c.lines)), len(c.lines)), "%", ""),
    # ── 供应商 ──
    ("supplier_count", "活跃供应商数", "供应商",
     lambda c: float(len({l.supplier_id for l in c.lines if l.supplier_id})), "家", ""),
    ("top_supplier_share", "首位供应商集中度", "供应商",
     lambda c: _top_share(c.lines), "%", ""),
    ("receipt_supplier_count", "本期到货供应商数", "供应商",
     lambda c: float(len({r.supplier_name for r in c.receipts if r.supplier_name})),
     "家", _CAVEAT_RECEIPT),
]


def compute_metrics(
    dataset: FrozenDataset,
    windows: WindowSet,
    *,
    thresholds: dict[str, float] | None = None,
    thresholds_confirmed: bool = False,
    caliber_confirmed: bool = False,
) -> tuple[Metric, ...]:
    """计算三窗口指标集。

    :param thresholds: 异常阈值。缺省用 `DEFAULT_THRESHOLDS`（**未经专员确认**）。
    :param thresholds_confirmed: 阈值是否已由专员显式签认。**只能由调用方显式传入**
        ——本函数签名里没有任何时间参数，故不存在「超时自动确认」这条路径（O-4 属
        判据类，IATF 要求显式签认，永不默认生效）。
    :param caliber_confirmed: 指标口径（O-1）是否已定版。未定版时各指标带口径假设
        标注；定版后标注清空。
    """
    th = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        th.update(thresholds)

    # 全量订单行索引，供收货行跨窗口 JOIN 回来源订单（见 `_Ctx.order_index` 说明）。
    order_index = {(l.po_id, l.line_no): l for l in dataset.order_lines}

    def _ctx(w: Window) -> _Ctx:
        return _Ctx(
            lines=tuple(l for l in dataset.order_lines if _in(w, l.order_date)),
            receipts=tuple(r for r in dataset.receipts if _in(w, r.receipt_date)),
            order_index=order_index,
        )

    buckets = {"current": _ctx(windows.current),
               "previous": _ctx(windows.previous),
               "month_ago": _ctx(windows.month_ago)}

    out: list[Metric] = []
    for key, name, group, fn, unit, caveat in _SPECS:
        values = {
            slot: MetricValue(value=fn(ctx), unit=unit,
                              caveat="" if caliber_confirmed else caveat)
            for slot, ctx in buckets.items()
        }
        metric = Metric(key=key, name=name, group=group,
                        current=values["current"],
                        previous=values["previous"],
                        month_ago=values["month_ago"],
                        threshold_unconfirmed=not thresholds_confirmed)
        out.append(_flag_anomaly(metric, th))
    return tuple(out)


def _flag_anomaly(metric: Metric, thresholds: dict[str, float]) -> Metric:
    """按阈值标出异常波动。无可比基准时不标——**没有基准不等于异常**。"""
    wow, mom = metric.week_over_week, metric.month_over_month
    hit = (
        (wow is not None and abs(wow) > thresholds["wow_abs_pct"])
        or (mom is not None and abs(mom) > thresholds["mom_abs_pct"])
    )
    if not hit:
        return metric
    return Metric(key=metric.key, name=metric.name, group=metric.group,
                  current=metric.current, previous=metric.previous,
                  month_ago=metric.month_ago, anomaly=True,
                  threshold_unconfirmed=metric.threshold_unconfirmed)


def metric_groups(metrics: Iterable[Metric]) -> dict[str, list[Metric]]:
    """按分组归拢，供周报呈现。"""
    grouped: dict[str, list[Metric]] = {}
    for m in metrics:
        grouped.setdefault(m.group, []).append(m)
    return grouped
