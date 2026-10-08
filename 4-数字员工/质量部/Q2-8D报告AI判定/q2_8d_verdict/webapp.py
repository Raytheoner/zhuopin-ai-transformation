"""Q2 门户页 —— `/quality/q2`（队列 §一 `#612` tasks 5.1；档 3，照 FI3 `/finance/fi3` 样板）。

🔴 **不新起端口、走 `.51:8090` 统一门户网关反代**（design D7 原判，本页与 FI3 不同——FI3 因
`#615` 现场改判过渡期独立端口，本页未获同等改判，仍按原纪律不新起端口）。本模块不持有端口，
监听地址由 `scripts/run_q2_web.py` 读 `Q2_WEB_HOST`／`Q2_WEB_PORT`，默认只绑 `127.0.0.1`。

🔴 **本页只展示档 1 mock 汇总**（七维 D1–D7 得分／满分、A/B/C/D 分级分布、处置建议分布；
`#612` 派工边界）：数据固定来自 `feed_source.load_mock()`，页面首屏显著标注「mock 数据」，
不得让人误以为是真实 8D 评审结论（同 FI3 `webapp.py` 引用的 2026-07 `:8092` 静态原型虚构占位
数据误导专员那次教训）。档 2 真实数据接线（QD-A 解析）不在本页职责内。

🔴 **网关 auth 接入点只预留、不实现**（`#612` 派工边界）：`default_identity_resolver()` 读
`X-Zp-Identity` 请求头（统一门户网关下发身份的既定约定，同 `fi3/sc2 webapp.py` 同名接入点），
网关未接管时恒返回 `None`，本页不因此拒绝展示（只读档 1 mock 页，无需身份即可看）。门禁走
`install_flask_gate` 的**共享口令** `ZP_GATE_PASSWORD`（`#160`，与 SC8／QD-B／FI2／FI3／SC2
同一个口令，成员不必记第二个），未配置即不装门禁（本机跑与测试因此无需改动）。🔴 口令值只在
`.51` 的 `.env`，不入库、不打印、不进日志——本页 5.2 `.51` 部署不在本批（`#612` 明令不做）。
"""
from __future__ import annotations

import html as _html
from pathlib import Path

from flask import Blueprint, Flask, Response, request

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.simple_gate import install_flask_gate

from . import config, dashboard, feed_source
from .engine import VerdictEngine

#: 统一门户网关落地后，身份由网关经该请求头下发（同 `fi3/sc2 webapp.py` GATEWAY_IDENTITY_HEADER）。
#: **过渡期无人下发，值恒为空**——本页只读展示档 1 mock 汇总，不因身份未知而拒绝渲染。
GATEWAY_IDENTITY_HEADER = "X-Zp-Identity"


def default_identity_resolver() -> str | None:
    """网关鉴权接入点（预留空壳）。

    接入点须存在，即便过渡期不起作用：网关落地时只替换本函数，页面代码一行不动。
    """
    return request.headers.get(GATEWAY_IDENTITY_HEADER) or None


_Q2_UI_CSS = """
* { box-sizing: border-box; }
body { margin: 0; background: #f5f8fc; color: #18253b;
  font: 14px/1.6 'Microsoft YaHei','PingFang SC','Segoe UI',sans-serif; }
main { max-width: 1364px; margin: auto; padding: 24px 38px 40px; }
h1 { font-size: 28px; margin: 12px 0; }
h2 { font-size: 18px; margin: 0 0 12px; }
a { color: #1677ff; }
.portal-link { display: inline-flex; align-items: center; min-height: 44px; }
.banner, .card, .report-detail { background: #ffffff; border: 1px solid #e7edf5;
  border-radius: 10px; padding: 20px; margin-bottom: 20px; }
.banner { border-left: 4px solid #1677ff; }
.metadata { color: #63738b; font-size: 12px; }
table { width: 100%; border-collapse: collapse; margin: 8px 0; }
caption { text-align: left; font-weight: 600; font-size: 18px; margin-bottom: 8px; }
th, td { text-align: left; vertical-align: top; padding: 8px 12px;
  border-bottom: 1px solid #e7edf5; }
summary { cursor: pointer; min-height: 44px; padding: 8px 4px; font-weight: 600; }
dl { margin: 12px 0; }
dt { color: #63738b; }
dd { margin: 0 0 8px; }
pre { white-space: pre-wrap; margin: 0; }
:focus-visible { outline: 3px solid #1677ff; outline-offset: 3px; }
.overview-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px; }
.overview-grid > :last-child { grid-column: 1 / -1; }
.overview-grid > *, section, header, details { min-width: 0; }
.table-scroll { max-width: 100%; overflow-x: auto; margin-bottom: 20px; }
.table-scroll table { min-width: 420px; }
.report-detail .table-scroll table { min-width: 760px; }
h1, h2, p, li, summary, dd, caption, td, th, pre, a { overflow-wrap: anywhere; }
pre { max-width: 100%; }
@media (max-width: 700px) {
  main { padding: 16px 17px 24px; }
  h1 { font-size: 25px; }
  .overview-grid { grid-template-columns: 1fr; gap: 12px; }
  .banner, .card, .report-detail { padding: 16px; border-radius: 8px; }
  .metadata { font-size: 11px; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important;
    scroll-behavior: auto !important; }
}
"""


