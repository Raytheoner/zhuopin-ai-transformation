"""QD-B 立项审核门禁 —— 内网 Web 服务（极简版发布收口，任务 9.1）。

流程：部门/PMO 把立项申请书 Excel（EQQR8082 A2.1）上传 → `evaluate()` 跑
解析→A/B/C 类规则→评分→报告聚合全链 → 页面直接呈现六段式《立项审核报告》。
**如实标注**：B 类语义判定/C 类转人工规则均是 MVP 占位版，报告如实写"转人工"；
④跨模块校验段如实标注"C01-C10 任务4未实现"，不伪装已判定（红线，见开场
prompt §4）。

红线（不得放宽）：
- 报告=审核建议，立项决定在评审委员会/PMO；AI 不自动执行任何业务动作。
- 真实立项书（未脱敏）留 LAN 不入库；上传文件落 `reports/uploads/`（gitignore）。
- 全链写平台 `audit`（IATF 8.3 可追溯）。
- 仅 LAN 访问（无登录鉴权，同 SC8/命令中心惯例）；灰度期标注"试用版"。
"""
from __future__ import annotations

import html
import time
import traceback
from pathlib import Path

from flask import Flask, Response, request

from .evaluate import EvaluationResult, evaluate
from .models import RuleResult, Verdict

ALLOWED_EXTENSIONS = {".xlsx"}
MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20MB —— 华丰样本含嵌入图片约 2.3MB，留足余量

_PAGE_HEAD = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>QD-B 立项审核门禁 · 试用版</title>
<style>
  body{font-family:-apple-system,"Segoe UI",'Microsoft YaHei',sans-serif;background:#0f172a;color:#e2e8f0;
       max-width:920px;margin:0 auto;padding:24px 20px 60px}
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


def _report_page(result: EvaluationResult) -> str:
    rep = result.report
    sr = rep.score_result
    head = "❌ 一票否决" if sr.veto else f"得分 {sr.total_score:.2f}"
    provisional = ""
    if sr.provisional:
        provisional = f'<div class="note">⚠ 暂定：{sr.pending} 条 A 类规则未实现（视为通过），全量实现后复核</div>'

    return _PAGE_HEAD + f"""
<h1>《立项审核报告》<span class="badge">试用版·灰度</span></h1>
<div class="sub">样本：{html.escape(rep.sample_id or '(未命名)')} ｜ 模板版本={html.escape(rep.template_version)}
 ｜ 规则版本={html.escape(rep.rule_version)} ｜ 项目类型={html.escape(rep.project_type or '未识别')}</div>
<div class="disclaimer">{html.escape(rep.disclaimer)}</div>

<div class="card">
  <h3>① 总判定</h3>
  <div class="verdict {_verdict_class(rep.verdict)}">{html.escape(rep.verdict)}（{html.escape(head)}）</div>
  {provisional}
</div>

<div class="card">
  <h3>② 阻断项清单（{len(rep.blocking_items)} 条）</h3>
  {_items_html(rep.blocking_items)}
</div>

<div class="card">
  <h3>③ 警告/提示清单（{len(rep.warning_items)} 条）</h3>
  {_items_html(rep.warning_items)}
</div>

<div class="card">
  <h3>④ 跨模块校验结果</h3>
  <div class="cross">{html.escape(rep.cross_module_note)}</div>
</div>

<div class="card">
  <h3>⑤ 转人工待办项（{len(rep.manual_todo_items)} 条）</h3>
  {_items_html(rep.manual_todo_items)}
</div>

<div class="card">
  <h3>⑥ 审计元数据</h3>
  <div class="meta">content_hash={html.escape(result.audit_event.content_hash[:16])}… ｜ 已写入平台 audit（scenario=QD-B，L2，append-only）</div>
</div>

<a href="/">‹ 上传下一份</a>
""" + _PAGE_FOOT


def create_app(*, upload_dir: Path, audit_path: Path) -> Flask:
    """构建 Flask app。upload_dir/audit_path 由调用方传入（通常是 reports/，gitignore）。"""
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
    upload_dir.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    @app.get("/api/ping")
    def ping():
        return {"status": "ok", "service": "QD-B 立项审核门禁"}

    @app.get("/")
    def index():
        return Response(_PAGE_HEAD + _INDEX_BODY + _PAGE_FOOT, mimetype="text/html")

    @app.post("/evaluate")
    def do_evaluate():
        f = request.files.get("proposal")
        if f is None or not f.filename:
            return Response(_error_page("请选择一份立项申请书 Excel 文件（.xlsx）"), mimetype="text/html"), 400
        suffix = Path(f.filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            return Response(
                _error_page(f"仅支持 .xlsx 文件，收到：{suffix or '(无扩展名)'}"), mimetype="text/html"
            ), 400

        ts = time.strftime("%Y%m%d-%H%M%S")
        saved_path = upload_dir / f"{ts}_{Path(f.filename).name}"
        f.save(saved_path)

        try:
            result = evaluate(
                saved_path,
                evaluator="AI预审(Web-试用版)",
                audit_path=audit_path,
                sample_id=Path(f.filename).stem,
            )
        except Exception as exc:  # noqa: BLE001 —— 解析/规则异常需如实呈现给用户，而非 500 空白页
            return Response(
                _error_page(f"评估失败：{exc}\n\n{traceback.format_exc()}"), mimetype="text/html"
            ), 500

        return Response(_report_page(result), mimetype="text/html")

    return app
