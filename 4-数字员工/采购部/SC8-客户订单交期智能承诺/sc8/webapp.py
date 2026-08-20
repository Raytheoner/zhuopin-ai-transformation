"""成品保供预警看板 —— 内网前后台 Web 服务（capability: baoguan-web-service）。

路由：
  GET  /                 看板壳页（壳 + JS 启动 fetch /api/baoguan 渲染，复用 baoguan 的 style/JS）
  GET  /api/ping         健康检查（存活 + 时间）
  GET  /api/baoguan      读缓存快照 JSON（无缓存→空态，不打全量）
  POST /api/refresh      手动触发重算（全局非阻塞锁串行，进行中→返回"刷新进行中"）
  GET  /materials        物料看板（队列 #334）：同一份快照按物料维度重新聚合的只读视图
  GET  /api/materials    物料看板数据 JSON（读同一份快照的 materials 字段，不触发重算）
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
import json as _json
import os
import threading
from datetime import date, datetime

from flask import Flask, jsonify, redirect, request

from zhuopin_platform.shared_tools.access_log import install_flask_access_log
from zhuopin_platform.shared_tools.simple_gate import install_flask_gate

from . import config
from .alert_dispatch import detect_new_red, dispatch_new_reds
from .baoguan import _HTML_JS, _HTML_STYLE, render_legend
from .baoguan_service import SnapshotStore, compute_snapshot
from .case_draft import generate as generate_draft
from .case_review import list_packages, load_package, render_review_page
from .case_store import NEXT_STATUS, CaseStatus, CaseStore
from .feedback_store import JsonlAppendStore
from .material_board import FIELD_GAP as _MAT_FIELD_GAP
from .material_board import STATUS_LABELS as _MAT_STATUS_LABELS


def create_app(*, snapshot_store: SnapshotStore, case_store: CaseStore,
               audit=None, trace=None, ops_webhook_url: str | None = None,
               fo_status: str | None = "2",
               cache_dir=None, srm_ttl_sec: int = 0,
               access_log_path=None,
               feedback_store: JsonlAppendStore | None = None,
               case_review_dir=None,
               case_review_store: JsonlAppendStore | None = None) -> Flask:
    """组装 Flask app（依赖注入，便于测试）。

    cache_dir/srm_ttl_sec：firm 承诺缓存目录与有效期（提速立即重算）；缺省关闭。
    access_log_path：队列 #112 轻量访问日志落盘路径，None 时不采集（零回归）。
    feedback_store：队列 #110 Feature A 看板逐行反馈落盘，None 时反馈接口返回 503。
    case_review_dir/case_review_store：队列 #110 Feature B 判例包网页表单化——分别为
    判例包定义文件所在目录（Cowork 手写 JSON，见 `sc8/case_review.py` 顶部说明）与
    提交落盘存储，任一为 None 时判例包路由返回 503。
    """
    app = Flask(__name__)
    install_flask_gate(app, service_name="成品保供预警看板")
    install_flask_access_log(app, service_name="成品保供预警看板", log_path=access_log_path)
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

    @app.get("/api/materials")
    def api_materials():
        """物料看板数据（队列 #334）——同一份快照的第二种切法，不触发任何重算。

        与 `/api/baoguan` 同一进程、同一端口、同一门禁（CLAUDE.md §5 硬约束：
        新视图不新起端口）。旧格式缓存无 materials 键时取缺省空列表，页面显示
        空态而非报错（design D1）。
        """
        snap = snapshot_store.get()
        return jsonify({"ok": snap.ok, "generated_at": snap.generated_at,
                        "today": snap.today, "note": snap.note,
                        "rows": snap.materials, "meta": snap.materials_meta})

    @app.post("/api/refresh")
    def api_refresh():
        try:
            ok, payload = _refresh_serial()
        except Exception as e:                  # fail-loud：报错但保留旧缓存
            return jsonify({"ok": False, "error": f"刷新失败：{type(e).__name__}: {e}"[:300]}), 502
        if not ok:
            return jsonify({"ok": False, "busy": True, "msg": payload}), 409
        return jsonify({"ok": True, **payload})

    # ── 看板逐行反馈（队列 #110 Feature A：判例确认搬进工具本身）────────────────
    # 红线：只采集标注、不自动改任何判据（改口径仍走判例批改+显式签认）。
    @app.post("/api/baoguan/feedback")
    def api_baoguan_feedback():
        if feedback_store is None:
            return jsonify({"ok": False, "error": "反馈功能未配置"}), 503
        body = request.get_json(silent=True) or {}
        product_id = (body.get("product_id") or "").strip()
        so_id = (body.get("so_id") or "").strip()
        verdict = (body.get("verdict") or "").strip()
        if not product_id or not so_id or verdict not in ("correct", "incorrect"):
            return jsonify({"ok": False, "error": "缺少必填字段（product_id/so_id/verdict）"}), 400
        feedback_store.append({
            "product_id": product_id,
            "so_id": so_id,
            "ship_date": (body.get("ship_date") or "").strip(),
            "verdict": verdict,
            "reason": (body.get("reason") or "").strip(),
            "risk": (body.get("risk") or "").strip(),
        })
        return jsonify({"ok": True})

    # ── 判例包网页表单化（队列 #110 Feature B）──────────────────────────────────
    @app.get("/cases/review")
    def cases_review_list():
        if case_review_dir is None:
            return "<p>判例包功能未配置</p><a href='/'>返回</a>", 503
        submitted_ids = (set(r.get("package_id", "") for r in case_review_store.read_all())
                        if case_review_store is not None else set())
        return _case_review_list_html(list_packages(case_review_dir), submitted_ids)

    @app.route("/cases/review/<package_id>", methods=["GET", "POST"])
    def cases_review_detail(package_id: str):
        if case_review_dir is None or case_review_store is None:
            return "<p>判例包功能未配置</p><a href='/'>返回</a>", 503
        try:
            package = load_package(case_review_dir, package_id)
        except FileNotFoundError:
            return "<p>判例包不存在</p><a href='/cases/review'>返回</a>", 404
        if request.method == "POST":
            f = request.form
            responses = []
            for case in package.cases:
                verdict = f.get(f"verdict_{case.case_no}", "").strip()
                note = f.get(f"note_{case.case_no}", "").strip()
                responses.append({
                    "case_no": case.case_no,
                    "verdict": verdict or None,   # ✅/❌ 独立于 ✏️，允许只填其一
                    "note": note,
                })
            new_issues = [v.strip() for v in f.getlist("new_issue") if v.strip()]
            case_review_store.append({
                "package_id": package_id,
                "respondent": (f.get("respondent") or "").strip(),
                "responses": responses,
                "supplement": (f.get("supplement") or "").strip(),
                "new_issues": new_issues,
            })
            return _case_review_thanks_html(package)
        return render_review_page(package)

    # ── 看板壳页 ──────────────────────────────────────────────────────────────
    @app.get("/")
    def index():
        return _shell_page()

    # ── 物料看板（队列 #334）──────────────────────────────────────────────────
    @app.get("/materials")
    def materials_page():
        return _materials_page()

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
                bottleneck_unanswered=(f.get("bottleneck_unanswered") == "on"),
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
        + '<button class="btn" id="xlsx" type="button">导出 Excel</button>\n'
        + '<button class="btn" id="legendBtn" type="button">📖 图例</button></div>\n'
        + '<div class="legend" id="legendPanel">' + render_legend(config.default_params()) + '</div>\n'
        + '<div class="cnt" id="cnt"></div>\n<div class="pager" id="pagerTop"></div>\n'
        + '<div class="cards" id="cards"></div>\n<div class="pager" id="pagerBottom"></div>\n'
        + '<div class="foot">分级只看<b>有确定承诺</b>子件的齐料缺口：🔴 真延期 · 🟠 待催 · 🟡 偏紧 · 🟢 按期。'
        + '🔴 真延期自动建案并推保供运维群，见 <a href="/cases">案例处置中心</a>。本服务 LAN 内部用，不对客。</div>\n'
        + '</div>\n<script>\n' + js + '\n</script></body></html>'
    )


# ── 物料看板页（队列 #334）────────────────────────────────────────────────────

_MAT_CSS = """<style>
.mat-wrap{max-width:1500px;margin:0 auto}
.mat-note{background:var(--surface2);border-radius:10px;padding:12px 16px;margin-bottom:14px;font-size:12.5px;color:var(--text2);line-height:1.75}
.mat-note b{color:var(--text)}
.mat-note ol{margin:6px 0 0;padding-left:20px}
.mat-scroll{overflow-x:auto;border:1px solid var(--border);border-radius:12px;background:var(--surface)}
.mat-tbl{width:100%;border-collapse:collapse;font-size:13px;white-space:nowrap}
.mat-tbl th{background:var(--surface2);padding:9px 11px;text-align:left;font-size:12px;color:var(--text2);position:sticky;top:0}
.mat-tbl td{padding:8px 11px;border-top:1px solid var(--border);vertical-align:top}
.mat-tbl td.num{text-align:right;font-family:var(--mono)}
.mat-tbl td.mono{font-family:var(--mono)}
.mat-tbl tr:hover td{background:var(--surface2)}
.mat-tot{font-weight:600;color:var(--danger)}
.mat-gapmark{color:var(--text3);font-style:normal}
.mat-tag{font-size:11px;padding:1px 6px;border-radius:6px;background:var(--surface2);color:var(--text2);margin-left:6px}
.mat-div{color:var(--gap);font-weight:600}
.mat-multi{white-space:normal;max-width:220px}
</style>"""


def _materials_page() -> str:
    """物料看板页（队列 #334，design D9）：挂现服务路由之下，不新起端口。

    与成品看板同源同一份快照——页面只 `fetch /api/materials` 读快照，**没有任何
    重算入口**（重算约 15 分钟，且重算是成品看板那边的既有动作，两处共用同一份结果）。
    """
    st_label = _json.dumps(_MAT_STATUS_LABELS, ensure_ascii=False)
    gap_mark = _json.dumps(_MAT_FIELD_GAP, ensure_ascii=False)
    js = r"""
