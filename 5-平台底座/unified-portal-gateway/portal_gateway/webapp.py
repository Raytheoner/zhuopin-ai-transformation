"""统一门户网关 Flask app 工厂 —— 串联 SSO / 权限 / 路由代理 / 访问日志。

请求处理顺序（`_gateway_gate` → 代理视图）：
  1. 路径命中豁免前缀（健康检查/SSO 自身路径）→ 直接放行，不鉴权不记录。
  2. 路径未命中任何路由表条目 → 404（白名单代理，不做通用转发，见 routing.py）。
  3. 会话 Cookie 缺失/过期/签名不符 → 记一条 `unauthenticated` 访问日志，
     跳转登录页（携带 next，登录后回跳）。
  4. 会话存在但权限层级不足该路由要求 → 记一条 `insufficient_tier` 访问日志，
     返回 403。
  5. 通过 → 记一条 `authorized` 访问日志 → 反向代理转发到后端。

三条登录入口见 `sso.py` 模块说明；应急登录入口存在但不在任何用户可见页面
里被链接（spec「应急通道不作为常规入口对外公示」）。
"""
from __future__ import annotations

import os
import secrets as _secrets_mod
from pathlib import Path
from urllib.parse import quote

from flask import Flask, Response, redirect, request

from zhuopin_platform.audit import AuditLogger

from portal_gateway import sso
from portal_gateway.access_log import AUTHORIZED, INSUFFICIENT_TIER, UNAUTHENTICATED, record_access
from portal_gateway.permissions import (
    PermissionTier,
    has_access,
    load_department_mapping,
    resolve_tier,
)
from portal_gateway.routing import default_route_table, forward_request, match_route

SESSION_SECRET_ENV = "PORTAL_GATEWAY_SESSION_SECRET"
OAUTH_STATE_COOKIE = "zp_portal_oauth_state"
OAUTH_NEXT_COOKIE = "zp_portal_oauth_next"

_EXEMPT_PREFIXES = ("/api/ping", "/portal/_sso/")


def _safe_next(next_url: str | None) -> str:
    """防开放重定向：next 必须是站内绝对路径，且不是协议相对 URL。"""
    if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
        return "/"
    return next_url


def _resolve_session_secret(explicit: str | None) -> str:
    secret = explicit or (os.environ.get(SESSION_SECRET_ENV) or "").strip()
    if not secret:
        raise RuntimeError(
            f"未配置 {SESSION_SECRET_ENV}——网关无法安全签发/校验会话，拒绝启动"
            "（不同于 simple_gate 的『未配置即不生效』，本项是身份鉴别的信任根，"
            "缺失时必须 fail loud，不能 fail open）。"
        )
    return secret


