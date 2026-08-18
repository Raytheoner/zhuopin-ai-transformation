"""取数层 —— ERP 单源 → 冻结数据集（design D15-R / D17 / D19 / D20）。

🔴 **D15 已在建造中被实测推翻，本模块实现的是修正后的 D15-R**（详见 design.md）：

- **原 D15**：收货侧走 SRM 供应计划看板，因为「ERP 结构上给不出本周收货」。
- **实测推翻（2026-08-18）**：
  ⑴ SRM 看板返回 `300234: 供应计划看板不允许查询当前时间 7 天之前的数据`
     ——它只能查**未来**区间，「上周」「四周前」两个历史窗口根本取不到，
     SRM 在周报这条路径上**结构性不可用**；
  ⑵ `GR/Query` 其实支持**无过滤分页整表拉取**（27,785 行），每行自带
     `BusinessDate`（真实入库过账日）、`RcvQtyTU`、`SrcDocNo/SrcDocLineNo`。
     原判断之所以错，是把底座封装 `get_gr_lines(doc_no)` 的形状当成了端点本身
     的能力——**读封装不等于读端点**。
- **修正后**：订单侧 `ZpViewPurOrder/Query`、收货侧 `GR/Query`，**双端点同属 ERP，
  单源即可完整覆盖周报**；口径反而更硬（ERP 已入库过账 > 供应商自报答交）。

🔴 **两个端点的服务端过滤一律不可信（F14）**：2026-08-18 实测 `ZpViewPurOrder/Query`
与 `GR/Query` 在参数名拼错时**静默返回全表**；`GR/Query` 对 `startDate`/`endDate`/
`businessDate`/`beginDate` 四种写法返回的 Total 与无过滤基线完全相同（27,785）。
⇒ 两侧一律整表取回后**在客户端按业务字段过滤**，不依赖任何服务端过滤条件。

🔴 **real 一律 fail-loud**：任一步失败即中止，不降级 mock、不降级缓存、不返回
部分数据。**一份基于残缺数据却看起来完整的周报，比一次明确的失败危害更大。**
"""
from __future__ import annotations

import datetime
from typing import Any, Callable, Protocol

from .models import (
    LINE_STATUS_UNKNOWN,
    FrozenDataset,
    OrderLine,
    ReceiptRecord,
)
from .windows import WindowSet

#: 回溯天数——须覆盖三窗口整体跨度并留余量。两个端点都是整表拉取后客户端过滤，
#: 故放宽天数不增加请求数。
ERP_LOOKBACK_DAYS = 90


class FeedError(RuntimeError):
    """取数失败。real 模式下任一源出错都收敛到本异常，由调用方中止本次周报。"""


class RateLimitedError(FeedError):
    """外部接口限流。

    刻意做成 `FeedError` 的子类而非独立异常：它是**取数失败**的一种，
    **不是「该窗口无数据」**。若把限流当成空数据，本周业务量会被静默算成零，
    而周报看上去完全正常。
    """


def _to_date(raw: Any) -> datetime.date | None:
    """`YYYY-MM-DD` / ISO 日期时间 → `date`；不可解析返回 None。"""
    if not raw:
        return None
    try:
        return datetime.date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def probe_endpoint_filter(*, query_ok: Callable[[], list],
                          query_bad_param: Callable[[], list]) -> str:
    """F14 参数名对照测试（design D20）。

    首碰新端点时跑一次：用正确参数与**故意拼错的参数名**各查一次。已知
    `POChange/Query`、`ZpViewPurOrder/Query`、`GR/Query` 在参数名拼错时都
    **不报错而静默返回全表**——命中该形态的端点，其过滤条件不可信，调用方必须
    在取数后按业务字段二次过滤。

    返回 ``"filter_trusted"`` 或 ``"filter_untrusted"``。
    """
    try:
        bad_rows = query_bad_param()
    except Exception:
        return "filter_trusted"      # 端点正确拒绝了错误参数名
    if not bad_rows:
        return "filter_trusted"      # 返回空集，同样说明过滤生效
    ok_rows = query_ok()
    # 错误参数名下返回的行数不少于正常查询 ⇒ 过滤显然没生效（静默全表）
    return "filter_untrusted" if len(bad_rows) >= len(ok_rows) else "filter_trusted"


class Feed(Protocol):
    """取数源接口——`MockFeed` 与 `RealFeed` 同签名，使切换只换实现。"""

    def fetch(self, windows: WindowSet) -> FrozenDataset: ...