var ROWS=[],MONTHS=[],META={},SNAP={};
var ST_LABEL=__ST_LABEL__, GAP_MARK=__GAP_MARK__;
var state={q:'',sort:'total',page:1,pageSize:50};
function $(id){return document.getElementById(id);}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function fmt(n){if(n==null||n==='')return '';var v=Number(n);
  if(!isFinite(v))return String(n);
  return (Math.round(v*100)/100).toLocaleString('zh-CN');}
function stText(r){
  var base=ST_LABEL[r.st]||r.st;
  if(r.st!=='divergent')return base;
  return base+'（'+(r.sts||[]).map(function(s){return ST_LABEL[s]||s;}).join(' / ')+'）';
}
function ansQty(r){return (r.cb&&r.cb.length)?r.cb.map(function(b){return fmt(b.q);}).join('、'):'无';}
function ansDate(r){return (r.cb&&r.cb.length)?r.cb.map(function(b){return b.d;}).join('、'):'无';}
// 🔴 供应商为空 ≠ 取数缺口：品牌/责任人是「全库没有这个字段」，而供应商为空是
// 「这个料当前没有未交采购订单」——那是一个**准确的答案**，不是取不到数。
// 生产实测 596 行里恰好 100 行为空，与状态列 no_transit(82)+confirmed_no_transit(18)
// 逐个对上，坐实两者同义。把它显示成「取数缺口」会重蹈 #296 那族「『无』与『0』
// 混为一谈」的老路，故单列措辞。
function supText(r){return (r.sup&&r.sup.length)?r.sup.join('、'):'无未交订单';}
function view(){
  var q=state.q.trim().toLowerCase();
  var l=ROWS.filter(function(r){
    if(!q)return true;
    return (r.id||'').toLowerCase().indexOf(q)>=0
        || (r.name||'').toLowerCase().indexOf(q)>=0
        || (r.sup||[]).join(' ').toLowerCase().indexOf(q)>=0;
  });
  var s=state.sort;
  l.sort(function(a,b){
    if(s==='id')return a.id<b.id?-1:(a.id>b.id?1:0);
    if(s==='tq')return (b.tq||0)-(a.tq||0);
    if(s==='total')return (b.total||0)-(a.total||0)||(a.id<b.id?-1:1);
    return 0;
  });
  return l;
}
function head(){
  var h=['料号','品名','品牌','状态','未交订单数量'];
  MONTHS.forEach(function(m){h.push(m.label+'缺口');});
  h.push(MONTHS.length?(MONTHS[0].label+'-'+MONTHS[MONTHS.length-1].label+'总缺口'):'总缺口');
  h.push('答交数量','答交日期','供应商名称','责任人');
  return h;
}
function cells(r){
  var c=[esc(r.id)+(r.hasSub?'<span class="mat-tag">含替代料</span>':'')
        +(r.out>0?'<span class="mat-tag" title="该物料另有落在三个月窗口之外的缺口，按口径不计入下列各月与合计">窗口外 '+fmt(r.out)+'</span>':''),
    esc(r.name),
    '<span class="mat-gapmark">'+esc(r.brand)+'</span>',
    (r.st==='divergent'?'<span class="mat-div">':'<span>')+esc(stText(r))+'</span>',
    fmt(r.tq)];
  (r.m||[]).forEach(function(v){c.push(fmt(v));});
  c.push('<span class="mat-tot">'+fmt(r.total)+'</span>');
  c.push(esc(ansQty(r)),esc(ansDate(r)),esc(supText(r)),
         '<span class="mat-gapmark">'+esc(r.owner)+'</span>');
  return c;
}
var NUMCOL={};   // 右对齐的列下标（未交订单量/各月/合计）
function render(){
  var l=view(),total=l.length;
  var ps=state.pageSize,pages=Math.max(1,Math.ceil(total/ps));
  if(state.page>pages)state.page=pages;
  var from=(state.page-1)*ps,page=l.slice(from,from+ps);
  var h=head();
  NUMCOL={};for(var i=4;i<5+MONTHS.length+1;i++)NUMCOL[i]=1;
  var html='<table class="mat-tbl"><thead><tr>'
    +h.map(function(x){return '<th>'+esc(x)+'</th>';}).join('')+'</tr></thead><tbody>';
  if(!page.length){
    html+='<tr><td colspan="'+h.length+'" style="text-align:center;color:var(--text3);padding:24px">'
      +(SNAP.ok?'没有符合条件的物料':'尚未刷新 —— 请到 <a href="/">成品看板</a> 点「立即重算」')+'</td></tr>';
  }
  page.forEach(function(r){
    html+='<tr>'+cells(r).map(function(c,i){
      var cl=i===0?' class="mono"':(NUMCOL[i]?' class="num"':(i>=h.length-4?' class="mat-multi"':''));
      return '<td'+cl+'>'+c+'</td>';}).join('')+'</tr>';
  });
  html+='</tbody></table>';
  $('tblBox').innerHTML=html;
  $('cnt').textContent='共 '+total+' 个缺料物料'
    +(META.out_of_window_materials?('　·　另有 '+META.out_of_window_materials
      +' 个物料的缺口全部落在窗口之外，按口径未列出'):'')
    +'　·　第 '+state.page+'/'+pages+' 页';
  var pg='';
  if(pages>1){
    pg+='<button class="btn" '+(state.page<=1?'disabled':'')+' data-p="'+(state.page-1)+'">上一页</button>';
    pg+='<button class="btn" '+(state.page>=pages?'disabled':'')+' data-p="'+(state.page+1)+'">下一页</button>';
  }
  $('pager').innerHTML=pg;
  Array.prototype.forEach.call($('pager').querySelectorAll('button[data-p]'),function(b){
    b.addEventListener('click',function(){state.page=parseInt(b.getAttribute('data-p'),10);render();});
  });
}
function applySnap(s){
  SNAP=s||{};ROWS=(s&&s.rows)||[];META=(s&&s.meta)||{};MONTHS=(META.months)||[];
  var ts=$('ts');
  if(ts)ts.textContent=(s&&s.ok)
    ?('数据同源于成品保供快照　·　最后更新 '+(s.generated_at||'—')+'　·　业务日期 '+(s.today||'—'))
    :'尚未刷新 —— 物料看板与成品看板共用同一份快照，请到成品看板点「立即重算」';
  var w=$('win');
  if(w)w.textContent=META.window?('本视图窗口＝'+META.window+'，共 '+MONTHS.length+' 个自然月，以快照业务日期所在月为首、随快照自动滚动。'):'';
  state.page=1;render();
}
function loadSnap(){
  fetch('/api/materials').then(function(r){return r.json();}).then(applySnap)
   .catch(function(){$('tblBox').innerHTML='<div class="empty">加载失败</div>';});
}
function exportExcel(){
  var l=view(),h=head();
  var thead='<tr>'+h.map(function(x){return '<th>'+esc(x)+'</th>';}).join('')+'</tr>';
  var tbody='';
  l.forEach(function(r){
    var c=[r.id+(r.hasSub?'（含替代料）':''),r.name,r.brand,stText(r),r.tq];
    (r.m||[]).forEach(function(v){c.push(v);});
    c.push(r.total,ansQty(r),ansDate(r),supText(r),r.owner);
    tbody+='<tr>'+c.map(function(x){return '<td>'+esc(x)+'</td>';}).join('')+'</tr>';
  });
  var html='﻿<html><head><meta charset="UTF-8"></head><body><table border="1">'
    +thead+tbody+'</table></body></html>';
  var blob=new Blob([html],{type:'application/vnd.ms-excel'});
  var a=document.createElement('a');a.href=URL.createObjectURL(blob);
  a.download='物料看板_'+(SNAP.today||'')+'.xls';
  document.body.appendChild(a);a.click();document.body.removeChild(a);URL.revokeObjectURL(a.href);
}
$('q').addEventListener('input',function(e){state.q=e.target.value;state.page=1;render();});
$('sort').addEventListener('change',function(e){state.sort=e.target.value;state.page=1;render();});
$('pageSize').addEventListener('change',function(e){
  state.pageSize=parseInt(e.target.value,10)||50;state.page=1;render();});
