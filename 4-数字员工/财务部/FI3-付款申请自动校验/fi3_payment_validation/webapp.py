"""FI3 门户页 —— `/finance/fi3`（design D7；档 3，队列 §一 `#613` 建页、`#615` 上线 `.51:8097`）。

🔴 **对外形态＝过渡期独立端口 8097**（`#615`，Shao Peishen 2026-09-18 答 `a`「现在都是内网，先上
功能，认证完善以后慢慢上」）：与 design D7「不新起端口、走 `.51:8090` 网关反代」相反，属过渡形态，
先例＝SC2 8096。**网关收编（决策件线③）时本端口一并回收**，届时 `/finance/fi3` 的 `required_tier`
与权限映射另判（收编条件见 `5-平台底座/unified-portal-gateway/CLAUDE.md` §6）。本模块不持有端口
——监听地址由 `scripts/run_fi3_web.py` 读 `FI3_WEB_HOST`／`FI3_WEB_PORT`，默认仍只绑 `127.0.0.1`
（本机跑不对外），`.51` 部署由 `deploy-server.ps1` 置 `0.0.0.0`。

🔴 **本页只展示档 1 mock 汇总**（`#613` 边界 ⑶）：数据固定来自 `feed_source.load_context("mock")`，
页面首屏显著标注「mock 数据」，不得让人误以为是真实付款申请（同 2026-07 `:8092` 静态原型
虚构占位数据误导专员那次的教训）。档 2 真实数据接线（U9C 五端点）不在本页职责内。

🔴 **网关 auth 接入点只预留、不实现**（`#613` 边界，"auth 接入点只预留不实现"）：
`default_identity_resolver()` 读 `X-Zp-Identity` 请求头（统一门户网关下发身份的既定约定，同
`sc2/webapp.py` 同名接入点），网关未接管时恒返回 `None`，本页不因此拒绝展示（只读档 1 mock
页，无需身份即可看）。门禁走 `install_flask_gate` 的**共享口令** `ZP_GATE_PASSWORD`（`#160`，与
SC8／QD-B／FI2／SC2 同一个口令，成员不必记第二个；`#615` 由 `FI3_GATE_PASSWORD` 改回共享键），
未配置即不装门禁（本机跑与测试因此无需改动）。🔴 口令值只在 `.51` 的 `.env`，不入库、不打印、
不进日志；`.env` 的读入由 `run_fi3_web.py` 经 `zhuopin_platform.env_anchor` 完成，本模块只读进程环境。
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
    # 共享口令门禁（#160）：env_var 取 install_flask_gate 默认值 ZP_GATE_PASSWORD，不再另设场景键（#615）。
    install_flask_gate(app, service_name=config.SERVICE_NAME,
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
