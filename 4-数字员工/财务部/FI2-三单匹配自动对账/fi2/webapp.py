"""FI2 三单匹配核对面板 v8 —— 内网 Web 服务（队列 #140 发布收口 → #182/#183 v8 改造）。

v8 改造（2026-07-31，唐燕萍回件《FI2面板改造指令及效果图》权威规格 + 队列 #182/#183）：
六段式平铺 → 结论看板 + 展开/并拢主表（10 列窄表 · 点击行号展开三张单据卡片 + 六个校验块）。
红线（唐燕萍原话"信息全保留，只换看法"，Shao Peishen 已拍板本次跳过 openspec design 审）：
- **只改本文件（UI 展示层）**，`match_engine.py`/`result_classify.py`/`price_check.py`/
  `recon_report.py`/`config.py`/`models.py` 一行未动——判据/容差/五类判定优先级零改动。
- 本文件新增 `_run_with_detail()` 是 `fi2.run.run()` 同一套函数（FeedSource→
  partition_invoices→classify_all→check_ap_po_price→build_report）的**原样复用**，只是
  额外把中间产出的原始 PO/AP/发票明细行一并返回，供"展开详情"渲染单据卡片用——不新增
  任何判定逻辑，审计/`fi2_reconcile_report.json` 落盘内容与改造前完全一致（`build_report`
  调用参数不变）。金额脱敏红线（design D7）约束的是**持久化**（审计 JSONL/报告 JSON 不落
  绝对金额），不约束**当次会话页面即时展示**给财务人员本人看——她本就有权限看真实单据金额。
- v8 规格新增的四个维度——**OCR 字段校验 / 重复发票检测 / 税率合规 / PO 变更检测**——
  当前引擎均未实现（税率合规/重复检测明确属本场景"二期"范围，见场景 CLAUDE.md「定位」段；
  OCR 选型未就绪；PO 变更检测已于队列 #80 评估后明确不采纳）。本文件**如实标注"二期未接入"
  灰色徽标**，不伪装已判定——同 FI2 一贯红线"结果分类如实标注，不伪装已判定"。
  "PO↔AP"列同理仅覆盖真实计算的单价维度（`price_check.py`），非四维全覆盖，列头已标注口径。
- 料品名称：数据模型（`models.py`）无独立"料品名称"字段，只有 `item_code`；本页如实展示
  为"料品编码"，不杜撰名称。

D19 改造（2026-08-03，队列 #214/§四#43，唐燕萍验收 v8 结构后唯一诉求"接真实数据"）：
`u9c` 模式接线真实 PO/AP（连接器代码 D15/D16 已就绪，本次首次被面板端到端驱动）；发票段
新增例外——若场景内 `data/real_round1/invoice.csv`（人工誊录小样，固定目录、非用户自由
填路径）存在则读取，否则维持现状 fail-loud（design D15-b 既定行为不变）。判定口径
（`match_engine.py`/`result_classify.py`/`price_check.py`/`config.py`/`models.py`）一字
未动。报告页在发票源为人工誊录小样时显式标注"⚠️ 发票为人工誊录小样，OCR 未接入"。
"""
from __future__ import annotations

import html
from pathlib import Path

from flask import Flask, Response, request

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.simple_gate import install_flask_gate

from . import config as _config
from .feed_source import FeedSource, partition_invoices
from .item_normalize import normalize_item_code
from .models import APLine, InvoiceLine, POLine
from .price_check import check_ap_po_price
from .recon_report import build_report
from .result_classify import classify_all

_ROOT = Path(__file__).resolve().parent.parent
_MOCK_DIR = _ROOT / "data" / "mock"
# design D19（队列 #214/§四#43，2026-08-03）：u9c 模式下发票人工誊录小样固定目录——
# 刻意不做成 Web 表单自由填路径（避免用户填任意本机路径造成路径穿越/信息泄露面），
# 目录不存在或缺 invoice.csv 时行为不变（load_invoice 维持现状 fail-loud）。
_INVOICE_SAMPLE_DIR = _ROOT / "data" / "real_round1"
_INVOICE_SAMPLE_LABEL = "u9c+人工誊录小样"

_R7_TIP = (
    "口径提示：超差为强制转人工标记，<b>不代表一定是记账错误</b>——round-1 真实数据溯源"
    "（队列 #80）发现“AP 单价 &lt; PO 单价”在卓品可能是"
    "“实际结算价已降、PO 未及时回写变更”的正常业务模式，请结合业务核实，不建议直接以此驳回。"
)

