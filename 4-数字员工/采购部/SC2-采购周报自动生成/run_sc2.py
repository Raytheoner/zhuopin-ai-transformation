"""SC2 采购周报服务入口 / CLI。

用法：
    python run_sc2.py serve --mode mock            # 起服务（过渡期端口 8096）
    python run_sc2.py report --mode real           # 生成一期周报到 stdout 并存快照
    python run_sc2.py probe                        # F14 端点参数名对照取证（需真实网络）
"""
from __future__ import annotations

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
ensure_paths(__file__, _HERE.parent)  # noqa: E402

import argparse  # noqa: E402
import os  # noqa: E402
from datetime import date  # noqa: E402

from sc2 import config  # noqa: E402


from zhuopin_platform.env_anchor import load_env as _resolve_and_load_env  # noqa: E402

#: **已按 `.51` 实测填实**（2026-08-27，OP-0827-B，tasks 2.3.5／2.3.6 的 LAN 留步项已销）。
#: 判据见 SC8 `run_baoguan_web.py` 同名常量上方（缺了会抛异常的才声明；`ZP_GATE_PASSWORD`
#: 缺失时门禁按设计自动跳过，属既定默认路径，不声明）。
#:
#: 🔴 **本入口是四个里唯一一个「服务入口兼 CLI」，故必需键与 `--mode` 绑定，不是一个定值**——
#: `load_env()` 在 argparse **分发之前**跑（见 `main()`），若把 `U9C_*` 无条件声明成必需，
#: `--mode mock` 就再也不能在没有凭据的机器上跑了，而 mock 模式存在的意义恰恰是免凭据。
#: `.51` 两个计划任务（`start-sc2.ps1` ＝ `serve --mode real`、`autopush-sc2.ps1` ＝
#: `autopush --mode real`）**都走 real**，所以生产侧一个都没漏声明。
REQUIRED_ENV_KEYS: tuple[str, ...] = ()

#: real 模式追加的必需键：`sc2/sources.py::build_real_feed` 用 `ZpConnector.from_env()`
#: 取数，缺任一即抛 `ValueError`。六个键均经 `.51`（`C:/sc2/.env`）只读探测确认在位。
REQUIRED_ENV_KEYS_REAL: tuple[str, ...] = REQUIRED_ENV_KEYS + (
    "U9C_API_BASE", "U9C_USER_CODE", "U9C_ENT_CODE",
    "U9C_ORG_CODE", "U9C_CLIENT_ID", "U9C_CLIENT_SECRET",
)


def load_env(mode: str | None = None) -> None:
    """读入本次运行该用的那份 `.env`（解析见 `zhuopin_platform.env_anchor`，队列 #354）。

    `mode` ＝ 本次子命令的 `--mode`（`probe` 没有这个参数 ⇒ `None`）。`"real"` 时用
    `REQUIRED_ENV_KEYS_REAL`，其余用 `REQUIRED_ENV_KEYS`——理由见上方常量注释。

    🔴 **原实现是「向上逐级找最近的 `.env`」的内联变体**（9 份手抄副本里唯一没有 `_find_env`
    函数的那份，docstring 自陈抄 SC8）——从 linked worktree 跑时命中 worktree 自己那份陈旧
    副本、**且不报错**。收拢后由 `--git-common-dir` 规范化到主工作区；扁平部署布局走部署根
    锚点，两种布局仍都能命中。🔴 **凭据只在 `.env`，不入库、不打印**。
    """
    required = REQUIRED_ENV_KEYS_REAL if mode == "real" else REQUIRED_ENV_KEYS
    print(_resolve_and_load_env(__file__, required=required).describe())


def _base_date(arg: str | None) -> date:
    return date.fromisoformat(arg) if arg else date.today()


def cmd_serve(args) -> int:
    from sc2.webapp import create_app

    app = create_app(base_date=_base_date(args.base), mode=args.mode,
                     max_status_materials=args.max_status_materials)
    # 绑定 0.0.0.0 供 LAN 访问；对外暴露由共享口令门禁把守（ZP_GATE_PASSWORD）。
    #
    # 🔴 长开服务走 waitress，不用 Flask 开发服务器（同 QD-B/SC8 惯例）：`app.run()`
    # 单线程、无请求排队，而本场景的 `POST /api/refresh` 真实模式要跑约 2 分 20 秒，
    # 期间开发服务器会把同时到达的页面请求全部堵死——看起来就是「服务挂了」。
    print(f"SC2 采购周报 — 服务启动中（mode={args.mode}, 路由前缀 {config.ROUTE_PREFIX}）…")
    print("  ⚠ 仅 LAN 内部访问，由共享口令门禁 ZP_GATE_PASSWORD 把守")
    print("  ⚠ L3：AI 自动汇总，经人工「确认发布」后方可对外推送")
    try:
        from waitress import serve
        print(f"\n[OK] waitress 生产模式 · http://0.0.0.0:{args.port}{config.ROUTE_PREFIX}/\n")
        serve(app, host="0.0.0.0", port=args.port, threads=4)
    except ImportError:
        print(f"\n[!] waitress 未安装，Flask 开发模式 · http://0.0.0.0:{args.port}{config.ROUTE_PREFIX}/\n")
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