$('xlsx').addEventListener('click',exportExcel);
$('refresh').addEventListener('click',loadSnap);
loadSnap();
setInterval(loadSnap,120000);
"""
    js = js.replace("__ST_LABEL__", st_label).replace("__GAP_MARK__", gap_mark)
    # ── 取数说明（design D7）：可算但有前提，就把前提写在脸上 ──────────────────
    note = (
        '<div class="mat-note"><b>📌 取数说明（请先看一眼，这几条决定了下面的数字怎么读）</b>'
        '<ol>'
        '<li><b>本视图是「缺料视图」，不是全量物料台账</b>——只列出当前快照里<b>确实存在缺口</b>'
        '（缺口数量 &gt; 0）的物料；不缺的料不会出现。</li>'
        '<li><b>月度缺口按「计划出货日期所在自然月」归集</b>。<span id="win"></span>'
        '<b>落在窗口之外的缺口不计入任何一个月度列与合计列</b>，故「总缺口」的含义是'
        '「这几个月的缺口之和」，不是「该物料的全部缺口」。</li>'
        '<li><b>答交数量/日期的累计口径与成品卡片不同，因此条数可能不一样，这是对的</b>——'
        '成品卡片按<b>那一张单</b>的缺口累计到够为止，本视图按<b>这几个月的合计缺口</b>累计到够为止，'
        '累计目标不同，取的批次自然不同。两者用的是同一份答交记录、同一个累计函数。</li>'
        '<li>🔴 <b>「品牌」与「责任人」两列当前无可用真实取数源，故显式标注取数缺口、不留空、'
        '也不用相近字段顶替。</b>2026-08-19 已用生产凭据实测：SRM「请购需求池-采购订单协同」页'
        '（这两列指定的取值来源）在携客云 OpenAPI 上<b>没有对应端点</b>（8 个候选路径全部 404，'
        '同批对照端点正常返回，排除探测方法本身的问题）；ERP 侧物料档案与采购订单逐字段查过，'
        '<b>无品牌字段</b>；ERP 的「制单人」<b>已被真实数据证伪</b>不等于「负责采购」'
        '（R01B.0115：SRM 页负责采购是一个人，该料未交 PO 的制单人却是三个人）。'
        '<b>下一步</b>：已请 IT 侧核实携客云 OpenAPI 是否提供该端点；同时随判例包请采购部确认'
        '「制单人」能否作为过渡替代。</li>'
        '<li>「供应商名称」取自 <b>ERP 未交采购订单的供应商</b>（＝实际下单供应商），'
        '与 SRM 页的「核定供应商」在极少数情况下可能不同；同一物料有多家时全部并列。'
        '该列显示<b>「无未交订单」</b>时是一个<b>准确的答案</b>（这个料当前确实没有在途采购订单），'
        '<b>不是</b>上一条说的那种取不到数——两者措辞刻意不同，请勿混看。</li>'
        '<li>⚠️ <b>齐料日期口径正在与采购部确认中</b>（已知缺陷：齐料日/瓶颈物料只取最早答交'
        '日期、不看答交数量，判例包已发出待回件）。本视图<b>不展示齐料日期</b>，不受该缺陷影响；'
        '成品看板上的齐料日在该口径确认前请谨慎使用。</li>'
        '</ol></div>'
    )
    return (
        '<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<title>物料看板 · 成品保供预警</title>\n' + _HTML_STYLE + _NAV_CSS + _MAT_CSS
        + '</head><body>\n' + _nav_html("materials") + '<div class="wrap mat-wrap">\n'
        + '<div class="head"><div><div class="title">物料看板 · 按单个物料看缺口</div>\n'
        + '<div class="sub" id="ts">加载中…</div></div>\n'
        + '<div class="badges"><span class="badge">与成品看板同源同一份快照</span>'
        + '<span class="badge">内部保供运维 · 不对客 · LAN</span></div></div>\n'
        + note
        + '<div class="toolbar">\n'
        + '<input class="search" id="q" type="text" placeholder="搜索 料号 / 品名 / 供应商" aria-label="搜索">\n'
        + '<select class="sel" id="sort" aria-label="排序"><option value="total">按总缺口</option>'
        + '<option value="tq">按未交订单数量</option><option value="id">按料号</option></select>\n'
        + '<select class="sel" id="pageSize" aria-label="每页行数"><option value="50">50 行/页</option>'
        + '<option value="100">100 行/页</option><option value="200">200 行/页</option>'
        + '<option value="1000">1000 行/页</option></select>\n'
        + '<button class="btn" id="xlsx" type="button" title="导出当前筛选命中的全部物料行（不受分页限制）">导出 Excel</button>\n'
        + '<button class="btn" id="refresh" type="button" title="重新读取最新快照（不触发重算）">🔄 刷新</button></div>\n'
        + '<div class="cnt" id="cnt"></div>\n'
        + '<div class="mat-scroll" id="tblBox"></div>\n'
        + '<div class="pager" id="pager" style="margin-top:12px"></div>\n'
        + '<div class="foot">本页为纯展示派生视图，不参与四色风险／齐料日／可齐套任何判定；'
        + '数据与 <a href="/">成品看板</a> 同源同一份快照，重算入口在成品看板。</div>\n'
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
    r = "active" if active == "review" else ""
    m = "active" if active == "materials" else ""
    return (f'<nav class="bg-nav"><div class="brand">⚡ 成品<span>保供预警</span></div>'
            f'<a href="/" class="{d}">📊 看板</a>'
            f'<a href="/materials" class="{m}">📦 物料看板</a>'
            f'<a href="/cases" class="{c}">🚨 案例处置</a>'
            f'<a href="/cases/review" class="{r}">📋 判例批改</a></nav>')


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
            f'{" <span style=\"color:#A32D2D\">（未答复，对客草稿将改用保守措辞）</span>" if case.bottleneck_unanswered else ""}'
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
            '<label style="display:flex;align-items:center;gap:6px;font-weight:normal">'
            '<input type="checkbox" name="bottleneck_unanswered" style="width:auto">'
            '瓶颈子件尚无供应商答复（对客草稿将改用"交期未确认"措辞，不写"确定延期"）</label>'
            '<label>操作人</label><input name="actor" placeholder="运维">'
            '<div style="margin-top:14px;display:flex;gap:10px">'
            '<button class="bg-btn primary" type="submit">建案</button>'
            '<a href="/cases" class="bg-btn">取消</a></div></form></div>')
    return _page("手动建案", "cases", body)


# ── 判例包网页表单化页面（队列 #110 Feature B）─────────────────────────────────

def _case_review_list_html(packages, submitted_ids) -> str:
    rows = ""
    for p in packages:
        status = '<span class="bg-stale">✅ 已提交</span>' if p.package_id in submitted_ids else "待作答"
        rows += (f'<tr><td><a href="/cases/review/{_html.escape(p.package_id)}">'
                 f'{_html.escape(p.title)}</a></td><td>{_html.escape(p.recipient)}</td>'
                 f'<td>{len(p.cases)}</td><td>{status}</td></tr>')
    body = (f'<h2 style="margin:0 0 4px">📋 判例批改（网页表单）</h2>'
            f'<p class="sub">点击标题进入作答，一次提交即可</p>'
            f'<table class="bg-tbl"><thead><tr><th>判例包</th><th>收件人</th>'
            f'<th>项数</th><th>状态</th></tr></thead>'
            f'<tbody>{rows or "<tr><td colspan=4 style=text-align:center;padding:28px;color:#888>暂无判例包</td></tr>"}</tbody></table>'
            f'<div style="margin-top:14px"><a href="/" class="bg-btn">← 看板</a></div>')
    return _page("判例批改", "review", body)


def _case_review_thanks_html(package) -> str:
    body = (f'<h2 style="margin:0 0 8px">✅ 已提交</h2>'
            f'<p class="sub">感谢批改「{_html.escape(package.title)}」，本次意见已记录。</p>'
            f'<a href="/cases/review" class="bg-btn">← 返回判例包列表</a>')
    return _page("已提交", "review", body)


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
