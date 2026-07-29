"""共享口令门禁（临时止血，非正式鉴权，见跨桌任务队列 #10）。

背景：`.51` 上四个内网服务（保供看板8091/命令中心8092/QD-B8093/FI2 8094）此前零鉴权、
绑 0.0.0.0，LAN 内任何人打开浏览器即可看到真实客户名/立项书财务数据/供应商单价。
本模块只解决"随便谁都能打开"这一层——不区分人员、不留"谁看了什么"的痕迹、口令在
HTTP 明文里裸传（LAN 内可接受）。**它是门锁，不是鉴权**。正式身份与权限走企微 OAuth
（另见架构决策件），届时本模块整体下线。

机制：浏览器 Cookie 按 host 隔离、不区分端口——四个服务同在 192.168.100.51，任一端口
种下的 Cookie 其余三个端口都能读到，故一次登录、四服务全通（含 8092 iframe 嵌 8091 场景，
iframe 顶层导航到另一端口不受 SameSite=Lax 影响，因"site"不含端口）。刻意不用 HTTP Basic：
iframe 嵌套会弹两次系统认证框，体验直接崩。

Cookie 值 = "{过期时间戳}.{HMAC-SHA256(密码, 过期时间戳)}"，服务端凭同一份密码重新计算
签名校验，不依赖服务端存储 session（无状态，四服务各自独立校验，无需共享 session 存储）。

密码来自环境变量 `ZP_GATE_PASSWORD`（各服务 .env，不入库）。**该变量未设置时门禁自动
跳过**（返回 app 原样），这样本地开发/既有测试套件无需为每个 create_app() 调用点显式关闭
门禁——只有生产 `.env` 显式配置了密码，门禁才真正生效。

命令中心（`1-转型规划/AI运营指挥中心/serve.py`）是纯标准库 `SimpleHTTPRequestHandler`，
刻意"零三方依赖"以便 `.51` 常驻，不引入 `zhuopin_platform` 依赖——其门禁逻辑在 serve.py
内自包含复制一份（同一套 cookie 名/签名算法/登录路径常量），本模块只服务三个 Flask 场景。
"""
from __future__ import annotations

import hashlib
import hmac
import time
from http.cookies import SimpleCookie

COOKIE_NAME = "zp_gate"
LOGIN_PATH = "/_gate/login"
LOGOUT_PATH = "/_gate/logout"
DEFAULT_COOKIE_DAYS = 30


def _sign(secret: str, exp_ts: int) -> str:
    return hmac.new(secret.encode("utf-8"), str(exp_ts).encode("utf-8"), hashlib.sha256).hexdigest()


def make_cookie_value(secret: str, *, days: int = DEFAULT_COOKIE_DAYS, now: int | None = None) -> str:
    """签发一个新的 cookie 值，`days` 天后过期。"""
    exp_ts = (now if now is not None else int(time.time())) + days * 86400
    return f"{exp_ts}.{_sign(secret, exp_ts)}"


def verify_cookie_value(secret: str, value: str | None, *, now: int | None = None) -> bool:
    """校验 cookie 值：签名匹配且未过期。签名不匹配/格式非法/已过期均返回 False（fail-closed）。"""
    if not value or "." not in value:
        return False
    exp_str, _, sig = value.partition(".")
    try:
        exp_ts = int(exp_str)
    except ValueError:
        return False
    current = now if now is not None else int(time.time())
    if exp_ts < current:
        return False
    expected = _sign(secret, exp_ts)
    return hmac.compare_digest(sig, expected)


def verify_auth_token(secret: str, token: str | None) -> bool:
    """程序化访问用：`X-Auth-Token` 请求头值需与口令字面一致（常量时间比较）。"""
    if not token:
        return False
    return hmac.compare_digest(token, secret)


def parse_cookie_header(cookie_header: str | None, name: str) -> str | None:
    """从原始 `Cookie` 请求头文本中取出指定名字的值（供非 Flask 场景，如 http.server，使用）。"""
    if not cookie_header:
        return None
    jar: SimpleCookie = SimpleCookie()
    try:
        jar.load(cookie_header)
    except Exception:
        return None
    morsel = jar.get(name)
    return morsel.value if morsel else None


def is_authorized(secret: str, *, cookie_header: str | None, auth_token: str | None,
                   now: int | None = None) -> bool:
    """统一判定入口：X-Auth-Token 命中 或 zp_gate cookie 校验通过 均视为已授权。"""
    if verify_auth_token(secret, auth_token):
        return True
    cookie_val = parse_cookie_header(cookie_header, COOKIE_NAME)
    return verify_cookie_value(secret, cookie_val, now=now)