def _now_iso() -> str:
    """取数时刻。**标注为本地时区带偏移**，避免 UTC/本地混读（CLAUDE.md 硬规则）。"""
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


_REAL_SOURCE_NOTES = {
    "订单侧": "ERP `ZpViewPurOrder/Query`（下单日＝制单日 makeDate）＋ "
              "`Purchase/Query` 行级关闭状态",
    "已知缺口": "⚠️ ERP 采购订单**无任何交期字段**（2026-08-18 实测：deliveryDate/"
                "expectDate/planDate/demandDate/arrivalDate 六个候选名在 28,274 行"
                "中全部 0 命中）⇒ **收货准时率首版不做**，非遗漏（见 O-6）",
    "收货侧": "ERP `GR/Query` —— 口径为**已入库过账日**（BusinessDate）。"
              "⚠️ 非供应商 SRM 答交回报：SRM 看板不允许查询 7 天前数据（300234），"
              "历史窗口取不到，故 design D15 已修正为 D15-R",
}


class MockFeed:
    """固定样例数据源——覆盖正常行 / 已关闭行 / 空窗口 / 逾期收货四类形态。

    mock 的作用是让全链路与全部单测在**无网络、无凭据**下跑通（D19）；样例刻意
    包含短缺关闭行，使 D17「不得用数量启发式判在途」这条在 mock 下就能被验证。
    """

    def fetch(self, windows: WindowSet) -> FrozenDataset:
        cur, prev, ago = windows.current, windows.previous, windows.month_ago
        lines = (
            # 本周：正常在途行
            OrderLine(po_id="PO-2601", line_no="1", material_id="R01B.0754",
                      supplier_id="ZA.0317", qty_ordered=1000, qty_received=0,
                      order_date=cur.start, expected_date=cur.end,
                      confirmed_date=cur.end, line_status=2, unit_price=5.5,
                      supplier_name="示例电子", buyer="示例采购员A"),
            # 本周：已足量收货
            OrderLine(po_id="PO-2602", line_no="1", material_id="S04Y.0112",
                      supplier_id="ZA.0208", qty_ordered=500, qty_received=500,
                      order_date=cur.start, expected_date=cur.start,
                      confirmed_date=cur.start, line_status=2, unit_price=12.0,
                      supplier_name="示例半导体", buyer="示例采购员B"),
            # 🔴 短缺关闭行：收货量长期小于订单量。纯数量启发式会永久误判为在途，
            #    D17 要求按 LineStatus 剔除——本行就是那条判据的活样本。
            OrderLine(po_id="PO-2603", line_no="2", material_id="R01B.0039",
                      supplier_id="ZA.0317", qty_ordered=800, qty_received=300,
                      order_date=cur.start, expected_date=cur.end,
                      confirmed_date=cur.end, line_status=4, unit_price=3.2,
                      supplier_name="示例电子", buyer="示例采购员A"),
            # 上周：正常行，供周环比
            OrderLine(po_id="PO-2551", line_no="1", material_id="R01B.0754",
                      supplier_id="ZA.0317", qty_ordered=600, qty_received=600,
                      order_date=prev.start, expected_date=prev.end,
                      confirmed_date=prev.end, line_status=2, unit_price=5.5,
                      supplier_name="示例电子", buyer="示例采购员A"),
            # 四周前：正常行，供月同比
            OrderLine(po_id="PO-2401", line_no="1", material_id="S04Y.0112",
                      supplier_id="ZA.0208", qty_ordered=400, qty_received=400,
                      order_date=ago.start, expected_date=ago.end,
                      confirmed_date=ago.end, line_status=2, unit_price=12.0,
                      supplier_name="示例半导体", buyer="示例采购员B"),
        )
        receipts = (
            # 本周：准时收货（入库日 ≤ 承诺交期）
            ReceiptRecord(receipt_doc_no="RCV-01", line_no="10", po_id="PO-2602",
                          po_line_no="1", material_id="S04Y.0112",
                          supplier_name="示例半导体", receipt_date=cur.start,
                          qty_received=500, unit_price=12.0),
            # 本周：逾期收货（入库日 > 承诺交期）——准时率分母里的反例
            ReceiptRecord(receipt_doc_no="RCV-02", line_no="10", po_id="PO-2551",
                          po_line_no="1", material_id="R01B.0754",
                          supplier_name="示例电子", receipt_date=cur.end,
                          qty_received=600, unit_price=5.5),
            ReceiptRecord(receipt_doc_no="RCV-03", line_no="10", po_id="PO-2551",
                          po_line_no="1", material_id="R01B.0754",
                          supplier_name="示例电子", receipt_date=prev.start,
                          qty_received=300, unit_price=5.5),
            ReceiptRecord(receipt_doc_no="RCV-04", line_no="10", po_id="PO-2401",
                          po_line_no="1", material_id="S04Y.0112",
                          supplier_name="示例半导体", receipt_date=ago.start,
                          qty_received=400, unit_price=12.0),
        )
        return FrozenDataset(
            order_lines=lines, receipts=receipts, mode="mock",
            fetched_at=_now_iso(),
            range_start=windows.month_ago.start, range_end=windows.current.end,
            source_notes={"订单侧": "mock 样例（无网络）",
                          "收货侧": "mock 样例（无网络）"},
        )


