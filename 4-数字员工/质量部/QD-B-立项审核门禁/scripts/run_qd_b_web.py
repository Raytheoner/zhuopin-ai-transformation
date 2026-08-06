"""QD-B 立项审核门禁 —— 内网 Web 服务启动入口（极简版发布收口，任务 9.1）。

启动：
  python scripts/run_qd_b_web.py                  # 默认 0.0.0.0:8093
  QD_B_WEB_PORT=9000 python scripts/run_qd_b_web.py

红线：真实立项书（未脱敏）留 LAN 不入库；上传文件落 reports/uploads/（gitignore）；
仅 LAN 访问（无登录鉴权，同 SC8/命令中心惯例）；AI 不自动执行任何业务动作，
报告页显著标注"试用版"+ AI 预审建议非终局。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

SCENE = Path(__file__).resolve().parent.parent


def _find_env() -> Path | None:
    """从本脚本向上逐级查找最近的 `.env`（布局无关，同 SC8 run_baoguan_web.py 范式）。"""
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

    from qd_b_gate.webapp import create_app

    reports = SCENE / "reports"  # gitignore（含未脱敏立项书上传件 + 审计明细）
    upload_dir = reports / "uploads"
    audit_path = reports / "qd_b_web_audit.jsonl"
    port = int(os.environ.get("QD_B_WEB_PORT", "8093"))
    access_log_path = reports / "qd_b_http_requests.jsonl"  # 队列 #112 轻量访问日志

    app = create_app(upload_dir=upload_dir, audit_path=audit_path, access_log_path=access_log_path)

    print("QD-B 立项审核门禁 — Web 服务启动中…")
    print(f"  上传目录：{upload_dir}（git-ignored，含未脱敏立项书）")
    print(f"  审计日志：{audit_path}")
    print("  ⚠ 试用版·灰度：AI 预审建议，立项决策在评审委员会/PMO；不自动执行任何业务动作")
    print("  ⚠ 仅 LAN 内部访问（无登录鉴权）")
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
