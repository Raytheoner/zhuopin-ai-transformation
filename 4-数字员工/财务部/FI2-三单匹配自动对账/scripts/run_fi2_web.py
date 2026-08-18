"""FI2 三单匹配自动对账 —— 内网 Web 服务启动入口（发布收口，队列 #140）。

启动：
  python scripts/run_fi2_web.py                  # 默认 0.0.0.0:8094
  FI2_WEB_PORT=9000 python scripts/run_fi2_web.py

红线：只读取数不写回 ERP；仅 LAN 访问（无登录鉴权，同 SC8/QD-B/命令中心惯例）；
报告页显著标注"试用版"+ AI 建议/预警非终局，未过账。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# —— 平台底座路径引导（队列 #345 收拢；唯一被允许的样板，实现见
# `5-平台底座/zhuopin_platform/zhuopin_platform/bootstrap.py`）。必须放在本文件任何
# zhuopin_platform / 场景包 import 之前。下方五行只负责让 bootstrap 自身可被 import、
# 不含任何判断分支；开发机 monorepo 与 `.51` 扁平部署两种布局的分歧由 ensure_paths 处理。——
_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, _HERE.parent.parent)  # noqa: E402

SCENE = Path(__file__).resolve().parent.parent


def _find_env() -> Path | None:
    """从本脚本向上逐级查找最近的 `.env`（布局无关，同 SC8/QD-B run_*_web.py 范式）。"""
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

    from fi2.webapp import create_app

    reports = SCENE / "reports"  # gitignore（含审计明细/访问痕迹）
    port = int(os.environ.get("FI2_WEB_PORT", "8094"))

    app = create_app(reports_dir=reports)

    print("FI2 三单匹配自动对账 — Web 服务启动中…")
    print(f"  报告/审计目录：{reports}（git-ignored）")
    print("  ⚠ 试用版·灰度：AI 建议/预警，未过账；结案与过账在财务人员")
    print("  ⚠ 只读取数，不写回 ERP；仅 LAN 内部访问（无登录鉴权）")
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
