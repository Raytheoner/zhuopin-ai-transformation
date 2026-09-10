"""交付层 —— Flask 蓝图（spec: sc2-report-delivery）。

🔴 **路由前缀自首版即为目标态 `/procurement/sc2`**（design D2/D9）。页内所有
链接与表单 action 也一律基于该前缀，**不用根路径绝对引用**——否则统一门户网关
落地那天，页面里每一个 `/xxx` 都会指错，本要求存在的意义就是免掉那次返工。

⚠️ **过渡期这是 `.51` 上的第 7 个对外端口**（8096），属对「新场景一律不新起
端口对外」硬约束的**显式豁免**，已获 Shao Peishen 认可；注销条件＝网关落地后
收编。详见场景 CLAUDE.md「部署状态」段。
"""
from __future__ import annotations

import html
from datetime import date

from flask import Blueprint, Flask, Response, jsonify, request

from zhuopin_platform.shared_tools.access_log import install_flask_access_log
from zhuopin_platform.shared_tools.simple_gate import install_flask_gate

from . import config, detail, outbox
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
               identity_resolver=None, store: ReviewStore | None = None,
               max_status_materials: int | None = None) -> Flask:
    """组装 Flask app（依赖注入，便于测试）。

    `max_status_materials`：行级状态取数的料号上限（D17 的已知代价开关）。
    🔴 **长开服务应传 0（不限）**：默认 200 会在窗口料号更多时截断，未取到状态的
    行按「状态未知」计入在途 ⇒ 在途类指标偏高。截断本身会写进周报取数说明
    （No silent caps），但那是「诚实地报告一个次优数」——真实部署当天实测窗口
    内料号 830 个，按默认值有 630 个拿不到状态。慢的代价由 D21 承担：页面读快照，
    全量重算走独立的 POST /api/refresh。
    """
    app = Flask(__name__)
    # 🔴 免口令路径必须带上路由前缀：`install_flask_gate` 的缺省豁免是裸 `/api/ping`，
    # 而本场景所有路由都在 `/procurement/sc2` 之下 ⇒ 不显式传就没有任何路径命中豁免，
    # 健康检查会被门禁 302 到登录页——部署脚本的 `Start-Zhuopin...CheckHealth` 与
    # 此后任何存活探测都会当场判服务不健康（而服务其实是好的）。
    install_flask_gate(app, service_name=config.SERVICE_NAME,
                       exempt_paths=(f"{config.ROUTE_PREFIX}/api/ping",))
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
        # 🔴 `base_date is None` ＝「跟着今天走」，**每次请求现取**（队列 §一 `#506`）。
        # 长开服务的装配方 `run_sc2._serve_base_date` 必须传 None 才能走到这一支；
        # 它一旦在启动时求值一次并传进来，本行就永远走不到，页面被冻在启动日那一期。
        base = base_date if base_date is not None else date.today()
        windows = build_windows(base)
        dataset = build_feed(mode, max_status_materials).fetch(windows)
        report = build_report(dataset, windows)
        (store or ReviewStore()).register(report)
        save_snapshot(report)
        # 🔴 数据集与周报快照**成对**落盘（§一 `#538`）：周报只存聚合值，展不开到行；
        # 明细导出只读这份落盘数据、绝不现取 ERP——现取的与他手上那份周报不是同一时刻。
        detail.save_dataset(dataset, report.period)
        return report

    def _current_report():
        """快照优先：有当期快照就渲染快照，没有才真算一次。"""
        # 🔴 `base_date is None` ＝「跟着今天走」，**每次请求现取**（队列 §一 `#506`）。
        # 长开服务的装配方 `run_sc2._serve_base_date` 必须传 None 才能走到这一支；
        # 它一旦在启动时求值一次并传进来，本行就永远走不到，页面被冻在启动日那一期。
        base = base_date if base_date is not None else date.today()
        # 期次＝采购口径周序（D22），与 `build_report` 落快照时用的标签一致。
        period = build_windows(base).current.label()
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

    def _detail_context():
        """当期周报 ＋ 其数据集快照 ＋ 三窗口，并**先过对账**再交给任何导出路径。"""
        report = _current_report()
        dataset = detail.load_dataset(report.period)
        windows = detail.windows_of(report)
        counts = detail.reconcile(dataset, windows, report)
        return report, dataset, windows, counts

    @bp.get("/api/detail")
    def api_detail_index():
        """明细导出索引：三节 × 三窗口的「计入行数」＋ 对应周报指标值 ＋ 下载链接。

        `counts` 由 `detail.reconcile` 产出，**它已断言每格与周报指标相等**——索引里两列
        并排给出，是让人一眼看到「明细行数 ＝ 周报数字」这件事有据可查。
        """
        try:
            report, _, _, counts = _detail_context()
        except FileNotFoundError as e:
            return jsonify(ok=False, error=str(e)), 404
        except detail.DetailMismatch as e:
            return jsonify(ok=False, error=str(e)), 500
        metrics = {m.key: m for m in report.metrics}
        sections = {}
        for section, (name, metric_key) in detail.SECTIONS.items():
            sections[section] = {
                "name": name, "metric": metric_key,
                "windows": {
                    slot: {
                        "name": detail.WINDOWS[slot],
                        "rows": counts[section][slot],
                        "reported": getattr(metrics[metric_key], slot).value,
                        "csv": f"{config.ROUTE_PREFIX}/api/detail/{section}.csv?window={slot}",
                    } for slot in detail.WINDOWS
                },
            }
        return jsonify(ok=True, period=report.period, base_date=report.base_date.isoformat(),
                       fetched_at=report.fetched_at, mode=report.mode, sections=sections)

    @bp.get("/api/detail/<section>.csv")
    def api_detail_csv(section: str):
        """某节某窗口的逐行明细 CSV（UTF-8 BOM，Excel 直接打开）。

        🔴 **对账不过即 500、不给文件**：一份行数与周报不一致的明细比没有明细更坏——
        他会把差的那几行当成 ERP 取数差异去追，而其实是我方两处口径分了叉。
        """
        slot = request.args.get("window", "current")
        if section not in detail.SECTIONS or slot not in detail.WINDOWS:
            return jsonify(ok=False, error=f"未知明细节或窗口：{section}/{slot}"), 404
        try:
            report, dataset, windows, _ = _detail_context()
        except FileNotFoundError as e:
            return jsonify(ok=False, error=str(e)), 404
        except detail.DetailMismatch as e:
            return jsonify(ok=False, error=str(e)), 500
        table = detail.build_table(dataset, windows, section, slot)
        filename = detail.csv_filename(report.period, section, slot)
        return Response(
            detail.render_csv(table), mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition":
                     f"attachment; filename*=UTF-8''{_quote(filename)}"})

    @bp.post("/api/confirm")
    def api_confirm():
        report = _current_report()
        (store or ReviewStore()).register(report)
        snapshot = save_snapshot(report)
        payload = request.get_json(silent=True) or {}
        # 三个来源按优先级取确认人：JSON body → 页面表单 → 网关身份。
        # ⚠️ **表单这一路不是可有可无的**：过渡期没有网关下发身份，页面上那个
        # 「确认发布」按钮提交的就是表单；只认 JSON 时它必然 400，等于页面上唯一的
        # L3 动作是坏的——而部署的全部意义就是让姚祖怡在页面上完成这一步。
        who = ((payload.get("confirmed_by") or request.form.get("confirmed_by") or "")
               .strip() or resolve_identity())
        if not who:
            # 没有主语的确认在 IATF 审核时等于没有确认，故宁可拒绝也不匿名放行。
            if not request.is_json:
                return _render_page(report, error="请先填写确认人姓名，再点「确认发布」"), 400
            return jsonify(ok=False, error="缺少确认人（confirmed_by 或网关身份）"), 400
        confirm(store or ReviewStore(), report.period,
                confirmed_by=who, snapshot_id=snapshot.name)
        if not request.is_json:
            return _render_page(report, confirmed_by=who)
        return jsonify(ok=True, period=report.period, confirmed_by=who)

    app.register_blueprint(bp)
    return app


