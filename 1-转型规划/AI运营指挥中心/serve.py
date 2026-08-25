"""AI 运营指挥中心 · 静态托管服务（Python 标准库，零三方依赖，便于 .51 常驻）。

托管当前目录：
  · index.html            —— 命令中心页面（部署时由 AI运营指挥中心-框架原型-*.html 改名而来）
  · data/                 —— 同源数据目录（销售域实时 JSON dashboard_data.json 等，见队列 #53）
端口默认 8092（区别于保供看板 8091 / 企微服务）；绑 0.0.0.0 供 LAN 访问。
所有响应 Cache-Control: no-store —— 保证销售域 fetch 每次拿到最新 dashboard_data.json。

用法：python serve.py [端口]    （不传端口则用环境变量 CC_PORT 或默认 8092）

── 共享口令门禁（临时止血，跨桌任务队列 #10，见 zhuopin_platform.shared_tools.simple_gate 顶部说明）──
本服务是纯标准库 SimpleHTTPRequestHandler（"零三方依赖"是既定设计原则，见上），刻意不引入
`zhuopin_platform` 依赖，故门禁逻辑在本文件内自包含实现——cookie 名/签名算法/登录路径与
`zhuopin_platform.shared_tools.simple_gate`（SC8/QD-B/FI2 三个 Flask 服务共用）**完全一致**，
保证浏览器在任一端口登录一次后，四个服务（8091/8092/8093/8094）凭同一枚 host-only cookie
全部放行（Cookie 按 host 隔离、不分端口）。密码来自环境变量 `ZP_GATE_PASSWORD`（本目录 `.env`，
不入库）；未配置时门禁自动跳过（不影响本地/无 .env 场景直接跑通）。`/api/ping`（本次新增，供
监控/程序化探活）与 `/_gate/login` 本身不受门禁拦截。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlsplit

ROOT = os.path.dirname(os.path.abspath(__file__))

# ── 轻量访问日志（队列 #112，自包含实现——本服务"零三方依赖"是既定设计原则，
#    见文件顶部门禁说明，不引入 zhuopin_platform.shared_tools.access_log 依赖；
#    字段/落盘约定与该模块保持一致，供 SC8/QD-B/FI2 三个 Flask 场景对照）──────
ACCESS_LOG_PATH = os.path.join(ROOT, "reports", "command_center_http_requests.jsonl")
_ACCESS_LOG_LOCK = threading.Lock()
_ACCESS_LOG_EXEMPT_PATHS = {"/api/ping"}


def _log_access(method: str, path: str, status: int, source_ip: str) -> None:
    if path in _ACCESS_LOG_EXEMPT_PATHS:
        return
    entry = {
        "service": "AI 运营指挥中心", "method": method, "path": path,
        "status": status, "source_ip": source_ip,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    os.makedirs(os.path.dirname(ACCESS_LOG_PATH), exist_ok=True)
    with _ACCESS_LOG_LOCK:
        with open(ACCESS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)

# ── .env 加载（凭据锚定，队列 #354）────────────────────────────────────────────
#
# 🔴 **本文件是 `env-anchor-collapse` 收拢范围内唯一的例外，且是刻意的**：本服务"零三方依赖"
# 是既定设计原则（见文件顶部门禁说明），`.51` 上由 `deploy-server.ps1` 注册的计划任务直接跑
# 裸 `python serve.py`，**其部署侧没有 venv、也没有 `pip install -e zhuopin_platform`**
# ——同目录的 `simple_gate` 与 `access_log` 已因同一理由各自内联一份。若在此 `import
# zhuopin_platform.env_anchor`，8092 命令中心会在 `.51` 上直接起不来，而**本地测起来永远是绿的**
# （#345 的原话：「本地永远能找到仓库根标记，本地全绿与它毫无关系」）。
#
# 故本文件**内联同一套解析语义**（与 `zhuopin_platform/env_anchor.py` 逐条对应，改一处须改两处，
# 已由 `工具-引导样板lint.py` 的豁免清单记名在案）：
#   ① `ZP_ENV_FILE` 显式覆盖 → ② monorepo（marker ＋ `--git-common-dir` 规范化）→ ③ 扁平部署根。
# 🔴 **修掉的实质缺陷**：原实现从 `ROOT` 向上找**最近的** `.env`，从 linked worktree 跑时命中
# 该 worktree 自己的陈旧副本而到不了主工作区，**且不报错**——门禁口令因此可能是上一代的。
_GATE_ENV_VAR = "ZP_GATE_PASSWORD"
_ENV_FILE_OVERRIDE = "ZP_ENV_FILE"
_MARKER_PARTS = ("5-平台底座", "zhuopin_platform")


def _canonical_repo_root(naive_root: str) -> str:
    """`--git-common-dir` 规范化到所有 linked worktree 共享的主工作区根。

    git 不可用（`.51` 上没有 git）或不在任何工作树里时**不抛异常**，回落 `naive_root`。
    """
    import subprocess
    try:
        result = subprocess.run(
            ["git", "-C", naive_root,
             "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, encoding="utf-8", check=True, timeout=30,
        )
    except Exception:
        return naive_root
    common_dir = result.stdout.strip()
    return os.path.dirname(common_dir) if common_dir else naive_root


def _find_env() -> str | None:
    override = (os.environ.get(_ENV_FILE_OVERRIDE) or "").strip()
    if override:
        # 显式声明的意图落空即报错——与「没找到任何 .env」不是一回事，不可混为静默。
        if not os.path.isfile(override):
            raise RuntimeError(
                f"{_ENV_FILE_OVERRIDE}={override} 指向的文件不存在（凭据锚定，队列 #354）"
            )
        return override

    here = ROOT
    while True:
        if os.path.isdir(os.path.join(here, *_MARKER_PARTS)):        # ② monorepo
            cand = os.path.join(_canonical_repo_root(here), ".env")
            return cand if os.path.isfile(cand) else None
        # ③ 扁平部署根：判据＝其下 `zhuopin_platform/pyproject.toml`。**不是**「有没有
        # `zhuopin_platform` 子目录」——分发目录自己也含一个同名内层包目录，朴素判据会在那里
        # 静默命中、把锚点少算一层，且返回一个存在的目录、不报错。
        if os.path.isfile(os.path.join(here, "zhuopin_platform", "pyproject.toml")):
            cand = os.path.join(here, ".env")
            return cand if os.path.isfile(cand) else None
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent


def _load_env() -> None:
    path = _find_env()
    if not path:
        return
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()
GATE_PASSWORD = (os.environ.get(_GATE_ENV_VAR) or "").strip()

# ── 共享口令门禁：cookie 名/签名算法/登录路径与 simple_gate.py 保持字面一致 ──
COOKIE_NAME = "zp_gate"
LOGIN_PATH = "/_gate/login"
LOGOUT_PATH = "/_gate/logout"
COOKIE_DAYS = 30


def _sign(secret: str, exp_ts: int) -> str:
    return hmac.new(secret.encode("utf-8"), str(exp_ts).encode("utf-8"), hashlib.sha256).hexdigest()


def _make_cookie_value(secret: str, days: int = COOKIE_DAYS) -> str:
    exp_ts = int(time.time()) + days * 86400
    return f"{exp_ts}.{_sign(secret, exp_ts)}"


def _verify_cookie_value(secret: str, value: str | None) -> bool:
    if not value or "." not in value:
        return False
    exp_str, _, sig = value.partition(".")
    try:
        exp_ts = int(exp_str)
    except ValueError:
        return False
    if exp_ts < int(time.time()):
        return False
    return hmac.compare_digest(sig, _sign(secret, exp_ts))


def _verify_auth_token(secret: str, token: str | None) -> bool:
    return bool(token) and hmac.compare_digest(token, secret)


def _parse_cookie_header(cookie_header: str | None, name: str) -> str | None:
    if not cookie_header:
        return None
    jar: SimpleCookie = SimpleCookie()
    try:
        jar.load(cookie_header)
    except Exception:
        return None
    morsel = jar.get(name)
    return morsel.value if morsel else None


def _safe_next(next_url: str | None) -> str:
    if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
        return "/"
    return next_url


def _login_page_html(next_url: str, *, error: bool = False) -> bytes:
    nxt = _safe_next(next_url)
    error_html = '<div class="err">口令不正确，请重新输入。</div>' if error else ""
    html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>访问口令 · AI 运营指挥中心</title>
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
  <h1>🔒 AI 运营指挥中心</h1>
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
    return html.encode("utf-8")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        self._zp_status = 200   # 队列 #112：由 send_response 覆写捕获，供访问日志使用
        super().__init__(*a, directory=ROOT, **k)

    def send_response(self, code, message=None):
        self._zp_status = code
        super().send_response(code, message)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # ── 门禁 ──────────────────────────────────────────────────────────────
    def _path_only(self) -> str:
        return urlsplit(self.path).path

    def _authorized(self) -> bool:
        if not GATE_PASSWORD:
            return True   # 未配置口令 → 门禁不生效（本地/无 .env 场景直接跑通）
        if _verify_auth_token(GATE_PASSWORD, self.headers.get("X-Auth-Token")):
            return True
        cookie_val = _parse_cookie_header(self.headers.get("Cookie"), COOKIE_NAME)
        return _verify_cookie_value(GATE_PASSWORD, cookie_val)

    def _redirect_to_login(self):
        nxt = quote(self.path, safe="")
        self.send_response(302)
        self.send_header("Location", f"{LOGIN_PATH}?next={nxt}")
        self.end_headers()

    def _serve_ping(self):
        body = json.dumps({"status": "ok", "service": "AI 运营指挥中心"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_login_get(self):
        qs = parse_qs(urlsplit(self.path).query)
        nxt = _safe_next((qs.get("next") or ["/"])[0])
        body = _login_page_html(nxt)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_login_post(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length).decode("utf-8", errors="replace") if length else ""
        form = parse_qs(raw)
        password = (form.get("password") or [""])[0]
        nxt = _safe_next((form.get("next") or ["/"])[0])
        if GATE_PASSWORD and hmac.compare_digest(password, GATE_PASSWORD):
            cookie_val = _make_cookie_value(GATE_PASSWORD)
            self.send_response(302)
            self.send_header("Location", nxt)
            self.send_header(
                "Set-Cookie",
                f"{COOKIE_NAME}={cookie_val}; Path=/; Max-Age={COOKIE_DAYS * 86400}; "
                "HttpOnly; SameSite=Lax",
            )
            self.end_headers()
            return
        body = _login_page_html(nxt, error=True)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_logout(self):
        self.send_response(302)
        self.send_header("Location", LOGIN_PATH)
        self.send_header("Set-Cookie", f"{COOKIE_NAME}=; Path=/; Max-Age=0")
        self.end_headers()

    def do_GET(self):
        path = self._path_only()
        try:
            if path == "/api/ping":
                return self._serve_ping()
            if path == LOGIN_PATH:
                return self._serve_login_get()
            if path == LOGOUT_PATH:
                return self._handle_logout()
            if not self._authorized():
                return self._redirect_to_login()
            super().do_GET()
        finally:
            _log_access("GET", path, self._zp_status, self.client_address[0])

    def do_HEAD(self):
        path = self._path_only()
        try:
            if path in (LOGIN_PATH, "/api/ping", LOGOUT_PATH):
                return self._serve_login_get()   # 简化处理：HEAD 探这几个路径场景极少
            if not self._authorized():
                return self._redirect_to_login()
            super().do_HEAD()
        finally:
            _log_access("HEAD", path, self._zp_status, self.client_address[0])

    def do_POST(self):
        path = self._path_only()
        try:
            if path == LOGIN_PATH:
                return self._handle_login_post()
            self.send_error(501, "Unsupported method (POST)")
        finally:
            _log_access("POST", path, self._zp_status, self.client_address[0])


if __name__ == "__main__":
    # 队列 #112 测试期间发现：PORT 此前在模块级读 sys.argv[1]，导致 import serve
    # 时若 sys.argv 携带其它参数（如 pytest 自身的命令行）会直接崩溃——PORT 只在
    # 本执行入口用到，移到这里既修掉这个隐患，也不改变命令行用法本身。
    PORT = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("CC_PORT", "8092"))
    os.chdir(ROOT)
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("AI 运营指挥中心 serving %s on 0.0.0.0:%d" % (ROOT, PORT), flush=True)
    print(f"  访问口令门禁：{'已启用（ZP_GATE_PASSWORD 已配置）' if GATE_PASSWORD else '未启用（未配置 ZP_GATE_PASSWORD，仅限本地/测试）'}", flush=True)
    httpd.serve_forever()
