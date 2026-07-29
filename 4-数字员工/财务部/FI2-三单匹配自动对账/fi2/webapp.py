"""FI2 三单匹配自动对账 —— 内网 Web 服务（发布收口，队列 #140，任务范围已定死不得膨胀）。

流程：财务专员选数据源（mock 演示 / csv 应急桥接·配合 dump_u9c_snapshot.py+人工誊录发票
/ u9c 真实直读）→ 填 AP 单号清单或供应商代码清单（u9c 模式）或数据目录（csv 模式）→
调**既有** `fi2.run.run()`（零改动，逐字透传其参数）→ 页面呈现六段式报告，**直接复用**
`recon_report.build_report()` 现有输出字段，不新增/不改写任何判定结构。

红线（不得放宽，逐条对应队列 #140 收口要求）：
- 只读取数，不写回 ERP —— 本层不新增任何写路径，`fi2.run.run()` 本身即为只读管线。
- L2/L3 人工确认门禁照旧 —— 报告 disclaimer 原样透传（"AI 建议通过/预警，未过账"）。
- R1/R5/R7 `config.py` 真值一字不动 —— 本层只从 `_config` 读取当前值用于展示说明文案，
  不修改、不新增判据（R7 判据本身正在队列 #80 里被重新评估，见 `_R7_NOTE`）。
- 结果分类如实标注（完全匹配/差异/待人工），不伪装已判定 —— 直接展示
  `item["classification"]`/`item["status"]` 原值，不做任何美化或合并。
- 数据源限制如实告知 —— u9c 源下 Invoice（发票）无条件 fail-loud（design D15-b，
  Attachment/OCR 未就绪），本层捕获后如实说明，不静默降级、不假装能出完整三单匹配。
- 仅 LAN 访问（无登录鉴权，同 SC8/QD-B/命令中心惯例）；页面显著标注"试用版"。
"""
from __future__ import annotations

import html
import traceback
from pathlib import Path

from flask import Flask, Response, request

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.simple_gate import install_flask_gate

from . import config as _config
from .run import run as _run_fi2