def _quote(name: str) -> str:
    from urllib.parse import quote
    return quote(name, safe="")


_PAGE = """<!doctype html>
<meta charset="utf-8">
<title>采购周报 {period}</title>
<style>
 body{{font-family:system-ui,"Microsoft YaHei",sans-serif;margin:2rem;line-height:1.6}}
 table{{border-collapse:collapse;margin:.5rem 0 1.5rem}}
 th,td{{border:1px solid #d0d7de;padding:.35rem .7rem;text-align:left}}
 th{{background:#f6f8fa}}
 .warn{{color:#9a6700;background:#fff8c5;padding:.5rem .8rem;border-radius:6px}}
 .ok{{color:#0a5c2e;background:#dafbe1;padding:.5rem .8rem;border-radius:6px}}
 input{{padding:.4rem .6rem;font-size:1rem;margin-right:.6rem}}
 button{{padding:.5rem 1.2rem;font-size:1rem;cursor:pointer}}
 pre{{white-space:pre-wrap}}
</style>
<h1>采购周报 {period}</h1>
<p>期次口径：<b>{period}（采购口径周序）</b>｜ISO 周号对照：{iso_period}</p>
<p class="warn">本页数字为 AI 自动汇总。<b>每周五 20:00 自动生成并自动推送采购部群</b>
（2026-08-22 拍板取消「确认发布」前置）。下方签认按钮仍可用，但它现在记录的是
<b>事后复核</b>，不再是推送的前置条件。</p>
<pre>{body}</pre>
<p>{detail_links}</p>
{notice}
<p>{backlog}</p>
<form method="post" action="{prefix}/api/confirm">
  <label>复核人姓名：<input name="confirmed_by" required autocomplete="name"></label>
  <button type="submit">确认发布</button>
</form>
"""


