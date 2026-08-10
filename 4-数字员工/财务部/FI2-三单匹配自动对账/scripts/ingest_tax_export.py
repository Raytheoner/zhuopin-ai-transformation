"""税务导出发票明细 Excel 摄取 CLI（队列 #295，design：fi2-tax-export-ingest）。

手动/按需触发（Q3 默认(a)，不挂定时——第 2 层定时扫描留待后置）。产出的
`invoice.csv` 落 `--out-dir`，供既有 `FeedSource(invoice_sample_dir=...)` 通道
原样消费，`feed_source.py` 本身零改动。

用法（在 `.51` 服务器本机跑，可直接访问 `D:\\airead` 与 U9C 财务 API）：
    python -m scripts.ingest_tax_export --export-dir D:\\airead --out-dir C:\\fi2\\app\\data\\tax_export

本地测试（指向本地样本目录 + 本地已处理清单）：
    python -m scripts.ingest_tax_export --export-dir data/tax_export_samples \\
        --out-dir data/tax_export --ledger data/tax_export/.processed.json
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
# 退化为跳过、交给正常 import 机制兜底，不阻断启动（2026-08-10 队列 #82 生产事故修复）。——
_HERE = Path(__file__).resolve()
for _p in (_HERE, *_HERE.parents):
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        for _entry in (_p / "5-平台底座" / "zhuopin_platform", _HERE.parent.parent):
            if str(_entry) not in sys.path:
                sys.path.insert(0, str(_entry))
        break

_ROOT = Path(__file__).resolve().parent.parent


def _find_env() -> Path | None:
    """从本脚本向上逐级查找最近的 `.env`（同 `scripts/run_fi2_web.py` 既有范式）。"""
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
    ap = argparse.ArgumentParser(description="税务导出发票明细 Excel 摄取（队列 #295）")
    ap.add_argument("--export-dir", required=True, help="税务导出 Excel 所在目录（如 D:\\airead）")
    ap.add_argument("--out-dir", default=str(_ROOT / "data" / "tax_export"),
                     help="产出 invoice.csv 的目录（即传给 FeedSource 的 invoice_sample_dir）")
    ap.add_argument("--ledger", default=None,
                     help="已处理清单路径（默认 <out-dir>/.processed_exports.json）")
    args = ap.parse_args()

    from fi2.tax_export_ingest import ingest_directory, write_invoice_csv
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
    result = ingest_directory(args.export_dir, ledger_path, conn, now=now)

    if result.resolved_rows:
        write_invoice_csv(result.resolved_rows, out_dir / "invoice.csv")

    print(f"新处理文件：{result.files_processed}")
    print(f"跳过（已处理过）：{result.files_skipped}")
    print(f"成功解析行数：{len(result.resolved_rows)}")
    print(f"未解析记录数：{len(result.diagnostics)}")
    for d in result.diagnostics:
        loc = f"{d.file}" + (f" 第{d.row_index}行" if d.row_index else "")
        print(f"  [{d.reason}] {loc}"
              + (f" 发票号={d.digital_invoice_no}" if d.digital_invoice_no else "")
              + (f" {d.detail}" if d.detail else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