def _text(value, missing="未提供") -> str:
    if value is None or (isinstance(value, str) and not value.strip()):
        value = missing
    return _html.escape(str(value), quote=True)


def _items(values, empty) -> str:
    return "<ul>" + ("".join(f"<li>{_text(value)}</li>" for value in values)
                     or f"<li>{_text(empty)}</li>") + "</ul>"


def _table(caption, headers, rows) -> str:
    head = "".join(f'<th scope="col">{_text(value)}</th>' for value in headers)
    body = "".join("<tr>" + "".join(f"<td>{_text(value, '')}</td>" for value in row)
                   + "</tr>" for row in rows)
    if not body:
        body = f'<tr><td colspan="{len(headers)}">本批无此类记录</td></tr>'
    return (f'<div class="table-scroll" role="region" tabindex="0" aria-label="{_text(caption)}">'
            f'<table><caption>{_text(caption)}</caption><thead><tr>{head}</tr>'
            f'</thead><tbody>{body}</tbody></table></div>')


def _report_detail(verdict, position: int) -> str:
    if verdict.grade is not None:
        grade = _text(verdict.grade)
    elif all(verdict.grade_range):
        grade = f"{_text(verdict.grade_range[0])} → {_text(verdict.grade_range[1])}（待人工）"
    else:
        grade = "等级范围未提供（待人工）"
    fields = (
        ("场景", _text(verdict.scene)), ("分级", grade),
        ("已自动判定得分", _text(verdict.score_auto)),
        ("可能得分上界", _text(verdict.score_upper)),
        ("待人工部分满分", _text(verdict.score_pending_max)),
        ("适用满分", _text(verdict.score_max)),
        ("处置建议", _text(verdict.disposition.value)),
        ("需要人工复核", "是" if verdict.needs_manual_review else "否"),
        ("自动化等级", _text(verdict.automation_level)),
    )
    metadata = "".join(f"<dt>{name}</dt><dd>{value}</dd>" for name, value in fields)
    rules = _table("逐规则依据", ("规则", "步骤", "维度", "判定方法", "状态", "得分", "满分", "依据"), [
        (r.rule_id, r.step, r.dimension, r.judge_method, r.status.value, r.score, r.max_score,
         r.evidence if r.evidence.strip() else "依据未提供") for r in verdict.rules
    ])
    redlines = _table("逐红线依据", ("红线", "步骤", "说明", "状态", "依据"), [
        (r.redline_no, r.step, r.description, r.status.value,
         r.evidence if r.evidence.strip() else "依据未提供") for r in verdict.redlines
    ])
    structural = "原结果：结构性退回" if verdict.structural_return else "原结果：未标结构性退回"
    return f'''<details class="report-detail" id="q2-report-{position}">
<summary id="q2-report-summary-{position}">报告{position} · {_text(verdict.report_id)}</summary>
<p>档1 · mock合成数据；AI建议；人工复核责任：质量工程师；此页不提交退回/签发。</p>
<dl>{metadata}</dl><p>可能得分上界不是最终评分。</p>
<h2>结构与场景</h2><p>{structural}</p>
{_items(verdict.structural_empty_sections, '本报告未列结构缺段')}
<h2>场景标记</h2>{_items(verdict.scene_flags, '场景标记未提供')}
{redlines}{rules}<h2>原备注</h2>{_items(verdict.notes, '备注未提供')}
<p class="metadata">原报告入口未接入，请沿既有质量流程核对原件。
单份审计标识未接入；复核人及签认时间未提供。</p></details>'''


