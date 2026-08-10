"""税务导出发票明细 Excel 接入（design：openspec/changes/fi2-tax-export-ingest，队列 #295）。

背景：唐燕萍（财务 AI 专员）2026-08-04 拍板 OCR 方案作废，改为「税务系统导出发票明细
Excel → 放固定目录 → 定期提取字段」；2026-08-06 把落盘目录/导出责任人时点/新增文件
判据/完整性校验口径四个决策点全部定死（详见场景 CLAUDE.md 队列 #295 段）。

本模块只产出既有 `feed_source.FeedSource(invoice_sample_dir=...)` 通道已经认识的
`invoice.csv`（字段：inv_no/ap_no/item_code/unit/unit_price/inv_qty/untaxed_amount/
tax_rate/tax_amount/inv_date）——`feed_source.py`/`parse_invoice`/`partition_invoices`
本模块一律不改、原样复用。

两处反查（design D1/D2，均基于 2026-08-07 真实探测，非纸面假设）：

  · ap_no：导出 Excel 无我方内部单号，唯一可用标识是「数电发票号码」。真实探测证实
    `AP/Query.InvoiceNo` 字段**与数电发票号码字面不总是相等**（多数只存后 8 位，少数
    存全串）——改用「后 8 位查询 + 客户端 suffix 校验」，已用全部 8 个真实样本验证
    8/8 唯一命中。`AP/Query` 的 `invoiceNo` 过滤参数服务端是 CONTAINS 语义（非精确
    匹配，用哨兵值验证过），故服务端返回集合不可直接信任，必须客户端二次校验。

  · item_code：导出 Excel 无我方料号（只有「货物或应税劳务名称」+「规格型号」文本，
    此前 65.8% 匹配率已证伪单纯文本匹配路子）。ap_no 已确定后，用该 AP 单下的行项目
    （`ItemCode` 即我方真实料号）按 (数量, 含税单价) 唯一匹配来赋值；命中 0 或 ≥2 行
    时不得猜测，标记未解析、留痕待人工核对（fail-loud，不静默丢弃也不静默猜错）。
"""
from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import openpyxl

_SHEET_NAME = "信息汇总表"

# 「信息汇总表」sheet 必需列（缺任一列即判定该文件解析失败，不产出部分数据）。
_REQUIRED_COLUMNS = (
    "数电发票号码", "货物或应税劳务名称", "规格型号", "单位",
    "数量", "单价", "金额", "税率", "税额", "开票日期",
)

_INVOICE_CSV_FIELDS = [
    "inv_no", "ap_no", "item_code", "unit", "unit_price",
    "inv_qty", "untaxed_amount", "tax_rate", "tax_amount", "inv_date",
]

# item_code 反查时 (数量, 含税单价) 的相对容差——非 config.py R1-R7 业务容差体系
# 的一部分，纯粹用于摄取阶段的行匹配去噪（真实浮点误差量级，见 design D2）。
_QTY_REL_TOL = 1e-6
_PRICE_REL_TOL = 1e-4


@dataclass
class IngestDiagnostic:
    """一条无法自动解析/摄取的记录（不静默丢弃，见 spec「未解析记录留痕不静默丢弃」）。"""
    file: str
    reason: str          # "sheet_missing" / "field_missing" / "ap_no_zero_match" /
                          # "ap_no_ambiguous" / "item_code_zero_match" / "item_code_ambiguous"
    detail: str = ""
    digital_invoice_no: Optional[str] = None
    row_index: Optional[int] = None   # 1-based，sheet 内数据行号；文件级问题为 None


@dataclass
class IngestResult:
    resolved_rows: list[dict] = field(default_factory=list)     # 已就绪的 invoice.csv 行
    diagnostics: list[IngestDiagnostic] = field(default_factory=list)
    files_processed: list[str] = field(default_factory=list)
    files_skipped: list[str] = field(default_factory=list)      # 已在已处理清单中，本次跳过


# ── 已处理清单（内容哈希，design D4）───────────────────────────────────────

