"""QD-B 立项审核门禁 —— 内网 Web 服务（极简版发布收口，任务 9.1；陈忱灰度反馈#116 重排）。

流程：部门/PMO 把立项申请书 Excel（EQQR8082 A2.1）上传 → `evaluate()` 跑
解析→A/B/C 类规则→评分→报告聚合全链 → 页面呈现重排后的《立项审核报告》
（总分+扣分小计/13模块得分率/扣分明细/全量明细双筛选/改进建议/跨模块/转人工/审计），
并提供 Excel 评分表下载（评审汇总/评审明细/扣分明细 3 sheet）。
**如实标注**：B 类语义判定/C 类转人工规则均是 MVP 占位版，报告如实写"转人工"；
④跨模块校验段如实标注"C01-C10 任务4未实现"，不伪装已判定（红线，见开场
prompt §4）。

红线（不得放宽）：
- 报告=审核建议，立项决定在评审委员会/PMO；AI 不自动执行任何业务动作。
- 真实立项书（未脱敏）留 LAN 不入库；上传文件落 `reports/uploads/`（gitignore）。
- 全链写平台 `audit`（IATF 8.3 可追溯）。
- 仅 LAN 访问（无登录鉴权，同 SC8/命令中心惯例）；灰度期标注"试用版"。
- 展示层重排（陈忱#116 反馈）不改 80 条权重表/扣分判据——逐项标准分/实得分/扣分
  全部复用 report_items.py 的既有公式，见该模块顶部说明。
"""
from __future__ import annotations

import html
import re
import time
import traceback
from pathlib import Path
from urllib.parse import quote

from flask import Flask, Response, request, send_from_directory

from zhuopin_platform.shared_tools.access_log import install_flask_access_log
from zhuopin_platform.shared_tools.simple_gate import install_flask_gate

from .evaluate import EvaluationResult, evaluate
from .models import RuleResult, Verdict
from .report_items import (
    ModuleRateRow,
    ScoredItem,
    build_basic_info,
    build_financial_summary,
    build_module_rates,
    build_scored_items,
    deduction_items,
    deduction_subtotals,
    module_order,
)
from .rules.registry import load_registry
from .xlsx_report import build_workbook, report_filename

ALLOWED_EXTENSIONS = {".xlsx"}
MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20MB —— 华丰样本含嵌入图片约 2.3MB，留足余量

# 队列 #108②（外部第二次交叉审核采纳项）：上传文件名此前只用 `Path(f.filename).name`
# 去掉路径部分，未过滤控制字符/Windows 保留字符。werkzeug 自带的 secure_filename 会把
# 非 ASCII 字符整体丢弃（中文文件名会变成空串），不适用——立项书文件名多为中文项目名，
# 需要保留可读性。改为自写的类 secure_filename 过滤：只滤路径分隔符/控制字符/
# Windows 非法字符，中文/常规标点原样保留。
_UNSAFE_FILENAME_CHARS = re.compile(r'[\x00-\x1f\x7f<>:"/\\|?*]')


def _secure_filename(filename: str) -> str:
    name = Path(filename).name  # 去掉任何路径部分（防路径穿越，如 "../../etc/passwd"）
    name = _UNSAFE_FILENAME_CHARS.sub("_", name)
    name = name.strip(" .")  # Windows 文件名不允许以空格/点收尾
    return name or "upload"

