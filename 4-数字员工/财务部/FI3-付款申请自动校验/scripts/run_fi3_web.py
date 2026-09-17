"""FI3 门户页 —— Web 服务启动入口（档 3，队列 §一 `#613`）。

启动：
  python scripts/run_fi3_web.py                  # 默认 127.0.0.1:8097
  FI3_WEB_PORT=9000 python scripts/run_fi3_web.py

🔴 **默认只绑 127.0.0.1、不建防火墙规则**（design D7「不新起端口」；SC2 8096 那次的过渡期
豁免本场景不适用，见 `fi3_payment_validation/webapp.py` 模块说明）——本进程只供同机的统一
门户网关（`.51:8090`）反向代理访问；真正对外挂载留待 tasks 5.2 `.51` 部署（本次不做，
off-LAN 留步，见场景 CLAUDE.md「下一步」段）。

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

    from fi3_payment_validation import config
    from fi3_payment_validation.webapp import create_app

    reports = SCENE / "reports"  # gitignore（含审计明细）
    host = os.environ.get("FI3_WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("FI3_WEB_PORT", "8097"))

    app = create_app(audit_path=reports / "fi3_web_audit.jsonl")

    print(f"{config.SERVICE_NAME} — 门户页启动中…（{config.ROUTE_PREFIX}）")
    print(f"  报告/审计目录：{reports}（git-ignored）")
    print("  ⚠ 档 1 mock 数据·非真实付款申请；付款执行永远由人在 U9C／银企系统完成")
    print("  ⚠ 默认只绑 127.0.0.1，不对 LAN 开放——对外访问走 .51:8090 统一门户网关（tasks 5.2）")
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