def create_app(*, secret: str | None = None, routes=None, mapping=None,
               audit_path: Path | str = "reports/portal_access.jsonl",
               start_dates: dict[str, str] | None = None) -> Flask:
    app = Flask(__name__)

    session_secret = _resolve_session_secret(secret)
    route_table = routes if routes is not None else default_route_table()
    dept_mapping = mapping if mapping is not None else load_department_mapping()
    audit_logger = AuditLogger.jsonl(audit_path)

    def _login_url(next_path: str) -> str:
        return f"/portal/_sso/login?next={quote(next_path, safe='')}"

    # ── 健康检查（豁免鉴权） ────────────────────────────────────────

    @app.route("/api/ping")
    def _ping():
        return {"status": "ok", "service": "统一门户网关"}

    # ── 登录选择页 ──────────────────────────────────────────────────

    @app.route("/portal/_sso/login")
    def _login_chooser():
        nxt = _safe_next(request.args.get("next"))
        oauth_cfg = sso.load_wecom_oauth_config()
        links = []
        if oauth_cfg is not None:
            links.append(f'<a href="/portal/_sso/oauth/start?next={quote(nxt, safe="")}">企业微信登录</a>')
        if sso.mock_login_enabled():
            links.append(
                f'<a href="/portal/_sso/mock-login?next={quote(nxt, safe="")}">'
                '⚠️ 开发/试点登录（非正式身份验证）</a>'
            )
        body = "<br>".join(links) or "<p>未配置任何登录方式，请联系运维。</p>"
        return Response(f"<!doctype html><html><body><h3>统一门户登录</h3>{body}</body></html>",
                         mimetype="text/html")

    # ── 真实企微 OAuth2 ─────────────────────────────────────────────

    @app.route("/portal/_sso/oauth/start")
    def _oauth_start():
        cfg = sso.load_wecom_oauth_config()
        if cfg is None:
            return Response("企微 OAuth 未配置", status=404)
        nxt = _safe_next(request.args.get("next"))
        state = _secrets_mod.token_urlsafe(16)
        redirect_uri = request.url_root.rstrip("/") + "/portal/_sso/oauth/callback"
        url = sso.build_wecom_authorize_url(corp_id=cfg.corp_id, agent_id=cfg.agent_id,
                                             redirect_uri=redirect_uri, state=state)
        resp = redirect(url)
        resp.set_cookie(OAUTH_STATE_COOKIE, state, max_age=600, httponly=True, samesite="Lax", path="/")
        resp.set_cookie(OAUTH_NEXT_COOKIE, nxt, max_age=600, httponly=True, samesite="Lax", path="/")
        return resp

    @app.route("/portal/_sso/oauth/callback")
    def _oauth_callback():
        cfg = sso.load_wecom_oauth_config()
        if cfg is None:
            return Response("企微 OAuth 未配置", status=404)
        state = request.args.get("state")
        cookie_state = request.cookies.get(OAUTH_STATE_COOKIE)
        if not state or not cookie_state or state != cookie_state:
            return Response("登录状态校验失败，请重新登录", status=400)
        code = request.args.get("code")
        userid = sso.exchange_code_for_userid(cfg, code) if code else None
        if not userid:
            return Response("企微登录失败，请重试或联系运维", status=401)
        nxt = _safe_next(request.cookies.get(OAUTH_NEXT_COOKIE))
        resp = redirect(nxt)
        resp.set_cookie(sso.COOKIE_NAME, sso.make_session_cookie_value(session_secret, userid),
                         max_age=sso.DEFAULT_COOKIE_DAYS * 86400, httponly=True, samesite="Lax", path="/")
        resp.delete_cookie(OAUTH_STATE_COOKIE, path="/")
        resp.delete_cookie(OAUTH_NEXT_COOKIE, path="/")
        return resp

    # ── mock 登录（开发/试点期，见 sso.py 顶部红线说明） ───────────────

    @app.route("/portal/_sso/mock-login", methods=["GET", "POST"])
    def _mock_login():
        if not sso.mock_login_enabled():
            return Response("mock 登录未启用", status=404)
        nxt = _safe_next(request.values.get("next"))
        if request.method == "POST":
            userid = (request.form.get("userid") or "").strip()
            if not userid:
                return Response("userid 不得为空", status=400)
            resp = redirect(nxt)
            resp.set_cookie(sso.COOKIE_NAME, sso.make_session_cookie_value(session_secret, userid),
                             max_age=sso.DEFAULT_COOKIE_DAYS * 86400, httponly=True, samesite="Lax", path="/")
            return resp
        return Response(
            "<!doctype html><html><body>"
            "<h3 style='color:#b45309'>⚠️ 开发/试点登录 —— 非正式身份验证，仅用于打通链路</h3>"
            f"<form method='post'><input type='hidden' name='next' value='{nxt}'>"
            "<input name='userid' placeholder='任意 userid（如 YaoZuYi）' autofocus>"
            "<button type='submit'>登录</button></form></body></html>",
            mimetype="text/html",
        )

    # ── 应急本地口令通道（刻意不在任何页面被链接，见模块说明） ─────────

    @app.route("/portal/_sso/emergency-login", methods=["GET", "POST"])
    def _emergency_login():
        nxt = _safe_next(request.values.get("next"))
        if request.method == "POST":
            password = request.form.get("password")
            if not sso.verify_emergency_password(password):
                return Response("口令不正确或应急通道未启用", status=401)
            resp = redirect(nxt)
            resp.set_cookie(sso.COOKIE_NAME,
                             sso.make_session_cookie_value(session_secret, sso.emergency_userid()),
                             max_age=sso.DEFAULT_COOKIE_DAYS * 86400, httponly=True, samesite="Lax", path="/")
            return resp
        return Response(
            "<!doctype html><html><body><h3>应急登录</h3>"
            f"<form method='post'><input type='hidden' name='next' value='{nxt}'>"
            "<input type='password' name='password' placeholder='应急口令'>"
            "<button type='submit'>进入</button></form></body></html>",
            mimetype="text/html",
        )

    @app.route("/portal/_sso/logout")
    def _logout():
        resp = redirect("/portal/_sso/login")
        resp.delete_cookie(sso.COOKIE_NAME, path="/")
        return resp

    # ── 反向代理主链路 ──────────────────────────────────────────────

    def _proxy(subpath: str):
        path = "/" + subpath
        route = match_route(route_table, path)
        if route is None:
            return Response("未知路由", status=404)

        userid = sso.verify_session_cookie_value(session_secret, request.cookies.get(sso.COOKIE_NAME))
        tier = resolve_tier(dept_mapping, userid, route.domain)

        if userid is None:
            record_access(audit_logger, userid=None, domain=route.domain, path=path,
                           tier_required=route.required_tier, tier_resolved=None,
                           allowed=False, auth_result=UNAUTHENTICATED, start_dates=start_dates)
            return redirect(_login_url(request.full_path if request.query_string else path))

        if not has_access(route.required_tier, tier):
            record_access(audit_logger, userid=userid, domain=route.domain, path=path,
                           tier_required=route.required_tier, tier_resolved=tier,
                           allowed=False, auth_result=INSUFFICIENT_TIER, start_dates=start_dates)
            return Response("权限不足", status=403)

        record_access(audit_logger, userid=userid, domain=route.domain, path=path,
                       tier_required=route.required_tier, tier_resolved=tier,
                       allowed=True, auth_result=AUTHORIZED, start_dates=start_dates)

        try:
            backend_resp = forward_request(
                route, path, method=request.method, headers=dict(request.headers),
                query_string=request.query_string.decode("utf-8"), data=request.get_data(),
            )
        except Exception:
            return Response("后端服务暂不可达，请稍后重试", status=502)

        excluded = {"content-encoding", "transfer-encoding", "content-length", "connection"}
        response_headers = [(k, v) for k, v in backend_resp.raw.headers.items() if k.lower() not in excluded]
        return Response(backend_resp.iter_content(chunk_size=8192), status=backend_resp.status_code,
                         headers=response_headers)

    @app.route("/", defaults={"subpath": ""},
               methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
    @app.route("/<path:subpath>",
               methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
    def _proxy_view(subpath):
        if request.path.startswith(_EXEMPT_PREFIXES):
            # 理论上不会走到这里（更具体的路由先匹配），留作双重保险。
            return Response("未知路由", status=404)
        return _proxy(subpath)

    return app
