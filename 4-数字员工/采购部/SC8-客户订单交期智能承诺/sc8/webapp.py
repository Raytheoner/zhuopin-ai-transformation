"""成品保供预警看板 —— 内网前后台 Web 服务（capability: baoguan-web-service）。

路由：
  GET  /                 看板壳页（壳 + JS 启动 fetch /api/baoguan 渲染，复用 baoguan 的 style/JS）
  GET  /api/ping         健康检查（存活 + 时间）
  GET  /api/baoguan      读缓存快照 JSON（无缓存→空态，不打全量）
  POST /api/refresh      手动触发重算（全局非阻塞锁串行，进行中→返回"刷新进行中"）
  GET  /cases            保供案例处置中心（待处置/超SLA/已关闭）
  GET/POST /cases/<id>   案例详情 + 推进/关闭表单
  GET/POST /cases/new    手动建案
  GET  /cases/<id>/draft 生成催货/协调/对客草稿（对客落闸，仅草稿）

设计：进程内重算（compute_snapshot，无 subprocess）；定时刷新 = 后台守护线程；
刷新串行 = 全局非阻塞 threading.Lock；真延期去重推送经案例账本（D6）。
红线：real fail-loud（保留旧缓存、不以空/假覆盖）；含真实客户名 → LAN-only、无鉴权（外网=待办#10）；
对客闸 CUSTOMER_OUTBOUND_ENABLED 全程 False；所有保供动作写 audit。
"""
from __future__ import annotations

import html as _html
import os
import threading
from datetime import date, datetime

from flask import Flask, jsonify, redirect, request

from . import config
from .alert_dispatch import detect_new_red, dispatch_new_reds
from .baoguan import _HTML_JS, _HTML_STYLE, render_legend
from .baoguan_service import SnapshotStore, compute_snapshot
from .case_draft import generate as generate_draft
from .case_store import NEXT_STATUS, CaseStatus, CaseStore


