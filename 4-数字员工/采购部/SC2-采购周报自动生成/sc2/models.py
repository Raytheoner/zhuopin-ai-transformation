"""SC2 数据模型 —— 冻结数据集与指标结果。

「冻结数据集」是取数层与指标层之间的唯一界面：取数层把 ERP/SRM 两侧拉回来的东西
规整成本模块的 dataclass，之后指标层只认它、不再碰连接器。这样口径变更（O-1/O-4，
必然会发生）只落在指标层，取数层与交付层不受牵动（design D18）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

# ── 行级关闭状态（design D17）────────────────────────────────────────────────
# 取自 U9C `PM_POLine.Status`，经底座 `get_purchase_line_status` 暴露：
#   0=开立 / 1=审核中 / 2=已审核未交清 / 3=自然关闭 / 4=短缺关闭 / 5=超额关闭
# 🔴 3/4/5 三类为**已关闭**，计算「在途/未清」时必须剔除。不能用
# `qty_received` vs `qty_ordered` 的数量启发式代替——短缺关闭行的收货量常年小于
# 订单量、超额关闭行常年大于，纯数量判据会把它们永久误判为在途（SC8 队列 #173）。
CLOSED_LINE_STATUSES = frozenset({3, 4, 5})

#: 行级状态未知（未取到 LineStatus）时的占位值。
LINE_STATUS_UNKNOWN = -1


@dataclass(frozen=True)
class OrderLine:
    """一条采购订单行（ERP `ZpViewPurOrder` + `Purchase/Query` 行级状态）。"""

    po_id: str
    line_no: str
    material_id: str
    supplier_id: str
    qty_ordered: float
    qty_received: float
    order_date: date | None          # 制单日期 makeDate —— 「本周下单」按它落窗口
    expected_date: date | None       # 交期（deliveryDate 降级 makeDate）
    confirmed_date: date | None      # 承诺交期，收货准时率的基准
    line_status: int = LINE_STATUS_UNKNOWN
    unit_price: float = 0.0          # 含税单价 finallyPriceTC —— 金额类指标用
    supplier_name: str = ""
    buyer: str = ""                  # 制单人（采购员）makeEmpName

    @property
    def amount(self) -> float:
        """下单金额（含税）。"""
        return self.qty_ordered * self.unit_price

    @property
    def is_closed(self) -> bool:
        """该行是否已关闭（自然/短缺/超额）。状态未知时按未关闭处理。"""
        return self.line_status in CLOSED_LINE_STATUSES

    @property
    def qty_open(self) -> float:
        """未清数量。已关闭行一律记 0——关闭即不再期待到货。"""
        if self.is_closed:
            return 0.0
        return max(0.0, self.qty_ordered - self.qty_received)


@dataclass(frozen=True)
class ReceiptRecord:
    """一条 ERP 收货行（`GR/Query`）。

    🔴 **口径 ＝ ERP 已入库过账**（`BusinessDate`），不是供应商在 SRM 上的答交回报。
    design D15 原定走 SRM，2026-08-18 建造时实测推翻：SRM 供应计划看板**不允许
    查询当前时间 7 天之前的数据**（错误码 300234），历史窗口根本取不到；而
    `GR/Query` 整表分页可取、每行自带真实入库日期。详见 design D15-R。
    """

    receipt_doc_no: str
    line_no: str
    po_id: str                       # 来源采购单号 —— 与 OrderLine 按行 JOIN 算准时率
    po_line_no: str
    material_id: str
    supplier_name: str
    receipt_date: date | None        # 入库过账日 BusinessDate —— 落窗口用
    qty_received: float
    unit_price: float = 0.0

    @property
    def amount(self) -> float:
        """收货金额（含税）。"""
        return self.qty_received * self.unit_price


@dataclass(frozen=True)
class FrozenDataset:
    """一次取数的完整结果——此后指标层只读它，不再触网。"""

    order_lines: tuple[OrderLine, ...]
    receipts: tuple[ReceiptRecord, ...]
    mode: str                         # "mock" | "real"
    fetched_at: str                   # ISO8601，含时区；供周报「取数时刻」标注
    range_start: date | None = None
    range_end: date | None = None
    #: 各源的取数说明，进周报「可追溯标注」与 audit 的 data_sources
    source_notes: dict[str, str] = field(default_factory=dict)
    #: F14 参数名对照测试的结论：{端点: "filter_trusted" | "filter_untrusted"}
    endpoint_filter_trust: dict[str, str] = field(default_factory=dict)


# ── 指标 ─────────────────────────────────────────────────────────────────────

#: 指标值为「无数据」时的表示（spec sc2-metric-engine：分母为零不得输出 0%）。
NO_DATA = "no_data"


@dataclass(frozen=True)
class MetricValue:
    """单个窗口内某指标的取值。

    `value` 为 None 表示「无数据」——**刻意不用 0 代替**：0% 会被读者读成
    「有业务量但表现极差」，而真相是这个窗口根本没有可算的分母。
    """

    value: float | None
    unit: str = ""
    #: 口径假设。未定版口径必须写清假设内容本身，而不只是「口径待定」四字。
    caveat: str = ""

    @property
    def has_data(self) -> bool:
        return self.value is not None


@dataclass(frozen=True)
class Metric:
    """一个指标在三个窗口上的取值与对比。"""

    key: str
    name: str
    group: str                        # 分组：下单 / 交付 / 在途 / 供应商
    current: MetricValue
    previous: MetricValue
    month_ago: MetricValue
    #: 是否被异常识别标出
    anomaly: bool = False
    #: 异常判定所用阈值是否未经专员确认（spec：默认阈值须带此标注）
    threshold_unconfirmed: bool = False

    def _delta(self, base: MetricValue) -> float | None:
        """相对某基准窗口的变化率。任一侧无数据即无可比基准。"""
        if not self.current.has_data or not base.has_data or base.value == 0:
            return None
        return (self.current.value - base.value) / abs(base.value)

    @property
    def week_over_week(self) -> float | None:
        return self._delta(self.previous)

    @property
    def month_over_month(self) -> float | None:
        return self._delta(self.month_ago)


@dataclass(frozen=True)
class WeeklyReport:
    """一期周报。"""

    period: str                       # ISO 周标签，如 2026-W34
    base_date: date
    metrics: tuple[Metric, ...]
    #: 三窗口起止的人可读文本，供「可追溯标注」
    window_text: dict[str, str] = field(default_factory=dict)
    mode: str = "mock"
    fetched_at: str = ""
    source_notes: dict[str, str] = field(default_factory=dict)
    thresholds: dict[str, Any] = field(default_factory=dict)
    thresholds_confirmed: bool = False

    @property
    def anomalies(self) -> tuple[Metric, ...]:
        return tuple(m for m in self.metrics if m.anomaly)