def _backlog_text() -> str:
    """outbox 积压提示。

    🔴 **页面必须说出「还没真的发出去」**：写进 outbox 只代表交给了中继，真实送达
    取决于笔记本侧中继是否在跑。不把积压摆到人眼前，就会重演 `#82` 那个形态——
    机制天天在跑、一条都没发出去，而没有任何人察觉。
    """
    n = outbox.pending()
    if n == 0:
        return "推送出口：企微智能机器人（采购部群）｜<b>无积压</b>"
    return (f'<span class="warn">推送出口：企微智能机器人（采购部群）｜'
            f'<b>{n} 条待中继取走</b> —— 尚未真正送达；若长期不降，说明笔记本侧中继没在跑。'
            f"</span>")


def _detail_links_html(report) -> str:
    """页面上的明细导出链接：三节 × 三窗口，全部基于路由前缀（不用根路径绝对引用）。

    🔴 **链接在、文件不一定在**：该期若生成于明细导出上线之前，数据集快照不存在，点开会得到
    404 与一句「请先全量重算」——这是刻意的，不在页面上替他猜「大概有」。
    """
    has_dataset = detail.dataset_path(report.period).exists()
    parts = []
    for section, (name, _) in detail.SECTIONS.items():
        links = "／".join(
            f'<a href="{config.ROUTE_PREFIX}/api/detail/{section}.csv?window={slot}">{wname}</a>'
            for slot, wname in detail.WINDOWS.items())
        parts.append(f"{name}明细：{links}")
    hint = ("" if has_dataset else
            '　<span class="warn">该期尚无数据集快照（生成于明细导出上线之前），'
            "请先点全量重算（POST api/refresh）</span>")
    return ("计算过程明细导出（CSV，每行＝周报行数里的一行；行数与周报不等时拒绝导出）："
            + "｜".join(parts) + hint)


def _render_page(report, *, error: str | None = None,
                 confirmed_by: str | None = None) -> str:
    if error:
        notice = f'<p class="warn">{html.escape(error)}</p>'
    elif confirmed_by:
        notice = f'<p class="ok">已由 {html.escape(confirmed_by)} 复核签认。</p>'
    else:
        notice = ""
    return _PAGE.format(period=html.escape(report.period),
                        iso_period=html.escape(report.iso_period or "—"),
                        body=html.escape(render_text(report)),
                        prefix=config.ROUTE_PREFIX, notice=notice,
                        detail_links=_detail_links_html(report),
                        backlog=_backlog_text())