def _render_page(verdicts: list) -> str:
    summary = dashboard.summarize(verdicts)
    markdown = dashboard.render_markdown(
        verdicts, rule_version=config.RULE_VERSION, automation_level=config.AUTOMATION_LEVEL,
    )
    steps = _table("七维得分（已自动判定部分）", ("维度", "自动得分", "适用满分之和", "说明"), [
        (step, value["auto"], value["max"], "本批无可计分项" if value["max"] == 0 else "")
        for step, value in summary["by_step"].items()
    ])
    grades = _table("分级分布", ("分级", "份数"), list(summary["by_grade"].items()))
    dispositions = _table("处置建议分布", ("建议", "份数"), list(summary["by_disposition"].items()))
    structural = _table("结构性退回清单", ("报告", "缺段"), [
        (row["report_id"], "、".join(row["empty_sections"])) for row in summary["structural_returns"]
    ])
    redlines = _table("需关注的红线记录", ("报告", "红线", "原状态"), [
        (row["report_id"], row["redline_no"], row["status"]) for row in summary["redline_hits"]
    ])
    reports = "".join(_report_detail(v, i) for i, v in enumerate(verdicts, 1))
    empty = "<p>暂无报告结果</p>" if not verdicts else ""
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_text(config.SERVICE_NAME)}（档1 · mock）</title>
<style>{_Q2_UI_CSS}</style></head><body><main>
<header><a class="portal-link" href="http://192.168.100.51:8092/">返回智能门户</a>
<h1>{_text(config.SERVICE_NAME)}</h1>
<div class="banner"><strong>档1 · mock合成数据；非真实8D评审结论</strong>
<p>AI建议由质量工程师复核；退回决定永远由质量工程师签发；此页不提交退回/签发。</p>
<p class="metadata">规则版本：{_text(config.RULE_VERSION)}；自动化等级：{_text(config.AUTOMATION_LEVEL)}。</p>
<p class="metadata">源数据更新时间未提供；单份审计标识未接入；原报告入口未接入。</p></div></header>
<section class="card"><h2>判定汇总</h2><p>报告数：{summary['total']}</p>{empty}
<p>七维满分是本批适用规则满分之和；不表示每维100分或单份平均分。</p>
<div class="overview-grid">{steps}{grades}{dispositions}</div>{structural}{redlines}
<p>需关注红线含疑似、抽取未命中及本批不验收，原状态逐条展示。</p></section>
<section aria-labelledby="report-heading"><h2 id="report-heading">逐报告结果与依据</h2>{reports}{empty}</section>
<section class="card"><h2>原Markdown清单</h2><pre>{_html.escape(markdown, quote=True)}</pre></section>
</main></body></html>'''


def create_app(*, identity_resolver=None, audit_path: Path | str = "reports/q2_web_audit.jsonl") -> Flask:
    """组装 Flask app（依赖注入 `identity_resolver`／`audit_path`，便于测试）。"""
    app = Flask(__name__)
    # 共享口令门禁（#160）：env_var 取 install_flask_gate 默认值 ZP_GATE_PASSWORD，不再另设场景键。
    install_flask_gate(app, service_name=config.SERVICE_NAME,
                       exempt_paths=(f"{config.ROUTE_PREFIX}/api/ping",))

    resolve_identity = identity_resolver or default_identity_resolver
    audit_logger = AuditLogger.jsonl(audit_path)
    engine = VerdictEngine(audit=audit_logger)
    bp = Blueprint("q2_portal", __name__, url_prefix=config.ROUTE_PREFIX)

    @bp.route("/api/ping")
    def _ping():
        return {"status": "ok", "service": config.SERVICE_NAME}

    @bp.route("/")
    def _index():
        resolve_identity()  # 接入点已挂；过渡期恒 None，不阻断只读 mock 展示
        verdicts = [engine.evaluate(doc) for doc, _ in feed_source.load_mock()]
        return Response(_render_page(verdicts), mimetype="text/html")

    app.register_blueprint(bp)
    return app
