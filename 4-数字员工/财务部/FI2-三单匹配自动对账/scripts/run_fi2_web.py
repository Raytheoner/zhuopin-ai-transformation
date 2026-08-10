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

# —— worktree 隔离引导（队列 #300）：把本 worktree 的平台底座与场景自身路径插到
# sys.path 最前，使 import 结果与全局 editable 安装当前指向谁无关。必须放在本文件
# 任何 zhuopin_platform / 场景包 import 之前（下方 main() 内的延迟 import 亦受此保护）。
# 找不到该标记（如 `.51` 等部署环境是扁平布局 C:\fi2\{app,zhuopin_platform}，没有
# 5-平台底座 这层嵌套）不视为致命错误——部署脚本已对两个包做过 editable install，
# 退化为跳过、交给正常 import 机制兜底，不阻断启动（2026-08-10 队列 #82 生产事故修复）。——
_HERE = Path(__file__).resolve()
for _p in (_HERE, *_HERE.parents):
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        for _entry in (_p / "5-平台底座" / "zhuopin_platform", _HERE.parent.parent):
            if str(_entry) not in sys.path:
                sys.path.insert(0, str(_entry))
        break

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
