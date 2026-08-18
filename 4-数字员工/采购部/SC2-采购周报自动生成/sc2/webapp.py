"""交付层 —— Flask 蓝图（spec: sc2-report-delivery）。

🔴 **路由前缀自首版即为目标态 `/procurement/sc2`**（design D2/D9）。页内所有
链接与表单 action 也一律基于该前缀，**不用根路径绝对引用**——否则统一门户网关
落地那天，页面里每一个 `/xxx` 都会指错，本要求存在的意义就是免掉那次返工。

⚠️ **过渡期这是 `.51` 上的第 5 个对外端口**（8095），属对「新场景一律不新起
端口对外」硬约束的**显式豁免**，已获 Shao Peishen 认可；注销条件＝网关落地后
收编。详见场景 CLAUDE.md「部署状态」段。
"""
from __future__ import annotations

import html
from datetime import date

from flask import Blueprint, Flask, jsonify, request

from zhuopin_platform.shared_tools.access_log import install_flask_access_log
from zhuopin_platform.shared_tools.simple_gate import install_flask_gate

from . import config
from .report import (
    build_report,
    load_snapshot,
    render_text,
    save_snapshot,
    snapshot_to_report,
)
from .review import ReviewStore, confirm
from .sources import build_feed
from .windows import build_windows

#: 统一门户网关落地后，身份由网关经该请求头下发。**过渡期无人下发，值为空。**
GATEWAY_IDENTITY_HEADER = "X-Zp-Identity"


def default_identity_resolver() -> str | None:
    """网关鉴权接入点（过渡期空壳）。

    spec 要求该接入点**必须存在**，即便过渡期不起作用：网关落地时只替换本函数，
    业务路由与页面代码一行不动。返回 None 表示「网关未接管，身份未知」。
    """
    return request.headers.get(GATEWAY_IDENTITY_HEADER) or None


def create_app(*, base_date: date | None = None, mode: str = "mock",
               identity_resolver=None, store: ReviewStore | None = None) -> Flask:
    """组装 Flask app（依赖注入，便于测试）。"""
    app = Flask(__name__)
    install_flask_gate(app, service_name=config.SERVICE_NAME)
    install_flask_access_log(app, service_name=config.SERVICE_NAME,
                             log_path=config.access_log_path())

    resolve_identity = identity_resolver or default_identity_resolver
    bp = Blueprint("sc2", __name__, url_prefix=config.ROUTE_PREFIX)

    def _regenerate():
        """真实取数并重算一期周报，落快照。

        ⚠️ **真实模式下这一步很慢**（2026-08-18 实测约 2 分 19 秒：`GR/Query`
        整表 56 次分页 ＋ 窗口内 812 个料号逐个查行级关闭状态）。故它**只在显式
        重算时执行**，页面请求一律走快照——把一次两分钟的取数挂在 HTTP 请求上，
        用户会以为服务挂了。
        """
        base = base_date or date.today()
        windows = build_windows(base)
        report = build_report(build_feed(mode).fetch(windows), windows)
        (store or ReviewStore()).register(report)
        save_snapshot(report)
        return report

    def _current_report():
        """快照优先：有当期快照就渲染快照，没有才真算一次。"""
        base = base_date or date.today()
        period = build_windows(base).current.iso_label()
        try:
            return snapshot_to_report(load_snapshot(period))
        except FileNotFoundError:
            return _regenerate()

    @bp.get("/api/ping")
    def ping():
        return jsonify(ok=True, service=config.SERVICE_NAME, mode=mode)

    @bp.get("/api/report")
    def api_report():
        r = _current_report()
        return jsonify(period=r.period, base_date=r.base_date.isoformat(),
                       mode=r.mode, anomalies=[m.key for m in r.anomalies])

    @bp.get("/")
    def index():
        return _render_page(_current_report())

    @bp.post("/api/refresh")
    def api_refresh():
        """显式全量重算（发布收口冒烟项之一）。真实模式下耗时以分钟计。"""
        report = _regenerate()
        return jsonify(ok=True, period=report.period,
                       anomalies=[m.key for m in report.anomalies])

    @bp.post("/api/confirm")
    def api_confirm():
        report = _current_report()
        (store or ReviewStore()).register(report)
        snapshot = save_snapshot(report)
        payload = request.get_json(silent=True) or {}
        who = (payload.get("confirmed_by") or "").strip() or resolve_identity()
        if not who:
            # 没有主语的确认在 IATF 审核时等于没有确认，故宁可拒绝也不匿名放行。
            return jsonify(ok=False, error="缺少确认人（confirmed_by 或网关身份）"), 400
        confirm(store or ReviewStore(), report.period,
                confirmed_by=who, snapshot_id=snapshot.name)
        return jsonify(ok=True, period=report.period, confirmed_by=who)

    app.register_blueprint(bp)
    return app


_PAGE = """<!doctype html>
<meta charset="utf-8">
<title>采购周报 {period}</title>
<style>
 body{{font-family:system-ui,"Microsoft YaHei",sans-serif;margin:2rem;line-height:1.6}}
 table{{border-collapse:collapse;margin:.5rem 0 1.5rem}}
 th,td{{border:1px solid #d0d7de;padding:.35rem .7rem;text-align:left}}
 th{{background:#f6f8fa}}
 .warn{{color:#9a6700;background:#fff8c5;padding:.5rem .8rem;border-radius:6px}}
 button{{padding:.5rem 1.2rem;font-size:1rem;cursor:pointer}}
 pre{{white-space:pre-wrap}}
</style>
<h1>采购周报 {period}</h1>
<p class="warn">本页数字为 AI 自动汇总，<b>经人工「确认发布」后方可对外推送</b>（L3）。</p>
<pre>{body}</pre>
<form method="post" action="{prefix}/api/confirm">
  <button type="submit">确认发布</button>
</form>
"""


def _render_page(report) -> str:
    return _PAGE.format(period=html.escape(report.period),
                        body=html.escape(render_text(report)),
                        prefix=config.ROUTE_PREFIX)