_PAGE_HEAD = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>QD-B 立项审核门禁 · 试用版</title>
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
  .verdict{font-size:26px;font-weight:800;margin:6px 0}
  .v-pass{color:#4ade80}.v-fail{color:#f87171}.v-warn{color:#fbbf24}
  ul{margin:6px 0 0;padding-left:20px}
  li{margin:4px 0;font-size:13px;line-height:1.5}
  .meta{font-size:12px;color:#94a3b8}
  .empty{color:#64748b;font-size:13px}
  form{background:#1e293b;border:1px dashed #475569;border-radius:8px;padding:24px;text-align:center}
  input[type=file]{color:#e2e8f0;margin-bottom:14px}
  button{background:#2563eb;color:#fff;border:0;border-radius:6px;padding:8px 20px;font-size:14px;cursor:pointer}
  button:hover{background:#1d4ed8}
  a{color:#60a5fa}
  .note{font-size:12px;color:#64748b;margin-top:6px}
  .cross{color:#94a3b8;font-style:italic;font-size:13px}

  .hero{display:flex;flex-wrap:wrap;align-items:center;gap:22px}
  .hero .score-big{font-size:42px;font-weight:800;line-height:1}
  .hero .ded{font-size:13px;color:#94a3b8}
  .hero .ded b{color:#f87171}
  .hero .ded b.warn{color:#fbbf24}
  .btn-download{background:#16a34a;color:#fff;border:0;border-radius:6px;padding:10px 18px;font-size:14px;
                font-weight:700;text-decoration:none;display:inline-block;white-space:nowrap}
  .btn-download:hover{background:#15803d}
  .info-grid{display:grid;grid-template-columns:repeat(2,minmax(180px,1fr));gap:4px 20px;font-size:13px;margin-top:14px}
  .info-grid div b{color:#93c5fd;font-weight:600}
  table.grid{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:4px}
  table.grid th{background:#0f172a;color:#93c5fd;text-align:left;padding:6px 8px;border-bottom:1px solid #334155;
                position:sticky;top:0}
  table.grid td{padding:5px 8px;border-bottom:1px solid #263349;vertical-align:top}
  table.grid tr.row-fail td{background:rgba(248,113,113,.08)}
  table.grid tr.row-warn td{background:rgba(251,191,36,.08)}
  .scroll-box{max-height:520px;overflow:auto;border:1px solid #263349;border-radius:6px}
  .tag{display:inline-block;padding:1px 7px;border-radius:10px;font-size:11px;font-weight:700;white-space:nowrap}
  .tag-pass{background:#14532d;color:#4ade80}
  .tag-warn{background:#78350f;color:#fbbf24}
  .tag-fail{background:#7f1d1d;color:#f87171}
  .tag-na{background:#334155;color:#94a3b8}
  .tag-manual{background:#1e3a5f;color:#93c5fd}
  .tag-pending{background:#334155;color:#cbd5e1}
  .rate-bar{background:#334155;border-radius:4px;height:8px;overflow:hidden;width:90px;display:inline-block;
            vertical-align:middle;margin-right:6px}
  .rate-bar i{display:block;height:100%;background:#4ade80}
  .rate-bar.warn i{background:#fbbf24}
  .filters{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin-bottom:10px;font-size:13px}
  .filters select{background:#0f172a;color:#e2e8f0;border:1px solid #334155;border-radius:4px;padding:4px 8px}
  .filters label{display:flex;align-items:center;gap:5px}
  .topbar{display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px}
</style></head><body>
"""
_PAGE_FOOT = "</body></html>"

_INDEX_BODY = """
<h1>QD-B 立项审核门禁<span class="badge">试用版·灰度</span></h1>
<div class="sub">上传立项申请书（EQQR8082 A2.1 模板，.xlsx）→ AI 出预审建议报告</div>
<div class="disclaimer">⚠ 试用版：AI 预审建议，立项决策仍在评审委员会/PMO；不作为正式立项依据。反馈请经企微机器人（陈忱/朱映桦经陈忱转）。</div>
<form action="/evaluate" method="post" enctype="multipart/form-data">
  <input type="file" name="proposal" accept=".xlsx" required><br>
  <button type="submit">上传并生成审核报告</button>
  <div class="note">仅支持开发类 EQQR8082 A2.1 模板；文件不会被提交入代码库，仅落本机 LAN。</div>
</form>
"""

_FILTER_JS = """
<script>
function qdbFilter(){
  var m=document.getElementById('flt-module'), s=document.getElementById('flt-status'), p=document.getElementById('flt-problem');
  if(!m) return;
  var mv=m.value, sv=s.value, pv=p.checked;
  document.querySelectorAll('#detail-table tbody tr').forEach(function(tr){
    var okM = !mv || tr.dataset.module===mv;
    var okS = !sv || tr.dataset.status===sv;
    var okP = !pv || tr.dataset.problem==='1';
    tr.style.display = (okM && okS && okP) ? '' : 'none';
  });
}
</script>
"""

_TAG_CLASS = {
    Verdict.PASS: "tag-pass", Verdict.NA: "tag-na", Verdict.WARN: "tag-warn",
    Verdict.FAIL: "tag-fail", Verdict.MANUAL: "tag-manual", Verdict.PENDING: "tag-pending",
}
_ROW_CLASS = {Verdict.FAIL: "row-fail", Verdict.WARN: "row-warn"}


def _error_page(message: str) -> str:
    return _PAGE_HEAD + f"""
<h1>QD-B 立项审核门禁</h1>
<div class="card"><h3>⚠ 处理失败</h3><pre style="white-space:pre-wrap;font-size:12px">{html.escape(message)}</pre></div>
<a href="/">‹ 返回重新上传</a>
""" + _PAGE_FOOT


def _verdict_class(verdict: str) -> str:
    if "不合格" in verdict:
        return "v-fail"
    if "合格" in verdict:
        return "v-pass"
    return "v-warn"


def _items_html(items: list[RuleResult]) -> str:
    if not items:
        return '<div class="empty">无</div>'
    lines = []
    for r in items:
        sug = f"｜建议：{html.escape(r.suggestion)}" if r.suggestion else ""
        lines.append(
            f"<li><b>规则{html.escape(r.rule_id)}</b> {html.escape(r.check_item)}："
            f"{html.escape(r.evidence)}{sug}</li>"
        )
    return "<ul>" + "".join(lines) + "</ul>"


def _item_table_rows_html(items: list[ScoredItem]) -> str:
    lines = []
    for it in items:
        row_cls = _ROW_CLASS.get(it.verdict, "")
        tag_cls = _TAG_CLASS.get(it.verdict, "")
        problem = "1" if it.is_problem else "0"
        ded_text = f"-{it.deduction:.2f}" if it.deduction else "0.00"
        lines.append(
            f'<tr class="{row_cls}" data-module="{html.escape(it.module_key)}" '
            f'data-status="{html.escape(it.verdict.value)}" data-problem="{problem}">'
            f'<td>{it.idx}</td><td>{html.escape(it.section)}</td>'
            f'<td>{html.escape(it.check_item)}</td><td>{html.escape(it.pass_condition)}</td>'
            f'<td><span class="tag {tag_cls}">{html.escape(it.status_label)}</span></td>'
            f'<td>{it.std_score:.2f}</td><td>{it.actual_score:.2f}</td>'
            f'<td>{ded_text}</td><td>{html.escape(it.detail_text)}</td></tr>'
        )
    return "".join(lines)


_STATUS_FILTER_OPTIONS = ["通过", "待改进", "不合格", "不适用", "转人工", "未实现"]


def _detail_table_html(items: list[ScoredItem], *, table_id: str,
                       module_options: list[tuple[str, str]] | None = None) -> str:
    filters_html = ""
    if module_options is not None:
        mod_opts = "".join(
            f'<option value="{html.escape(mk)}">{html.escape(sec)}</option>' for mk, sec in module_options
        )
        status_opts = "".join(f'<option value="{s}">{s}</option>' for s in _STATUS_FILTER_OPTIONS)
        filters_html = f"""
<div class="filters">
  <label>模块：<select id="flt-module" onchange="qdbFilter()"><option value="">全部</option>{mod_opts}</select></label>
  <label>状态：<select id="flt-status" onchange="qdbFilter()"><option value="">全部</option>{status_opts}</select></label>
  <label><input type="checkbox" id="flt-problem" onchange="qdbFilter()"> 仅看问题项</label>
</div>
"""
    rows = _item_table_rows_html(items)
    return f"""{filters_html}
<div class="scroll-box">
<table class="grid" id="{table_id}">
<thead><tr><th>序号</th><th>所属模块</th><th>检查项</th><th>评审标准</th><th>状态</th><th>标准分</th><th>实得</th><th>扣分</th><th>详情</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</div>
"""


def _module_rate_table_html(rates: list[ModuleRateRow]) -> str:
    rows = []
    for r in rates:
        bar_cls = "" if r.all_pass else "warn"
        status = "✅ 通过" if r.all_pass else "⚠️ 待改进"
        pct = max(0.0, min(100.0, r.rate_pct))
        rows.append(
            f'<tr><td>{html.escape(r.section)}</td>'
            f'<td><span class="rate-bar {bar_cls}"><i style="width:{pct:.0f}%"></i></span>{r.rate_pct:.1f}%</td>'
            f'<td>{status}</td></tr>'
        )
    return (
        '<table class="grid"><thead><tr><th>模块</th><th>得分率</th><th>状态</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


def _info_grid_html(info: dict[str, str], fin: dict[str, str]) -> str:
    def _rows(d: dict[str, str]) -> str:
        return "".join(f"<div><b>{html.escape(k)}</b>：{html.escape(str(v))}</div>" for k, v in d.items())
    return (
        f'<div class="info-grid">{_rows(info)}</div>'
        f'<div class="info-grid" style="margin-top:10px">{_rows(fin)}</div>'
    )


def _hero_html(verdict: str, score_result, fail_ded: float, warn_ded: float) -> str:
    vcls = _verdict_class(verdict)
    score_text = "❌ 一票否决" if score_result.veto else f'{score_result.total_score:.1f}<span style="font-size:16px">/100</span>'
    return f"""
<div class="hero">
  <div>
    <div class="verdict {vcls}" style="font-size:15px;margin-bottom:2px">{html.escape(verdict)}</div>
    <div class="score-big {vcls}">{score_text}</div>
  </div>
  <div class="ded">
    不合格扣分 <b>-{fail_ded:.1f}</b>　待改进扣分 <b class="warn">-{warn_ded:.1f}</b>
  </div>
</div>
"""


def _report_page(result: EvaluationResult, download_url: str) -> str:
    rep = result.report
    sr = rep.score_result
    reg = load_registry()
    items = build_scored_items(rep, reg)
    rates = build_module_rates(rep, reg)
    ded_rows = deduction_items(items)
    fail_ded, warn_ded = deduction_subtotals(items)
    info = build_basic_info(result.document)
    fin = build_financial_summary(result.document)

    provisional = ""
    if sr.provisional:
        provisional = f'<div class="note">⚠ 暂定：{sr.pending} 条 A 类规则未实现（视为通过），全量实现后复核</div>'

    dedu_section = (
        _detail_table_html(ded_rows, table_id="dedu-table")
        if ded_rows else '<div class="empty">无待改进/不合格项——本次评审零扣分</div>'
    )
    download_btn = (
        f'<a class="btn-download" href="{html.escape(download_url)}">⬇ 下载 Excel 评分表</a>'
        if download_url else '<span class="note">⚠ Excel 导出暂不可用（详见服务日志）</span>'
    )

    return _PAGE_HEAD + f"""
<div class="topbar">
  <div>
    <h1>《立项审核报告》<span class="badge">试用版·灰度</span></h1>
    <div class="sub">样本：{html.escape(rep.sample_id or '(未命名)')} ｜ 模板版本={html.escape(rep.template_version)}
     ｜ 规则版本={html.escape(rep.rule_version)} ｜ 项目类型={html.escape(rep.project_type or '未识别')}</div>
  </div>
  {download_btn}
</div>
<div class="disclaimer">{html.escape(rep.disclaimer)}</div>

<div class="card">
  <h3>① 总判定</h3>
  {_hero_html(rep.verdict, sr, fail_ded, warn_ded)}
  {provisional}
  {_info_grid_html(info, fin)}
</div>

<div class="card">
  <h3>② 各模块得分率一览（13 模块）</h3>
  {_module_rate_table_html(rates)}
</div>

<div class="card">
  <h3>③ 扣分明细（{len(ded_rows)} 条，按扣分从高到低）</h3>
  {dedu_section}
</div>

<div class="card">
  <h3>④ 全量评审明细表（{len(items)} 项）</h3>
  {_detail_table_html(items, table_id="detail-table", module_options=module_order(reg))}
</div>

<div class="card">
  <h3>⑤ 改进建议与行动项</h3>
  {_items_html(rep.blocking_items + rep.warning_items)}
</div>

<div class="card">
  <h3>⑥ 跨模块校验结果</h3>
  <div class="cross">{html.escape(rep.cross_module_note)}</div>
</div>

<div class="card">
  <h3>⑦ 转人工待办项（{len(rep.manual_todo_items)} 条）</h3>
  {_items_html(rep.manual_todo_items)}
</div>

<div class="card">
  <h3>⑧ 审计元数据</h3>
  <div class="meta">content_hash={html.escape(result.audit_event.content_hash[:16])}… ｜ 已写入平台 audit（scenario=QD-B，L2，append-only）</div>
</div>

{_FILTER_JS}
<a href="/">‹ 上传下一份</a>
""" + _PAGE_FOOT


def create_app(*, upload_dir: Path, audit_path: Path, output_dir: Path | None = None,
               access_log_path: Path | str | None = None) -> Flask:
    """构建 Flask app。upload_dir/audit_path/output_dir 由调用方传入（通常是 reports/，gitignore）。

    access_log_path：队列 #112 轻量访问日志落盘路径，None 时不采集（零回归）。
    """
    app = Flask(__name__)
    install_flask_gate(app, service_name="QD-B 立项审核门禁")
    install_flask_access_log(app, service_name="QD-B 立项审核门禁", log_path=access_log_path)
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
    upload_dir.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    out_dir = output_dir or (upload_dir.parent / "xlsx_reports")
    out_dir.mkdir(parents=True, exist_ok=True)

    @app.get("/api/ping")
    def ping():
        return {"status": "ok", "service": "QD-B 立项审核门禁"}

    @app.get("/")
    def index():
        return Response(_PAGE_HEAD + _INDEX_BODY + _PAGE_FOOT, mimetype="text/html")

    @app.get("/download/<path:filename>")
    def download_xlsx(filename: str):
        return send_from_directory(out_dir, filename, as_attachment=True)

    @app.post("/evaluate")
    def do_evaluate():
        f = request.files.get("proposal")
        if f is None or not f.filename:
            return Response(_error_page("请选择一份立项申请书 Excel 文件（.xlsx）"), mimetype="text/html"), 400
        safe_name = _secure_filename(f.filename)
        suffix = Path(safe_name).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            return Response(
                _error_page(f"仅支持 .xlsx 文件，收到：{suffix or '(无扩展名)'}"), mimetype="text/html"
            ), 400

        ts = time.strftime("%Y%m%d-%H%M%S")
        saved_path = upload_dir / f"{ts}_{safe_name}"
        f.save(saved_path)

        try:
            result = evaluate(
                saved_path,
                evaluator="AI预审(Web-试用版)",
                audit_path=audit_path,
                sample_id=Path(safe_name).stem,
            )
        except Exception as exc:  # noqa: BLE001 —— 解析/规则异常需如实呈现给用户，而非 500 空白页
            return Response(
                _error_page(f"评估失败：{exc}\n\n{traceback.format_exc()}"), mimetype="text/html"
            ), 500

        try:
            wb = build_workbook(result)
            xlsx_name = report_filename(result)
            wb.save(out_dir / xlsx_name)
            download_url = f"/download/{quote(xlsx_name)}"
        except Exception:  # noqa: BLE001 —— Excel 导出失败不应挡住网页报告本身
            download_url = ""

        return Response(_report_page(result, download_url), mimetype="text/html")

    return app