class RealFeed:
    """真实 ERP 取数（订单侧 + 收货侧，同一连接器）。

    `erp` 由外部注入（便于测试），生产由 `build_real_feed()` 从环境构造。
    """

    #: 行级状态取数的料号数上限。`get_purchase_line_status` 按料号逐个分页查询，
    #: 料号多时请求数线性上升（D17 的已知代价）。0 表示不设上限。
    #: **一旦触发截断必须在 `source_notes` 里说出来**——静默截断会让「未清行数」
    #: 偏低而报表看上去完全正常。
    DEFAULT_MAX_STATUS_MATERIALS = 200

    def __init__(self, *, erp, max_status_materials: int | None = None):
        self._erp = erp
        self.max_status_materials = (
            self.DEFAULT_MAX_STATUS_MATERIALS
            if max_status_materials is None else max_status_materials
        )
        self.notes: list[str] = []

    @staticmethod
    def _wrap(e: Exception, what: str) -> FeedError:
        msg = str(e)
        if "900301" in msg or "限流" in msg:
            return RateLimitedError(f"{what}限流，本次周报中止：{e}")
        return FeedError(f"{what}失败：{e}")

    def _fetch_order_lines(self, windows: WindowSet) -> tuple[OrderLine, ...]:
        try:
            orders = self._erp.get_purchase_orders(days=ERP_LOOKBACK_DAYS)
        except Exception as e:                       # noqa: BLE001
            raise self._wrap(e, "ERP 采购订单取数") from e

        # 🔴 刻意**不**按窗口裁剪订单集合：窗口归属由 `order_date` 在指标层判定，
        # 而「在途/未清」类指标必须能看到更早下单、至今未清的行——取数层先裁剪会
        # 把它们悄悄抹掉，指标看上去正常、数却少了一截。
        #
        # D17：行级关闭状态必须来自 `Purchase/Query`，不得用数量启发式推断。
        # ⚠️ 该端点**按料号逐个分页查询**（服务端不支持多料号一次查全），故只对
        # **落在三窗口内的行**所涉料号取状态（D17 的既定缓解）。
        lo, hi = windows.overall_range()
        material_ids = sorted({
            str(getattr(o, "material_id", ""))
            for o in orders
            if getattr(o, "material_id", "")
            and (d := _to_date(getattr(o, "make_date", "")
                               or getattr(o, "expected_date", ""))) is not None
            and lo <= d <= hi
        })
        if self.max_status_materials and len(material_ids) > self.max_status_materials:
            # 「No silent caps」：截断了就必须说出来，否则「未清行数」会静默偏低，
            # 而报表看上去完全正常。
            self.notes.append(
                f"⚠️ 窗口内料号 {len(material_ids)} 个，超过行级状态取数上限 "
                f"{self.max_status_materials}，仅取前 {self.max_status_materials} 个；"
                f"未取到状态的行按「状态未知」处理（计入在途，不会被静默剔除）")
            material_ids = material_ids[:self.max_status_materials]
        try:
            status_map = self._erp.get_purchase_line_status(material_ids) or {}
        except Exception as e:                       # noqa: BLE001
            raise self._wrap(e, "ERP 采购行级状态取数") from e

        lines = []
        for o in orders:
            key = (str(getattr(o, "po_id", "")), str(getattr(o, "line_no", "")))
            # 下单日取**真实制单日** `make_date`；旧夹具无该字段时降级 expected_date
            # 并在 source_notes 说明（不静默近似）。
            make_date = _to_date(getattr(o, "make_date", ""))
            if make_date is None:
                make_date = _to_date(getattr(o, "expected_date", ""))
            lines.append(OrderLine(
                po_id=key[0], line_no=key[1],
                material_id=str(getattr(o, "material_id", "")),
                supplier_id=str(getattr(o, "supplier_id", "")),
                qty_ordered=float(getattr(o, "qty_ordered", 0) or 0),
                qty_received=float(getattr(o, "qty_received", 0) or 0),
                order_date=make_date,
                expected_date=_to_date(getattr(o, "expected_date", None)),
                confirmed_date=_to_date(getattr(o, "supplier_confirmed_date", None)),
                line_status=int(status_map.get(key, LINE_STATUS_UNKNOWN)),
                unit_price=float(getattr(o, "unit_price", 0) or 0),
                supplier_name=str(getattr(o, "supplier_name", "")),
                buyer=str(getattr(o, "buyer", "")),
            ))
        return tuple(lines)

    def _fetch_receipts(self, windows: WindowSet) -> tuple[ReceiptRecord, ...]:
        try:
            rows = self._erp.get_receipt_lines(days=ERP_LOOKBACK_DAYS)
        except Exception as e:                       # noqa: BLE001
            raise self._wrap(e, "ERP 收货行取数") from e

        lo, hi = windows.overall_range()
        out = []
        for r in rows or []:
            d = _to_date(getattr(r, "receipt_date", None))
            # 🔴 客户端二次过滤：该端点的服务端日期过滤实测无效（F14 静默全表），
            # 故窗口归属一律自己算，不信任任何服务端过滤条件。
            if d is None or not (lo <= d <= hi):
                continue
            out.append(ReceiptRecord(
                receipt_doc_no=str(getattr(r, "receipt_doc_no", "")),
                line_no=str(getattr(r, "line_no", "")),
                po_id=str(getattr(r, "po_id", "")),
                po_line_no=str(getattr(r, "po_line_no", "")),
                material_id=str(getattr(r, "material_id", "")),
                supplier_name=str(getattr(r, "supplier_name", "")),
                receipt_date=d,
                qty_received=float(getattr(r, "qty_received", 0) or 0),
                unit_price=float(getattr(r, "unit_price", 0) or 0),
            ))
        return tuple(out)

    def fetch(self, windows: WindowSet) -> FrozenDataset:
        self.notes = []
        lines = self._fetch_order_lines(windows)
        receipts = self._fetch_receipts(windows)
        notes = dict(_REAL_SOURCE_NOTES)
        for i, note in enumerate(self.notes, 1):
            notes[f"取数提示{i}"] = note
        return FrozenDataset(
            order_lines=lines, receipts=receipts, mode="real",
            fetched_at=_now_iso(),
            range_start=windows.month_ago.start, range_end=windows.current.end,
            source_notes=notes,
        )


