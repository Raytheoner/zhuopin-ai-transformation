"""QD-B 立项审核门禁 —— 内网 Web 服务（极简版发布收口，任务 9.1；陈忱灰度反馈#116 重排）。

流程：部门/PMO 把立项申请书 Excel（EQQR8082 A2.1）上传 → `evaluate()` 跑
解析→A/B/C 类规则→评分→报告聚合全链 → 页面呈现重排后的《立项审核报告》
（总分+扣分小计/13模块得分率/扣分明细/全量明细双筛选/改进建议/跨模块/转人工/审计），
并提供 Excel 评分表下载（评审汇总/评审明细/扣分明细 3 sheet）。
**如实标注**：B 类语义判定/C 类转人工规则均是 MVP 占位版，报告如实写"转人工"；
跨模块校验段按 C01–C10 逐条呈现实现状态与判定，未实现项写具体原因（红线，见开场
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
    STATUS_LABELS,
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
from .rules.cross_module import status_label as cross_status_label
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
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QD-B 立项审核门禁 · 试用版</title>
<style>
  /* 批准来源：UI设计评审-2026-10-07/设计变量.json，方向1。独立服务内联子集。 */
  :root{--brand:#1677ff;--action:#126bd9;--text:#18253b;--secondary:#63738b;
        --canvas:#f5f8fc;--surface:#fff;--border:#e7edf5;--risk:#a3433b;--warning:#85621b;--covered:#176b59}
  *{box-sizing:border-box}
  body{font-family:'Microsoft YaHei','PingFang SC','Segoe UI',sans-serif;background:var(--canvas);
       color:var(--text);max-width:1280px;margin:0 auto;padding:32px 38px 60px;font-size:14px;line-height:1.65;
       overflow-wrap:anywhere}
  h1{font-size:28px;line-height:1.35;margin:0 0 8px}
  .badge{display:inline-block;background:#fff2d4;color:var(--warning);font-size:12px;font-weight:700;
         padding:3px 8px;border-radius:6px;vertical-align:middle;margin-left:8px}
  .sub,.meta,.note,.cross{color:var(--secondary)}
  .sub{margin-bottom:20px}.meta,.note{font-size:12px}.note{margin-top:8px}
  .eyebrow{color:var(--action);font-size:12px;font-weight:700;margin-bottom:8px}
  .disclaimer{background:#fff8e9;border:1px solid #f1d9a1;border-left:3px solid var(--warning);
              padding:12px 16px;border-radius:6px;color:var(--warning);margin-bottom:20px}
  .card{background:var(--surface);border:1px solid var(--border);border-radius:10px;
        padding:24px;margin-bottom:20px;min-width:0;scroll-margin-top:24px}
  .card h2,.card h3{margin:0 0 16px;font-size:18px;line-height:1.5}
  .verdict{font-size:26px;font-weight:800;margin:6px 0}
  .v-pass{color:var(--covered)}.v-fail{color:var(--risk)}.v-warn{color:var(--warning)}
  ul{margin:8px 0 0;padding-left:20px}li{margin:10px 0}
  .empty{color:var(--secondary);padding:12px 0}
  form{background:var(--surface);border:1px dashed #a9b9cf;border-radius:10px;padding:32px;max-width:760px}
  .upload-label{display:block;font-size:18px;font-weight:700;margin-bottom:12px}
  input[type=file]{display:block;max-width:100%;margin:0 0 20px;color:var(--text);font:inherit}
  button,.btn-download{background:var(--action);color:#fff;border:0;border-radius:6px;padding:12px 20px;
                      font:inherit;font-weight:700;cursor:pointer;text-decoration:none;display:inline-block}
  button:hover,.btn-download:hover{background:#0f59b7}
  a{color:var(--action)}
  a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,.scroll-box:focus-visible{
    outline:3px solid var(--brand);outline-offset:3px}
  .page-nav{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 20px}
  .page-nav a{display:block;padding:8px 14px;background:var(--surface);border:1px solid var(--border);
              border-radius:6px;text-decoration:none;font-weight:600}
  .page-nav a:hover{background:#eef5ff}
  .hero{display:flex;flex-wrap:wrap;align-items:center;gap:24px;padding:8px 0 20px;border-bottom:1px solid var(--border)}
  .hero .score-big{font-size:42px;font-weight:800;line-height:1.2}
  .hero .ded{color:var(--secondary)}.hero .ded b{color:var(--risk)}.hero .ded b.warn{color:var(--warning)}
  .info-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 24px;margin-top:20px}
  .info-grid div b{font-weight:600}
  table.grid{width:100%;border-collapse:collapse;font-size:14px;margin-top:4px}
  table.grid th{background:var(--canvas);text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);
                position:sticky;top:0;z-index:1}
  table.grid td{padding:10px 12px;border-bottom:1px solid var(--border);vertical-align:top}
  table.grid th{white-space:nowrap}
  table.grid td[data-label="序号"],table.grid td[data-label="标准分"],
  table.grid td[data-label="实得"],table.grid td[data-label="扣分"]{white-space:nowrap}
  table.grid tr.row-fail td{background:#fff5f3}table.grid tr.row-warn td{background:#fffaf0}
  .scroll-box{max-height:560px;overflow:auto;border:1px solid var(--border);border-radius:6px}
  .tag{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;font-weight:700;white-space:nowrap}
  .tag-pass{background:#e8f5ef;color:var(--covered)}.tag-warn{background:#fff2d4;color:var(--warning)}
  .tag-fail{background:#fdebe7;color:var(--risk)}.tag-na,.tag-pending{background:#eef1f6;color:var(--secondary)}
  .tag-manual{background:#e9f2ff;color:var(--action)}
  .rate-bar{background:var(--border);border-radius:4px;height:8px;overflow:hidden;width:90px;display:inline-block;
            vertical-align:middle;margin-right:6px}
  .rate-bar i{display:block;height:100%;background:var(--covered)}.rate-bar.warn i{background:var(--warning)}
  .filters{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:16px}
  .filters select{background:var(--surface);color:var(--text);border:1px solid #a9b9cf;border-radius:6px;
                  padding:8px;max-width:100%;min-width:0;font:inherit}
  .filters label{display:flex;align-items:center;gap:8px;max-width:100%;min-width:0}
  .topbar{display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:16px;margin-bottom:4px}
  .topbar>div{flex:1;min-width:0}
  .sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);border:0}
  .skip-link{position:absolute;top:-100px}.skip-link:focus{top:8px;background:var(--surface);padding:8px;z-index:2}
  @media(max-width:700px){
    body{padding:24px 17px 40px}h1{font-size:25px}.badge{margin-left:0;margin-top:8px}
    .card{padding:16px;border-radius:8px}.info-grid{grid-template-columns:1fr;gap:10px}
    form{padding:20px}.topbar{display:block}.topbar .btn-download{margin-bottom:16px}
    .filters{display:block}.filters label{margin-bottom:12px}.filters select{flex:1;width:0}
    .scroll-box{max-height:none;overflow:visible;border:0}
    table.grid,table.grid tbody,table.grid tr{display:block;width:100%}
    table.grid thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
    table.grid tr{border:1px solid var(--border);border-radius:8px;margin:12px 0;overflow:hidden}
    table.grid td{display:grid;grid-template-columns:5em minmax(0,1fr);gap:12px;padding:8px 12px}
    table.grid td::before{content:attr(data-label);color:var(--secondary);font-size:12px}
    table.grid td:last-child{border-bottom:0}.page-nav a{padding:8px 10px}
  }
</style></head><body>
"""
_PAGE_FOOT = "</body></html>"