def create_app(*, snapshot_store: SnapshotStore, case_store: CaseStore,
               audit=None, trace=None, ops_webhook_url: str | None = None,
               fo_status: str | None = "2",
               cache_dir=None, srm_ttl_sec: int = 0) -> Flask:
    """组装 Flask app（依赖注入，便于测试）。

    cache_dir/srm_ttl_sec：firm 承诺缓存目录与有效期（提速立即重算）；缺省关闭。
    """
    app = Flask(__name__)
    app.config["SNAP"] = snapshot_store
    app.config["CASES"] = case_store
    refresh_lock = threading.Lock()

    def _do_refresh() -> dict:
        """执行一次重算（持锁串行）。fail-loud：异常时保留旧缓存、上抛摘要。"""
        snap = compute_snapshot(today=date.today(), status=fo_status,
                                audit=audit, trace=trace,
                                cache_dir=cache_dir, srm_ttl_sec=srm_ttl_sec)
        prev = snapshot_store.get()
        prev = prev if prev.ok else None        # 空态不作为去重基线（首刷全推）
        snapshot_store.set(snap)
        new_reds = detect_new_red(snap, prev)
        pushed = dispatch_new_reds(new_reds, case_store, webhook_url=ops_webhook_url,
                                   audit=audit)
        return {"generated_at": snap.generated_at, "counts": snap.counts,
                "rows": len(snap.rows), "new_reds": len(pushed)}

    def _refresh_serial() -> tuple[bool, dict | str]:
        """非阻塞抢锁刷新。拿不到→(False, '刷新进行中')；成功→(True, 结果)。"""
        if not refresh_lock.acquire(blocking=False):
            return False, "刷新进行中，请稍候（携客云限流，串行执行）"
        try:
            return True, _do_refresh()
        finally:
            refresh_lock.release()

    app.config["_REFRESH"] = _refresh_serial   # 供后台线程/测试复用

    # ── 健康 / 数据 / 刷新 ────────────────────────────────────────────────────
    @app.get("/api/ping")
    def ping():
        return jsonify({"status": "ok", "time": datetime.now().isoformat(timespec="seconds")})

    @app.get("/api/baoguan")
    def api_baoguan():
        snap = snapshot_store.get()
        return jsonify(snap.to_dict())

    @app.post("/api/refresh")
    def api_refresh():
        try:
            ok, payload = _refresh_serial()
        except Exception as e:                  # fail-loud：报错但保留旧缓存
            return jsonify({"ok": False, "error": f"刷新失败：{type(e).__name__}: {e}"[:300]}), 502
        if not ok:
            return jsonify({"ok": False, "busy": True, "msg": payload}), 409
        return jsonify({"ok": True, **payload})

    # ── 看板壳页 ──────────────────────────────────────────────────────────────
    @app.get("/")
    def index():
        return _shell_page()

    # ── 案例处置中心 ──────────────────────────────────────────────────────────
    @app.get("/cases")
    def cases_page():
        show_closed = request.args.get("closed") == "1"
        cases = case_store.get_all_cases(include_closed=show_closed)
        stale_ids = {c.id for c in case_store.get_stale_cases()}
        return _cases_list_html(cases, stale_ids, show_closed)

    @app.route("/cases/new", methods=["GET", "POST"])
    def cases_new():
        if request.method == "POST":
            f = request.form
            item_code = (f.get("item_code") or "").strip()
            fo_id = (f.get("fo_id") or "").strip()
            if not item_code or not fo_id:
                return "<p style='color:#c00'>成品料号与预测订单号必填</p><a href='/cases/new'>返回</a>"
            case_store.create_case(
                item_code=item_code, fo_id=fo_id,
                customer_name=(f.get("customer_name") or "").strip(),
                ship_date=(f.get("ship_date") or "").strip(),
                confirmed_gap_days=int(f.get("confirmed_gap_days") or 0),
                bottleneck_material=(f.get("bottleneck_material") or "").strip(),
                actor=(f.get("actor") or "运维").strip(), manual=True)
            if audit is not None:
                _audit_case(audit, "baoguan_case_manual", item_code, fo_id)
            return redirect("/cases")
        return _case_new_html()

    @app.route("/cases/<int:case_id>", methods=["GET", "POST"])
    def case_detail(case_id: int):
        if request.method == "POST":
            f = request.form
            actor = (f.get("actor") or "运维").strip()
            note = (f.get("note") or "").strip()
            action = f.get("action", "advance")
            new_date = (f.get("new_confirmed_date") or "").strip()
            try:
                if action == "close":
                    case_store.resolve_case(case_id, actor=actor, note=note)
                else:
                    case_store.advance_status(case_id, actor=actor, note=note,
                                              new_confirmed_date=new_date)
            except ValueError as e:
                return f"<p style='color:#c00'>{_html.escape(str(e))}</p><a href='/cases/{case_id}'>返回</a>"
            if audit is not None:
                _audit_case(audit, "baoguan_case_advance", str(case_id), action)
            return redirect(f"/cases/{case_id}")
        case = case_store.get_case(case_id)
        if not case:
            return "<p>案例不存在</p><a href='/cases'>返回</a>", 404
        return _case_detail_html(case, case_store.get_events(case_id))

    @app.get("/cases/<int:case_id>/draft")
    def case_draft_route(case_id: int):
        case = case_store.get_case(case_id)
        if not case:
            return "<p>案例不存在</p><a href='/cases'>返回</a>", 404
        kind = request.args.get("kind", "expedite")
        if kind not in ("expedite", "coordinate", "customer"):
            kind = "expedite"
        result = generate_draft(case, case_store.get_events(case_id), kind=kind)
        case_store.add_note(case_id, actor="系统",
                            note=f"生成{kind}草稿（AI={result.used_ai}，对客闸={result.gated}）")
        return _draft_html(case, result)

    return app


# ── 壳页：复用 baoguan 的 style/JS，DATA 改为 fetch（design D9）────────────────