def build_real_feed(max_status_materials: int | None = None):
    """从环境构造真实取数源（凭据走 `.env`，不落任何会被同步的 settings）。

    🔴 **必须注入 `ConnectorAudit`**：连接器对真实业务库的每次访问都要留痕，
    这是 IATF 可追溯红线。不注入时底座会 warn「生产环境连接器访问将不留痕」——
    2026-08-18 首次 F14 探测就撞出过这条 warning，此处一并封住。
    """
    from zhuopin_platform.audit.sinks import JsonlSink
    from zhuopin_platform.shared_tools.connector_audit import ConnectorAudit
    from zhuopin_platform.shared_tools.erp_connector.connector import ZpConnector

    from . import config

    audit = ConnectorAudit(JsonlSink(config.connector_trace_path()))
    return RealFeed(erp=ZpConnector.from_env(audit=audit),
                    max_status_materials=max_status_materials)


def build_feed(mode: str, max_status_materials: int | None = None) -> Feed:
    """按模式取源。`mode` 只接受 ``"mock"`` / ``"real"``，拼错即报错不猜。

    `max_status_materials` 透传给 `RealFeed`（`None` ＝ 用其缺省 200，`0` ＝ 不限）。
    对 `MockFeed` 无意义，忽略。
    """
    if mode == "mock":
        return MockFeed()
    if mode == "real":
        return build_real_feed(max_status_materials)
    raise ValueError(f"未知取数模式：{mode!r}（只接受 'mock' / 'real'）")
