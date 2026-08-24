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

发票级幂等（2026-08-24 补，队列 #371）
────────────────────────────────────
**真实生产错误**：唐燕萍 2026-08-21 举证 `AP-2026070036·行10`／`R01F.0034` 面板显示
数量 42,000／未税 145,320／税额 18,891.60，恰为真实发票（`26327000000742719331`）
21,000／72,660／9,445.80 的 **2 倍**，面板据此报「数量金额不符」并 BLOCK 退回。

**根因**：原去重只有**文件内容 SHA256** 一层（`_hash_file`→`discover_new_files`→
`is_processed`）。同一张发票只要出现在两份**字节不同**的 xlsx 里（重导一次、导出
区间重叠、另存一次都会改变字节），两份都会被摄取，`write_invoice_csv` 又是追加写
⇒ 同一发票的行进 `invoice.csv` 两次，面板按 `(ap_no, item_code)` 聚合求和后翻倍。
2026-08-24 在 `.51` 实测坐实：3409 行中 `(inv_no, ap_no, item_code)` 去重后仅 2703，
上述目标发票在 `invoice.csv` 里正好 2 行且逐字段相同，而它在现存源文件里只有 1 行
（另一份来自已被删除的文件）。

**修法＝发票级幂等，「首个文件胜出」**：数电发票号码唯一标识一张发票，发票一经开出
其明细不可变（要改只能红冲重开、换号）⇒ **某个 `inv_no` 已由某个文件贡献过，则此后
任何**其它**文件里的同号发票行一律跳过**。

  🔴 **判据只对「跨文件」成立，同一文件内不去重** —— 真实数据里同一张发票出现同
  料品、同数量、同单价的多行是合法的（实测 `26942000000588188581` 单张发票 60 行、
  其中一组签名重复 6 次，全部来自同一份源文件）。**按行内容去重会误删这些合法行**，
  故本模块**不看行内容**，只看「这张发票是不是别的文件已经贡献过了」。

  🔴 **零新增载体** —— 已摄取发票号集合**直接从 `invoice.csv` 现读**
  （`load_ingested_invoice_nos`），不另立状态文件。理由同 `detect_source_silence`
  复用 ledger：多一份状态就多一处会与真相分叉的地方；而 `invoice.csv` 本身就是
  「哪些发票已经进来了」的唯一真相，重建它即自动重建这道闸，不会出现「CSV 已重建
  但闸还记得旧发票、那批行再也回不来」的锁死态。

  跳过的行**不进 `diagnostics`** —— 那是「未解析、需人工核对」的留痕，而跨文件重复
  是预期内的正常现象（她的导出区间本就会重叠），混进去会淹没真正的失败信号，也会
  被 `tax_export_scan` 的文件级失败判定误读。改为独立计数
  （`duplicate_rows_skipped`／`duplicate_invoice_nos`）由调用方如实打印——**不静默**。
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
    # 发票级幂等（队列 #371）：因该发票号已由**别的**文件贡献过而跳过的行。
    # 刻意不进 `diagnostics`——那是「需人工核对」的留痕，跨文件重复属预期正常现象。
    duplicate_rows_skipped: int = 0
    duplicate_invoice_nos: list[str] = field(default_factory=list)


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


# ── 发票级幂等闸（队列 #371）──────────────────────────────────────────────

def load_ingested_invoice_nos(invoice_csv_path: Path | str) -> set[str]:
    """读出 `invoice.csv` 里已有的全部 `inv_no`——即「哪些发票已经进来了」。

    **零新增载体**（见模块 docstring）：不另立状态文件，`invoice.csv` 自己就是唯一
    真相。文件不存在（首次摄取）返回空集合，**不报错**——「还没开始」不是异常。

    ⚠️ 表头缺失/字段名不符时同样返回空集合而非抛错：本函数只是一道去重闸，读不到
    就退化为「不去重」＝原有行为，绝不因为闸本身读不出而让整次摄取失败。
    """
    p = Path(invoice_csv_path)
    if not p.exists():
        return set()
    with open(p, encoding="utf-8-sig", newline="") as f:
        return {
            str(row["inv_no"]).strip()
            for row in csv.DictReader(f)
            if row.get("inv_no")
        }


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