def _shell_page() -> str:
    """看板壳页：结构+样式+JS，启动时 fetch /api/baoguan 注入 DATA 再渲染。"""
    # 复用静态看板的 JS，但 DATA/META 由 fetch 注入（不嵌入真实数据 → 壳页本身无客户名）
    boot = r"""
var DATA=[],META={today:'',ver:''};
function applySnap(s){
  DATA=(s&&s.rows)||[];META={today:(s&&s.today)||'',ver:(s&&s.param_version)||''};
  var ts=document.getElementById('ts');
  if(ts)ts.textContent=(s&&s.ok)?('最后更新 '+(s.generated_at||'—')):'尚未刷新 —— 点「刷新」或等待定时刷新';
  renderKpis();renderFbtns();render();
}
function loadSnap(){
  fetch('/api/baoguan').then(function(r){return r.json();}).then(applySnap)
   .catch(function(){var c=document.getElementById('cards');if(c)c.innerHTML='<div class="empty">加载失败</div>';});
}
function doRefresh(){
  var b=document.getElementById('recompute');if(b){b.disabled=true;b.textContent='重算中…';}
  fetch('/api/refresh',{method:'POST'}).then(function(r){return r.json().then(function(j){return {s:r.status,j:j};});})
   .then(function(o){
     if(o.s===409){alert(o.j.msg||'重算进行中');}
     else if(!o.j.ok){alert('重算失败：'+(o.j.error||'未知'));}
     loadSnap();
   }).catch(function(){alert('重算请求失败');})
   .finally(function(){if(b){b.disabled=false;b.textContent='⟳ 立即重算';}});
}
"""
    # 复用静态 JS，但要做两处剥离：
    # ① 去掉静态版的内嵌占位符 `const DATA=__DATA__;`/`const META=__META__;`——壳页不内嵌数据，
    #    DATA/META 由 boot 用 var 声明、applySnap 经 fetch 填充；保留这两行会是非法 JS（__DATA__ 未定义）
    #    且与 boot 的声明冲突，导致整段脚本报错、页面停在"加载中…"（务必保留本剥离，有回归测试守护）。
    # ② 去掉静态版结尾的"立即渲染"调用——壳页改由 applySnap 在 fetch 完成后触发渲染。
    js_core = (_HTML_JS
               .replace("const DATA=__DATA__;", "")
               .replace("const META=__META__;", "")
               .replace("renderKpis();renderFbtns();render();", "/* 渲染改由 applySnap 触发 */"))
    js = boot + js_core + r"""
var rb=document.getElementById('refresh');if(rb)rb.addEventListener('click',loadSnap);      // 🔄刷新=只读缓存(秒开)
var rc=document.getElementById('recompute');if(rc)rc.addEventListener('click',doRefresh);  // ⟳立即重算=全量重算(慢)
loadSnap();
setInterval(loadSnap, 120000);   // 前端每 2 分钟回读缓存（不打全量，仅读快照）
"""
    nav = _nav_html("dashboard")
    return (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\"><head><meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>成品保供预警看板 · 服务</title>\n" + _HTML_STYLE + _NAV_CSS + "</head><body>\n"
        + nav + "<div class=\"wrap\">\n"
        + '<div class="head"><div><div class="title">成品保供预警看板</div>\n'
        + '<div class="sub" id="ts">加载中…</div></div>\n'
        + '<div class="badges">'
        + '<button class="btn" id="refresh" type="button" title="读取最新缓存，秒开">🔄 刷新</button>'
        + '<button class="btn" id="recompute" type="button" title="重新向 FO/U9C/携客云全量取数计算，较慢（约1-2分钟），需要最新数据时用">⟳ 立即重算</button>'
        + '<span class="badge">内部保供运维 · 不对客 · LAN</span></div></div>\n'
        + '<div class="kpis" id="kpis"></div>\n'
        + '<div class="toolbar"><div class="fbtns" id="fbtns"></div>\n'
        + '<input class="search" id="q" type="text" placeholder="搜索 料号 / 品名 / 客户 / 瓶颈子件" aria-label="搜索">\n'
        + '<select class="sel" id="sort" aria-label="排序"><option value="gap">按缺口天数</option>'
        + '<option value="ship">按计划出货日</option><option value="id">按料号</option></select>\n'
        + '<select class="sel" id="pageSize" aria-label="每页行数"><option value="10">10 行/页</option>'
        + '<option value="50">50 行/页</option><option value="100">100 行/页</option>'
        + '<option value="200">200 行/页</option></select>\n'
        + '<button class="btn" id="csv" type="button">导出 CSV</button>\n'
        + '<button class="btn" id="xlsx" type="button">导出 Excel</button>\n'
        + '<button class="btn" id="legendBtn" type="button">📖 图例</button></div>\n'
        + '<div class="legend" id="legendPanel">' + render_legend(config.default_params()) + '</div>\n'
        + '<div class="cnt" id="cnt"></div>\n<div class="pager" id="pagerTop"></div>\n'
        + '<div class="cards" id="cards"></div>\n<div class="pager" id="pagerBottom"></div>\n'
        + '<div class="foot">分级只看<b>有确定承诺</b>子件的齐料缺口：🔴 真延期 · 🟠 待催 · 🟡 偏紧 · 🟢 按期。'
        + '🔴 真延期自动建案并推保供运维群，见 <a href="/cases">案例处置中心</a>。本服务 LAN 内部用，不对客。</div>\n'
        + '</div>\n<script>\n' + js + '\n</script></body></html>'
    )