# ────────────────────────────── 页面骨架（v8 浅色主题，贴合唐燕萍效果图配色 §4.1）──────────────────────────────
_PAGE_HEAD = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>FI2 三单匹配核对面板 · 试用版</title>
<style>
  :root{
    --pass:#2e7d32; --pass-bg:#e8f5e9; --pass-border:#4caf50;
    --fail:#c62828; --fail-bg:#ffebee; --fail-border:#f44336;
    --warn:#e65100; --warn-bg:#fff3e0; --warn-border:#ff9800;
    --po-ap:#1565c0; --po-ap-bg:#e3f2fd;
    --neutral:#616161; --neutral-bg:#f0f0f0;
  }
  *{box-sizing:border-box}
  body{font-family:-apple-system,"Segoe UI",'Microsoft YaHei',sans-serif;background:#f5f6f8;color:#1f2937;
       max-width:1240px;margin:0 auto;padding:24px 20px 60px}
  h1{font-size:20px;margin:0 0 4px;color:#111827}
  .badge{display:inline-block;background:#f59e0b;color:#1c1917;font-size:12px;font-weight:700;
         padding:2px 8px;border-radius:4px;vertical-align:middle;margin-left:8px}
  .sub{color:#6b7280;font-size:12.5px;margin-bottom:16px}
  .disclaimer{background:#fdf6e3;border-left:4px solid #f5a623;padding:10px 14px;border-radius:4px;
              font-size:13px;color:#8a5a00;margin-bottom:16px}
  .disclaimer-183{background:#fff8dc;border:1px solid #f0c419;border-radius:6px;padding:10px 16px;
                  font-size:13.5px;font-weight:700;color:#7a5200;margin:14px 0}
  .disclaimer-d19{background:#e3f2fd;border-left:4px solid #1565c0;border-radius:4px;padding:9px 14px;
                   font-size:13px;font-weight:700;color:#0d47a1;margin:10px 0}
  .card{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:16px 20px;margin-bottom:14px;
        box-shadow:0 1px 2px rgba(0,0,0,.04)}
  form{background:#fff;border:1px dashed #cbd5e1;border-radius:8px;padding:24px}
  fieldset{border:1px solid #e5e7eb;border-radius:6px;padding:12px 16px;margin-bottom:14px}
  legend{font-size:12px;color:#1565c0;padding:0 6px}
  label.f{display:block;font-size:12px;color:#374151;margin:8px 0 3px}
  input[type=text]{width:100%;background:#fff;color:#1f2937;border:1px solid #d1d5db;
                    border-radius:4px;padding:7px 10px;font-size:13px;box-sizing:border-box}
  select{background:#fff;color:#1f2937;border:1px solid #d1d5db;border-radius:4px;padding:6px 10px;font-size:13px}
  button{background:#1565c0;color:#fff;border:0;border-radius:6px;padding:9px 22px;font-size:14px;
         cursor:pointer;margin-top:6px}
  button:hover{background:#0d47a1}
  a{color:#1565c0}
  .note{font-size:12px;color:#9ca3af;margin-top:6px}
  pre{white-space:pre-wrap;font-size:12px}

  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin:6px 0}
  .kpi{border-radius:8px;padding:14px 16px;text-align:center;border:1px solid transparent}
  .kpi .kv{font-size:30px;font-weight:800}
  .kpi .kl{font-size:13px;margin-top:2px}
  .kpi-pass{background:var(--pass-bg);color:var(--pass);border-color:var(--pass-border)}
  .kpi-l2{background:var(--warn-bg);color:var(--warn);border-color:var(--warn-border)}
  .kpi-block{background:var(--fail-bg);color:var(--fail);border-color:var(--fail-border)}
  .summary-line{background:#eef4fb;border-radius:6px;padding:9px 14px;font-size:13px;color:#1e3a5f;margin-top:4px}

  .path-labels{margin:10px 0 6px;font-size:12.5px}
  .path-badge{display:inline-block;padding:3px 10px;border-radius:4px;font-weight:700;margin-right:8px}
  .path-badge.po-ap{background:var(--po-ap-bg);color:var(--po-ap)}
  .path-badge.ap-inv{background:var(--warn-bg);color:var(--warn)}
  .path-hint{color:#6b7280}

  table.v8{width:100%;border-collapse:collapse;font-size:12px;min-width:1000px}
  .table-scroll{overflow-x:auto;border:1px solid #e5e7eb;border-radius:6px}
  table.v8 th{background:#f9fafb;color:#374151;text-align:left;padding:8px 8px;border-bottom:1px solid #e5e7eb;
              font-size:11px;white-space:nowrap}
  table.v8 td{padding:7px 8px;border-bottom:1px solid #f1f3f5;vertical-align:top}
  table.v8 tr.row-block td{background:#fff5f5}
  table.v8 tr.row-l2 td{background:#fffaf0}
  table.v8 tr.row-pass td{background:#f4fbf5}
  table.v8 tr.row-detail td{background:#fafbfc}
  .expander{cursor:pointer;border:0;background:none;font-size:13px;color:#4b5563;padding:0 4px}
  .merge-badge{display:inline-block;background:var(--po-ap-bg);color:var(--po-ap);font-size:10px;
               font-weight:700;border-radius:3px;padding:1px 5px;margin-left:4px}
  .ok{color:var(--pass);font-weight:700}
  .bad{color:var(--fail);font-weight:700}
  .na{color:#9ca3af}
  .status-badge{display:inline-block;padding:3px 9px;border-radius:10px;font-size:11px;font-weight:700;
                white-space:nowrap}
  .status-pass{background:var(--pass-bg);color:var(--pass)}
  .status-l2{background:var(--warn-bg);color:var(--warn)}
  .status-block{background:var(--fail-bg);color:var(--fail)}
  .status-sub{font-size:10px;color:#9ca3af;display:block;margin-top:2px}
  .stub{display:inline-block;background:var(--neutral-bg);color:var(--neutral);font-size:10.5px;
        border-radius:3px;padding:1px 6px}

  .op-btn{border:1px solid #d1d5db;background:#fff;color:#374151;border-radius:4px;padding:4px 9px;
          font-size:11px;cursor:pointer}
  .op-btn.disabled{background:#f3f4f6;color:#9ca3af;cursor:default;border-color:#e5e7eb}
  .op-btn.go{background:var(--pass);color:#fff;border-color:var(--pass)}
  .op-btn.back{background:var(--fail);color:#fff;border-color:var(--fail)}
  .reason-pop{display:none;margin-top:6px;background:#fff5f5;border:1px solid var(--fail-border);
              border-radius:4px;padding:8px 10px;font-size:11.5px;color:#7a1f1f;max-width:220px}
  .reason-pop.open{display:block}

  .doc-cards{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0}
  .doc-card{flex:1;min-width:220px;background:#fff;border:1px solid #e5e7eb;border-left:4px solid #999;
            border-radius:6px;padding:10px 12px;font-size:11.5px}
  .doc-card.po{border-left-color:#1565c0}
  .doc-card.ap{border-left-color:#e65100}
  .doc-card.inv{border-left-color:#2e7d32}
  .doc-card h4{margin:0 0 6px;font-size:12.5px}
  .doc-card .miss{color:#9ca3af;font-style:italic}
  .doc-card dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:2px 8px}
  .doc-card dt{color:#6b7280}
  .doc-card dd{margin:0;text-align:right;font-family:ui-monospace,Consolas,monospace}

  .check-blocks{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px;margin:10px 0}
  .check-block{background:#fbfbfc;border:1px solid #e5e7eb;border-radius:6px;padding:9px 11px;font-size:11.5px}
  .check-block h5{margin:0 0 6px;font-size:12px;color:#374151}
  .check-block ul{margin:0;padding-left:16px}
  .check-block li{margin:3px 0}
  .check-block .tip{margin-top:6px;padding-top:6px;border-top:1px dashed #e5e7eb;color:#8a5a00;font-size:11px}

  .block-flow{display:flex;gap:0;align-items:stretch;margin:12px 0 6px;flex-wrap:wrap}
  .flow-step{flex:1;min-width:150px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;
             padding:10px 12px;font-size:12px;text-align:center;position:relative}
  .flow-step b{display:block;font-size:12.5px;margin-bottom:2px}
  .flow-arrow{align-self:center;color:#9ca3af;padding:0 6px;font-size:16px}
</style></head><body>
"""
_PAGE_FOOT = """
<script>
function toggleRow(id){
  var detail = document.getElementById('detail-' + id);
  var icon = document.getElementById('caret-' + id);
  if(!detail) return;
  var open = detail.style.display !== 'none';
  detail.style.display = open ? 'none' : 'table-row';
  if(icon) icon.textContent = open ? '▶' : '▼';
}
function toggleReason(id){
  var el = document.getElementById('reason-' + id);
  if(el) el.classList.toggle('open');
}
</script>
</body></html>"""

_DATA_SOURCE_HELP = (
    "mock＝内置演示夹具（无需填写下方任何字段，用于查看面板长相）｜"
    "csv＝应急桥接目录（如 dump_u9c_snapshot.py 产出的真实 PO/GR/AP 快照 + 人工誊录 invoice.csv"
    "，round-1 已验证路径，不依赖 OCR）｜"
    "u9c＝真实直读 PO/GR/AP；发票段：若场景内已备好人工誊录小样（design D19，队列 #214）"
    "则自动读取并在报告页显式标注'人工誊录小样，OCR未接入'，未备好则如实报错（design D15-b，"
    "Attachment/OCR 尚未就绪）——本模式不支持自由填写发票路径，样本目录固定，不开放任意本机路径"
)

_INDEX_BODY = f"""
<h1>FI2 三单匹配自动对账<span class="badge">试用版·灰度</span></h1>
<div class="sub">AP 单 vs INV 按料品汇总归集比对 + AP-PO 单价强制比对（R7）</div>
<div class="disclaimer">⚠ 试用版：AI 建议/预警，未过账；结案与过账在财务人员（L3 阶段不自动执行，达标后另行晋级 L4）。只读取数，不写回 ERP。</div>
<form action="/run" method="post">
  <fieldset>
    <legend>数据源</legend>
    <label class="f">data_source</label>
    <select name="data_source">
      <option value="mock">mock（演示，无需填写下方字段）</option>
      <option value="csv">csv（应急桥接目录，round-1 人工誊录路径）</option>
      <option value="u9c">u9c（真实直读 PO/GR/AP，发票源暂未就绪）</option>
    </select>
    <div class="note">{html.escape(_DATA_SOURCE_HELP)}</div>
  </fieldset>
  <fieldset>
    <legend>csv 模式</legend>
    <label class="f">数据目录（服务器本机路径，含 po_lines/ap_lines/invoice/payment.csv）</label>
    <input type="text" name="csv_dir" placeholder="如 data/real_round1">
  </fieldset>
  <fieldset>
    <legend>u9c 模式（二选一）</legend>
    <label class="f">AP 单号清单（逗号分隔）</label>
    <input type="text" name="ap_doc_nos" placeholder="如 AP-2026070036,AP-2026070035">
    <label class="f">供应商代码清单（逗号分隔，批量）</label>
    <input type="text" name="ap_supplier_codes" placeholder="如 ZA0066">
    <div class="note">发票段无需填写：若场景内已备好人工誊录小样则自动读取（报告页会显式标注
      "人工誊录小样，OCR未接入"），未备好则如实报错——不支持自由填写发票路径（design D19）。</div>
  </fieldset>
  <fieldset>
    <legend>报告标注（不参与过滤/判定，仅留痕）</legend>
    <label class="f">复核责任人（L3 可归责，IATF 8.3）</label>
    <input type="text" name="evaluator" placeholder="如 唐燕萍/李姣龙">
    <label class="f">期间（仅作报告标注；U9C 暂无按期间过滤字段，不参与取数）</label>
    <input type="text" name="period" placeholder="如 2026-07">
  </fieldset>
  <button type="submit">跑三单匹配</button>
</form>
"""


def _error_page(message: str) -> str:
    return _PAGE_HEAD + f"""
<h1>FI2 三单匹配核对面板</h1>
<div class="card"><h3>⚠ 处理失败（如实回显，非伪装成功）</h3>
<pre>{html.escape(message)}</pre></div>
<a href="/">‹ 返回重新填写</a>
""" + _PAGE_FOOT


def _split_csv_arg(v: str) -> list[str] | None:
    v = (v or "").strip()
    if not v:
        return None
    return [s.strip() for s in v.split(",") if s.strip()]


def _spct(v) -> str:
    """带符号百分比（差异展示用）。"""
    return "—" if v is None else f"{v * 100:+.2f}%"


def _money(v) -> str:
    return "—" if v is None else f"{v:,.2f}"


# ────────────────────────────── 引擎编排（原样复用 fi2.run.run 的调用序列，见模块 docstring）──────────────────────────────

def _run_with_detail(
    data_source: str, *, csv_dir: Path | None = None, evaluator: str = "", period: str = "",
    audit=None, u9c_connector=None, ap_doc_nos: list[str] | None = None,
    ap_supplier_codes: list[str] | None = None, invoice_sample_dir: Path | None = None,
):
    """与 `fi2.run.run()` 调用序列逐字相同（FeedSource→partition_invoices→classify_all→
    check_ap_po_price→build_report，均为既有未改动函数），额外把中间产出的原始明细行
    一并返回供展开详情渲染，不改变 `rep`（审计/报告落盘内容）本身。

    `invoice_sample_dir`（design D19，队列 #214/§四#43）：仅在 `data_source="u9c"` 下有
    意义，调用方传入 `_INVOICE_SAMPLE_DIR`（已存在 invoice.csv 时）或 `None`；原样透传给
    `FeedSource`，不新增判定逻辑。"""
    fs = FeedSource(data_source, mock_dir=_MOCK_DIR, csv_dir=csv_dir,
                     u9c_connector=u9c_connector, ap_doc_nos=ap_doc_nos,
                     ap_supplier_codes=ap_supplier_codes, invoice_sample_dir=invoice_sample_dir)
    po_lines = fs.load_po_lines()
    ap_lines = fs.load_ap_lines()
    invoice_rows = fs.load_invoice()

    linked, orphaned = partition_invoices(ap_lines, invoice_rows)
    items = classify_all(ap_lines, linked)
    price_results = check_ap_po_price(ap_lines, po_lines)

    invoice_source_label = (
        _INVOICE_SAMPLE_LABEL if fs.invoice_sample_dir is not None else fs.data_source
    )
    rep = build_report(
        items, orphaned, price_results,
        ap_lines=ap_lines, po_lines=po_lines,
        data_sources={"po": fs.data_source, "ap": fs.data_source, "invoice": invoice_source_label},
        evaluator=evaluator, period=period, audit=audit,
    )
    return rep, po_lines, ap_lines, linked, orphaned, price_results


# ────────────────────────────── v8 行视图构建（纯展示层聚合，不改判定）──────────────────────────────

def _group_lines(ap_lines: list[APLine], invoice_rows: list[InvoiceLine]):
    """按 (ap_no, 归一化 item_code) 分组，供展开详情查原始行——用既有 `normalize_item_code`
    （item_normalize.py 未改动）与 match_engine 聚合口径保持一致。"""
    ap_by_key: dict[tuple[str, str], list[APLine]] = {}
    for a in ap_lines:
        ap_by_key.setdefault((a.ap_no, normalize_item_code(a.item_code)), []).append(a)
    inv_by_key: dict[tuple[str, str], list[InvoiceLine]] = {}
    for i in invoice_rows:
        inv_by_key.setdefault((i.ap_no, normalize_item_code(i.item_code)), []).append(i)
    return ap_by_key, inv_by_key


def _price_group(price_results) -> dict[tuple[str, str], list]:
    out: dict[tuple[str, str], list] = {}
    for r in price_results:
        out.setdefault((r.ap_no, normalize_item_code(r.item_code)), []).append(r)
    return out


def _po_ap_cell(price_infos) -> str:
    if not price_infos:
        return '<span class="na">— 无PO对照</span>'
    if any(not p.has_po for p in price_infos):
        return '<span class="bad">❌ 缺PO对应行</span>'
    worst = max(price_infos, key=lambda p: abs(p.price_diff_pct or 0))
    if worst.exceeds_tolerance:
        return f'<span class="bad">❌ 单价{_spct(worst.price_diff_pct)}（超差）</span>'
    return '<span class="ok">✅ 单价一致</span>'


def _ap_inv_cell(item: dict) -> str:
    if not item["has_invoice"]:
        return '<span class="na">— 缺发票</span>'
    if item["classification"] == "完全匹配":
        return '<span class="ok">✅ 一致</span>'
    parts = []
    if item.get("qty_diff_pct") not in (None, 0):
        parts.append(f'数量{_spct(item["qty_diff_pct"])}')
    if item.get("untaxed_amount_diff_pct") not in (None, 0):
        parts.append(f'未税{_spct(item["untaxed_amount_diff_pct"])}')
    if item.get("tax_amount_diff_pct") not in (None, 0):
        parts.append(f'税额{_spct(item["tax_amount_diff_pct"])}')
    summary = "，".join(parts) if parts else item["classification"]
    return f'<span class="bad">❌ {html.escape(summary)}（{html.escape(item["classification"])}）</span>'


_STUB = '<span class="stub">🔷 二期未接入</span>'
_STUB_POCHANGE = '<span class="stub">🔷 已评估暂不实现（队列 #80）</span>'

_STATUS_META = {
    "l3_suggested_pass": ("status-pass", "row-pass", "✅ 自动通过"),
    "l2_self_resolved": ("status-l2", "row-l2", "⚡ 微差消化"),
    "needs_review": ("status-block", "row-block", "🚫 BLOCK退回"),
}


def _doc_card_po(po: POLine | None) -> str:
    if po is None:
        return '<div class="doc-card po"><h4>PO 采购订单</h4><div class="miss">— 缺失</div></div>'
    rows = (
        ("单号·行号", f"{po.po_no}·行{po.line_no}"), ("供应商", po.supplier or "—"),
        ("数量·单位", f"{po.qty:g}"), ("单价", _money(po.unit_price)),
        ("不含税金额", _money(po.qty * po.unit_price)), ("税率", _pct_plain(po.tax_rate)),
        ("价税合计", _money(po.amount)), ("下单日期", po.po_date or "—"),
    )
    dl = "".join(f"<dt>{html.escape(k)}</dt><dd>{html.escape(str(v))}</dd>" for k, v in rows)
    return f'<div class="doc-card po"><h4>PO 采购订单</h4><dl>{dl}</dl></div>'


def _doc_card_ap(ap_list: list[APLine]) -> str:
    if not ap_list:
        return '<div class="doc-card ap"><h4>AP 应付单</h4><div class="miss">— 缺失</div></div>'
    a = ap_list[0]
    qty = sum(x.qty for x in ap_list)
    untaxed = sum(x.untaxed_amount for x in ap_list)
    tax = sum(x.tax_amount for x in ap_list)
    rows = (
        ("单号·行号", f"{a.ap_no}·行{a.line_no}" + ("+" if len(ap_list) > 1 else "")),
        ("料品编码", a.item_code), ("数量·单位", f"{qty:g}"),
        ("单价", _money(a.unit_price)), ("不含税金额", _money(untaxed)),
        ("税额", _money(tax)), ("价税合计", _money(untaxed + tax)), ("配票日期", a.ap_date or "—"),
    )
    dl = "".join(f"<dt>{html.escape(k)}</dt><dd>{html.escape(str(v))}</dd>" for k, v in rows)
    return f'<div class="doc-card ap"><h4>AP 应付单</h4><dl>{dl}</dl></div>'


def _doc_card_inv(inv_list: list[InvoiceLine]) -> str:
    if not inv_list:
        return '<div class="doc-card inv"><h4>发票</h4><div class="miss">— 缺失</div></div>'
    i = inv_list[0]
    qty = sum(x.inv_qty for x in inv_list)
    untaxed = sum(x.untaxed_amount for x in inv_list)
    tax = sum(x.tax_amount for x in inv_list)
    rows = (
        ("发票号", i.inv_no + ("+" if len(inv_list) > 1 else "")), ("料品编码", i.item_code),
        ("数量·单位", f"{qty:g}{i.unit or ''}"), ("单价", _money(i.unit_price)),
        ("不含税金额", _money(untaxed)), ("税率", _pct_plain(i.tax_rate)),
        ("税额", _money(tax)), ("价税合计", _money(untaxed + tax)), ("开票日期", i.inv_date or "—"),
    )
    dl = "".join(f"<dt>{html.escape(k)}</dt><dd>{html.escape(str(v))}</dd>" for k, v in rows)
    return f'<div class="doc-card inv"><h4>发票</h4><dl>{dl}</dl></div>'


def _pct_plain(v) -> str:
    return "—" if v is None else f"{v * 100:.0f}%"


def _mapping_lines(po_no_lines: list[APLine], inv_list: list[InvoiceLine]) -> str:
    if not po_no_lines:
        return "无PO无AP，孤立发票"
    lines = []
    for a in po_no_lines:
        inv_part = "、".join(f"发票{i.inv_no}" for i in inv_list) if inv_list else "缺发票"
        lines.append(f"PO-{a.po_no} 行{a.line_no} → AP-{a.ap_no} → {inv_part}")
    return "<br>".join(html.escape(x) for x in lines)


def _four_dim_block(item: dict, price_infos, ap_list: list[APLine]) -> str:
    qty_ok = item["has_invoice"] and (item.get("qty_diff_pct") in (None, 0) or item["classification"] not in
                                       ("数量金额不符", "明细错位"))
    li = []
    li.append(f'<li>料品编码：<span class="ok">✅</span> {html.escape(item["item_code"])}</li>')
    if not item["has_invoice"]:
        li.append('<li>数量：<span class="na">无法核对（缺发票）</span></li>')
        li.append('<li>未税金额：<span class="na">无法核对（缺发票）</span></li>')
        li.append('<li>税额：<span class="na">无法核对（缺发票）</span></li>')
    else:
        for label, key in (("数量", "qty_diff_pct"), ("未税金额", "untaxed_amount_diff_pct"), ("税额", "tax_amount_diff_pct")):
            v = item.get(key)
            if v in (None, 0):
                li.append(f'<li>{label}：<span class="ok">✅</span></li>')
            else:
                li.append(f'<li>{label}：<span class="bad">❌ {_spct(v)}</span></li>')
    if len(ap_list) > 1:
        li.append(f'<li>底部备注：AP {len(ap_list)} 行合并归集后按总额比对</li>')
    body = f'<ul>{"".join(li)}</ul>'
    price_failed = item.get("price_check_failed") and any(p.exceeds_tolerance for p in price_infos)
    tip = f'<div class="tip">{_R7_TIP}</div>' if price_failed else ""
    return f'<div class="check-block"><h5>① 四维匹配</h5>{body}{tip}</div>'


def _build_row(idx: int, item: dict, ap_by_key, inv_by_key, price_by_key) -> str:
    """渲染一行（并拢 <tr> + 展开 <tr id=detail-N>）。"""
    key = (item["ap_no"], normalize_item_code(item["item_code"]))
    ap_list = sorted(ap_by_key.get(key, []), key=lambda a: a.line_no)
    price_infos = price_by_key.get(key, [])

    css_cls, row_cls, status_label = _STATUS_META[item["status"]]
    ap_no_disp = f'{item["ap_no"]}·行{ap_list[0].line_no}' if ap_list else item["ap_no"]
    if len(ap_list) > 1:
        ap_no_disp = f'{item["ap_no"]}·行{ap_list[0].line_no}-{ap_list[-1].line_no}'
        merge_badge = '<span class="merge-badge">合并</span>'
    else:
        merge_badge = ""

    if item["status"] == "needs_review":
        reason = html.escape(_ap_inv_reason_text(item))
        action = (
            f'<button class="op-btn" onclick="toggleReason({idx})">📋 退回原因</button>'
            f'<div class="reason-pop" id="reason-{idx}">{reason}</div>'
        )
    elif item["status"] == "l3_suggested_pass":
        action = '<span class="op-btn disabled">已通过</span>'
    else:
        action = '<span class="op-btn disabled">已消化</span>'

    tr = f"""
<tr class="{row_cls}">
  <td><button class="expander" id="caret-{idx}" onclick="toggleRow({idx})">▶</button> {idx + 1}</td>
  <td>{html.escape(ap_no_disp)}{merge_badge}</td>
  <td>{html.escape(item["item_code"])}</td>
  <td>{_po_ap_cell(price_infos)}</td>
  <td>{_ap_inv_cell(item)}</td>
  <td>{_STUB}</td>
  <td>{_STUB}</td>
  <td>{_STUB}</td>
  <td><span class="status-badge {css_cls}">{status_label}</span></td>
  <td>{action}</td>
</tr>"""
    return tr


def _ap_inv_reason_text(item: dict) -> str:
    bits = [f'判定：{item["classification"]}']
    if item.get("price_check_failed"):
        bits.append(f'单价超差 {_spct(item.get("price_diff_pct"))}')
    if not item["has_invoice"]:
        bits.append("该 AP 单此料品缺发票支撑")
    return "；".join(bits)


def _render_table(rep: dict, po_lines, ap_lines, linked_invoices, orphaned, price_results) -> str:
    ap_by_key, inv_by_key = _group_lines(ap_lines, linked_invoices)
    price_by_key = _price_group(price_results)
    po_by_key = {(p.po_no, p.line_no): p for p in po_lines}

    rows_html = []
    idx = 0
    for item in rep["items"]:
        key = (item["ap_no"], normalize_item_code(item["item_code"]))
        ap_list = sorted(ap_by_key.get(key, []), key=lambda a: a.line_no)
        inv_list = inv_by_key.get(key, [])
        price_infos = price_by_key.get(key, [])

        rows_html.append(_build_row(idx, item, ap_by_key, inv_by_key, price_by_key))

        po_cards = "".join(_doc_card_po(po_by_key.get((a.po_no, a.line_no))) for a in ap_list) or _doc_card_po(None)
        detail = f"""
<tr class="row-detail" id="detail-{idx}" style="display:none">
  <td colspan="10">
    <div class="doc-cards">{po_cards}{_doc_card_ap(ap_list)}{_doc_card_inv(inv_list)}</div>
    <div class="check-blocks">
      {_four_dim_block(item, price_infos, ap_list)}
      <div class="check-block"><h5>② OCR 字段校验（8字段）</h5>{_STUB}</div>
      <div class="check-block"><h5>③ 税率合规</h5>{_STUB}</div>
      <div class="check-block"><h5>④ 重复发票检测</h5>{_STUB}</div>
      <div class="check-block"><h5>⑤ PO 变更检测</h5>{_STUB_POCHANGE}</div>
      <div class="check-block"><h5>⑥ 行级映射</h5>{_mapping_lines(ap_list, inv_list)}</div>
    </div>
  </td>
</tr>"""
        rows_html.append(detail)
        idx += 1

    for inv in orphaned:
        item_pseudo = {
            "ap_no": "（无AP）", "item_code": inv.item_code, "has_invoice": False,
            "classification": "孤立发票", "status": "needs_review",
            "price_check_failed": False, "price_diff_pct": None,
            "qty_diff_pct": None, "untaxed_amount_diff_pct": None, "tax_amount_diff_pct": None,
        }
        css_cls, row_cls, status_label = _STATUS_META["needs_review"]
        reason = html.escape(f"孤立发票：{inv.inv_no} 挂载 ap_no={inv.ap_no} 找不到对应 AP 单")
        rows_html.append(f"""
<tr class="{row_cls}">
  <td><button class="expander" id="caret-{idx}" onclick="toggleRow({idx})">▶</button> {idx + 1}</td>
  <td>（无AP）</td>
  <td>{html.escape(inv.item_code)}</td>
  <td><span class="na">— 缺PO</span></td>
  <td><span class="na">— 无法核对（孤立发票）</span></td>
  <td>{_STUB}</td>
  <td>{_STUB}</td>
  <td>{_STUB}</td>
  <td><span class="status-badge {css_cls}">{status_label}</span></td>
  <td><button class="op-btn" onclick="toggleReason({idx})">📋 退回原因</button>
      <div class="reason-pop" id="reason-{idx}">{reason}</div></td>
</tr>
<tr class="row-detail" id="detail-{idx}" style="display:none">
  <td colspan="10">
    <div class="doc-cards">{_doc_card_po(None)}{_doc_card_ap([])}{_doc_card_inv([inv])}</div>
    <div class="check-blocks">
      <div class="check-block"><h5>① 四维匹配</h5>无法核对（孤立发票，找不到对应AP单/PO单）</div>
      <div class="check-block"><h5>② OCR 字段校验（8字段）</h5>{_STUB}</div>
      <div class="check-block"><h5>③ 税率合规</h5>{_STUB}</div>
      <div class="check-block"><h5>④ 重复发票检测</h5>{_STUB}</div>
      <div class="check-block"><h5>⑤ PO 变更检测</h5>{_STUB_POCHANGE}</div>
      <div class="check-block"><h5>⑥ 行级映射</h5>无PO无AP，孤立发票</div>
    </div>
  </td>
</tr>""")
        idx += 1

    return (
        '<div class="table-scroll"><table class="v8">'
        '<thead><tr><th>#</th><th>AP单号·行号</th><th>料品编码</th><th>PO↔AP(单价)</th>'
        '<th>AP↔发票</th><th>税率合规</th><th>重复检测</th><th>OCR</th><th>判定/状态</th><th>操作</th></tr></thead>'
        f'<tbody>{"".join(rows_html)}</tbody></table></div>'
    )


def _render_kpi(total_rows: int, n_pass: int, n_l2: int, n_block: int) -> str:
    return f"""
<div class="kpis">
  <div class="kpi kpi-pass"><div class="kv">{n_pass}</div><div class="kl">✅ 自动通过</div></div>
  <div class="kpi kpi-l2"><div class="kv">{n_l2}</div><div class="kl">⚡ 微差消化</div></div>
  <div class="kpi kpi-block"><div class="kv">{n_block}</div><div class="kl">🚫 BLOCK退回</div></div>
</div>
<div class="summary-line">本次共 {total_rows} 项料品，{n_pass} 项自动通过，{n_l2} 项微差消化，{n_block} 项BLOCK退回。</div>
"""


def _render_block_flow() -> str:
    steps = (
        ("① BLOCK退回", "系统自动判定"), ("② 业务部门ERP补传", "在ERP中补充/修正"),
        ("③ 回到财务", "数据回流面板"), ("④ 财务人工审核", "看附件 → 点过/退回"),
    )
    parts = []
    for i, (t, s) in enumerate(steps):
        if i:
            parts.append('<div class="flow-arrow">→</div>')
        parts.append(f'<div class="flow-step"><b>{html.escape(t)}</b>{html.escape(s)}</div>')
    return (
        '<div class="card"><h3 style="margin:0 0 8px;font-size:14px">🔁 BLOCK处理流程</h3>'
        f'<div class="block-flow">{"".join(parts)}</div>'
        '<div class="note">说明：数值差异统一走BLOCK退回，补传由业务部门在ERP中完成，面板不设补传按钮。'
        '财务仅需在"已补充待审核"状态下查看附件，人工点击确认通过或退回。</div></div>'
    )


def _report_page(rep: dict, po_lines, ap_lines, linked_invoices, orphaned, price_results) -> str:
    ds = rep["data_sources"]
    n_pass = rep["summary"]["l3_suggested_pass"]
    n_l2 = rep["summary"]["l2_self_resolved"]
    n_block = rep["summary"]["needs_review"] + len(orphaned)
    total_rows = rep["summary"]["total"] + len(orphaned)

    invoice_is_sample = ds.get("invoice") == _INVOICE_SAMPLE_LABEL
    d19_banner = (
        '<div class="disclaimer-d19">⚠️ 发票为人工誊录小样，OCR 未接入——'
        '本轮真实数据接入第一轮（design D19，队列 #214），仅 PO/AP 为真实直读，'
        '发票段来自人工誊录的真实发票小样（非自动解析），供核对判定口径用；'
        '规模化自动读票待 OCR round-2（队列 #82）。</div>'
    ) if invoice_is_sample else ""

    return _PAGE_HEAD + f"""
<h1>FI2 三单匹配核对面板<span class="badge">试用版·灰度</span></h1>
<div class="sub">规则版本 {html.escape(rep["rule_version"])} ｜ 自动化等级 {html.escape(rep["automation_level"])}
 ｜ 数据源 PO={html.escape(ds["po"])}/AP={html.escape(ds["ap"])}/发票={html.escape(ds["invoice"])}
 ｜ 期间 {html.escape(rep["period"] or "（未填）")}</div>
<div class="disclaimer">{html.escape(rep["disclaimer"])}</div>
{d19_banner}

<div class="card">
  {_render_kpi(total_rows, n_pass, n_l2, n_block)}
</div>

<div class="disclaimer-183">⚠️ 本报告所有判定均为 AI 建议，不构成过账依据。自动通过/微差消化/BLOCK 退回均需财务确认后操作。</div>

<div class="path-labels">
  核对路径：<span class="path-badge po-ap">PO↔AP</span><span class="path-badge ap-inv">AP↔发票</span>
  <span class="path-hint">四维匹配：料品名称·数量·未税金额·税额（本页料品名称展示为料品编码，见页脚说明）</span>
</div>

<div class="card">
  <h3 style="margin:0 0 8px;font-size:14px">📋 三单核对明细表 — 点击行号展开/收起详情</h3>
  {_render_table(rep, po_lines, ap_lines, linked_invoices, orphaned, price_results)}
</div>

{_render_block_flow()}

<div class="note" style="margin-top:10px">
  已知口径说明：① "PO↔AP"仅覆盖单价维度（R7 强制比对），非四维全覆盖；
  ② 税率合规/重复发票检测/OCR字段校验/PO变更检测四项本引擎尚未实现（税率合规·重复检测为本场景"二期"范围，
  OCR 选型未就绪，PO变更检测已于队列 #80 评估后明确不采纳），如实标注"二期未接入"，不伪装已判定；
  ③ 已写入平台 audit（scenario=FI2，L3，append-only，金额脱敏——仅留差异比例，本页展示的原始单据金额
  仅用于当次会话即时展示，不落审计/报告持久化）。
</div>

<a href="/">‹ 重新跑一次</a>
""" + _PAGE_FOOT


def create_app(*, reports_dir: Path) -> Flask:
    """构建 Flask app。`reports_dir` 由调用方传入（通常是场景内 reports/，已 gitignore）。"""
    app = Flask(__name__)
    install_flask_gate(app, service_name="FI2 三单匹配自动对账")
    reports_dir.mkdir(parents=True, exist_ok=True)
    audit_path = reports_dir / "fi2_web_audit.jsonl"
    access_trace_path = reports_dir / "fi2_web_access_trace.jsonl"

    @app.get("/api/ping")
    def ping():
        return {"status": "ok", "service": "FI2 三单匹配自动对账"}

    @app.get("/")
    def index():
        return Response(_PAGE_HEAD + _INDEX_BODY + _PAGE_FOOT, mimetype="text/html")

    @app.post("/run")
    def do_run():
        data_source = (request.form.get("data_source") or "mock").strip().lower()
        if data_source not in ("mock", "csv", "u9c"):
            return Response(_error_page(f"未知数据源：{data_source}"), mimetype="text/html"), 400

        csv_dir_raw = (request.form.get("csv_dir") or "").strip()
        evaluator = (request.form.get("evaluator") or "").strip() or "财务专员(Web-试用版)"
        period = (request.form.get("period") or "").strip()
        ap_doc_nos = _split_csv_arg(request.form.get("ap_doc_nos", ""))
        ap_supplier_codes = _split_csv_arg(request.form.get("ap_supplier_codes", ""))

        csv_dir = None
        if data_source == "csv":
            if not csv_dir_raw:
                return Response(_error_page("csv 模式需填写数据目录路径"), mimetype="text/html"), 400
            csv_dir = Path(csv_dir_raw)
            if not csv_dir.is_dir():
                return Response(
                    _error_page(f"数据目录不存在或不是目录：{csv_dir_raw}"), mimetype="text/html"
                ), 400

        u9c_connector = None
        invoice_sample_dir = None
        if data_source == "u9c":
            if not ap_doc_nos and not ap_supplier_codes:
                return Response(
                    _error_page("u9c 模式需填写「AP 单号清单」或「供应商代码清单」其一"),
                    mimetype="text/html",
                ), 400
            try:
                from zhuopin_platform.audit.sinks import JsonlSink
                from zhuopin_platform.shared_tools.connector_audit import ConnectorAudit
                from zhuopin_platform.shared_tools.erp_connector import ZpConnector

                trace = ConnectorAudit(sink=JsonlSink(access_trace_path))
                u9c_connector = ZpConnector.from_env(audit=trace)
            except Exception as exc:  # noqa: BLE001 —— 凭据/连接构造失败需如实呈现
                return Response(
                    _error_page(f"U9C 连接构造失败：{exc}"), mimetype="text/html"
                ), 500
            # design D19（队列 #214/§四#43）：固定目录、非用户可填路径（见模块常量注释）；
            # 目录或 invoice.csv 缺失时保持 None，`load_invoice()` 维持现状 fail-loud。
            if (_INVOICE_SAMPLE_DIR / "invoice.csv").is_file():
                invoice_sample_dir = _INVOICE_SAMPLE_DIR

        audit = AuditLogger.jsonl(audit_path)
        try:
            rep, po_lines, ap_lines, linked, orphaned, price_results = _run_with_detail(
                data_source, csv_dir=csv_dir, evaluator=evaluator, period=period,
                audit=audit, u9c_connector=u9c_connector,
                ap_doc_nos=ap_doc_nos, ap_supplier_codes=ap_supplier_codes,
                invoice_sample_dir=invoice_sample_dir,
            )
        except Exception as exc:  # noqa: BLE001 —— 引擎异常（含 fail-loud）需如实回显，而非空白 500
            import traceback
            return Response(
                _error_page(f"对账失败：{exc}\n\n{traceback.format_exc()}"), mimetype="text/html"
            ), 500

        return Response(_report_page(rep, po_lines, ap_lines, linked, orphaned, price_results), mimetype="text/html")

    return app
