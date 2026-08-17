"""税务导出 Excel 定时扫描 CLI（队列 #82 第2层，2026-08-10 build）。

计划任务专用入口（`register-tax-export-scan-task.ps1` 每日调度）——与手动 CLI
`scripts/ingest_tax_export.py`（Q3 拍板"不挂定时"，保留原样不改）并存：两者共享
同一 `--out-dir`/`--ledger`（内容哈希幂等，谁先跑到都一样，互不冲突）。本脚本
额外做手动 CLI 不做的事：文件级摄取失败（sheet 名/必需列不符、无法解析）与源头
断供（连续 N 个工作日无新文件）经群 webhook 告警 Shao Peishen，非零退出码，供计划
任务"上次运行结果"留痕（见 `fi2/tax_export_scan.py` 模块 docstring）。

**退出码语义**（计划任务 `LastTaskResult` 据此区分，勿合并）：
    0 = 扫描正常（有新文件摄取成功，或无新文件但未超断供阈值）
    1 = 扫描本身异常，或有文件级摄取失败——**我方机制出问题**，需查代码/连接/目录
    2 = 源头断供超阈值——**我方机制正常，是没有新文件来**，需人去问源头一声
两者性质完全不同、处置动作也完全不同，故不共用一个非零码。

用法（在 `.51` 服务器本机跑，可直接访问 `D:\\airead` 与 U9C 财务 API）：
    python scan_tax_export_scheduled.py --export-dir D:\\airead --out-dir C:\\fi2\\app\\data\\tax_export

本地测试（指向本地样本目录 + 本地已处理清单）：
    python scan_tax_export_scheduled.py --export-dir data/tax_export_samples \\
        --out-dir data/tax_export --ledger data/tax_export/.processed_exports.json
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys
from pathlib import Path

# —— worktree 隔离引导（队列 #300／#313 补漏）：把本 worktree 的平台底座与场景自身路径插到
# sys.path 最前，使 import 结果与全局 editable 安装当前指向谁无关。必须放在本文件
# 任何 zhuopin_platform / 场景包 import 之前（下方 main() 内的延迟 import 亦受此保护）。
# 找不到该标记（如 `.51` 等部署环境是扁平布局 C:\fi2\{app,zhuopin_platform}，没有
# 5-平台底座 这层嵌套）不视为致命错误——部署脚本已对两个包做过 editable install，
# 退化为跳过、交给正常 import 机制兜底，不阻断启动（同 #82 生产事故修复既有约定）。——
_HERE = Path(__file__).resolve()
for _p in (_HERE, *_HERE.parents):
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        for _entry in (_p / "5-平台底座" / "zhuopin_platform", _HERE.parent.parent):
            if str(_entry) not in sys.path:
                sys.path.insert(0, str(_entry))
        break

_ROOT = Path(__file__).resolve().parent.parent


def _find_env() -> Path | None:
    """从本脚本向上逐级查找最近的 `.env`（同 `scripts/ingest_tax_export.py` 既有范式）。"""
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
    load_env()
    ap = argparse.ArgumentParser(description="税务导出发票明细 Excel 定时扫描（队列 #82 第2层）")
    ap.add_argument("--export-dir", required=True, help="税务导出 Excel 所在目录（如 D:\\airead）")
    ap.add_argument("--out-dir", default=str(_ROOT / "data" / "tax_export"),
                     help="产出 invoice.csv 的目录（即传给 FeedSource 的 invoice_sample_dir）")
    ap.add_argument("--ledger", default=None,
                     help="已处理清单路径（默认 <out-dir>/.processed_exports.json）")
    ap.add_argument("--silence-workdays", type=int, default=None,
                     help="源头断供阈值：连续多少个工作日无新文件即告警（默认 3）")
    args = ap.parse_args()

    from fi2.tax_export_scan import SILENCE_WORKDAYS_DEFAULT, ScanFailedError, scan_once
    from zhuopin_platform.audit.sinks import JsonlSink
    from zhuopin_platform.shared_tools.connector_audit import ConnectorAudit
    from zhuopin_platform.shared_tools.erp_connector import ZpConnector

    out_dir = Path(args.out_dir)
    ledger_path = Path(args.ledger) if args.ledger else out_dir / ".processed_exports.json"

    reports_dir = _ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    trace = ConnectorAudit(sink=JsonlSink(reports_dir / "fi2_access_trace.jsonl"))
    conn = ZpConnector.from_env(audit=trace)

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    webhook_url = os.environ.get("WECOM_WEBHOOK_URL")

    silence_workdays = (args.silence_workdays if args.silence_workdays is not None
                        else SILENCE_WORKDAYS_DEFAULT)

    try:
        outcome = scan_once(args.export_dir, out_dir, ledger_path, conn, now=now,
                             webhook_url=webhook_url, silence_workdays=silence_workdays)
    except ScanFailedError as e:
        print(f"扫描异常：{e.outcome.scan_error}", file=sys.stderr)
        if e.outcome.alert_sent:
            print("已发送 webhook 告警。", file=sys.stderr)
        elif webhook_url:
            print(f"webhook 告警发送失败：{e.outcome.alert_error}", file=sys.stderr)
        else:
            print("WECOM_WEBHOOK_URL 未配置，未发送告警。", file=sys.stderr)
        return 1

    result = outcome.result
    print(f"新处理文件：{result.files_processed}")
    print(f"跳过（已处理过）：{result.files_skipped}")
    print(f"成功解析行数：{len(result.resolved_rows)}")
    print(f"未解析记录数：{len(result.diagnostics)}")
    for d in result.diagnostics:
        loc = f"{d.file}" + (f" 第{d.row_index}行" if d.row_index else "")
        print(f"  [{d.reason}] {loc}"
              + (f" 发票号={d.digital_invoice_no}" if d.digital_invoice_no else "")
              + (f" {d.detail}" if d.detail else ""))

    def _report_alert() -> None:
        if outcome.alert_sent:
            print("已发送 webhook 告警。", file=sys.stderr)
        elif webhook_url:
            print(f"webhook 告警发送失败：{outcome.alert_error}", file=sys.stderr)
        else:
            print("WECOM_WEBHOOK_URL 未配置，未发送告警。", file=sys.stderr)

    if outcome.file_level_failures:
        print(f"⚠️ 文件级摄取失败 {len(outcome.file_level_failures)} 处", file=sys.stderr)
        _report_alert()
        return 1

    if outcome.source_silence is not None:
        s = outcome.source_silence
        print(f"⚠️ 源头断供：已连续 {s.workdays_silent} 个工作日无新增导出文件"
              f"（阈值 {s.threshold}），最后一次成功摄取 {s.last_ingest_at}（UTC）。"
              "扫描机制本身正常，是源头没有新文件。", file=sys.stderr)
        _report_alert()
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