# ── 案例页面 HTML ─────────────────────────────────────────────────────────────

_NAV_CSS = """<style>
.bg-nav{display:flex;align-items:center;gap:18px;background:#23221f;padding:0 22px;height:46px;position:sticky;top:0;z-index:99}
.bg-nav .brand{color:#f1efe8;font-size:15px;font-weight:600}
.bg-nav .brand span{color:#5DCAA5}
.bg-nav a{color:#b4b2a9;font-size:13px;text-decoration:none;padding:5px 12px;border-radius:6px}
.bg-nav a.active,.bg-nav a:hover{background:#3a3833;color:#f1efe8}
.bg-pg{max-width:920px;margin:0 auto;padding:22px}
.bg-card{background:var(--surface,#fff);border:1px solid var(--border,#0002);border-radius:12px;padding:16px 18px;margin-bottom:14px}
.bg-tbl{width:100%;border-collapse:collapse;background:var(--surface,#fff);border-radius:12px;overflow:hidden}
.bg-tbl th{background:var(--surface2,#f1efe8);padding:9px 11px;text-align:left;font-size:12px;color:var(--text2,#5f5e5a)}
.bg-tbl td{padding:9px 11px;border-top:1px solid var(--border,#0001);font-size:13px}
.bg-btn{display:inline-block;padding:7px 15px;border-radius:8px;border:1px solid var(--border,#0002);background:var(--surface,#fff);color:var(--text,#23221f);font-size:13px;cursor:pointer;text-decoration:none}
.bg-btn.primary{background:#23221f;color:#fff;border-color:#23221f}
.bg-btn.danger{background:#A32D2D;color:#fff;border-color:#A32D2D}
.bg-stale{color:#A32D2D;font-weight:600}
.bg-in label{display:block;font-size:12px;color:var(--text2,#5f5e5a);margin:10px 0 3px}
.bg-in input,.bg-in textarea,.bg-in select{width:100%;padding:7px;border:1px solid var(--border,#0003);border-radius:6px;font-size:14px;box-sizing:border-box;background:var(--surface,#fff);color:var(--text,#23221f)}
</style>"""


def _nav_html(active: str) -> str:
    d = "active" if active == "dashboard" else ""
    c = "active" if active == "cases" else ""
    return (f'<nav class="bg-nav"><div class="brand">⚡ 成品<span>保供预警</span></div>'
            f'<a href="/" class="{d}">📊 看板</a>'
            f'<a href="/cases" class="{c}">🚨 案例处置</a></nav>')


def _page(title: str, active: str, body: str) -> str:
    return (f'<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{_html.escape(title)}</title>{_HTML_STYLE}{_NAV_CSS}</head><body>'
            f'{_nav_html(active)}<div class="bg-pg">{body}</div></body></html>')


def _cases_list_html(cases, stale_ids, show_closed: bool) -> str:
    rows = ""
    for c in cases:
        stale = ' <span class="bg-stale">⚠️超SLA</span>' if c.id in stale_ids else ""
        op = 'style="opacity:.5"' if not c.is_open else ""
        link = (f'<a href="/cases/{c.id}">详情/推进</a>' if c.is_open else '已关闭')
        rows += (f'<tr {op}><td><b>{_html.escape(c.case_no)}</b></td>'
                 f'<td>{_html.escape(c.item_code)}</td><td>{_html.escape(c.fo_id)}</td>'
                 f'<td>{_html.escape(c.customer_name[:12])}</td><td>{_html.escape(c.ship_date)}</td>'
                 f'<td style="text-align:right;color:#A32D2D">+{c.confirmed_gap_days}</td>'
                 f'<td>{c.status_label}{stale}</td>'
                 f'<td style="text-align:right">{c.hours_since_update:.0f}h</td><td>{link}</td></tr>')
    open_n = sum(1 for c in cases if c.is_open)
    toggle = ('/cases' if show_closed else '/cases?closed=1')
    toggle_t = ('隐藏已关闭' if show_closed else '显示已关闭')
    body = (f'<h2 style="margin:0 0 4px">🚨 保供案例处置中心</h2>'
            f'<p class="sub">每条 🔴 真延期自动建案，催货→协调→改期/确认→关闭。'
            f'待处置 <b>{open_n}</b> · 超SLA <b class="bg-stale">{len(stale_ids)}</b></p>'
            f'<div style="margin:14px 0;display:flex;gap:10px">'
            f'<a href="/cases/new" class="bg-btn primary">+ 手动建案</a>'
            f'<a href="{toggle}" class="bg-btn">{toggle_t}</a>'
            f'<a href="/" class="bg-btn">← 看板</a></div>'
            f'<table class="bg-tbl"><thead><tr><th>案例号</th><th>成品</th><th>订单</th>'
            f'<th>客户</th><th>计划出货</th><th>确定延期</th><th>状态</th><th>滞留</th><th>操作</th>'
            f'</tr></thead><tbody>{rows or "<tr><td colspan=9 style=text-align:center;padding:28px;color:#888>暂无案例</td></tr>"}</tbody></table>')
    return _page("保供案例处置中心", "cases", body)