_INDEX_BODY = """
<div class="eyebrow">质量部 / 立项预审</div>
<h1>QD-B 立项审核门禁<span class="badge">试用版·灰度</span></h1>
<div class="sub">上传立项申请书（EQQR8082 A2.1 模板，.xlsx）→ AI 出预审建议报告</div>
<div class="disclaimer">⚠ 试用版：AI 预审建议，立项决策仍在评审委员会/PMO；不作为正式立项依据。反馈请经企微机器人（陈忱/朱映桦经陈忱转）。</div>
<form action="/evaluate" method="post" enctype="multipart/form-data">
  <label for="proposal" class="upload-label">选择立项申请书</label>
  <input id="proposal" type="file" name="proposal" accept=".xlsx" required aria-describedby="upload-note">
  <button type="submit">上传并生成审核报告</button>
  <div id="upload-note" class="note">仅支持开发类 EQQR8082 A2.1 模板，.xlsx，最大 20 MB；文件不会被提交入代码库，仅落本机 LAN。</div>
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
    if "有条件合格" in verdict:
        return "v-warn"
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
            f'<li><span class="tag {_TAG_CLASS.get(r.verdict, "")}">{html.escape(r.verdict.value)}</span> '
            f"<b>规则{html.escape(r.rule_id)}</b> {html.escape(r.check_item)}："
            f"{html.escape(r.evidence)}{sug}</li>"
        )
    return "<ul>" + "".join(lines) + "</ul>"


def _cross_module_html(items: list[RuleResult]) -> str:
    """④跨模块校验表：逐条列出 C01–C10 的实现状态与判定。

    此前此处是一行恒定文案"C01–C10 尚未实现"，而其中 4 条其实一直由规则 14/68/59/60
    在核——把已核的说成没核（队列 #340）。故改为逐条呈现，未实现项写具体原因。
    """
    if not items:
        return '<div class="empty">无跨模块校验结果</div>'
    rows = []
    for it in items:
        tag_cls = _TAG_CLASS.get(it.verdict, "")
        row_cls = _ROW_CLASS.get(it.verdict, "")
        label = cross_status_label(it)
        detail = html.escape(it.evidence)
        if it.suggestion:
            detail += f'<div class="note">建议：{html.escape(it.suggestion)}</div>'
        rows.append(
            f'<tr class="{row_cls}"><td data-label="编号">{html.escape(it.rule_id)}</td>'
            f'<td data-label="校验内容">{html.escape(it.check_item)}</td>'
            f'<td data-label="判定"><span class="tag {tag_cls}">{html.escape(label)}</span></td>'
            f'<td data-label="依据"><div>{detail}</div></td></tr>'
        )
    return ('<table class="grid" id="cross-results"><caption class="sr-only">跨模块校验结果</caption>'
            '<thead><tr><th>编号</th><th>校验内容</th><th>判定</th><th>依据</th></tr></thead>'
            '<tbody>' + "".join(rows) + '</tbody></table>')


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
            f'<td data-label="序号">{it.idx}</td><td data-label="所属模块">{html.escape(it.section)}</td>'
            f'<td data-label="检查项">{html.escape(it.check_item)}</td><td data-label="评审标准">{html.escape(it.pass_condition)}</td>'
            f'<td data-label="状态"><span class="tag {tag_cls}">{html.escape(it.status_label)}</span></td>'
            f'<td data-label="标准分">{it.std_score:.2f}</td><td data-label="实得">{it.actual_score:.2f}</td>'
            f'<td data-label="扣分">{ded_text}</td><td data-label="详情"><div>{html.escape(it.detail_text)}</div></td></tr>'
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
<div class="scroll-box" tabindex="0" role="region" aria-label="{'全量评审明细' if module_options is not None else '扣分明细'}">
<table class="grid" id="{table_id}">
<caption class="sr-only">{'全量评审明细' if module_options is not None else '扣分明细'}</caption>
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
            f'<tr><td data-label="模块">{html.escape(r.section)}</td>'
            f'<td data-label="得分率"><div><span class="rate-bar {bar_cls}" aria-hidden="true"><i style="width:{pct:.0f}%"></i></span>{r.rate_pct:.1f}%</div></td>'
            f'<td data-label="状态">{status}</td></tr>'
        )
    return (
        '<table class="grid" id="module-rates"><caption class="sr-only">各模块得分率</caption>'
        '<thead><tr><th>模块</th><th>得分率</th><th>状态</th></tr></thead>'
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
<a class="skip-link" href="#report-summary">跳到预审报告</a>
<div class="eyebrow">质量部 / QD-B 立项预审</div>
<div class="topbar">
  <div>
    <h1>《立项审核报告》<span class="badge">试用版·灰度</span></h1>
    <div class="sub">样本：{html.escape(rep.sample_id or '(未命名)')} ｜ 模板版本={html.escape(rep.template_version)}
     ｜ 规则版本={html.escape(rep.rule_version)} ｜ 项目类型={html.escape(rep.project_type or '未识别')}</div>
  </div>
  {download_btn}
</div>
<div class="disclaimer">{html.escape(rep.disclaimer)}</div>
<nav class="page-nav" aria-label="报告区块">
  <a href="#report-summary">预审报告</a><a href="#report-details">全量明细</a>
  <a href="#rule-evidence">规则与证据</a><a href="#manual-todo">转人工待办</a>
  <a href="#audit-metadata">审计信息</a>
</nav>

<div class="card" id="report-summary">
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

<div class="card" id="report-details">
  <h3>④ 全量评审明细表（{len(items)} 项）</h3>
  {_detail_table_html(items, table_id="detail-table", module_options=module_order(reg))}
</div>

<div class="card">
  <h3>⑤ 改进建议与行动项</h3>
  {_items_html(rep.blocking_items + rep.warning_items)}
</div>

<div class="card" id="rule-evidence">
  <h3>⑥ 跨模块校验结果（C01–C10）</h3>
  <div class="cross">{html.escape(rep.cross_module_note)}</div>
  {_cross_module_html(rep.cross_module_items)}
</div>

<div class="card" id="manual-todo">
  <h3>⑦ 转人工待办项（{len(rep.manual_todo_items)} 条）</h3>
  {_items_html(rep.manual_todo_items)}
</div>

<div class="card" id="audit-metadata">
  <h3>⑧ 审计元数据</h3>
  <div class="info-grid meta">
    <div><b>本次评估时间</b>：{html.escape(result.audit_event.timestamp or '未提供')}</div>
    <div><b>原始资料更新时间</b>：未提供</div>
  </div>
  <div class="note">评估时间为审计事件时间；当前结果未提供来源系统更新时间，无法据此判断资料新鲜度。</div>
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
