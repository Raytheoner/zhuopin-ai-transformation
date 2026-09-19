"""Q2 门户页 —— `/quality/q2`（队列 §一 `#612` tasks 5.1；档 3，照 FI3 `/finance/fi3` 样板）。

🔴 **`.51` 上走过渡期独立端口 8098**（design D7 原判「不新起端口、走 `.51:8090` 网关反代」；
Shao Peishen 2026-09-19 答 `1a` 改判＝比照 FI3 `#615` 走独立端口过渡形态，网关收编时回收）。
本模块不持有端口，监听地址由 `scripts/run_q2_web.py` 读 `Q2_WEB_HOST`／`Q2_WEB_PORT`，默认只绑
`127.0.0.1`；对外绑定与端口只在 `deploy-server.ps1` 生成的 `start-q2.ps1` 里置。

🔴 **本页只展示档 1 mock 汇总**（七维 D1–D7 得分／满分、A/B/C/D 分级分布、处置建议分布；
`#612` 派工边界）：数据固定来自 `feed_source.load_mock()`，页面首屏显著标注「mock 数据」，
不得让人误以为是真实 8D 评审结论（同 FI3 `webapp.py` 引用的 2026-07 `:8092` 静态原型虚构占位
数据误导专员那次教训）。档 2 真实数据接线（QD-A 解析）不在本页职责内。

🔴 **网关 auth 接入点只预留、不实现**（`#612` 派工边界）：`default_identity_resolver()` 读
`X-Zp-Identity` 请求头（统一门户网关下发身份的既定约定，同 `fi3/sc2 webapp.py` 同名接入点），
网关未接管时恒返回 `None`，本页不因此拒绝展示（只读档 1 mock 页，无需身份即可看）。门禁走
`install_flask_gate` 的**共享口令** `ZP_GATE_PASSWORD`（`#160`，与 SC8／QD-B／FI2／FI3／SC2
同一个口令，成员不必记第二个），未配置即不装门禁（本机跑与测试因此无需改动）。🔴 口令值只在
`.51` 的 `C:/q2/.env`（从同机 FI3 借值，不新设键），不入库、不打印、不进日志。
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


def _render_page(verdicts: list) -> str:
    s = dashboard.summarize(verdicts)
    md = dashboard.render_markdown(verdicts, rule_version=config.RULE_VERSION, automation_level=config.AUTOMATION_LEVEL)
    step_rows = "".join(
        f"<tr><td>{_html.escape(k)}</td><td style='text-align:right'>{v['auto']}</td>"
        f"<td style='text-align:right'>{v['max']}</td></tr>"
        for k, v in s["by_step"].items()
    )
    grade_rows = "".join(
        f"<tr><td>{_html.escape(g)}</td><td style='text-align:right'>{n}</td></tr>"
        for g, n in s["by_grade"].items()
    )
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_html.escape(config.SERVICE_NAME)}（档 1 · mock）</title>
<style>
  body{{font-family:-apple-system,"Segoe UI",'Microsoft YaHei',sans-serif;margin:24px;color:#1e293b}}
  .banner{{background:#fef3c7;border:1px solid #f59e0b;border-radius:6px;padding:10px 14px;margin-bottom:16px}}
  table{{border-collapse:collapse;margin-bottom:20px}}
  td,th{{border:1px solid #cbd5e1;padding:4px 10px}}
  pre{{background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:12px;white-space:pre-wrap}}
</style></head><body>
<h2>{_html.escape(config.SERVICE_NAME)}</h2>
<div class="banner">⚠️ 本页数据为 <b>mock</b>（档 1 mock 验证），并非真实 8D 评审结论，不构成真实
退回决定；退回决定永远由质量工程师签发。规则版本 {_html.escape(config.RULE_VERSION)}，
自动化等级 {_html.escape(config.AUTOMATION_LEVEL)}。</div>
<h3>七维得分（D1–D7）</h3>
<table><tr><th>维度</th><th>自动得分</th><th>满分</th></tr>{step_rows}</table>
<h3>分级分布（A/B/C/D，含语义层待人工区间桶）</h3>
<table><tr><th>分级</th><th>份数</th></tr>{grade_rows}</table>
<pre>{_html.escape(md)}</pre>
</body></html>"""


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
