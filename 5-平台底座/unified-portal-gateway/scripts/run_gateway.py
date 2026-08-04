"""统一门户网关 —— 内网 Web 服务启动入口（队列 #162，决策件§六线②地基线）。

启动：
  python scripts/run_gateway.py                  # 默认 0.0.0.0:8090
  PORTAL_GATEWAY_PORT=9000 python scripts/run_gateway.py

必须配置 `PORTAL_GATEWAY_SESSION_SECRET`（会话签名密钥，未配置直接拒绝启动，
见 webapp.py::_resolve_session_secret）。企微 OAuth/mock 登录/应急通道均按
各自环境变量按需启用，见 sso.py 模块说明。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

SCENE = Path(__file__).resolve().parent.parent


def _find_env() -> Path | None:
    here = Path(__file__).resolve()
    for d in (here.parent, *here.parents):
        cand = d / ".env"
        if cand.exists():
            return cand
    return None


def load_env() -> None:
    env = _find_env()
    if not env:
        return
    for line in env.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() in ("gbk", "gb2312", "gb18030"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    load_env()

    from portal_gateway import sso
    from portal_gateway.webapp import create_app

    reports = SCENE / "reports"  # gitignore（含访问 userid 记录）
    audit_path = reports / "portal_access.jsonl"
    port = int(os.environ.get("PORTAL_GATEWAY_PORT", "8090"))

    try:
        app = create_app(audit_path=audit_path)
    except RuntimeError as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        return 1

    print("统一门户网关 — Web 服务启动中…")
    print(f"  访问日志：{audit_path}（git-ignored，含 userid 访问记录）")
    print(f"  企微 OAuth：{'已配置' if sso.load_wecom_oauth_config() else '未配置（企微凭据申请见队列 #240）'}")
    print(f"  开发/试点 mock 登录：{'已启用 ⚠️' if sso.mock_login_enabled() else '未启用'}")
    print(f"  应急本地口令通道：{'已启用（不对外公示）' if sso.emergency_login_enabled() else '未启用'}")
    print("  ⚠ 本次试点路由：仅门户首页（/ → 8092），存量四服务收编另行安排（决策件线③）")
    try:
        from waitress import serve
        print(f"\n[OK] waitress 生产模式 · http://0.0.0.0:{port}/\n")
        serve(app, host="0.0.0.0", port=port, threads=4)
    except ImportError:
        print(f"\n[!] waitress 未安装，Flask 开发模式 · http://0.0.0.0:{port}/\n")
        app.run(host="0.0.0.0", port=port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