def _case_detail_html(case, events) -> str:
    ev = ""
    for e in reversed(events):
        chg = f'{e.from_status} → {e.to_status}' if e.to_status else '—'
        ev += (f'<tr><td style="color:#888;font-size:12px">{_html.escape(e.created_at[:16])}</td>'
               f'<td>{_html.escape(e.actor)}</td><td>{_html.escape(e.action)}</td>'
               f'<td>{_html.escape(chg)}</td><td>{_html.escape(e.note)}</td></tr>')
    form = ""
    if case.is_open:
        nxt = NEXT_STATUS[case.status]
        show_date = nxt in (CaseStatus.RESCHEDULE, CaseStatus.CLOSED)
        date_field = ('<label>供应商新承诺 / 改期后出货日</label>'
                      '<input type="date" name="new_confirmed_date">') if show_date else ""
        form = (f'<div class="bg-card bg-in"><h3 style="margin:0 0 8px">推进处置</h3>'
                f'<form method="POST"><label>操作人</label>'
                f'<input name="actor" placeholder="如：保供小王" required>'
                f'<label>备注</label><textarea name="note" rows="3" placeholder="本次跟进结果…"></textarea>'
                f'{date_field}<div style="display:flex;gap:10px;margin-top:12px">'
                f'<button class="bg-btn primary" name="action" value="advance" type="submit">'
                f'推进 → {STATUS_LABEL_NEXT(case)}</button>'
                f'<button class="bg-btn danger" name="action" value="close" type="submit" '
                f'onclick="return confirm(\'关闭此案例？\')">关闭案例</button>'
                f'<a href="/cases" class="bg-btn">返回</a></div></form></div>')
    drafts = (f'<div style="margin:6px 0 14px;display:flex;gap:8px;flex-wrap:wrap">'
              f'<a class="bg-btn" href="/cases/{case.id}/draft?kind=expedite">📝 催货草稿</a>'
              f'<a class="bg-btn" href="/cases/{case.id}/draft?kind=coordinate">📝 协调草稿</a>'
              f'<a class="bg-btn" href="/cases/{case.id}/draft?kind=customer">📝 对客改期草稿（闸关）</a></div>')
    body = (f'<h2 style="margin:0 0 4px">{_html.escape(case.case_no)}　{case.status_label}</h2>'
            f'<p class="sub">建案 {_html.escape(case.created_at[:16])} · 最后更新 '
            f'{_html.escape(case.updated_at[:16])} · 滞留 {case.hours_since_update:.0f}h</p>'
            f'<div class="bg-card"><b>成品</b> {_html.escape(case.item_code)} · '
            f'<b>订单</b> {_html.escape(case.fo_id)} · <b>客户</b> {_html.escape(case.customer_name)}<br>'
            f'<b>计划出货</b> {_html.escape(case.ship_date)} · '
            f'<b>确定延期</b> <span style="color:#A32D2D">+{case.confirmed_gap_days} 天</span> · '
            f'<b>瓶颈子件</b> {_html.escape(case.bottleneck_material or "—")}'
            f'{(" · <b>新承诺</b> " + _html.escape(case.new_confirmed_date)) if case.new_confirmed_date else ""}</div>'
            f'{drafts}{form}'
            f'<div class="bg-card"><h3 style="margin:0 0 8px">操作历史</h3>'
            f'<table class="bg-tbl"><thead><tr><th>时间</th><th>操作人</th><th>动作</th>'
            f'<th>状态变更</th><th>备注</th></tr></thead>'
            f'<tbody>{ev or "<tr><td colspan=5 style=color:#888>暂无</td></tr>"}</tbody></table></div>')
    return _page(f"{case.case_no} 案例详情", "cases", body)


