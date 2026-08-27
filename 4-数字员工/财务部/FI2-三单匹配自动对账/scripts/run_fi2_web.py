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


from zhuopin_platform.env_anchor import load_env as _resolve_and_load_env  # noqa: E402

#: **已按 `.51` 实测填实**（2026-08-27，OP-0827-B，tasks 2.3.3／2.3.6 的 LAN 留步项已销）。
#: 判据见 SC8 `run_baoguan_web.py` 同名常量上方（缺了会抛异常的才声明）。
#:
#: 下列六个键经 `.51`（`C:/fi2/.env`）只读探测确认在位；缺任一即 `ZpConnector.from_env()`
#: 抛 `ValueError`，而 `fi2/run.py` 与 `fi2/feed_source.py` 的 `u9c` 源全靠它取 PO／AP／GRN。
#: ⚠️ **`.51` 上另有三个键刻意不进本清单**：`STOCK_API_BASE`／`STOCK_API_KEY`（`fi2/` 全包零
#: 命中，是同机其它场景的）、`WECOM_WEBHOOK_URL_OPS`（属定时扫描 `scan_tax_export_scheduled.py`
#: 的告警去向，**不是本 Web 服务的依赖**——把它声明在这里会让「webhook 没配」变成「看板起不来」）。
REQUIRED_ENV_KEYS: tuple[str, ...] = (
    "U9C_API_BASE", "U9C_USER_CODE", "U9C_ENT_CODE",
    "U9C_ORG_CODE", "U9C_CLIENT_ID", "U9C_CLIENT_SECRET",
)


def load_env() -> None:
    """读入本次运行该用的那份 `.env`（解析见 `zhuopin_platform.env_anchor`，队列 #354）。

    🔴 **原实现是「向上逐级找最近的 `.env`」**——本文件正是 FI2 那一族的上游（`ingest_tax_export.py`
    与 `scan_tax_export_scheduled.py` 的 docstring 逐字自陈抄它）。从 linked worktree 跑时命中
    worktree 自己那份陈旧副本、**且不报错**。收拢后由 `--git-common-dir` 规范化到主工作区。
    凭据只在 `.env`，不入库、不打印。
    """
    print(_resolve_and_load_env(__file__, required=REQUIRED_ENV_KEYS).describe())


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