def cmd_autopush(args) -> int:
    """周五 20:00 自动生成本周周报并推群（队列 §四 `#89`，Shao Peishen 2026-08-22 拍板 (a)）。

    姚祖怡原话：「周五晚 8 点自动给出本周的，出来后挂到页面上，**同步推到群里**」。
    ⇒ 三件事一次做完：**取数生成 → 落快照（页面即刻可见）→ 写 outbox（中继代发）**。

    🔴 **不问确认**：确认发布前置已按拍板取消（见 `sc2/notify.py` 模块头）。
    🔴 **幂等**：同一期重复跑不会发第二遍（`ReviewStore.mark_pushed`），
    故计划任务重试、手工补跑都安全。

    ⚠️ **基准日就是「今天」，即本周**——他要的是本周的。周五跑时本周只过了 5/7 天，
    周报顶部会自动带上 O-7 那句「本周窗口尚未走完」的声明（`report._incomplete_week_note`）。
    **那句声明不是噪音，正是让他不会把结构性偏低当成采购塌方**，不要因为「难看」去掉它。
    """
    from sc2 import notify, outbox
    from sc2.report import build_report, render_text, save_snapshot
    from sc2.review import ReviewStore
    from sc2.sources import build_feed
    from sc2.windows import build_windows

    base = _base_date(args.base)
    windows = build_windows(base)
    feed = build_feed(args.mode)
    if hasattr(feed, "max_status_materials"):
        # 与 serve 同口径：不截断，否则在途类指标偏高（见 build_parser 注释）。
        feed.max_status_materials = args.max_status_materials
    report = build_report(feed.fetch(windows), windows)

    store = ReviewStore()
    store.register(report)
    snapshot = save_snapshot(report)
    print(f"[快照] {snapshot}")

    if args.no_push:
        print("[跳过推送] --no-push")
        return 0

    sent = notify.push(report.period, text=render_text(report), store=store)
    if sent:
        print(f"[已入 outbox] {report.period} → {outbox.outbox_path()}")
    else:
        print(f"[跳过] {report.period} 此前已推送过（幂等）")

    # 🔴 积压必须被打出来。写进 outbox ≠ 群里已经看到——中继在笔记本上，
    # 笔记本关机期间消息只是积压。不打这一行，就会重演 `#82`：
    # 机制天天在跑、一条都没真发出去，而没有人察觉。
    backlog = outbox.pending()
    print(f"[outbox 积压] {backlog} 条待中继取走"
          + ("" if backlog == 0 else " —— 若长期不降，说明笔记本侧中继没在跑"))
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


def build_parser() -> argparse.ArgumentParser:
    """构造 CLI parser。抽出来是为了能被单测直接检查缺省值——服务端缺省
    `--max-status-materials 0` 是一条会影响页面数字的部署约定，值得有测试守住。"""
    p = argparse.ArgumentParser(description="SC2 采购周报自动生成")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="启动 Web 服务")
    s.add_argument("--mode", choices=("mock", "real"), default="mock")
    s.add_argument("--port", type=int, default=config.DEFAULT_PORT)
    s.add_argument("--base", help="基准日期 YYYY-MM-DD，缺省今天")
    # 🔴 服务端缺省 0（不限）而非 RealFeed 的 200：截断会让未取到状态的行按「状态
    # 未知」计入在途，在途类指标偏高——那是页面上要给姚祖怡看的数。慢由 D21 兜。
    s.add_argument("--max-status-materials", type=int, default=0,
                   help="行级状态取数的料号上限（0=不限，服务端缺省）")
    s.set_defaults(func=cmd_serve)

    r = sub.add_parser("report", help="生成一期周报")
    r.add_argument("--mode", choices=("mock", "real"), default="mock")
    r.add_argument("--base", help="基准日期 YYYY-MM-DD，缺省今天")
    r.add_argument("--max-status-materials", type=int, default=None,
                   help="行级状态取数的料号上限（D17 缓解；0=不限，缺省 200）")
    r.set_defaults(func=cmd_report)

    a = sub.add_parser("autopush", help="生成本周周报并推群（周五 20:00 计划任务调用）")
    # 🔴 缺省 real：这条命令的唯一调用方是 `.51` 上的计划任务，跑 mock 等于每周
    # 往群里发一份假数据。与 serve/report 缺省 mock 刻意不同——那两个是人手工跑的。
    a.add_argument("--mode", choices=("mock", "real"), default="real")
    a.add_argument("--base", help="基准日期 YYYY-MM-DD，缺省今天（＝本周）")
    a.add_argument("--max-status-materials", type=int, default=0,
                   help="行级状态取数的料号上限（0=不限，与 serve 同口径）")
    a.add_argument("--no-push", action="store_true",
                   help="只生成与落快照，不写 outbox（首次上线演练用）")
    a.set_defaults(func=cmd_autopush)

    pr = sub.add_parser("probe", help="F14 端点参数名对照取证（需真实网络）")
    pr.set_defaults(func=cmd_probe)
    return p


def main(argv=None) -> int:
    # `.51` 的计划任务跑在 GBK 控制台下，print 中文会 UnicodeEncodeError 直接崩掉
    # 服务进程（表现同「计划任务 LastResult=0 而进程秒退」）。同 QD-B 处置。
    if sys.stdout.encoding and sys.stdout.encoding.lower() in ("gbk", "gb2312", "gb18030"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)
    load_env(getattr(args, "mode", None))
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
