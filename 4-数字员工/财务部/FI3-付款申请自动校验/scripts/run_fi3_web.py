"""FI3 门户页 —— Web 服务启动入口（档 3，队列 §一 `#613` 建页、`#615` 上线 `.51:8097`）。

启动：
  python scripts/run_fi3_web.py                  # 默认 127.0.0.1:8097（本机跑，不对外）
  FI3_WEB_PORT=9000 python scripts/run_fi3_web.py
  FI3_WEB_HOST=0.0.0.0 …                         # 仅 `.51` 部署由 deploy-server.ps1 生成的
                                                 # start-fi3.ps1 这样置；默认值不改

🔴 **默认只绑 127.0.0.1**：本机跑永不对外。`.51` 上以过渡期独立端口 8097 对外（`#615`，
Shao Peishen 2026-09-18 答 `a`，与 design D7 相反、先例＝SC2 8096；网关收编时回收），
防火墙入站规则与计划任务由 `deploy-server.ps1` 建，本文件不持有任何一项。

凭据：启动时经 `zhuopin_platform.env_anchor.load_env` 读入本次该用的 `.env`（`.51` 扁平布局
＝ `C:/fi3/.env`；monorepo ＝ 主工作区根 `.env`），供共享口令门禁 `ZP_GATE_PASSWORD`（`#160`）
取值。`required=()`：本页档 1 只读 mock、无必需键——门禁键缺失即门禁静默 no-op（部署标准
清单 §三⑥ 点名的静默失效形态），**由部署段冒烟三件套第 2 项（未登录 302）显式核对**，不靠报错。
🔴 只打印命中的 `.env` 路径，绝不回显键值。

红线：本页只读档 1 mock 数据，不接 U9C，不写回 ERP；页面首屏显著标注"mock 数据"。
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


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() in ("gbk", "gb2312", "gb18030"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    from zhuopin_platform.env_anchor import load_env
    print(load_env(__file__).describe())  # 只回报路径与键名，不含键值（env_anchor 硬约束）

    from fi3_payment_validation import config
    from fi3_payment_validation.webapp import create_app

    reports = SCENE / "reports"  # gitignore（含审计明细）
    host = os.environ.get("FI3_WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("FI3_WEB_PORT", "8097"))

    app = create_app(audit_path=reports / "fi3_web_audit.jsonl")

    print(f"{config.SERVICE_NAME} — 门户页启动中…（{config.ROUTE_PREFIX}）")
    print(f"  报告/审计目录：{reports}（git-ignored）")
    print("  ⚠ 档 1 mock 数据·非真实付款申请；付款执行永远由人在 U9C／银企系统完成")
    if host == "127.0.0.1":
        print("  ⚠ 只绑 127.0.0.1，不对 LAN 开放（.51 部署由 deploy-server.ps1 置 FI3_WEB_HOST=0.0.0.0）")
    print("  ⚠ 门禁＝共享口令 ZP_GATE_PASSWORD（未配置即无门禁，部署段冒烟第 2 项核对）")
    try:
        from waitress import serve
        print(f"\n[OK] waitress 生产模式 · http://{host}:{port}{config.ROUTE_PREFIX}/\n")
        serve(app, host=host, port=port, threads=4)
    except ImportError:
        print(f"\n[!] waitress 未安装，Flask 开发模式 · http://{host}:{port}{config.ROUTE_PREFIX}/\n")
        app.run(host=host, port=port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
