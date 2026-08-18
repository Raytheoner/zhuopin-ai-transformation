"""SC2 采购周报服务入口 / CLI。

用法：
    python run_sc2.py serve --mode mock            # 起服务（过渡期端口 8095）
    python run_sc2.py report --mode real           # 生成一期周报到 stdout 并存快照
    python run_sc2.py probe                        # F14 端点参数名对照取证（需真实网络）
"""
from __future__ import annotations

# —— worktree 隔离引导（队列 #300）：把本 worktree 的平台底座与场景自身路径插到
# sys.path 最前，使 import 结果与全局 editable 安装当前指向谁无关。必须放在本文件
# 任何 zhuopin_platform / 场景包 import 之前。——
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
for _p in (_HERE, *_HERE.parents):
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        for _entry in (_p / "5-平台底座" / "zhuopin_platform", _HERE.parent):
            if str(_entry) not in sys.path:
                sys.path.insert(0, str(_entry))
        break
else:
    raise RuntimeError(f"未找到仓库根标记 5-平台底座/zhuopin_platform（从 {_HERE} 向上查找）")

import argparse  # noqa: E402
import os  # noqa: E402
from datetime import date  # noqa: E402

from sc2 import config  # noqa: E402


def load_env() -> None:
    """把最近的 `.env` 读入 `os.environ`（已存在的不覆盖）。

    与 SC8 `scripts/run_baoguan_web.py::load_env` 同一模式（向上逐级查找、纯标准库、
    不新增依赖），使笔记本 monorepo 布局与 `.51` 扁平部署布局都能命中。
    🔴 **凭据只在 `.env`，不入库、不打印**。
    """
    here = Path(__file__).resolve()
    for d in (here.parent, *here.parents):
        cand = d / ".env"
        if not cand.exists():
            continue
        for line in cand.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        return


def _base_date(arg: str | None) -> date:
    return date.fromisoformat(arg) if arg else date.today()


def cmd_serve(args) -> int:
    from sc2.webapp import create_app

    app = create_app(base_date=_base_date(args.base), mode=args.mode)
    # 绑定 0.0.0.0 供 LAN 访问；对外暴露由共享口令门禁把守（ZP_GATE_PASSWORD）。
    app.run(host="0.0.0.0", port=args.port)
    return 0


def cmd_report(args) -> int:
    from sc2.report import build_report, render_text, save_snapshot
    from sc2.sources import build_feed
    from sc2.windows import build_windows

    windows = build_windows(_base_date(args.base))
    feed = build_feed(args.mode)
    if getattr(args, "max_status_materials", None) is not None and hasattr(
            feed, "max_status_materials"):
        feed.max_status_materials = args.max_status_materials
    report = build_report(feed.fetch(windows), windows)
    print(render_text(report))
    path = save_snapshot(report)
    print(f"\n[快照] {path}", file=sys.stderr)
    return 0


def cmd_probe(args) -> int:
    """F14 参数名对照取证（design D20）。

    **一次性取证脚本，不是常驻单测**——它需要真实网络与凭据，进不了 CI。
    结论请手工抄进场景 CLAUDE.md。
    """
    from sc2.sources import probe_endpoint_filter
    from zhuopin_platform.audit.sinks import JsonlSink
    from zhuopin_platform.shared_tools.connector_audit import ConnectorAudit
    from zhuopin_platform.shared_tools.erp_connector.connector import ZpConnector

    # 注入 audit：真实业务库访问必须留痕（IATF 可追溯红线）。
    erp = ZpConnector.from_env(audit=ConnectorAudit(JsonlSink(config.connector_trace_path())))
    verdict = probe_endpoint_filter(
        query_ok=lambda: erp._zp_post("/api/ZpViewPurOrder/Query"),
        # 故意拼错参数名：已知同族端点 POChange/Query 在此情形下**静默返回全表**
        query_bad_param=lambda: erp._zp_post("/api/ZpViewPurOrder/Query",
                                             {"itemCodeXX": "__NOT_EXIST__"}),
    )
    print(f"ZpViewPurOrder/Query 过滤可信度：{verdict}")
    if verdict == "filter_untrusted":
        print("⚠️ 该端点参数名拼错时静默返回全表 —— 取数后必须按业务字段二次过滤。")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="SC2 采购周报自动生成")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="启动 Web 服务")
    s.add_argument("--mode", choices=("mock", "real"), default="mock")
    s.add_argument("--port", type=int, default=config.DEFAULT_PORT)
    s.add_argument("--base", help="基准日期 YYYY-MM-DD，缺省今天")
    s.set_defaults(func=cmd_serve)

    r = sub.add_parser("report", help="生成一期周报")
    r.add_argument("--mode", choices=("mock", "real"), default="mock")
    r.add_argument("--base", help="基准日期 YYYY-MM-DD，缺省今天")
    r.add_argument("--max-status-materials", type=int, default=None,
                   help="行级状态取数的料号上限（D17 缓解；0=不限，缺省 200）")
    r.set_defaults(func=cmd_report)

    pr = sub.add_parser("probe", help="F14 端点参数名对照取证（需真实网络）")
    pr.set_defaults(func=cmd_probe)

    args = p.parse_args(argv)
    load_env()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
