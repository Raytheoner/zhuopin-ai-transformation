"""明细层 —— 冻结数据集 → 逐行明细（**纯函数**）＋ 数据集快照读写（队列 §一 `#538`）。

🔴 **为什么要有这一层**（姚祖怡 2026-09-09 原话）：「你的周报数据和我线下计算的数据无法对
起来……需要把你的计算的过程明细列出来，例如你周报中下单行数是 187 行，你把这 187 行的明细
列出来反馈给我，然后我们线下人工一一核对后进行运算逻辑及取数差异的纠正。」

⇒ 这不是新指标，是**既有指标的正确性质疑**。要回答它，周报上每一个「行数」都必须能展开成
「正是这些行」，而且展开出来的行数**必须与周报上的数字逐字相等**——差一行，明细就是在
替一个数说谎。

三条纪律：

1. **明细与指标同源**：本模块只吃 `FrozenDataset` ＋ `Window`，行集判据（落窗口、剔除已关闭、
   确认数量已知）**直接复用 `metrics.py` 的同一组函数**，不另写一份。口径只有一处，明细才不会
   与指标各说各话。
2. **对账是硬断言**：`reconcile()` 把每节明细的行数与周报指标逐格比对，**任一格不等即上抛**。
   导出接口在写出第一个字节前先过这一关——宁可 500，也不给出一份「看起来对、数却不一致」的明细。
3. **数据集随快照落盘**：周报快照（`sc2_weekly_*.json`）只存聚合值，无法事后展开；本模块把整个
   `FrozenDataset` 另存一份（`sc2_dataset_*.json`），使**任何一期**都能脱离 ERP 重新展开到行、
   甚至重算全部指标。导出接口**只读这份落盘数据、绝不现取 ERP**——现取的数据与他手上那份周报
   不是同一时刻的，对不上是必然的、对上了才是巧合。

⚠️ 本模块不碰基准日逻辑（§一 `#506` 在跑行）、不接任何推送通道；明细交到专员手上属对外交付，
须走跟进信审批，本模块只管产出与自查。
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from . import config
from .metrics import _open_lines
from .models import (
    LINE_STATUS_UNKNOWN,
    FrozenDataset,
    OrderLine,
    ReceiptRecord,
    WeeklyReport,
)
from .windows import Window, WindowSet, build_windows

#: 三个可导出的节。键＝URL 段与 CLI 参数；值＝(中文名, 对账所对的周报指标 key)。
#: 🔴 「在途」节对的是 `open_line_count`（未清行数）——它数的是**本窗口内下单、且至今未清**的行，
#: 不是全库所有未清行；这一口径与 `metrics._SPECS` 里 `open_line_count` 的定义**完全同源**。
SECTIONS: dict[str, tuple[str, str]] = {
    "order": ("下单", "order_line_count"),
    "receipt": ("收货", "receipt_line_count"),
    "open": ("在途", "open_line_count"),
}

#: 三个窗口槽位。键＝URL 参数；值＝周报上的中文名。
WINDOWS: dict[str, str] = {
    "current": "本周",
    "previous": "上周",
    "month_ago": "上月同期",
}

#: 行级状态码的人可读名（U9C `PM_POLine.Status`，见 `models.CLOSED_LINE_STATUSES`）。
_LINE_STATUS_TEXT = {
    0: "0 开立", 1: "1 审核中", 2: "2 已审核未交清",
    3: "3 自然关闭", 4: "4 短缺关闭", 5: "5 超额关闭",
    LINE_STATUS_UNKNOWN: "未取到",
}

#: 「未取到」的统一呈现。**不写 0**——0 会被读成「订了 0 个」，而真相是这个数没取到。
_UNKNOWN = "未取到"


class DetailMismatch(RuntimeError):
    """明细行数与周报指标不等。

    刻意做成异常而非告警：一份行数与周报不一致的明细，比没有明细更坏——他会拿它逐行核对，
    然后把「差的那几行」当成 ERP 取数差异去追，而其实是我方两处口径分了叉。
    """


@dataclass(frozen=True)
class DetailTable:
    """一节明细：列头 ＋ 行 ＋ 「计入本节行数」的行数。

    `counted` 是**被周报指标数进去的行数**，与 `len(rows)` 可能不同：在途节把窗口内全部下单行
    都列出来、用「计入未清行数」一列标出哪几行被数进去、其余几行为什么被剔除——他要核对的
    正是这些剔除理由，只给「数进去的行」等于把判据藏起来。
    """

    section: str
    window: str
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    counted: int


def _fmt_date(d: date | None) -> str:
    return d.isoformat() if d else ""


def _fmt_num(v: float) -> str:
    """数值列：整数不带小数位，其余保留两位。**不做千分位**——那是给人看的，这是给 Excel 对的。"""
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.2f}"


def _in_window(window: Window, day: date | None) -> bool:
    return day is not None and window.contains(day)


# ── 下单 ────────────────────────────────────────────────────────────────────

_ORDER_COLUMNS = (
    "采购单号", "行号", "制单日期", "单据类型", "料号", "供应商编码", "供应商名称", "采购员",
    "确认数量", "含税单价", "下单金额", "累计收货", "行状态", "未清数量",
)


def order_lines_in(dataset: FrozenDataset, window: Window) -> list[OrderLine]:
    """本窗口内**下单**的行——与 `metrics.compute_metrics` 里 `_ctx().lines` 同一判据。"""
    return [l for l in dataset.order_lines if _in_window(window, l.order_date)]


def _order_row(l: OrderLine) -> tuple[Any, ...]:
    known = l.qty_confirmed_known
    return (
        l.po_id, l.line_no, _fmt_date(l.order_date), l.doc_type, l.material_id,
        l.supplier_id, l.supplier_name, l.buyer,
        _fmt_num(l.qty_ordered) if known else _UNKNOWN,
        _fmt_num(l.unit_price),
        _fmt_num(l.amount) if known else _UNKNOWN,
        _fmt_num(l.qty_received),
        _LINE_STATUS_TEXT.get(l.line_status, str(l.line_status)),
        _fmt_num(l.qty_open) if known else _UNKNOWN,
    )


def order_table(dataset: FrozenDataset, window: Window, slot: str = "current") -> DetailTable:
    """下单明细：**每一行就是「下单行数」数进去的一行**，行数恒等于该指标。"""
    lines = sorted(order_lines_in(dataset, window),
                   key=lambda l: (l.order_date or date.min, l.po_id, _line_sort_key(l.line_no)))
    rows = tuple(_order_row(l) for l in lines)
    return DetailTable("order", slot, _ORDER_COLUMNS, rows, counted=len(rows))


def _line_sort_key(line_no: str) -> tuple[int, Any]:
    """行号排序：数字行号按数值排，非数字的排在后面按字面排。"""
    try:
        return (0, int(line_no))
    except (TypeError, ValueError):
        return (1, line_no)


# ── 收货 ────────────────────────────────────────────────────────────────────

_RECEIPT_COLUMNS = (
    "收货单号", "行号", "入库过账日", "来源采购单号", "来源行号", "料号", "供应商名称",
    "收货数量", "含税单价", "收货金额", "可溯源到采购订单行",
)


def receipts_in(dataset: FrozenDataset, window: Window) -> list[ReceiptRecord]:
    """本窗口内**收货**的行——与 `metrics.compute_metrics` 里 `_ctx().receipts` 同一判据。"""
    return [r for r in dataset.receipts if _in_window(window, r.receipt_date)]


def receipt_table(dataset: FrozenDataset, window: Window, slot: str = "current") -> DetailTable:
    """收货明细：行数恒等于「收货行数」；「可溯源」一列＝该行能否 JOIN 回**全量**订单行索引
    （与 `metrics._receipt_match_rate` 同一索引——那张订单可能是几周前下的，故索引不限窗口）。"""
    order_index = {(l.po_id, l.line_no) for l in dataset.order_lines}
    receipts = sorted(receipts_in(dataset, window),
                      key=lambda r: (r.receipt_date or date.min, r.receipt_doc_no,
                                     _line_sort_key(r.line_no)))
    rows = tuple((
        r.receipt_doc_no, r.line_no, _fmt_date(r.receipt_date), r.po_id, r.po_line_no,
        r.material_id, r.supplier_name, _fmt_num(r.qty_received), _fmt_num(r.unit_price),
        _fmt_num(r.amount), "是" if (r.po_id, r.po_line_no) in order_index else "否",
    ) for r in receipts)
    return DetailTable("receipt", slot, _RECEIPT_COLUMNS, rows, counted=len(rows))


# ── 在途 ────────────────────────────────────────────────────────────────────

_OPEN_COLUMNS = _ORDER_COLUMNS + ("计入未清行数", "剔除原因")


def _open_exclusion_reason(l: OrderLine) -> str:
    """一行为什么**没**被数进「未清行数」。与 `metrics._open_lines` 的判据逐条对应，
    顺序也一致（先看关闭状态，再看未清量）。"""
    if l.is_closed:
        return f"行状态已关闭（{_LINE_STATUS_TEXT.get(l.line_status, l.line_status)}）"
    if not l.qty_confirmed_known:
        return "确认数量未取到 ⇒ 未清数量无法计算，按 0 处理"
    if l.qty_open <= 0:
        return "累计收货 ≥ 确认数量，未清数量为 0"
    return ""


def open_table(dataset: FrozenDataset, window: Window, slot: str = "current") -> DetailTable:
    """在途明细：列出本窗口内**全部**下单行，标出哪几行被数进「未清行数」、其余为何剔除。

    `counted` ＝ 被 `metrics._open_lines` 选中的行数，恒等于「未清行数」。
    """
    lines = sorted(order_lines_in(dataset, window),
                   key=lambda l: (l.order_date or date.min, l.po_id, _line_sort_key(l.line_no)))
    counted_ids = {(l.po_id, l.line_no) for l in _open_lines(lines)}
    rows = []
    for l in lines:
        counted = (l.po_id, l.line_no) in counted_ids
        rows.append(_order_row(l) + ("是" if counted else "否",
                                     "" if counted else _open_exclusion_reason(l)))
    return DetailTable("open", slot, _OPEN_COLUMNS, tuple(rows), counted=len(counted_ids))


_BUILDERS = {"order": order_table, "receipt": receipt_table, "open": open_table}


def build_table(dataset: FrozenDataset, windows: WindowSet, section: str, slot: str) -> DetailTable:
    """按节与窗口槽位出一张明细表。`section`／`slot` 拼错即报错，不猜。"""
    if section not in SECTIONS:
        raise ValueError(f"未知明细节：{section!r}（只接受 {'/'.join(SECTIONS)}）")
    if slot not in WINDOWS:
        raise ValueError(f"未知窗口：{slot!r}（只接受 {'/'.join(WINDOWS)}）")
    return _BUILDERS[section](dataset, getattr(windows, slot), slot)


# ── 对账 ────────────────────────────────────────────────────────────────────

def reconcile(dataset: FrozenDataset, windows: WindowSet, report: WeeklyReport) -> dict[str, dict[str, int]]:
    """三节 × 三窗口逐格对账：明细「计入行数」必须等于周报指标值。

    返回 ``{section: {slot: counted}}`` 供接口回显；**任一格不等即抛 `DetailMismatch`**。
    """
    metrics = {m.key: m for m in report.metrics}
    out: dict[str, dict[str, int]] = {}
    problems: list[str] = []
    for section, (name, metric_key) in SECTIONS.items():
        out[section] = {}
        metric = metrics.get(metric_key)
        for slot in WINDOWS:
            table = build_table(dataset, windows, section, slot)
            out[section][slot] = table.counted
            reported = None if metric is None else getattr(metric, slot).value
            if reported is None or int(round(reported)) != table.counted:
                problems.append(
                    f"{name}节·{WINDOWS[slot]}：明细计入 {table.counted} 行，"
                    f"周报「{metric_key}」＝{reported}")
    if problems:
        raise DetailMismatch("明细与周报指标不一致，拒绝导出：" + "；".join(problems))
    return out


# ── CSV ─────────────────────────────────────────────────────────────────────

def render_csv(table: DetailTable) -> str:
    """CSV 文本。**带 UTF-8 BOM**——不带的话 Excel 双击打开中文全是乱码，而他就是用 Excel 对。
    行尾 CRLF 同理（RFC 4180 ＋ Excel 习惯）。"""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(table.columns)
    w.writerows(table.rows)
    return "\ufeff" + buf.getvalue()


def csv_filename(period: str, section: str, slot: str) -> str:
    """下载文件名，如 ``sc2_2026-W36_下单_本周.csv``。"""
    return f"sc2_{period}_{SECTIONS[section][0]}_{WINDOWS[slot]}.csv"


# ── 数据集快照 ──────────────────────────────────────────────────────────────

#: 数据集快照 schema 版本。字段增减必须升版，旧文件读到版本不符**直接拒绝**——
#: 静默补缺省值正是 D29 那次事故的形态（旧缓存缺字段 ⇒ 取到缺省值而报表看上去正常）。
DATASET_SCHEMA = 1


def dataset_path(period: str) -> Path:
    """某期的数据集快照，与 `config.snapshot_path` 同目录、同期次键。"""
    return config.reports_dir() / f"sc2_dataset_{period}.json"


def _line_to_dict(l: OrderLine) -> dict[str, Any]:
    return {
        "po_id": l.po_id, "line_no": l.line_no, "material_id": l.material_id,
        "supplier_id": l.supplier_id, "qty_ordered": l.qty_ordered,
        "qty_received": l.qty_received, "order_date": _fmt_date(l.order_date) or None,
        "expected_date": _fmt_date(l.expected_date) or None,
        "confirmed_date": _fmt_date(l.confirmed_date) or None,
        "line_status": l.line_status, "unit_price": l.unit_price,
        "supplier_name": l.supplier_name, "buyer": l.buyer, "doc_type": l.doc_type,
        "qty_confirmed_known": l.qty_confirmed_known,
    }


def _line_from_dict(d: dict[str, Any]) -> OrderLine:
    return OrderLine(
        po_id=d["po_id"], line_no=d["line_no"], material_id=d["material_id"],
        supplier_id=d["supplier_id"], qty_ordered=d["qty_ordered"],
        qty_received=d["qty_received"],
        order_date=date.fromisoformat(d["order_date"]) if d.get("order_date") else None,
        expected_date=date.fromisoformat(d["expected_date"]) if d.get("expected_date") else None,
        confirmed_date=date.fromisoformat(d["confirmed_date"]) if d.get("confirmed_date") else None,
        line_status=d["line_status"], unit_price=d["unit_price"],
        supplier_name=d["supplier_name"], buyer=d["buyer"], doc_type=d["doc_type"],
        qty_confirmed_known=d["qty_confirmed_known"],
    )


def _receipt_to_dict(r: ReceiptRecord) -> dict[str, Any]:
    return {
        "receipt_doc_no": r.receipt_doc_no, "line_no": r.line_no, "po_id": r.po_id,
        "po_line_no": r.po_line_no, "material_id": r.material_id,
        "supplier_name": r.supplier_name,
        "receipt_date": _fmt_date(r.receipt_date) or None,
        "qty_received": r.qty_received, "unit_price": r.unit_price,
    }


def _receipt_from_dict(d: dict[str, Any]) -> ReceiptRecord:
    return ReceiptRecord(
        receipt_doc_no=d["receipt_doc_no"], line_no=d["line_no"], po_id=d["po_id"],
        po_line_no=d["po_line_no"], material_id=d["material_id"],
        supplier_name=d["supplier_name"],
        receipt_date=date.fromisoformat(d["receipt_date"]) if d.get("receipt_date") else None,
        qty_received=d["qty_received"], unit_price=d["unit_price"],
    )


def dataset_to_dict(dataset: FrozenDataset, period: str) -> dict[str, Any]:
    return {
        "schema": DATASET_SCHEMA,
        "period": period,
        "mode": dataset.mode,
        "fetched_at": dataset.fetched_at,
        "range_start": _fmt_date(dataset.range_start) or None,
        "range_end": _fmt_date(dataset.range_end) or None,
        "source_notes": dict(dataset.source_notes),
        "endpoint_filter_trust": dict(dataset.endpoint_filter_trust),
        "order_lines": [_line_to_dict(l) for l in dataset.order_lines],
        "receipts": [_receipt_to_dict(r) for r in dataset.receipts],
    }


def dataset_from_dict(data: dict[str, Any]) -> FrozenDataset:
    if data.get("schema") != DATASET_SCHEMA:
        raise ValueError(
            f"数据集快照 schema={data.get('schema')!r} 与当前 {DATASET_SCHEMA} 不符，拒绝读取"
            "（静默补缺省值会让明细看起来正常而数是错的，同 D29）")
    return FrozenDataset(
        order_lines=tuple(_line_from_dict(d) for d in data["order_lines"]),
        receipts=tuple(_receipt_from_dict(d) for d in data["receipts"]),
        mode=data["mode"], fetched_at=data["fetched_at"],
        range_start=date.fromisoformat(data["range_start"]) if data.get("range_start") else None,
        range_end=date.fromisoformat(data["range_end"]) if data.get("range_end") else None,
        source_notes=dict(data.get("source_notes", {})),
        endpoint_filter_trust=dict(data.get("endpoint_filter_trust", {})),
    )


def save_dataset(dataset: FrozenDataset, period: str) -> Path:
    """随周报快照一并落盘整个冻结数据集。**与 `report.save_snapshot` 成对调用**，
    缺了它，该期周报就只有聚合值、展不开到行。"""
    path = dataset_path(period)
    path.write_text(json.dumps(dataset_to_dict(dataset, period), ensure_ascii=False, indent=1),
                    encoding="utf-8")
    return path


def load_dataset(period: str) -> FrozenDataset:
    """读某期数据集快照。**不存在即上抛**——绝不回退到现取 ERP：现取的数据与他手上那份
    周报不是同一时刻的，行数对不上是必然、对上了才是巧合。"""
    path = dataset_path(period)
    if not path.exists():
        raise FileNotFoundError(
            f"未找到 {period} 期数据集快照：{path}。该期周报生成于明细导出上线之前，"
            f"或快照已被清理；请对该期重新全量重算（POST /api/refresh）后再导出。")
    return dataset_from_dict(json.loads(path.read_text(encoding="utf-8")))


def windows_of(report: WeeklyReport) -> WindowSet:
    """由周报的基准日复原三窗口——与生成该期时用的 `build_windows(base)` 同一函数。"""
    return build_windows(report.base_date)