def STATUS_LABEL_NEXT(case) -> str:
    from .case_store import STATUS_LABEL
    return STATUS_LABEL.get(NEXT_STATUS[case.status], "下一步")


def _case_new_html() -> str:
    body = ('<h2 style="margin:0 0 14px">手动建案</h2>'
            '<div class="bg-card bg-in"><form method="POST">'
            '<label>成品料号 *</label><input name="item_code" required placeholder="如 S02Y.0188">'
            '<label>预测订单号 *</label><input name="fo_id" required placeholder="如 FO2026060001">'
            '<label>客户</label><input name="customer_name">'
            '<label>计划出货日</label><input name="ship_date" type="date">'
            '<label>确定延期天数</label><input name="confirmed_gap_days" type="number" value="0">'
            '<label>瓶颈子件</label><input name="bottleneck_material">'
            '<label>操作人</label><input name="actor" placeholder="运维">'
            '<div style="margin-top:14px;display:flex;gap:10px">'
            '<button class="bg-btn primary" type="submit">建案</button>'
            '<a href="/cases" class="bg-btn">取消</a></div></form></div>')
    return _page("手动建案", "cases", body)


def _draft_html(case, result) -> str:
    badge = ('🤖 AI 生成' if result.used_ai else '📝 模板生成')
    gate_note = ""
    if result.is_customer:
        gate_note = ('<div class="bg-card" style="border-color:#A32D2D">'
                     '⚠️ <b>对客改期草稿</b>：对客外发闸 <code>CUSTOMER_OUTBOUND_ENABLED=False</code> '
                     '全程关闭——本草稿<b>仅供人工复制核对</b>，系统绝不自动外发客户（红线）。</div>')
    body = (f'<h2 style="margin:0 0 4px">📧 {_KIND_CN(result.kind)}草稿　<span class="badge">{badge}</span></h2>'
            f'<p class="sub">{_html.escape(case.case_no)} · {_html.escape(case.item_code)} · '
            f'{_html.escape(case.fo_id)}</p>{gate_note}'
            f'<div class="bg-card"><textarea id="dft" style="width:100%;height:300px;padding:12px;'
            f'border:1px solid var(--border,#0003);border-radius:8px;font-size:14px;line-height:1.7;'
            f'box-sizing:border-box;background:var(--surface,#fff);color:var(--text,#23221f)">'
            f'{_html.escape(result.text)}</textarea>'
            f'<div style="margin-top:10px;display:flex;gap:10px">'
            f'<button class="bg-btn primary" onclick="var t=document.getElementById(\'dft\');t.select();'
            f'navigator.clipboard&&navigator.clipboard.writeText(t.value);">📋 复制</button>'
            f'<a class="bg-btn" href="/cases/{case.id}/draft?kind={result.kind}">🔄 重新生成</a>'
            f'<a class="bg-btn" href="/cases/{case.id}">← 返回案例</a></div></div>')
    return _page(f"{case.case_no} 草稿", "cases", body)


def _KIND_CN(kind: str) -> str:
    return {"expedite": "催货", "coordinate": "协调", "customer": "对客改期"}.get(kind, kind)


def _audit_case(audit, action: str, a: str, b: str) -> None:
    from zhuopin_platform.audit import AuditEvent
    audit.record(AuditEvent(scenario="SC8", action=action, evaluator="operator",
                            automation_level="L2", decision={"k": a, "v": b}))


def start_background_refresh(app: Flask, *, interval_min: int) -> threading.Thread:
    """启动后台守护线程，按 interval_min 周期刷新（与手动共用同一把锁）。"""
    import time

    refresh = app.config["_REFRESH"]

    def _loop():
        while True:
            time.sleep(max(1, interval_min) * 60)
            try:
                refresh()                    # 拿不到锁→静默跳过本轮（返回 busy）
            except Exception:
                pass                         # fail-loud 已在 _do_refresh 内保留旧缓存
    t = threading.Thread(target=_loop, name="baoguan-refresh", daemon=True)
    t.start()
    return t