def ingest_directory(
    export_dir: Path | str, ledger_path: Path | str, connector, *, now: str,
    known_invoice_nos: set[str] | None = None,
) -> IngestResult:
    """扫描目录 → 跳过已处理 → 解析 → ap_no/item_code 反查 → 产出结果（不落盘，见
    `write_invoice_csv`）。`now` 由调用方传入处理时间戳（ISO 字符串），保持本函数
    纯净可测（不读系统时钟）。

    `known_invoice_nos`＝**此前批次**已摄取过的数电发票号码集合（队列 #371 发票级
    幂等闸，调用方用 `load_ingested_invoice_nos(<out_dir>/invoice.csv)` 取）。命中者
    其行一律跳过并计入 `duplicate_rows_skipped`。**本函数不修改传入的集合**（复制一份
    用），调用方可安全复用。

    ⚠️ **传 None 不等于关掉闸** —— 它只表示「没有历史包袱」，本次运行内**跨文件**的
    重复照样会被挡（本次新处理的每份文件都会把自己贡献的发票号并进闸）。要让闸完全
    生效必须传 `known_invoice_nos`，否则跨批次的重复（第二天的新文件含昨天的发票）
    仍会漏过——**#371 那次翻倍正是跨批次形态**。

    🔴 **闸只挡跨文件重复**：每份文件开始处理前先快照一次「已知发票号」，该文件自身
    新贡献的发票号在**本文件处理完之后**才并入快照 —— 故同一文件内同号发票的多行
    （真实数据里合法且常见）全部保留，不会被自己挡掉。
    """
    ledger = load_ledger(ledger_path)
    result = IngestResult()
    new_files = discover_new_files(export_dir, ledger)
    known: set[str] = set(known_invoice_nos or ())

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
        # 本文件开始处理前的快照——闸只挡「别的文件已贡献过」，不挡本文件自身
        # 同号发票的多行（真实数据里合法且常见，见模块 docstring）。
        seen_before_this_file = set(known)
        contributed_here: set[str] = set()
        for idx, raw in enumerate(raw_rows, start=2):
            digital_no = str(raw.get("数电发票号码") or "").strip()
            if not digital_no:
                result.diagnostics.append(IngestDiagnostic(
                    file=path.name, row_index=idx, reason="digital_invoice_no_missing"))
                continue

            if digital_no in seen_before_this_file:
                # 该发票已由别的文件（或此前批次）贡献过 —— 跳过，不重复计数。
                # 刻意不进 diagnostics（见 IngestResult 字段注释），但如实计数。
                result.duplicate_rows_skipped += 1
                if digital_no not in result.duplicate_invoice_nos:
                    result.duplicate_invoice_nos.append(digital_no)
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
            contributed_here.add(digital_no)

        # 本文件贡献的发票号在此刻才并入闸——保证同文件内多行不自挡（见 docstring）。
        known |= contributed_here
        mark_processed(ledger, file_hash, path.name, row_count=row_count, processed_at=now)
        result.files_processed.append(path.name)

    save_ledger(ledger_path, ledger)
    return result


def write_invoice_csv(rows: list[dict], out_path: Path | str) -> None:
    """把已解析行写入 `invoice.csv`（既有 `invoice_sample_dir` 通道认识的字段格式）。

    追加写入：若目标文件已存在（此前批次摄取过），保留旧行、追加新行。

    🔴 **本函数本身不做去重**（2026-08-24 队列 #371 更正此处口径）。去重现在有**两**
    层，缺一层就会出现「面板数字翻倍」：

      ① **文件层**（`.processed_exports.json`，内容 SHA256）——同一份**字节相同**的
         源文件不会被摄取两次。
      ② **发票层**（`ingest_directory(known_invoice_nos=...)`，队列 #371 新增）——
         同一张**数电发票**不会由两份不同文件各贡献一次。

    2026-08-24 之前只有 ①，而她的导出区间本就会重叠、重导一次即改变字节 ⇒ 同一发票
    经两份文件各入库一次，本函数照单追加，面板聚合后翻倍。**调用方必须传
    `known_invoice_nos`**，否则退化回只有 ① 的旧行为。
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
