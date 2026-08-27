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

#: **已按 `.51` 实测核实，结论是「本入口确实一个凭据键都不需要」**（2026-08-27，OP-0827-B，
#: tasks 2.3.2／2.3.6 的 LAN 留步项已销）。判据见 SC8 `run_baoguan_web.py` 同名常量上方。
#:
#: 🔴 **空元组在此是一个经核查的结论，不是「还没填」**——判据＝`qd_b_gate/` 全包 `os.environ`／
#: `getenv` **零命中**（QD-B 只做本地立项书解析，不连任何外部系统）；`.51` 的 `C:\qd-b\.env`
#: 实测只有一个 `ZP_GATE_PASSWORD`，而它按判据属「缺了走既定默认路径」不声明。
#: 此后若本场景新增真凭据依赖，请同步补进本清单。
REQUIRED_ENV_KEYS: tuple[str, ...] = ()


def load_env() -> None:
    """读入本次运行该用的那份 `.env`（解析见 `zhuopin_platform.env_anchor`，队列 #354）。

    🔴 **原实现是「向上逐级找最近的 `.env`」**——从 linked worktree 跑时命中 worktree 自己那
    份陈旧副本、**且不报错**。收拢后由 `--git-common-dir` 规范化到主工作区；`.51` 扁平布局
    （无 git、无 marker）走部署根锚点，行为与此前一致。凭据只在 `.env`，不入库、不打印。
    """
    print(_resolve_and_load_env(__file__, required=REQUIRED_ENV_KEYS).describe())


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