def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_ledger(ledger_path: Path | str) -> dict:
    p = Path(ledger_path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_ledger(ledger_path: Path | str, ledger: dict) -> None:
    p = Path(ledger_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")


def is_processed(ledger: dict, file_hash: str) -> bool:
    return file_hash in ledger


def mark_processed(ledger: dict, file_hash: str, filename: str, *, row_count: int, processed_at: str) -> None:
    ledger[file_hash] = {"file": filename, "row_count": row_count, "processed_at": processed_at}


# ── Excel 解析 ────────────────────────────────────────────────────────────

def _resolve_sheet_name(sheetnames: list[str]) -> Optional[str]:
    """匹配「信息汇总表」sheet：精确名优先，否则退而取第一个以该名为前缀的 sheet。

    队列 #82 第二班拆件巡逻真实数据比对发现：唐燕萍手工导出的真实批量文件里，该
    sheet 实际命名为「信息汇总表1」（round-1 那 8 个验证样本里是精确的「信息汇总表」，
    无后缀）——两者列结构逐字段核对完全一致，只是 sheet 名多一个后缀，故按前缀匹配
    兼容两种命名，不改变列结构解析逻辑。
    """
    if _SHEET_NAME in sheetnames:
        return _SHEET_NAME
    for name in sheetnames:
        if name.startswith(_SHEET_NAME):
            return name
    return None


def parse_export_workbook(path: Path | str) -> list[dict]:
    """解析「信息汇总表」（或「信息汇总表1」等前缀变体）sheet，返回逐行原始字典（键=表头原文）。

    工作表缺失/必需列缺失时抛 ValueError（调用方据此产出 sheet_missing/field_missing
    诊断，不产出该文件的任何发票明细记录——spec「工作表缺失或结构不符」场景）。
    """
    wb = openpyxl.load_workbook(path, data_only=True)
    sheet_name = _resolve_sheet_name(wb.sheetnames)
    if sheet_name is None:
        raise ValueError(f"缺少「{_SHEET_NAME}」工作表（现有 sheet：{wb.sheetnames}）")
    ws = wb[sheet_name]
    header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())
    header = [str(h).strip() if h is not None else "" for h in header_row]
    missing = [c for c in _REQUIRED_COLUMNS if c not in header]
    if missing:
        raise ValueError(f"「{_SHEET_NAME}」缺少必需列：{missing}")

    rows: list[dict] = []
    for raw in ws.iter_rows(min_row=2, values_only=True):
        if raw is None or all(v is None for v in raw):
            continue
        rows.append(dict(zip(header, raw)))
    return rows


def _parse_tax_rate(v) -> float:
    """「13%」这类字符串 → 0.13；已是数值则原样转 float。"""
    if v is None:
        return 0.0
    s = str(v).strip()
    if s.endswith("%"):
        return float(s[:-1]) / 100.0
    return float(s)


def _parse_date(v) -> str:
    """「2026-07-10 11:33:22」→「2026-07-10」（同既有 `_u9c_date` 截取惯例）。"""
    if v is None:
        return ""
    s = str(v).strip()
    return s[:10]


# ── ap_no 反查（design D1）───────────────────────────────────────────────

def resolve_ap_no(connector, digital_invoice_no: str) -> tuple[Optional[str], str, str]:
    """用「数电发票号码」反查唯一 ap_no。

    返回 (ap_no_or_None, reason, detail)：
      · 唯一命中 → (ap_no, "", "")
      · 零命中   → (None, "ap_no_zero_match", "")
      · 歧义     → (None, "ap_no_ambiguous", "候选：<ap_no 列表>")

    不假设服务端 `invoiceNo` 过滤是精确匹配（2026-08-07 真实探测证实是 CONTAINS
    语义）——用后 8 位查询后，仍对每一候选行的 `InvoiceNo` 做客户端 suffix 校验，
    只有 `digital_invoice_no.endswith(候选.InvoiceNo)` 才采信。
    """
    suffix = digital_invoice_no[-8:] if len(digital_invoice_no) > 8 else digital_invoice_no
    candidates = connector.get_ap_lines_by_invoice_no(suffix)
    ap_nos: set[str] = set()
    for row in candidates:
        stored = row.get("InvoiceNo")
        if stored and digital_invoice_no.endswith(str(stored)):
            doc_no = row.get("DocNo")
            if doc_no:
                ap_nos.add(str(doc_no))
    if not ap_nos:
        return None, "ap_no_zero_match", ""
    if len(ap_nos) > 1:
        return None, "ap_no_ambiguous", f"候选：{sorted(ap_nos)}"
    return next(iter(ap_nos)), "", ""


# ── item_code 反查（design D2）───────────────────────────────────────────

def resolve_item_code(
    ap_lines_for_ap_no: list[dict], qty: float, untaxed_unit_price: float, tax_rate: float,
) -> tuple[Optional[str], str, str]:
    """用 (数量, 含税单价) 在已知 ap_no 的行项目中唯一匹配料品编码。

    `ap_lines_for_ap_no`：该 ap_no 下 `AP/Query` 原始行列表（调用方按 ap_no 取好，
    本函数不发起网络调用，便于测试与复用同一 ap_no 下多张发票行共享一次拉取）。

    返回 (item_code_or_None, reason, detail)，reason 语义同 `resolve_ap_no`。
    """
    taxed_unit_price = untaxed_unit_price * (1 + tax_rate)
    matched_codes: set[str] = set()
    for row in ap_lines_for_ap_no:
        ap_qty = row.get("APQtyTU")
        ap_price = row.get("TaxPrice")
        item_code = row.get("ItemCode")
        if ap_qty is None or ap_price is None or not item_code:
            continue
        ap_qty = float(ap_qty)
        ap_price = float(ap_price)
        qty_close = abs(ap_qty - qty) <= max(abs(qty), abs(ap_qty)) * _QTY_REL_TOL + 1e-9
        price_close = abs(ap_price - taxed_unit_price) <= max(abs(taxed_unit_price), abs(ap_price)) * _PRICE_REL_TOL + 1e-9
        if qty_close and price_close:
            matched_codes.add(str(item_code))
    if not matched_codes:
        return None, "item_code_zero_match", ""
    if len(matched_codes) > 1:
        return None, "item_code_ambiguous", f"候选：{sorted(matched_codes)}"
    return next(iter(matched_codes)), "", ""


# ── 编排 ──────────────────────────────────────────────────────────────────

def discover_new_files(export_dir: Path | str, ledger: dict) -> list[tuple[Path, str]]:
    """列出 `export_dir` 下未出现在 `ledger` 中的 `.xlsx` 文件，返回 (路径, 内容哈希) 列表。"""
    out: list[tuple[Path, str]] = []
    for p in sorted(Path(export_dir).glob("*.xlsx")):
        h = _hash_file(p)
        if not is_processed(ledger, h):
            out.append((p, h))
    return out


def ingest_directory(export_dir: Path | str, ledger_path: Path | str, connector, *, now: str) -> IngestResult:
    """扫描目录 → 跳过已处理 → 解析 → ap_no/item_code 反查 → 产出结果（不落盘，见
    `write_invoice_csv`）。`now` 由调用方传入处理时间戳（ISO 字符串），保持本函数
    纯净可测（不读系统时钟）。
    """
    ledger = load_ledger(ledger_path)
    result = IngestResult()
    new_files = discover_new_files(export_dir, ledger)

    all_files = sorted(Path(export_dir).glob("*.xlsx"))
    new_paths = {p for p, _ in new_files}
    for p in all_files:
        if p not in new_paths:
            result.files_skipped.append(p.name)

    ap_lines_cache: dict[str, list[dict]] = {}
    # 同一张发票的多个明细行共享同一「数电发票号码」（真实样本已观察到单张发票
    # 182 行的情形，见 sample_8/AP-2026050057）——按 digital_no 缓存 ap_no 反查结果，
    # 避免对同一发票号重复发起真实网络请求（此前无缓存时曾在真实端点上耗时超 2 分钟）。
    ap_no_cache: dict[str, tuple[Optional[str], str, str]] = {}

    for path, file_hash in new_files:
        try:
            raw_rows = parse_export_workbook(path)
        except ValueError as e:
            result.diagnostics.append(IngestDiagnostic(file=path.name, reason="parse_error", detail=str(e)))
            continue

        row_count = 0
        for idx, raw in enumerate(raw_rows, start=2):
            digital_no = str(raw.get("数电发票号码") or "").strip()
            if not digital_no:
                result.diagnostics.append(IngestDiagnostic(
                    file=path.name, row_index=idx, reason="digital_invoice_no_missing"))
                continue

            if digital_no not in ap_no_cache:
                ap_no_cache[digital_no] = resolve_ap_no(connector, digital_no)
            ap_no, reason, detail = ap_no_cache[digital_no]
            if ap_no is None:
                result.diagnostics.append(IngestDiagnostic(
                    file=path.name, row_index=idx, digital_invoice_no=digital_no,
                    reason=reason, detail=detail))
                continue

            if ap_no not in ap_lines_cache:
                ap_lines_cache[ap_no] = connector.get_ap_lines(ap_no)

            qty = float(raw.get("数量") or 0)
            unit_price = float(raw.get("单价") or 0)
            tax_rate = _parse_tax_rate(raw.get("税率"))
            item_code, i_reason, i_detail = resolve_item_code(
                ap_lines_cache[ap_no], qty, unit_price, tax_rate)
            if item_code is None:
                result.diagnostics.append(IngestDiagnostic(
                    file=path.name, row_index=idx, digital_invoice_no=digital_no,
                    reason=i_reason, detail=i_detail))
                continue

            result.resolved_rows.append({
                "inv_no": digital_no,
                "ap_no": ap_no,
                "item_code": item_code,
                "unit": str(raw.get("单位") or ""),
                "unit_price": unit_price,
                "inv_qty": qty,
                "untaxed_amount": float(raw.get("金额") or 0),
                "tax_rate": tax_rate,
                "tax_amount": float(raw.get("税额") or 0),
                "inv_date": _parse_date(raw.get("开票日期")),
            })
            row_count += 1

        mark_processed(ledger, file_hash, path.name, row_count=row_count, processed_at=now)
        result.files_processed.append(path.name)

    save_ledger(ledger_path, ledger)
    return result


def write_invoice_csv(rows: list[dict], out_path: Path | str) -> None:
    """把已解析行写入 `invoice.csv`（既有 `invoice_sample_dir` 通道认识的字段格式）。

    追加写入：若目标文件已存在（此前批次摄取过），保留旧行、追加新行——`ap_no`
    反查具备幂等性（同一发票重复摄取会解出同一 ap_no），但本函数本身不做去重，
    去重责任在「已处理清单」层（同一份源文件不会被摄取两次）。
    """
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    file_exists = p.exists()
    with open(p, "a" if file_exists else "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_INVOICE_CSV_FIELDS)
        if not file_exists:
            w.writeheader()
        for r in rows:
            w.writerow(r)
