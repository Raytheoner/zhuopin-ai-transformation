"""成品保供预警看板 —— 真实数据 runner（FO + U9C BOM + 携客云承诺 → 保供看板）。

数据流（全真实源，密钥轮换后到位）：
  ① FO 预测订单（成品保供需求 + 计划出货日）  ← load_real_orders（FO API，LAN）
  ② 成品 → 直接子件 BOM                        ← load_real_bom（U9C /BOM/Query）
  ③ 子件供应商承诺交期（分层取数）            ← load_srm_deliveries（携客云 /purchase/answer）
  ④ 无答复子件 → max(出货日,今天)+30           ← baoguan.assess_supply_risk
  → 齐料日 vs 计划出货日 → 🔴/🟡/🟢 三色看板

红线：看板含真实客户名 → 只写 reports/（git-ignored），绝不入库；本看板为内部保供运维，不对客
（CUSTOMER_OUTBOUND_ENABLED 全程关，本 runner 不触发任何对客外发）。real 缺端点 fail-loud。

用法：
  SC8_DATA_SOURCE=real python scripts/run_baoguan_dashboard.py [--limit N]
  （凭据从最近的 .env 读入，布局无关——见 load_env()；--limit 小样本验证，不放量）
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
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


from zhuopin_platform.env_anchor import load_env as _resolve_and_load_env  # noqa: E402

#: 本 CLI 必需的凭据键（队列 #354 决策点 4 ＝ (c)）。一次性 CLI，改错当场可见，
#: 故与两个同族 CLI 一样显式声明——不像常驻服务那样要为「起不来」留余地。
REQUIRED_ENV_KEYS = ("FO_API_BASE", "FORECAST_API_KEY", "U9C_API_BASE", "XKY_API_BASE")


def load_env() -> None:
    """读入本次运行该用的那份 `.env`（解析见 `zhuopin_platform.env_anchor`，队列 #354）。

    🔴 **本文件两副面孔都亲历过**：最早是 `REPO = Path(__file__).resolve().parents[4]`——
    `.51` 扁平布局 `C:/baoguan/app/scripts/` 向上只有 3 层，`parents[4]` 直接 `IndexError: 4`，
    **本 CLI 因此在 `.51` 上从未可用过**（没人报，因为没人从这条入口跑过）；2026-08-24 改并入
    「向上找最近的 `.env`」后越界没了，**却换上了另一副面孔**：从 worktree 内跑会命中该
    worktree 自己的陈旧副本、且不报错。本次收拢两副面孔一起挡掉——`--git-common-dir` 规范化
    到主工作区，`.51` 扁平布局走部署根锚点（无 git 的退化路径已配单测）。
    凭据只在 `.env`，不入库、不打印。
    """
    print(_resolve_and_load_env(__file__, required=REQUIRED_ENV_KEYS).describe())


def main() -> int:
    # Windows GBK 控制台强制 UTF-8 输出，避免三色徽标 emoji 触发 UnicodeEncodeError
    # （与同目录 `run_baoguan_web.py` 同一处置）。🔴 **这是 `.51` 上挡住本 CLI 的第二道坎**：
    # 修掉 `parents[4]` 越界后真机复跑，取数三步全通（FO/BOM/SRM 都拿到了真实数据、
    # 看板文件也已落盘），却在最后一行汇总 `print` 上炸 —— `'gbk' codec can't encode
    # character '\U0001f534'`，退出码 1。**一个入口从未被跑过时，坏掉的往往不止一处；
    # 修好第一处只会让你看见第二处。**
    if sys.stdout.encoding and sys.stdout.encoding.lower() in ("gbk", "gb2312", "gb18030"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description="成品保供预警看板（真实数据）")
    ap.add_argument("--limit", type=int, default=None, help="只取前 N 条成品行（小样本验证）")
    args = ap.parse_args()

    load_env()

    from sc8 import config
    if config.data_source_mode() != "real":
        print("✗ 需 SC8_DATA_SOURCE=real 才跑真实保供看板（红线 §7.1：真实库须显式开启）。", file=sys.stderr)
        return 2

    from zhuopin_platform.audit import AuditLogger
    from zhuopin_platform.audit.sinks import JsonlSink
    from zhuopin_platform.shared_tools.connector_audit import ConnectorAudit

    reports = Path(__file__).resolve().parent.parent / "reports"   # **/reports/ 已 gitignore
    reports.mkdir(parents=True, exist_ok=True)
    trace = ConnectorAudit(sink=JsonlSink(reports / "baoguan_access_trace.jsonl"))
    audit = AuditLogger(sink=JsonlSink(reports / "baoguan_audit.jsonl"))

    from sc8.baoguan import (RISK_GAP, RISK_GREEN, RISK_RED, RISK_YELLOW,
                             build_dashboard, render_html, render_markdown)
    from sc8.sources import load_real_bom, load_real_orders, load_srm_deliveries

    today = date.today()
    fo_base = os.environ.get("FO_API_BASE")
    ops_hook = os.environ.get("SC8_FO_OPS_WEBHOOK_URL") or os.environ.get("WECOM_WEBHOOK_URL")
    # 默认只取已审核 FO（status=2，单据头口径）；置 SC8_FO_STATUS=all 可不过滤。
    # 行级"关闭"由 load_real_orders 内部按 LineStatus 过滤，见其 docstring（队列 #173）。
    fo_status = os.environ.get("SC8_FO_STATUS", "2")
    fo_status = None if fo_status.lower() == "all" else fo_status

    # ① 真实成品保供需求（FO 不可达 → fail-loud + 内部运维告警，不回退 mock）
    orders = load_real_orders(api_base=fo_base, limit=args.limit, audit=trace,
                              ops_webhook_url=ops_hook, status=fo_status)
    print(f"FO 成品行：{len(orders)} 条（status={fo_status or 'all'}）")

    # ② 真实 BOM（成品 → 直接子件）
    product_ids = list(dict.fromkeys(o.item_code for o in orders))
    bom = load_real_bom(product_ids, max_depth=1, audit=trace)
    components = {r.component_id for r in bom if r.level == 1}
    print(f"成品 {len(product_ids)} 个 → 直接子件 {len(components)} 个（BOM 行 {len(bom)}）")

    # ③ 真实承诺交期（分层取数：/purchase/answer 权威 > 看板辅助 > 无答复兜底）
    srm = load_srm_deliveries("real", materials=components, audit=trace)
    print(f"携客云承诺命中子件：{len(srm)} / {len(components)}（其余走无答复 +{config.NO_FEEDBACK_LEAD_DAYS}）")

    # ④ 保供齐套 → 三色看板（HTML 主看板 + markdown 文本副本，均 git-ignored）
    rows = build_dashboard(orders, bom, srm, today=today)
    out_html = reports / f"baoguan_dashboard_{today.isoformat()}.html"
    out_html.write_text(render_html(rows, today=today), encoding="utf-8")
    out_md = reports / f"baoguan_dashboard_{today.isoformat()}.md"
    out_md.write_text(render_markdown(rows, today=today), encoding="utf-8")

    n_red = sum(1 for r in rows if r.risk == RISK_RED)
    n_gap = sum(1 for r in rows if r.risk == RISK_GAP)
    n_yel = sum(1 for r in rows if r.risk == RISK_YELLOW)
    n_grn = sum(1 for r in rows if r.risk == RISK_GREEN)
    print(f"\n保供看板：🔴 真延期 {n_red} / 🟠 待催 {n_gap} / 🟡 偏紧 {n_yel} / 🟢 按期 {n_grn}（共 {len(rows)} 行）")
    print(f"HTML 看板（浏览器打开，git-ignored）：{out_html}")
    print(f"markdown 副本：{out_md}")
    # 红灯成品料号摘要（料号属内部，不含客户名/交期细节）
    red_ids = sorted({r.product_id for r in rows if r.risk == RISK_RED})
    if red_ids:
        print(f"🔴 成品料号：{', '.join(red_ids[:20])}{' …' if len(red_ids) > 20 else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
