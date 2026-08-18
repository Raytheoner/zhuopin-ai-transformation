"""FI1 对账一键运行 —— FeedSource → 引擎 → 分类 → 报告（+ 审计）。

用法（默认 mock 夹具）：
    python -m fi1.run                     # 跑 data/mock，打印摘要 + 写 reports/
    FI1_DATA_SOURCE=csv python -m fi1.run --csv-dir <ERP导出目录>   # 过渡期应急桥接真实数据

mock/csv 安全（不连真实库）；u9c 直读端点 404 时 fail-loud。报告 = AI 对账建议，非终局。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# —— worktree 隔离引导（队列 #300／#313 补漏）：把本 worktree 的平台底座与场景自身路径插到
# sys.path 最前，使 import 结果与全局 editable 安装当前指向谁无关。必须放在本文件
# 任何 zhuopin_platform / 场景包 import 之前。——
_HERE = Path(__file__).resolve()
for _p in (_HERE, *_HERE.parents):
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        for _entry in (_p / "5-平台底座" / "zhuopin_platform", _HERE.parent.parent):
            if str(_entry) not in sys.path:
                sys.path.insert(0, str(_entry))
        break
else:
    # 🔴 找不到仓库根标记时**不得硬失败**（2026-08-18 实测事故，队列 #345）：#300 要防的是
    # "N 个平等 worktree 共用一套全局 site-packages、谁装的 editable 指针谁说了算"——
    # **该前提只在开发机成立**。`.51` 的部署布局是扁平的 `C:/<svc>/app` ＋
    # `C:/<svc>/zhuopin_platform`（后者已由 deploy 脚本 pip install -e 进 venv，全机唯一
    # 一份、无歧义），**没有也不需要 `5-平台底座/` 这层目录**。原实现在此直接 raise，等于
    # 把入口在生产布局上钉死（现象：计划任务 LastResult=0 但进程秒退、端口无监听）。
    # ⇒ 找到标记 → 按 #300 前插（开发机，确定性优先）；找不到 → 只插自身包路径、平台底座
    # 交由环境解析（生产机，唯一一份）。**不引入静默失败**：环境里也没有 zhuopin_platform
    # 时仍然明确报错。——
    if str(_HERE.parent.parent) not in sys.path:
        sys.path.insert(0, str(_HERE.parent.parent))
    from importlib.util import find_spec
    if find_spec("zhuopin_platform") is None:
        raise RuntimeError(
            f"既未找到仓库根标记 5-平台底座/zhuopin_platform（从 {_HERE} 向上查找），"
            "环境中也没有可导入的 zhuopin_platform——请检查部署或安装平台底座包")

from zhuopin_platform.audit import AuditLogger

from . import config as _config
from .feed_source import FeedSource
from .reconcile_engine import compute_reconcile
from .recon_report import build_report
from .variance_classify import classify_all, rule_version

_ROOT = Path(__file__).resolve().parent.parent


def run(data_source: str | None = None, *, mock_dir: Path | None = None,
        csv_dir: Path | None = None, evaluator: str = "", period: str = "",
        audit=None) -> dict:
    """跑一轮对账，返回报告 dict。"""
    fs = FeedSource(data_source, mock_dir=mock_dir or _ROOT / "data" / "mock",
                    csv_dir=csv_dir, audit=None)
    outputs = fs.load_outputs()
    feeds = fs.load_feeds()
    product_ids = sorted({o.product_id for o in outputs})
    bom_rows, failed = fs.load_bom(product_ids)
    comp = compute_reconcile(bom_rows, outputs, feeds, bom_failed_product_ids=failed)
    classified = classify_all(comp.components)
    return build_report(
        classified, comp.incomplete_products,
        data_sources={"bom": fs.data_source, "output": fs.data_source, "feed": fs.data_source},
        rule_version=rule_version(), bom_source=fs.data_source,
        evaluator=evaluator, period=period, audit=audit,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="FI1 供应链仓库对账（内部对账 MVP）")
    ap.add_argument("--data-source", default=_config.DATA_SOURCE_DEFAULT, choices=["mock", "csv", "u9c"])
    ap.add_argument("--csv-dir", default=None, help="ERP 导出 CSV 目录（data_source=csv）")
    ap.add_argument("--evaluator", default="", help="L2 复核责任人（IATF 可归责）")
    args = ap.parse_args()

    reports_dir = _ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    audit = AuditLogger.jsonl(reports_dir / "fi1_audit.jsonl")
    rep = run(args.data_source, csv_dir=Path(args.csv_dir) if args.csv_dir else None,
              evaluator=args.evaluator, audit=audit)

    out_path = reports_dir / "fi1_reconcile_report.json"
    out_path.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")

    s = rep["summary"]
    print(f"FI1 对账（{rep['data_sources']['bom']}）规则版本 {rep['rule_version']}")
    print(f"  子件 {s['total']}：AI建议通过 {s['auto_suggest_pass']} / 需人工确认 {s['needs_review']} / 待人工核 {s['manual_check']}")
    print(f"  分类分布：{s['by_classification']}")
    print(f"  BOM 残缺成品：{s['incomplete_products']}")
    print(f"  {rep['disclaimer']}")
    print(f"  报告 → {out_path}")


if __name__ == "__main__":
    main()
