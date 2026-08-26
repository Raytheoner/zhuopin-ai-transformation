"""数据接入层（design D1/D6/D10/D11，spec: fi2-feed-source）—— 三单四表统一接口：mock / csv 应急桥接 / u9c 直读。

v3 口径修正（2026-07-09）：核对对象改 AP 单 vs INV，PO/GR 保留加载（PO 作 AP-PO 单价前置
参照，GR 本次匹配数学暂不消费，供未来 FI2-1 完整性校验用）。发票挂载 `ap_no`（U9C 应付单
附件语义），按 `ap_no` 关联 AP↔Invoice；`(po_no, line_no)` 仍用于 AP↔PO 单价前置参照关联。
切源不改匹配引擎/分类逻辑：
  · mock：贴口径备稿字段的夹具（单测/回归）。
  · csv ：应急桥接（同字段约定，接口先搭，真实路径待 9 月数据闸接通）。
  · u9c ：U9C 财务接口直读（design D15，队列 #60，2026-07-20 起 PO/GR/AP 三单可用）——
    注入 `u9c_connector`+`ap_doc_nos` 时按 AP 单号驱动真实查询（AP→去重 SrcPONo/SrcRcvNo
    →PO/GR）；未注入连接器时维持 fail-loud（不静默回退 mock/csv）。发票（Invoice）默认仍
    fail-loud（Attachment/OCR 未就绪，队列 #59），但 design D19（队列 #214/§四#43，
    2026-08-03）新增例外：显式提供 `invoice_sample_dir`（人工誊录小样目录）时改读该目录，
    未提供则行为不变。付款（Payment）u9c 源下始终 fail-loud，不受本次改动影响。
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional as _Opt

from pydantic import BaseModel, field_validator

from zhuopin_platform.shared_tools.connector_errors import RealEndpointNotReadyError

from . import config as _config
from .models import APLine, GRNLine, InvoiceLine, POLine, PaymentRecord


def _read_csv(path: Path | str) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# ── Pydantic 边界校验（脏数据挡在接入层）─────────────────────────────────────

class _POLineRow(BaseModel):
    po_no: str
    line_no: str
    item_code: str
    qty: float
    unit_price: float
    tax_rate: float
    amount: float
    supplier: _Opt[str] = ""
    po_date: _Opt[str] = ""

    @field_validator("po_no", "line_no", "item_code", mode="before")
    @classmethod
    def _require(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("必填字段不能为空")
        return str(v).strip()

    @field_validator("qty", "unit_price", "tax_rate", "amount", mode="before")
    @classmethod
    def _coerce(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("数值字段不能为空")
        return float(v)


class _GRNRow(BaseModel):
    grn_no: str
    po_no: str
    line_no: str
    item_code: str
    recv_qty: float
    recv_date: _Opt[str] = ""

    @field_validator("grn_no", "po_no", "line_no", "item_code", mode="before")
    @classmethod
    def _require(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("必填字段不能为空")
        return str(v).strip()

    @field_validator("recv_qty", mode="before")
    @classmethod
    def _coerce(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("recv_qty 不能为空")
        return float(v)


class _APLineRow(BaseModel):
    """应付单明细行边界校验（v3 新增）。"""
    ap_no: str
    po_no: str
    line_no: str
    item_code: str
    qty: float
    unit_price: float
    untaxed_amount: float
    tax_amount: float
    ap_date: _Opt[str] = ""

    @field_validator("ap_no", "po_no", "line_no", "item_code", mode="before")
    @classmethod
    def _require(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("必填字段不能为空")
        return str(v).strip()

    @field_validator("qty", "unit_price", "untaxed_amount", "tax_amount", mode="before")
    @classmethod
    def _coerce(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("数值字段不能为空")
        return float(v)


class _InvoiceRow(BaseModel):
    """发票明细行边界校验（v3 修正4 字段：挂载 ap_no，字段贴 INV 票面）。"""
    inv_no: str
    ap_no: str
    item_code: str
    unit: _Opt[str] = ""
    unit_price: float
    inv_qty: float
    untaxed_amount: float
    tax_rate: float
    tax_amount: float
    inv_date: _Opt[str] = ""

    @field_validator("inv_no", "ap_no", "item_code", mode="before")
    @classmethod
    def _require(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("必填字段不能为空")
        return str(v).strip()

    @field_validator("unit_price", "inv_qty", "untaxed_amount", "tax_rate", "tax_amount", mode="before")
    @classmethod
    def _coerce(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("数值字段不能为空")
        return float(v)


class _PaymentRow(BaseModel):
    pay_no: str
    inv_no: str
    pay_amount: float
    pay_date: _Opt[str] = ""

    @field_validator("pay_no", "inv_no", mode="before")
    @classmethod
    def _require(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("必填字段不能为空")
        return str(v).strip()

    @field_validator("pay_amount", mode="before")
    @classmethod
    def _coerce(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("pay_amount 不能为空")
        return float(v)


def parse_po_lines(rows: list[dict]) -> list[POLine]:
    out: list[POLine] = []
    for raw in rows:
        try:
            r = _POLineRow.model_validate(raw)
        except Exception as e:
            raise ValueError(f"FI2 PO明细行校验失败: {e}") from None
        out.append(POLine(r.po_no, r.line_no, r.item_code, r.qty, r.unit_price,
                           r.tax_rate, r.amount, r.supplier or "", r.po_date or ""))
    return out


def parse_grn(rows: list[dict]) -> list[GRNLine]:
    out: list[GRNLine] = []
    for raw in rows:
        try:
            r = _GRNRow.model_validate(raw)
        except Exception as e:
            raise ValueError(f"FI2 入库单校验失败: {e}") from None
        out.append(GRNLine(r.grn_no, r.po_no, r.line_no, r.item_code, r.recv_qty, r.recv_date or ""))
    return out


@dataclass
class APNoPOLinkRow:
    """一条「无 PO 关联」的应付明细行（队列 #390）——**留痕，不是丢弃**。

    `po_no`／`line_no` 双空（或其一为空）的应付行在账上真实存在：费用类应付、无采购
    订单的应付都是这个形态。它们进不了三单核对的数学（`(po_no, line_no)` 是 AP↔PO
    的 join 键），但**绝不能静默跳过——静默丢弃就是无声漏单**。
    """
    index: int                  # 在传入 rows 里的 0-based 位置（与 raw_ap_rows 对齐用）
    ap_no: str
    item_code: str
    reason: str                 # 恒为 "no_po_link"（预留将来细分）
    raw: dict                   # 原始行，原样留存供人工核对


def _no_po_link_fields(raw: dict) -> list[str]:
    """→ `po_no`/`line_no` 中为空的那些字段名（都不空则返回空列表）。"""
    return [f for f in ("po_no", "line_no")
            if raw.get(f) is None or str(raw.get(f)).strip() == ""]


def parse_ap_lines(rows: list[dict], *, no_po_link: str = "raise",
                   diverted: list[APNoPOLinkRow] | None = None) -> list[APLine]:
    """解析应付单明细行（v3 新增，design D10）。

    `no_po_link`（队列 #390）——「无 PO 关联」行（`po_no`／`line_no` 有一个为空）怎么办：

      · `"raise"`（默认，行为与本参数引入前逐字相同）：照旧 fail-loud 抛 `ValueError`。
        🔴 **fail-loud 本身是对的，不要改成静默跳过**——见 `APNoPOLinkRow` 文档。
      · `"divert"`：把这类行**分流**进 `diverted`（调用方必须提供该列表，否则抛错——
        没地方留痕就等于静默丢弃，本函数不允许），其余行照常解析，批量加载得以跑完。

    🔴 **`"divert"` 只解决「批量跑得完 ＋ 这类行留可查诊断」，不代表「费用类应付不进
    三单核对」这条账务口径已定** —— 该口径归唐燕萍（队列 #390 三条选项 ⒜⒝⒞ 原样待
    她拍板），故默认值刻意保持 `"raise"`，不默认生效。

    其余任何校验失败（`ap_no`／`item_code` 为空、数值字段非法等）在两种模式下**一律
    照旧 fail-loud**——那是真正的脏数据，不在本次分流范围内。
    """
    if no_po_link not in ("raise", "divert"):
        raise ValueError(f"未知 no_po_link 模式: {no_po_link}（可选 'raise' / 'divert'）")
    if no_po_link == "divert" and diverted is None:
        raise ValueError(
            "parse_ap_lines(no_po_link='divert') 必须提供 diverted 列表承接分流行——"
            "无处留痕的分流等同静默漏单（队列 #390）"
        )

    out: list[APLine] = []
    for idx, raw in enumerate(rows):
        if no_po_link == "divert":
            missing = _no_po_link_fields(raw)
            if missing:
                diverted.append(APNoPOLinkRow(
                    index=idx,
                    ap_no=str(raw.get("ap_no") or ""),
                    item_code=str(raw.get("item_code") or ""),
                    reason="no_po_link",
                    raw=dict(raw),
                ))
                continue
        try:
            r = _APLineRow.model_validate(raw)
        except Exception as e:
            # 队列 #390：原消息只有 pydantic 原文，不含单号/行位置——`AP-2026010125`
            # 那次 640 单批量当场中止，日志里查不出是哪一张单打挂的。补上定位信息。
            where = f"第 {idx + 1} 行（ap_no={raw.get('ap_no') or '?'}）"
            hint = ""
            if _no_po_link_fields(raw):
                hint = ("；该行 po_no／line_no 为空＝「无 PO 关联」应付行（费用类应付在账上"
                        "真实存在），批量加载可用 no_po_link='divert' 分流留痕，见队列 #390")
            raise ValueError(f"FI2 应付单明细行校验失败: {where}: {e}{hint}") from None
        out.append(APLine(r.ap_no, r.po_no, r.line_no, r.item_code, r.qty, r.unit_price,
                           r.untaxed_amount, r.tax_amount, r.ap_date or ""))
    return out


def parse_invoice(rows: list[dict]) -> list[InvoiceLine]:
    out: list[InvoiceLine] = []
    for raw in rows:
        try:
            r = _InvoiceRow.model_validate(raw)
        except Exception as e:
            raise ValueError(f"FI2 发票行校验失败: {e}") from None
        out.append(InvoiceLine(r.inv_no, r.ap_no, r.item_code, r.unit or "", r.unit_price,
                                r.inv_qty, r.untaxed_amount, r.tax_rate, r.tax_amount, r.inv_date or ""))
    return out


def parse_payment(rows: list[dict]) -> list[PaymentRecord]:
    out: list[PaymentRecord] = []
    for raw in rows:
        try:
            r = _PaymentRow.model_validate(raw)
        except Exception as e:
            raise ValueError(f"FI2 付款凭证校验失败: {e}") from None
        out.append(PaymentRecord(r.pay_no, r.inv_no, r.pay_amount, r.pay_date or ""))
    return out


def partition_invoices(
    ap_lines: list[APLine], invoice_rows: list[InvoiceLine]
) -> tuple[list[InvoiceLine], list[InvoiceLine]]:
    """按 `ap_no` 是否存在对应 AP 单，切分发票为 (可匹配, 孤立) 两组（v3：锚点从 PO 行改 AP 单号）。

    孤立发票（挂载的 ap_no 在 AP 明细行里完全找不到，数据完整性异常——正常流程下发票是
    配票生成的 AP 单附件，理论不应出现）不得进入料品汇总归集当作正常匹配对象——由调用方
    另行标记待处理。
    """
    ap_nos = {a.ap_no for a in ap_lines}
    linked: list[InvoiceLine] = []
    orphaned: list[InvoiceLine] = []
    for inv in invoice_rows:
        (linked if inv.ap_no in ap_nos else orphaned).append(inv)
    return linked, orphaned


def _u9c_str(v) -> str:
    """真实 API 字段可能是 int（如 DocLineNo=10）或 str（如 SrcPOLineNo="240"），统一转 str。"""
    return "" if v is None else str(v)


def _u9c_date(v) -> str:
    """真实 API 日期形如 "2025-12-26T00:00:00"，取日期部分；空值原样返回空串。"""
    return (v or "")[:10]


def _map_u9c_po_row(row: dict) -> dict:
    """`Purchase/Query` 原始行 → `_POLineRow` 字段（design D15-b）。

    `FinalPriceTC` 已实测确认为含税单价（`ConfirmQty×FinalPriceTC=TotalMnyTC`），
    与 AP `TaxPrice` 同基准，R7 单价比对可直接用（design D15-a②）。
    """
    return {
        "po_no": row.get("DocNo"), "line_no": _u9c_str(row.get("DocLineNo")),
        "item_code": row.get("ItemCode"), "qty": row.get("ConfirmQty"),
        "unit_price": row.get("FinalPriceTC"), "tax_rate": row.get("TaxRate"),
        "amount": row.get("NetMnyTC"), "supplier": row.get("SupplierName") or "",
        "po_date": _u9c_date(row.get("BusinessDate")),
    }


def _map_u9c_gr_row(row: dict) -> dict:
    """`GR/Query` 原始行 → `_GRNRow` 字段（design D15-b）。`SrcDocNo`/`SrcDocLineNo`
    = 来源 PO 单号/行号（GR 本次匹配数学暂不消费，见 design D10）。"""
    return {
        "grn_no": row.get("RcvDocNo"), "po_no": row.get("SrcDocNo"),
        "line_no": _u9c_str(row.get("SrcDocLineNo")), "item_code": row.get("ItemCode"),
        "recv_qty": row.get("RcvQtyTU"), "recv_date": _u9c_date(row.get("BusinessDate")),
    }


def _map_u9c_ap_row(row: dict) -> dict:
    """`AP/Query` 原始行 → `_APLineRow` 字段（design D15-b）。`TaxPrice` 已实测确认
    为含税单价（`APQtyTU×TaxPrice=TotalAmtTC`），与 PO `FinalPriceTC` 同基准。"""
    return {
        "ap_no": row.get("DocNo"), "po_no": row.get("SrcPONo"),
        "line_no": _u9c_str(row.get("SrcPOLineNo")), "item_code": row.get("ItemCode"),
        "qty": row.get("APQtyTU"), "unit_price": row.get("TaxPrice"),
        "untaxed_amount": row.get("NonTaxAmtTC"), "tax_amount": row.get("TaxAmtTC"),
        "ap_date": "",  # AP/Query 未提供独立单据日期字段，非匹配引擎消费字段
    }


class FeedSource:
    """三单四表统一加载器（v3：PO/GR/AP/Invoice/Payment）。

    Args:
        data_source: "mock" | "csv" | "u9c"（None → config.DATA_SOURCE_DEFAULT）。
        mock_dir:    mock 夹具目录（含 po_lines.csv/grn.csv/ap_lines.csv/invoice.csv/payment.csv）。
        csv_dir:     应急桥接目录（同字段约定，真实路径待接通）。
        audit:       ConnectorAudit（连接器访问留痕，占位）。
        u9c_connector: `u9c` 源下驱动真实查询的连接器（如 `ZpConnector`，需暴露
            `get_purchase_lines`/`get_gr_lines`/`get_ap_lines(doc_no)` 三方法，design D15；
            批量模式另需 `get_ap_lines_by_supplier(supplier_code)`，design D16）。
            `None`（默认）→ `u9c` 源五个 loader 保持 fail-loud（现状行为不变）。
        ap_supplier_codes: `u9c` 源下按供应商批量取数（design D16，队列 #61 追加）——
            自动分页拉取这些供应商名下**全部** AP 明细行，取代逐单号手工清单。
            与 `ap_doc_nos` 二选一（同时注入时优先批量模式，见 `_fetch_u9c_ap_rows`）。
            `AP/Query` 的 `supplierCode` 过滤此前有服务器端 SQL bug（design D15-a①），
            2026-07-21 已由 IT 修复（队列 #61），本参数才具备可用性。
        ap_doc_nos:  `u9c` 源下待对账的 AP 单号清单（显式给单号的原始 MVP 形态，
            design D15-a①）——`ap_supplier_codes` 未注入时的手工兜底路径，仍受支持
            （如财务专员只想追一批具体单号，不想拉某供应商全量）。
        invoice_sample_dir: `u9c` 源下人工誊录发票小样目录（design D19，队列 #214/
            §四#43）——提供时 `load_invoice()` 改读该目录 `invoice.csv`（同既有
            `parse_invoice`/`_InvoiceRow` 边界校验），不再 fail-loud；`None`（默认）→
            `load_invoice()` 维持现状 fail-loud（Attachment/OCR 未就绪，队列 #59），
            行为与本参数引入前完全一致。仅影响 `load_invoice()`，不影响
            `load_po_lines`/`load_grn`/`load_ap_lines`/`load_payment`。
        ap_no_po_link: 「无 PO 关联」应付行的处理模式（队列 #390），透传给
            `parse_ap_lines`：`"raise"`（默认，现状 fail-loud 不变）或 `"divert"`
            （分流留痕，批量加载得以跑完）。`"divert"` 下分流行落
            `self.ap_no_po_link_rows`，调用方须如实呈现——**不得静默**。
            🔴 默认刻意不改：「费用类应付要不要进三单核对」是唐燕萍的账务口径
            （队列 #390 ⒜⒝⒞ 待她拍板），本参数只解决「批量跑得完」，不替她选。
    """

    def __init__(self, data_source: str | None = None, *, mock_dir: Path | str | None = None,
                 csv_dir: Path | str | None = None, audit=None, cfg=_config,
                 u9c_connector=None, ap_doc_nos: list[str] | None = None,
                 ap_supplier_codes: list[str] | None = None,
                 invoice_sample_dir: Path | str | None = None,
                 ap_no_po_link: str = "raise"):
        self.data_source = (data_source or cfg.DATA_SOURCE_DEFAULT).strip().lower()
        self.mock_dir = Path(mock_dir) if mock_dir else None
        self.csv_dir = Path(csv_dir) if csv_dir else None
        self.audit = audit
        self.cfg = cfg
        self.u9c_connector = u9c_connector
        self.ap_doc_nos = list(ap_doc_nos) if ap_doc_nos else None
        self.ap_supplier_codes = list(ap_supplier_codes) if ap_supplier_codes else None
        self.invoice_sample_dir = Path(invoice_sample_dir) if invoice_sample_dir else None
        self.ap_no_po_link = ap_no_po_link
        # 队列 #390：`ap_no_po_link="divert"` 时被分流出来的「无 PO 关联」应付行。
        # 由最近一次 `load_ap_lines()` 重填（不累积），调用方据此留痕/呈现。
        self.ap_no_po_link_rows: list[APNoPOLinkRow] = []
        self._u9c_ap_rows_cache: list[dict] | None = None
        # 被分流行在 `_u9c_ap_rows_cache` 里的下标——`raw_ap_rows()` 据此同步剔除，
        # 保住它与 `load_ap_lines()` 结果「按位置一一对应」的既有契约（见该方法）。
        self._u9c_ap_diverted_idx: set[int] = set()

    def _dir(self) -> Path:
        if self.data_source == "mock":
            return self.mock_dir
        if self.data_source == "csv":
            return self.csv_dir
        raise ValueError(f"未知 data_source: {self.data_source}")

    def _fetch_u9c_ap_rows(self) -> list[dict]:
        """拉取待对账的 AP 明细行（design D16，队列 #61 追加），同次 FeedSource 实例
        内缓存复用（`load_ap_lines`/`load_po_lines`/`load_grn` 三方共享，避免重复
        网络调用）。两种驱动模式二选一，`ap_supplier_codes` 优先：
          · 批量模式（`ap_supplier_codes`）：按供应商自动分页拉取全部 AP 明细行，
            取代原"手工给单号清单"的 MVP 限制（该限制源于 `AP/Query` 服务器端过滤
            参数 bug，design D15-a①，2026-07-21 已由 IT 修复，见队列 #61）。
          · 手工模式（`ap_doc_nos`）：逐单号精确拉取，D15-a① 原始 MVP 形态，仍受
            支持（财务专员只想追一批具体单号时更直接）。
        """
        if self._u9c_ap_rows_cache is None:
            if self.ap_supplier_codes:
                rows: list[dict] = []
                for code in self.ap_supplier_codes:
                    rows.extend(self.u9c_connector.get_ap_lines_by_supplier(code))
                self._u9c_ap_rows_cache = rows
            elif self.ap_doc_nos:
                rows = []
                for ap_no in self.ap_doc_nos:
                    rows.extend(self.u9c_connector.get_ap_lines(ap_no))
                self._u9c_ap_rows_cache = rows
            else:
                raise ValueError(
                    "u9c 源 + 已注入 u9c_connector 时，FeedSource 需同时注入 "
                    "ap_supplier_codes（批量，按供应商）或 ap_doc_nos（手工，按单号）之一"
                )
        return self._u9c_ap_rows_cache

    def raw_ap_rows(self) -> list[dict]:
        """展示层专用（队列 #250，问题3/4）：u9c 源下曝出最近一次 `load_ap_lines()`
        已缓存的原始 `AP/Query` 行（含 `DocLineNo`——AP 单据自身行号，`_map_u9c_ap_row`
        未映射进 `APLine` 的字段，因 `APLine.line_no` 固定语义为 `SrcPOLineNo`，供
        `price_check.py` 与 PO 做 `(po_no, line_no)` join，不可挪作他用，见该方法注释）。
        与 `load_ap_lines()` 返回的 `APLine` 列表按同序一一对应（`_map_u9c_ap_row` 经
        list comprehension、`parse_ap_lines` 经同序 append，均不重排/不过滤），调用方
        （webapp.py）借此按位置配对还原真实 AP 行号，供"展开详情"展示用，不影响任何
        判定逻辑。非 u9c 源或尚未调用过 `load_ap_lines()`/`load_po_lines()`/`load_grn()`
        （三者共享同一缓存）时返回空列表。

        队列 #390：`ap_no_po_link="divert"` 下被分流的「无 PO 关联」行会从这里**一并
        剔除**——否则本方法与 `load_ap_lines()` 的长度就不再相等，`webapp` 的
        `_u9c_ap_real_line_no` 会整批回落、全表 AP 行号显示悄悄退化。"""
        if not self._u9c_ap_rows_cache:
            return []
        if not self._u9c_ap_diverted_idx:
            return list(self._u9c_ap_rows_cache)
        return [r for i, r in enumerate(self._u9c_ap_rows_cache)
                if i not in self._u9c_ap_diverted_idx]

    def load_po_lines(self) -> list[POLine]:
        if self.data_source == "u9c":
            if self.u9c_connector is None:
                raise RealEndpointNotReadyError("load_po_lines", self.cfg.U9C_FI_NOT_READY)
            po_nos = sorted({r.get("SrcPONo") for r in self._fetch_u9c_ap_rows() if r.get("SrcPONo")})
            rows: list[dict] = []
            for po_no in po_nos:
                rows.extend(self.u9c_connector.get_purchase_lines(po_no))
            return parse_po_lines([_map_u9c_po_row(r) for r in rows])
        return parse_po_lines(_read_csv(self._dir() / "po_lines.csv"))

    def load_grn(self) -> list[GRNLine]:
        if self.data_source == "u9c":
            if self.u9c_connector is None:
                raise RealEndpointNotReadyError("load_grn", self.cfg.U9C_FI_NOT_READY)
            rcv_nos = sorted({r.get("SrcRcvNo") for r in self._fetch_u9c_ap_rows() if r.get("SrcRcvNo")})
            rows: list[dict] = []
            for rcv_no in rcv_nos:
                rows.extend(self.u9c_connector.get_gr_lines(rcv_no))
            return parse_grn([_map_u9c_gr_row(r) for r in rows])
        return parse_grn(_read_csv(self._dir() / "grn.csv"))

    def load_ap_lines(self) -> list[APLine]:
        # 队列 #390：分流留痕列表每次重填，不跨调用累积（同一实例可能被调多次）。
        self.ap_no_po_link_rows = []
        self._u9c_ap_diverted_idx = set()
        kwargs = ({"no_po_link": "divert", "diverted": self.ap_no_po_link_rows}
                  if self.ap_no_po_link == "divert" else {"no_po_link": self.ap_no_po_link})
        if self.data_source == "u9c":
            if self.u9c_connector is None:
                raise RealEndpointNotReadyError("load_ap_lines", self.cfg.U9C_FI_NOT_READY)
            lines = parse_ap_lines(
                [_map_u9c_ap_row(r) for r in self._fetch_u9c_ap_rows()], **kwargs)
            # `_map_u9c_ap_row` 是同序 list comprehension ⇒ 分流行的下标即原始行下标。
            self._u9c_ap_diverted_idx = {d.index for d in self.ap_no_po_link_rows}
            return lines
        return parse_ap_lines(_read_csv(self._dir() / "ap_lines.csv"), **kwargs)

    def load_invoice(self) -> list[InvoiceLine]:
        if self.data_source == "u9c":
            # design D19（队列 #214/§四#43）：显式提供人工誊录小样目录时读取该目录，
            # 不再 fail-loud——但这不是"发票源已解决"，只是把已知的人工誊录小样接进来；
            # 未提供该参数（默认）时，Attachment/OCR 未就绪（队列 #59）的 fail-loud 行为
            # 与本次改动前完全一致，不静默变化。
            if self.invoice_sample_dir is not None:
                return parse_invoice(_read_csv(self.invoice_sample_dir / "invoice.csv"))
            raise RealEndpointNotReadyError("load_invoice", self.cfg.U9C_FI_NOT_READY)
        return parse_invoice(_read_csv(self._dir() / "invoice.csv"))

    def load_payment(self) -> list[PaymentRecord]:
        if self.data_source == "u9c":
            raise RealEndpointNotReadyError("load_payment", self.cfg.U9C_FI_NOT_READY)
        return parse_payment(_read_csv(self._dir() / "payment.csv"))
