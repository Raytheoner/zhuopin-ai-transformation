"""FI3 门户页 —— `/finance/fi3`（design D7；档 3，只建页面，不做 `.51` 部署，队列 §一 `#613`）。

🔴 **不新起端口对外**（D7 原文，`#613` 边界 ⑴）：本服务不比照 SC2 8096 那次的「过渡期新端口」
豁免——监听端口默认只绑 `127.0.0.1`（非 `0.0.0.0`），不建 `deploy-server.ps1`／防火墙规则。唯一
被认可的访问路径是 `.51:8090` 统一门户网关反向代理到本进程（收编条件与登记流程见
`5-平台底座/unified-portal-gateway/CLAUDE.md` §6「决策件线③存量收编」，财务域排第一顺位）。

🔴 **本页只展示档 1 mock 汇总**（`#613` 边界 ⑶）：数据固定来自 `feed_source.load_context("mock")`，
页面首屏显著标注「mock 数据」，不得让人误以为是真实付款申请（同 2026-07 `:8092` 静态原型
虚构占位数据误导专员那次的教训）。档 2 真实数据接线（U9C 五端点）不在本页职责内。

🔴 **网关 auth 接入点只预留、不实现**（`#613` 边界，"auth 接入点只预留不实现"）：
`default_identity_resolver()` 读 `X-Zp-Identity` 请求头（统一门户网关下发身份的既定约定，同
`sc2/webapp.py` 同名接入点），网关未接管时恒返回 `None`，本页不因此拒绝展示（只读档 1 mock
页，无需身份即可看）。`install_flask_gate` 用 `FI3_GATE_PASSWORD` 环境变量，未配置即不装门禁
（同 FI2/SC2 惯例），本包不代配、不代联络 IT。
"""
from __future__ import annotations

import html as _html
from datetime import date
from pathlib import Path

from flask import Blueprint, Flask, Response, request

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.simple_gate import install_flask_gate

from . import config, dashboard, feed_source, validation_engine

#: 统一门户网关落地后，身份由网关经该请求头下发（同 `sc2/webapp.py` GATEWAY_IDENTITY_HEADER）。
#: **过渡期无人下发，值恒为空**——本页只读展示档 1 mock 汇总，不因身份未知而拒绝渲染。
GATEWAY_IDENTITY_HEADER = "X-Zp-Identity"


def default_identity_resolver() -> str | None:
    """网关鉴权接入点（过渡期空壳）。

    接入点须存在，即便过渡期不起作用：网关落地时只替换本函数，页面代码一行不动。
    """
    return request.headers.get(GATEWAY_IDENTITY_HEADER) or None


def _render_page(verdicts: list) -> str:
    s = dashboard.summarize(verdicts)
    md = dashboard.render_markdown(verdicts)
    rows = "".join(
        f"<tr><td>{_html.escape(o)}</td><td style='text-align:right'>{n}</td></tr>"
        for o, n in s["by_outcome"].items()
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
<div class="banner">⚠️ 本页数据为 <b>mock</b>（档 1 mock 验证），并非真实付款申请，不构成真实拦截
结论；付款执行永远由人在 U9C／银企系统完成。规则版本 {_html.escape(s['rule_version'])}，
自动化等级 {_html.escape(s['automation_level'])}。</div>
<table><tr><th>结果态</th><th>数量</th></tr>{rows}</table>
<pre>{_html.escape(md)}</pre>
</body></html>"""


def create_app(*, today: date | None = None, identity_resolver=None,
               audit_path: Path | str = "reports/fi3_web_audit.jsonl") -> Flask:
    """组装 Flask app（依赖注入 `identity_resolver`／`audit_path`，便于测试）。"""
    app = Flask(__name__)
    install_flask_gate(app, service_name=config.SERVICE_NAME, env_var="FI3_GATE_PASSWORD",
                       exempt_paths=(f"{config.ROUTE_PREFIX}/api/ping",))

    resolve_identity = identity_resolver or default_identity_resolver
    audit_logger = AuditLogger.jsonl(audit_path)
    bp = Blueprint("fi3_portal", __name__, url_prefix=config.ROUTE_PREFIX)

    @bp.route("/api/ping")
    def _ping():
        return {"status": "ok", "service": config.SERVICE_NAME}

    @bp.route("/")
    def _index():
        resolve_identity()  # 接入点已挂；过渡期恒 None，不阻断只读 mock 展示
        ctx = feed_source.load_context("mock", today=today or date.today(), audit_logger=audit_logger)
        reqs = feed_source.load_payment_requests()
        verdicts = validation_engine.validate_batch(reqs, ctx)
        return Response(_render_page(verdicts), mimetype="text/html")

    app.register_blueprint(bp)
    return app