def set_cookie_header_value(secret: str, *, days: int = DEFAULT_COOKIE_DAYS) -> str:
    """生成可直接写入 `Set-Cookie` 响应头的完整值（供非 Flask 场景手工拼响应头用）。"""
    value = make_cookie_value(secret, days=days)
    return f"{COOKIE_NAME}={value}; Path=/; Max-Age={days * 86400}; HttpOnly; SameSite=Lax"


def _safe_next(next_url: str | None) -> str:
    """防开放重定向：next 必须是站内绝对路径，且不是协议相对 URL（`//evil.com`）。"""
    if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
        return "/"
    return next_url


def login_page_html(service_name: str, next_url: str, *, error: bool = False) -> str:
    """共享登录页模板（内联样式，无外部依赖）。"""
    nxt = _safe_next(next_url)
    error_html = (
        '<div class="err">口令不正确，请重新输入。</div>' if error else ""
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>访问口令 · {service_name}</title>
<style>
  body{{font-family:-apple-system,"Segoe UI",'Microsoft YaHei',sans-serif;background:#0f172a;color:#e2e8f0;
       display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}
  .box{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:32px 36px;width:320px}}
  h1{{font-size:16px;margin:0 0 4px}}
  .sub{{color:#94a3b8;font-size:12px;margin-bottom:18px}}
  input[type=password]{{width:100%;background:#0f172a;color:#e2e8f0;border:1px solid #334155;
       border-radius:6px;padding:9px 10px;font-size:14px;box-sizing:border-box;margin-bottom:12px}}
  button{{width:100%;background:#2563eb;color:#fff;border:0;border-radius:6px;padding:10px;
       font-size:14px;cursor:pointer}}
  button:hover{{background:#1d4ed8}}
  .err{{color:#f87171;font-size:12px;margin-bottom:10px}}
  .note{{color:#64748b;font-size:11px;margin-top:14px;line-height:1.5}}
</style></head><body>
<div class="box">
  <h1>🔒 {service_name}</h1>
  <div class="sub">内部服务访问口令 · 登录后 30 天内本机免登录</div>
  <form method="post" action="{LOGIN_PATH}">
    <input type="hidden" name="next" value="{nxt}">
    <input type="password" name="password" placeholder="访问口令" autofocus required>
    {error_html}
    <button type="submit">进入</button>
  </form>
  <div class="note">忘记口令请联系 Paul / IT。本页仅做基础访问限制，非正式身份鉴权。</div>
</div>
</body></html>"""


# ── Flask 集成（SC8/QD-B/FI2 三个 Flask 场景共用） ──────────────────────────

def install_flask_gate(app, *, service_name: str, env_var: str = "ZP_GATE_PASSWORD",
                        exempt_paths: tuple[str, ...] = ("/api/ping",)):
    """给一个 Flask app 装上共享口令门禁。

    `env_var` 未设置/为空时**不装门禁**、原样返回 app——本地开发与既有测试套件
    因此无需改动即可继续通过；只有生产 `.env` 显式配置了口令，门禁才生效。
    """
    import os

    secret = (os.environ.get(env_var) or "").strip()
    if not secret:
        return app

    from flask import Response, redirect, request

    exempt = set(exempt_paths) | {LOGIN_PATH, LOGOUT_PATH}

    @app.before_request
    def _zp_gate_check():  # noqa: ANN202
        if request.path in exempt:
            return None
        if is_authorized(secret, cookie_header=request.headers.get("Cookie"),
                          auth_token=request.headers.get("X-Auth-Token")):
            return None
        if request.method in ("GET", "HEAD"):
            qs = request.query_string.decode("utf-8")
            full = request.path + (f"?{qs}" if qs else "")
            from urllib.parse import quote
            return redirect(f"{LOGIN_PATH}?next={quote(full, safe='')}")
        return Response("未登录或口令已失效，请在浏览器中打开本服务任意页面重新登录。",
                        status=401, mimetype="text/plain")

    @app.route(LOGIN_PATH, methods=["GET", "POST"])
    def _zp_gate_login():  # noqa: ANN202
        nxt = _safe_next(request.values.get("next", "/"))
        if request.method == "POST":
            pw = request.form.get("password", "")
            if hmac.compare_digest(pw, secret):
                resp = redirect(nxt)
                resp.set_cookie(COOKIE_NAME, make_cookie_value(secret),
                                 max_age=DEFAULT_COOKIE_DAYS * 86400,
                                 httponly=True, samesite="Lax", path="/")
                return resp
            return Response(login_page_html(service_name, nxt, error=True), mimetype="text/html")
        return Response(login_page_html(service_name, nxt), mimetype="text/html")

    @app.route(LOGOUT_PATH, methods=["GET"])
    def _zp_gate_logout():  # noqa: ANN202
        resp = redirect(LOGIN_PATH)
        resp.delete_cookie(COOKIE_NAME, path="/")
        return resp

    return app