_PAGE_HEAD = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>FI2 三单匹配自动对账 · 试用版</title>
<style>
  body{font-family:-apple-system,"Segoe UI",'Microsoft YaHei',sans-serif;background:#0f172a;color:#e2e8f0;
       max-width:1080px;margin:0 auto;padding:24px 20px 60px}
  h1{font-size:20px;margin:0 0 4px}
  .badge{display:inline-block;background:#f59e0b;color:#1c1917;font-size:12px;font-weight:700;
         padding:2px 8px;border-radius:4px;vertical-align:middle;margin-left:8px}
  .sub{color:#94a3b8;font-size:13px;margin-bottom:20px}
  .disclaimer{background:#1e293b;border-left:3px solid #f59e0b;padding:10px 14px;border-radius:4px;
              font-size:13px;color:#fbbf24;margin-bottom:20px}
  .card{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px 20px;margin-bottom:14px}
  .card h3{margin:0 0 10px;font-size:14px;color:#93c5fd;display:flex;align-items:center;gap:8px}
  ul{margin:6px 0 0;padding-left:20px}
  li{margin:4px 0;font-size:13px;line-height:1.5}
  .meta{font-size:12px;color:#94a3b8}
  .empty{color:#64748b;font-size:13px}
  form{background:#1e293b;border:1px dashed #475569;border-radius:8px;padding:24px}
  fieldset{border:1px solid #334155;border-radius:6px;padding:12px 16px;margin-bottom:14px}
  legend{font-size:12px;color:#93c5fd;padding:0 6px}
  label.f{display:block;font-size:12px;color:#cbd5e1;margin:8px 0 3px}
  input[type=text]{width:100%;background:#0f172a;color:#e2e8f0;border:1px solid #334155;
                    border-radius:4px;padding:7px 10px;font-size:13px;box-sizing:border-box}
  select{background:#0f172a;color:#e2e8f0;border:1px solid #334155;border-radius:4px;padding:6px 10px;font-size:13px}
  button{background:#2563eb;color:#fff;border:0;border-radius:6px;padding:9px 22px;font-size:14px;
         cursor:pointer;margin-top:6px}
  button:hover{background:#1d4ed8}
  a{color:#60a5fa}
  .note{font-size:12px;color:#64748b;margin-top:6px}
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin:10px 0 4px}
  .kpi{background:#0f172a;border:1px solid #263349;border-radius:6px;padding:10px 12px}
  .kpi .kl{font-size:11px;color:#94a3b8}
  .kpi .kv{font-size:20px;font-weight:700;margin-top:2px}
  table.grid{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:4px}
  table.grid th{background:#0f172a;color:#93c5fd;text-align:left;padding:6px 8px;border-bottom:1px solid #334155}
  table.grid td{padding:5px 8px;border-bottom:1px solid #263349;vertical-align:top}
  table.grid tr.row-review td{background:rgba(248,113,113,.08)}
  table.grid tr.row-l2 td{background:rgba(251,191,36,.08)}
  table.grid tr.row-pass td{background:rgba(74,222,128,.06)}
  .scroll-box{max-height:420px;overflow:auto;border:1px solid #263349;border-radius:6px}
  .tag{display:inline-block;padding:1px 7px;border-radius:10px;font-size:11px;font-weight:700;white-space:nowrap}
  .tag-pass{background:#14532d;color:#4ade80}
  .tag-review{background:#7f1d1d;color:#f87171}
  .tag-l2{background:#78350f;color:#fbbf24}
</style></head><body>
"""
_PAGE_FOOT = "</body></html>"

_DATA_SOURCE_HELP = (
    "mock＝内置演示夹具（无需填写下方任何字段，用于查看报告长相）｜"
    "csv＝应急桥接目录（如 dump_u9c_snapshot.py 产出的真实 PO/GR/AP 快照 + 人工誊录 invoice.csv"
    "，round-1 已验证路径，不依赖 OCR）｜"
    "u9c＝真实直读 PO/GR/AP（发票源 Attachment/OCR 尚未就绪，design D15-b，将在此步如实报错）"
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
<h1>FI2 三单匹配自动对账</h1>
<div class="card"><h3>⚠ 处理失败（如实回显，非伪装成功）</h3>
<pre style="white-space:pre-wrap;font-size:12px">{html.escape(message)}</pre></div>
<a href="/">‹ 返回重新填写</a>
""" + _PAGE_FOOT


def _split_csv_arg(v: str) -> list[str] | None:
    v = (v or "").strip()
    if not v:
        return None
    return [s.strip() for s in v.split(",") if s.strip()]


def _pct(v) -> str:
    return "—" if v is None else f"{v * 100:.2f}%"


_STATUS_TAG = {
    "l3_suggested_pass": ("tag-pass", "row-pass", "L3 建议通过"),
    "needs_review": ("tag-review", "row-review", "需人工确认"),
    "l2_self_resolved": ("tag-l2", "row-l2", "L2 自行消化"),
}


def _item_rows_html(items: list[dict]) -> str:
    if not items:
        return '<div class="empty">无</div>'
    rows = []
    for it in items:
        tag_cls, row_cls, label = _STATUS_TAG.get(it["status"], ("", "", it["status"]))
        price_note = f'单价超差 {_pct(it["price_diff_pct"])}' if it["price_check_failed"] else "—"
        rows.append(
            f'<tr class="{row_cls}"><td>{html.escape(it["ap_no"])}</td>'
            f'<td>{html.escape(it["item_code"])}</td>'
            f'<td>{html.escape(it["classification"])}</td>'
            f'<td>{_pct(it["qty_diff_pct"])}</td><td>{_pct(it["untaxed_amount_diff_pct"])}</td>'
            f'<td>{_pct(it["tax_amount_diff_pct"])}</td><td>{html.escape(price_note)}</td>'
            f'<td><span class="tag {tag_cls}">{html.escape(label)}</span></td></tr>'
        )
    return (
        '<div class="scroll-box"><table class="grid">'
        '<thead><tr><th>AP单号</th><th>料品</th><th>分类</th><th>数量差%</th>'
        '<th>未税差%</th><th>税额差%</th><th>单价校验</th><th>状态</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


def _orphaned_rows_html(orphaned: list[dict]) -> str:
    if not orphaned:
        return '<div class="empty">无孤立发票</div>'
    rows = "".join(
        f'<tr><td>{html.escape(o["inv_no"])}</td><td>{html.escape(o["ap_no"])}</td>'
        f'<td>{html.escape(o["item_code"])}</td></tr>'
        for o in orphaned
    )
    return (
        '<table class="grid"><thead><tr><th>发票号</th><th>挂载AP单号</th><th>料品</th></tr></thead>'
        f'<tbody>{rows}</tbody></table>'
    )


def _r7_note_html(cfg) -> str:
    suppliers = "、".join(cfg.FOREIGN_CURRENCY_SUPPLIERS) or "（无）"
    return (
        f'人民币供应商统一容差 ±{cfg.AP_PO_PRICE_TOLERANCE_PCT * 100:.1f}%'
        f'（外币供应商 {html.escape(suppliers)} 过渡期同一容差处理）。'
        '规则版本：' + html.escape(cfg.RULE_VERSION) + '。'
        '<br><b>口径提示</b>：超差为强制转人工标记，<b>不代表一定是记账错误</b>——'
        'round-1 真实数据溯源（队列 #80）发现"AP 单价 &lt; PO 单价"在卓品可能是'
        '"实际结算价已降、PO 未及时回写变更"的正常业务模式，R7 判据本身正在业务口径'
        '重新评估中，请结合业务核实，不建议直接以此驳回。'
    )


def _report_page(rep: dict) -> str:
    s = rep["summary"]
    ds = rep["data_sources"]
    return _PAGE_HEAD + f"""
<h1>FI2 三单匹配对账报告<span class="badge">试用版·灰度</span></h1>
<div class="sub">规则版本 {html.escape(rep["rule_version"])} ｜ 自动化等级 {html.escape(rep["automation_level"])}
 ｜ 数据源 PO={html.escape(ds["po"])}/AP={html.escape(ds["ap"])}/发票={html.escape(ds["invoice"])}
 ｜ 期间 {html.escape(rep["period"] or "（未填）")}</div>
<div class="disclaimer">{html.escape(rep["disclaimer"])}</div>

<div class="card">
  <h3>① 总判定</h3>
  <div class="kpis">
    <div class="kpi"><div class="kl">料品总数</div><div class="kv">{s["total"]}</div></div>
    <div class="kpi"><div class="kl">L3 建议通过</div><div class="kv" style="color:#4ade80">{s["l3_suggested_pass"]}</div></div>
    <div class="kpi"><div class="kl">L2 自行消化</div><div class="kv" style="color:#fbbf24">{s["l2_self_resolved"]}</div></div>
    <div class="kpi"><div class="kl">需人工确认</div><div class="kv" style="color:#f87171">{s["needs_review"]}</div></div>
    <div class="kpi"><div class="kl">孤立发票</div><div class="kv">{s["orphaned_invoices"]}</div></div>
    <div class="kpi"><div class="kl">AP-PO单价超差</div><div class="kv" style="color:#f87171">{s["price_check_alerts"]}</div></div>
  </div>
  <div class="meta">分类分布：{html.escape(str(s["by_classification"]))}</div>
</div>

<div class="card">
  <h3>② 完全匹配 / L3 建议通过（{len(rep["l3_suggested_pass"])} 项，AI 建议通过，未过账，可批量抽查）</h3>
  {_item_rows_html(rep["l3_suggested_pass"])}
</div>

<div class="card">
  <h3>③ 需人工确认（{len(rep["needs_review"])} 项，如实标注差异/待人工，不伪装已判定）</h3>
  {_item_rows_html(rep["needs_review"])}
</div>

<div class="card">
  <h3>④ L2 自行消化（{len(rep["l2_self_resolved"])} 项，整单差异总额在 R5 门禁线内，AP 自行消化不转人工）</h3>
  {_item_rows_html(rep["l2_self_resolved"])}
</div>

<div class="card">
  <h3>⑤ AP-PO 单价强制比对（{len(rep["price_check_alerts"])} 项超差）</h3>
  <div class="meta">{_r7_note_html(_config)}</div>
  {_item_rows_html(rep["price_check_alerts"])}
</div>

<div class="card">
  <h3>⑥ 孤立发票 &amp; 审计元数据</h3>
  {_orphaned_rows_html(rep["orphaned_invoices"])}
  <div class="meta" style="margin-top:8px">已写入平台 audit（scenario=FI2，L3，append-only，金额脱敏——仅留差异比例）</div>
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

        audit = AuditLogger.jsonl(audit_path)
        try:
            rep = _run_fi2(
                data_source, csv_dir=csv_dir, evaluator=evaluator, period=period,
                audit=audit, u9c_connector=u9c_connector,
                ap_doc_nos=ap_doc_nos, ap_supplier_codes=ap_supplier_codes,
            )
        except Exception as exc:  # noqa: BLE001 —— 引擎异常（含 fail-loud）需如实回显，而非空白 500
            return Response(
                _error_page(f"对账失败：{exc}\n\n{traceback.format_exc()}"), mimetype="text/html"
            ), 500

        return Response(_report_page(rep), mimetype="text/html")

    return app
